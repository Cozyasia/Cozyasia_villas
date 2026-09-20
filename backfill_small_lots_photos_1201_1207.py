# -*- coding: utf-8 -*-
"""Gated, idempotent photo backfill for Cozy Asia small-channel lots 1201-1207.

probe: read-only source/reference verification.
apply: strict source guard -> Drive upload/public permission -> Telegram caption edit/readback.
Normal service starts immediately; maintenance work runs in a daemon thread.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import hashlib
import json
import logging
import mimetypes
import os
import re
import resource
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from telethon.errors import FloodWaitError, MessageNotModifiedError
from telethon.tl.types import MessageEntityTextUrl

import cozy_catalog
import mtproto_user_client
import publication_safety
from airbnb_photo_backfill_core import (
    dhash_bytes,
    extract_muscache_candidates,
    filter_listing_photo_urls,
    hamming_distance,
    rewrite_url_host,
    select_additional_hashes,
)

log = logging.getLogger("backfill-small-photos-1201-1207")
ARCHIVE_FILE_ID = "1t0wL63g9VxQ7eoSGywksTGySZhaMnHIz"
ARCHIVE_ROOT = "Cozy_Asia_Small_Channel_1200-1207"
CHANNEL = "arenda_vill_samui"
LABEL = "📸 Дополнительные фото"

LOTS = {
    "1201": {"room_id":"1259009506231059461","source":"https://www.airbnb.com/rooms/1259009506231059461","archive_folder":"1201-villa-jasmine-waterslide","drive_folder_id":"1pKyGjUlCvZHg_XYKNhf0Mf28oyHoW0OG","message_id":941},
    "1202": {"room_id":"20470786","source":"https://www.airbnb.com/rooms/20470786","archive_folder":"1202-villa-samujana","drive_folder_id":"1Pz9wclc3OAga935jsdhtbRD6G5BK7Zja","message_id":951},
    "1203": {"room_id":"1424526292630741009","source":"https://www.airbnb.com/rooms/1424526292630741009","archive_folder":"1203-villa-ray","drive_folder_id":"1aQmoiuVhW4sm9zScyKbLI94vSQqx3h3x","message_id":961},
    "1204": {"room_id":"20901998","source":"https://www.airbnb.com/rooms/20901998","archive_folder":"1204-villa-sangsuri-3","drive_folder_id":"1n3U_8bPh2sZ9rhhLdc4JTMb0vSSPiJdj","message_id":971},
    "1205": {"room_id":"1764938638907964460","source":"https://www.airbnb.com/rooms/1764938638907964460","archive_folder":"1205-villa-oceanfront-fishermans","drive_folder_id":"12Nh91OqzjAXxs2BMfS03n4YRnDx1hu6s","message_id":981},
    "1206": {"room_id":"1525859637375407453","source":"https://www.airbnb.com/rooms/1525859637375407453","archive_folder":"1206-villa-steps-to-heaven","drive_folder_id":"1YbZ6A9hAYG9NYFxbmQPLTjgJ_qkzs5JI","message_id":991},
    "1207": {"room_id":"1380289917461504669","source":"https://www.airbnb.com/rooms/1380289917461504669","archive_folder":"1207-villa-once-upon-a-time","drive_folder_id":"1OBWTHtbAYiPtTlk7sQVPSIWqQ0aX4cdv","message_id":1001},
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
_ALLOWED_SOURCE_HOSTS = {"www.airbnb.com", "www.airbnb.ca", "www.airbnb.co.uk", "www.airbnb.de"}


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def enabled() -> bool:
    return os.getenv("BACKFILL_SMALL_LOTS_PHOTOS_1201_1207", "0").strip().lower() in {"1","true","yes","on"}


def _mode() -> str:
    return (os.getenv("AIRBNB_PHOTO_BACKFILL_MODE", "probe").strip().lower() or "probe")


def _selected_lots() -> list[str]:
    raw = os.getenv("AIRBNB_PHOTO_BACKFILL_LOTS", "1201").strip()
    out = [x.strip() for x in raw.split(",") if x.strip()]
    bad = [x for x in out if x not in LOTS]
    if bad:
        raise RuntimeError(f"Unknown lots requested: {bad}")
    return out


def _source_hosts() -> list[str]:
    raw = os.getenv("AIRBNB_PHOTO_SOURCE_HOSTS", "www.airbnb.com").strip()
    out: list[str] = []
    for item in raw.split(","):
        host = item.strip().lower()
        if not host:
            continue
        if host not in _ALLOWED_SOURCE_HOSTS:
            raise RuntimeError(f"Unsupported AIRBNB_PHOTO_SOURCE_HOSTS host: {host}")
        if host not in out:
            out.append(host)
    if not out:
        raise RuntimeError("AIRBNB_PHOTO_SOURCE_HOSTS resolved to an empty host list")
    return out


def _credentials(scopes: list[str]) -> Credentials:
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON missing")
    return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)


def _download_archive(tmp: str) -> Path:
    session = AuthorizedSession(_credentials(["https://www.googleapis.com/auth/drive.readonly"]))
    r = session.get(f"https://www.googleapis.com/drive/v3/files/{ARCHIVE_FILE_ID}?alt=media", timeout=180)
    r.raise_for_status()
    p = Path(tmp) / "small_lots.zip"
    p.write_bytes(r.content)
    return p


def _reference_hashes(zf: zipfile.ZipFile, lot: str) -> list[int]:
    base = f"{ARCHIVE_ROOT}/{LOTS[lot]['archive_folder']}/photos"
    hashes: list[int] = []
    for i in range(1, 11):
        raw = zf.read(f"{base}/{i:02d}.jpg")
        h = dhash_bytes(raw)
        if h not in hashes:
            hashes.append(h)
    return hashes


def _page_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def _fetch_candidate_urls_once(source: str) -> tuple[list[str], list[dict]]:
    session = _page_session()
    variants = [source, source + "?modal=PHOTO_TOUR_SCROLLABLE"]
    urls: list[str] = []
    seen: set[str] = set()
    page_info: list[dict] = []
    try:
        for url in variants:
            r = session.get(url, timeout=60, allow_redirects=True)
            page_info.append({"requested":url,"status":r.status_code,"final_url":r.url,"bytes":len(r.content),"content_type":r.headers.get("content-type","")})
            r.raise_for_status()
            for item in filter_listing_photo_urls(extract_muscache_candidates(r.text)):
                if item not in seen:
                    seen.add(item); urls.append(item)
    finally:
        session.close()
    return urls, page_info


def _fetch_candidate_urls(source: str, min_expected: int) -> tuple[list[str], list[dict]]:
    waits = [0, 20, 45]
    hosts = _source_hosts()
    last_urls: list[str] = []
    last_info: list[dict] = []
    for attempt, wait in enumerate(waits, start=1):
        if wait:
            log.warning("AIRBNB_SOURCE_BACKOFF seconds=%s hosts=%s", wait, hosts)
            time.sleep(wait)
        for host in hosts:
            effective_source = rewrite_url_host(source, host)
            try:
                urls, info = _fetch_candidate_urls_once(effective_source)
                last_urls, last_info = urls, info
                if len(urls) >= min_expected:
                    log.info("AIRBNB_SOURCE_HOST_OK host=%s count=%s source=%s", host, len(urls), effective_source)
                    return urls, info
                log.warning("AIRBNB_SOURCE_TOO_SMALL attempt=%s host=%s count=%s expected_at_least=%s info=%s", attempt, host, len(urls), min_expected, info)
            except Exception as exc:
                log.warning("AIRBNB_SOURCE_FETCH_FAILED attempt=%s host=%s error=%r", attempt, host, exc)
    return last_urls, last_info


def _download_hash(index: int, url: str, source: str) -> tuple[int, str, int] | None:
    try:
        with requests.get(url + "?im_w=720", headers={"User-Agent":UA,"Referer":source}, timeout=60, stream=True) as r:
            if not r.ok or "image" not in (r.headers.get("content-type") or "").lower():
                return None
            raw = r.content
        if not raw:
            return None
        return index, url, dhash_bytes(raw)
    except Exception:
        return None


def _candidate_hashes(urls: list[str], source: str) -> list[tuple[str, int]]:
    out: list[tuple[int,str,int]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_download_hash, i, u, source) for i,u in enumerate(urls)]
        for fut in concurrent.futures.as_completed(futures):
            item = fut.result()
            if item is not None:
                out.append(item)
    out.sort(key=lambda x:x[0])
    return [(u,h) for _,u,h in out]


def _match_count(ref_hashes: list[int], candidates: list[tuple[str,int]]) -> int:
    return sum(1 for ref in ref_hashes if any(hamming_distance(ref,h) <= 5 for _,h in candidates))


def _diagnostics(lot: str, ref_hashes: list[int], urls: list[str], candidates: list[tuple[str,int]], page_info: list[dict]) -> dict:
    best=[]
    for idx,ref in enumerate(ref_hashes,start=1):
        distances=sorted((hamming_distance(ref,h),u) for u,h in candidates)
        best.append({"reference_unique_index":idx,"distance":distances[0][0] if distances else None,"url":distances[0][1] if distances else None})
    matched=_match_count(ref_hashes,candidates)
    return {"lot":lot,"room_id":LOTS[lot]["room_id"],"page_info":page_info,"source_photos":len(urls),"downloaded_candidates":len(candidates),"unique_reference_images":len(ref_hashes),"matched_reference_images_threshold5":matched,"all_references_matched":matched==len(ref_hashes),"rss_mb":round(_rss_mb(),1),"best_reference_matches":best}


def _drive_session() -> AuthorizedSession:
    return AuthorizedSession(_credentials(["https://www.googleapis.com/auth/drive"]))


def _drive_url(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _ensure_public_folder(session: AuthorizedSession, folder_id: str) -> dict:
    fields="id,name,webViewLink,permissions(id,type,role,allowFileDiscovery)"
    r=session.get(f"https://www.googleapis.com/drive/v3/files/{folder_id}",params={"fields":fields},timeout=60)
    r.raise_for_status(); data=r.json()
    perms=data.get("permissions") or []
    if not any(p.get("type")=="anyone" and p.get("role")=="reader" for p in perms):
        w=session.post(
            f"https://www.googleapis.com/drive/v3/files/{folder_id}/permissions",
            params={"sendNotificationEmail":"false"},
            json={"type":"anyone","role":"reader","allowFileDiscovery":False},timeout=60,
        )
        w.raise_for_status()
    v=session.get(f"https://www.googleapis.com/drive/v3/files/{folder_id}",params={"fields":fields},timeout=60)
    v.raise_for_status(); verified=v.json()
    public=any(p.get("type")=="anyone" and p.get("role")=="reader" for p in (verified.get("permissions") or []))
    if not public:
        raise RuntimeError(f"Drive folder is not public after permission write: {folder_id}")
    return verified


def _list_drive_children(session: AuthorizedSession, folder_id: str) -> list[dict]:
    files=[]; token=None
    while True:
        params={"q":f"'{folder_id}' in parents and trashed=false","fields":"nextPageToken,files(id,name,mimeType,appProperties,webViewLink,size)","pageSize":1000}
        if token: params["pageToken"]=token
        r=session.get("https://www.googleapis.com/drive/v3/files",params=params,timeout=60); r.raise_for_status()
        data=r.json(); files.extend(data.get("files") or []); token=data.get("nextPageToken")
        if not token: return files


def _mime_for_url(url: str) -> tuple[str,str]:
    ext=Path(urlsplit(url).path).suffix.lower() or ".jpg"
    if ext==".jpeg": ext=".jpg"
    mime=mimetypes.types_map.get(ext,"image/jpeg")
    return ext,mime


def _download_full_image(url: str, source: str) -> bytes:
    last=None
    for attempt in range(4):
        try:
            with requests.get(url + "?im_w=1600",headers={"User-Agent":UA,"Referer":source},timeout=90,stream=True) as r:
                r.raise_for_status()
                if "image" not in (r.headers.get("content-type") or "").lower():
                    raise RuntimeError("non-image response")
                raw=r.content
            if raw:
                dhash_bytes(raw)
                return raw
        except Exception as exc:
            last=exc; time.sleep(2*(attempt+1))
    raise RuntimeError(f"Could not download image {url}: {last!r}")


def _upload_drive_image(session: AuthorizedSession, folder_id: str, name: str, mime: str, raw: bytes, lot: str, index: int) -> dict:
    boundary="cozy_"+uuid.uuid4().hex
    meta={"name":name,"parents":[folder_id],"appProperties":{"cozy_lot":lot,"source_index":str(index),"source":"airbnb"}}
    body=(
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta,ensure_ascii=False)}\r\n"
        f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + raw + f"\r\n--{boundary}--\r\n".encode("utf-8")
    r=session.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        params={"uploadType":"multipart","fields":"id,name,parents,mimeType,appProperties,size"},
        data=body,headers={"Content-Type":f"multipart/related; boundary={boundary}"},timeout=180,
    )
    r.raise_for_status(); return r.json()


def _py_from_u16(text: str, offset: int) -> int:
    used=0
    for i,ch in enumerate(text):
        if used>=offset: return i
        used+=len(ch.encode("utf-16-le"))//2
    return len(text)


def _segment(text: str, ent) -> str:
    a=_py_from_u16(text,int(ent.offset)); b=_py_from_u16(text,int(ent.offset)+int(ent.length)); return text[a:b]


def _caption_with_drive_link(text: str, entities, drive_url: str):
    entities=list(copy.deepcopy(list(entities or [])))
    p=text.find(LABEL)
    if p>=0:
        good=[e for e in entities if isinstance(e,MessageEntityTextUrl) and _segment(text,e)==LABEL and str(getattr(e,"url","") or "")==drive_url]
        if good:
            return text,entities,False
        s16=len(text[:p].encode("utf-16-le"))//2; e16=s16+len(LABEL.encode("utf-16-le"))//2
        kept=[]
        for e in entities:
            if isinstance(e,MessageEntityTextUrl) and int(e.offset)<e16 and int(e.offset)+int(e.length)>s16:
                continue
            kept.append(e)
        kept.append(MessageEntityTextUrl(offset=s16,length=e16-s16,url=drive_url)); kept.sort(key=lambda e:(int(e.offset),-int(e.length)))
        return text,kept,True
    m=re.search(r"(?m)^#",text)
    pos=m.start() if m else len(text.rstrip())
    prefix="\n\n" if pos and not text[:pos].endswith("\n\n") else ""
    block=prefix+LABEL+"\n\n"
    rel=[MessageEntityTextUrl(offset=len(prefix.encode("utf-16-le"))//2,length=len(LABEL.encode("utf-16-le"))//2,url=drive_url)]
    return (*mtproto_user_client._apply_replacements(text,entities,[{"start":pos,"end":pos,"text":block,"entities":rel}]),True)


async def _telegram_preflight(lot: str) -> dict:
    cfg=LOTS[lot]; client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto session is not authorized")
    try:
        channel=await client.get_entity(CHANNEL); mid=int(cfg["message_id"])
        anchor=await client.get_messages(channel,ids=mid)
        if not anchor or publication_safety.lot_from_message(anchor)!=lot:
            raise RuntimeError(f"Telegram lot mismatch lot={lot} mid={mid}")
        gid=int(getattr(anchor,"grouped_id",0) or 0)
        if not gid: raise RuntimeError(f"Telegram post is not an album lot={lot}")
        msgs=await client.get_messages(channel,ids=list(range(mid,mid+10)))
        msgs=[m for m in msgs if m]
        if len(msgs)!=10 or any(int(getattr(m,"grouped_id",0) or 0)!=gid for m in msgs) or any(not getattr(m,"media",None) for m in msgs):
            raise RuntimeError(f"Telegram album integrity failed lot={lot}")
        return {"grouped_id":gid,"media_ids":[int(m.id) for m in msgs],"caption":anchor.message or ""}
    finally:
        await client.disconnect()


async def _telegram_edit_verify(lot: str, drive_url: str, preflight: dict) -> dict:
    cfg=LOTS[lot]; client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto session is not authorized")
    try:
        channel=await client.get_entity(CHANNEL); mid=int(cfg["message_id"])
        current=await client.get_messages(channel,ids=mid)
        if not current or publication_safety.lot_from_message(current)!=lot: raise RuntimeError(f"Telegram lot changed before edit {lot}")
        if int(getattr(current,"grouped_id",0) or 0)!=int(preflight["grouped_id"]): raise RuntimeError(f"Telegram grouped_id changed lot={lot}")
        text,entities,changed=_caption_with_drive_link(current.message or "",current.entities or [],drive_url)
        if len(text)>4000: raise RuntimeError(f"Unexpected caption length lot={lot}: {len(text)}")
        if changed:
            while True:
                try:
                    await client.edit_message(channel,mid,text,formatting_entities=entities,link_preview=False); break
                except MessageNotModifiedError: break
                except FloodWaitError as exc: await asyncio.sleep(int(exc.seconds)+2)
        verify=await client.get_messages(channel,ids=mid)
        live=verify.message or ""; vent=list(verify.entities or [])
        if publication_safety.lot_from_message(verify)!=lot: raise RuntimeError(f"Post-edit lot mismatch {lot}")
        if int(getattr(verify,"grouped_id",0) or 0)!=int(preflight["grouped_id"]): raise RuntimeError(f"Post-edit grouped_id mismatch {lot}")
        links=[str(getattr(e,"url","") or "") for e in vent if isinstance(e,MessageEntityTextUrl) and _segment(live,e)==LABEL]
        if links!=[drive_url]: raise RuntimeError(f"Drive link readback failed lot={lot}: {links}")
        msgs=await client.get_messages(channel,ids=preflight["media_ids"]); msgs=[m for m in msgs if m]
        if len(msgs)!=10 or any(int(getattr(m,"grouped_id",0) or 0)!=int(preflight["grouped_id"]) for m in msgs): raise RuntimeError(f"Album changed after edit lot={lot}")
        return {"message_id":mid,"url":f"https://t.me/{CHANNEL}/{mid}","grouped_id":preflight["grouped_id"],"media_count":10,"drive_link_verified":True}
    finally:
        await client.disconnect()


def _prepare_source(lot: str, zf: zipfile.ZipFile) -> tuple[list[str],list[tuple[str,int]],list[int],list[dict]]:
    cfg=LOTS[lot]; refs=_reference_hashes(zf,lot)
    urls,info=_fetch_candidate_urls(cfg["source"],len(refs))
    candidates=_candidate_hashes(urls,cfg["source"])
    matched=_match_count(refs,candidates)
    if matched!=len(refs):
        raise RuntimeError(f"Source reference guard failed lot={lot}: matched={matched}/{len(refs)} source_photos={len(urls)}")
    if len(candidates)!=len(urls):
        raise RuntimeError(f"Could not hash every source photo lot={lot}: {len(candidates)}/{len(urls)}")
    return urls,candidates,refs,info


def run_probe() -> dict:
    selected=_selected_lots(); results=[]
    with tempfile.TemporaryDirectory(prefix="cozy-airbnb-probe-") as td:
        archive=_download_archive(td)
        with zipfile.ZipFile(archive,"r") as zf:
            for lot in selected:
                urls,candidates,refs,info=_prepare_source(lot,zf)
                item=_diagnostics(lot,refs,urls,candidates,info); results.append(item)
                log.info("AIRBNB_PHOTO_PROBE_LOT %s",json.dumps(item,ensure_ascii=False))
    final={"mode":"probe","selected":selected,"results":results}; log.info("AIRBNB_PHOTO_PROBE_DONE %s",json.dumps(final,ensure_ascii=False)); return final


def _apply_one(lot: str, zf: zipfile.ZipFile) -> dict:
    cfg=LOTS[lot]; drive_url=_drive_url(cfg["drive_folder_id"])
    preflight=asyncio.run(_telegram_preflight(lot))
    urls,candidates,refs,info=_prepare_source(lot,zf)
    selected=select_additional_hashes(refs,candidates,ref_threshold=5,duplicate_threshold=0)
    source_index={u:i+1 for i,u in enumerate(urls)}
    session=_drive_session(); folder=_ensure_public_folder(session,cfg["drive_folder_id"])
    existing=_list_drive_children(session,cfg["drive_folder_id"]); by_name={f.get("name"):f for f in existing}
    expected=[]; uploaded=0; exact_seen=set()
    for url,h in selected:
        idx=source_index[url]; ext,mime=_mime_for_url(url); token=Path(urlsplit(url).path).stem[-36:]
        name=f"source_{idx:03d}_{token}{ext}"; expected.append(name)
        if name in by_name: continue
        raw=_download_full_image(url,cfg["source"]); digest=hashlib.sha256(raw).hexdigest()
        if digest in exact_seen: continue
        exact_seen.add(digest)
        item=_upload_drive_image(session,cfg["drive_folder_id"],name,mime,raw,lot,idx); by_name[name]=item; uploaded+=1
        log.info("AIRBNB_PHOTO_DRIVE_UPLOAD lot=%s index=%s name=%s uploaded=%s/%s",lot,idx,name,uploaded,len(selected))
    children=_list_drive_children(session,cfg["drive_folder_id"]); names={f.get("name") for f in children}
    missing=[n for n in expected if n not in names]
    if missing: raise RuntimeError(f"Drive verification missing files lot={lot}: {missing[:10]} total={len(missing)}")
    tg=asyncio.run(_telegram_edit_verify(lot,drive_url,preflight))
    result={"lot":lot,"source_total":len(urls),"telegram_photos":10,"additional_selected":len(selected),"drive_file_count":len(children),"drive_url":drive_url,"folder_public":True,"folder_name":folder.get("name"),"new_uploads":uploaded,"telegram":tg,"status":"complete"}
    log.info("AIRBNB_PHOTO_APPLY_LOT %s",json.dumps(result,ensure_ascii=False)); return result


def run_apply() -> dict:
    selected=_selected_lots(); results=[]
    with tempfile.TemporaryDirectory(prefix="cozy-airbnb-apply-") as td:
        archive=_download_archive(td)
        with zipfile.ZipFile(archive,"r") as zf:
            for lot in selected: results.append(_apply_one(lot,zf))
    final={"mode":"apply","selected":selected,"results":results,"status":"complete"}; log.info("AIRBNB_PHOTO_APPLY_DONE %s",json.dumps(final,ensure_ascii=False)); return final


def run() -> dict:
    mode=_mode()
    if mode=="probe": return run_probe()
    if mode=="apply": return run_apply()
    raise RuntimeError(f"Unknown AIRBNB_PHOTO_BACKFILL_MODE={mode!r}")


def _maintenance_worker() -> None:
    try:
        result=run(); log.info("AIRBNB_PHOTO_BACKFILL_SERVICE_RESULT %s",json.dumps(result,ensure_ascii=False))
    except Exception:
        log.exception("AIRBNB_PHOTO_BACKFILL_SERVICE_FAILED")


def _start_normal_service() -> None:
    import main_legacy as entry
    try: entry.publish_fb_1070904912524019.start_once=lambda:None
    except Exception: pass
    entry.main()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",force=True)
    threading.Thread(target=_maintenance_worker,name="photo-backfill-1201-1207",daemon=True).start()
    _start_normal_service()

# -*- coding: utf-8 -*-
"""One-shot publication of Cozy Asia small-channel lots 1200–1207."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-small-lots-1200-1207")
CHANNEL = "arenda_vill_samui"
DRIVE_FILE_ID = "1t0wL63g9VxQ7eoSGywksTGySZhaMnHIz"
OWNER = "+66 96 047 1696"
OWNER_WA = "https://wa.me/66960471696"
ROOT = "Cozy_Asia_Small_Channel_1200-1207"

LOT_META = {
    "1200": {"folder":"1200-villa-nappa","area":"Северный Чавенг, Narayan Heights","beds":"4","baths":"4,5","daily_thb":"","month_thb":"","title":"ВИЛЛА NAPPA"},
    "1201": {"folder":"1201-villa-jasmine-waterslide","area":"Чавенг","beds":"5","baths":"5,5","daily_thb":"","month_thb":"","title":"ВИЛЛА JASMINE WATERSLIDE"},
    "1202": {"folder":"1202-villa-samujana","area":"Чавенг / Чонгмон","beds":"4","baths":"4,5","daily_thb":"50251","month_thb":"1507521","title":"ВИЛЛА SAMUJANA"},
    "1203": {"folder":"1203-villa-ray","area":"Чавенг Ной","beds":"4","baths":"","daily_thb":"45796","month_thb":"1373873","title":"ВИЛЛА RAY"},
    "1204": {"folder":"1204-villa-sangsuri-3","area":"Чавенг, побережье у Koh Matlang","beds":"7","baths":"7","daily_thb":"","month_thb":"","title":"ВИЛЛА SANGSURI 3"},
    "1205": {"folder":"1205-villa-oceanfront-fishermans","area":"Банграк / Fisherman’s Village","beds":"6","baths":"6","daily_thb":"48000","month_thb":"1440000","title":"OCEANFRONT VILLA — FISHERMAN’S VILLAGE"},
    "1206": {"folder":"1206-villa-steps-to-heaven","area":"Бопхут, холмы над Fisherman’s Village","beds":"5","baths":"5","daily_thb":"39669","month_thb":"1190057","title":"ВИЛЛА STEPS TO HEAVEN"},
    "1207": {"folder":"1207-villa-once-upon-a-time","area":"Бопхут, северо-восток Самуи — приблизительно","beds":"4","baths":"4,5","daily_thb":"34114","month_thb":"1023429","title":"ВИЛЛА ONCE UPON A TIME"},
}

SHORTEN = {
    "1200": [
        ("Просторная вилла на возвышенности с панорамным видом на море и побережье. Современные интерьеры, большие открытые зоны отдыха и приватный бассейн делают её отличным вариантом для семейного отпуска или компании.",
         "Просторная вилла на возвышенности с панорамным видом на море. Современные интерьеры, открытые зоны отдыха и приватный бассейн — для семьи или компании."),
        ("✨ ВКЛЮЧЕНО И ДОПОЛНИТЕЛЬНО","✨ ВКЛЮЧЕНО"),
    ],
    "1204": [
        ("Роскошная вилла для большой семьи или компании на первой линии. Панорамный бассейн, джакузи, тренажёрный зал, массажная комната и просторные зоны для совместного отдыха.",
         "Вилла на первой линии для большой семьи или компании: панорамный бассейн, джакузи, тренажёрный зал и массажная комната."),
        ("✨ ВКЛЮЧЕНО И ДОПОЛНИТЕЛЬНО","✨ ВКЛЮЧЕНО"),
        ("🛎 Менеджер виллы и обслуживающий персонал","🛎 Менеджер и персонал"),
    ],
    "1205": [
        ("Hidden Cove — масштабная вилла у моря недалеко от Fisherman’s Village. Пространство создано для роскошного отдыха большой компании: несколько бассейнов, собственный wellness-комплекс и команда персонала.",
         "Hidden Cove — вилла у моря рядом с Fisherman’s Village: 3 бассейна, wellness и персонал."),
        ("🏋️ Приватный тренажёрный зал и wellness-зона","🏋️ Тренажёрный зал и wellness-зона"),
        ("✨ ВКЛЮЧЕНО И ДОПОЛНИТЕЛЬНО","✨ ВКЛЮЧЕНО"),
        ("👨‍🍳 Собственный шеф-повар и команда персонала","👨‍🍳 Шеф-повар и персонал"),
        ("🧖 Сауна, парная и бассейн в стиле онсэн","🧖 Сауна, парная, онсэн"),
        ("🚶 Около 10 минут пешком до Fisherman’s Village","🚶 ~10 минут до Fisherman’s Village"),
        ("🔥 Специальная скидка на первый заказ","🔥 Скидка на первый заказ"),
        ("ℹ️ В стоимость уже включена наценка Cozy Asia 20%","ℹ️ Наценка Cozy Asia 20% включена"),
        ("🎬 Кинотеатр, игровая комната и бар","🎬 Кинотеатр, игровая и бар"),
    ],
    "1206": [
        ("Просторная вилла в тропических садах на холмах Бопхута с панорамным видом на море. Четыре спальни с кроватями king-size и отдельная большая детская комната.",
         "Вилла в садах на холмах Бопхута с панорамным видом на море. 4 спальни king-size и большая детская комната."),
        ("✨ ВКЛЮЧЕНО И ДОПОЛНИТЕЛЬНО","✨ ВКЛЮЧЕНО"),
    ],
}

def _u16_len(text: str) -> int:
    return len((text or "").encode("utf-16-le")) // 2

def _download_archive(directory: str) -> Path:
    raw = os.environ.get("GOOGLE_CREDS_JSON","").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    creds.refresh(GoogleAuthRequest())
    response = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{DRIVE_FILE_ID}?alt=media",
        headers={"Authorization":f"Bearer {creds.token}"}, timeout=120)
    response.raise_for_status()
    target = Path(directory)/"small_lots_1200_1207.zip"
    target.write_bytes(response.content)
    return target

def _clean_caption(lot: str, original: str) -> str:
    text = original.strip()
    for old,new in SHORTEN.get(lot,[]):
        text = text.replace(old,new)
    # Strict public-safety checks.
    low = text.lower()
    if "airbnb.com" in low or "wa.me/" in low or "66960471696" in low or "+66 96 047 1696" in text:
        raise RuntimeError(f"Private/source contact leaked into public caption for lot {lot}")
    if text.count("👤 Оператор: @cozy_asia") != 1:
        raise RuntimeError(f"Operator line invalid for lot {lot}")
    if text.count("НАПИСАТЬ БОТУ") != 1:
        raise RuntimeError(f"Bot label count invalid for lot {lot}")
    if "🗺 ГЕОЛОКАЦИЯ" not in text or "https://" not in text:
        raise RuntimeError(f"Geolocation missing for lot {lot}")
    nonblank = [x.strip() for x in text.splitlines() if x.strip()]
    if not nonblank or not nonblank[-1].startswith("#"):
        raise RuntimeError(f"Hashtags are not at absolute bottom for lot {lot}")
    if text.find("НАПИСАТЬ БОТУ") < text.find("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ"):
        raise RuntimeError(f"Bot label is not final CTA for lot {lot}")
    # Markdown URL is removed from visible caption; validate Telegram's UTF-16 limit.
    visible = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    if _u16_len(visible) > 1024:
        raise RuntimeError(f"Caption too long after prepared compaction for lot {lot}: {_u16_len(visible)}")
    return text

def _read_lot_files(z: zipfile.ZipFile, lot: str, directory: str):
    meta = LOT_META[lot]
    base = f"{ROOT}/{meta['folder']}"
    original = z.read(f"{base}/post_ru.txt").decode("utf-8")
    source = z.read(f"{base}/source_and_contact.txt").decode("utf-8").strip()
    caption = _clean_caption(lot, original)
    photos = []
    pd = Path(directory)/lot
    pd.mkdir(parents=True, exist_ok=True)
    for i in range(1,11):
        name = f"{base}/photos/{i:02d}.jpg"
        target = pd/f"{i:02d}.jpg"
        target.write_bytes(z.read(name))
        photos.append(str(target))
    geo_match = re.search(r"Геолокация:\s*(https?://\S+)", source)
    source_match = re.search(r"Источник:\s*(https?://\S+)", source)
    if not geo_match or not source_match:
        raise RuntimeError(f"Internal source/geo missing for lot {lot}")
    return original.strip(), caption, source, geo_match.group(1), source_match.group(1), photos

async def _existing_lot(client, channel, lot: str):
    async for msg in client.iter_messages(channel, limit=250):
        if publication_safety.lot_from_message(msg) == lot:
            return msg
    return None

def _upsert_sheet(lot: str, msg, public_text: str, original_text: str, source_text: str, source_url: str, geo: str):
    ws = cozy_catalog.ensure_lots_sheet()
    headers = ws.row_values(1)
    if not headers:
        headers = cozy_catalog.HEADERS
        ws.append_row(headers, value_input_option="RAW")
    all_rows = ws.get_all_values()
    target = None
    for idx,row in enumerate(all_rows[1:], start=2):
        lid = row[0].strip() if len(row)>0 else ""
        mid = row[1].strip() if len(row)>1 else ""
        if lid == lot or mid == str(msg.id):
            target = idx
            break
    meta = LOT_META[lot]
    desc = ""
    m = re.search(r"💬 ОПИСАНИЕ\s*\n(.+?)(?:\n\n|\n📍)", public_text, re.S)
    if m:
        desc = re.sub(r"\s+"," ",m.group(1)).strip()
    record = {h:"" for h in headers}
    record.update({
        "lot_id":lot,
        "telegram_message_id":str(msg.id),
        "telegram_url":f"https://t.me/{CHANNEL}/{msg.id}",
        "published_at":msg.date.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "status":"active",
        "тип":"вилла",
        "район":meta["area"],
        "спальни":meta["beds"],
        "ванные":meta["baths"],
        "бассейн":"yes",
        "тип_бассейна":"private",
        "цена_месяц_thb":meta["month_thb"],
        "цена_сутки_thb":meta["daily_thb"],
        "комиссия_thb":"10000",
        "доступность":"по запросу",
        "контакт_собственника":OWNER,
        "описание":desc,
        "исходный_текст":(
            f"{source_text}\nАрхив Drive: https://drive.google.com/file/d/{DRIVE_FILE_ID}/view\n"
            f"Исходная Airbnb-ссылка (внутренняя): {source_url}\n"
            f"Геолокация: {geo}\n\nPUBLIC_POST_SOURCE:\n{original_text}"
        ),
        "extracted_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "confidence":"1.0",
        "needs_review":"FALSE",
    })
    row = [record.get(h,"") for h in headers]
    end = cozy_catalog._col(len(headers))
    if target:
        ws.update(f"A{target}:{end}{target}", [row], value_input_option="USER_ENTERED")
    else:
        ws.append_row(row, value_input_option="USER_ENTERED")

async def run() -> dict:
    from telethon.extensions import markdown
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results = []
    try:
        channel = await client.get_entity(CHANNEL)
        with tempfile.TemporaryDirectory(prefix="small-1200-1207-") as td:
            archive = await asyncio.to_thread(_download_archive, td)
            with zipfile.ZipFile(archive) as z:
                for lot in [str(x) for x in range(1200,1208)]:
                    original, prepared, source_text, geo, source_url, photos = _read_lot_files(z, lot, td)
                    existing = await _existing_lot(client, channel, lot)
                    if existing:
                        verify = existing
                        result = "already"
                    else:
                        text, entities = markdown.parse(prepared)
                        sent = await client.send_file(
                            channel, photos, caption=text, formatting_entities=entities,
                            link_preview=False
                        )
                        messages = sent if isinstance(sent,list) else [sent]
                        if len(messages) != 10:
                            raise RuntimeError(f"Lot {lot}: expected 10 media messages, got {len(messages)}")
                        gids = {int(getattr(m,"grouped_id",0) or 0) for m in messages}
                        if len(gids) != 1 or 0 in gids:
                            raise RuntimeError(f"Lot {lot}: album grouping invalid {gids}")
                        verify = next((m for m in messages if getattr(m,"message",None)), messages[0])
                        verify = await client.get_messages(channel, ids=int(verify.id))
                        result = "published"
                    live = getattr(verify,"message",None) or ""
                    decoded = publication_safety.lot_from_message(verify)
                    if decoded != lot:
                        raise RuntimeError(f"Lot {lot}: read-back lot mismatch {decoded!r}")
                    if live.count("Оператор: @cozy_asia") != 1:
                        raise RuntimeError(f"Lot {lot}: operator read-back invalid")
                    if live.count("НАПИСАТЬ БОТУ") != 1:
                        raise RuntimeError(f"Lot {lot}: bot label read-back invalid")
                    if geo not in live:
                        raise RuntimeError(f"Lot {lot}: geolocation missing after read-back")
                    low = live.lower()
                    if "airbnb.com" in low or "wa.me/" in low or "66960471696" in low:
                        raise RuntimeError(f"Lot {lot}: private source leaked after read-back")
                    nonblank = [x.strip() for x in live.splitlines() if x.strip()]
                    if not nonblank or not nonblank[-1].startswith("#"):
                        raise RuntimeError(f"Lot {lot}: hashtags not at bottom after read-back")
                    await asyncio.to_thread(_upsert_sheet, lot, verify, live, original, source_text, source_url, geo)
                    item = {
                        "lot":lot, "message_id":int(verify.id),
                        "url":f"https://t.me/{CHANNEL}/{verify.id}",
                        "published_at":verify.date.astimezone(timezone.utc).isoformat(timespec="seconds"),
                        "photos":10, "result":result
                    }
                    results.append(item)
                    log.info("SMALL_LOT_PUBLISHED %s", json.dumps(item, ensure_ascii=False))
                    await asyncio.sleep(2.5)
        final = {"channel":CHANNEL,"count":len(results),"results":results,"result":"complete"}
        log.info("PUBLISH_SMALL_LOTS_1200_1207_DONE %s", json.dumps(final, ensure_ascii=False))
        return {"enabled":True,"result":final}
    finally:
        await client.disconnect()

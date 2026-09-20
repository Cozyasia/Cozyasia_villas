# -*- coding: utf-8 -*-
"""Gated photo backfill for Cozy Asia small-channel lots 1201-1207.

Modes:
- probe: read-only diagnostics only; never writes Drive or Telegram.
- apply: reserved for verified extraction path; guarded by full reference matching.

The module is intentionally not imported by ordinary service startup unless the
BACKFILL_SMALL_LOTS_PHOTOS_1201_1207 flag is enabled in main.py.
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path

import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from airbnb_photo_backfill_core import (
    dhash_bytes,
    extract_muscache_candidates,
    hamming_distance,
    reference_match_count,
)

log = logging.getLogger("backfill-small-photos-1201-1207")
ARCHIVE_FILE_ID = "1t0wL63g9VxQ7eoSGywksTGySZhaMnHIz"
ARCHIVE_ROOT = "Cozy_Asia_Small_Channel_1200-1207"

LOTS = {
    "1201": {
        "room_id": "1259009506231059461",
        "source": "https://www.airbnb.com/rooms/1259009506231059461",
        "archive_folder": "1201-villa-jasmine-waterslide",
        "drive_folder_id": "1pKyGjUlCvZHg_XYKNhf0Mf28oyHoW0OG",
        "message_id": 941,
    },
    "1202": {
        "room_id": "20470786",
        "source": "https://www.airbnb.com/rooms/20470786",
        "archive_folder": "1202-villa-samujana",
        "drive_folder_id": "1Pz9wclc3OAga935jsdhtbRD6G5BK7Zja",
        "message_id": 951,
    },
    "1203": {
        "room_id": "1424526292630741009",
        "source": "https://www.airbnb.com/rooms/1424526292630741009",
        "archive_folder": "1203-villa-ray",
        "drive_folder_id": "1aQmoiuVhW4sm9zScyKbLI94vSQqx3h3x",
        "message_id": 961,
    },
    "1204": {
        "room_id": "20901998",
        "source": "https://www.airbnb.com/rooms/20901998",
        "archive_folder": "1204-villa-sangsuri-3",
        "drive_folder_id": "1n3U_8bPh2sZ9rhhLdc4JTMb0vSSPiJdj",
        "message_id": 971,
    },
    "1205": {
        "room_id": "1764938638907964460",
        "source": "https://www.airbnb.com/rooms/1764938638907964460",
        "archive_folder": "1205-villa-oceanfront-fishermans",
        "drive_folder_id": "12Nh91OqzjAXxs2BMfS03n4YRnDx1hu6s",
        "message_id": 981,
    },
    "1206": {
        "room_id": "1525859637375407453",
        "source": "https://www.airbnb.com/rooms/1525859637375407453",
        "archive_folder": "1206-villa-steps-to-heaven",
        "drive_folder_id": "1YbZ6A9hAYG9NYFxbmQPLTjgJ_qkzs5JI",
        "message_id": 991,
    },
    "1207": {
        "room_id": "1380289917461504669",
        "source": "https://www.airbnb.com/rooms/1380289917461504669",
        "archive_folder": "1207-villa-once-upon-a-time",
        "drive_folder_id": "1OBWTHtbAYiPtTlk7sQVPSIWqQ0aX4cdv",
        "message_id": 1001,
    },
}


def enabled() -> bool:
    return os.getenv("BACKFILL_SMALL_LOTS_PHOTOS_1201_1207", "0").strip().lower() in {"1", "true", "yes", "on"}


def _mode() -> str:
    return (os.getenv("AIRBNB_PHOTO_BACKFILL_MODE", "probe").strip().lower() or "probe")


def _selected_lots() -> list[str]:
    raw = os.getenv("AIRBNB_PHOTO_BACKFILL_LOTS", "1201").strip()
    out = [x.strip() for x in raw.split(",") if x.strip()]
    bad = [x for x in out if x not in LOTS]
    if bad:
        raise RuntimeError(f"Unknown lots requested: {bad}")
    return out


def _credentials(scopes: list[str]) -> Credentials:
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON missing")
    return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)


def _download_archive(tmp: str) -> Path:
    session = AuthorizedSession(_credentials(["https://www.googleapis.com/auth/drive.readonly"]))
    r = session.get(
        f"https://www.googleapis.com/drive/v3/files/{ARCHIVE_FILE_ID}?alt=media",
        timeout=180,
    )
    r.raise_for_status()
    p = Path(tmp) / "small_lots.zip"
    p.write_bytes(r.content)
    return p


def _reference_images(zf: zipfile.ZipFile, lot: str) -> list[bytes]:
    folder = LOTS[lot]["archive_folder"]
    base = f"{ARCHIVE_ROOT}/{folder}/photos"
    return [zf.read(f"{base}/{i:02d}.jpg") for i in range(1, 11)]


def _page_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def _fetch_candidate_urls(source: str) -> tuple[list[str], list[dict]]:
    session = _page_session()
    variants = [source, source + "?modal=PHOTO_TOUR_SCROLLABLE"]
    urls: list[str] = []
    seen: set[str] = set()
    page_info: list[dict] = []
    for url in variants:
        r = session.get(url, timeout=60, allow_redirects=True)
        page_info.append({
            "requested": url,
            "status": r.status_code,
            "final_url": r.url,
            "bytes": len(r.content),
            "content_type": r.headers.get("content-type", ""),
        })
        r.raise_for_status()
        found = extract_muscache_candidates(r.text)
        for item in found:
            if item not in seen:
                seen.add(item)
                urls.append(item)
    return urls, page_info


def _download_image(url: str, source: str) -> tuple[str, bytes] | None:
    try:
        r = requests.get(
            url + ("&" if "?" in url else "?") + "im_w=1200",
            headers={"User-Agent": _page_session().headers["User-Agent"], "Referer": source},
            timeout=45,
        )
        if not r.ok or not r.content:
            return None
        ctype = (r.headers.get("content-type") or "").lower()
        if "image" not in ctype:
            return None
        # Validate decodability now so one malformed response cannot poison the run.
        dhash_bytes(r.content)
        return url, r.content
    except Exception:
        return None


def _download_candidates(urls: list[str], source: str) -> list[tuple[str, bytes]]:
    if not urls:
        return []
    out: list[tuple[int, str, bytes]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_download_image, u, source): i for i, u in enumerate(urls)}
        for fut in concurrent.futures.as_completed(futures):
            item = fut.result()
            if item:
                out.append((futures[fut], item[0], item[1]))
    out.sort(key=lambda x: x[0])
    return [(u, b) for _, u, b in out]


def _diagnostics(lot: str, refs: list[bytes], urls: list[str], candidates: list[tuple[str, bytes]], page_info: list[dict]) -> dict:
    ref_hashes: list[int] = []
    for raw in refs:
        h = dhash_bytes(raw)
        if h not in ref_hashes:
            ref_hashes.append(h)
    cand_hashes = [(u, dhash_bytes(b)) for u, b in candidates]
    best = []
    for idx, ref in enumerate(ref_hashes, start=1):
        distances = sorted((hamming_distance(ref, h), u) for u, h in cand_hashes)
        best.append({"reference_unique_index": idx, "distance": distances[0][0] if distances else None, "url": distances[0][1] if distances else None})
    matched, unique_refs = reference_match_count(refs, candidates, threshold=5)
    room_id = LOTS[lot]["room_id"]
    scoped = [u for u in urls if room_id in u]
    return {
        "lot": lot,
        "room_id": room_id,
        "page_info": page_info,
        "candidate_urls": len(urls),
        "downloaded_candidates": len(candidates),
        "room_id_scoped_urls": len(scoped),
        "unique_reference_images": unique_refs,
        "matched_reference_images_threshold5": matched,
        "all_references_matched": matched == unique_refs,
        "first_urls": urls[:12],
        "last_urls": urls[-8:],
        "best_reference_matches": best,
    }


def run_probe() -> dict:
    selected = _selected_lots()
    results = []
    with tempfile.TemporaryDirectory(prefix="cozy-airbnb-probe-") as td:
        archive = _download_archive(td)
        with zipfile.ZipFile(archive, "r") as zf:
            for lot in selected:
                cfg = LOTS[lot]
                refs = _reference_images(zf, lot)
                urls, page_info = _fetch_candidate_urls(cfg["source"])
                candidates = _download_candidates(urls, cfg["source"])
                item = _diagnostics(lot, refs, urls, candidates, page_info)
                results.append(item)
                log.info("AIRBNB_PHOTO_PROBE_LOT %s", json.dumps(item, ensure_ascii=False))
    final = {"mode": "probe", "selected": selected, "results": results}
    log.info("AIRBNB_PHOTO_PROBE_DONE %s", json.dumps(final, ensure_ascii=False))
    return final


def run() -> dict:
    mode = _mode()
    if mode == "probe":
        return run_probe()
    if mode == "apply":
        raise RuntimeError("apply mode is not enabled until probe verifies full reference recovery")
    raise RuntimeError(f"Unknown AIRBNB_PHOTO_BACKFILL_MODE={mode!r}")


def _start_normal_service() -> None:
    import main_legacy as entry
    try:
        entry.publish_fb_1070904912524019.start_once = lambda: None
    except Exception:
        pass
    entry.main()


def run_service_mode() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    try:
        result = run()
        log.info("AIRBNB_PHOTO_BACKFILL_SERVICE_RESULT %s", json.dumps(result, ensure_ascii=False))
    except Exception:
        log.exception("AIRBNB_PHOTO_BACKFILL_SERVICE_FAILED")
    _start_normal_service()

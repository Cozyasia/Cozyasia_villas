# -*- coding: utf-8 -*-
"""Caption-only maintenance for Cozy Asia small-channel lots 1201-1207.

This job never downloads Airbnb media and never writes to Google Drive.
It only preflights each existing Telegram album and adds/verifies the public
Drive-folder link in the existing caption.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading

import backfill_small_lots_photos_1201_1207 as backfill

log = logging.getLogger("edit-small-lots-drive-links-1201-1207")


def enabled() -> bool:
    return os.getenv("EDIT_SMALL_LOTS_DRIVE_LINKS_1201_1207", "0").strip().lower() in {"1", "true", "yes", "on"}


def _selected_lots() -> list[str]:
    raw = os.getenv("EDIT_SMALL_LOTS_DRIVE_LINKS_LOTS", "1201,1202,1203,1204,1205,1206,1207").strip()
    lots = [x.strip() for x in raw.split(",") if x.strip()]
    bad = [x for x in lots if x not in backfill.LOTS]
    if bad:
        raise RuntimeError(f"Unknown lots requested: {bad}")
    return lots


async def _run_async() -> dict:
    results = []
    for lot in _selected_lots():
        cfg = backfill.LOTS[lot]
        drive_url = backfill._drive_url(cfg["drive_folder_id"])
        preflight = await backfill._telegram_preflight(lot)
        result = await backfill._telegram_edit_verify(lot, drive_url, preflight)
        item = {
            "lot": lot,
            "message_id": cfg["message_id"],
            "drive_url": drive_url,
            "grouped_id": result["grouped_id"],
            "media_count": result["media_count"],
            "drive_link_verified": result["drive_link_verified"],
            "telegram_url": result["url"],
            "status": "complete",
        }
        results.append(item)
        log.info("DRIVE_LINK_EDIT_LOT %s", json.dumps(item, ensure_ascii=False))
    final = {"selected": _selected_lots(), "results": results, "status": "complete"}
    log.info("DRIVE_LINK_EDIT_DONE %s", json.dumps(final, ensure_ascii=False))
    return final


def run() -> dict:
    return asyncio.run(_run_async())


def _worker() -> None:
    try:
        run()
    except Exception:
        log.exception("DRIVE_LINK_EDIT_FAILED")


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    threading.Thread(target=_worker, name="drive-link-edit-1201-1207", daemon=True).start()
    backfill._start_normal_service()

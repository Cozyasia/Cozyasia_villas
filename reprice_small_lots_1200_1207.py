# -*- coding: utf-8 -*-
"""One-shot repricing of small-channel lots 1200–1207 to current Cozy Asia tariff."""
from __future__ import annotations

import asyncio
import json
import logging

from telethon.errors import FloodWaitError, MessageNotModifiedError

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("reprice-small-1200-1207")
CHANNEL = "arenda_vill_samui"

LOTS = {
    "1200": {"mid":931,  "daily":32918, "week":207381},
    "1201": {"mid":941,  "daily":33129, "week":197119},
    "1202": {"mid":951,  "daily":52417, "week":391379},
    "1203": {"mid":961,  "daily":27099, "week":200228},
    "1204": {"mid":971,  "daily":63070, "week":496681},
    "1205": {"mid":981,  "daily":67142, "week":469992},
    "1206": {"mid":991,  "daily":54864, "week":370776},
    "1207": {"mid":1001, "daily":24678, "week":134809},
}

def fmt(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")

def price_block(daily: int, week: int) -> str:
    return (
        "💰\n"
        "УСЛОВИЯ АРЕНДЫ\n"
        "💵\n"
        f"От 3 ночей: {fmt(daily)} THB/сутки\n"
        "📆\n"
        f"За 7 ночей: {fmt(week)} THB\n"
        "🗓\n"
        "За 30 ночей: по запросу\n"
        "🤝\n"
        "Комиссия агентства: 10 000 THB\n"
        "📅\n"
        "Доступность на сезон 2026/27: по запросу\n"
    )

def find_price_span(text: str):
    start = text.find("💰\nУСЛОВИЯ АРЕНДЫ")
    if start < 0:
        raise RuntimeError("price block start not found")
    end = text.find("✨\n", start)
    if end < 0:
        raise RuntimeError("price block end not found")
    return start, end

def apply_block(text, entities, daily, week):
    start, end = find_price_span(text)
    repl = price_block(daily, week)
    return mtproto_user_client._apply_replacements(
        text, entities, [{"start":start, "end":end, "text":repl, "entities":[]}]
    )

async def safe_edit(client, channel, mid, text, entities):
    while True:
        try:
            await client.edit_message(channel, mid, text, formatting_entities=entities, link_preview=False)
            return
        except MessageNotModifiedError:
            return
        except FloodWaitError as exc:
            wait = int(getattr(exc, "seconds", 0) or 0) + 2
            log.warning("REPRICE_SMALL_FLOOD_WAIT mid=%s seconds=%s", mid, wait)
            await asyncio.sleep(wait)

async def run():
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results = []
    try:
        channel = await client.get_entity(CHANNEL)
        for lot, cfg in LOTS.items():
            msg = await client.get_messages(channel, ids=cfg["mid"])
            if not msg or not getattr(msg, "message", None):
                raise RuntimeError(f"missing caption lot={lot} mid={cfg['mid']}")
            if publication_safety.lot_from_message(msg) != lot:
                raise RuntimeError(f"lot mismatch before edit lot={lot}")
            original_group = int(getattr(msg, "grouped_id", 0) or 0)
            text = getattr(msg, "message", None) or ""
            entities = list(getattr(msg, "entities", None) or [])

            text, entities = apply_block(text, entities, cfg["daily"], cfg["week"])

            # Public post must not expose markup or source/private data.
            low = text.lower()
            for forbidden in ("наценка cozy asia", "20%", "10% нацен", "airbnb.com", "wa.me/", "66960471696"):
                if forbidden in low:
                    raise RuntimeError(f"forbidden public text {forbidden!r} lot={lot}")
            if text.count("Оператор: @cozy_asia") != 1:
                raise RuntimeError(f"operator invalid lot={lot}")
            if text.count("НАПИСАТЬ БОТУ") != 1:
                raise RuntimeError(f"bot CTA count invalid lot={lot}")
            if text.count("ЖМИ ЗДЕСЬ") != 1:
                raise RuntimeError(f"rent CTA count invalid lot={lot}")
            if "ГЕОЛОКАЦИЯ" not in text:
                raise RuntimeError(f"geolocation missing lot={lot}")
            nonblank = [x.strip() for x in text.splitlines() if x.strip()]
            if not nonblank or not nonblank[-1].startswith("#"):
                raise RuntimeError(f"hashtags not bottom lot={lot}")
            if len(text) > 1024:
                raise RuntimeError(f"caption too long lot={lot}: {len(text)}")

            await safe_edit(client, channel, cfg["mid"], text, entities)
            verify = await client.get_messages(channel, ids=cfg["mid"])
            live = getattr(verify, "message", None) or ""
            if publication_safety.lot_from_message(verify) != lot:
                raise RuntimeError(f"lot mismatch after edit lot={lot}")
            if int(getattr(verify, "grouped_id", 0) or 0) != original_group:
                raise RuntimeError(f"album group changed lot={lot}")
            for needle in (
                f"От 3 ночей: {fmt(cfg['daily'])} THB/сутки",
                f"За 7 ночей: {fmt(cfg['week'])} THB",
                "За 30 ночей: по запросу",
                "Доступность на сезон 2026/27: по запросу",
            ):
                if needle not in live:
                    raise RuntimeError(f"read-back missing {needle!r} lot={lot}")
            low2 = live.lower()
            if "наценка cozy asia" in low2 or "20%" in low2 or "10% нацен" in low2:
                raise RuntimeError(f"markup mention remains lot={lot}")
            if live.count("НАПИСАТЬ БОТУ") != 1 or live.count("ЖМИ ЗДЕСЬ") != 1:
                raise RuntimeError(f"CTA read-back invalid lot={lot}")
            results.append({
                "lot":lot,
                "message_id":cfg["mid"],
                "daily_thb":cfg["daily"],
                "week_thb":cfg["week"],
                "month":"по запросу",
                "availability":"сезон 2026/27 — по запросу",
                "result":"edited",
            })
            log.info("REPRICE_SMALL_LOT_DONE %s", json.dumps(results[-1], ensure_ascii=False))
            await asyncio.sleep(2.0)

        final = {"channel":CHANNEL, "count":len(results), "results":results, "result":"complete"}
        log.info("REPRICE_SMALL_1200_1207_DONE %s", json.dumps(final, ensure_ascii=False))
        return {"enabled":True, "result":final}
    finally:
        await client.disconnect()

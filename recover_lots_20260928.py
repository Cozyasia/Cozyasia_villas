# -*- coding: utf-8 -*-
"""One-shot read-only Telegram lot recovery diagnostic."""
from __future__ import annotations
import asyncio, json, logging, os, re

TARGETS = {x.strip() for x in os.getenv("LOT_RECOVERY_TARGETS","").split(",") if x.strip()}
CHANNELS = ("samuirental", "arenda_vill_samui")

async def run():
    import cozy_catalog as catalog
    import mtproto_user_client as mt
    from channel_bot_routing_audit import _trusted_lot_from_message
    client = await mt._new_client(catalog)
    if client is None:
        raise RuntimeError("MTProto session unavailable")
    result = {"targets": sorted(TARGETS), "channels": {}, "found": {}}
    try:
        for channel in CHANNELS:
            scanned = 0
            hits = []
            async for msg in client.iter_messages(channel, limit=None):
                scanned += 1
                lot = _trusted_lot_from_message(msg)
                if lot in TARGETS:
                    text = getattr(msg, "message", None) or ""
                    item = {
                        "channel": channel,
                        "message_id": int(msg.id),
                        "lot": lot,
                        "grouped_id": getattr(msg, "grouped_id", None),
                        "date": msg.date.isoformat() if getattr(msg, "date", None) else None,
                        "url": f"https://t.me/{channel}/{int(msg.id)}",
                        "text": text,
                    }
                    hits.append(item)
                    result["found"].setdefault(lot, []).append(item)
            result["channels"][channel] = {"scanned": scanned, "hits": len(hits)}
    finally:
        await client.disconnect()
    result["missing"] = sorted(TARGETS - set(result["found"]))
    return result

def run_service_mode():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("LOT_RECOVERY_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

if __name__ == "__main__":
    run_service_mode()

"""Read-only Samui News audit mode.

The mode prints the latest channel messages with IDs and timestamps. It never
edits, deletes, or publishes Telegram content.
"""
from __future__ import annotations

import asyncio
import json
import logging

import cozy_catalog
import mtproto_user_client

log = logging.getLogger("samui-news-audit")


async def audit(limit: int = 30):
    client = await mtproto_user_client._new_client(cozy_catalog)
    if client is None:
        raise RuntimeError("MTProto authorization unavailable")
    try:
        channel = await client.get_entity("samui_news_ru")
        messages = await client.get_messages(channel, limit=limit)
        rows = []
        for message in reversed(list(messages or [])):
            text = (getattr(message, "raw_text", "") or "").strip()
            rows.append(
                {
                    "id": int(getattr(message, "id", 0) or 0),
                    "date": getattr(message, "date", None).isoformat()
                    if getattr(message, "date", None)
                    else "",
                    "edited": getattr(message, "edit_date", None).isoformat()
                    if getattr(message, "edit_date", None)
                    else "",
                    "has_media": bool(getattr(message, "media", None)),
                    "text": text[:3000],
                }
            )
        for row in rows:
            log.info("SAMUI_NEWS_AUDIT %s", json.dumps(row, ensure_ascii=False))
        log.info("SAMUI_NEWS_AUDIT_COMPLETE count=%s", len(rows))
        return rows
    finally:
        await client.disconnect()


def run_service_mode():
    logging.basicConfig(level=logging.INFO)
    asyncio.run(audit(30))


if __name__ == "__main__":
    run_service_mode()

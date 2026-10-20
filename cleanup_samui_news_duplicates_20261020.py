"""Explicit, idempotent deletion mode for confirmed Samui News duplicates.

Deletion is impossible unless both an exact ID list and the confirmation token
are supplied through Render environment variables. This prevents accidental
cleanup on ordinary service starts.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

import cozy_catalog
import mtproto_user_client

log = logging.getLogger("samui-news-cleanup")


def _ids():
    result = []
    for token in re.split(r"[;,\\s]+", os.environ.get("SAMUI_NEWS_DELETE_MESSAGE_IDS", "")):
        if token.isdigit() and int(token) > 0 and int(token) not in result:
            result.append(int(token))
    return result


async def cleanup():
    if os.environ.get("SAMUI_NEWS_DELETE_CONFIRM", "") != "DELETE_CONFIRMED_DUPLICATES":
        raise RuntimeError("Deletion confirmation token is missing")
    ids = _ids()
    if not ids:
        raise RuntimeError("No explicit Samui News message IDs supplied")
    client = await mtproto_user_client._new_client(cozy_catalog)
    if client is None:
        raise RuntimeError("MTProto authorization unavailable")
    try:
        channel = await client.get_entity("samui_news_ru")
        before = await client.get_messages(channel, ids=ids)
        for message in before if isinstance(before, list) else [before]:
            if message is not None:
                log.info("SAMUI_NEWS_DELETE_TARGET id=%s text=%s", message.id, (message.raw_text or "")[:300])
        await client.delete_messages(channel, ids, revoke=True)
        after = await client.get_messages(channel, ids=ids)
        remaining = [
            int(getattr(message, "id", 0))
            for message in (after if isinstance(after, list) else [after])
            if message is not None
        ]
        if remaining:
            raise RuntimeError(f"Deletion verification failed; remaining IDs: {remaining}")
        log.info("SAMUI_NEWS_DELETE_COMPLETE ids=%s", ids)
    finally:
        await client.disconnect()


def run_service_mode():
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup())


if __name__ == "__main__":
    run_service_mode()

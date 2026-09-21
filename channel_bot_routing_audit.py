# -*- coding: utf-8 -*-
"""Audit/migrate Telegram bot routing in Cozy Asia property channels.

This maintenance tool is intentionally gated from ``main.py``.  It can scan all
messages in the two property channels and, in migrate mode, replace only
MessageEntityTextUrl targets that point to a bot for the wrong channel.  The
message text and every other Telegram entity (blockquote, custom emoji, bold,
spacing, etc.) are preserved byte-for-byte.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import re
from collections import Counter

log = logging.getLogger("channel-bot-routing")

CHANNELS = {
    "samuirental": "cozy_asia_bot",
    "arenda_vill_samui": "Cozyasia_villa_bot",
}


def enabled() -> bool:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "").strip().lower() in {"audit", "migrate"}


def mode() -> str:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "audit").strip().lower()


def _bot_from_url(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?t\.me/([A-Za-z0-9_]+)", url or "", re.I)
    return m.group(1) if m else ""


def _rewrite_target(url: str, expected_bot: str) -> str:
    return re.sub(
        r"(https?://(?:www\.)?t\.me/)([A-Za-z0-9_]+)",
        lambda m: m.group(1) + expected_bot,
        url,
        count=1,
        flags=re.I,
    )


def _is_bot_url(url: str) -> bool:
    bot = _bot_from_url(url)
    return bool(bot and bot.lower().endswith("bot"))


def _sample(msg) -> dict:
    text = getattr(msg, "message", None) or ""
    entities = list(getattr(msg, "entities", None) or [])
    return {
        "id": int(getattr(msg, "id", 0) or 0),
        "text": text,
        "entities": [
            {
                "type": type(e).__name__,
                "offset": int(getattr(e, "offset", 0) or 0),
                "length": int(getattr(e, "length", 0) or 0),
                "url": str(getattr(e, "url", "") or ""),
                "collapsed": getattr(e, "collapsed", None),
            }
            for e in entities
        ],
    }


async def _audit_channel(client, channel: str, expected_bot: str, do_migrate: bool) -> dict:
    total = 0
    text_messages = 0
    bot_counter = Counter()
    starts = Counter()
    wrong = []
    plain_url_wrong = []
    migrated = []
    latest_samples = []

    async for msg in client.iter_messages(channel, limit=None):
        total += 1
        text = getattr(msg, "message", None) or ""
        if not text:
            continue
        text_messages += 1
        entities = list(getattr(msg, "entities", None) or [])
        if len(latest_samples) < 12:
            latest_samples.append(_sample(msg))

        changed = False
        new_entities = []
        for ent in entities:
            cloned = copy.copy(ent)
            url = str(getattr(ent, "url", "") or "")
            if url and _is_bot_url(url):
                bot = _bot_from_url(url)
                bot_counter[bot] += 1
                sm = re.search(r"[?&]start=([^&#]+)", url)
                if sm:
                    starts[sm.group(1)] += 1
                if bot.lower() != expected_bot.lower():
                    wrong.append({
                        "id": int(msg.id),
                        "url": url,
                        "bot": bot,
                        "type": type(ent).__name__,
                        "text_head": text[:160].replace("\n", " | "),
                    })
                    if do_migrate and type(ent).__name__ == "MessageEntityTextUrl":
                        cloned.url = _rewrite_target(url, expected_bot)
                        changed = True
            new_entities.append(cloned)

        # Detect plain URL text so the audit is complete.  We deliberately do
        # not auto-rewrite it because that would require offset surgery and can
        # damage hand-edited formatting.
        for url in re.findall(r"https?://(?:www\.)?t\.me/[A-Za-z0-9_]+(?:\?[^\s<>()]+)?", text):
            if not _is_bot_url(url):
                continue
            bot = _bot_from_url(url)
            if bot.lower() != expected_bot.lower():
                plain_url_wrong.append({
                    "id": int(msg.id),
                    "url": url,
                    "bot": bot,
                    "text_head": text[:160].replace("\n", " | "),
                })

        if changed:
            await client.edit_message(channel, msg.id, text, formatting_entities=new_entities)
            migrated.append(int(msg.id))
            await asyncio.sleep(0.35)

    return {
        "expected_bot": expected_bot,
        "total_messages": total,
        "text_messages": text_messages,
        "bot_counter": dict(bot_counter),
        "start_params_top": starts.most_common(30),
        "wrong_entity_count": len(wrong),
        "wrong_entity_examples": wrong[:200],
        "plain_url_wrong_count": len(plain_url_wrong),
        "plain_url_wrong_examples": plain_url_wrong[:100],
        "migrated_count": len(migrated),
        "migrated_message_ids": migrated[:500],
        "latest_samples": latest_samples,
    }


async def run() -> dict:
    import cozy_catalog as catalog
    import mtproto_user_client as mt

    client = await mt._new_client(catalog)
    if client is None:
        raise RuntimeError("MTProto session unavailable")
    do_migrate = mode() == "migrate"
    result = {"mode": mode(), "channels": {}}
    try:
        for channel, expected in CHANNELS.items():
            result["channels"][channel] = await _audit_channel(client, channel, expected, do_migrate)
    finally:
        await client.disconnect()
    return result


def run_service_mode() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    result = asyncio.run(run())
    print("CHANNEL_BOT_ROUTING_RESULT=" + json.dumps(result, ensure_ascii=False))

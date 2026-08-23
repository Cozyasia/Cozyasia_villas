# -*- coding: utf-8 -*-
"""Capture Premium Custom Emoji entities from manually edited channel posts.

This lets the owner prepare one representative post in Telegram's channel editor
(where the alphabet custom-emoji pack is available) and have the bot persist the
real custom_emoji_id values and their order for later reuse.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from telegram.ext import MessageHandler, filters

log = logging.getLogger("channel-template-capture")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract_entities(msg):
    text = msg.text or msg.caption or ""
    entities = list(msg.entities or []) + list(msg.caption_entities or [])
    out = []
    for ent in entities:
        cid = getattr(ent, "custom_emoji_id", None)
        typ = str(getattr(ent, "type", ""))
        if not cid or not typ.endswith("custom_emoji"):
            continue
        try:
            segment = msg.parse_entity(ent) if msg.text else msg.parse_caption_entity(ent)
        except Exception:
            segment = ""
        out.append({
            "offset": int(getattr(ent, "offset", 0) or 0),
            "length": int(getattr(ent, "length", 0) or 0),
            "custom_emoji_id": str(cid),
            "fallback": segment,
        })
    out.sort(key=lambda x: x["offset"])
    return text, out


def _store(catalog, msg, text, entities):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        ws = sh.worksheet("EmojiCapture")
    except Exception:
        ws = sh.add_worksheet(title="EmojiCapture", rows=300, cols=7)
        ws.append_row([
            "captured_at", "channel", "message_id", "telegram_url",
            "text", "custom_emoji_entities_json", "entity_count"
        ], value_input_option="RAW")
    url = f"https://t.me/{catalog.CATALOG_CHANNEL}/{msg.message_id}"
    ws.append_row([
        _now(), catalog.CATALOG_CHANNEL, str(msg.message_id), url,
        text, json.dumps(entities, ensure_ascii=False), str(len(entities))
    ], value_input_option="RAW")


def install(app, catalog):
    async def capture(update, context):
        msg = update.edited_channel_post
        if not msg:
            return
        username = (getattr(msg.chat, "username", None) or "").lstrip("@").lower()
        if username and username != catalog.CATALOG_CHANNEL.lower():
            return
        text, entities = _extract_entities(msg)
        if not entities:
            return
        await asyncio.to_thread(_store, catalog, msg, text, entities)
        log.info(
            "Captured %s custom emoji entities from @%s message_id=%s",
            len(entities), catalog.CATALOG_CHANNEL, msg.message_id,
        )

    app.add_handler(MessageHandler(filters.ALL, capture), group=-60)
    log.info("Channel Premium emoji capture installed for @%s", catalog.CATALOG_CHANNEL)

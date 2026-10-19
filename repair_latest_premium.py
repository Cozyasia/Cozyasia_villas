# -*- coding: utf-8 -*-
"""One-shot repair of the latest listing caption with Cozy Asia Premium Emoji."""
from __future__ import annotations

import asyncio
import json
import logging
import re

import cozy_catalog
import mtproto_user_client
import publication_safety
import post_layout_v6_premium as premium

log = logging.getLogger("repair-latest-premium")
CHANNEL = "samuirental"


def _is_listing(msg) -> bool:
    text = str(getattr(msg, "message", None) or "")
    return bool(text and getattr(msg, "media", None) and publication_safety.lot_from_message(msg))


def _replace_header(html_text: str, lot: str) -> str:
    lines = html_text.splitlines()
    for i, line in enumerate(lines):
        plain = re.sub(r"<[^>]+>", "", line)
        if "ЛОТ" in plain or "🔤" in plain:
            lines[i] = premium._premium_lot(lot)
            break
    return "\n".join(lines)


def _replace_cta(html_text: str) -> str:
    if "tg-emoji" in html_text:
        return html_text
    pattern = re.compile(r"ОСТАВИТЬ\s+ЗАЯВКУ", re.I)
    replacement = premium._premium_word("ОСТАВИТЬ", premium.CTA_IDS) + " " + premium._premium_word("ЗАЯВКУ", premium.CTA_IDS)
    return pattern.sub(replacement, html_text)


async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        messages = [m async for m in client.iter_messages(CHANNEL, limit=120)]
        candidates = [m for m in messages if _is_listing(m)]
        if not candidates:
            raise RuntimeError("No recent media listing with a lot number found")
        msg = max(candidates, key=lambda m: int(m.id))
        lot = publication_safety.lot_from_message(msg)
        from telethon.extensions import html as telethon_html
        old_html = telethon_html.unparse(
            str(getattr(msg, "message", None) or ""),
            list(getattr(msg, "entities", None) or []),
        )
        new_html = _replace_header(old_html, lot)
        new_html = _replace_cta(new_html)
        new_text, new_entities = telethon_html.parse(new_html)
        new_text, new_entities, changed = mtproto_user_client.upgrade_text(new_text, new_entities, lot)
        if not changed:
            raise RuntimeError("Premium conversion produced no custom emoji entities")
        publication_safety.validate_premium_caption(new_text, new_entities, lot)
        try:
            await client.edit_message(
                CHANNEL,
            int(msg.id),
            new_text,
            formatting_entities=new_entities,
                link_preview=False,
            )
        except Exception as exc:
            if exc.__class__.__name__ != "MessageNotModifiedError":
                raise
        verify = await client.get_messages(CHANNEL, ids=int(msg.id))
        entities = list(getattr(verify, "entities", None) or [])
        custom_count = sum(1 for e in entities if getattr(e, "custom_emoji_id", None))
        result = {
            "channel": CHANNEL,
            "message_id": int(msg.id),
            "url": f"https://t.me/{CHANNEL}/{int(msg.id)}",
            "lot": str(lot),
            "custom_emoji_count": custom_count,
            "grouped_id": int(getattr(verify, "grouped_id", 0) or 0),
            "result": "edited",
        }
        if custom_count < 8:
            raise RuntimeError(f"Premium emoji read-back failed: {result}")
        log.info("REPAIR_LATEST_PREMIUM_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("REPAIR_LATEST_PREMIUM_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

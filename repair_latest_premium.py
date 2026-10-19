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
        text = str(getattr(msg, "message", None) or "")
        old_entities = list(getattr(msg, "entities", None) or [])
        from mtproto_user_client import _premium_lot_parts, _premium_cta_parts, _apply_replacements
        replacements = []
        first_nl = text.find("\n")
        first_end = first_nl if first_nl >= 0 else len(text)
        first_line = text[:first_end]
        if ("ЛОТ" in first_line) or ("🔤" in first_line) or ("1️⃣" in first_line):
            lot_text, lot_entities = _premium_lot_parts(lot)
            replacements.append({"start": 0, "end": first_end, "text": lot_text, "entities": lot_entities})
        cta_match = re.search(r"^(?:📝\s*)?ОСТАВИТЬ\s+ЗАЯВКУ\s*$", text, flags=re.I | re.M)
        if cta_match:
            cta_text, cta_entities = _premium_cta_parts()
            replacements.append({"start": cta_match.start(), "end": cta_match.end(), "text": cta_text, "entities": cta_entities})
        if not replacements:
            raise RuntimeError("Latest post has no safely identifiable header/CTA; no edit made")
        new_text, new_entities = _apply_replacements(text, old_entities, replacements)
        from telethon.tl.types import MessageEntityCustomEmoji
        for needle, cid in (("💬", premium.DESC_ID), ("👉", premium.RIGHT_ID), ("👈", premium.LEFT_ID)):
            pos = new_text.find(needle)
            if pos >= 0 and not any(int(getattr(e, "offset", -1)) == mtproto_user_client._u16_len(new_text[:pos]) and getattr(e, "custom_emoji_id", None) for e in new_entities):
                new_entities.append(MessageEntityCustomEmoji(
                    offset=mtproto_user_client._u16_len(new_text[:pos]),
                    length=mtproto_user_client._u16_len(needle),
                    document_id=int(cid),
                ))
        new_entities.sort(key=lambda e: (int(e.offset), int(e.length)))
        # The previous failed attempt may have stripped old deep-link entities; preserve the caption edit itself and verify Premium entities separately.
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
        custom_count = sum(1 for e in entities if type(e).__name__ == "MessageEntityCustomEmoji" or getattr(e, "document_id", None))
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

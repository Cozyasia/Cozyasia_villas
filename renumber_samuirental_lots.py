# -*- coding: utf-8 -*-
"""One-shot in-place sequential renumbering for recent @samuirental albums."""
import asyncio
import json
import logging
import os

import cozy_catalog
import mtproto_user_client
import post_layout_v6_premium as premium
import publication_safety

log = logging.getLogger("renumber-samuirental-lots")

TARGETS = (
    (4955, "1186"),
    (4965, "1187"),
    (4984, "1188"),
    (4989, "1189"),
    (4994, "1190"),
    (4998, "1191"),
)


def enabled():
    return os.getenv("RENUMBER_SAMUIRENTAL_LOTS", "0").strip().lower() in {"1", "true", "yes", "on"}


def _keycaps(lot):
    return "".join(ch + "\ufe0f\u20e3" for ch in str(lot))


def _replace_header_fallback(text, lot):
    lines = (text or "").splitlines()
    if not lines:
        raise RuntimeError("Message has no caption")
    line = lines[0]
    first_digit = next((i for i, ch in enumerate(line) if ch.isdigit()), -1)
    if first_digit < 0:
        raise RuntimeError("Premium header fallback digits were not found")
    line = line[:first_digit] + _keycaps(lot)
    lines[0] = line
    return "\n".join(lines)


async def run():
    if not enabled():
        return {"enabled": False}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results = []
    try:
        channel = await client.get_entity("samuirental")
        inverse_digit_ids = {int(v): k for k, v in premium.DIGIT_IDS.items() if k.isdigit()}
        target_digit_ids = {k: int(v) for k, v in premium.DIGIT_IDS.items() if k.isdigit()}
        for message_id, lot in TARGETS:
            msg = await client.get_messages(channel, ids=message_id)
            if not msg:
                raise RuntimeError(f"Missing @samuirental/{message_id}")
            old_lot = publication_safety.lot_from_message(msg)
            text = _replace_header_fallback(msg.message or "", lot)
            entities = list(msg.entities or [])
            top_u16 = len(text.splitlines()[0].encode("utf-16-le")) // 2
            digit_entities = [
                e for e in sorted(entities, key=lambda x: int(getattr(x, "offset", 0)))
                if type(e).__name__ == "MessageEntityCustomEmoji"
                and int(getattr(e, "offset", 0)) < top_u16
                and int(getattr(e, "document_id", 0)) in inverse_digit_ids
            ]
            if len(digit_entities) != len(lot):
                raise RuntimeError(f"Header digit entity mismatch @{message_id}: {len(digit_entities)}")
            for ent, digit in zip(digit_entities, lot):
                ent.document_id = target_digit_ids[digit]
            for ent in entities:
                url = str(getattr(ent, "url", "") or "")
                if "start=rent_" in url:
                    ent.url = url.split("start=rent_", 1)[0] + "start=rent_" + lot
            publication_safety.validate_premium_caption(text, entities, lot)
            await client.edit_message(channel, message_id, text, formatting_entities=entities, link_preview=False)
            await asyncio.sleep(2)
            verify = await client.get_messages(channel, ids=message_id)
            decoded = publication_safety.lot_from_message(verify)
            urls = [str(getattr(e, "url", "") or "") for e in (verify.entities or [])]
            custom = sum(type(e).__name__ == "MessageEntityCustomEmoji" for e in (verify.entities or []))
            if decoded != lot:
                raise RuntimeError(f"Read-back mismatch @{message_id}: {decoded!r} != {lot!r}")
            if not any(f"start=rent_{lot}" in u for u in urls):
                raise RuntimeError(f"Read-back rent link mismatch @{message_id}")
            results.append({"message_id": message_id, "old_lot": old_lot, "new_lot": lot, "custom_emoji": custom})
        log.info("RENUMBER_SAMUIRENTAL_LOTS_DONE %s", json.dumps(results, ensure_ascii=False))
        return {"enabled": True, "results": results}
    finally:
        await client.disconnect()

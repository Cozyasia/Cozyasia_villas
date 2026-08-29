# -*- coding: utf-8 -*-
"""One-shot repair of recent @samuirental sequence and duplicate publications."""
import asyncio
import json
import logging
import os

import cozy_catalog
import mtproto_user_client
import publication_safety
import publish_fb_replies_20260828 as publication

log = logging.getLogger("renumber-samuirental-lots")

EDITS = (
    (0, "samuirental", 4974, "1188"),
    (1, "samuirental", 4979, "1189"),
    (2, "samuirental", 4994, "1190"),
    (3, "samuirental", 4998, "1191"),
)
DUPLICATE_BIG_IDS = tuple(range(4984, 4994))
DUPLICATE_SMALL_IDS = (930,)


def enabled():
    return os.getenv("RENUMBER_SAMUIRENTAL_LOTS", "0").strip().lower() in {"1", "true", "yes", "on"}


async def _edit(client, item_index, channel_name, message_id, lot):
    channel = await client.get_entity(channel_name)
    current = await client.get_messages(channel, ids=message_id)
    if not current:
        raise RuntimeError(f"Missing @{channel_name}/{message_id}")
    old = publication_safety.lot_from_message(current)
    if old == lot:
        verify = current
    else:
        text, entities = publication._final_caption(publication.LISTINGS[item_index], lot, channel_name)
        await client.edit_message(channel, message_id, text, formatting_entities=entities, link_preview=False)
        await asyncio.sleep(2)
        verify = await client.get_messages(channel, ids=message_id)
    publication_safety.validate_premium_caption(verify.message or "", verify.entities or [], lot)
    return {"channel": channel_name, "message_id": message_id, "old_lot": old, "new_lot": lot,
            "custom_emoji": sum(type(e).__name__ == "MessageEntityCustomEmoji" for e in (verify.entities or []))}


def _update_registry(results):
    sh = cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    ws = sh.worksheet("SourceRegistry")
    rows = ws.get_all_values()
    by_source = {}
    for item_index, channel_name, message_id, lot in EDITS:
        source_id = publication.LISTINGS[item_index]["source_id"]
        by_source.setdefault(source_id, []).append({"channel": channel_name, "message_id": message_id, "lot": lot})
    for row_index, row in enumerate(rows[1:], start=2):
        source_id = row[1] if len(row) > 1 else ""
        if source_id not in by_source:
            continue
        values = by_source[source_id]
        lots = {x["channel"]: x["lot"] for x in values}
        messages = {x["channel"]: x["message_id"] for x in values}
        ws.update(f"H{row_index}:J{row_index}", [[json.dumps(list(lots), ensure_ascii=False),
            json.dumps(lots, ensure_ascii=False), json.dumps(messages, ensure_ascii=False)]], value_input_option="RAW")


async def run():
    if not enabled():
        return {"enabled": False}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results = []
    try:
        for args in EDITS:
            results.append(await _edit(client, *args))
        big = await client.get_entity("samuirental")
        small = await client.get_entity("arenda_vill_samui")
        await client.delete_messages(big, list(DUPLICATE_BIG_IDS))
        await client.delete_messages(small, list(DUPLICATE_SMALL_IDS))
        await asyncio.sleep(3)
        for message_id in DUPLICATE_BIG_IDS:
            if await client.get_messages(big, ids=message_id):
                raise RuntimeError(f"Duplicate big-channel message still exists: {message_id}")
        for message_id in DUPLICATE_SMALL_IDS:
            if await client.get_messages(small, ids=message_id):
                raise RuntimeError(f"Duplicate small-channel message still exists: {message_id}")
        await asyncio.to_thread(_update_registry, results)
        payload={"edits":results,"deleted_big":list(DUPLICATE_BIG_IDS),"deleted_small":list(DUPLICATE_SMALL_IDS)}
        log.info("RENUMBER_SAMUIRENTAL_LOTS_DONE %s", json.dumps(payload, ensure_ascii=False))
        return {"enabled": True, **payload}
    finally:
        await client.disconnect()

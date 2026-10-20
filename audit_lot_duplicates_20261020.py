# -*- coding: utf-8 -*-
"""Audit and clean duplicate 2026-10-19 small-channel villa albums."""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import mtproto_user_client
import cozy_catalog

CHANNEL = "arenda_vill_samui"
OLD_FIRST_IDS = tuple(range(1611, 1702, 10))
KEEP_ITEMS = (
    (1711, "V0️⃣1️⃣", "1️⃣2️⃣2️⃣1️⃣"),
    (1721, "V0️⃣2️⃣", "1️⃣2️⃣2️⃣2️⃣"),
    (1731, "V0️⃣3️⃣", "1️⃣2️⃣2️⃣3️⃣"),
    (1741, "V0️⃣4️⃣", "1️⃣2️⃣2️⃣4️⃣"),
    (1751, "V0️⃣5️⃣", "1️⃣2️⃣2️⃣5️⃣"),
    (1761, "V0️⃣6️⃣", "1️⃣2️⃣2️⃣6️⃣"),
    (1771, "V0️⃣7️⃣", "1️⃣2️⃣2️⃣7️⃣"),
    (1781, "V0️⃣8️⃣", "1️⃣2️⃣2️⃣8️⃣"),
    (1791, "V0️⃣9️⃣", "1️⃣2️⃣2️⃣9️⃣"),
    (1801, "V1️⃣1️⃣", "1️⃣2️⃣3️⃣0️⃣"),
)
LOT_RE = re.compile(r"(?:V(?:0?[1-9]|1[01])|12[-: ]?[12][0-9])", re.I)


def _caption_html(message: Any) -> str:
    from telethon.extensions import html as telethon_html
    raw = getattr(message, "message", None) or getattr(message, "raw_text", None) or ""
    entities = getattr(message, "entities", None) or []
    return telethon_html.unparse(raw, entities)


async def inspect() -> dict[str, Any]:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        channel = await client.get_entity(f"@{CHANNEL}")
        rows = []
        async for m in client.iter_messages(channel, limit=500):
            text = str(getattr(m, "message", "") or "").replace("\n", " ")
            if int(m.id) >= 1600 and int(m.id) <= 1820 and text:
                rows.append({
                    "id": int(m.id),
                    "date": str(getattr(m, "date", "")),
                    "grouped_id": int(getattr(m, "grouped_id", 0) or 0),
                    "hits": LOT_RE.findall(text),
                    "text": text[:700],
                    "url": f"https://t.me/{CHANNEL}/{m.id}",
                })
        return {"channel": CHANNEL, "rows": rows}
    finally:
        await client.disconnect()


async def cleanup() -> dict[str, Any]:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    from telethon.extensions import html as telethon_html
    try:
        channel = await client.get_entity(f"@{CHANNEL}")
        messages = [m async for m in client.iter_messages(channel, limit=500)]
        by_id = {int(m.id): m for m in messages}

        # Resolve complete old albums from their first caption messages.
        delete_ids: set[int] = set()
        old_groups = []
        for first_id in OLD_FIRST_IDS:
            first = by_id.get(first_id)
            if not first:
                continue
            gid = int(getattr(first, "grouped_id", 0) or 0)
            if gid:
                members = [m for m in messages if int(getattr(m, "grouped_id", 0) or 0) == gid]
                ids = [int(m.id) for m in members]
            else:
                ids = [first_id]
            delete_ids.update(ids)
            old_groups.append({"first_id": first_id, "grouped_id": gid, "message_ids": sorted(ids)})

        # Correct visible headers in the one retained album set.
        edited = []
        for message_id, old_header, new_header in KEEP_ITEMS:
            message = by_id.get(message_id) or await client.get_messages(channel, ids=message_id)
            if not message:
                raise RuntimeError(f"kept message {message_id} not found")
            source_html = _caption_html(message)
            updated_html = source_html.replace(old_header, new_header)
            # Also repair plain-text fallbacks if an old header was stored without keycap entities.
            updated_html = updated_html.replace(old_header.replace("️⃣", ""), new_header)
            if updated_html != source_html:
                text, entities = telethon_html.parse(updated_html)
                await client.edit_message(
                    channel,
                    message_id,
                    text=text,
                    formatting_entities=entities,
                    link_preview=False,
                )
            check = await client.get_messages(channel, ids=message_id)
            check_text = str(getattr(check, "message", "") or "")
            if new_header not in check_text or old_header in check_text:
                raise RuntimeError(f"header read-back failed for {message_id}")
            edited.append({"message_id": message_id, "old_header": old_header, "new_header": new_header})

        if delete_ids:
            await client.delete_messages(channel, sorted(delete_ids))

        remaining_old = []
        for first_id in OLD_FIRST_IDS:
            check = await client.get_messages(channel, ids=first_id)
            if check:
                remaining_old.append(first_id)
        return {
            "ok": True,
            "channel": CHANNEL,
            "kept_first_message_ids": [x[0] for x in KEEP_ITEMS],
            "edited": edited,
            "old_groups": old_groups,
            "deleted_message_ids": sorted(delete_ids),
            "remaining_old_first_ids": remaining_old,
        }
    finally:
        await client.disconnect()


def run_service_mode():
    if os.getenv("CLEANUP_DUPLICATE_LOTS_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}:
        result = asyncio.run(cleanup())
        print("LOT_DUPLICATE_CLEANUP=" + json.dumps(result, ensure_ascii=False), flush=True)
    else:
        result = asyncio.run(inspect())
        print("LOT_AUDIT=" + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_service_mode()

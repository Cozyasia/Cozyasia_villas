# -*- coding: utf-8 -*-
"""Audit and remove malformed Facebook villa albums from the Cozy Asia small channel."""
from __future__ import annotations
import asyncio, json, re, os
import mtproto_user_client
import cozy_catalog

CHANNEL = "arenda_vill_samui"
LOT_RE = re.compile(r"\bЛОТ\s+V(?:0?[1-9]|1[01])\b", re.I)

def _is_bad(msg) -> bool:
    text = str(getattr(msg, "message", "") or "")
    if not text:
        return False
    raw_html = any(x in text for x in ("<b>", "</b>", "<blockquote>", "</blockquote>", "<a href="))
    return bool(LOT_RE.search(text)) and raw_html

async def inspect(delete: bool = False) -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        channel = await client.get_entity(f"@{CHANNEL}")
        messages = [m async for m in client.iter_messages(channel, limit=500)]
        bad = [m for m in messages if _is_bad(m)]
        group_ids = {int(getattr(m, "grouped_id", 0) or 0) for m in bad}
        delete_ids = []
        groups = []
        for gid in sorted(group_ids):
            if not gid:
                continue
            members = [m for m in messages if int(getattr(m, "grouped_id", 0) or 0) == gid]
            ids = [int(m.id) for m in members]
            delete_ids.extend(ids)
            groups.append({"grouped_id": gid, "message_ids": ids, "lots": sorted({x for m in members for x in LOT_RE.findall(str(getattr(m, "message", "") or ""))})})
        delete_ids.extend(int(m.id) for m in bad if not getattr(m, "grouped_id", None))
        if delete:
            await client.delete_messages(channel, sorted(set(delete_ids)))
        return {"channel": CHANNEL, "bad_caption_message_ids": [int(m.id) for m in bad], "groups": groups, "deleted_message_ids": sorted(set(delete_ids)) if delete else [], "delete": delete}
    finally:
        await client.disconnect()

def run_service_mode():
    delete = os.getenv("CLEANUP_MALFORMED_FB_VILLA_20261020", "0").strip().lower() in {"1","true","yes","on"}
    result = asyncio.run(inspect(delete=delete))
    print("MALFORMED_FB_VILLA_AUDIT=" + json.dumps(result, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    run_service_mode()

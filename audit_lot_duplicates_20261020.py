# -*- coding: utf-8 -*-
"""Read-only audit of recent small-channel villa lot albums."""
from __future__ import annotations
import asyncio, json, re
import mtproto_user_client
import cozy_catalog

CHANNEL = "arenda_vill_samui"
LOT_RE = re.compile(r"(?:V(?:0?[1-9]|1[01])|12[-: ]?[12][0-9])", re.I)

async def inspect():
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        channel = await client.get_entity(f"@{CHANNEL}")
        rows = []
        async for m in client.iter_messages(channel, limit=500):
            text = str(getattr(m, "message", "") or "").replace("\n", " ")
            hits = LOT_RE.findall(text)
            if hits:
                rows.append({
                    "id": int(m.id),
                    "date": str(getattr(m, "date", "")),
                    "grouped_id": int(getattr(m, "grouped_id", 0) or 0),
                    "hits": hits,
                    "text": text[:700],
                    "url": f"https://t.me/{CHANNEL}/{m.id}",
                })
        return {"channel": CHANNEL, "rows": rows}
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("LOT_AUDIT=" + json.dumps(asyncio.run(inspect()), ensure_ascii=False), flush=True)

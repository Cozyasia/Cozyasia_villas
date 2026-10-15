# -*- coding: utf-8 -*-
"""Remove the accidental duplicate created by the Living Pool one-shot job."""
from __future__ import annotations
import asyncio
import json
import logging

import cozy_catalog
import mtproto_user_client

CHANNEL = "samuirental"
DUPLICATE_MESSAGE_ID = 5184
log = logging.getLogger("cleanup-fb-living-pool-duplicate")

async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        message = await client.get_messages(channel, ids=DUPLICATE_MESSAGE_ID)
        if not message:
            return {"channel": CHANNEL, "message_id": DUPLICATE_MESSAGE_ID, "result": "missing"}
        body = message.message or ""
        if "Чавенг" not in body or "85 000" not in body or "Living Pool" not in body:
            raise RuntimeError("Refusing to delete a message that does not match the accidental duplicate")
        await client.delete_messages(channel, [DUPLICATE_MESSAGE_ID], revoke=True)
        check = await client.get_messages(channel, ids=DUPLICATE_MESSAGE_ID)
        result = {"channel": CHANNEL, "message_id": DUPLICATE_MESSAGE_ID, "result": "deleted" if not check else "still_present"}
        log.info("CLEANUP_FB_LIVING_POOL_DUPLICATE_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()

def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("CLEANUP_FB_LIVING_POOL_DUPLICATE_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

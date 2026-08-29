# -*- coding: utf-8 -*-
"""Read-only diagnostic of recent lot headers in @samuirental."""
import asyncio, json, logging, os
import cozy_catalog, mtproto_user_client, publication_safety
log=logging.getLogger("diagnose-samuirental-lots")

def enabled(): return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled(): return {"enabled":False}
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    rows=[]
    try:
        channel=await client.get_entity("samuirental")
        async for msg in client.iter_messages(channel,limit=140):
            text=(getattr(msg,"message",None) or "").strip()
            if not text: continue
            lot=publication_safety.lot_from_message(msg)
            if not lot: continue
            first=text.splitlines()[0][:160]
            rows.append({"message_id":int(msg.id),"date":msg.date.isoformat(),"lot":lot,"first_line":first,"entities":len(getattr(msg,"entities",None) or [])})
        rows.sort(key=lambda x:x["message_id"])
        result={"enabled":True,"count":len(rows),"rows":rows}
        log.info("DIAGNOSE_SAMUIRENTAL_LOTS_DONE %s",json.dumps(result,ensure_ascii=False))
        return result
    finally:
        await client.disconnect()

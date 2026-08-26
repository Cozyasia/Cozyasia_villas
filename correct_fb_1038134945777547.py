# -*- coding: utf-8 -*-
"""One-shot in-place correction for the two published Facebook albums."""
import asyncio, json, logging, os
import cozy_catalog, mtproto_user_client, publication_safety
import publish_fb_1038134945777547 as publication

log=logging.getLogger("correct-fb-1038134945777547")
TARGETS=(("samuirental",4945,"1185"),("arenda_vill_samui",891,"1182"))

def enabled():
    return os.getenv("CORRECT_FB_1038134945777547","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled(): return {"enabled":False}
    prepared={lot:publication._final_caption(lot) for _,_,lot in TARGETS}
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    results=[]
    try:
        for channel_name,message_id,lot in TARGETS:
            channel=await client.get_entity(channel_name)
            msg=await client.get_messages(channel,ids=message_id)
            if not msg: raise RuntimeError(f"Missing @{channel_name}/{message_id}")
            text,entities=prepared[lot]
            await client.edit_message(channel,message_id,text,formatting_entities=entities,link_preview=False)
            await asyncio.sleep(3)
            verify=await client.get_messages(channel,ids=message_id)
            decoded=publication_safety.lot_from_message(verify)
            custom=sum(type(e).__name__=="MessageEntityCustomEmoji" for e in (verify.entities or []))
            urls=[str(getattr(e,"url","") or "") for e in (verify.entities or [])]
            if decoded!=lot: raise RuntimeError(f"Lot mismatch @{channel_name}: {decoded!r} != {lot}")
            if custom < 21+len(lot): raise RuntimeError(f"Premium entities missing @{channel_name}: {custom}")
            if not any(f"start=rent_{lot}" in u for u in urls): raise RuntimeError(f"Rent link missing @{channel_name}")
            if (verify.message or "").count("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ")!=1: raise RuntimeError(f"CTA duplicate @{channel_name}")
            results.append({"channel":channel_name,"message_id":message_id,"lot":lot,"custom_emoji":custom})
        log.info("CORRECT_FB_1038134945777547_DONE %s",json.dumps(results,ensure_ascii=False))
        return {"enabled":True,"results":results}
    finally: await client.disconnect()

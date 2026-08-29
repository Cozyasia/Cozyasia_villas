# -*- coding: utf-8 -*-
"""Read-only diagnostic of every recent message in @samuirental."""
import asyncio, json, logging, os
import cozy_catalog, mtproto_user_client, publication_safety
log=logging.getLogger("diagnose-samuirental-lots")

def enabled(): return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled(): return {"enabled":False}
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    rows=[]; groups={}
    try:
        channel=await client.get_entity("samuirental")
        async for msg in client.iter_messages(channel,limit=90):
            mid=int(msg.id)
            if mid < 4935: break
            text=(getattr(msg,"message",None) or "")
            gid=int(getattr(msg,"grouped_id",0) or 0)
            if gid: groups[gid]=groups.get(gid,0)+1
            entities=list(getattr(msg,"entities",None) or [])
            custom=[{"offset":int(getattr(e,"offset",0)),"length":int(getattr(e,"length",0)),"doc":str(getattr(e,"document_id",""))} for e in entities if type(e).__name__=="MessageEntityCustomEmoji"]
            rows.append({"message_id":mid,"date":msg.date.isoformat(),"grouped_id":gid,"has_media":bool(getattr(msg,"media",None)),"media_type":type(getattr(msg,"media",None)).__name__,"lot":publication_safety.lot_from_message(msg),"first_line":text.splitlines()[0][:180] if text else "","text_len":len(text),"entities":len(entities),"custom_top":custom[:10]})
        rows.sort(key=lambda x:x["message_id"])
        for row in rows: row["album_size"]=groups.get(row["grouped_id"],0) if row["grouped_id"] else 1
        result={"enabled":True,"count":len(rows),"rows":rows}
        log.info("DIAGNOSE_SAMUIRENTAL_LOTS_DONE %s",json.dumps(result,ensure_ascii=False))
        return result
    finally:
        await client.disconnect()

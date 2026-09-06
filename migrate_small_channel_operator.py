# -*- coding: utf-8 -*-
"""One-shot migration: normalize operator line in every property listing in @arenda_vill_samui."""
from __future__ import annotations

import asyncio, copy, json, logging, re
from telethon.errors import FloodWaitError, MessageNotModifiedError
from telethon.tl.types import MessageEntityMention

import cozy_catalog, mtproto_user_client, publication_safety

log=logging.getLogger("migrate-small-channel-operator")
CHANNEL="arenda_vill_samui"
EXACT="👤 Оператор: @cozy_asia"
HANDLE="@cozy_asia"

def _u16(s):
    return len((s or "").encode("utf-16-le"))//2

def _listing(msg):
    text=getattr(msg,"message",None) or ""
    if not text:
        return False
    lot=publication_safety.lot_from_message(msg)
    if not lot:
        return False
    low=text.lower()
    return any(k in low for k in ("описание","аренд","thb","бат","стоимость","условия"))

def _transform_entities(text, entities, start, end, repl):
    s16=_u16(text[:start]); e16=_u16(text[:end]); delta=_u16(repl)-(e16-s16)
    out=[]
    for ent in copy.deepcopy(list(entities or [])):
        a=int(getattr(ent,"offset",0)); b=a+int(getattr(ent,"length",0))
        if b<=s16:
            out.append(ent)
        elif a>=e16:
            ent.offset=a+delta
            out.append(ent)
        else:
            # Drop formatting/entity overlapping the replaced legacy operator span.
            continue
    hp=repl.find(HANDLE)
    if hp>=0:
        out.append(MessageEntityMention(offset=s16+_u16(repl[:hp]),length=_u16(HANDLE)))
    out.sort(key=lambda e:(int(getattr(e,"offset",0)),-int(getattr(e,"length",0))))
    return out

def _find_legacy(text):
    patterns=[
        r"👤\s*Оператор:\s*@cozy_asia",
        r"Оператор:\s*@cozy_asia",
    ]
    for pat in patterns:
        m=re.search(pat,text,re.I)
        if m:
            return m.start(),m.end()
    return None

def _insert_pos(text):
    # Prefer immediately before final CTA block, otherwise before hashtags.
    p=text.find("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ")
    if p>=0:
        line=text.rfind("\n",0,p)+1
        # If there is an "ОСТАВИТЬ ЗАЯВКУ" block immediately above, operator belongs before it.
        q=text.rfind("ОСТАВИТЬ ЗАЯВКУ",0,line)
        if q>=0 and line-q<300:
            return text.rfind("\n",0,q)+1
        return line
    for m in re.finditer(r"(?m)^\s*#",text):
        return m.start()
    return len(text)

def _compact(text, need):
    # Only remove redundant blank lines; no content changes.
    while need>0 and "\n\n" in text:
        text=text.replace("\n\n","\n",1)
        need-=1
    return text

async def run():
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    scanned=listings=edited=already=errors=too_long=0
    error_ids=[]; too_long_ids=[]; edited_ids=[]
    try:
        channel=await client.get_entity(CHANNEL)
        async for msg in client.iter_messages(channel,limit=None):
            scanned+=1
            if not _listing(msg):
                continue
            listings+=1
            text=getattr(msg,"message",None) or ""
            old_lot=publication_safety.lot_from_message(msg)
            if text.count(EXACT)==1 and not re.search(r"(?<!👤 )Оператор:\s*@cozy_asia",text,re.I):
                already+=1
                continue

            entities=list(getattr(msg,"entities",None) or [])
            legacy=_find_legacy(text)
            if legacy:
                start,end=legacy
                repl=EXACT
                new_text=text[:start]+repl+text[end:]
                new_entities=_transform_entities(text,entities,start,end,repl)
            else:
                pos=_insert_pos(text)
                prefix="" if pos==0 or text[:pos].endswith("\n") else "\n"
                repl=prefix+EXACT+"\n"
                new_text=text[:pos]+repl+text[pos:]
                new_entities=_transform_entities(text,entities,pos,pos,repl)

            # Collapse accidental duplicate exact operator lines if legacy text was malformed.
            if new_text.count(EXACT)>1:
                first=new_text.find(EXACT)
                second=new_text.find(EXACT,first+len(EXACT))
                # Do not risk entity surgery on unexpected duplicate; flag for manual retry.
                errors+=1; error_ids.append(int(msg.id))
                log.error("SMALL_OPERATOR_DUPLICATE_PRECHECK mid=%s",msg.id)
                continue

            media_name=type(getattr(msg,"media",None)).__name__
            limit=4096 if media_name in {"NoneType","MessageMediaWebPage"} else 1024
            if len(new_text)>limit:
                # Rebuild from plain text only if blank-line compaction is enough; preserve all entities
                # by skipping here rather than corrupting formatting.
                too_long+=1; too_long_ids.append(int(msg.id))
                log.warning("SMALL_OPERATOR_TOO_LONG mid=%s len=%s limit=%s",msg.id,len(new_text),limit)
                continue

            try:
                await client.edit_message(channel,int(msg.id),new_text,formatting_entities=new_entities,link_preview=(media_name=="MessageMediaWebPage"))
            except MessageNotModifiedError:
                pass
            except FloodWaitError as exc:
                wait=int(getattr(exc,"seconds",0) or 0)+2
                log.warning("SMALL_OPERATOR_FLOOD_WAIT seconds=%s mid=%s",wait,msg.id)
                await asyncio.sleep(wait)
                try:
                    await client.edit_message(channel,int(msg.id),new_text,formatting_entities=new_entities,link_preview=(media_name=="MessageMediaWebPage"))
                except MessageNotModifiedError:
                    pass
            except Exception:
                errors+=1; error_ids.append(int(msg.id))
                log.exception("SMALL_OPERATOR_EDIT_FAILED mid=%s",msg.id)
                continue

            verify=await client.get_messages(channel,ids=int(msg.id))
            live=getattr(verify,"message",None) or ""
            if live.count(EXACT)!=1:
                errors+=1; error_ids.append(int(msg.id))
                log.error("SMALL_OPERATOR_READBACK_FAILED mid=%s count=%s",msg.id,live.count(EXACT))
                continue
            if old_lot and publication_safety.lot_from_message(verify)!=old_lot:
                errors+=1; error_ids.append(int(msg.id))
                log.error("SMALL_OPERATOR_LOT_CHANGED mid=%s old=%s new=%s",msg.id,old_lot,publication_safety.lot_from_message(verify))
                continue
            edited+=1; edited_ids.append(int(msg.id))
            if edited%10==0:
                log.info("SMALL_OPERATOR_PROGRESS scanned=%s listings=%s edited=%s already=%s too_long=%s errors=%s",scanned,listings,edited,already,too_long,errors)
            await asyncio.sleep(5.0)

        # Final read-only audit of all listing captions.
        audit_listings=audit_missing=audit_bad=0
        sample=[]
        async for msg in client.iter_messages(channel,limit=None,reverse=True):
            if not _listing(msg):
                continue
            audit_listings+=1
            live=getattr(msg,"message",None) or ""
            if EXACT not in live:
                audit_missing+=1
                if len(sample)<20: sample.append(int(msg.id))
            elif live.count(EXACT)!=1:
                audit_bad+=1
                if len(sample)<20: sample.append(int(msg.id))
        result={
            "channel":CHANNEL,"scanned":scanned,"listings":listings,"edited":edited,"already":already,
            "too_long":too_long,"too_long_ids":too_long_ids,"errors":errors,"error_ids":error_ids,
            "audit_listings":audit_listings,"audit_missing":audit_missing,"audit_bad":audit_bad,
            "audit_sample_ids":sample,
            "first_edited_id":min(edited_ids) if edited_ids else None,
            "last_edited_id":max(edited_ids) if edited_ids else None,
            "result":"complete" if audit_missing==0 and audit_bad==0 else "partial"
        }
        log.info("MIGRATE_SMALL_OPERATOR_DONE %s",json.dumps(result,ensure_ascii=False))
        return {"enabled":True,"result":result}
    finally:
        await client.disconnect()

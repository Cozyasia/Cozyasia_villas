# -*- coding: utf-8 -*-
"""Fix Premium lot headers and application CTA for small-channel lots 1200–1207."""
from __future__ import annotations

import asyncio
import copy
import json
import logging

from telethon.errors import FloodWaitError, MessageNotModifiedError
from telethon.tl.types import MessageEntityBold, MessageEntityCustomEmoji, MessageEntityTextUrl

import cozy_catalog
import mtproto_user_client
import post_layout_v6_premium as premium
import publication_safety

log=logging.getLogger("fix-small-premium-1200-1207")
CHANNEL="arenda_vill_samui"
BOT="Cozyasia_villa_bot"
LOTS={
    "1200":931,
    "1201":941,
    "1202":951,
    "1203":961,
    "1204":971,
    "1205":981,
    "1206":991,
    "1207":1001,
}

def u16(s:str)->int:
    return len((s or "").encode("utf-16-le"))//2

def py_from_u16(text:str, offset:int)->int:
    used=0
    for i,ch in enumerate(text):
        if used>=offset:
            return i
        used+=u16(ch)
    return len(text)

def seg(text, ent):
    s=py_from_u16(text,int(ent.offset))
    e=py_from_u16(text,int(ent.offset)+int(ent.length))
    return text[s:e]

def text_urls(text, entities):
    out=[]
    for e in entities or []:
        if isinstance(e,MessageEntityTextUrl):
            out.append((seg(text,e),str(getattr(e,"url","") or "")))
    return out

def _top_is_correct(text, entities, lot):
    nl=text.find("\n")
    top_end=u16(text[:nl if nl>=0 else len(text)])
    custom=[e for e in entities or [] if isinstance(e,MessageEntityCustomEmoji) and int(e.offset)<top_end]
    exp_text, exp=mtproto_user_client._premium_lot_parts(lot)
    got=[int(e.document_id) for e in sorted(custom,key=lambda x:int(x.offset))]
    want=[int(e.document_id) for e in exp]
    return got==want and len(got)==8

def _cta_is_correct(text, entities, lot):
    urls=text_urls(text,entities)
    rent=f"https://t.me/{BOT}?start=rent_{lot}"
    search=f"https://t.me/{BOT}?start=search"
    rent_hits=[u for label,u in urls if label=="ЖМИ ЗДЕСЬ" and u==rent]
    search_hits=[u for label,u in urls if label=="НАПИСАТЬ БОТУ" and u==search]
    # 14 custom emoji IDs for ОСТАВИТЬ + ЗАЯВКУ.
    cta_ids={int(x) for x in premium.CTA_IDS.values()}
    cta_custom=[e for e in entities or [] if isinstance(e,MessageEntityCustomEmoji) and int(e.document_id) in cta_ids]
    return len(rent_hits)==1 and len(search_hits)==1 and len(cta_custom)>=14 and text.count("ЖМИ ЗДЕСЬ")==1

def _replace_top(text, entities, lot):
    nl=text.find("\n")
    end=nl if nl>=0 else len(text)
    new_top, new_top_entities=mtproto_user_client._premium_lot_parts(lot)
    return mtproto_user_client._apply_replacements(
        text,entities,[{"start":0,"end":end,"text":new_top,"entities":new_top_entities}]
    )

def _remove_existing_application(text, entities):
    """Remove a previous application block if present, based on its rent URL or visible marker."""
    rent_ents=[]
    for e in entities or []:
        if isinstance(e,MessageEntityTextUrl) and "start=rent" in str(getattr(e,"url","") or ""):
            rent_ents.append(e)
    # Find visible CTA region using ЖМИ ЗДЕСЬ if present.
    p=text.find("ЖМИ ЗДЕСЬ")
    if p<0 and not rent_ents:
        return text,list(entities or [])
    if p<0 and rent_ents:
        p=py_from_u16(text,int(rent_ents[0].offset))
    # Start at up to two preceding lines; this captures premium ОСТАВИТЬ/ЗАЯВКУ fallback lines.
    line=text.rfind("\n",0,p)
    start=line+1 if line>=0 else 0
    for _ in range(3):
        prev=text.rfind("\n",0,max(0,start-1))
        if prev<0: break
        candidate=text[prev+1:start].strip()
        if candidate and ("🔤" in candidate or candidate.upper() in {"ОСТАВИТЬ","ЗАЯВКУ"}):
            start=prev+1
        elif not candidate:
            start=prev+1
        else:
            break
    # End after the ЖМИ line plus following blank lines, but before search CTA.
    eol=text.find("\n",p)
    end=len(text) if eol<0 else eol+1
    while end<len(text) and text[end]=="\n":
        end+=1
    search=text.find("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ",p)
    if search>=0:
        search_line=text.rfind("\n",0,search)+1
        end=min(end,search_line)
    return mtproto_user_client._apply_replacements(
        text,entities,[{"start":start,"end":end,"text":"","entities":[]}]
    )

def _insert_application(text, entities, lot):
    search=text.find("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ")
    if search<0:
        raise RuntimeError(f"search CTA marker missing lot={lot}")
    pos=text.rfind("\n",0,search)+1
    cta_text,cta_entities=mtproto_user_client._premium_cta_parts()
    block=cta_text+"\n\n👉 ЖМИ ЗДЕСЬ 👈\n\n"
    rel=list(cta_entities)
    # Premium arrows.
    right=block.find("👉")
    left=block.find("👈")
    rel.append(MessageEntityCustomEmoji(
        offset=u16(block[:right]),length=u16("👉"),document_id=int(premium.RIGHT_ID)))
    rel.append(MessageEntityCustomEmoji(
        offset=u16(block[:left]),length=u16("👈"),document_id=int(premium.LEFT_ID)))
    # Deep link to the questionnaire for this exact lot.
    label="ЖМИ ЗДЕСЬ"
    lp=block.find(label)
    rent=f"https://t.me/{BOT}?start=rent_{lot}"
    rel.append(MessageEntityTextUrl(offset=u16(block[:lp]),length=u16(label),url=rent))
    rel.append(MessageEntityBold(offset=u16(block[:lp]),length=u16(label)))
    rel.sort(key=lambda e:(int(e.offset),-int(e.length)))
    return mtproto_user_client._apply_replacements(
        text,entities,[{"start":pos,"end":pos,"text":block,"entities":rel}]
    )

def _fix_search_link(text, entities):
    label="НАПИСАТЬ БОТУ"
    p=text.find(label)
    if p<0:
        raise RuntimeError("НАПИСАТЬ БОТУ marker missing")
    s16=u16(text[:p]); e16=s16+u16(label)
    search=f"https://t.me/{BOT}?start=search"
    out=[]
    found=False
    for e in copy.deepcopy(list(entities or [])):
        if isinstance(e,MessageEntityTextUrl):
            a=int(e.offset); b=a+int(e.length)
            if a==s16 and b==e16:
                if not found:
                    e.url=search
                    out.append(e)
                    found=True
                continue
        out.append(e)
    if not found:
        out.append(MessageEntityTextUrl(offset=s16,length=u16(label),url=search))
        out.append(MessageEntityBold(offset=s16,length=u16(label)))
    out.sort(key=lambda e:(int(e.offset),-int(e.length)))
    return text,out

async def _edit(client,channel,mid,text,entities):
    while True:
        try:
            await client.edit_message(channel,mid,text,formatting_entities=entities,link_preview=False)
            return
        except MessageNotModifiedError:
            return
        except FloodWaitError as exc:
            wait=int(getattr(exc,"seconds",0) or 0)+2
            log.warning("FIX_SMALL_PREMIUM_FLOOD_WAIT mid=%s seconds=%s",mid,wait)
            await asyncio.sleep(wait)

async def run():
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results=[]
    try:
        channel=await client.get_entity(CHANNEL)
        for lot,mid in LOTS.items():
            msg=await client.get_messages(channel,ids=mid)
            if not msg or not getattr(msg,"message",None):
                raise RuntimeError(f"Missing Telegram caption lot={lot} mid={mid}")
            original_group=int(getattr(msg,"grouped_id",0) or 0)
            old_lot=publication_safety.lot_from_message(msg)
            if old_lot!=lot:
                raise RuntimeError(f"Pre-edit lot mismatch mid={mid}: {old_lot!r} != {lot!r}")
            text=getattr(msg,"message",None) or ""
            entities=list(getattr(msg,"entities",None) or [])

            # Replace Unicode fallback header with the real saved Cozy Asia custom emoji IDs.
            text,entities=_replace_top(text,entities,lot)
            # Rebuild application CTA idempotently.
            text,entities=_remove_existing_application(text,entities)
            text,entities=_insert_application(text,entities,lot)
            # Ensure final search CTA goes to the small-channel bot.
            text,entities=_fix_search_link(text,entities)

            if text.count("Оператор: @cozy_asia")!=1:
                raise RuntimeError(f"Operator line invalid lot={lot}")
            if "airbnb.com" in text.lower() or "wa.me/" in text.lower() or "66960471696" in text:
                raise RuntimeError(f"Private/source data leaked lot={lot}")
            if text.count("НАПИСАТЬ БОТУ")!=1 or text.count("ЖМИ ЗДЕСЬ")!=1:
                raise RuntimeError(f"CTA visible count invalid lot={lot}")
            nonblank=[x.strip() for x in text.splitlines() if x.strip()]
            if not nonblank or not nonblank[-1].startswith("#"):
                raise RuntimeError(f"Hashtags are not at bottom lot={lot}")

            await _edit(client,channel,mid,text,entities)
            verify=await client.get_messages(channel,ids=mid)
            live=getattr(verify,"message",None) or ""
            vent=list(getattr(verify,"entities",None) or [])
            if publication_safety.lot_from_message(verify)!=lot:
                raise RuntimeError(f"Post-edit lot mismatch lot={lot}")
            if int(getattr(verify,"grouped_id",0) or 0)!=original_group:
                raise RuntimeError(f"Album grouping changed lot={lot}")
            if not _top_is_correct(live,vent,lot):
                raise RuntimeError(f"Premium lot header verification failed lot={lot}")
            if not _cta_is_correct(live,vent,lot):
                raise RuntimeError(f"Premium CTA/deep-link verification failed lot={lot}")
            if live.count("Оператор: @cozy_asia")!=1:
                raise RuntimeError(f"Operator read-back invalid lot={lot}")
            if "airbnb.com" in live.lower() or "wa.me/" in live.lower() or "66960471696" in live:
                raise RuntimeError(f"Private/source leaked after read-back lot={lot}")
            urls=text_urls(live,vent)
            item={
                "lot":lot,"message_id":mid,"url":f"https://t.me/{CHANNEL}/{mid}",
                "rent_url":f"https://t.me/{BOT}?start=rent_{lot}",
                "search_url":f"https://t.me/{BOT}?start=search",
                "top_premium":True,"application_premium":True,"result":"fixed",
            }
            results.append(item)
            log.info("FIX_SMALL_PREMIUM_LOT_DONE %s",json.dumps(item,ensure_ascii=False))
            await asyncio.sleep(2.0)
        final={"channel":CHANNEL,"count":len(results),"results":results,"result":"complete"}
        log.info("FIX_SMALL_PREMIUM_1200_1207_DONE %s",json.dumps(final,ensure_ascii=False))
        return {"enabled":True,"result":final}
    finally:
        await client.disconnect()

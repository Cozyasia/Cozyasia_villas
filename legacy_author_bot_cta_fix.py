# -*- coding: utf-8 -*-
"""Targeted fallback for legacy @samuirental posts not editable via MTProto.

The current Cozyasia_villas service owns @Cozyasia_villa_bot. Two historical
big-channel posts appear to have been created by that bot, so Telegram rejects
edits from the Premium user and from @cozy_asia_bot. This fallback asks the
original publishing bot to append the correct public CTAs to @cozy_asia_bot.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import requests

import channel_bot_routing as routing
import cozy_catalog
import mtproto_user_client

TARGETS=((4817,"1172"),(4785,"1168"))
CHANNEL="samuirental"
EXPECTED_EDITOR_BOT="Cozyasia_villa_bot"


def _bot_entity(e):
    name=type(e).__name__
    base={"offset":int(getattr(e,"offset",0)),"length":int(getattr(e,"length",0))}
    basic={
        "MessageEntityBold":"bold","MessageEntityItalic":"italic","MessageEntityUnderline":"underline",
        "MessageEntityStrike":"strikethrough","MessageEntitySpoiler":"spoiler","MessageEntityCode":"code",
        "MessageEntityUrl":"url","MessageEntityMention":"mention","MessageEntityHashtag":"hashtag",
        "MessageEntityBotCommand":"bot_command","MessageEntityEmail":"email","MessageEntityPhone":"phone_number",
        "MessageEntityCashtag":"cashtag",
    }
    if name in basic:return {"type":basic[name],**base}
    if name=="MessageEntityTextUrl":return {"type":"text_link",**base,"url":str(getattr(e,"url","") or "")}
    if name=="MessageEntityCustomEmoji":return {"type":"custom_emoji",**base,"custom_emoji_id":str(getattr(e,"document_id","") or "")}
    if name=="MessageEntityPre":return {"type":"pre",**base,"language":str(getattr(e,"language","") or "")}
    if name=="MessageEntityBlockquote":
        return {"type":"expandable_blockquote" if bool(getattr(e,"collapsed",False)) else "blockquote",**base}
    return None


def _edit_with_service_bot(mid,text,entities,is_media):
    token=os.getenv("TELEGRAM_TOKEN","").strip()
    if not token:return {"ok":False,"description":"TELEGRAM_TOKEN missing"}
    me=requests.post(f"https://api.telegram.org/bot{token}/getMe",timeout=20).json()
    username=str((me.get("result") or {}).get("username") or "")
    if not me.get("ok") or username.lower()!=EXPECTED_EDITOR_BOT.lower():
        return {"ok":False,"description":f"Unexpected service bot @{username}"}
    ents=[x for x in (_bot_entity(e) for e in entities or []) if x]
    if is_media:
        method="editMessageCaption"
        payload={"chat_id":f"@{CHANNEL}","message_id":mid,"caption":text,"caption_entities":json.dumps(ents,ensure_ascii=False)}
    else:
        method="editMessageText"
        payload={"chat_id":f"@{CHANNEL}","message_id":mid,"text":text,"entities":json.dumps(ents,ensure_ascii=False),"disable_web_page_preview":"true"}
    return requests.post(f"https://api.telegram.org/bot{token}/{method}",data=payload,timeout=30).json()


def _urls(entities):
    return [str(getattr(e,"url","") or "") for e in entities or [] if getattr(e,"url",None)]


def _valid(urls,lot):
    rent=any(f"t.me/cozy_asia_bot?start=rent_{lot}" in u.lower() for u in urls)
    search=any("t.me/cozy_asia_bot?start=search" in u.lower() for u in urls)
    return rent and search


async def run():
    if not routing.enabled():return {"enabled":False}
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client:raise RuntimeError("MTProto session unavailable for read-back")
    results=[]
    try:
        channel=await client.get_entity(CHANNEL)
        for mid,lot in TARGETS:
            msg=await client.get_messages(channel,ids=mid)
            if not msg or not getattr(msg,"message",None):
                results.append({"message_id":mid,"lot":lot,"result":"missing"});continue
            current=_urls(msg.entities or [])
            if _valid(current,lot):
                results.append({"message_id":mid,"lot":lot,"result":"already_correct"});continue
            text,entities,changed=routing._append_missing_ctas(msg.message,msg.entities or [],CHANNEL,lot,bool(getattr(msg,"media",None)))
            if not changed:
                results.append({"message_id":mid,"lot":lot,"result":"no_change"});continue
            reply=await asyncio.to_thread(_edit_with_service_bot,mid,text,entities,bool(getattr(msg,"media",None)))
            if not reply.get("ok"):
                results.append({"message_id":mid,"lot":lot,"result":"failed","error":str(reply.get("description") or "unknown")});continue
            await asyncio.sleep(1)
            verify=await client.get_messages(channel,ids=mid)
            urls=_urls(getattr(verify,"entities",None) or [])
            results.append({"message_id":mid,"lot":lot,"result":"corrected" if _valid(urls,lot) else "verify_failed"})
        return {"enabled":True,"results":results}
    finally:
        await client.disconnect()

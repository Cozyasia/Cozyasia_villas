# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 1993231127859485."""
from __future__ import annotations
import asyncio, json, logging, os, tempfile, zipfile
from pathlib import Path
import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
import cozy_catalog, mtproto_user_client, publication_safety

log=logging.getLogger("publish-fb-1993231127859485")
SOURCE_ID="facebook_marketplace_1993231127859485"
CHANNEL="samuirental"
BOT_USERNAME="Cozyasia_villa_bot"
DRIVE_FILE_ID="1KYTbHcMutC0KULMmV-eoMH1U7Tp6jQZM"
PHOTO_SUFFIXES=(
"cozy_asia_1993231127859485_01.jpg",
"cozy_asia_1993231127859485_43.jpg",
"cozy_asia_1993231127859485_17.jpg",
"cozy_asia_1993231127859485_32.jpg",
"cozy_asia_1993231127859485_22.jpg",
"cozy_asia_1993231127859485_41.jpg",
"cozy_asia_1993231127859485_23.jpg",
"cozy_asia_1993231127859485_10.jpg",
"cozy_asia_1993231127859485_24.jpg",
"cozy_asia_1993231127859485_06.jpg",
)

def _caption_html(lot:str)->str:
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Тропическая вилла в балийском стиле с приватным бассейном. Полностью меблирована, недавно отремонтирована, с большой кухней западного типа, просторной гостиной, садом и крытой парковкой. Территория полностью огорожена и обеспечивает хорошую приватность.</blockquote>

📍 Район: уточняется
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 3
🏊 Бассейн: приватный
🚗 Парковка: крытая
🐾 Питомцы: разрешены с дополнительным депозитом

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 70 000 THB/мес
🔐 Депозит: уточняется
🤝 Комиссия: 5 000 THB
📅 Доступность: свободна
📆 Только долгосрочная аренда
⚡ Электричество: гос. тариф
💧 Вода: гос. тариф
📶 Wi‑Fi: включён
🏊 Обслуживание бассейна: включено

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>НАПИСАТЬ БОТУ</b></a> 👈

🔎 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #PoolVilla #KohSamuiRental #CozyAsia"""

def _final_caption(lot:str):
    from telethon.extensions import html as telethon_html
    text,entities=telethon_html.parse(_caption_html(lot))
    text,entities,changed=mtproto_user_client.upgrade_text(text,entities,lot)
    if not changed: raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text,entities,lot)
    if len(text)>1024: raise RuntimeError(f"Album caption too long: {len(text)}")
    return text,entities

def _download_photos(directory:str)->list[str]:
    raw=os.environ.get("GOOGLE_CREDS_JSON","").strip()
    if not raw: raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    info=json.loads(raw)
    creds=service_account.Credentials.from_service_account_info(info,scopes=["https://www.googleapis.com/auth/drive.readonly"])
    creds.refresh(GoogleAuthRequest())
    response=requests.get(f"https://www.googleapis.com/drive/v3/files/{DRIVE_FILE_ID}?alt=media",headers={"Authorization":f"Bearer {creds.token}"},timeout=90)
    response.raise_for_status()
    zp=Path(directory)/"facebook_1993231127859485.zip"; zp.write_bytes(response.content)
    pd=Path(directory)/"photos"; pd.mkdir(parents=True,exist_ok=True)
    paths=[]
    with zipfile.ZipFile(zp) as archive:
        names=archive.namelist()
        for suffix in PHOTO_SUFFIXES:
            matches=[n for n in names if n.endswith("/photos/"+suffix) or n.endswith(suffix)]
            if len(matches)!=1: raise RuntimeError(f"Expected one archive member for {suffix}, found {len(matches)}")
            target=pd/suffix; target.write_bytes(archive.read(matches[0]))
            paths.append(str(target))
    return paths

async def run()->dict:
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel=await client.get_entity(CHANNEL)
        duplicate=await publication_safety.find_duplicate_listing(client,channel,("70 000","балийском","долгосрочная"),limit=300)
        if duplicate:
            lot=publication_safety.lot_from_message(duplicate)
            result={"channel":CHANNEL,"lot":lot,"message_id":int(duplicate.id),"result":"already","source":SOURCE_ID}
            log.info("PUBLISH_FB_1993231127859485_DONE %s",json.dumps(result,ensure_ascii=False))
            return {"enabled":True,"result":result}
        previous=await publication_safety.latest_numeric_lot(client,channel,limit=300)
        if not previous: raise RuntimeError("Could not determine previous live lot")
        lot=str(int(previous)+1)
        await publication_safety.assert_next_lot(client,channel,lot)
        text,entities=_final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-1993231127859485-") as directory:
            photos=await asyncio.to_thread(_download_photos,directory)
            sent=await client.send_file(channel,photos,caption=text,formatting_entities=entities,link_preview=False)
        messages=sent if isinstance(sent,list) else [sent]
        caption_msg=next((m for m in messages if getattr(m,"message",None)),messages[0])
        verify=await client.get_messages(channel,ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify)!=lot: raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message,verify.entities,lot)
        for signature in ("70 000","5 000","долгосрочная"):
            if signature not in (verify.message or ""): raise RuntimeError(f"Read-back signature missing: {signature}")
        result={"channel":CHANNEL,"lot":lot,"message_id":int(caption_msg.id),"result":"published","photos":len(PHOTO_SUFFIXES),"source":SOURCE_ID}
        log.info("PUBLISH_FB_1993231127859485_DONE %s",json.dumps(result,ensure_ascii=False))
        return {"enabled":True,"result":result}
    finally:
        await client.disconnect()

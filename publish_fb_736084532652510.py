# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 736084532652510."""
from __future__ import annotations
import asyncio, json, logging, os, tempfile, zipfile
from pathlib import Path
import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
import cozy_catalog, mtproto_user_client, publication_safety

log=logging.getLogger("publish-fb-736084532652510")
SOURCE_ID="facebook_marketplace_736084532652510"
CHANNEL="samuirental"
BOT_USERNAME="cozy_asia_bot"
DRIVE_FILE_ID="1tNBkX_TgJH-My7bug9rpxQWoLHnpuzAs"
PHOTO_SUFFIXES=(
"01-bedroom-main.png",
"02-bedroom-view.png",
"03-bedroom-tv.png",
"04-bathroom.png",
"05-kitchen.png",
"06-dining-area.png",
)

def _caption_html(lot:str)->str:
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Уютные апартаменты с одной спальней в районе Wat Sawang Arom на Самуи. Подойдут для комфортного долгосрочного проживания одного человека или пары. Есть отдельная кухня, кондиционер, рабочее место, телевизор, стиральная машина и необходимая мебель.</blockquote>

📍 Район: Wat Sawang Arom, Самуи
🏠 Тип: апартаменты
🛏 Спальни: 1
🛁 Ванные: 1
🏊 Бассейн: нет
🐾 Питомцы: уточняется

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 22 000 THB/мес
🔐 Депозит: 5 000 THB
🤝 Комиссия: 5 000 THB
📅 Доступность: свободны сейчас
📆 При долгосрочной аренде возможна скидка
⚡ Электричество: 8 THB/юнит
💧 Вода: 250 THB/чел
📶 Wi‑Fi: включён
🧹 Уборка: 1 раз в неделю бесплатно

🗺 <a href="https://maps.app.goo.gl/Vz8GwJsuMEQLiL638?g_st=com.google.maps.preview.copy"><b>ГЕОЛОКАЦИЯ</b></a>

✨ Дополнительно: отдельная оборудованная кухня · стиральная машина · парковка · рабочее место

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #АпартаментыСамуи #WatSawangArom #KohSamuiRental #CozyAsia"""

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
    creds=service_account.Credentials.from_service_account_info(
        info,scopes=["https://www.googleapis.com/auth/drive.readonly"])
    creds.refresh(GoogleAuthRequest())
    response=requests.get(
        f"https://www.googleapis.com/drive/v3/files/{DRIVE_FILE_ID}?alt=media",
        headers={"Authorization":f"Bearer {creds.token}"},timeout=90)
    response.raise_for_status()
    zp=Path(directory)/"facebook_736084532652510.zip"; zp.write_bytes(response.content)
    pd=Path(directory)/"photos"; pd.mkdir(parents=True,exist_ok=True)
    paths=[]
    with zipfile.ZipFile(zp) as archive:
        names=archive.namelist()
        for suffix in PHOTO_SUFFIXES:
            matches=[n for n in names if n.endswith("/"+suffix) or n==suffix]
            if len(matches)!=1:
                raise RuntimeError(f"Expected one archive member for {suffix}, found {len(matches)}")
            target=pd/suffix
            target.write_bytes(archive.read(matches[0]))
            paths.append(str(target))
    return paths

async def run()->dict:
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel=await client.get_entity(CHANNEL)
        duplicate=await publication_safety.find_duplicate_listing(
            client,channel,("22 000","Wat Sawang Arom","250 THB"),limit=300)
        if duplicate:
            lot=publication_safety.lot_from_message(duplicate)
            result={"channel":CHANNEL,"lot":lot,"message_id":int(duplicate.id),
                    "result":"already","source":SOURCE_ID}
            log.info("PUBLISH_FB_736084532652510_DONE %s",json.dumps(result,ensure_ascii=False))
            return {"enabled":True,"result":result}
        previous=await publication_safety.latest_numeric_lot(client,channel,limit=300)
        if not previous: raise RuntimeError("Could not determine previous live lot")
        lot=str(int(previous)+1)
        await publication_safety.assert_next_lot(client,channel,lot)
        text,entities=_final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-736084532652510-") as directory:
            photos=await asyncio.to_thread(_download_photos,directory)
            sent=await client.send_file(
                channel,photos,caption=text,formatting_entities=entities,link_preview=False)
        messages=sent if isinstance(sent,list) else [sent]
        caption_msg=next((m for m in messages if getattr(m,"message",None)),messages[0])
        verify=await client.get_messages(channel,ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify)!=lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message,verify.entities,lot)
        for signature in ("22 000","5 000","Wat Sawang Arom","250 THB"):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back signature missing: {signature}")
        if (verify.message or "").count("НАПИСАТЬ БОТУ") != 1:
            raise RuntimeError("НАПИСАТЬ БОТУ must occur exactly once")
        result={"channel":CHANNEL,"lot":lot,"message_id":int(caption_msg.id),
                "result":"published","photos":len(PHOTO_SUFFIXES),"source":SOURCE_ID}
        log.info("PUBLISH_FB_736084532652510_DONE %s",json.dumps(result,ensure_ascii=False))
        return {"enabled":True,"result":result}
    finally:
        await client.disconnect()

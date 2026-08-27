# -*- coding: utf-8 -*-
"""One-shot, idempotent publication of Marketplace item 28520466234226624."""
from __future__ import annotations
import asyncio, json, logging, os
from datetime import datetime, timezone
from pathlib import Path
import cozy_catalog, mtproto_user_client, publication_safety

log=logging.getLogger("publish-fb-28520466234226624")
SOURCE_ID="facebook_marketplace_28520466234226624"
SOURCE_URL="https://www.facebook.com/marketplace/item/28520466234226624/"
OWNER_URL="https://www.facebook.com/marketplace/profile/100065378491465/?product_id=28520466234226624"
CHANNELS=("samuirental","arenda_vill_samui")
BOT_USERNAME="Cozyasia_villa_bot"
ASSET_DIR=Path(__file__).with_name("publication_assets")/SOURCE_ID
PHOTO_NAMES=[f"{i:02d}.jpg" for i in range(1,10)]

def enabled():
    return os.getenv("PUBLISH_FB_28520466234226624","0").strip().lower() in {"1","true","yes","on"}

def _caption_html(lot):
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Уютный отдельный дом в тихом районе Бан-Тай с приватным бассейном и видом на зелёные холмы. На фото — светлая гостиная, кухня с обеденной зоной, 2 спальни с кондиционерами, ванная комната, просторный огороженный двор и зона отдыха у бассейна.</blockquote>

📍 Район: Бан-Тай, Маенам
📍 <a href="https://maps.google.com/?q=Baan+Tai+Maenam+Koh+Samui">Локация на карте</a>
🏠 Тип: частный дом
🛏 Спальни: 2
🛁 Ванные: 1
🏊 Бассейн: приватный
🐾 Питомцы: разрешены

💰 <b>Условия аренды</b>
💵 Цена: 45 000 THB/мес
🔐 Депозит: 1 месяц
🤝 Комиссия Cozy Asia: 5 000 THB
📅 Доступность: сейчас — до 30 декабря 2026
⚡ Электричество: государственный тариф
💧 Вода: 500 THB/мес
📶 Wi-Fi: включён
🏊 Обслуживание бассейна: включено, 1 раз в месяц
🧹 Уборка и вывоз мусора: оплачиваются отдельно

✨ Огороженная территория · вид на горы · уличный душ у бассейна · просторный двор

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #БанТай #Маенам #ДомСамуи #ВиллаСамуи #Бассейн #МожноСПитомцами #CozyAsia"""

def _final_caption(lot):
    from telethon.extensions import html as telethon_html
    text,entities=telethon_html.parse(_caption_html(lot))
    text,entities,changed=mtproto_user_client.upgrade_text(text,entities,lot)
    if not changed: raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text,entities,lot)
    if len(text)>1024: raise RuntimeError(f"Album caption too long: {len(text)}")
    return text,entities

def _store_source(results):
    ws=cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID).worksheet("SourceRegistry")
    if any(len(r)>1 and r[1]==SOURCE_ID for r in ws.get_all_values()[1:]): return
    ws.append_row([datetime.now(timezone.utc).isoformat(timespec="seconds"),SOURCE_ID,SOURCE_URL,OWNER_URL,"35000","2-bedroom private pool house in Baan Tai, Maenam; pet friendly; mountain view.","Available now through 2026-12-30",json.dumps([r["channel"] for r in results],ensure_ascii=False),json.dumps({r["channel"]:r["lot"] for r in results},ensure_ascii=False),json.dumps({r["channel"]:r["message_id"] for r in results},ensure_ascii=False),"published","Owner: Apilada Ketkaew. Availability confirmed in Messenger; public contacts removed."],value_input_option="RAW")

async def run():
    if not enabled(): return {"enabled":False}
    photos=[str(ASSET_DIR/n) for n in PHOTO_NAMES]
    if any(not Path(p).is_file() for p in photos): raise RuntimeError("Missing publication assets")
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    results=[]
    try:
        for channel_name in CHANNELS:
            channel=await client.get_entity(channel_name)
            duplicate=await publication_safety.find_duplicate_listing(client,channel,("Бан-Тай","45 000","500 THB/мес","30 декабря 2026"),limit=220)
            if duplicate:
                results.append({"channel":channel_name,"lot":publication_safety.lot_from_message(duplicate),"message_id":int(duplicate.id),"result":"already"}); continue
            previous=await publication_safety.latest_numeric_lot(client,channel,limit=220)
            lot=str(int(previous)+1)
            await publication_safety.assert_next_lot(client,channel,lot)
            text,entities=_final_caption(lot)
            sent=await client.send_file(channel,photos,caption=text,formatting_entities=entities)
            messages=sent if isinstance(sent,list) else [sent]
            caption_msg=next((m for m in messages if getattr(m,"message",None)),messages[0])
            verify=await client.get_messages(channel,ids=int(caption_msg.id))
            if publication_safety.lot_from_message(verify)!=lot: raise RuntimeError("Read-back lot mismatch")
            publication_safety.validate_premium_caption(verify.message,verify.entities,lot)
            results.append({"channel":channel_name,"lot":lot,"message_id":int(caption_msg.id),"result":"published"})
            await asyncio.sleep(2)
        await asyncio.to_thread(_store_source,results)
        log.info("PUBLISH_FB_28520466234226624_DONE %s",json.dumps(results,ensure_ascii=False))
        return {"enabled":True,"results":results}
    finally:
        await client.disconnect()

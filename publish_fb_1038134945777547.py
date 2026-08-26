# -*- coding: utf-8 -*-
"""One-shot, idempotent publication of Facebook Marketplace item 1038134945777547."""
from __future__ import annotations
import asyncio, json, logging, os
from datetime import datetime, timezone
from pathlib import Path
import cozy_catalog, mtproto_user_client, publication_safety

log = logging.getLogger("publish-fb-1038134945777547")
SOURCE_ID = "facebook_marketplace_1038134945777547"
SOURCE_URL = "https://www.facebook.com/marketplace/item/1038134945777547/"
OWNER_URL = "https://www.facebook.com/marketplace/profile/61550073990530/?product_id=1038134945777547"
CHANNELS = ("samuirental", "arenda_vill_samui")
BOT_USERNAME = "Cozyasia_villa_bot"
ASSET_DIR = Path(__file__).with_name("publication_assets") / SOURCE_ID
PHOTO_NAMES = ["01_pool_seaview.png", "02_terrace_pool.png", "03_seaview.png", "04_open_plan.png", "05_living_tv.png", "06_kitchen.png", "07_bathroom.png", "08_lounge.png", "09_bedroom_one.png", "10_bedroom_two.png"]

def enabled():
    return os.getenv("PUBLISH_FB_1038134945777547", "0").strip().lower() in {"1","true","yes","on"}

def _caption_html(lot):
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Меблированный двухуровневый таунхаус с панорамным видом на море и приватным инфинити-бассейном. На фото — просторная гостиная, обеденная зона, оборудованная кухня, 2 спальни, санузел и открытая терраса с зоной отдыха.</blockquote>

📍 Район: Ко Самуи, точная локация по запросу
🏠 Тип: таунхаус
🛏 Спальни: 2
🛁 Ванные: 2,5
🏊 Бассейн: Да, приватный инфинити-бассейн
🐾 Питомцы: Не указано

💰 <b>Условия аренды</b>
💵 Цена: 60 000 THB/мес
🔐 Депозит: Не указано
🤝 Комиссия: 5 000 THB
📅 Доступность: доступен сейчас
⚡ Электричество: 7 THB/кВт·ч
💧 Вода: 2 000 THB/мес
📶 Wi‑Fi: 800 THB/мес

✨ Дополнительно: полностью меблирован · гостиная · кухня · терраса · вид на море

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ТаунхаусСамуи #ВиллаСамуи #Бассейн #ВидНаМоре #KohSamuiRental #CozyAsia"""

def _final_caption(lot):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed: raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    if len(text) > 1024: raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities

def _store_source(results):
    sh = cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    try: ws = sh.worksheet("SourceRegistry")
    except Exception:
        ws = sh.add_worksheet(title="SourceRegistry", rows=500, cols=12)
        ws.append_row(["created_at","source_id","source_url","owner_url","original_price_thb","original_description","availability","channels_json","lots_json","message_ids_json","status","notes"], value_input_option="RAW")
    if any(len(r)>1 and r[1]==SOURCE_ID for r in ws.get_all_values()[1:]): return
    ws.append_row([datetime.now(timezone.utc).isoformat(timespec="seconds"),SOURCE_ID,SOURCE_URL,OWNER_URL,"50000","Townhouse for Rent – Sea View. 2 bedrooms, 2.5 bathrooms, living room, kitchen, fully furnished.","Available now",json.dumps([r["channel"] for r in results],ensure_ascii=False),json.dumps({r["channel"]:r["lot"] for r in results},ensure_ascii=False),json.dumps({r["channel"]:r["message_id"] for r in results},ensure_ascii=False),"published","Public owner contacts removed; original source retained internally."], value_input_option="RAW")

async def run():
    if not enabled(): return {"enabled":False}
    photos=[str(ASSET_DIR/n) for n in PHOTO_NAMES]
    missing=[p for p in photos if not Path(p).is_file()]
    if missing: raise RuntimeError(f"Missing publication assets: {missing}")
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    results=[]
    try:
        for channel_name in CHANNELS:
            channel=await client.get_entity(channel_name)
            duplicate=await publication_safety.find_duplicate_listing(client,channel,("таунхаус","60 000","инфинити-бассейн","2 000 THB/мес"),limit=160)
            if duplicate:
                results.append({"channel":channel_name,"lot":publication_safety.lot_from_message(duplicate),"message_id":int(duplicate.id),"result":"already"}); continue
            previous=await publication_safety.latest_numeric_lot(client,channel,limit=160)
            if not previous: raise RuntimeError(f"Could not determine latest lot for @{channel_name}")
            lot=str(int(previous)+1)
            await publication_safety.assert_next_lot(client,channel,lot)
            text,entities=_final_caption(lot)
            sent=await client.send_file(channel,photos,caption=text,formatting_entities=entities)
            messages=sent if isinstance(sent,list) else [sent]
            caption_msg=next((m for m in messages if getattr(m,"message",None)),messages[0])
            verify=await client.get_messages(channel,ids=int(caption_msg.id))
            if publication_safety.lot_from_message(verify)!=lot: raise RuntimeError(f"Read-back lot mismatch in @{channel_name}")
            results.append({"channel":channel_name,"lot":lot,"message_id":int(caption_msg.id),"result":"published"})
            await asyncio.sleep(2)
        await asyncio.to_thread(_store_source,results)
        log.info("PUBLISH_FB_1038134945777547_DONE %s",json.dumps(results,ensure_ascii=False))
        return {"enabled":True,"results":results}
    finally: await client.disconnect()

# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 1405490825011828."""
from __future__ import annotations
import asyncio, json, logging, os
from datetime import datetime, timezone
from pathlib import Path
import cozy_catalog, mtproto_user_client, publication_safety

log=logging.getLogger("publish-fb-1405490825011828")
SOURCE_ID="facebook_marketplace_1405490825011828"
SOURCE_URL="https://www.facebook.com/marketplace/item/1405490825011828/"
OWNER_NAME="Supattra PL"
CHANNELS=("samuirental","arenda_vill_samui")
BOT_USERNAME="Cozyasia_villa_bot"
ASSET_DIR=Path(__file__).with_name("publication_assets")/SOURCE_ID
PHOTO_NAMES=[f"{i:02d}.jpg" for i in range(1,11)]

def enabled():
    return os.getenv("PUBLISH_FB_1405490825011828","0").strip().lower() in {"1","true","yes","on"}

def _caption_html(lot):
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Свежий после ремонта частный дом в Маенаме с приватным бассейном. Светлый интерьер, гостиная, оборудованная кухня, обеденная зона, 2 просторные спальни, 2 ванные и гостевой санузел. Крытая парковка на 4–5 автомобилей.</blockquote>

📍 Район: Маенам, Soi 6
🗺 <a href="https://maps.google.com/?q=Maenam+Soi+6+Koh+Samui">Примерная локация</a>
🏠 Тип: частный дом
🛏 Спальни: 2
🛁 Ванные: 2 + гостевой санузел
🏊 Бассейн: приватный
🐾 Питомцы: нельзя

💰 <b>Условия аренды</b>
💵 75 000 THB/мес — договор на год
💵 78 000 THB/мес — договор на 6 месяцев
🔐 Депозит: уточняется
🤝 Комиссия Cozy Asia: 5 000 THB
📅 Доступен с 1 сентября 2026
⚡ Электричество: государственный тариф
💧 Вода: государственный тариф
📶 Интернет: включён
🧹 Уборка дома: 2 раза в месяц
🏊 Обслуживание бассейна: 2 раза в неделю

✨ 3 кондиционера · 2 ТВ · духовка · СВЧ · стиральная и сушильная машины · 500 м до пляжа

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Маенам #ДомСамуи #ВиллаСамуи #Бассейн #KohSamuiRental #CozyAsia"""

def _final_caption(lot):
    from telethon.extensions import html as telethon_html
    text,entities=telethon_html.parse(_caption_html(lot))
    text,entities,changed=mtproto_user_client.upgrade_text(text,entities,lot)
    if not changed: raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text,entities,lot)
    if len(text)>1024: raise RuntimeError(f"Album caption too long: {len(text)}")
    return text,entities

def _store_source(results):
    sh=cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    try: ws=sh.worksheet("SourceRegistry")
    except Exception:
        ws=sh.add_worksheet(title="SourceRegistry",rows=500,cols=12)
        ws.append_row(["created_at","source_id","source_url","owner_url","original_price_thb","original_description","availability","channels_json","lots_json","message_ids_json","status","notes"],value_input_option="RAW")
    if any(len(r)>1 and r[1]==SOURCE_ID for r in ws.get_all_values()[1:]): return
    ws.append_row([datetime.now(timezone.utc).isoformat(timespec="seconds"),SOURCE_ID,SOURCE_URL,"", "65000 yearly / 68000 six months","Newly renovated 2-bedroom private pool house, Maenam Soi 6. Internet and twice-monthly cleaning included; utilities excluded.","Available from 2026-09-01",json.dumps([r["channel"] for r in results],ensure_ascii=False),json.dumps({r["channel"]:r["lot"] for r in results},ensure_ascii=False),json.dumps({r["channel"]:r["message_id"] for r in results},ensure_ascii=False),"published",f"Owner: {OWNER_NAME}. Public contacts removed; source retained internally."],value_input_option="RAW")

async def run():
    if not enabled(): return {"enabled":False}
    photos=[str(ASSET_DIR/n) for n in PHOTO_NAMES]
    missing=[p for p in photos if not Path(p).is_file()]
    if missing: raise RuntimeError(f"Missing assets: {missing}")
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client: raise RuntimeError("MTProto Premium session is not authorized")
    results=[]
    try:
        for channel_name in CHANNELS:
            channel=await client.get_entity(channel_name)
            duplicate=await publication_safety.find_duplicate_listing(client,channel,("Маенам","75 000","1 сентября 2026","приватный бассейн"),limit=180)
            if duplicate:
                results.append({"channel":channel_name,"lot":publication_safety.lot_from_message(duplicate),"message_id":int(duplicate.id),"result":"already"}); continue
            previous=await publication_safety.latest_numeric_lot(client,channel,limit=180)
            if not previous: raise RuntimeError(f"Could not determine latest lot for @{channel_name}")
            lot=str(int(previous)+1)
            await publication_safety.assert_next_lot(client,channel,lot)
            text,entities=_final_caption(lot)
            sent=await client.send_file(channel,photos,caption=text,formatting_entities=entities)
            messages=sent if isinstance(sent,list) else [sent]
            caption_msg=next((m for m in messages if getattr(m,"message",None)),messages[0])
            verify=await client.get_messages(channel,ids=int(caption_msg.id))
            if publication_safety.lot_from_message(verify)!=lot: raise RuntimeError(f"Read-back lot mismatch in @{channel_name}")
            publication_safety.validate_premium_caption(verify.message,verify.entities,lot)
            results.append({"channel":channel_name,"lot":lot,"message_id":int(caption_msg.id),"result":"published"})
            await asyncio.sleep(2)
        await asyncio.to_thread(_store_source,results)
        log.info("PUBLISH_FB_1405490825011828_DONE %s",json.dumps(results,ensure_ascii=False))
        return {"enabled":True,"results":results}
    finally: await client.disconnect()

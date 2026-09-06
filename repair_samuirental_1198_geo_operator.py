# -*- coding: utf-8 -*-
"""One-shot repair of @samuirental message 5075 / lot 1198."""
from __future__ import annotations
import json, logging
import cozy_catalog, mtproto_user_client, publication_safety

log=logging.getLogger("repair-samuirental-1198-geo-operator")
CHANNEL="samuirental"
MESSAGE_ID=5075
LOT="1198"
BOT="cozy_asia_bot"
GEO="https://maps.app.goo.gl/Vz8GwJsuMEQLiL638?g_st=com.google.maps.preview.copy"

def _html():
    return f"""🏡 <b>ЛОТ №{LOT}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Уютные апартаменты с одной спальней в районе Wat Sawang Arom на Самуи. Для долгосрочного проживания одного человека или пары. Есть отдельная кухня, кондиционер, рабочее место, телевизор, стиральная машина и мебель.</blockquote>

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

📍 Геолокация: <a href="{GEO}">{GEO}</a>

✨ Дополнительно: отдельная кухня · стиральная машина · парковка · рабочее место

Оператор: @cozy_asia

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT}?start=rent_{LOT}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #АпартаментыСамуи #WatSawangArom #KohSamuiRental #CozyAsia"""

async def run():
    from telethon.extensions import html as telethon_html
    client=await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel=await client.get_entity(CHANNEL)
        before=await client.get_messages(channel,ids=MESSAGE_ID)
        if not before or not getattr(before,"message",None):
            raise RuntimeError("Target message is missing")
        text,entities=telethon_html.parse(_html())
        text,entities,changed=mtproto_user_client.upgrade_text(text,entities,LOT)
        if not changed:
            raise RuntimeError("Premium conversion failed")
        publication_safety.validate_premium_caption(text,entities,LOT)
        if len(text)>1024:
            raise RuntimeError(f"Caption too long: {len(text)}")
        await client.edit_message(channel,MESSAGE_ID,text,formatting_entities=entities,link_preview=False)
        verify=await client.get_messages(channel,ids=MESSAGE_ID)
        if publication_safety.lot_from_message(verify)!=LOT:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message,verify.entities,LOT)
        live=verify.message or ""
        for signature in (GEO,"Оператор: @cozy_asia","22 000","5 000"):
            if signature not in live:
                raise RuntimeError(f"Read-back signature missing: {signature}")
        if live.count("НАПИСАТЬ БОТУ")!=1:
            raise RuntimeError("НАПИСАТЬ БОТУ must occur exactly once")
        if not [x for x in live.splitlines() if x.strip()][-1].startswith("#"):
            raise RuntimeError("Hashtags are not at absolute bottom")
        result={"channel":CHANNEL,"message_id":MESSAGE_ID,"lot":LOT,"result":"edited","geo":GEO,"operator":"@cozy_asia"}
        log.info("REPAIR_SAMUIRENTAL_1198_DONE %s",json.dumps(result,ensure_ascii=False))
        return {"enabled":True,"result":result}
    finally:
        await client.disconnect()

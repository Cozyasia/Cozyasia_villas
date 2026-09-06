# -*- coding: utf-8 -*-
"""One-shot repair of @samuirental message 5065 / lot 1197."""
from __future__ import annotations
import json, logging
import cozy_catalog, mtproto_user_client, publication_safety

log = logging.getLogger("repair-samuirental-1197-layout")
CHANNEL = "samuirental"
MESSAGE_ID = 5065
LOT = "1197"
BOT = "cozy_asia_bot"

def _html():
    return f"""🏡 <b>ЛОТ №{LOT}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Тропическая вилла в балийском стиле с приватным бассейном. Полностью меблирована, недавно отремонтирована, с большой кухней западного типа, просторной гостиной, садом и крытой парковкой. Территория полностью огорожена и обеспечивает хорошую приватность.</blockquote>

📍 Район: уточняется
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 3
🏊 Бассейн: приватный
🐾 Питомцы: разрешены с дополнительным депозитом

💰 <b>Условия аренды</b>
💵 Цена: 70 000 THB/мес
🔐 Депозит: уточняется
🤝 Комиссия: 5 000 THB
📅 Доступность: свободна
📆 Только долгосрочная аренда
⚡ Электричество: гос. тариф
💧 Вода: гос. тариф
📶 Wi‑Fi: включён
🏊 Обслуживание бассейна: включено

✨ Дополнительно: 🚗 Парковка: крытая

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT}?start=rent_{LOT}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #PoolVilla #KohSamuiRental #CozyAsia"""

async def run():
    from telethon.extensions import html as telethon_html
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        before = await client.get_messages(channel, ids=MESSAGE_ID)
        if not before or not getattr(before, "message", None):
            raise RuntimeError("Target message is missing")
        before_lot = publication_safety.lot_from_message(before)

        text, entities = telethon_html.parse(_html())
        text, entities, changed = mtproto_user_client.upgrade_text(text, entities, LOT)
        if not changed:
            raise RuntimeError("Premium conversion failed")
        publication_safety.validate_premium_caption(text, entities, LOT)
        if len(text) > 1024:
            raise RuntimeError(f"Caption too long: {len(text)}")

        await client.edit_message(channel, MESSAGE_ID, text, formatting_entities=entities, link_preview=False)

        verify = await client.get_messages(channel, ids=MESSAGE_ID)
        after_lot = publication_safety.lot_from_message(verify)
        if after_lot != LOT:
            raise RuntimeError(f"Read-back lot mismatch: {after_lot!r}")
        publication_safety.validate_premium_caption(verify.message, verify.entities, LOT)
        if verify.message.count("НАПИСАТЬ БОТУ") != 1:
            raise RuntimeError("Bot label is not final-only")
        tags = [x for x in verify.message.splitlines() if x.strip()]
        if not tags[-1].startswith("#"):
            raise RuntimeError("Hashtags are not at absolute bottom")
        result = {
            "channel": CHANNEL,
            "message_id": MESSAGE_ID,
            "lot": LOT,
            "before_lot": before_lot,
            "after_lot": after_lot,
            "bot_label_count": verify.message.count("НАПИСАТЬ БОТУ"),
            "result": "edited"
        }
        log.info("REPAIR_SAMUIRENTAL_1197_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

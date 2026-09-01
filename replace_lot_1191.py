# -*- coding: utf-8 -*-
"""One-shot replacement of lot 1191 with the owner-supplied photo album."""
from __future__ import annotations

import base64
import logging
import os
import tempfile
from pathlib import Path

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("replace-lot-1191")
FLAG = "REPLACE_LOT_1191"
CHANNEL = "samuirental"
LOT = "1191"
OLD_MESSAGE_ID = 4998
ASSET_DIR = Path(__file__).with_name("publication_assets") / "lot_1191_owner"
PHOTO_NAMES = (
    "01_bathroom.jpg.b64",
    "02_kitchen.jpg.b64",
    "03_living_pool_view.jpg.b64",
    "04_bedroom_one.jpg.b64",
    "05_living_dining.jpg.b64",
    "06_terrace_view.jpg.b64",
    "07_private_pool_day.jpg.b64",
    "08_private_pool_night.jpg.b64",
    "10_bedroom_two.jpg.b64",
)


def enabled():
    return os.getenv(FLAG, "0").strip().lower() in {"1", "true", "yes", "on"}


def _caption():
    return f"""🏡 <b>ЛОТ №{LOT}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современная видовая вилла в холмах Бопхута с приватным бассейном и открытой панорамой острова. Светлая гостиная объединена с кухней и обеденной зоной, из комнат есть выход к бассейну и террасе. Вилла полностью меблирована и готова к заселению.</blockquote>

📍 Район: Бопхут, холмы
🏠 Тип: приватная вилла
🛏 Спальни: 2
🛁 Ванные: 2
🏊 Бассейн: приватный
🌅 Панорамный вид
🍳 Оборудованная кухня
🛋 Полностью меблирована

📌 <b>РАСПОЛОЖЕНИЕ</b>
🚗 5 минут до Fisherman’s Village
🏖 5 минут до пляжа Бопхут
🛒 10 минут до супермаркета
🛍 15 минут до Central Chaweng
🗺 <a href="https://maps.google.com/?q=Bophut+Hills+Koh+Samui"><b>ГЕОЛОКАЦИЯ РАЙОНА</b></a>

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 50 000 THB/мес
📅 Срок аренды: от 2 месяцев до 1 года
✅ Доступность: свободна сейчас
🔐 Депозит: 1 месяц аренды
🤝 Комиссия: 5 000 THB
⚡ Электричество: 7 THB/кВт·ч
📶 Интернет 1 Гбит/с: 500 THB/мес
🗑 Вывоз мусора: 800 THB
💧 Вода: бесплатно
🏊 Обслуживание бассейна: включено

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/cozy_asia_bot?start=rent_{LOT}"><b>НАПИСАТЬ БОТУ</b></a> 👈

🔎 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/cozy_asia_bot?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Бопхут #KohSamuiRental #CozyAsia"""


def _final_caption():
    from telethon.extensions import html as telethon_html

    text, entities = telethon_html.parse(_caption())
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, LOT)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, LOT)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities


def _decode_photos(root):
    photos = []
    for name in PHOTO_NAMES:
        source = ASSET_DIR / name
        target = Path(root) / name.removesuffix(".b64")
        target.write_bytes(base64.b64decode(source.read_text(encoding="ascii")))
        if target.stat().st_size < 10_000:
            raise RuntimeError(f"Photo is too small: {name}")
        photos.append(str(target))
    return photos


async def run():
    if not enabled():
        return {"enabled": False}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        old = await client.get_messages(channel, ids=OLD_MESSAGE_ID)
        if old and publication_safety.lot_from_message(old) not in {None, LOT}:
            raise RuntimeError(f"Refusing to replace message {OLD_MESSAGE_ID}: it is not lot {LOT}")

        # Idempotency: if a later multi-photo lot 1191 already exists, keep it and
        # only remove the obsolete single-photo source message.
        existing = await publication_safety.find_duplicate_listing(
            client, channel, ("Бопхут, холмы", "Интернет 1 Гбит/с", "50 000"), limit=80
        )
        if existing and int(existing.id) != OLD_MESSAGE_ID:
            if old:
                await client.delete_messages(channel, [OLD_MESSAGE_ID])
            return {"enabled": True, "result": "already", "message_id": int(existing.id), "lot": LOT}

        text, entities = _final_caption()
        with tempfile.TemporaryDirectory(prefix="lot-1191-") as tmp:
            photos = _decode_photos(tmp)
            sent = await client.send_file(
                channel,
                photos,
                caption=text,
                formatting_entities=entities,
                link_preview=False,
            )
        first = sent[0] if isinstance(sent, list) else sent
        verify = await client.get_messages(channel, ids=first.id)
        if publication_safety.lot_from_message(verify) != LOT:
            await client.delete_messages(channel, [m.id for m in sent] if isinstance(sent, list) else [sent.id])
            raise RuntimeError("Replacement read-back failed")
        if old:
            await client.delete_messages(channel, [OLD_MESSAGE_ID])
        log.info("REPLACE_LOT_1191_DONE message_id=%s photos=%s", first.id, len(PHOTO_NAMES))
        return {"enabled": True, "result": "published", "message_id": int(first.id), "lot": LOT, "photos": len(PHOTO_NAMES)}
    finally:
        await client.disconnect()

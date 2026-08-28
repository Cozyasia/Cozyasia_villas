# -*- coding: utf-8 -*-
"""One-shot, idempotent publication of Airbnb listing 1074551173034733330."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-airbnb-1074551173034733330")
SOURCE_ID = "airbnb_1074551173034733330"
SOURCE_URL = "https://www.airbnb.com/rooms/1074551173034733330"
OWNER_URL = "https://www.airbnb.com/users/profile/1463722496404980781"
CHANNEL = "arenda_vill_samui"
BOT_USERNAME = "Cozyasia_villa_bot"
PHOTO_URLS = [
    "https://a0.muscache.com/im/pictures/hosting/Hosting-1074551173034733330/original/dd205a80-ca4f-429f-8857-9f35b671eb2e.png?im_w=1200",
    "https://a0.muscache.com/im/pictures/hosting/Hosting-1074551173034733330/original/dd82f48e-d61d-46d3-b803-720f738e7058.png?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/d4f68396-72be-4b8f-ae81-1068440042ca.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/69926fc2-2644-4858-b83a-10567b9af236.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/47488d98-014b-4026-bbec-907e99dcabcf.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/1099004c-a8a7-4b23-a80f-98a4fae87df7.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/9a0d222e-b504-4647-a487-dbe00e9f8d96.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/5775e1e9-0c5a-4ce8-b0cd-670c36ef6a47.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/dd5a70c7-eddd-403e-a33e-d0c805ecac42.jpeg?im_w=1200",
    "https://a0.muscache.com/im/pictures/miso/Hosting-1074551173034733330/original/012fe42a-f1a2-4590-b205-36fe881b6346.jpeg?im_w=1200",
]


def enabled():
    return os.getenv("PUBLISH_AIRBNB_1074551173034733330", "0").strip().lower() in {"1", "true", "yes", "on"}


def _caption_html(lot):
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Aqua Jai 2 — роскошная вилла на холмах Чавенга с панорамным видом на море и частным infinity-бассейном. Три просторные спальни с кроватями King size и собственными ванными, открытая гостиная, террасы и яркие закаты над Самуи.</blockquote>

📍 Район: холмы Чавенга, Бо Пхут
📍 <a href="https://maps.google.com/?q=Chaweng+Hills+Koh+Samui">Локация на карте</a>
🏠 Вилла целиком · до 6 гостей
🛏 3 спальни · 🛁 3 ванные
🏊 Приватный панорамный бассейн
🐾 Можно с питомцами

🎄 <b>АРЕНДА НА НОВЫЙ 2027 ГОД</b>
📅 31.12.2026–03.01.2027 — <b>50 000 THB</b>
📅 07.12.2026–13.12.2026 — <b>55 000 THB</b>
📆 Другие даты — по запросу
🤝 Комиссия Cozy Asia: 3 000 THB
⚡ Электричество: 8 THB/кВт⋅ч
🧹 Уборка при выезде до 7 ночей включена; дополнительная — 2 500 THB
🚗 Рекомендуется автомобиль или мотобайк
🚫 Без вечеринок и сильного шума

📞 Собственник: Михаэль
☎️ +60 16-480 5897

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #НовыйГодНаСамуи #Чавенг #ВиллаСамуи #ВидНаМоре #CozyAsia"""


def _final_caption(lot):
    from telethon.extensions import html as telethon_html

    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities


def _store_source(result):
    ws = cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID).worksheet("SourceRegistry")
    if any(len(r) > 1 and r[1] == SOURCE_ID for r in ws.get_all_values()[1:]):
        return
    ws.append_row([
        datetime.now(timezone.utc).isoformat(timespec="seconds"), SOURCE_ID, SOURCE_URL, OWNER_URL,
        "50000 / 55000", "Aqua Jai 2; 3-bedroom ocean-view villa with private infinity pool in Chaweng Hills.",
        "2026-12-07 to 2026-12-13; 2026-12-31 to 2027-01-03; other dates on request",
        json.dumps([result["channel"]], ensure_ascii=False),
        json.dumps({result["channel"]: result["lot"]}, ensure_ascii=False),
        json.dumps({result["channel"]: result["message_id"]}, ensure_ascii=False),
        "published", "Owner permission confirmed by Cozy Asia. Owner: Michael; public contact +60 16-480 5897."
    ], value_input_option="RAW")


def _download_photos(directory):
    paths = []
    for index, url in enumerate(PHOTO_URLS, 1):
        path = Path(directory) / f"{index:02d}.jpg"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            path.write_bytes(response.read())
        if path.stat().st_size < 20_000:
            raise RuntimeError(f"Downloaded photo is unexpectedly small: {path.name}")
        paths.append(str(path))
    return paths


async def run():
    if not enabled():
        return {"enabled": False}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("Aqua Jai 2", "31.12.2026", "50 000 THB"), limit=240
        )
        if duplicate:
            result = {"channel": CHANNEL, "lot": publication_safety.lot_from_message(duplicate),
                      "message_id": int(duplicate.id), "result": "already"}
        else:
            previous = await publication_safety.latest_numeric_lot(client, channel, limit=240)
            lot = str(int(previous) + 1)
            await publication_safety.assert_next_lot(client, channel, lot)
            text, entities = _final_caption(lot)
            with tempfile.TemporaryDirectory(prefix="aqua-jai-") as directory:
                photos = await asyncio.to_thread(_download_photos, directory)
                sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities)
            messages = sent if isinstance(sent, list) else [sent]
            caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
            verify = await client.get_messages(channel, ids=int(caption_msg.id))
            if publication_safety.lot_from_message(verify) != lot:
                raise RuntimeError("Read-back lot mismatch")
            publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
            result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id), "result": "published"}
        await asyncio.to_thread(_store_source, result)
        log.info("PUBLISH_AIRBNB_1074551173034733330_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

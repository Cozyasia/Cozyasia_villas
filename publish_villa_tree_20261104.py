# -*- coding: utf-8 -*-
"""One-shot publication for LOT 1237 via Render Telethon."""
from __future__ import annotations
import asyncio, json, logging, tempfile
from pathlib import Path
import requests
import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-villa-tree-20261104")
CHANNEL = "arenda_vill_samui"
SOURCE_ID = "google_drive_folder_1Xy2AjZ9d5GjSzJFVoKQEZ36CMkOOBGfR"
SOURCE_URL = "https://drive.google.com/drive/folders/1Xy2AjZ9d5GjSzJFVoKQEZ36CMkOOBGfR?usp=sharing"
MAP_URL = "https://maps.app.goo.gl/BwnjJVpRzE9zTCgN8"
DRIVE_URL = "https://drive.google.com/drive/folders/1-4evIQJW4KmIr_QW2D61EFKuAQfmNdWG"
PHOTO_URLS = [
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/01.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/02.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/03.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/04.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/05.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/06.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/07.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/08.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/09.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot1237/10.jpg",
]

def caption_html(lot):
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>VILLA TREE SAMUI — тропическая вилла с 4 спальнями и приватным бассейном в тихой зелёной локации Маенама.</blockquote>

📍 Район: Маенам
🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: вилла
🛏 Спальни: 4
🛁 Ванные: 4
🏊 Бассейн: приватный
🚗 Парковка: да
🌿 Тихая тропическая локация
🧹 Уборка раз в неделю · 🌊 Обслуживание бассейна и сада

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 160 000 THB/мес
🤝 Комиссия Cozy Asia: 7 500 THB
🔐 Депозит: 25 000 THB при заселении
⚡ Электричество: 7,5 THB/kWh
💧 Вода: 400 THB/ночь
📅 Доступность: по запросу

📸 <a href="{DRIVE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Маенам #СнятьВиллуСамуи #CozyAsia"""

def final_caption(lot):
    from telethon.extensions import html
    text, entities = html.parse(caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    channel_publication_policy.validate_listing_caption(text, entities, lot, CHANNEL)
    if len(text) > 1024:
        raise RuntimeError(f"Caption too long: {len(text)}")
    return text, entities

def download_photos(directory):
    p = Path(directory) / "photos"
    p.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, url in enumerate(PHOTO_URLS, 1):
        target = p / f"{i:02d}.png"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        target.write_bytes(r.content)
        paths.append(str(target))
    if len(paths) != 10 or any(Path(x).stat().st_size < 10000 for x in paths):
        raise RuntimeError("Expected exactly 10 valid property photos")
    return paths

async def run():
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("Telethon session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        recent = await client.get_messages(channel, limit=80)
        duplicate = next((m for m in recent if publication_safety.lot_from_message(m) == "1237"), None)
        if duplicate:
            result = {"channel": CHANNEL, "lot": "1237", "message_id": int(duplicate.id), "result": "already_published", "photos": 10, "source": SOURCE_ID}
            log.info("PUBLISH_VILLA_TREE_20261104_DONE %s", json.dumps(result, ensure_ascii=False))
            return result
        lot = "1237"
        text, entities = final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="villa-tree-") as d:
            photos = await asyncio.to_thread(download_photos, d)
            sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)
        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        for signature in ("Маенам", "160 000", "7 500"):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back signature missing: {signature}")
        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id), "result": "published", "photos": len(photos), "source": SOURCE_ID}
        log.info("PUBLISH_VILLA_TREE_20261104_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()

def run_service_mode():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("PUBLISH_VILLA_TREE_20261104_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

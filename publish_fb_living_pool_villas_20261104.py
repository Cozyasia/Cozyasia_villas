# -*- coding: utf-8 -*-
"""One-shot publication for LOT 12-35 via the existing Render Telethon worker."""
from __future__ import annotations
import asyncio, json, logging, tempfile
from pathlib import Path
import requests
import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety
import publish_fb_living_pool_villas_20261015 as legacy

log = logging.getLogger("publish-fb-living-pool-villas-20261104")
CHANNEL = "arenda_vill_samui"
SOURCE_ID = "facebook_post_TheLivingPoolVillasKohSamui_1172710827988074"
SOURCE_URL = "https://www.facebook.com/TheLivingPoolVillasKohSamui/posts/pfbid0fj7TF7xwyYCbY2Qsc3fy8ysgUaNzCMPxUVv5KWJ7GdKZdsS6KNCrCiNzYRfUY8hDl"
MAP_URL = "https://maps.app.goo.gl/E7FujCNftjVi1ZNN7"
DRIVE_URL = "https://drive.google.com/drive/folders/1Vt5hmGMSao7-S1cnh9Ytpuk-H9WBKcY2"
PHOTO_URLS = [
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot12-35/06.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot12-35/07.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot12-35/08.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot12-35/09.jpg",
    "https://raw.githubusercontent.com/Cozyasia/Cozyasia_villas/main/assets/lot12-35/10.jpg",
]

def caption_html(lot):
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Двухспальная вилла с приватным бассейном и джакузи в центре Чавенга. Доступна посуточно, помесячно и на год.</blockquote>

📍 Район: Чавенг
🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 2, ванна и горячая вода
🏊 Бассейн: приватный, с джакузи
📏 Площадь: 240 м²
❄️ Кондиционеры · 📶 Wi‑Fi · 📺 Smart TV
🍳 Оборудованная кухня · 🏊 Общий бассейн отеля
🚗 Парковка · 🧹 Уборка виллы и бассейна раз в неделю
💧 Вода включена · ☕ THONG JAN 55 Café & Bar
🏖 До пляжа Чавенг — 1,5 км · ✈️ Аэропорт — 4,5 км

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 90 000 THB/мес
🤝 Комиссия Cozy Asia: 5 000 THB
🔐 Депозит: 10 000 THB, возвратный
⚡ Электричество: 8 THB/unit
💧 Вода: включена
📅 Доступность: посуточно, помесячно и на год, даты подтверждаются

📸 <a href="{DRIVE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Чавенг #СнятьВиллуСамуи #CozyAsia"""

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
    for i, encoded in enumerate(legacy.PHOTO_B64, 1):
        target = p / f"{i:02d}.jpg"
        target.write_bytes(__import__("base64").b64decode(encoded))
        paths.append(str(target))
    for i, url in enumerate(PHOTO_URLS, 6):
        target = p / f"{i:02d}.jpg"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.facebook.com/"}, timeout=60)
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
        await client.delete_messages(channel, list(range(1901, 1931)))
        recent = await client.get_messages(channel, limit=80)
        duplicate = next((m for m in recent if publication_safety.lot_from_message(m) == "1235"), None)
        if duplicate:
            result = {"channel": CHANNEL, "lot": "1235", "message_id": int(duplicate.id), "result": "already_published", "photos": 10, "source": SOURCE_ID}
            log.info("PUBLISH_FB_LIVING_POOL_20261104_DONE %s", json.dumps(result, ensure_ascii=False))
            return result
        lot = "1235"
        text, entities = final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-living-pool-") as d:
            photos = await asyncio.to_thread(download_photos, d)
            sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)
        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        for signature in ("Чавенг", "90 000", "5 000"):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back signature missing: {signature}")
        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id), "result": "published", "photos": len(photos), "source": SOURCE_ID}
        log.info("PUBLISH_FB_LIVING_POOL_20261104_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()

def run_service_mode():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("PUBLISH_FB_LIVING_POOL_20261104_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

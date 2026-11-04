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
"https://scontent-den2-1.xx.fbcdn.net/v/t39.30808-6/491859810_1172711174654706_3830793778810090455_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1212&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=aFJGPnl_AdIQ7kNvwGrcURw&_nc_oc=AdrFB7rwDVSErvnNGIpjgDXYR1NiIQKjz7neoJ--GqNSvijyECB7C0E4zg0tW4Zr7vUX_ntEMJzI05c9iSB1Uhdj&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=Bgjw9UYAydI2ewVYqQ8vrg&_nc_ss=7b2a8&oh=00_AQSqEsKPq3aq7lSUGRRcSJwzwu5LL7r0Gl6XGU3wvJJ_9Q&oe=6AF0F0D8",
"https://scontent-den2-1.xx.fbcdn.net/v/t39.30808-6/491843065_1172712617987895_965314525203906071_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=101&ccb=1-7&_nc_sid=833d8c&_nc_ohc=b-ZkPjw_rwcQ7kNvwHZ0dhx&_nc_oc=Ador6MARifQ9zk1L7xXYLnKjy5S6XsJm-Wavti3qNAbJsUdr9cMUUw5aSQ7HI2N75UyKHxIBNrvthudbhFtPGja-&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=Bgjw9UYAydI2ewVYqQ8vrg&_nc_ss=7b2a8&oh=00_AQTNO4YTD3WOuCTipgHy7Evdcd0k8eYuYM407_T37ZAjYA&oe=6AF0F10F",
"https://scontent-den2-1.xx.fbcdn.net/v/t39.30808-6/491960774_1172713374654486_4737601601611731255_n.jpg?stp=dst-jpg_tt6&cstp=mx1536x2048&ctp=s590x590&_nc_cat=102&ccb=1-7&_nc_sid=833d8c&_nc_ohc=oDVHDVLEdAQQ7kNvwHyKb8i&_nc_oc=AdotHjA9C2SbG5gnkW9k7Xy72OUFU4UnBk6a-1GjV0_E0BPJczP90gbJvm9wwkH-fD4xP2LQTW1BU7_Epr3uj1Jm&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=Bgjw9UYAydI2ewVYq8vrg&_nc_ss=7b2a8&oh=00_AQTSafs8ayFGO0SRQ00AGa8Y7SnzNq3wlerDzlkfLDiElw&oe=6AF11451",
"https://scontent-den2-1.xx.fbcdn.net/v/t39.30808-6/492141453_1172713264654497_4114511531823071674_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=108&ccb=1-7&_nc_sid=833d8c&_nc_ohc=osdcx7ZKmKsQ7kNvwH1H3kh&_nc_oc=AdpY7WDgnGeP9Bg77IAgdbyM05wwm6MRfYO6B5b5-3qx2ZT9d4EhRjP1SqE2vxImEpbg24r8RpINGMaun8i_i4Zb&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=Bgjw9UYAydI2ewVYqQ8vrg&_nc_ss=7b2a8&oh=00_AQSQfGycF3oVwGKG93MGRBLBd2vl2n255mmiFMKbVDDZAg&oe=6AF10877",
"https://scontent-den2-1.xx.fbcdn.net/v/t39.30808-6/491292571_1172712611321229_5047101303473597363_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=105&ccb=1-7&_nc_sid=833d8c&_nc_ohc=U7qmtAlbmRcQ7kNvwFZM0rX&_nc_oc=Adq_B2vJMh9iOhUsnn_LltXf_d9UVCKmw0my8-fcGZwC32bfJiAicGogapfoG7Zy4lnkQOMfwVyhXoLrP6qVPtzw&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=Bgjw9UYAydI2ewVYqQ8vrg&_nc_ss=7b2a8&oh=00_AQSW3k5Msy9tN-4QXtGZKmAtxNeFcwlLW9X9wUWPGbgfTQ&oe=6AF0E445",
]
def caption_html(lot):
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Уютная двухспальная вилла с приватным бассейном и джакузи в центре Чавенга. Подходит для посуточной, помесячной и годовой аренды. На территории — отельная инфраструктура, общий бассейн, кафе-бар и общая зона отдыха.</blockquote>

📍 Район: Чавенг
🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 2, ванна и горячая вода
🏊 Бассейн: приватный, с джакузи
📏 Площадь: 240 м²
❄️ Кондиционеры
📶 Бесплатный Wi‑Fi
📺 Smart TV, Netflix и YouTube
🍳 Полностью оборудованная кухня
🏊 Общий бассейн отеля
🚗 Парковка для автомобиля или байка
🧹 Уборка виллы и бассейна 1 раз в неделю, включая обслуживание хлора
💧 Вода включена
☕ THONG JAN 55 Café & Bar
🏖 До пляжа Чавенг — 1,5 км
🛒 Tesco Lotus — 1 км
🛍 Central Festival — 3 км
✈️ Аэропорт — 4,5 км

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
        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine previous live lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)
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
        for signature in ("Чавенг", "90 000", "5 000", "12-35"):
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

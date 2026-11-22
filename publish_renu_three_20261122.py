# -*- coding: utf-8 -*-
"""Publish the next three RENU villas to the small Cozy Asia channel.

This is an explicitly gated, duplicate-safe one-shot used by Render.  The
website is the source of truth for the photographs and prices; no owner or
commission data is invented here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path

import requests

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import post_layout_v6_premium
import publication_safety

log = logging.getLogger("publish-renu-three-20261122")
CHANNEL = "arenda_vill_samui"

LISTINGS = [
    {
        "lot": "1242",
        "district": "Ламай",
        "title": "Villa Capri",
        "description": (
            "Villa Capri — просторная вилла с видом на море в холмах Ламая, рядом со смотровой площадкой Overlap Stone. "
            "5 спален, 4 ванные комнаты, размещение до 10 гостей, большой приватный infinity-бассейн, терраса, "
            "оборудованная кухня и частная парковка. Четыре спальни расположены на основном уровне; отдельная большая "
            "спальня находится этажом ниже и имеет собственную ванную и террасу. Подъезд крутой, рекомендуется автомобиль или скутер."
        ),
        "features": "🛏 5 спален · 🛁 4 ванные · 🏊 приватный infinity-бассейн · 🌊 вид на море · 👥 до 10 гостей",
        "price": "270 424 THB/мес (≈ 7 954 USD)",
        "daily": "7 054 THB/сутки (≈ 207 USD)",
        "weekly": "78 098 THB/7 ночей (≈ 2 297 USD)",
        "electricity": "7 THB/кВт⋅ч",
        "site": "https://cozy-asia.com/ru/properties/cw_f43e88fb5c08",
        "photos": [
            "https://api.cozy-asia.com/api/public/media/cwm_830cc04226795b1563fc08d1",
            "https://api.cozy-asia.com/api/public/media/cwm_92601f6b939d4073d6ec9edb",
            "https://api.cozy-asia.com/api/public/media/cwm_d608834ef078ccca26eb8593",
            "https://api.cozy-asia.com/api/public/media/cwm_c25e8889ed361676e7038eb9",
            "https://api.cozy-asia.com/api/public/media/cwm_d0768f9d6411b800a1635253",
            "https://api.cozy-asia.com/api/public/media/cwm_7e7129ad014512a69429c85d",
            "https://api.cozy-asia.com/api/public/media/cwm_fbc270396dddd5c50af45c6a",
            "https://api.cozy-asia.com/api/public/media/cwm_3e9a1dd57dbd3e85c46eb7d3",
            "https://api.cozy-asia.com/api/public/media/cwm_468667f27d285253e2863bc3",
            "https://api.cozy-asia.com/api/public/media/cwm_9631ce05a56c5fdd69d7f183",
        ],
        "hashtags": "#Самуи #АрендаВиллы #Ламай #CozyAsia #KohSamui #PoolVilla",
    },
    {
        "lot": "1243",
        "district": "Ламай",
        "title": "Sunset of Siam",
        "description": (
            "Sunset of Siam — современная вилла площадью около 330 м² в тихом районе в семи минутах к югу от Ламая. "
            "4 спальни-сьюта, 4 ванные комнаты, размещение до 8 гостей, приватный infinity-бассейн 10×4 м, бильярд, "
            "оборудованная кухня, тропический сад и крытая парковка. В каждой спальне king-size кровать, собственная ванная, "
            "гардеробная, Smart TV, быстрый Wi‑Fi и терраса или балкон. До ближайшего пляжа около 3 минут на машине."
        ),
        "features": "🛏 4 спальни · 🛁 4 ванные · 🏊 infinity-бассейн 10×4 м · 🎱 бильярд · 👥 до 8 гостей",
        "price": "293 068 THB/мес (≈ 8 620 USD)",
        "daily": "5 063 THB/сутки (≈ 149 USD)",
        "weekly": "91 168 THB/7 ночей (≈ 2 681 USD)",
        "deposit": "10 000 THB",
        "electricity": "7 THB/кВт⋅ч",
        "site": "https://cozy-asia.com/ru/properties/cw_3c7119f2e0ad",
        "photos": [
            "https://api.cozy-asia.com/api/public/media/cwm_5846ab035d2aeec6b2e9ba56",
            "https://api.cozy-asia.com/api/public/media/cwm_f1ced901b5a5783b4065b8e0",
            "https://api.cozy-asia.com/api/public/media/cwm_e6fcad763b83003afbbad415",
            "https://api.cozy-asia.com/api/public/media/cwm_bf9592dc092800c9c300c09d",
            "https://api.cozy-asia.com/api/public/media/cwm_c820e5185d8aa87c7a472809",
            "https://api.cozy-asia.com/api/public/media/cwm_aae0fe0674bed5b170ba866d",
            "https://api.cozy-asia.com/api/public/media/cwm_c159250bf03b0624b78fc0f7",
            "https://api.cozy-asia.com/api/public/media/cwm_f61cae5822e0e1d18b2fe08b",
            "https://api.cozy-asia.com/api/public/media/cwm_a2320734ee2ddd68360d78b4",
            "https://api.cozy-asia.com/api/public/media/cwm_500565c5f9f448d8842acfc6",
        ],
        "hashtags": "#Самуи #АрендаВиллы #Ламай #CozyAsia #KohSamui #PoolVilla",
    },
    {
        "lot": "1244",
        "district": "На-Муанг",
        "title": "Villa Florida",
        "description": (
            "Villa Florida — полностью приватная и огороженная вилла площадью около 240 м² в тихом районе На-Муанг, "
            "примерно в 10 минутах от Ламая. Четыре кондиционируемые спальни-сьюта с собственными ванными, размещение "
            "до 8 гостей, большой частный бассейн, тропический сад, светлая гостиная с открытой кухней, затенённая терраса "
            "и охраняемая парковка. Разрешено проживание с питомцами. В стоимость входят финальная уборка, бельё и полотенца, "
            "быстрый интернет, обслуживание бассейна дважды в неделю и сада раз в месяц."
        ),
        "features": "🛏 4 спальни · 🛁 4 ванные · 🏊 частный бассейн · 🌿 тропический сад · 🐾 питомцы разрешены · 👥 до 8 гостей",
        "price": "199 781 THB/мес (≈ 5 876 USD)",
        "daily": "3 563 THB/сутки (≈ 105 USD)",
        "weekly": "60 339 THB/7 ночей (≈ 1 775 USD)",
        "deposit": "10 000 THB",
        "electricity": "7 THB/кВт⋅ч",
        "site": "https://cozy-asia.com/ru/properties/cw_6b5d8f1244a1",
        "photos": [
            "https://api.cozy-asia.com/api/public/media/cwm_1244_01",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_02",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_03",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_04",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_05",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_06",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_07",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_08",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_09",
            "https://api.cozy-asia.com/api/public/media/cwm_1244_10",
        ],
        "hashtags": "#Самуи #АрендаВиллы #НаМуанг #CozyAsia #KohSamui #PoolVilla",
    },
]


def enabled() -> bool:
    import os
    return os.getenv("PUBLISH_RENU_THREE_20261122", "0").strip().lower() in {"1", "true", "yes", "on"}


def caption_html(item: dict) -> str:
    lot = item["lot"]
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    deposit = f"\n🔐 Депозит: {item['deposit']}" if item.get("deposit") else ""
    electricity = f"\n⚡ Электричество: {item['electricity']}" if item.get("electricity") else ""
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>{item['title']} — {item['description']}</blockquote>

📍 Район: {item['district']}
🏠 Тип: вилла
{item['features']}

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: {item['price']}
💵 {item['daily']}
💵 {item['weekly']}{deposit}{electricity}
📅 Тарифы по календарю источника; доступность и точные даты подтверждаются по запросу
🌿 Сезонная скидка при месячном проживании рассчитывается индивидуально после запроса

📸 <a href="{item['site']}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

{item['hashtags']}"""


def final_caption(item: dict):
    from telethon.extensions import html
    text, entities = html.parse(caption_html(item))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, item["lot"])
    if not changed:
        raise RuntimeError(f"Premium conversion failed for lot {item['lot']}")
    publication_safety.validate_premium_caption(text, entities, item["lot"])
    channel_publication_policy.validate_listing_caption(text, entities, item["lot"], CHANNEL)
    if len(text) > 1024:
        raise RuntimeError(f"Caption too long for lot {item['lot']}: {len(text)}")
    return text, entities


def download_photos(item: dict, directory: str) -> list[str]:
    paths = []
    root = Path(directory) / item["lot"]
    root.mkdir(parents=True, exist_ok=True)
    for idx, url in enumerate(item["photos"], 1):
        target = root / f"{idx:02d}.jpg"
        response = requests.get(url, timeout=90, headers={"User-Agent": "CozyAsia/1.0"})
        response.raise_for_status()
        target.write_bytes(response.content)
        if target.stat().st_size < 10_000:
            raise RuntimeError(f"Photo {idx} for lot {item['lot']} is unexpectedly small")
        paths.append(str(target))
    if len(paths) != 10:
        raise RuntimeError(f"Expected 10 photos for lot {item['lot']}")
    return paths


async def run():
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("Telethon session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        previous = await publication_safety.latest_numeric_lot(client, channel, limit=120)
        if previous and int(previous) != 1241:
            raise RuntimeError(f"Expected last published lot 1241 before batch, found {previous}")
        results = []
        with tempfile.TemporaryDirectory(prefix="renu-three-") as directory:
            for item in LISTINGS:
                lot = item["lot"]
                recent = await client.get_messages(channel, limit=180)
                existing = next((m for m in recent if publication_safety.lot_from_message(m) == lot), None)
                if existing:
                    results.append({"lot": lot, "message_id": int(existing.id), "result": "already_published", "photos": 10})
                    continue
                live_previous = await publication_safety.latest_numeric_lot(client, channel, limit=180)
                if live_previous and int(live_previous) + 1 != int(lot):
                    raise RuntimeError(f"Lot sequence failed before {lot}: previous={live_previous}")
                text, entities = final_caption(item)
                photos = await asyncio.to_thread(download_photos, item, directory)
                sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)
                messages = sent if isinstance(sent, list) else [sent]
                caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
                verify = await client.get_messages(channel, ids=int(caption_msg.id))
                if publication_safety.lot_from_message(verify) != lot:
                    raise RuntimeError(f"Read-back lot mismatch for {lot}")
                publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
                for signature in (item["district"], item["price"].split(" THB")[0]):
                    if signature not in (verify.message or ""):
                        raise RuntimeError(f"Read-back signature missing for {lot}: {signature}")
                results.append({"lot": lot, "message_id": int(caption_msg.id), "result": "published", "photos": len(photos)})
        result = {"channel": CHANNEL, "batch": "RENU V1242-V1244", "results": results}
        log.info("PUBLISH_RENU_THREE_20261122_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("PUBLISH_RENU_THREE_20261122_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))


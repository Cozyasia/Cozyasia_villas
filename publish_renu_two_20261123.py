# -*- coding: utf-8 -*-
"""Publish RENU lots 1245 and 1246 to the small Cozy Asia channel.

The job is explicitly gated in Render, duplicate-safe, and records the
Telegram URL plus the available agency contact in the Lots sheet used by
VillaBot.  The public post never exposes owner/agency phone data.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-renu-two-20261123")
CHANNEL = "arenda_vill_samui"
AGENCY_CONTACT = "RENU Samui Properties (агентство; собственник не указан), +66 80 719 3760"
SOURCE_BASE = "https://cozy-asia.com/ru/properties/"

LISTINGS = [
    {
        "lot": "1245",
        "district": "На Муанг",
        "title": "Villa Roxy",
        "description": (
            "Villa Roxy — просторная вилла с приватным бассейном в спокойном районе На-Муанг, "
            "примерно в 11 минутах от пляжа и центра Ламая. До 8 гостей: спальня с ванной рядом "
            "с гостиной и кухней, две независимые спальни-сьюта и отдельные апартаменты со своей "
            "кухней, гостиной, спальней и ванной. Есть большая терраса с обеденной и лаунж-зонами, "
            "оборудованная кухня, быстрый Wi‑Fi, стиральная машина и частная парковка. Подъезд по "
            "ровной дороге; питомцы разрешены."
        ),
        "features": "🛏 4 спальни · 🛁 4 ванные · 🏊 приватный бассейн · 🌿 терраса · 🐾 питомцы разрешены · 👥 до 8 гостей",
        "price": "207 698 THB/мес (≈ 6 109 USD)",
        "daily": "3 214 THB/сутки (≈ 95 USD)",
        "weekly": "62 499 THB/7 ночей (≈ 1 838 USD)",
        "deposit": "10 000 THB",
        "electricity": "7 THB/кВт⋅ч",
        "website_id": "cw_7c6e9a1245b2",
        "gallery_prefix": "cwm_1245_",
        "hashtags": "#Самуи #АрендаВиллы #НаМуанг #CozyAsia #KohSamui #PoolVilla",
    },
    {
        "lot": "1246",
        "district": "Ламай",
        "title": "One Life One Dream",
        "description": (
            "One Life One Dream — современная одноуровневая вилла на сваях в тихих холмах Ламая "
            "с панорамным видом на джунгли, горы и море. Три кондиционируемые спальни, две ванные "
            "комнаты, размещение до 6 гостей, приватный infinity-бассейн, светлая гостиная с "
            "панорамными окнами, большая терраса с лаунж- и обеденной зонами, кухня, Smart TV и "
            "оптоволоконный Wi‑Fi 500 Мбит/с. Доступ только по лестнице; объект не подходит маленьким "
            "детям и гостям с ограниченной мобильностью. Рядом ведётся строительство, поэтому цена снижена "
            "с учётом возможного шума."
        ),
        "features": "🛏 3 спальни · 🛁 2 ванные · 🏊 приватный infinity-бассейн · 🌊 панорамный вид · 👥 до 6 гостей",
        "price": "272 455 THB/мес (≈ 8 013 USD)",
        "daily": "3 788 THB/сутки (≈ 111 USD)",
        "weekly": "79 080 THB/7 ночей (≈ 2 326 USD)",
        "electricity": "7 THB/кВт⋅ч",
        "website_id": "cw_8d7fab1246c3",
        "gallery_prefix": "cwm_1246_",
        "hashtags": "#Самуи #АрендаВиллы #Ламай #CozyAsia #KohSamui #PoolVilla",
    },
]


def enabled() -> bool:
    return os.getenv("PUBLISH_RENU_TWO_20261123", "0").strip().lower() in {"1", "true", "yes", "on"}


def website_url(item: dict) -> str:
    return SOURCE_BASE + item["website_id"]


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
{item['features']}

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: {item['price']}
💵 {item['daily']}
💵 {item['weekly']}{deposit}{electricity}
📅 Доступность и точные даты — по запросу
🌿 Сезонная скидка при месячном проживании рассчитывается индивидуально после запроса

📸 <a href="{website_url(item)}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>

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
    root = Path(directory) / item["lot"]
    root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for idx in range(1, 11):
        media_id = f"{item['gallery_prefix']}{idx:02d}"
        url = f"https://api.cozy-asia.com/api/public/media/{media_id}"
        target = root / f"{idx:02d}.jpg"
        response = requests.get(url, timeout=90, headers={"User-Agent": "CozyAsia/1.0"})
        response.raise_for_status()
        target.write_bytes(response.content)
        if target.stat().st_size < 10_000:
            raise RuntimeError(f"Photo {idx} for lot {item['lot']} is unexpectedly small")
        paths.append(str(target))
    if len(paths) != 10:
        raise RuntimeError(f"Expected exactly 10 photos for lot {item['lot']}")
    return paths


def _upsert_lots_sheet(item: dict, message_id: int) -> None:
    """Persist the Telegram link and agency contact for VillaBot lookups."""
    ws = cozy_catalog.ensure_lots_sheet()
    values = ws.get_all_values()
    headers = list(values[0]) if values else list(cozy_catalog.HEADERS)
    for header in cozy_catalog.HEADERS:
        if header not in headers:
            headers.append(header)
    if not values:
        ws.append_row(headers, value_input_option="RAW")
        values = [headers]
    elif headers != list(values[0]):
        ws.update("A1", [headers], value_input_option="RAW")
        values[0] = headers

    telegram_url = f"https://t.me/{CHANNEL}/{message_id}"
    source = (
        f"Источник: {website_url(item)}\n"
        f"Галерея: {item['gallery_prefix']}01–{item['gallery_prefix']}10\n"
        f"Контакт: {AGENCY_CONTACT}"
    )
    record = {h: "" for h in headers}
    record.update({
        "lot_id": item["lot"],
        "telegram_message_id": str(message_id),
        "telegram_url": telegram_url,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "active",
        "тип": "вилла",
        "район": item["district"],
        "спальни": "4" if item["lot"] == "1245" else "3",
        "ванные": "4" if item["lot"] == "1245" else "2",
        "бассейн": "yes",
        "тип_бассейна": "infinity" if item["lot"] == "1246" else "private",
        "цена_месяц_thb": item["price"].split(" THB")[0].replace(" ", ""),
        "цена_сутки_thb": item["daily"].split(" THB")[0].replace(" ", ""),
        "депозит_thb": item.get("deposit", "").split(" THB")[0].replace(" ", ""),
        "доступность": "по календарю источника; подтверждается по запросу",
        "питомцы": "yes" if item["lot"] == "1245" else "",
        "электричество": item["electricity"],
        "контакт_собственника": AGENCY_CONTACT,
        "описание": item["description"],
        "исходный_текст": source,
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "confidence": "high",
        "needs_review": "yes",
    })
    row = [record.get(h, "") for h in headers]
    existing_row = None
    for row_number, old in enumerate(values[1:], start=2):
        padded = old + [""] * max(0, len(headers) - len(old))
        old_record = dict(zip(headers, padded))
        if old_record.get("lot_id", "").strip() == item["lot"]:
            existing_row = row_number
            break
    if existing_row:
        ws.update(f"A{existing_row}:{cozy_catalog._col(len(headers))}{existing_row}", [row], value_input_option="USER_ENTERED")
    else:
        ws.append_row(row, value_input_option="USER_ENTERED")


async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("Telethon session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        previous = await publication_safety.latest_numeric_lot(client, channel, limit=180)
        if previous and int(previous) != 1244:
            raise RuntimeError(f"Unexpected last published lot before batch: {previous}")
        results = []
        with tempfile.TemporaryDirectory(prefix="renu-two-") as directory:
            for item in LISTINGS:
                lot = item["lot"]
                recent = await client.get_messages(channel, limit=220)
                existing = next((m for m in recent if publication_safety.lot_from_message(m) == lot), None)
                if existing:
                    message_id = int(existing.id)
                    result = "already_published"
                else:
                    live_previous = await publication_safety.latest_numeric_lot(client, channel, limit=220)
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
                    message_id = int(caption_msg.id)
                    result = "published"
                await asyncio.to_thread(_upsert_lots_sheet, item, message_id)
                results.append({"lot": lot, "message_id": message_id, "result": result, "telegram_url": f"https://t.me/{CHANNEL}/{message_id}", "website_url": website_url(item), "photos": 10})
        payload = {"channel": CHANNEL, "batch": "RENU V1245-V1246", "results": results, "owner_contact_recorded": AGENCY_CONTACT}
        log.info("PUBLISH_RENU_TWO_20261123_DONE %s", json.dumps(payload, ensure_ascii=False))
        return payload
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("PUBLISH_RENU_TWO_20261123_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))


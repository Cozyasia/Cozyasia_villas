# -*- coding: utf-8 -*-
"""One-shot, idempotent publication of Facebook Marketplace item 1791905108663402."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-fb-1791905108663402")
SOURCE_ID = "facebook_marketplace_1791905108663402"
SOURCE_URL = "https://www.facebook.com/marketplace/item/1791905108663402/"
CHANNEL = "samuirental"
BOT_USERNAME = "Cozyasia_villa_bot"
DRIVE_FILE_ID = "1lkeiExqGyxI4j2Laz06qDg3c55BS8ebV"

PHOTO_SUFFIXES = (
    "cozy_asia_1791905108663402_02.jpg",
    "cozy_asia_1791905108663402_03.jpg",
    "cozy_asia_1791905108663402_04.jpg",
    "cozy_asia_1791905108663402_06.jpg",
    "cozy_asia_1791905108663402_07.jpg",
    "cozy_asia_1791905108663402_10.jpg",
    "cozy_asia_1791905108663402_14.jpg",
    "cozy_asia_1791905108663402_18.jpg",
    "cozy_asia_1791905108663402_13.jpg",
    "cozy_asia_1791905108663402_23.jpg",
)

def _caption_html(lot: str) -> str:
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Просторная полностью меблированная вилла с приватным бассейном в районе Plai Laem Soi 8. Три спальни, три полноценные ванные комнаты и гостевой санузел, большая гостиная, оборудованная кухня, терраса, сад и крытая приватная парковка. Удобное расположение рядом с Big Buddha, храмом Plai Laem, Fisherman’s Village, магазинами, ресторанами и пляжами Choeng Mon и Thong Son.</blockquote>

📍 Район: Plai Laem, Soi 8
🗺 <a href="https://maps.google.com/?q=Plai+Laem+Soi+8+Koh+Samui"><b>РАЙОН НА КАРТЕ</b></a>
🏠 Тип: вилла
🛏 Спальни: 3
🛁 Ванные: 3,5
🏊 Бассейн: приватный, размер указан владельцем как 8 × 2,5
🚗 Парковка: крытая, приватная
🐾 Питомцы: нельзя

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 95 000 THB/мес
🔐 Депозит: уточняется
🤝 Комиссия: 5 000 THB
📅 Доступность: уточняется
⚡ Электричество: государственный тариф
💧 Вода: включена
📶 3BB Fiber: включён
🧹 Уборка дома: 1 раз/нед
🏊 Обслуживание бассейна: 2 раза/нед
🌿 Сад: 1 раз/нед
🗑 Вывоз мусора: 1 раз/нед

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>НАПИСАТЬ БОТУ</b></a> 👈

🔎 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #PlaiLaem #ВиллаСамуи #PoolVilla #KohSamuiRental #CozyAsia"""

def _final_caption(lot: str):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities

def _download_photos(directory: str) -> list[str]:
    raw = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    creds.refresh(GoogleAuthRequest())
    url = f"https://www.googleapis.com/drive/v3/files/{DRIVE_FILE_ID}?alt=media"
    response = requests.get(url, headers={"Authorization": f"Bearer {creds.token}"}, timeout=90)
    response.raise_for_status()

    zip_path = Path(directory) / "facebook_1791905108663402.zip"
    zip_path.write_bytes(response.content)
    if zip_path.stat().st_size < 100_000:
        raise RuntimeError("Publication archive is unexpectedly small")

    photo_dir = Path(directory) / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        for suffix in PHOTO_SUFFIXES:
            matches = [n for n in names if n.endswith("/photos/" + suffix) or n.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f"Expected one archive member for {suffix}, found {len(matches)}")
            target = photo_dir / suffix
            target.write_bytes(archive.read(matches[0]))
            if target.stat().st_size < 10_000:
                raise RuntimeError(f"Photo is unexpectedly small: {suffix}")
            paths.append(str(target))
    return paths

async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)

        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("Plai Laem, Soi 8", "95 000", "3,5", "8 × 2,5"), limit=300
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {"channel": CHANNEL, "lot": lot, "message_id": int(duplicate.id),
                      "result": "already", "source": SOURCE_ID}
            log.info("PUBLISH_FB_1791905108663402_DONE %s", json.dumps(result, ensure_ascii=False))
            return {"enabled": True, "result": result}

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine previous live lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)

        text, entities = _final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-1791905108663402-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory)
            sent = await client.send_file(
                channel, photos, caption=text, formatting_entities=entities, link_preview=False
            )

        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        live = verify.message or ""
        for signature in ("Plai Laem", "95 000", "5 000", "3,5"):
            if signature not in live:
                raise RuntimeError(f"Read-back listing signature missing: {signature}")

        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id),
                  "result": "published", "photos": len(PHOTO_SUFFIXES), "source": SOURCE_ID}
        log.info("PUBLISH_FB_1791905108663402_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

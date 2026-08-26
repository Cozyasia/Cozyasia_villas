# -*- coding: utf-8 -*-
"""One-shot publisher for the Maenam Soi 5 villa.

Enabled only when PUBLISH_LOT_1180=1. The first run accidentally used lot 1180
in the small channel, but 1180 already belongs to a different Bang Po property
in the large channel. This corrected pass changes the small-channel caption to
1181 and publishes the same 10-photo listing to the large channel as 1181.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import cozy_catalog
import mtproto_user_client

log = logging.getLogger("publish-lot-1180")

LOT_ID = "1181"
BOT_USERNAME = "Cozyasia_villa_bot"
SMALL_CHANNEL = "arenda_vill_samui"
LARGE_CHANNEL = "samuirental"
SMALL_EXISTING_MESSAGE_ID = 881
DRIVE_FILES = (
    ("1QunqW44gZTeUi4L8env6G5wthmJQGG_U", "01.jpg"),
    ("1NL5fZqsV3R93Fw0Q6HMlhDHD9tJEK4_I", "02.jpg"),
    ("1ATTj59xqhHq9HY1-TS9-g1MPde9Mk7Z8", "03.jpg"),
    ("1zhhv2y-8OiCSza5a5D1AyXOYe9h4Y8Pc", "04.jpg"),
    ("1ujI99noTRp8nGB4JlcQI7xNiR2jrxpwo", "05.jpg"),
    ("1sQHClavBU0NOxjHVR71xbLOmDXdc7xr-", "06.jpg"),
    ("15no7kturwOabwlBSL5qlSnminxB3SlSn", "07.jpg"),
    ("1PjsDRsPMd9w59W8TLe2h1Xr-u3ISkQbJ", "08.jpg"),
    ("1SGmRP9o0y8pAeenjVh3DnhqfHXW-vynw", "09.jpg"),
    ("14F2_mP9q0Z78IicjZdmCkIsnKDa67Ts1", "10.jpg"),
)

CAPTION_HTML = f"""🏡 <b>ЛОТ №{LOT_ID}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Полностью меблированная вилла с 2 спальнями и приватным бассейном в тихом районе Маенам, Soi 5. Современная кухня, Smart TV, Wi‑Fi и частная парковка.</blockquote>

📍 Район: Маенам, Soi 5
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 2
🏊 Бассейн: Да, приватный
🐾 Питомцы: Нет

💰 <b>Условия аренды</b>
💵 Цена: 60 000 THB/мес
🔐 Депозит: 50 000 THB
🤝 Комиссия: 5 000 THB
📅 Доступность: до 14 ноября 2026
⚡ Электричество: государственный тариф
💧 Вода: 800 THB/мес
🌊 Пляж Маенам: около 7 минут на авто

✨ Дополнительно: участок 152 м² · 3 кондиционера · холодильник · микроволновка · стиральная машина · уборка 1 раз/мес · бассейн 2 раза/нед · CCTV · 7-Eleven 5 мин · пирс Маенам 13 мин · Fisherman’s Village 15 мин

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{LOT_ID}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Maenam #PoolVilla #KohSamuiRental #CozyAsia"""


def enabled() -> bool:
    return os.getenv("PUBLISH_LOT_1180", "0").strip().lower() in {"1", "true", "yes", "on"}


def _download_images(temp_dir: str) -> list[str]:
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON missing")
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    session = AuthorizedSession(creds)
    paths = []
    root = Path(temp_dir)
    for file_id, name in DRIVE_FILES:
        response = session.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media", timeout=45
        )
        response.raise_for_status()
        path = root / name
        path.write_bytes(response.content)
        if path.stat().st_size < 10_000:
            raise RuntimeError(f"Downloaded image too small: {file_id}")
        paths.append(str(path))
    return paths


def _caption_with_entities():
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(CAPTION_HTML)
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, LOT_ID)
    if not changed:
        raise RuntimeError("Premium caption upgrade did not match expected V7 layout")
    return text, entities


async def _find_exact_existing(client, entity):
    async for msg in client.iter_messages(entity, limit=100):
        text = getattr(msg, "message", None) or ""
        if (
            text
            and cozy_catalog.extract_lot_id(text) == LOT_ID
            and "Маенам" in text
            and "60 000" in text
            and "14 ноября 2026" in text
        ):
            return msg
    return None


async def run() -> dict:
    if not enabled():
        return {"enabled": False}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results = {}
    try:
        text, entities = _caption_with_entities()

        # Correct the already-posted 10-photo small-channel album in place.
        small = await client.get_entity(SMALL_CHANNEL)
        small_msg = await client.get_messages(small, ids=SMALL_EXISTING_MESSAGE_ID)
        if not small_msg or not getattr(small_msg, "message", None):
            raise RuntimeError("Small-channel lot album caption message 881 is missing")
        if (
            cozy_catalog.extract_lot_id(small_msg.message) == LOT_ID
            and "Маенам" in small_msg.message
            and "60 000" in small_msg.message
        ):
            results[SMALL_CHANNEL] = {"result": "already", "caption_message_id": SMALL_EXISTING_MESSAGE_ID}
        else:
            await client.edit_message(
                small,
                SMALL_EXISTING_MESSAGE_ID,
                text,
                formatting_entities=entities,
                link_preview=False,
            )
            results[SMALL_CHANNEL] = {"result": "corrected", "caption_message_id": SMALL_EXISTING_MESSAGE_ID}
            log.info("Lot %s corrected @%s message_id=%s", LOT_ID, SMALL_CHANNEL, SMALL_EXISTING_MESSAGE_ID)

        # Publish the same 10-photo album to the large channel unless the exact
        # Maenam listing is already there.
        large = await client.get_entity(LARGE_CHANNEL)
        existing = await _find_exact_existing(client, large)
        if existing:
            results[LARGE_CHANNEL] = {"result": "already", "caption_message_id": int(existing.id)}
            log.info("Lot %s exact listing already exists @%s message_id=%s", LOT_ID, LARGE_CHANNEL, existing.id)
        else:
            with tempfile.TemporaryDirectory(prefix="cozy-lot-1181-") as temp_dir:
                images = await asyncio.to_thread(_download_images, temp_dir)
                sent = await client.send_file(
                    large,
                    images,
                    caption=text,
                    formatting_entities=entities,
                )
            messages = sent if isinstance(sent, (list, tuple)) else [sent]
            caption_msg = next((m for m in messages if (getattr(m, "message", None) or "").strip()), messages[0])
            ids = [int(m.id) for m in messages]
            results[LARGE_CHANNEL] = {
                "result": "posted",
                "caption_message_id": int(caption_msg.id),
                "media_message_ids": ids,
            }
            log.info("Lot %s posted @%s caption_message_id=%s media_ids=%s", LOT_ID, LARGE_CHANNEL, caption_msg.id, ids)

        log.info("Lot %s corrected publish complete: %s", LOT_ID, results)
        return results
    finally:
        await client.disconnect()

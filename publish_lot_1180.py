# -*- coding: utf-8 -*-
"""One-shot publisher for Cozy Asia lot 1180.

Enabled only when PUBLISH_LOT_1180=1. Uses the already-authorized Premium
MTProto account, downloads the 10 user-provided photos from Drive through the
service account, and posts the same album to both Cozy Asia channels.
Idempotent: before posting it searches recent channel history for lot 1180.
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

LOT_ID = "1180"
BOT_USERNAME = "Cozyasia_villa_bot"
CHANNELS = ("arenda_vill_samui", "samuirental")
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
        json.loads(raw),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    session = AuthorizedSession(creds)
    paths = []
    root = Path(temp_dir)
    for file_id, name in DRIVE_FILES:
        response = session.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
            timeout=45,
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


async def _find_existing(client, entity):
    async for msg in client.iter_messages(entity, limit=80):
        text = getattr(msg, "message", None) or ""
        if text and cozy_catalog.extract_lot_id(text) == LOT_ID:
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
        with tempfile.TemporaryDirectory(prefix="cozy-lot-1180-") as temp_dir:
            images = await asyncio.to_thread(_download_images, temp_dir)
            for channel_name in CHANNELS:
                entity = await client.get_entity(channel_name)
                existing = await _find_existing(client, entity)
                if existing:
                    results[channel_name] = {
                        "result": "already",
                        "caption_message_id": int(existing.id),
                    }
                    log.info("Lot %s already exists @%s message_id=%s", LOT_ID, channel_name, existing.id)
                    continue
                sent = await client.send_file(
                    entity,
                    images,
                    caption=text,
                    formatting_entities=entities,
                )
                messages = sent if isinstance(sent, (list, tuple)) else [sent]
                caption_msg = next((m for m in messages if (getattr(m, "message", None) or "").strip()), messages[0])
                ids = [int(m.id) for m in messages]
                results[channel_name] = {
                    "result": "posted",
                    "caption_message_id": int(caption_msg.id),
                    "media_message_ids": ids,
                }
                log.info(
                    "Lot %s posted @%s caption_message_id=%s media_ids=%s",
                    LOT_ID, channel_name, caption_msg.id, ids,
                )
                await asyncio.sleep(2)
        log.info("Lot %s publish complete: %s", LOT_ID, results)
        return results
    finally:
        await client.disconnect()

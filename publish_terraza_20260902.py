# -*- coding: utf-8 -*-
"""One-shot, idempotent publication of The Terraza Samui studio to @samuirental."""
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

log = logging.getLogger("publish-terraza-20260902")
CHANNEL = "samuirental"
BOT_USERNAME = "Cozyasia_villa_bot"
DRIVE_FILE_ID = "1fNLuzonZcnNjNjH_DlS7Sim6lDmWqvOR"
PHOTO_NAMES = [f"{i:02d}.jpg" for i in range(1, 11)]


def enabled() -> bool:
    return os.getenv("PUBLISH_TERRAZA_20260902", "0").strip().lower() in {"1", "true", "yes", "on"}


def _caption_html(lot: str) -> str:
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Уютная студия в современном кондоминиуме The Terraza Samui в самом центре Ламая. Пляж, рестораны, кафе, магазины и центр Lamai — в пешей доступности, поэтому можно комфортно жить без байка или автомобиля.</blockquote>

📍 Район: Ламай, центр
📍 <a href="https://maps.app.goo.gl/ySSu6m4n4Nq46aef9?g_st=ac">Локация на карте</a>
🏠 Тип: студия / кондоминиум
🛁 Ванная: 1
🌿 Балкон: Да
📶 Wi-Fi: Да
💻 Рабочее место: Да
🚗 Парковка: Да
🏊 Общий бассейн · сауна · фитнес-зал · бильярдная
🍳 Оборудованная мини-кухня · стиральная машина

💰 <b>Условия аренды</b>
💵 Цена: 35 000 THB/мес
📅 Контракт 12 месяцев: 30 000 THB/мес
🔐 Депозит: уточняется
🤝 Комиссия Cozy Asia: 5 000 THB
⚡ Электричество: 7 THB/unit
💧 Вода: 500 THB
🎥 Видео объекта — по запросу

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Ламай #Lamai #СтудияСамуи #КондоСамуи #CozyAsia"""


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
        info,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    creds.refresh(GoogleAuthRequest())
    url = f"https://www.googleapis.com/drive/v3/files/{DRIVE_FILE_ID}?alt=media"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=60,
    )
    response.raise_for_status()
    zip_path = Path(directory) / "terraza.zip"
    zip_path.write_bytes(response.content)
    if zip_path.stat().st_size < 100_000:
        raise RuntimeError("Terraza photo archive is unexpectedly small")

    photo_dir = Path(directory) / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        for name in PHOTO_NAMES:
            if name not in names:
                raise RuntimeError(f"Missing photo in Terraza archive: {name}")
            path = photo_dir / name
            path.write_bytes(archive.read(name))
            if path.stat().st_size < 10_000:
                raise RuntimeError(f"Terraza photo is unexpectedly small: {name}")
            paths.append(str(path))
    return paths


async def run() -> dict:
    if not enabled():
        return {"enabled": False}

    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client,
            channel,
            ("The Terraza Samui", "35 000 THB", "30 000 THB"),
            limit=260,
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {
                "channel": CHANNEL,
                "lot": lot,
                "message_id": int(duplicate.id),
                "result": "already",
            }
            log.info("PUBLISH_TERRAZA_20260902_DONE %s", json.dumps(result, ensure_ascii=False))
            return {"enabled": True, "result": result}

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=260)
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)
        text, entities = _final_caption(lot)

        with tempfile.TemporaryDirectory(prefix="terraza-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory)
            sent = await client.send_file(
                channel,
                photos,
                caption=text,
                formatting_entities=entities,
            )

        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Terraza read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        if "The Terraza Samui" not in (verify.message or ""):
            raise RuntimeError("Terraza read-back listing signature mismatch")

        result = {
            "channel": CHANNEL,
            "lot": lot,
            "message_id": int(caption_msg.id),
            "result": "published",
        }
        log.info("PUBLISH_TERRAZA_20260902_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

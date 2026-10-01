# -*- coding: utf-8 -*-
"""One-shot publication of Cozy Asia Choeng Mon house lot 1205."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

CHANNEL = "samuirental"
LOT_ID = 1205
EXPECTED_LOT = str(LOT_ID)
PRICE_ONE_MONTH = 49000
PRICE_LONG_TERM = 45000
COMMISSION = 4000
MAP_URL = "https://maps.app.goo.gl/fezbG6VJb8orKtAK7?g_st=ic"
PHOTO_ZIP_FILE_ID = "1Jp51jK09EHA6gEH-eVX5B_1qpZjFXj-e"
PHOTO_NAMES = [
    "01_exterior.jpg",
    "02_living.jpg",
    "03_dining.jpg",
    "04_bedroom_blue.jpg",
    "05_bedroom_grey.jpg",
    "06_kitchen.jpg",
    "07_office.jpg",
    "08_bathroom.jpg",
    "09_thai_kitchen.jpg",
    "10_carport.jpg",
]


def _caption_html(lot: str) -> str:
    rent_url = f"https://t.me/cozy_asia_bot?start=rent_{lot}"
    search_url = "https://t.me/cozy_asia_bot?start=search"
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Уютный полностью меблированный дом с 2 спальнями в Choeng Mon. Просторная гостиная, европейская кухня и отдельная тайская кухня, отдельный кабинет для работы, зона отдыха на свежем воздухе и парковка на 2 автомобиля. В доме есть стиральная и посудомоечная машины.</blockquote>

📍 Район: Choeng Mon, Koh Samui
🏠 Тип: дом
🛏 Спальни: 2
🛁 Ванные: 1
💻 Отдельный кабинет
🚗 Парковка: 2 автомобиля
🌿 Зона отдыха на улице

💰 <b>Условия аренды</b>
💵 49 000 THB/мес — аренда на 1 месяц
💵 45 000 THB/мес — аренда на 3–6 месяцев
🔐 Депозит: 1 месяц аренды
🤝 Комиссия Cozy Asia: 4 000 THB
⚡ Электричество: государственный тариф
💧 Вода: бесплатно
📶 Интернет: 950 THB/мес
📅 Доступность: по запросу
🐾 Питомцы: уточняется

📍 <a href="{MAP_URL}"><b>Геолокация</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ChoengMon #ДомСамуи #KohSamuiRental #CozyAsia"""


CAPTION = _caption_html(EXPECTED_LOT)


def enabled() -> bool:
    return os.getenv("PUBLISH_CHOENGMON_1205", "0").strip().lower() in {"1", "true", "yes", "on"}


def _drive_session():
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    creds = Credentials.from_service_account_info(
        json.loads(raw),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return AuthorizedSession(creds)


def _materialize_package() -> list[Path]:
    work = Path("/tmp/cozy_choengmon_1205")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    package = work / "package"
    package.mkdir()

    session = _drive_session()
    response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{PHOTO_ZIP_FILE_ID}",
        params={"alt": "media", "supportsAllDrives": "true"},
        timeout=120,
    )
    response.raise_for_status()
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(package)

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    listed = list(manifest.get("photos") or [])
    if listed != PHOTO_NAMES:
        raise RuntimeError(f"Unexpected photo manifest: {listed}")
    photos = [package / "photos" / name for name in PHOTO_NAMES]
    missing = [str(path) for path in photos if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing publication assets: {missing}")
    return photos


def _final_caption(lot: str):
    import mtproto_user_client
    import publication_safety
    import channel_publication_policy
    from telethon.extensions import html as telethon_html

    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    channel_publication_policy.validate_listing_caption(text, entities, lot, CHANNEL)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities


async def run() -> dict:
    if not enabled():
        return {"enabled": False}

    import cozy_catalog
    import mtproto_user_client
    import publication_safety
    import channel_publication_policy

    photos = await asyncio.to_thread(_materialize_package)
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client,
            channel,
            ("Choeng Mon", "49 000", "950 THB/мес", "2 спальнями"),
            limit=300,
        )
        if duplicate:
            existing_lot = publication_safety.lot_from_message(duplicate)
            result = {
                "enabled": True,
                "result": "already",
                "lot": existing_lot,
                "message_id": int(duplicate.id),
                "telegram_url": f"https://t.me/{CHANNEL}/{int(duplicate.id)}",
            }
            logging.getLogger("publish-choengmon-1205").info(
                "PUBLISH_CHOENGMON_1205_DONE %s", json.dumps(result, ensure_ascii=False)
            )
            return result

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine latest big-channel lot")
        next_lot = str(int(previous) + 1)
        if next_lot != EXPECTED_LOT:
            raise RuntimeError(f"Expected next lot {EXPECTED_LOT}, but Telegram says next is {next_lot}")
        await publication_safety.assert_next_lot(client, channel, EXPECTED_LOT)

        text, entities = _final_caption(EXPECTED_LOT)
        sent = await client.send_file(
            channel,
            [str(path) for path in photos],
            caption=text,
            formatting_entities=entities,
        )
        messages = sent if isinstance(sent, list) else [sent]
        if len(messages) != 10:
            raise RuntimeError(f"Expected 10 Telegram album messages, got {len(messages)}")
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])

        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != EXPECTED_LOT:
            raise RuntimeError("Read-back lot mismatch")
        channel_publication_policy.validate_listing_caption(
            verify.message or "", verify.entities or [], EXPECTED_LOT, CHANNEL
        )

        result = {
            "enabled": True,
            "result": "published",
            "lot": EXPECTED_LOT,
            "message_id": int(caption_msg.id),
            "telegram_url": f"https://t.me/{CHANNEL}/{int(caption_msg.id)}",
            "telegram_photo_count": len(messages),
        }
        logging.getLogger("publish-choengmon-1205").info(
            "PUBLISH_CHOENGMON_1205_DONE %s", json.dumps(result, ensure_ascii=False)
        )
        return result
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    result = asyncio.run(run())
    print("PUBLISH_CHOENGMON_1205_RESULT=" + json.dumps(result, ensure_ascii=False))

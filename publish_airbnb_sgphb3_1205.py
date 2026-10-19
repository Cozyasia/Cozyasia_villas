# -*- coding: utf-8 -*-
"""One-shot publication of Airbnb sgphb3 villa lot 1205."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

CHANNEL = "arenda_vill_samui"
LOT_ID = 1205
EXPECTED_LOT = str(LOT_ID)
PHOTO_ZIP_FILE_ID = "1KjjD1SBKqBaeZSnHS-mHsjurOdMWaOgy"
PHOTO_NAMES = [
    "01_exterior.jpeg",
    "02_pool.jpeg",
    "03_living.jpeg",
    "04_bedroom.jpeg",
    "05_kitchen.jpeg",
]
MAP_URL = "https://www.google.com/maps/search/?api=1&query=Mae+Nam+Koh+Samui"
AIRBNB_URL = "https://airbnb.com/h/sgphb3"


def _caption_html(lot: str) -> str:
    rent_url = f"https://t.me/Cozyasia_villa_bot?start=rent_{lot}"
    search_url = "https://t.me/Cozyasia_villa_bot?start=search"
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Новая семейная вилла с 2 спальнями и приватным бассейном в спокойном районе Мэнам. Просторная гостиная, высокие потолки 4 метра, современная кухня и приватная территория. До пляжа Мэнам — около 5–10 минут на автомобиле.</blockquote>

📍 Район: Мэнам, Ко Самуи
🏠 Тип: отдельная вилла
🛏 Спальни: 2
🛁 Ванные комнаты: 2,5
👨‍👩‍👧‍👦 Размещение: до 4 гостей
🏊 Приватный бассейн
🏋️ Общий тренажёрный зал
❄️ Кондиционеры и потолочные вентиляторы
🍳 Полностью оборудованная кухня
📺 Телевизор
🧺 Стиральная и сушильная машины
📶 Wi‑Fi
🚗 Частная парковка
🌿 Тихий развивающийся район

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 155 000 THB/мес
🧹 Уборка: 4 000 THB/неделю
🧽 Финальная уборка: 2 000 THB
🔐 Депозит: 15 000 THB, возвратный
🤝 Комиссия Cozy Asia: 5 000 THB
⚡ Электричество: 6 THB/кВт
💧 Вода: 100 THB/единица
📅 Доступность: по запросу
🚫 Вечеринки запрещены
⚠️ Штраф за шум или размещение дополнительных гостей: 20 000 THB

📍 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

Оператор: @cozy_asia

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Мэнам #ВиллаСамуи #СнятьВиллуСамуи #CozyAsia"""


def enabled() -> bool:
    return os.getenv("PUBLISH_AIRBNB_SGPHB3_1205", "0").strip().lower() in {"1", "true", "yes", "on"}


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
    work = Path("/tmp/cozy_airbnb_sgphb3_1205")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    package = work / "package"
    package.mkdir()
    response = _drive_session().get(
        f"https://www.googleapis.com/drive/v3/files/{PHOTO_ZIP_FILE_ID}",
        params={"alt": "media", "supportsAllDrives": "true"},
        timeout=120,
    )
    response.raise_for_status()
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(package)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    if list(manifest.get("photos") or []) != PHOTO_NAMES:
        raise RuntimeError(f"Unexpected photo manifest: {manifest.get('photos')}")
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
        raise RuntimeError("Premium emoji conversion failed")
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
            client, channel, ("Мэнам", "155 000", "2 спальнями", "приватным бассейном"), limit=300
        )
        if duplicate:
            result = {
                "enabled": True,
                "result": "already",
                "lot": publication_safety.lot_from_message(duplicate),
                "message_id": int(duplicate.id),
                "telegram_url": f"https://t.me/{CHANNEL}/{int(duplicate.id)}",
            }
            logging.getLogger("publish-airbnb-sgphb3").info("PUBLISH_AIRBNB_SGPHB3_DONE %s", json.dumps(result, ensure_ascii=False))
            return result

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine latest small-channel lot")
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
        if len(messages) != len(PHOTO_NAMES):
            raise RuntimeError(f"Expected {len(PHOTO_NAMES)} Telegram album messages, got {len(messages)}")
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])

        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != EXPECTED_LOT:
            raise RuntimeError("Read-back lot mismatch")
        channel_publication_policy.validate_listing_caption(
            verify.message or "", verify.entities or [], EXPECTED_LOT, CHANNEL
        )
        custom_emoji_count = sum(1 for entity in (verify.entities or []) if entity.__class__.__name__ == "MessageEntityCustomEmoji")
        if custom_emoji_count < 10:
            raise RuntimeError(f"Premium emoji verification failed: only {custom_emoji_count} custom emojis")

        result = {
            "enabled": True,
            "result": "published",
            "lot": EXPECTED_LOT,
            "message_id": int(caption_msg.id),
            "telegram_url": f"https://t.me/{CHANNEL}/{int(caption_msg.id)}",
            "telegram_photo_count": len(messages),
            "custom_emoji_count": custom_emoji_count,
        }
        logging.getLogger("publish-airbnb-sgphb3").info("PUBLISH_AIRBNB_SGPHB3_DONE %s", json.dumps(result, ensure_ascii=False))
        return result
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("PUBLISH_AIRBNB_SGPHB3_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

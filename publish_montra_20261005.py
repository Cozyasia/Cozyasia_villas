# -*- coding: utf-8 -*-
"""One-shot publication of the Montra Resort villa to the small villa channel."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-montra-20261005")

CHANNEL = "arenda_vill_samui"
EXPECTED_LOT = "1215"
SOURCE_URL = "https://www.facebook.com/marketplace/item/4023955804572839/"
PHOTO_ZIP_FILE_ID = os.getenv("MONTRA_PHOTO_ZIP_FILE_ID", "").strip()
MAP_URL = "https://maps.app.goo.gl/8crsg27nVMKyrEuC7?g_st=ac"


def enabled() -> bool:
    return os.getenv("PUBLISH_MONTRA_20261005", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _drive_session():
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return AuthorizedSession(creds)


def _materialize_package() -> tuple[Path, dict]:
    if not PHOTO_ZIP_FILE_ID:
        raise RuntimeError("MONTRA_PHOTO_ZIP_FILE_ID is missing")
    work = Path("/tmp/cozy_montra_20261005")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    root = work / "package"
    root.mkdir()

    session = _drive_session()
    response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{PHOTO_ZIP_FILE_ID}?alt=media",
        timeout=180,
    )
    response.raise_for_status()
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive, "r") as zipped:
        zipped.extractall(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("manifest.json missing from photo package")
    return root, json.loads(manifest_path.read_text(encoding="utf-8"))


def _caption_html(lot: str) -> str:
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Вилла в Montra Resort у пляжа Ламай, стиль Nara. Мастер-спальня с кроватью 2 м; вторая — с кроватью 1,2 м и может использоваться как отдельная гостиная.</blockquote>

📍 Район: Ламай
🏠 Вилла в резорте
🛏 Спальни: 2
🛁 Ванные: 1
🏊 Большой общий бассейн 24/7
🏋️ Фитнес и чайный павильон
🍳 Мини-кухня: микроволновка, индукционная плита, посуда, мини-бар
🧺 Стиральная машина
🛁 Ванна, душ, двойная раковина, smart-туалет
❄️ 2 кондиционера, ТВ, сейф, балкон

💰 <b>Условия аренды</b>
• октябрь–ноябрь: 36 000 THB/мес.
• декабрь–март: 62 000 THB/мес.
• год, полная предоплата: 36 000 THB/мес.
• год, помесячно: 39 000 THB/мес.
🔐 Депозит: 58 000 THB — при годовой помесячной оплате
🤝 Комиссия Cozy Asia: 5 000 THB
⚡ Электричество: 6,5 THB/кВт·ч
💧 Вода: 300 THB/мес.
🧹 Уборка: 300 THB/сеанс
📅 Доступность: по запросу

📍 <a href="{MAP_URL}"><b>Геолокация</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

Оператор: @Cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Ламай #ВиллаСамуи #CozyAsia"""


def _final_caption(lot: str):
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
    root, manifest = _materialize_package()
    selected = [root / "photos" / Path(item).name for item in manifest.get("telegram_selected", [])]
    if len(selected) != 10:
        raise RuntimeError(f"Expected exactly 10 Telegram photos, got {len(selected)}")
    missing = [str(path) for path in selected if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing selected photos: {missing}")

    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("Montra Resort", "62 000", "Ламай"), limit=300
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {
                "enabled": True,
                "result": "already",
                "lot": lot,
                "message_id": int(duplicate.id),
                "telegram_url": f"https://t.me/{CHANNEL}/{int(duplicate.id)}",
            }
            log.info("PUBLISH_MONTRA_DONE %s", json.dumps(result, ensure_ascii=False))
            return result

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine latest villa-channel lot")
        lot = str(int(previous) + 1)
        if lot != EXPECTED_LOT:
            raise RuntimeError(f"Expected next lot {EXPECTED_LOT}, but Telegram says next is {lot}")
        await publication_safety.assert_next_lot(client, channel, lot)

        text, entities = _final_caption(lot)
        sent = await client.send_file(
            channel,
            [str(path) for path in selected],
            caption=text,
            formatting_entities=entities,
        )
        messages = sent if isinstance(sent, list) else [sent]
        if len(messages) != 10:
            raise RuntimeError(f"Expected 10 Telegram album messages, got {len(messages)}")
        caption_message = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_message.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        channel_publication_policy.validate_listing_caption(
            verify.message or "", verify.entities or [], lot, CHANNEL
        )
        result = {
            "enabled": True,
            "result": "published",
            "lot": lot,
            "message_id": int(caption_message.id),
            "telegram_url": f"https://t.me/{CHANNEL}/{int(caption_message.id)}",
            "telegram_photo_count": len(messages),
            "source_url": SOURCE_URL,
        }
        log.info("PUBLISH_MONTRA_DONE %s", json.dumps(result, ensure_ascii=False))
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
    print("PUBLISH_MONTRA_RESULT=" + json.dumps(result, ensure_ascii=False))

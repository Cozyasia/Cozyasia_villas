# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 1548741747291928."""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import shutil
import uuid
import zipfile
from pathlib import Path

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety


log = logging.getLogger("publish-fb-1548741747291928")

CHANNEL = "samuirental"
EXPECTED_LOT = "1206"
PRICE_MONTHLY = 65000
COMMISSION = 5000
SOURCE_URL = "https://www.facebook.com/marketplace/item/1548741747291928/"
MAP_URL = (
    "https://www.google.com/maps/search/?api=1&query="
    "International+School+of+Samui"
)

PHOTO_ZIP_FILE_ID = os.getenv("FB_1548741747291928_PHOTO_ZIP_FILE_ID", "").strip()
EXTRA_FOLDER_ID = os.getenv("FB_1548741747291928_EXTRA_FOLDER_ID", "").strip()
EXTRA_FOLDER_URL = os.getenv("FB_1548741747291928_EXTRA_FOLDER_URL", "").strip()

TELEGRAM_PHOTO_NAMES = [
    "22.jpg",
    "01.jpg",
    "02.jpg",
    "05.jpg",
    "04.jpg",
    "07.jpg",
    "09.jpg",
    "14.jpg",
    "20.jpg",
    "12.jpg",
]
ADDITIONAL_PHOTO_NAMES = [
    "03.jpg",
    "06.jpg",
    "08.jpg",
    "10.jpg",
    "11.jpg",
    "13.jpg",
    "15.jpg",
    "16.jpg",
    "17.jpg",
    "18.jpg",
    "19.jpg",
    "21.jpg",
]


def enabled() -> bool:
    return os.getenv("PUBLISH_FB_1548741747291928", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _drive_session(scope: str = "https://www.googleapis.com/auth/drive"):
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_info(json.loads(raw), scopes=[scope])
    return AuthorizedSession(credentials)


def _validate_manifest(manifest: dict) -> tuple[list[str], list[str]]:
    selected = list(manifest.get("telegram_selected") or [])
    if selected != TELEGRAM_PHOTO_NAMES:
        raise RuntimeError(f"Unexpected Telegram photo manifest: {selected}")
    overflow = list(manifest.get("additional_photos") or [])
    if overflow != ADDITIONAL_PHOTO_NAMES:
        raise RuntimeError(f"Unexpected additional photo manifest: {overflow}")
    if len(set(selected + overflow)) != 22:
        raise RuntimeError("Photo manifest must contain 22 unique files")
    return selected, overflow


def _materialize_package() -> tuple[Path, list[Path], list[Path]]:
    if not PHOTO_ZIP_FILE_ID:
        raise RuntimeError("FB_1548741747291928_PHOTO_ZIP_FILE_ID is missing")
    work = Path("/tmp/cozy_fb_1548741747291928")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    root = work / "package"
    root.mkdir()

    response = _drive_session("https://www.googleapis.com/auth/drive.readonly").get(
        f"https://www.googleapis.com/drive/v3/files/{PHOTO_ZIP_FILE_ID}",
        params={"alt": "media", "supportsAllDrives": "true"},
        timeout=180,
    )
    response.raise_for_status()
    archive.write_bytes(response.content)

    with zipfile.ZipFile(archive, "r") as zipped:
        members = {name for name in zipped.namelist() if not name.endswith("/")}
        expected = {"manifest.json"} | {
            f"photos/{name}" for name in TELEGRAM_PHOTO_NAMES + ADDITIONAL_PHOTO_NAMES
        }
        if members != expected:
            raise RuntimeError(f"Unexpected files in photo package: {sorted(members)}")
        zipped.extractall(root)

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("manifest.json missing from photo package")
    selected_names, overflow_names = _validate_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    selected = [root / "photos" / name for name in selected_names]
    overflow = [root / "photos" / name for name in overflow_names]
    missing = [str(path) for path in selected + overflow if not path.is_file()]
    if missing:
        raise RuntimeError(f"Missing publication assets: {missing}")
    return root, selected, overflow


def _multipart_upload(session, folder_id: str, name: str, data: bytes) -> str:
    boundary = "cozy-" + uuid.uuid4().hex
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    metadata = json.dumps(
        {"name": name, "parents": [folder_id]}, ensure_ascii=False
    ).encode("utf-8")
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + metadata
        + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = session.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        params={"uploadType": "multipart", "fields": "id,name", "supportsAllDrives": "true"},
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        data=body,
        timeout=120,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def _ensure_public_folder(session) -> str:
    if not EXTRA_FOLDER_ID:
        raise RuntimeError("FB_1548741747291928_EXTRA_FOLDER_ID is missing")
    response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{EXTRA_FOLDER_ID}",
        params={
            "fields": "id,name,webViewLink,permissions(id,type,role)",
            "supportsAllDrives": "true",
        },
        timeout=60,
    )
    response.raise_for_status()
    metadata = response.json()
    permissions = metadata.get("permissions") or []
    public = any(
        item.get("type") == "anyone" and item.get("role") == "reader"
        for item in permissions
    )
    if not public:
        permission = session.post(
            f"https://www.googleapis.com/drive/v3/files/{EXTRA_FOLDER_ID}/permissions",
            params={"sendNotificationEmail": "false", "supportsAllDrives": "true"},
            json={"type": "anyone", "role": "reader", "allowFileDiscovery": False},
            timeout=60,
        )
        permission.raise_for_status()
    return str(
        metadata.get("webViewLink")
        or EXTRA_FOLDER_URL
        or f"https://drive.google.com/drive/folders/{EXTRA_FOLDER_ID}"
    )


def _ensure_additional_photos(overflow: list[Path]) -> tuple[list[str], str]:
    session = _drive_session()
    folder_url = _ensure_public_folder(session)
    response = session.get(
        "https://www.googleapis.com/drive/v3/files",
        params={
            "q": f"'{EXTRA_FOLDER_ID}' in parents and trashed=false",
            "fields": "files(id,name)",
            "pageSize": 1000,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
        timeout=60,
    )
    response.raise_for_status()
    existing = {
        str(item.get("name") or ""): str(item.get("id") or "")
        for item in response.json().get("files", [])
    }
    uploaded = []
    for index, source in enumerate(overflow, start=1):
        destination = f"{index:02d}_{source.name}"
        if destination in existing:
            uploaded.append(existing[destination])
            continue
        uploaded.append(
            _multipart_upload(session, EXTRA_FOLDER_ID, destination, source.read_bytes())
        )
    return uploaded, folder_url


def _caption_html(lot: str, extra_folder_url: str | None = None) -> str:
    folder_url = str(extra_folder_url or EXTRA_FOLDER_URL).strip()
    if not folder_url:
        raise RuntimeError("FB_1548741747291928_EXTRA_FOLDER_URL is missing")
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современный двухэтажный дом в комплексе The Ville напротив International School of Samui (ISS). Удобный вариант для семьи: три спальни, оборудованная западная кухня, просторные общие зоны и общий бассейн.</blockquote>

📍 Район: Бопхут, напротив ISS
🏠 Дом
🛏 Спальни: 3
🛁 Ванные: 3 + ванна
🍳 Западная кухня
🍽 Посудомоечная машина
🍷 Барная стойка и винный холодильник
🧺 Стиральная машина
🚗 Крытая парковка на 2 авто
🏊 Общий бассейн
🛡 Охрана 24/7

💰 <b>Условия аренды</b>
💵 65 000 THB/мес.
📆 Контракт: 1 год
🤝 Комиссия Cozy Asia: 5 000 THB
🔐 Депозит: уточняется
⚡ Электричество: государственный тариф
💧 Вода: 60 THB/м³
📶 Wi‑Fi: включён
🏘 Обслуживание комплекса: включено
📅 Доступность: по запросу
🐾 Питомцы: уточняется

🛒 3 мин. до Big C · 4 мин. до Lotus
🏙 7 мин. до Central Samui · 11 мин. до аэропорта

📍 <a href="{MAP_URL}"><b>Геолокация</b></a>
📸 <a href="{folder_url}"><b>Дополнительные фото</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Бопхут #ДомСамуи #ISS #CozyAsia"""


def _final_caption(lot: str, extra_folder_url: str | None = None):
    from telethon.extensions import html as telethon_html

    text, entities = telethon_html.parse(_caption_html(lot, extra_folder_url))
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

    _root, selected, overflow = await asyncio.to_thread(_materialize_package)
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client,
            channel,
            ("The Ville", "65 000", "Посудомоечная машина"),
            limit=300,
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
            log.info("PUBLISH_FB_1548741747291928_DONE %s", json.dumps(result))
            return result

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine latest big-channel lot")
        next_lot = str(int(previous) + 1)
        if next_lot != EXPECTED_LOT:
            raise RuntimeError(
                f"Expected next lot {EXPECTED_LOT}, but Telegram says next is {next_lot}"
            )
        await publication_safety.assert_next_lot(client, channel, EXPECTED_LOT)

        uploaded_ids, folder_url = await asyncio.to_thread(
            _ensure_additional_photos, overflow
        )
        if len(uploaded_ids) != len(ADDITIONAL_PHOTO_NAMES):
            raise RuntimeError("Not all additional photos were uploaded to Drive")

        text, entities = _final_caption(EXPECTED_LOT, folder_url)
        sent = await client.send_file(
            channel,
            [str(path) for path in selected],
            caption=text,
            formatting_entities=entities,
            link_preview=False,
        )
        messages = sent if isinstance(sent, list) else [sent]
        if len(messages) != 10:
            raise RuntimeError(f"Expected 10 Telegram album messages, got {len(messages)}")
        caption_message = next(
            (message for message in messages if getattr(message, "message", None)),
            messages[0],
        )
        verify = await client.get_messages(channel, ids=int(caption_message.id))
        if publication_safety.lot_from_message(verify) != EXPECTED_LOT:
            raise RuntimeError("Read-back lot mismatch")
        channel_publication_policy.validate_listing_caption(
            verify.message or "", verify.entities or [], EXPECTED_LOT, CHANNEL
        )

        result = {
            "enabled": True,
            "result": "published",
            "lot": EXPECTED_LOT,
            "message_id": int(caption_message.id),
            "telegram_url": f"https://t.me/{CHANNEL}/{int(caption_message.id)}",
            "telegram_photo_count": len(messages),
            "drive_additional_count": len(uploaded_ids),
            "drive_folder_url": folder_url,
            "source_url": SOURCE_URL,
        }
        log.info(
            "PUBLISH_FB_1548741747291928_DONE %s",
            json.dumps(result, ensure_ascii=False),
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
    print("PUBLISH_FB_1548741747291928_RESULT=" + json.dumps(result, ensure_ascii=False))

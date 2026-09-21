# -*- coding: utf-8 -*-
"""One-shot publication of Villa Santi to the Cozy Asia villa channel.

The media package is supplied through Google Drive. Exactly 10 selected photos
are sent to Telegram; the remaining photos are uploaded into the public Drive
folder and linked from the caption.
"""
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

import cozy_catalog
import mtproto_user_client
import publication_safety
import channel_publication_policy

log = logging.getLogger("publish-villa-santi-20260921")

CHANNEL = "arenda_vill_samui"
EXPECTED_LOT = "1213"
SOURCE_URL = "https://www.airbnb.com/rooms/1772125910622611517"
PHOTO_ZIP_FILE_ID = os.getenv("VILLA_SANTI_PHOTO_ZIP_FILE_ID", "").strip()
EXTRA_FOLDER_ID = os.getenv("VILLA_SANTI_EXTRA_FOLDER_ID", "").strip()
EXTRA_FOLDER_URL = "https://drive.google.com/drive/folders/1NmayrOgSBPyzZqACgEe8lSLMmFKjoUo6"
MAP_URL = "https://www.google.com/maps/search/?api=1&query=38%2F24+Plai+Laem%2C+Koh+Samui%2C+Surat+Thani+84330%2C+Thailand"
OWNER_CONTACT = "+66943968704"


def enabled() -> bool:
    return os.getenv("PUBLISH_VILLA_SANTI_20260921", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _drive_session(scope: str = "https://www.googleapis.com/auth/drive"):
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    creds = Credentials.from_service_account_info(json.loads(raw), scopes=[scope])
    return AuthorizedSession(creds)


def _materialize_package() -> tuple[Path, dict]:
    if not PHOTO_ZIP_FILE_ID:
        raise RuntimeError("VILLA_SANTI_PHOTO_ZIP_FILE_ID is missing")
    work = Path("/tmp/cozy_villa_santi_20260921")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    root = work / "package"
    root.mkdir()

    session = _drive_session("https://www.googleapis.com/auth/drive.readonly")
    r = session.get(
        f"https://www.googleapis.com/drive/v3/files/{PHOTO_ZIP_FILE_ID}?alt=media",
        timeout=180,
    )
    r.raise_for_status()
    archive.write_bytes(r.content)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("manifest.json missing from photo package")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return root, manifest


def _multipart_upload(session, folder_id: str, name: str, data: bytes) -> str:
    boundary = "cozy-" + uuid.uuid4().hex
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    metadata = json.dumps({"name": name, "parents": [folder_id]}, ensure_ascii=False).encode("utf-8")
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode("utf-8")
        + metadata
        + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8")
        + data
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )
    r = session.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        params={"uploadType": "multipart", "fields": "id,name"},
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        data=body,
        timeout=120,
    )
    r.raise_for_status()
    return str(r.json()["id"])


def _ensure_additional_photos(root: Path, manifest: dict) -> list[str]:
    if not EXTRA_FOLDER_ID:
        raise RuntimeError("VILLA_SANTI_EXTRA_FOLDER_ID is missing")
    session = _drive_session()
    q = f"'{EXTRA_FOLDER_ID}' in parents and trashed=false"
    r = session.get(
        "https://www.googleapis.com/drive/v3/files",
        params={"q": q, "fields": "files(id,name)", "pageSize": 1000},
        timeout=60,
    )
    r.raise_for_status()
    existing = {str(x.get("name") or ""): str(x.get("id") or "") for x in r.json().get("files", [])}
    uploaded = []
    for idx, rel in enumerate(manifest.get("additional_photos") or [], start=1):
        src = root / "photos" / Path(rel).name
        if not src.is_file():
            raise RuntimeError(f"Missing additional photo {src}")
        dst_name = f"{idx:02d}_{src.name}"
        if dst_name in existing:
            uploaded.append(existing[dst_name])
            continue
        uploaded.append(_multipart_upload(session, EXTRA_FOLDER_ID, dst_name, src.read_bytes()))
    return uploaded


def _caption_html(lot: str) -> str:
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современная 3-спальная Villa Santi в Plai Laem с приватным бассейном и видами на море и закат. Просторная гостиная с оборудованной кухней, 3 спальни и 3 ванные, терраса на крыше, зона отдыха у бассейна и наружный душ. Подходит до 6 гостей.</blockquote>

📍 Район: Plai Laem — между Choeng Mon и Big Buddha
🏠 Тип: вилла
🛏 Спальни: 3
🛁 Ванные: 3
🏊 Бассейн: приватный, 2.5×6.5 м
🚗 Парковка: есть
✈️ До аэропорта: ~10–15 мин

💰 <b>Условия аренды</b>
💵 Цена: 250 000 THB
🔐 Депозит: 1 000 USD
🤝 Комиссия Cozy Asia: 7 000 THB
⚡ Электричество: 7 THB/кВт·ч
💧 Вода: включена
📶 Wi‑Fi: есть
📅 Доступность: по запросу
🐾 Питомцы: не указано

📍 <a href="{MAP_URL}"><b>Геолокация</b></a>
📸 <a href="{EXTRA_FOLDER_URL}"><b>Дополнительные фото</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #PlaiLaem #ВиллаСамуи #Бассейн #ВидНаМоре #CozyAsia"""


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
    selected = [root / "photos" / Path(x).name for x in (manifest.get("telegram_selected") or [])]
    if len(selected) != 10:
        raise RuntimeError(f"Expected exactly 10 Telegram photos, got {len(selected)}")
    missing = [str(p) for p in selected if not p.is_file()]
    if missing:
        raise RuntimeError(f"Missing selected photos: {missing}")

    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client,
            channel,
            ("Villa Santi", "250 000", "Plai Laem"),
            limit=250,
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
            log.info("PUBLISH_VILLA_SANTI_DONE %s", json.dumps(result, ensure_ascii=False))
            return result

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=250)
        if not previous:
            raise RuntimeError("Could not determine latest villa-channel lot")
        lot = str(int(previous) + 1)
        if lot != EXPECTED_LOT:
            raise RuntimeError(f"Expected next lot {EXPECTED_LOT}, but Telegram says next is {lot}")
        await publication_safety.assert_next_lot(client, channel, lot)

        uploaded_extra_ids = await asyncio.to_thread(_ensure_additional_photos, root, manifest)
        if len(uploaded_extra_ids) != len(manifest.get("additional_photos") or []):
            raise RuntimeError("Not all additional photos were uploaded to Drive")

        text, entities = _final_caption(lot)
        sent = await client.send_file(
            channel,
            [str(p) for p in selected],
            caption=text,
            formatting_entities=entities,
        )
        messages = sent if isinstance(sent, list) else [sent]
        if len(messages) != 10:
            raise RuntimeError(f"Expected 10 Telegram album messages, got {len(messages)}")
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        channel_publication_policy.validate_listing_caption(
            verify.message or "", verify.entities or [], lot, CHANNEL
        )
        result = {
            "enabled": True,
            "result": "published",
            "lot": lot,
            "message_id": int(caption_msg.id),
            "telegram_url": f"https://t.me/{CHANNEL}/{int(caption_msg.id)}",
            "telegram_photo_count": len(messages),
            "drive_additional_count": len(uploaded_extra_ids),
            "drive_folder_url": EXTRA_FOLDER_URL,
            "source_url": SOURCE_URL,
            "owner_contact_internal": OWNER_CONTACT,
        }
        log.info("PUBLISH_VILLA_SANTI_DONE %s", json.dumps(result, ensure_ascii=False))
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
    print("PUBLISH_VILLA_SANTI_RESULT=" + json.dumps(result, ensure_ascii=False))

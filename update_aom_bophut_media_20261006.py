# -*- coding: utf-8 -*-
"""Create public Drive media links and add them to LOT 1218's Telegram caption."""
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

log = logging.getLogger("update-aom-bophut-media-20261006")

CHANNEL = "arenda_vill_samui"
LOT = "1218"
MESSAGE_ID = 1202
MAP_URL = "https://maps.app.goo.gl/B5PyarN9dictuPUC7?g_st=ac"
PHOTO_ZIP_FILE_ID = os.getenv("AOM_BOPHUT_PHOTO_ZIP_FILE_ID", "").strip()
VIDEO_SOURCE_FILE_ID = os.getenv("AOM_BOPHUT_VIDEO_SOURCE_FILE_ID", "").strip()
FOLDER_NAME = "LOT 1218 — Bo Phut villa — additional photos and video"


def enabled() -> bool:
    return os.getenv("UPDATE_AOM_BOPHUT_MEDIA_20261006", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _drive_session():
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive"]
    )
    return AuthorizedSession(creds)


def _download(session, file_id: str) -> bytes:
    response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
        timeout=240,
    )
    response.raise_for_status()
    return response.content


def _find_one(session, query: str, fields: str = "files(id,name,mimeType)") -> dict | None:
    response = session.get(
        "https://www.googleapis.com/drive/v3/files",
        params={"q": query, "fields": fields, "pageSize": 20},
        timeout=60,
    )
    response.raise_for_status()
    files = response.json().get("files") or []
    return files[0] if files else None


def _ensure_folder(session) -> str:
    safe_name = FOLDER_NAME.replace("'", "\\'")
    found = _find_one(
        session,
        f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
    )
    if found:
        folder_id = found["id"]
    else:
        response = session.post(
            "https://www.googleapis.com/drive/v3/files",
            params={"fields": "id,name"},
            json={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            timeout=60,
        )
        response.raise_for_status()
        folder_id = response.json()["id"]
    permission = session.post(
        f"https://www.googleapis.com/drive/v3/files/{folder_id}/permissions",
        params={"fields": "id", "sendNotificationEmail": "false"},
        json={"type": "anyone", "role": "reader"},
        timeout=60,
    )
    if permission.status_code not in {200, 201, 409}:
        permission.raise_for_status()
    return folder_id


def _multipart_upload(session, folder_id: str, name: str, data: bytes, mime_type: str) -> str:
    safe_name = name.replace("'", "\\'")
    found = _find_one(
        session,
        f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false",
    )
    if found:
        return found["id"]
    boundary = "cozy_" + uuid.uuid4().hex
    metadata = json.dumps(
        {"name": name, "parents": [folder_id]}, ensure_ascii=False
    ).encode("utf-8")
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + metadata
        + f"\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n".encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = session.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        params={"uploadType": "multipart", "fields": "id,name"},
        headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        data=body,
        timeout=300,
    )
    response.raise_for_status()
    return response.json()["id"]


def _prepare_drive_media() -> tuple[str, str, int]:
    if not PHOTO_ZIP_FILE_ID or not VIDEO_SOURCE_FILE_ID:
        raise RuntimeError("Drive source file IDs are missing")
    session = _drive_session()
    folder_id = _ensure_folder(session)
    work = Path("/tmp/cozy_aom_bophut_media_20261006")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    archive.write_bytes(_download(session, PHOTO_ZIP_FILE_ID))
    photos_dir = work / "photos"
    photos_dir.mkdir()
    with zipfile.ZipFile(archive, "r") as zipped:
        for item in zipped.namelist():
            if item.startswith("photos/") and not item.endswith("/"):
                zipped.extract(item, work)
    photos = sorted((work / "photos").iterdir())
    if len(photos) != 10:
        raise RuntimeError(f"Expected 10 photos, got {len(photos)}")
    for path in photos:
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        _multipart_upload(session, folder_id, path.name, path.read_bytes(), mime_type)
    video_id = _multipart_upload(
        session,
        folder_id,
        "LOT 1218 — видео виллы Bo Phut.mp4",
        _download(session, VIDEO_SOURCE_FILE_ID),
        "video/mp4",
    )
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"
    video_url = f"https://drive.google.com/file/d/{video_id}/view?usp=sharing"
    return folder_url, video_url, len(photos)


def _caption_html(folder_url: str, video_url: str) -> str:
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{LOT}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{LOT}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Светлая двухспальная вилла в тихом жилом комплексе Бопхута. Общий бассейн расположен рядом с домом. Отличный вариант для отдыха в новогодний сезон.</blockquote>

📍 Район: Бопхут
🏠 Вилла
🛏 Спальни: 2
🛋 Просторная гостиная
🍳 Полностью оборудованная кухня
❄️ Кондиционеры
📺 Телевизоры
🌿 Терраса и зелёная территория
🏊 Общий бассейн рядом с виллой
🐾 Без животных

💰 <b>Условия аренды</b>
💵 Цена на новогодний сезон: 95 000 THB/мес.
🤝 Комиссия Cozy Asia: 5 000 THB
🔑 Депозит: 1 месяц
⚡ Электричество: государственный тариф
💧 Вода: тариф комплекса
📅 Свободно: конец ноября, декабрь, январь и февраль
📆 Долгосрок: по запросу

📍 <a href="{MAP_URL}"><b>Геолокация</b></a>
📸 <a href="{folder_url}"><b>Дополнительные фото</b></a>
🎥 <a href="{video_url}"><b>Видео</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Бопхут #ВиллаСамуи #CozyAsia"""


def _final_caption(folder_url: str, video_url: str):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(folder_url, video_url))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, LOT)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, LOT)
    channel_publication_policy.validate_listing_caption(text, entities, LOT, CHANNEL)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities


async def run() -> dict:
    if not enabled():
        return {"enabled": False}
    folder_url, video_url, photo_count = _prepare_drive_media()
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        message = await client.get_messages(channel, ids=MESSAGE_ID)
        if not message or publication_safety.lot_from_message(message) != LOT:
            raise RuntimeError("LOT 1218 caption message not found")
        text, entities = _final_caption(folder_url, video_url)
        await client.edit_message(
            channel, MESSAGE_ID, text,
            formatting_entities=entities,
            link_preview=False,
        )
        verify = await client.get_messages(channel, ids=MESSAGE_ID)
        urls = {
            getattr(entity, "url", "")
            for entity in (getattr(verify, "entities", None) or [])
            if getattr(entity, "url", "")
        }
        if folder_url not in urls or video_url not in urls:
            raise RuntimeError("Drive links missing after Telegram read-back")
        result = {
            "enabled": True,
            "result": "updated",
            "lot": LOT,
            "message_id": MESSAGE_ID,
            "telegram_url": f"https://t.me/{CHANNEL}/{MESSAGE_ID}",
            "folder_url": folder_url,
            "video_url": video_url,
            "photo_count": photo_count,
        }
        log.info("UPDATE_AOM_BOPHUT_MEDIA_DONE %s", json.dumps(result, ensure_ascii=False))
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
    print("UPDATE_AOM_BOPHUT_MEDIA_RESULT=" + json.dumps(result, ensure_ascii=False))

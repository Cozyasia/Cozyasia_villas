# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 973556095092770 in lot 12-31."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import requests
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.service_account import Credentials

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-fb-973556095092770")
SOURCE_ID = "facebook_marketplace_973556095092770"
CHANNEL = "arenda_vill_samui"
LOT = "12-31"
DRIVE_FOLDER_ID = "1js2Pq7x8WJPQpax7o_goqbDOm3hlUgKv"
DRIVE_URL = f"https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}"
MAP_URL = "https://maps.app.goo.gl/8YY9PiENmCivA4nY8"
RENT_URL = "https://cozy-asia.com/rent"

FALLBACK_PHOTO_URLS = [
    "https://sdmntprukwest.oaiusercontent.com/files/00000000-37c8-8243-90bb-648e8b7ebae4/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T07%3A12%3A18Z&ske=2026-11-04T07%3A12%3A18Z&sks=b&skv=2026-02-06&sig=QtjqpZnOz9RMERqS5J1fTvWJSWWylcfrdcpPJIV6a5Q%3D",
    "https://sdmntprsoutheastus3.oaiusercontent.com/files/00000000-889c-820c-9e0f-9ab5f12af8ef/raw?se=2026-11-03T09%3A25%3A07Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T08%3A10%3A36Z&ske=2026-11-04T08%3A10%3A36Z&sks=b&skv=2026-02-06&sig=p9Xsh7o/%2BGjN7xkJXQp%2BuxHO3IGdTpaaH7f9PubE03s%3D",
    "https://sdmntprcentralus.oaiusercontent.com/files/00000000-f368-81f5-97d5-350d47592a63/raw?se=2026-11-03T09%3A25%3A07Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T00%3A19%3A43Z&ske=2026-11-04T00%3A19%3A43Z&sks=b&skv=2026-02-06&sig=dfisIB3t90z5R1Lo5HtNq5oPLzLfam0YsCXW7z6oc%2BQ%3D",
    "https://sdmntpritalynorth.oaiusercontent.com/files/00000000-ddb8-8246-990f-ad295e421621/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T07%3A13%3A03Z&ske=2026-11-04T07%3A13%3A03Z&sks=b&skv=2026-02-06&sig=B2MuMaOw7JRJZZ8Z/PeiCeU/p1y0aklyb2y5uxU%2Bcto%3D",
    "https://sdmntprnortheu.oaiusercontent.com/files/00000000-35fc-81f4-8f61-52cfdbb354ae/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T00%3A34%3A28Z&ske=2026-11-04T00%3A34%3A28Z&sks=b&skv=2026-02-06&sig=QgReWSShSZg/OM9Qpz/UurjhZ9i91jWOpMEo5yxxCZ4%3D",
    "https://sdmntprdenmarkeast.oaiusercontent.com/files/00000000-0758-8210-b841-abe65b311c6d/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T06%3A23%3A33Z&ske=2026-11-04T06%3A23%3A33Z&sks=b&skv=2026-02-06&sig=COMKLkOion3TTEiqmD8xg6C7YvIZ/UHLPSrB14zmyL0%3D",
    "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-e824-820a-bca2-c161c79b6475/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T08%3A10%3A40Z&ske=2026-11-04T08%3A10%3A40Z&sks=b&skv=2026-02-06&sig=EHHKndUITRnrQYG5ZNXbi6/qee%2BpGCSIK0cBEzljf1Y%3D",
    "https://sdmntprukwest.oaiusercontent.com/files/00000000-893c-8243-98f8-b850d9f0d262/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T07%3A11%3A59Z&ske=2026-11-04T07%3A11%3A59Z&sks=b&skv=2026-02-06&sig=9ZjufjQ5jKA2Mp1TOPp3UOMxJUwUXTCbNe/%2B65MtZ5U%3D",
    "https://sdmntprnortheu.oaiusercontent.com/files/00000000-8bdc-81f4-aa5a-67eb6bb33758/raw?se=2026-11-03T09%3A25%3A06Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T04%3A43%3A36Z&ske=2026-11-04T04%3A43%3A36Z&sks=b&skv=2026-02-06&sig=aythvOlFA1ZVELZ3bhw76z7bT4oLJn8Y9v3uwe0uPww%3D",
    "https://sdmntprsouthcentralus.oaiusercontent.com/files/00000000-5ae8-81f7-8369-ad38503fbf19/raw?se=2026-11-03T09%3A25%3A07Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T08%3A59%3A55Z&ske=2026-11-04T08%3A59%3A55Z&sks=b&skv=2026-02-06&sig=BZ4x%2B4MyTQ5rCas1lRVK1y88dULoJTZLQxX5Sgo/Ico%3D"
]


def _caption_html() -> str:
    return f"""🏡 <b>ЛОТ №{LOT}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современная вилла в Bophut с панорамным видом на море и Koh Phangan. Просторная вилла площадью около 335 м² с приватным infinity-бассейном и всем необходимым для комфортного проживания.</blockquote>

📍 Район: Bophut, Koh Samui
🏠 Тип: вилла
🛏 Спальни: 3
🛁 Ванные комнаты: 3
📐 Площадь: около 335 м²
🏊 Приватный infinity-бассейн
🌊 Панорамный вид на море и Koh Phangan
🚗 Крытая парковка
🍳 Оборудованная кухня
🧺 Стиральная и сушильная машины

💰 <b>УСЛОВИЯ АРЕНДЫ</b>

💵 Стоимость: 270 000 THB/мес
📅 Свободна: ноябрь, декабрь, январь, февраль
🔐 Депозит: 1 месяц
🤝 Комиссия в новогодний/high season: 5 000 THB
⚡ Электричество: 7 THB/unit
💧 Вода: 60 THB/unit
🛜 Интернет включён
🏊 Уход за бассейном и садом включён
🧹 Уборка 2 раза в месяц включена

📍 <b>ЛОКАЦИЯ</b>

До Fisherman’s Village, Bophut Beach и Coco Tam’s — около 6 минут.
До Big C и Makro — около 5 минут.

🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>

📸 <a href="{DRIVE_URL}"><b>40 ФОТО</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{RENT_URL}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @Cozy_asia

#Бопхут #ВиллаСамуи #CozyAsia"""


def _make_creds():
    raw = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    return Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive"]
    )


def _token(creds):
    creds.refresh(GoogleAuthRequest())
    return {"Authorization": f"Bearer {creds.token}"}


def _make_folder_public(creds) -> bool:
    base = f"https://www.googleapis.com/drive/v3/files/{DRIVE_FOLDER_ID}"
    headers = _token(creds)
    meta = requests.get(
        base, headers=headers,
        params={"fields": "permissions(type,role)"}, timeout=60
    )
    meta.raise_for_status()
    permissions = meta.json().get("permissions") or []
    if not any(p.get("type") == "anyone" and p.get("role") == "reader" for p in permissions):
        created = requests.post(
            f"{base}/permissions",
            headers={**headers, "Content-Type": "application/json"},
            params={"sendNotificationEmail": "false"},
            json={"type": "anyone", "role": "reader", "allowFileDiscovery": False},
            timeout=60,
        )
        created.raise_for_status()
    verify = requests.get(
        base, headers=_token(creds),
        params={"fields": "permissions(type,role)"}, timeout=60
    )
    verify.raise_for_status()
    public = any(
        p.get("type") == "anyone" and p.get("role") == "reader"
        for p in (verify.json().get("permissions") or [])
    )
    if not public:
        raise RuntimeError("Drive folder is not publicly readable after permission update")
    return True


def _list_photo_files(creds) -> list[dict]:
    headers = _token(creds)
    query = f"'{DRIVE_FOLDER_ID}' in parents and trashed = false and mimeType contains 'image/'"
    files = []
    page_token = None
    while True:
        params = {
            "q": query,
            "pageSize": 1000,
            "orderBy": "createdTime,name",
            "fields": "nextPageToken,files(id,name,mimeType,size,createdTime)",
        }
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers, params=params, timeout=60
        )
        response.raise_for_status()
        payload = response.json()
        files.extend(payload.get("files") or [])
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    if len(files) < 10:
        raise RuntimeError(f"Expected at least 10 photos in Drive folder, found {len(files)}")
    return files


def _download_photos(directory: str, files: list[dict]) -> list[str]:
    creds = _make_creds()
    headers = _token(creds)
    photo_dir = Path(directory) / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, item in enumerate(files[:10], start=1):
        response = requests.get(
            item.get("url") or f"https://www.googleapis.com/drive/v3/files/{item['id']}",
            headers={} if item.get("url") else headers, params={} if item.get("url") else {"alt": "media"}, timeout=120
        )
        response.raise_for_status()
        suffix = Path(item.get("name") or "").suffix.lower() or ".jpg"
        target = photo_dir / f"{index:02d}{suffix}"
        target.write_bytes(response.content)
        if target.stat().st_size < 10_000:
            raise RuntimeError(f"Drive photo {item.get('name')} is unexpectedly small")
        paths.append(str(target))
    return paths


def _premium_caption():
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html())
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, LOT)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    if len(text) > 1024:
        raise RuntimeError(f"Caption is too long: {len(text)}")
    return text, entities


async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("Bophut", "270 000", "Koh Phangan"), limit=300
        )
        if duplicate:
            result = {
                "channel": CHANNEL,
                "lot": publication_safety.lot_from_message(duplicate),
                "message_id": int(duplicate.id),
                "result": "already",
                "source": SOURCE_ID,
            }
            log.info("PUBLISH_FB_973556095092770_DONE %s", json.dumps(result, ensure_ascii=False))
            return result

        try:
            creds = _make_creds()
            public_drive = await asyncio.to_thread(_make_folder_public, creds)
            files = await asyncio.to_thread(_list_photo_files, creds)
        except Exception as exc:
            log.warning("Drive folder unavailable; using Facebook source photos: %s", exc)
            public_drive = False
            files = [{"name": f"facebook-{i:02d}.jpg", "url": url} for i, url in enumerate(FALLBACK_PHOTO_URLS, 1)]
        text, entities = _premium_caption()

        with tempfile.TemporaryDirectory(prefix="fb-973556095092770-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory, files)
            sent = await client.send_file(
                channel, photos, caption=text,
                formatting_entities=entities, link_preview=False
            )

        messages = sent if isinstance(sent, list) else [sent]
        if len(messages) != 10:
            raise RuntimeError(f"Expected 10 album messages, got {len(messages)}")
        grouped_ids = {int(getattr(m, "grouped_id", 0) or 0) for m in messages}
        if len(grouped_ids) != 1 or 0 in grouped_ids:
            raise RuntimeError(f"Album grouping invalid: {grouped_ids}")
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        live_text = getattr(verify, "message", None) or ""
        decoded_lot = publication_safety.lot_from_message(verify)
        if "270 000 THB/мес" not in live_text or RENT_URL not in live_text:
            raise RuntimeError("Read-back caption signature missing")
        if decoded_lot != LOT:
            raise RuntimeError(f"Read-back lot mismatch: got {decoded_lot!r}, expected {LOT!r}")

        result = {
            "channel": CHANNEL,
            "lot": LOT,
            "message_id": int(caption_msg.id),
            "result": "published",
            "photos": len(photos),
            "drive_files": len(files),
            "drive_public_reader": public_drive,
            "source": SOURCE_ID,
        }
        log.info("PUBLISH_FB_973556095092770_DONE %s", json.dumps(result, ensure_ascii=False))
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
    print("PUBLISH_FB_973556095092770_RESULT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    run_service_mode()

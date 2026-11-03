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
    "https://sdmntprindiasocentral.oaiusercontent.com/files/00000000-4398-8211-b398-de33f2ab32f6/raw?se=2026-11-03T09%3A24%3A37Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T07%3A39%3A52Z&ske=2026-11-04T07%3A39%3A52Z&sks=b&skv=2026-02-06&sig=wHQ3BYU0zAKINX1MWfxIx7QD2rVbGgMrXIzXM4VAuxc%3D",
    "https://sdmntprcentralus.oaiusercontent.com/files/00000000-3dc4-81f5-8299-2f88e5cc53e9/raw?se=2026-11-03T09%3A24%3A36Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T08%3A59%3A47Z&ske=2026-11-04T08%3A59%3A47Z&sks=b&skv=2026-02-06&sig=TF79w0n6Hv4oG1fYfnvicCy5g5LQU5HkP%2BoWCGDr358%3D",
    "https://sdmntprindiasocentral.oaiusercontent.com/files/00000000-adc0-8211-b4e2-015b595d1f58/raw?se=2026-11-03T09%3A24%3A36Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d20-977b-a7460af67e45&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T06%3A23%3A36Z&ske=2026-11-04T06%3A23%3A36Z&sks=b&skv=2026-02-06&sig=C7sDS8UStDBQ2ExjhOCqkDf6BNyrsA7A4e0BuAXuWHM%3D",
    "https://sdmntprnortheu.oaiusercontent.com/files/00000000-d9ac-81f4-aafd-2c12f2d5149a/raw?se=2026-11-03T09%3A24%3A34Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T04%3A57%3A01Z&ske=2026-11-04T04%3A57%3A01Z&sks=b&skv=2026-02-06&sig=dY0gb9fXFVRtz9iieMBy/E9r22f4Zy5MrdSaV45Hxrs%3D",
    "https://sdmntprindiasocentral.oaiusercontent.com/files/00000000-3968-8211-b321-d207cce87248/raw?se=2026-11-03T09%3A24%3A36Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d20-977b-a7460af67e45&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T05%3A35%3A34Z&ske=2026-11-04T05%3A35%3A34Z&sks=b&skv=2026-02-06&sig=u/BRNpA9zFNkC4cTx0AwEjQNxVdJEGRHOZqDV4PLhZ8%3D",
    "https://sdmntprnortheu.oaiusercontent.com/files/00000000-e894-81f4-81d6-e1394a333dcf/raw?se=2026-11-03T09%3A24%3A35Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T07%3A39%3A47Z&ske=2026-11-04T07%3A39%3A47Z&sks=b&skv=2026-02-06&sig=MTUm%2BdHYyG2BpzREmpK5cGDKnwN4DUoK7D3VfUUs0VI%3D",
    "https://sdmntprdenmarkeast.oaiusercontent.com/files/00000000-83c8-8210-8527-ced3159dd8ac/raw?se=2026-11-03T09%3A24%3A35Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T00%3A31%3A41Z&ske=2026-11-04T00%3A31%3A41Z&sks=b&skv=2026-02-06&sig=dF5RcQ%2Bs8giHshlts5pkUAbcJPedrj54AvM3fW52%2BBg%3D",
    "https://sdmntprsoutheastus3.oaiusercontent.com/files/00000000-4ea8-820c-b443-a9d3eb11ad43/raw?se=2026-11-03T09%3A24%3A35Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T05%3A35%3A42Z&ske=2026-11-04T05%3A35%3A42Z&sks=b&skv=2026-02-06&sig=95UxVm8W0k4ytrZHGJXmFfa5q2jdM8omj4VTRTfs7rk%3D",
    "https://sdmntprwestus.oaiusercontent.com/files/00000000-1864-8230-9640-9ecc1c68c658/raw?se=2026-11-03T09%3A24%3A36Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T08%3A10%3A55Z&ske=2026-11-04T08%3A10%3A55Z&sks=b&skv=2026-02-06&sig=obN7M8/ejKoNaRDlJ2euPIGP1cT14T%2Bb0hiYkQHENcw",
    "https://sdmntprnortheu.oaiusercontent.com/files/00000000-c53c-81f4-ac0d-d378ecc1a448/raw?se=2026-11-03T09%3A24%3A34Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T07%3A39%3A47Z&ske=2026-11-04T07%3A39%3A47Z&sks=b&skv=2026-02-06&sig=ec%2BE3%2B1sF2oxy4sKsb6OU/YPURVSSBqP0gUflt0QWhM%3D",
    "https://sdmntprnortheu.oaiusercontent.com/files/00000000-59c8-81f4-a814-47a797293a13/raw?se=2026-11-03T09%3A24%3A35Z&sp=r&sv=2026-02-06&sr=b&scid=18fed97d-adba-4d20-977b-a7460af67e45&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2026-11-03T06%3A55%3A42Z&ske=2026-11-04T06%3A55%3A42Z&sks=b&skv=2026-02-06&sig=hcRM1jfGtdgNb8dMPa3RxvnmxOihqrQG7UZwBThJ5fI%3D"
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

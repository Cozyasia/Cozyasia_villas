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
DRIVE_FOLDER_ID = "1RLOwqpA1167ZxVxXVQnyiPtegc68NySi"
DRIVE_URL = f"https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}"
MAP_URL = "https://maps.app.goo.gl/8YY9PiENmCivA4nY8"
RENT_URL = "https://cozy-asia.com/rent"

FALLBACK_PHOTO_URLS = [
    "https://scontent-den2-1.xx.fbcdn.net/v/t39.84726-6/836667283_4593738957572126_7615573023795077502_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=92e707&_nc_ohc=Z6bcP0HUlNsQ7kNvwFxBI9e&_nc_oc=AdqJFBeEpeYv4-OiR0U4uvlfej3FZi057HT8kMGrmMlUUDqczDU-gCi6ILE4XF2gWS3jw8O31Gkr2RBUUJ2kLfcd&_nc_zt=14&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQTrFCU17-1525snb8Z2tRfUYHWbDC0pfwwRxU7pEWZARQ&oe=6AEEAB07",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/837661865_1412461194326593_1635954809709858821_n.jpg?_nc_cat=104&ccb=1-7&_nc_sid=247b10&_nc_ohc=GPZimzcOrHQQ7kNvwHQPAKI&_nc_oc=Adon_bESymOcL01AOkWJd1r7-Rm_wk5smRmMpZMI_qmlVeCQDhtW0oYbDNQxpy_TS4U5c6jxP1-C4L5SDLo02ytu&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQSI2FLFae4JMnt1BYJrww4K0NN8_J6sXfIf1IhzrSaQyQ&oe=6AEEA62C",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/834168453_2267969717357930_81654719685157576_n.jpg?_nc_cat=104&ccb=1-7&_nc_sid=247b10&_nc_ohc=2cyXQtaODowQ7kNvwFVqsE2&_nc_oc=AdqJOYUmVkliwMp1j1MevRW4kyUAdiAgDGxje9Fmxj_0rX2BAc7FiDAAlzqIVeCzP_A7HttJtka5nIDt42gsDu9u&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQQMUz6XacL4FYlbb131tB7uJTTKPUmKxCVSzGbqiTBJPA&oe=6AEEB698",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/834014150_1658845652696223_8714116245827205865_n.jpg?_nc_cat=111&ccb=1-7&_nc_sid=247b10&_nc_ohc=U3ygCtNuhN8Q7kNvwFa14Zp&_nc_oc=AdrNLezaGFAQlsu_L2hy3uinti1kaQW__OjYeH7DOZA-dW54nR9PnVSuzzx37p0G8NJaOe3Awx_jd-le4HdB1ok-&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQSXjf0ciMO4raui4pvYiVZ0CbPeD7UJ_k-eh6gjMgSONg&oe=6AEEA99A",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/836871124_1863475481289232_1273148598453959063_n.jpg?_nc_cat=109&ccb=1-7&_nc_sid=247b10&_nc_ohc=nPo2_245P_sQ7kNvwEGcLnS&_nc_oc=Adob1OWyRZdGPvmkHQEGDhrqZxqwVBt-Hp1bNqIWq1K_PgEAtXnQAwlTz-VX6VOle8q4DFx_s5tNUXdqS8HDUQIG&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQRyX4PyJgB_2k8ylc1J0n3FIGTKpSlEH70JxcKCnDUIxA&oe=6AEEA7B5",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/831280645_2737689603328957_4662508562805028695_n.jpg?_nc_cat=111&ccb=1-7&_nc_sid=247b10&_nc_ohc=sV76I6vJG20Q7kNvwESPGQt&_nc_oc=AdqcMIax66XUYR0NA97Ov-M477RB-tgHkHurIDIieXJwIdWg8B5VStZ9_dpxtDs19qsX465O4bz-YyLexroiZk74&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQRyX4PyJgB_2k8ylc1J0n3FIGTKpSlEH70JxcKCnDUIxA&oe=6AEEAB09",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/834299328_1095759289765567_3918993753370035197_n.jpg?_nc_cat=111&ccb=1-7&_nc_sid=247b10&_nc_ohc=Wfdh6Y2n7EgQ7kNvwHpePSA&_nc_oc=Adq3EzioxliBvZL4qk9_mPhwP1JRNVnGIud0JBZ1655gLCWB57Sk7Zbw0XnphjF-i0Ids_xfnbRhVUrcHqqy6Y0U&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQSRLs0GllHq9PI9-7vtquYu9vWfgBYeQMmHNnoqNUOkNw&oe=6AEEA466",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/832896035_1528357479057071_8501570379461434138_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=247b10&_nc_ohc=J-i4kxgVCJIQ7kNvwF7uIZa&_nc_oc=AdqLK8sSf1xMlmNBKF6PpQj7yokCEm00ZrwBjO3fnj_tB87mxlnsGiataa6tzwwFxECmIXgNydBt57NoRt8U2lw9&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQQ9nAUB1LAMQoPi1gML62HSzpuKdYIHcoGhyMitor9Umw&oe=6AEE800C",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/839631859_2251726072039798_5305260339420749046_n.jpg?_nc_cat=106&ccb=1-7&_nc_sid=247b10&_nc_ohc=51f3dqkSckYQ7kNvwGv6Meq&_nc_oc=AdptBH1c3y-DZiEQyjs9bc1op93uyZAQrjVdRqrT5CMw9MbCK0dypj8RM3uHglAySSsm064XFMZ6pzrF7Io-nJBB&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQR9XbfHXQf6IMhcaGczB4oJlvyg51v4fz22PcI34OBFCg&oe=6AEE8FF9",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/836842027_1100627482566721_6505995408698213114_n.jpg?_nc_cat=100&ccb=1-7&_nc_sid=247b10&_nc_ohc=PT2usQHMyFsQ7kNvwFwJ3GR&_nc_oc=AdpIxveM_2iW_iOnwO9qPwWTQEl4l33ftMCVsHbs2jfcJQX53tdrqf3-gqdbcvLQgNibDuiPCLahQJWw9j3yhdZ0&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=K55OOJGyt6NV4xSrCQdQ4A&_nc_ss=7b2a8&oh=00_AQTktO6B6zftWxWs9MOhEaMuBEkNQUuNe5lBQtIy5WEgbA&oe=6AEE9B1A"
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

📸 <a href="{DRIVE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО — 40 ФОТО</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{RENT_URL}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @Cozy_asia

#АрендаСамуи #Бопхут #ВиллаСамуи #ВиллаСБассейном #ВидНаМоре #KohSamuiRental #CozyAsia"""


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

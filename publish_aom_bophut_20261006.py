# -*- coding: utf-8 -*-
"""One-shot publication of Aom's Bo Phut villa to the small villa channel."""
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

log = logging.getLogger("publish-aom-bophut-20261006")

CHANNEL = "arenda_vill_samui"
PHOTO_ZIP_FILE_ID = os.getenv("AOM_BOPHUT_PHOTO_ZIP_FILE_ID", "").strip()
MAP_URL = "https://maps.app.goo.gl/B5PyarN9dictuPUC7?g_st=ac"
SOURCE_URL = "https://wa.me/66640323150"


def enabled() -> bool:
    return os.getenv("PUBLISH_AOM_BOPHUT_20261006", "0").strip().lower() in {
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
        raise RuntimeError("AOM_BOPHUT_PHOTO_ZIP_FILE_ID is missing")
    work = Path("/tmp/cozy_aom_bophut_20261006")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    root = work / "package"
    root.mkdir()
    response = _drive_session().get(
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
<blockquote>Светлая двухспальная вилла в тихом жилом комплексе Бопхута. Общий бассейн расположен рядом с домом. Отличный вариант для отдыха в новогодний сезон; видео доступно по запросу.</blockquote>

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
🎥 Видео: по запросу

📍 <a href="{MAP_URL}"><b>Геолокация</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Бопхут #ВиллаСамуи #CozyAsia"""


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
        if os.getenv("CLEANUP_AOM_DUPLICATE_1219", "0").strip().lower() in {"1", "true", "yes", "on"}:
            duplicate_caption = await client.get_messages(channel, ids=1212)
            if duplicate_caption and publication_safety.lot_from_message(duplicate_caption) == "1219":
                await client.delete_messages(channel, list(range(1212, 1222)), revoke=True)
                log.info("Deleted accidental duplicate album for lot 1219 (messages 1212-1221)")
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("Светлая двухспальная вилла", "95 000", "новогодний сезон"), limit=300
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {
                "enabled": True, "result": "already", "lot": lot,
                "message_id": int(duplicate.id),
                "telegram_url": f"https://t.me/{CHANNEL}/{int(duplicate.id)}",
            }
            log.info("PUBLISH_AOM_BOPHUT_DONE %s", json.dumps(result, ensure_ascii=False))
            return result

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine latest villa-channel lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)

        text, entities = _final_caption(lot)
        sent = await client.send_file(
            channel, [str(path) for path in selected], caption=text,
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
            "enabled": True, "result": "published", "lot": lot,
            "message_id": int(caption_message.id),
            "telegram_url": f"https://t.me/{CHANNEL}/{int(caption_message.id)}",
            "telegram_photo_count": len(messages), "source_url": SOURCE_URL,
        }
        log.info("PUBLISH_AOM_BOPHUT_DONE %s", json.dumps(result, ensure_ascii=False))
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
    print("PUBLISH_AOM_BOPHUT_RESULT=" + json.dumps(result, ensure_ascii=False))

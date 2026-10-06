# -*- coding: utf-8 -*-
"""Replace and reorder LOT 1218 album photos without creating a new post."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import zipfile
from pathlib import Path

import cozy_catalog
import mtproto_user_client
import publication_safety
import update_aom_bophut_media_20261006 as media_update
from telethon.errors import MessageNotModifiedError

log = logging.getLogger("reorder-aom-bophut-photos-20261006")

CHANNEL = "arenda_vill_samui"
LOT = "1218"
MESSAGE_IDS = tuple(range(1202, 1212))
PACKAGE_FILE_ID = os.getenv(
    "AOM_BOPHUT_REORDERED_PACKAGE_FILE_ID",
    "1N0DznlKJK1mYduvL6nAyL6GqGZMV5q8E",
).strip()
VIDEO_FILE_ID = os.getenv(
    "AOM_BOPHUT_VIDEO_SOURCE_FILE_ID",
    "1FOsizaCqARduCQSUIxrKmstaeIvra75j",
).strip()


def enabled() -> bool:
    return os.getenv("REORDER_AOM_BOPHUT_PHOTOS_20261006", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _prepare_photos() -> tuple[list[Path], str, str]:
    if not PACKAGE_FILE_ID or not VIDEO_FILE_ID:
        raise RuntimeError("Drive source file IDs are missing")
    session = media_update._drive_session()
    media_update._make_public(session, PACKAGE_FILE_ID)
    media_update._make_public(session, VIDEO_FILE_ID)

    response = session.get(
        f"https://www.googleapis.com/drive/v3/files/{PACKAGE_FILE_ID}?alt=media",
        timeout=240,
    )
    response.raise_for_status()

    work = Path("/tmp/cozy_aom_bophut_reorder_20261006")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "photos.zip"
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive, "r") as zipped:
        zipped.extractall(work / "photos")

    photos = sorted(
        p for p in (work / "photos").iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if len(photos) != 10:
        raise RuntimeError(f"Expected exactly 10 reordered photos, got {len(photos)}")
    expected = [f"{idx:02d}-" for idx in range(1, 11)]
    for prefix, path in zip(expected, photos):
        if not path.name.startswith(prefix):
            raise RuntimeError(f"Unexpected photo order at {path.name}; wanted {prefix}*")

    photos_url = f"https://drive.google.com/file/d/{PACKAGE_FILE_ID}/view?usp=sharing"
    video_url = f"https://drive.google.com/file/d/{VIDEO_FILE_ID}/view?usp=sharing"
    return photos, photos_url, video_url


async def run() -> dict:
    if not enabled():
        return {"enabled": False}
    photos, photos_url, video_url = _prepare_photos()
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")

    try:
        channel = await client.get_entity(CHANNEL)
        messages = await client.get_messages(channel, ids=list(MESSAGE_IDS))
        by_id = {message.id: message for message in messages if message}
        if set(by_id) != set(MESSAGE_IDS):
            raise RuntimeError("Could not read all ten LOT 1218 album messages")
        if publication_safety.lot_from_message(by_id[MESSAGE_IDS[0]]) != LOT:
            raise RuntimeError("LOT 1218 caption message not found")

        caption, entities = media_update._final_caption(photos_url, video_url)
        for index, (message_id, photo) in enumerate(zip(MESSAGE_IDS, photos)):
            if index == 0:
                text = caption
                formatting_entities = entities
            else:
                text = by_id[message_id].message or ""
                formatting_entities = by_id[message_id].entities or []
            try:
                await client.edit_message(
                    channel,
                    message_id,
                    text,
                    formatting_entities=formatting_entities,
                    file=str(photo),
                    link_preview=False,
                )
            except MessageNotModifiedError:
                # Safe idempotency: a previous interrupted run may already have
                # placed this exact photo and caption in the requested slot.
                log.info("Album slot already correct: message_id=%s", message_id)

        verify = await client.get_messages(channel, ids=list(MESSAGE_IDS))
        verify_by_id = {message.id: message for message in verify if message}
        if set(verify_by_id) != set(MESSAGE_IDS):
            raise RuntimeError("Album verification failed: messages missing")
        if any(not getattr(verify_by_id[mid], "photo", None) for mid in MESSAGE_IDS):
            raise RuntimeError("Album verification failed: a photo is missing")
        first = verify_by_id[MESSAGE_IDS[0]]
        urls = {
            getattr(entity, "url", "")
            for entity in (getattr(first, "entities", None) or [])
            if getattr(entity, "url", "")
        }
        if photos_url not in urls or video_url not in urls:
            raise RuntimeError("Updated Drive links missing after Telegram read-back")

        result = {
            "enabled": True,
            "result": "reordered",
            "lot": LOT,
            "message_ids": list(MESSAGE_IDS),
            "telegram_url": f"https://t.me/{CHANNEL}/{MESSAGE_IDS[0]}",
            "photos_url": photos_url,
            "video_url": video_url,
            "order": [path.name for path in photos],
        }
        log.info("REORDER_AOM_BOPHUT_PHOTOS_DONE %s", json.dumps(result, ensure_ascii=False))
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
    print("REORDER_AOM_BOPHUT_PHOTOS_RESULT=" + json.dumps(result, ensure_ascii=False))

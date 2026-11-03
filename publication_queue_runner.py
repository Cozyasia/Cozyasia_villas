"""Google Sheets publication queue runner; explicit manual execution only."""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
import requests
import re
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2.service_account import Credentials
from telethon.extensions import html as telethon_html
import cozy_catalog
import mtproto_user_client
import publication_safety

LOG = logging.getLogger("cozy-publication-queue")
SHEET = "PublicationQueue"
EXPECTED = ("lot", "status", "caption_html", "photo_drive_ids", "telegram_url", "error", "updated_at", "channel")

def _sheet():
    return cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID).worksheet(SHEET)

def _photo_paths(ids, directory):
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDS_JSON"]),
        scopes=["https://www.googleapis.com/auth/drive.readonly"])
    creds.refresh(AuthRequest())
    result = []
    for i, fid in enumerate(ids, 1):
        response = requests.get(
            "https://www.googleapis.com/drive/v3/files/" + fid,
            params={"alt": "media"},
            headers={"Authorization": "Bearer " + creds.token},
            timeout=90)
        response.raise_for_status()
        path = Path(directory) / ("%02d.jpg" % i)
        path.write_bytes(response.content)
        if path.stat().st_size < 10000:
            raise RuntimeError("Invalid photo " + str(i))
        result.append(str(path))
    return result

async def _publish(lot, caption, ids, channel_name):
    client = await mtproto_user_client._new_client(cozy_catalog)
    if client is None:
        raise RuntimeError("MTProto session unavailable")
    try:
        channel = await client.get_entity(channel_name)
        recent = await client.get_messages(channel, limit=300)
        for msg in recent:
            if publication_safety.lot_from_message(msg) == lot or re.search(r"(?i)(?:лот|lot)\s*[№#]?\s*" + re.escape(lot) + r"(?!\d)", getattr(msg, "message", "") or ""):
                return "https://t.me/" + channel_name + "/" + str(msg.id), "already"
        text, entities = telethon_html.parse(caption)
        text, entities, upgraded = mtproto_user_client.upgrade_text(text, entities, lot)
        if not upgraded:
            raise RuntimeError("Premium emoji upgrade failed")
        if len(text.encode("utf-16-le")) // 2 > 1024:
            raise RuntimeError("Telegram album caption exceeds 1024 UTF-16 units")
        with tempfile.TemporaryDirectory(prefix="cozy-queue-") as directory:
            photos = await asyncio.to_thread(_photo_paths, ids, directory)
            sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)
        messages = sent if isinstance(sent, list) else [sent]
        if len(messages) != 10:
            raise RuntimeError("Expected 10 photos, got " + str(len(messages)))
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=caption_msg.id)
        if verify is None or not (publication_safety.lot_from_message(verify) == lot or re.search(r"(?i)(?:лот|lot)\s*[№#]?\s*" + re.escape(lot) + r"(?!\d)", getattr(verify, "message", "") or "")):
            LOG.warning("Telegram album sent but caption readback mismatch; message_id=%s lot=%s", caption_msg.id, lot)
            return "https://t.me/" + channel_name + "/" + str(caption_msg.id), "sent_unverified"
        return "https://t.me/" + channel_name + "/" + str(caption_msg.id), "published"
    finally:
        await client.disconnect()

def run_once():
    ws = _sheet()
    values = ws.get_all_values()
    if not values or tuple(values[0][:8]) != EXPECTED:
        raise RuntimeError("PublicationQueue header mismatch")
    for row_number, raw in enumerate(values[1:], 2):
        row = (raw + [""] * 8)[:8]
        lot, status, caption, photo_ids, url, error, updated, channel = row
        if status == "failed" and "Telegram readback failed" in error:
            client = None
            try:
                async def _reconcile():
                    c = await mtproto_user_client._new_client(cozy_catalog)
                    if c is None:
                        raise RuntimeError("MTProto session unavailable")
                    try:
                        entity = await c.get_entity(channel)
                        for m in await c.get_messages(entity, limit=300):
                            if publication_safety.lot_from_message(m) == lot or re.search(r"(?i)(?:лот|lot)\s*[№#]?\s*" + re.escape(lot) + r"(?!\d)", getattr(m, "message", "") or ""):
                                return "https://t.me/" + channel + "/" + str(m.id)
                    finally:
                        await c.disconnect()
                found = asyncio.run(_reconcile())
                if found:
                    ws.update_cell(row_number, 5, found)
                    ws.update_cell(row_number, 6, "reconciled_after_readback_error")
                    ws.update_cell(row_number, 2, "published")
            except Exception:
                LOG.exception("Reconciliation failed for lot %s", lot)
            continue
        if status != "ready":
            continue
        if not lot or not channel or not caption:
            ws.update_cell(row_number, 6, "Missing required queue data")
            ws.update_cell(row_number, 2, "failed")
            continue
        ids = [x.strip() for x in photo_ids.split(",") if x.strip()]
        if len(ids) != 10:
            ws.update_cell(row_number, 6, "Expected 10 Drive photo IDs")
            ws.update_cell(row_number, 2, "failed")
            continue
        ws.update_cell(row_number, 2, "processing")
        try:
            link, outcome = asyncio.run(_publish(lot, caption, ids, channel))
            ws.update_cell(row_number, 5, link)
            ws.update_cell(row_number, 6, outcome)
            ws.update_cell(row_number, 2, "published")
            LOG.info("QUEUE_PUBLICATION_RESULT lot=%s url=%s outcome=%s", lot, link, outcome)
        except Exception as exc:
            LOG.exception("Queue publication failed for lot %s", lot)
            ws.update_cell(row_number, 6, str(exc)[:400])
            ws.update_cell(row_number, 2, "failed")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_once()

# -*- coding: utf-8 -*-
"""One-shot in-place correction of the 2026-10-19 Facebook villa batch.

Edits only the ten already published album captions (first message of each
album) and synchronizes the corresponding Lots rows. No new posts, deletes,
bookings, or payments.
"""
from __future__ import annotations

import asyncio
import html as pyhtml
import json
import os
import re
from typing import Any

CHANNEL = "arenda_vill_samui"
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1AUXHak2TrKH-r3U_J4_pmUF6r8VjS1loa4SSGmcy2JE")
LOTS_SHEET = "Lots"

# The last pre-batch post is 1261, recorded as lot 1220 in Lots.
# V10 was not published, so the ten existing albums map to 1221..1230.
ITEMS = (
    (1711, "V01", "1221", 130000, 140000),
    (1721, "V02", "1222", 88000, 98000),
    (1731, "V03", "1223", 120000, 130000),
    (1741, "V04", "1224", 98000, 108000),
    (1751, "V05", "1225", 100000, 110000),
    (1761, "V06", "1226", 120000, 130000),
    (1771, "V07", "1227", 90000, 100000),
    (1781, "V08", "1228", 85000, 95000),
    (1791, "V09", "1229", 125000, 135000),
    (1801, "V11", "1230", 110000, 120000),
)
COMMISSION = 5000


def _replace_prices(source_html: str, new_price: int) -> str:
    formatted = f"{new_price:,}"
    out = re.sub(
        r"В объявлении:\s*[\d,\s]+\s*THB/мес\.",
        f"Цена для клиента: {formatted} THB/мес.",
        source_html,
        count=1,
    )
    out = re.sub(
        r"Цена:\s*[\d,\s]+\s*THB/мес\.",
        f"Цена: {formatted} THB/мес.",
        out,
        count=1,
    )
    out = re.sub(
        r"Комиссия(?: Cozy Asia)?:\s*(?:уточняется|не указано|Не указано|[\d,\s]+\s*THB)?",
        f"Комиссия Cozy Asia: {COMMISSION:,} THB",
        out,
        count=1,
    )
    return out


def _replace_lot(source_html: str, old_lot: str, new_lot: str) -> str:
    out = source_html.replace(f"rent_{old_lot}", f"rent_{new_lot}")
    # Replace visible V01/V02 text while retaining the surrounding Telegram
    # formatting and custom emoji entities after reparsing.
    out = re.sub(re.escape(old_lot), new_lot, out)
    return out


def _caption_html(message: Any) -> str:
    from telethon.extensions import html as telethon_html
    raw = getattr(message, "message", None) or getattr(message, "raw_text", None) or ""
    entities = getattr(message, "entities", None) or []
    return telethon_html.unparse(raw, entities)


async def _run_telegram() -> dict[str, Any]:
    import cozy_catalog
    from mtproto_user_client import _new_client
    from telethon.extensions import html as telethon_html

    client = await _new_client(cozy_catalog)
    if client is None:
        raise RuntimeError("MTProto session is not authorized")
    channel = await client.get_entity(f"@{CHANNEL}")
    changed: list[dict[str, Any]] = []
    try:
        for message_id, old_lot, new_lot, source_price, client_price in ITEMS:
            message = await client.get_messages(channel, ids=message_id)
            if not message:
                raise RuntimeError(f"message {message_id} not found")
            source_html = _caption_html(message)
            updated_html = _replace_lot(source_html, old_lot, new_lot)
            updated_html = _replace_prices(updated_html, client_price)
            text, entities = telethon_html.parse(updated_html)
            await client.edit_message(
                channel,
                message_id,
                text=text,
                formatting_entities=entities,
                link_preview=False,
            )
            check = await client.get_messages(channel, ids=message_id)
            check_html = _caption_html(check)
            if new_lot not in check_html or f"{client_price:,} THB/мес." not in check_html:
                raise RuntimeError(f"read-back failed for {new_lot} / {message_id}")
            changed.append({
                "message_id": message_id,
                "old_lot": old_lot,
                "new_lot": new_lot,
                "source_price_thb": source_price,
                "client_price_thb": client_price,
                "commission_thb": COMMISSION,
                "telegram_url": f"https://t.me/{CHANNEL}/{message_id}",
            })
        return {"changed": changed}
    finally:
        await client.disconnect()


def _sync_lots(changed: list[dict[str, Any]]) -> dict[str, Any]:
    import gspread
    from google.oauth2.service_account import Credentials

    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")
    info = json.loads(raw)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    client = gspread.authorize(Credentials.from_service_account_info(info, scopes=scopes))
    ws = client.open_by_key(SHEET_ID).worksheet(LOTS_SHEET)
    values = ws.get_all_values()
    if not values:
        raise RuntimeError("Lots sheet is empty")
    headers = {name.strip(): idx + 1 for idx, name in enumerate(values[0])}
    required = ["lot_id", "telegram_message_id", "цена_месяц_thb", "комиссия_thb"]
    missing = [x for x in required if x not in headers]
    if missing:
        raise RuntimeError(f"Lots headers missing: {missing}")

    by_message = {
        str(row[headers["telegram_message_id"] - 1]).strip(): row_index
        for row_index, row in enumerate(values[1:], start=2)
        if len(row) >= headers["telegram_message_id"]
    }
    updated = []
    for item in changed:
        row_index = by_message.get(str(item["message_id"]))
        if not row_index:
            raise RuntimeError(f"Lots row not found for Telegram message {item['message_id']}")
        ws.update_cell(row_index, headers["lot_id"], item["new_lot"])
        ws.update_cell(row_index, headers["цена_месяц_thb"], item["client_price_thb"])
        ws.update_cell(row_index, headers["комиссия_thb"], item["commission_thb"])
        updated.append({"row": row_index, "message_id": item["message_id"], "lot_id": item["new_lot"]})
    return {"updated_rows": updated}


def run_service_mode() -> None:
    changed = asyncio.run(_run_telegram())["changed"]
    sheet = _sync_lots(changed)
    print(json.dumps({"ok": True, "channel": CHANNEL, "changed": changed, "sheet": sheet}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_service_mode()

# -*- coding: utf-8 -*-
"""One-shot Premium Custom Emoji smoke test for a single channel listing."""
from __future__ import annotations

import json
import logging
import time

import post_template_patch as tpl

log = logging.getLogger("premium-smoke")
MARKER = "__PREMIUM_V6_SMOKE__"
REFERENCE_MID = "872"


def _state(mod, catalog):
    try:
        for row in mod._backup_sheet(catalog).get_all_values():
            if row and str(row[0]) == MARKER:
                return row
    except Exception:
        log.exception("Could not read smoke marker")
    return None


def _save(mod, catalog, result):
    try:
        mod._backup_sheet(catalog).append_row([
            MARKER,
            str(result.get("lot") or ""),
            str(result.get("url") or ""),
            "", "",
            json.dumps(result, ensure_ascii=False),
            time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        ], value_input_option="RAW")
    except Exception:
        log.exception("Could not persist smoke result")


def _call(mod, token, method, data):
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        r = mod.requests.post(url, data=data, timeout=45)
        try:
            p = r.json()
        except Exception:
            p = {"ok": False, "description": r.text[:500]}
        return p
    except Exception as exc:
        return {"ok": False, "description": f"network error: {exc}"}


def run(mod, catalog):
    if _state(mod, catalog):
        log.info("Premium V6 smoke already recorded; skipping")
        return

    token, bot_username, can_edit, status = mod.bot_identity_and_rights(catalog.CATALOG_CHANNEL)
    if not can_edit:
        result = {"ok": False, "error": "can_edit_messages=false", "status": status}
        _save(mod, catalog, result)
        log.error("Premium smoke aborted: %s", result)
        return

    rows = [
        r for r in catalog.load_catalog_rows(True)
        if str(r.get("telegram_message_id") or "").isdigit()
        and str(r.get("telegram_message_id")) != REFERENCE_MID
        and str(r.get("lot_id") or "").strip()
        and str(r.get("status") or "active").lower() not in {"archived", "inactive"}
    ]
    if not rows:
        result = {"ok": False, "error": "no candidate row"}
        _save(mod, catalog, result)
        log.error("Premium smoke aborted: no candidate")
        return

    # Use the nearest previous listing to the reference post so the visual result is easy to inspect.
    rows.sort(key=lambda r: int(r.get("telegram_message_id") or 0), reverse=True)
    row = next((r for r in rows if int(r["telegram_message_id"]) < int(REFERENCE_MID)), rows[0])
    mid = str(row["telegram_message_id"])
    lot = str(row.get("lot_id") or "")
    url = str(row.get("telegram_url") or f"https://t.me/{catalog.CATALOG_CHANNEL}/{mid}")
    log.info("Premium V6 smoke START @%s mid=%s lot=%s", catalog.CATALOG_CHANNEL, mid, lot)

    links_by_mid, texts_by_mid, mode_by_mid = tpl._crawl_payloads(
        mod, catalog.CATALOG_CHANNEL, [mid], min(catalog.MAX_PAGES, 40)
    )
    try:
        mod._backup_rows(catalog, [row], links_by_mid, texts_by_mid)
    except Exception:
        log.exception("Smoke backup failed (continuing; original should already exist in PostBackup)")

    new_html = mod.build_post(row, bot_username, links_by_mid.get(mid, []))
    mode = mode_by_mid.get(mid, "caption")
    common = {"chat_id": f"@{catalog.CATALOG_CHANNEL}", "message_id": mid, "parse_mode": "HTML"}
    method = "editMessageCaption" if mode == "caption" else "editMessageText"
    data = {**common, ("caption" if mode == "caption" else "text"): new_html}
    if mode != "caption":
        data["disable_web_page_preview"] = "true"
    payload = _call(mod, token, method, data)

    # Only fall back between text/caption when Telegram says the selected kind is wrong.
    if not payload.get("ok"):
        desc = str(payload.get("description") or "")
        low = desc.lower()
        wrong_kind = (
            (mode == "caption" and ("not a media message" in low or "there is no caption" in low))
            or (mode == "text" and "there is no text in the message to edit" in low)
        )
        if wrong_kind:
            alt = "text" if mode == "caption" else "caption"
            method = "editMessageText" if alt == "text" else "editMessageCaption"
            data = {**common, ("text" if alt == "text" else "caption"): new_html}
            if alt == "text":
                data["disable_web_page_preview"] = "true"
            payload = _call(mod, token, method, data)
            mode = alt

    result = {
        "ok": bool(payload.get("ok")),
        "channel": catalog.CATALOG_CHANNEL,
        "mid": mid,
        "lot": lot,
        "url": url,
        "mode": mode,
        "error": "" if payload.get("ok") else str(payload.get("description") or "unknown Telegram error")[:600],
    }
    _save(mod, catalog, result)
    if result["ok"]:
        log.info("Premium V6 smoke SUCCESS mid=%s lot=%s url=%s", mid, lot, url)
    else:
        log.error("Premium V6 smoke FAILED mid=%s lot=%s error=%s", mid, lot, result["error"])

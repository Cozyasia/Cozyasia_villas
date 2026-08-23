# -*- coding: utf-8 -*-
"""Correct already-rendered V6 Premium posts whose lot_id was temporarily collapsed to 0/1."""
from __future__ import annotations

import json
import logging
import time

import lot_id_repair
import post_template_patch as tpl

log = logging.getLogger("premium-lot-corrective")
PROGRESS_PREFIX = "__STD_V6_PREMIUM__:"
REPAIR_PREFIX = "__STD_V6_LOT_REPAIR__:"
SMOKE_MARKER = "__PREMIUM_V6_SMOKE__"


def _call(mod, token, method, data):
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        r = mod.requests.post(url, data=data, timeout=45)
        try:
            payload = r.json()
        except Exception:
            payload = {"ok": False, "description": r.text[:500]}
        payload["_status"] = r.status_code
        return payload
    except Exception as exc:
        return {"ok": False, "description": f"network error: {exc}", "_status": 0}


def _edit(mod, token, channel, mid, html_text, mode):
    common = {"chat_id": f"@{channel}", "message_id": mid, "parse_mode": "HTML"}
    for selected in (mode, "text" if mode == "caption" else "caption"):
        method = "editMessageCaption" if selected == "caption" else "editMessageText"
        data = {**common, ("caption" if selected == "caption" else "text"): html_text}
        if selected == "text":
            data["disable_web_page_preview"] = "true"
        payload = _call(mod, token, method, data)
        if payload.get("ok"):
            return True, selected, ""
        desc = str(payload.get("description") or "")
        low = desc.lower()
        if "message is not modified" in low:
            return True, selected, "unchanged"
        retry = (payload.get("parameters") or {}).get("retry_after")
        if retry is not None or payload.get("_status") == 429:
            try:
                wait = max(1, int(float(retry or 5)))
            except Exception:
                wait = 5
            time.sleep(wait + 2)
            payload = _call(mod, token, method, data)
            if payload.get("ok") or "message is not modified" in str(payload.get("description") or "").lower():
                return True, selected, ""
            desc = str(payload.get("description") or "")
            low = desc.lower()
        wrong_kind = (
            selected == mode
            and ((selected == "caption" and ("not a media message" in low or "there is no caption" in low))
                 or (selected == "text" and "there is no text in the message to edit" in low))
        )
        if not wrong_kind:
            return False, selected, desc[:600]
    return False, mode, "could not determine editable message kind"


def _read_state(mod, catalog):
    vals = mod._backup_sheet(catalog).get_all_values()
    progress = {}
    repaired = set()
    smoke = None
    for row in vals[1:]:
        if not row:
            continue
        key = str(row[0] or "").strip()
        if key.startswith(PROGRESS_PREFIX):
            mid = key[len(PROGRESS_PREFIX):].strip()
            lot = str(row[1] if len(row) > 1 else "").strip()
            if mid.isdigit():
                progress[mid] = lot
        elif key.startswith(REPAIR_PREFIX):
            mid = key[len(REPAIR_PREFIX):].strip()
            if mid.isdigit():
                repaired.add(mid)
        elif key == SMOKE_MARKER:
            try:
                data = json.loads(row[5] if len(row) > 5 and row[5] else "{}")
            except Exception:
                data = {}
            if str(data.get("mid") or "").isdigit():
                smoke = {"mid": str(data.get("mid")), "lot": str(data.get("lot") or "")}
    return progress, repaired, smoke


def _save(mod, catalog, mid, lot, url, result):
    mod._backup_sheet(catalog).append_row([
        REPAIR_PREFIX + str(mid), str(lot), str(url), "", "",
        json.dumps(result, ensure_ascii=False),
        time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    ], value_input_option="RAW")


def run(mod, catalog):
    try:
        authority = lot_id_repair.authoritative_lots_by_mid(catalog)
        rows = catalog.load_catalog_rows(True)
        by_mid = {str(r.get("telegram_message_id") or ""): dict(r) for r in rows if str(r.get("telegram_message_id") or "").isdigit()}
        progress, repaired, smoke = _read_state(mod, catalog)
    except Exception:
        log.exception("Could not prepare Premium lot corrective pass")
        return {"error": "prepare_failed"}

    targets = set()
    for mid, rendered_lot in progress.items():
        correct = authority.get(mid) or str(by_mid.get(mid, {}).get("lot_id") or "").strip()
        if correct and rendered_lot != correct:
            targets.add(mid)
    if smoke:
        mid = smoke["mid"]
        correct = authority.get(mid) or str(by_mid.get(mid, {}).get("lot_id") or "").strip()
        if correct and smoke.get("lot") != correct:
            targets.add(mid)
    targets -= repaired

    # Only correct posts for which we have an authoritative valid lot ID and catalog row.
    targets = sorted(
        (m for m in targets if m in by_mid and (authority.get(m) or by_mid[m].get("lot_id"))),
        key=int,
    )
    if not targets:
        log.info("Premium lot corrective: no mismatches remain")
        return {"targets": 0, "repaired": 0, "failed": 0}

    token, bot_username, can_edit, status = mod.bot_identity_and_rights(catalog.CATALOG_CHANNEL)
    if not can_edit:
        log.error("Premium lot corrective aborted: bot status=%s can_edit=%s", status, can_edit)
        return {"targets": len(targets), "repaired": 0, "failed": len(targets), "error": "can_edit=false"}

    links_by_mid, _, mode_by_mid = tpl._crawl_payloads(
        mod, catalog.CATALOG_CHANNEL, targets, min(catalog.MAX_PAGES, 80)
    )
    repaired_n = 0
    failed_n = 0
    last_api_at = 0.0

    for mid in targets:
        row = by_mid[mid]
        correct = authority.get(mid) or str(row.get("lot_id") or "").strip()
        row["lot_id"] = correct
        url = str(row.get("telegram_url") or f"https://t.me/{catalog.CATALOG_CHANNEL}/{mid}")
        new_html = mod.build_post(row, bot_username, links_by_mid.get(mid, []))
        wait = 3.4 - (time.monotonic() - last_api_at)
        if wait > 0:
            time.sleep(wait)
        ok, used_mode, detail = _edit(
            mod, token, catalog.CATALOG_CHANNEL, mid, new_html, mode_by_mid.get(mid, "caption")
        )
        last_api_at = time.monotonic()
        result = {
            "mid": mid, "lot": correct, "url": url,
            "ok": bool(ok), "mode": used_mode, "detail": detail,
        }
        try:
            _save(mod, catalog, mid, correct, url, result)
        except Exception:
            log.exception("Could not persist lot corrective marker mid=%s", mid)
        if ok:
            repaired_n += 1
            log.info("Premium lot corrective SUCCESS mid=%s lot=%s", mid, correct)
        else:
            failed_n += 1
            log.error("Premium lot corrective FAILED mid=%s lot=%s error=%s", mid, correct, detail)

    stats = {"targets": len(targets), "repaired": repaired_n, "failed": failed_n}
    log.info("Premium lot corrective DONE %s", stats)
    return stats

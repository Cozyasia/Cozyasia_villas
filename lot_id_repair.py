# -*- coding: utf-8 -*-
"""Repair lot IDs damaged by spaced/keycap/custom-emoji rendering and prevent recurrence."""
from __future__ import annotations

import re
import logging

log = logging.getLogger("lot-id-repair")


def _collapse_candidate(value: str) -> str:
    s = re.sub(r"\s+", "", value or "")
    s = s.replace("–", "-").replace("—", "-").replace("−", "-").replace("➖", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    if not re.fullmatch(r"\d{3,7}(?:-\d{1,2})?|\d{1,2}-\d{3,7}(?:-\d{1,2})?", s):
        return ""
    return s


def _robust_from_normalized(norm: str) -> str:
    head = (norm or "")[:700]
    marker = re.search(r"(?is)(?:\bлот\b|\blot\b)\s*(?:№|#|no\.?)?\s*[:\-]?\s*", head)
    if marker:
        tail = head[marker.end():marker.end()+90]
        m = re.match(
            r"((?:\d\s*){1,2}-\s*(?:\d\s*){3,7}(?:-\s*(?:\d\s*){1,2})?|"
            r"(?:\d\s*){3,7}(?:-\s*(?:\d\s*){1,2})?)",
            tail,
        )
        if m:
            value = _collapse_candidate(m.group(1))
            if value:
                return value
    m = re.search(r"(?<!\d)((?:\d\s*){1,2})-\s*((?:\d\s*){3,7})(?:-\s*((?:\d\s*){1,2}))?", head)
    if m:
        left = re.sub(r"\s+", "", m.group(1)); right = re.sub(r"\s+", "", m.group(2)); suffix = re.sub(r"\s+", "", m.group(3) or "")
        value = f"{left}-{right}" + (f"-{suffix}" if suffix else "")
        if re.fullmatch(r"\d{1,2}-\d{3,7}(?:-\d{1,2})?", value):
            return value
    first = head[:220]
    m = re.search(r"(?:🔤\s*){3,6}((?:\d\s*){3,7}(?:-\s*(?:\d\s*){1,2})?)", first)
    if m:
        value = _collapse_candidate(m.group(1))
        if value:
            return value
    m = re.search(r"(?<!\d)(\d{3,7}(?:-\d{1,2})?)(?!\d)", head[:180])
    if m and any(x in head[:180].lower() for x in ("лот", "lot", "🔤")):
        return m.group(1)
    return ""


def _valid_existing_lot(value: str) -> bool:
    s = str(value or "").strip()
    return bool(s and len(re.sub(r"\D", "", s)) >= 3)


def apply(catalog):
    original_extract = catalog.extract_lot_id
    original_record = catalog._record
    original_canonical = catalog.canonical

    def robust(text):
        raw = text or ""
        norm = catalog._digits(raw)
        found = _robust_from_normalized(norm)
        if found:
            return found
        return original_extract(raw)

    def stable_canonical(rec, source=""):
        # A confirmed lot_id already stored against a Telegram message is authoritative.
        # Never let a reformatted/custom-emoji source text collapse it to 0/1.
        existing = str((rec or {}).get("lot_id") or "").strip()
        out = original_canonical(rec, source)
        if _valid_existing_lot(existing):
            out["lot_id"] = existing
        return out

    def stable_record(p, old=None):
        rec = original_record(p, old)
        # telegram_message_id is the stable identity. Once its lot_id has been
        # repaired/confirmed, AI or a reformatted post may not replace it.
        if old and _valid_existing_lot(old.get("lot_id")):
            rec["lot_id"] = str(old.get("lot_id")).strip()
        return rec

    catalog.extract_lot_id = robust
    catalog.canonical = stable_canonical
    catalog._record = stable_record
    log.info("Robust emoji lot parser + immutable canonical/record lot IDs installed")


def _original_backup_by_mid(catalog):
    out = {}
    try:
        sh = catalog._client().open_by_key(catalog.SHEET_ID)
        ws = sh.worksheet("PostBackup")
        vals = ws.get_all_values()
        if not vals:
            return out
        h = vals[0]
        mid_i = h.index("message_id") if "message_id" in h else 0
        text_i = h.index("original_text") if "original_text" in h else 3
        for row in vals[1:]:
            row = row + [""] * max(0, len(h)-len(row))
            mid = str(row[mid_i] or "").strip(); text = str(row[text_i] or "")
            if mid.isdigit() and text and mid not in out:
                out[mid] = text
    except Exception:
        log.exception("Could not read original PostBackup texts")
    return out


def authoritative_lots_by_mid(catalog):
    """Return message_id -> lot_id parsed only from the first/original PostBackup text."""
    out = {}
    for mid, text in _original_backup_by_mid(catalog).items():
        try:
            lot = catalog.extract_lot_id(text)
        except Exception:
            lot = ""
        if _valid_existing_lot(lot):
            out[mid] = str(lot).strip()
    return out


def repair_sheet(catalog):
    ws = catalog.ensure_lots_sheet(); vals = ws.get_all_values()
    if len(vals) <= 1:
        return {"rows": 0, "changed": 0}
    headers = vals[0]
    try:
        lot_i = headers.index("lot_id"); src_i = headers.index("исходный_текст"); mid_i = headers.index("telegram_message_id")
    except ValueError:
        return {"rows": len(vals)-1, "changed": 0, "error": "required columns missing"}
    originals = _original_backup_by_mid(catalog); new_lots = []; changed = []
    for rowno, row in enumerate(vals[1:], start=2):
        row = row + [""] * max(0, len(headers)-len(row))
        old = str(row[lot_i] or "").strip(); mid = str(row[mid_i] or "").strip(); current_src = str(row[src_i] or "")
        authority_src = originals.get(mid) or current_src
        found = catalog.extract_lot_id(authority_src)
        if found and found != old and len(re.sub(r"\D", "", found)) >= 3:
            new_lots.append([found]); changed.append({"row": rowno, "old": old, "new": found, "mid": mid, "from_backup": mid in originals})
        else:
            new_lots.append([old])
    if changed:
        ws.update(f"A2:A{len(vals)}", new_lots, value_input_option="RAW")
        try: catalog._invalidate()
        except Exception: pass
    log.info("Lot ID repair rows=%s changed=%s samples=%s", len(vals)-1, len(changed), changed[:25])
    return {"rows": len(vals)-1, "changed": len(changed), "samples": changed[:25]}

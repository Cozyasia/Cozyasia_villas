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
    if not re.fullmatch(r"\d{3,7}|\d{1,2}-\d{3,7}(?:-\d{1,2})?", s):
        return ""
    return s


def _robust_from_normalized(norm: str) -> str:
    # 1) Explicit LOT marker, allowing every digit to be separated by whitespace/newlines.
    head = (norm or "")[:700]
    marker = re.search(r"(?is)(?:\bлот\b|\blot\b)\s*(?:№|#|no\.?)?\s*[:\-]?\s*", head)
    if marker:
        tail = head[marker.end():marker.end()+80]
        m = re.match(r"((?:\d\s*){3,7}|(?:\d\s*){1,2}-\s*(?:\d\s*){3,7}(?:-\s*(?:\d\s*){1,2})?)", tail)
        if m:
            value = _collapse_candidate(m.group(1))
            if value:
                return value

    # 2) Old displayed family like 01 - 1060, even if marker was replaced by a custom emoji.
    m = re.search(r"(?<!\d)((?:\d\s*){1,2})-\s*((?:\d\s*){3,7})(?:-\s*((?:\d\s*){1,2}))?", head)
    if m:
        left = re.sub(r"\s+", "", m.group(1))
        right = re.sub(r"\s+", "", m.group(2))
        suffix = re.sub(r"\s+", "", m.group(3) or "")
        value = f"{left}-{right}" + (f"-{suffix}" if suffix else "")
        if re.fullmatch(r"\d{1,2}-\d{3,7}(?:-\d{1,2})?", value):
            return value

    # 3) Current Premium template: leading custom-letter fallbacks then spaced digits.
    first = head[:180]
    m = re.search(r"(?:🔤\s*){3,6}((?:\d\s*){3,7})", first)
    if m:
        value = _collapse_candidate(m.group(1))
        if value:
            return value

    # 4) A compact number near the start, only when clearly adjacent to lot-like decoration.
    m = re.search(r"(?<!\d)(\d{3,7})(?!\d)", head[:180])
    if m and any(x in head[:180].lower() for x in ("лот", "lot", "🔤")):
        return m.group(1)
    return ""


def apply(catalog):
    original = catalog.extract_lot_id

    def robust(text):
        raw = text or ""
        norm = catalog._digits(raw)
        found = _robust_from_normalized(norm)
        if found:
            return found
        return original(raw)

    catalog.extract_lot_id = robust
    log.info("Robust emoji lot parser installed")


def repair_sheet(catalog):
    ws = catalog.ensure_lots_sheet()
    vals = ws.get_all_values()
    if len(vals) <= 1:
        return {"rows": 0, "changed": 0}
    headers = vals[0]
    try:
        lot_i = headers.index("lot_id")
        src_i = headers.index("исходный_текст")
    except ValueError:
        return {"rows": len(vals)-1, "changed": 0, "error": "required columns missing"}

    new_lots = []
    changed = []
    for rowno, row in enumerate(vals[1:], start=2):
        row = row + [""] * max(0, len(headers)-len(row))
        old = str(row[lot_i] or "").strip()
        src = str(row[src_i] or "")
        found = catalog.extract_lot_id(src)
        # Only replace when the source supplies a trustworthy multi-character ID.
        if found and found != old and (len(re.sub(r"\D", "", found)) >= 3):
            new_lots.append([found])
            changed.append({"row": rowno, "old": old, "new": found, "mid": row[headers.index("telegram_message_id")] if "telegram_message_id" in headers else ""})
        else:
            new_lots.append([old])

    if changed:
        ws.update(f"A2:A{len(vals)}", new_lots, value_input_option="RAW")
        try:
            catalog._invalidate()
        except Exception:
            pass
    log.info("Lot ID repair rows=%s changed=%s samples=%s", len(vals)-1, len(changed), changed[:20])
    return {"rows": len(vals)-1, "changed": len(changed), "samples": changed[:20]}

# -*- coding: utf-8 -*-
"""Header-only lot parser guard.

Premium posts contain many numbers (prices, dates, distances). If the visual
header uses Custom Emoji, a fallback parser must never choose a body number such
as the year 2026 as the lot ID.
"""
from __future__ import annotations

import logging

import publication_safety

log = logging.getLogger("lot-parser-safety")


def apply(catalog):
    previous = catalog.extract_lot_id

    def safe_extract(text):
        raw = text or ""
        header_lot = publication_safety.lot_from_header_text(raw)
        if header_lot:
            return header_lot

        # Premium/custom-emoji posts are deliberately header-only. If their
        # header cannot be decoded, return unknown instead of guessing from a
        # date, price or distance later in the caption.
        header_raw = "\n".join(raw.splitlines()[:12])
        if any(marker in header_raw for marker in ("🔤", "\u20e3", "➖")):
            return ""
        return previous(raw)

    catalog.extract_lot_id = safe_extract
    log.info("Header-only Premium lot parser guard installed")

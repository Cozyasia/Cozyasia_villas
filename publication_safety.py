# -*- coding: utf-8 -*-
"""Safety checks for Cozy Asia channel publications.

Rules enforced here:
- lot number is read from the live Telegram header, never from dates/body text;
- the next lot is checked independently for each channel;
- Premium custom emoji + deep links are validated before any send/edit;
- duplicate checks use the live channel before publication.
"""
from __future__ import annotations

import re
import unicodedata
from types import SimpleNamespace

import post_layout_v6_premium as premium


def _u16_len(text: str) -> int:
    return len((text or "").encode("utf-16-le")) // 2


def _digits(text: str) -> str:
    s = (text or "").replace("\ufe0f", "").replace("\u20e3", "")
    s = s.replace("➖", "-").replace("–", "-").replace("—", "-").replace("−", "-")
    s = unicodedata.normalize("NFKC", s)
    out = []
    for ch in s:
        try:
            out.append(str(int(unicodedata.digit(ch))))
        except Exception:
            out.append(ch)
    return "".join(out)


def lot_from_header_text(text: str) -> str:
    """Parse a lot only from the header area; never fall through to dates/body."""
    lines = [x.strip() for x in _digits(text).splitlines() if x.strip()]
    if not lines:
        return ""
    header_lines = []
    for line in lines[:12]:
        low = line.lower()
        if "описание" in low or "район:" in low or "условия аренды" in low:
            break
        header_lines.append(line)
    header = "\n".join(header_lines)
    m = re.search(r"(?i)(?:лот|lot)\s*(?:№|#|no\.?)?\s*[:\-]?\s*(\d{3,7})", header)
    if m:
        return m.group(1).lstrip("0") or "0"
    # Premium fallback: 🔤🔤🔤 🔤 1️⃣1️⃣8️⃣3️⃣
    for line in header_lines[:4]:
        raw_line = line
        if "🔤" not in raw_line and not re.search(r"\d\ufe0f?\u20e3", raw_line):
            continue
        nums = re.findall(r"(?<!\d)(\d{3,7})(?!\d)", raw_line)
        if nums:
            return nums[0].lstrip("0") or "0"
    # Older Premium layout can put one digit on each line.
    run = []
    for line in header_lines[:12]:
        if re.fullmatch(r"\d", line):
            run.append(line)
            if len(run) > 7:
                run = run[-7:]
        elif run:
            break
    if 3 <= len(run) <= 7:
        return "".join(run).lstrip("0") or "0"
    return ""


def lot_from_message(msg) -> str:
    """Prefer Custom Emoji document IDs from the first line, then safe header text."""
    text = getattr(msg, "message", None) or ""
    entities = list(getattr(msg, "entities", None) or [])
    first_nl = text.find("\n")
    top = text if first_nl < 0 else text[:first_nl]
    top_u16 = _u16_len(top)
    inverse = {int(v): str(k) for k, v in premium.DIGIT_IDS.items() if str(k).isdigit()}
    decoded = []
    for ent in sorted(entities, key=lambda e: int(getattr(e, "offset", 0))):
        if type(ent).__name__ != "MessageEntityCustomEmoji":
            continue
        if int(getattr(ent, "offset", 0)) >= top_u16:
            continue
        digit = inverse.get(int(getattr(ent, "document_id", 0)))
        if digit is not None:
            decoded.append(digit)
    if 3 <= len(decoded) <= 7:
        return "".join(decoded).lstrip("0") or "0"
    return lot_from_header_text(text)


def _valid_sequence_lot(lot: str) -> bool:
    if not re.fullmatch(r"\d{3,7}", str(lot or "")):
        return False
    n = int(lot)
    # A four-digit year is never accepted as an inferred Cozy Asia lot.
    if 2000 <= n <= 2099:
        return False
    return True


async def latest_numeric_lot(client, channel, *, exclude_ids=None, limit: int = 120) -> str:
    excluded = {int(x) for x in (exclude_ids or set())}
    async for msg in client.iter_messages(channel, limit=limit):
        if int(getattr(msg, "id", 0) or 0) in excluded:
            continue
        lot = lot_from_message(msg)
        if _valid_sequence_lot(lot):
            return lot
    return ""


async def assert_next_lot(client, channel, requested_lot: str, *, exclude_ids=None) -> dict:
    requested = str(requested_lot or "").strip()
    if not requested.isdigit():
        raise RuntimeError(f"Sequential lot must be numeric, got {requested!r}")
    previous = await latest_numeric_lot(client, channel, exclude_ids=exclude_ids)
    if not previous:
        raise RuntimeError("Could not determine previous live lot from Telegram")
    expected = str(int(previous) + 1)
    if requested != expected:
        raise RuntimeError(f"Lot preflight failed: previous={previous}, expected={expected}, requested={requested}")
    return {"previous": previous, "expected": expected, "requested": requested}


def validate_premium_caption(text: str, entities, lot: str) -> dict:
    lot = str(lot or "").strip()
    if not lot.isdigit():
        raise RuntimeError("Premium preflight requires a numeric lot")
    fake = SimpleNamespace(message=text, entities=list(entities or []))
    decoded = lot_from_message(fake)
    if decoded != lot:
        raise RuntimeError(f"Premium header mismatch: decoded={decoded!r}, expected={lot!r}")

    custom = [e for e in (entities or []) if type(e).__name__ == "MessageEntityCustomEmoji"]
    minimum = 21 + len(lot)  # LOT letters+№ + digits + CTA letters + bubble/arrows
    if len(custom) < minimum:
        raise RuntimeError(f"Premium preflight failed: only {len(custom)} custom emoji, need >= {minimum}")

    urls = [str(getattr(e, "url", "") or "") for e in (entities or [])]
    if not any(f"start=rent_{lot}" in u for u in urls):
        raise RuntimeError(f"Deep link rent_{lot} is missing")
    if not any("start=search" in u for u in urls):
        raise RuntimeError("Search deep link is missing")

    cta_pos = text.find("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ")
    tag_pos = text.find("#АрендаСамуи")
    if cta_pos < 0 or tag_pos < 0 or tag_pos < cta_pos:
        raise RuntimeError("Hashtags must be below both CTA blocks")
    return {"lot": lot, "custom_emoji": len(custom), "deep_links": "ok", "hashtags": "ok"}


async def find_duplicate_listing(client, channel, signature_terms, *, exclude_ids=None, limit: int = 120):
    excluded = {int(x) for x in (exclude_ids or set())}
    terms = [str(x).lower() for x in signature_terms if str(x).strip()]
    async for msg in client.iter_messages(channel, limit=limit):
        if int(getattr(msg, "id", 0) or 0) in excluded:
            continue
        text = (getattr(msg, "message", None) or "").lower()
        if text and all(term in text for term in terms):
            return msg
    return None

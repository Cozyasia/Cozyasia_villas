# -*- coding: utf-8 -*-
"""Permanent Cozy Asia publication routing and layout policy.

Channel routing is strict:
- @samuirental -> @cozy_asia_bot
- @arenda_vill_samui -> @Cozyasia_villa_bot

Both the lot application CTA and the final search CTA must use the channel's
assigned bot.  New listing captions must also follow the manually approved
Telegram layout: quoted description, application CTA, blank spacing, operator,
final search CTA, then hashtags.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

CHANNEL_BOTS = {
    "samuirental": "cozy_asia_bot",
    "arenda_vill_samui": "Cozyasia_villa_bot",
}


def normalize_channel(channel: str) -> str:
    return str(channel or "").strip().lstrip("@").lower()


def bot_for_channel(channel: str) -> str:
    key = normalize_channel(channel)
    if key not in CHANNEL_BOTS:
        raise RuntimeError(f"No Cozy Asia publication policy for channel @{key}")
    return CHANNEL_BOTS[key]


def bot_url(channel: str, payload: str) -> str:
    return f"https://t.me/{bot_for_channel(channel)}?start={payload}"


def _py_from_u16(text: str, offset: int) -> int:
    used = 0
    for i, ch in enumerate(text):
        if used >= offset:
            return i
        used += len(ch.encode("utf-16-le")) // 2
    return len(text)


def _entity_text(text: str, ent) -> str:
    start = _py_from_u16(text, int(getattr(ent, "offset", 0) or 0))
    end = _py_from_u16(
        text,
        int(getattr(ent, "offset", 0) or 0) + int(getattr(ent, "length", 0) or 0),
    )
    return text[start:end]


def _bot_path(url: str) -> str:
    try:
        parts = urlsplit(str(url or ""))
    except Exception:
        return ""
    if (parts.netloc or "").lower() not in {
        "t.me", "telegram.me", "www.t.me", "www.telegram.me"
    }:
        return ""
    return (parts.path or "").strip("/")


def validate_listing_caption(text: str, entities, lot: str, channel: str) -> dict:
    text = str(text or "")
    lot = str(lot or "").strip()
    expected_bot = bot_for_channel(channel)
    rent = []
    search = []
    blockquotes = []

    for ent in entities or []:
        if type(ent).__name__ == "MessageEntityBlockquote":
            blockquotes.append(ent)
        url = str(getattr(ent, "url", "") or "")
        if not url:
            continue
        if re.search(r"(?:[?&])start=rent_[^&#]+", url, re.I):
            rent.append((ent, url))
        if re.search(r"(?:[?&])start=search(?:[&#]|$)", url, re.I):
            search.append((ent, url))

    expected_rent = f"rent_{lot}"
    if not any(
        _bot_path(url).lower() == expected_bot.lower()
        and re.search(
            rf"(?:[?&])start={re.escape(expected_rent)}(?:[&#]|$)", url, re.I
        )
        for _, url in rent
    ):
        raise RuntimeError(
            f"Expected @{expected_bot} deep link start={expected_rent} is missing"
        )
    if not any(_bot_path(url).lower() == expected_bot.lower() for _, url in search):
        raise RuntimeError(f"Expected @{expected_bot} deep link start=search is missing")

    wrong = [
        url
        for _, url in rent + search
        if _bot_path(url) and _bot_path(url).lower() != expected_bot.lower()
    ]
    if wrong:
        raise RuntimeError(
            f"Wrong bot for @{normalize_channel(channel)}; expected @{expected_bot}: {wrong[0]}"
        )

    if not any("ЖМИ ЗДЕСЬ" in _entity_text(text, ent) for ent, _ in rent):
        raise RuntimeError("Per-lot rent deep link must be attached to ЖМИ ЗДЕСЬ")
    if not any("НАПИСАТЬ БОТУ" in _entity_text(text, ent) for ent, _ in search):
        raise RuntimeError("Search deep link must be attached to НАПИСАТЬ БОТУ")

    desc_head = text.find("ОПИСАНИЕ")
    if desc_head < 0:
        raise RuntimeError("Description heading is missing")
    if not blockquotes:
        raise RuntimeError("Description must use a Telegram blockquote")
    valid_quote = False
    for ent in blockquotes:
        quoted = _entity_text(text, ent).strip()
        quote_start = _py_from_u16(text, int(getattr(ent, "offset", 0) or 0))
        if quoted and quote_start > desc_head:
            valid_quote = True
            break
    if not valid_quote:
        raise RuntimeError("Description blockquote must follow ОПИСАНИЕ")

    cta_pos = text.find("ЖМИ ЗДЕСЬ")
    operator_pos = text.find("Оператор: @cozy_asia")
    search_pos = text.find("ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ")
    hashtag_pos = text.find("#")
    if min(cta_pos, operator_pos, search_pos, hashtag_pos) < 0 or not (
        cta_pos < operator_pos < search_pos < hashtag_pos
    ):
        raise RuntimeError("CTA/operator/search/hashtags order is invalid")

    between = text[cta_pos:operator_pos]
    after_cta_line = between.split("\n", 1)[1] if "\n" in between else ""
    blank_prefix = 0
    for line in after_cta_line.splitlines():
        if line.strip() == "":
            blank_prefix += 1
        else:
            break
    if blank_prefix < 2:
        raise RuntimeError(
            "At least two blank lines are required between ЖМИ ЗДЕСЬ and operator"
        )

    if "\n\n#" not in text[search_pos:]:
        raise RuntimeError("A blank line is required before hashtags")

    return {
        "channel": normalize_channel(channel),
        "bot": expected_bot,
        "lot": lot,
        "description": "blockquote",
        "spacing": "current_manual_standard",
    }

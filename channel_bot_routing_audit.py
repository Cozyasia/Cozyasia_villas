# -*- coding: utf-8 -*-
"""Audit/migrate Telegram bot routing in Cozy Asia property channels.

This maintenance tool is intentionally gated from ``main.py``. It scans the
complete history of both property channels. In migrate mode it changes only
MessageEntityTextUrl targets: the visible text, blockquotes, spacing, bold,
Premium custom emoji and every other entity are preserved.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import re
import unicodedata
from collections import Counter

log = logging.getLogger("channel-bot-routing")

CHANNELS = {
    "samuirental": "cozy_asia_bot",
    "arenda_vill_samui": "Cozyasia_villa_bot",
}


def enabled() -> bool:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "").strip().lower() in {"audit", "migrate"}


def mode() -> str:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "audit").strip().lower()


def _bot_from_url(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?t\.me/([A-Za-z0-9_]+)", url or "", re.I)
    return m.group(1) if m else ""


def _rewrite_bot(url: str, expected_bot: str) -> str:
    return re.sub(
        r"(https?://(?:www\.)?t\.me/)([A-Za-z0-9_]+)",
        lambda m: m.group(1) + expected_bot,
        url,
        count=1,
        flags=re.I,
    )


def _rewrite_rent_start(url: str, lot: str) -> str:
    return re.sub(
        r"([?&]start=)rent_[^&#]+",
        lambda m: m.group(1) + "rent_" + lot,
        url,
        count=1,
        flags=re.I,
    )


def _is_bot_url(url: str) -> bool:
    bot = _bot_from_url(url)
    return bool(bot and bot.lower().endswith("bot"))


def _normalize_header_line(line: str) -> str:
    """Normalize only a visible Telegram header line, never the listing body."""
    value = str(line or "").replace("\ufe0f", "").replace("\u20e3", "")
    value = value.replace("➖", "-").replace("–", "-").replace("—", "-").replace("−", "-")
    value = unicodedata.normalize("NFKC", value)
    chars = []
    for ch in value:
        try:
            chars.append(str(int(unicodedata.digit(ch))))
        except Exception:
            chars.append(ch)
    return "".join(chars)


def _visible_lot_from_text(text: str) -> str:
    """Read a lot only from the first visible line.

    This deliberately refuses to search the body, where years, prices, areas and
    utility rates previously produced false `rent_<lot>` mismatch reports.
    Legacy prefixed lots such as ``01-1060`` are preserved.
    """
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    raw = lines[0]
    line = _normalize_header_line(raw)

    marker = re.search(r"(?i)\b(?:лот|lot)\b\s*(?:№|#|no\.?)?\s*[:\-]?\s*", line)
    search_from = marker.end() if marker else 0

    # Without an explicit LOT marker, accept a number only from our stylized
    # Cozy Asia header. This prevents a title like "Villa 2026" becoming a lot.
    if marker is None and not any(token in raw for token in ("🔤", "\u20e3", "➖")):
        return ""

    tail = line[search_from:]
    match = re.search(
        r"(?<!\d)(\d{1,2}-\d{1,7}(?:-\d{1,2})?|\d{3,7}(?:-\d{1,2})?)(?!\d)",
        tail,
    )
    if not match:
        return ""
    candidate = match.group(1)

    # A Premium header can expose a literal dash while the suffix itself is a
    # custom emoji placeholder. Do not guess in that ambiguous case.
    remainder = tail[match.end():]
    if remainder.startswith("-") and not re.match(r"-\d", remainder):
        return ""
    return candidate


def _trusted_lot_from_message(msg) -> str:
    """Return a lot only when the message header itself carries one."""
    text = getattr(msg, "message", None) or ""
    visible = _visible_lot_from_text(text)
    if visible:
        return visible

    # For Premium headers with a hidden custom-emoji suffix, the text can be
    # ambiguous (e.g. visible ``1168-``). publication_safety decodes known digit
    # document IDs, but we invoke it only when the FIRST line is visibly a Cozy
    # Asia lot header so body numbers can never leak into the result.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    first = lines[0]
    normalized = _normalize_header_line(first)
    header_like = bool(
        re.search(r"(?i)\b(?:лот|lot)\b", normalized)
        or any(token in first for token in ("🔤", "\u20e3", "➖"))
    )
    if not header_like:
        return ""
    try:
        import publication_safety

        decoded = str(publication_safety.lot_from_message(msg) or "").strip()
        if re.fullmatch(r"(?:\d{1,2}-)?\d{1,7}(?:-\d{1,2})?", decoded):
            return decoded
    except Exception:
        pass
    return ""


def _sample(msg) -> dict:
    text = getattr(msg, "message", None) or ""
    entities = list(getattr(msg, "entities", None) or [])
    return {
        "id": int(getattr(msg, "id", 0) or 0),
        "text": text,
        "entities": [
            {
                "type": type(e).__name__,
                "offset": int(getattr(e, "offset", 0) or 0),
                "length": int(getattr(e, "length", 0) or 0),
                "url": str(getattr(e, "url", "") or ""),
                "collapsed": getattr(e, "collapsed", None),
            }
            for e in entities
        ],
    }


async def _audit_channel(client, catalog, channel: str, expected_bot: str, do_migrate: bool) -> dict:
    total = 0
    text_messages = 0
    bot_counter = Counter()
    starts = Counter()
    wrong = []
    deep_link_mismatches = []
    plain_url_wrong = []
    migrated = []
    failed = []
    latest_samples = []

    async for msg in client.iter_messages(channel, limit=None):
        total += 1
        text = getattr(msg, "message", None) or ""
        if not text:
            continue
        text_messages += 1
        entities = list(getattr(msg, "entities", None) or [])
        if len(latest_samples) < 12:
            latest_samples.append(_sample(msg))

        lot = _trusted_lot_from_message(msg)

        changed = False
        new_entities = []
        for ent in entities:
            cloned = copy.copy(ent)
            url = str(getattr(ent, "url", "") or "")
            if url and _is_bot_url(url):
                bot = _bot_from_url(url)
                bot_counter[bot] += 1
                sm = re.search(r"[?&]start=([^&#]+)", url)
                start_value = sm.group(1) if sm else ""
                if start_value:
                    starts[start_value] += 1

                if bot.lower() != expected_bot.lower():
                    wrong.append({
                        "id": int(msg.id),
                        "url": url,
                        "bot": bot,
                        "type": type(ent).__name__,
                        "text_head": text[:160].replace("\n", " | "),
                    })
                    if do_migrate and type(ent).__name__ == "MessageEntityTextUrl":
                        cloned.url = _rewrite_bot(url, expected_bot)
                        changed = True

                if lot and start_value.lower().startswith("rent_"):
                    expected_start = "rent_" + lot
                    if start_value.lower() != expected_start.lower():
                        deep_link_mismatches.append({
                            "id": int(msg.id),
                            "lot": lot,
                            "start": start_value,
                            "expected_start": expected_start,
                            "url": url,
                        })
                        if do_migrate and type(ent).__name__ == "MessageEntityTextUrl":
                            cloned.url = _rewrite_rent_start(str(getattr(cloned, "url", "") or url), lot)
                            changed = True
            new_entities.append(cloned)

        # Detect plain URL text for completeness. We do not auto-rewrite it:
        # changing visible text would require offset surgery and could damage
        # user-edited formatting.
        for url in re.findall(r"https?://(?:www\.)?t\.me/[A-Za-z0-9_]+(?:\?[^\s<>()]+)?", text):
            if not _is_bot_url(url):
                continue
            bot = _bot_from_url(url)
            if bot.lower() != expected_bot.lower():
                plain_url_wrong.append({
                    "id": int(msg.id),
                    "url": url,
                    "bot": bot,
                    "text_head": text[:160].replace("\n", " | "),
                })

        if changed:
            try:
                await client.edit_message(channel, msg.id, text, formatting_entities=new_entities)
                migrated.append(int(msg.id))
                log.info("routing migration edited %s/%s", channel, msg.id)
                await asyncio.sleep(0.4)
            except Exception as exc:
                failed.append({
                    "id": int(msg.id),
                    "error": f"{type(exc).__name__}: {exc}",
                })
                log.warning("routing migration could not edit %s/%s: %s", channel, msg.id, exc)

    return {
        "expected_bot": expected_bot,
        "total_messages": total,
        "text_messages": text_messages,
        "bot_counter": dict(bot_counter),
        "start_params_top": starts.most_common(30),
        "wrong_entity_count": len(wrong),
        "wrong_entity_examples": wrong[:200],
        "deep_link_mismatch_count": len(deep_link_mismatches),
        "deep_link_mismatch_examples": deep_link_mismatches[:200],
        "plain_url_wrong_count": len(plain_url_wrong),
        "plain_url_wrong_examples": plain_url_wrong[:100],
        "migrated_count": len(migrated),
        "migrated_message_ids": migrated[:500],
        "failed_count": len(failed),
        "failed": failed[:200],
        "latest_samples": latest_samples,
    }


async def run() -> dict:
    import cozy_catalog as catalog
    import mtproto_user_client as mt

    client = await mt._new_client(catalog)
    if client is None:
        raise RuntimeError("MTProto session unavailable")
    do_migrate = mode() == "migrate"
    result = {"mode": mode(), "channels": {}}
    try:
        for channel, expected in CHANNELS.items():
            result["channels"][channel] = await _audit_channel(
                client, catalog, channel, expected, do_migrate
            )
    finally:
        await client.disconnect()
    return result


def run_service_mode() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    result = asyncio.run(run())
    print("CHANNEL_BOT_ROUTING_RESULT=" + json.dumps(result, ensure_ascii=False))

# -*- coding: utf-8 -*-
"""Audit/migrate Telegram bot routing in Cozy Asia property channels.

This maintenance tool is intentionally gated from ``main.py``. It scans the
complete history of both property channels. In migrate mode it changes only
MessageEntityTextUrl targets: the visible text, blockquotes, spacing, bold,
Premium custom emoji and every other entity are preserved.

Migration can be restricted to confirmed message IDs with
``CHANNEL_BOT_ROUTING_TARGETS``. Telegram FloodWait is honored and retried on
the same message before moving on.
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

from telethon.errors import FloodWaitError, MessageIdInvalidError

log = logging.getLogger("channel-bot-routing")
_sleep = asyncio.sleep

CHANNELS = {
    "samuirental": "cozy_asia_bot",
    "arenda_vill_samui": "Cozyasia_villa_bot",
}


def enabled() -> bool:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "").strip().lower() in {"audit", "migrate"}


def mode() -> str:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "audit").strip().lower()


def _target_ids_for(channel: str):
    """Return confirmed migrate targets for one channel, or None for all.

    Malformed/non-object configuration is fail-closed: migration never silently
    broadens from a targeted repair to the whole history.
    """
    raw = os.getenv("CHANNEL_BOT_ROUTING_TARGETS", "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError("CHANNEL_BOT_ROUTING_TARGETS must be valid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("CHANNEL_BOT_ROUTING_TARGETS must be a JSON object")
    values = data.get(channel, [])
    if not isinstance(values, list):
        raise RuntimeError(f"CHANNEL_BOT_ROUTING_TARGETS[{channel!r}] must be a list")
    try:
        return {int(x) for x in values}
    except Exception as exc:
        raise RuntimeError(f"Invalid message id in CHANNEL_BOT_ROUTING_TARGETS[{channel!r}]") from exc


def _group_caption_candidates(messages, grouped_id, original_id):
    """Find same-album caption siblings that contain URL entities."""
    result = []
    for msg in messages or []:
        if int(getattr(msg, "id", 0) or 0) == int(original_id):
            continue
        if getattr(msg, "grouped_id", None) != grouped_id:
            continue
        if not (getattr(msg, "message", None) or ""):
            continue
        entities = list(getattr(msg, "entities", None) or [])
        if not any(str(getattr(ent, "url", "") or "") for ent in entities):
            continue
        result.append(msg)
    return result


async def _edit_with_retry(client, channel, message_id, text, entities, max_attempts: int = 3):
    """Edit one exact message, respecting Telegram FloodWait and retrying it."""
    for attempt in range(max_attempts):
        try:
            return await client.edit_message(
                channel,
                int(message_id),
                text,
                formatting_entities=list(entities or []),
            )
        except FloodWaitError as exc:
            if attempt + 1 >= max_attempts:
                raise
            wait_seconds = int(getattr(exc, "seconds", 0) or 0) + 3
            log.warning(
                "Telegram FloodWait on %s/%s: waiting %ss before retry %s/%s",
                channel,
                message_id,
                wait_seconds,
                attempt + 2,
                max_attempts,
            )
            await _sleep(wait_seconds)
    raise RuntimeError("unreachable edit retry state")


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
        "grouped_id": getattr(msg, "grouped_id", None),
        "sender_id": getattr(msg, "sender_id", None),
        "out": getattr(msg, "out", None),
        "post_author": getattr(msg, "post_author", None),
        "media_type": type(getattr(msg, "media", None)).__name__ if getattr(msg, "media", None) else None,
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


def _entity_urls(entities):
    return [str(getattr(e, "url", "") or "") for e in (entities or []) if str(getattr(e, "url", "") or "")]


def _rewritten_entities_for_message(msg, expected_bot: str):
    """Recompute safe URL-only edits for one message."""
    text = getattr(msg, "message", None) or ""
    lot = _trusted_lot_from_message(msg)
    changed = False
    new_entities = []
    for ent in list(getattr(msg, "entities", None) or []):
        cloned = copy.copy(ent)
        url = str(getattr(ent, "url", "") or "")
        if url and _is_bot_url(url) and type(ent).__name__ == "MessageEntityTextUrl":
            bot = _bot_from_url(url)
            if bot.lower() != expected_bot.lower():
                cloned.url = _rewrite_bot(url, expected_bot)
                changed = True
            sm = re.search(r"[?&]start=([^&#]+)", url)
            start_value = sm.group(1) if sm else ""
            if lot and start_value.lower().startswith("rent_") and start_value.lower() != ("rent_" + lot).lower():
                cloned.url = _rewrite_rent_start(str(getattr(cloned, "url", "") or url), lot)
                changed = True
        new_entities.append(cloned)
    return text, lot, new_entities, changed


def _verify_routes(msg, expected_bot: str):
    lot = _trusted_lot_from_message(msg)
    bad = []
    for url in _entity_urls(getattr(msg, "entities", None) or []):
        if not _is_bot_url(url):
            continue
        bot = _bot_from_url(url)
        if bot.lower() != expected_bot.lower():
            bad.append({"kind": "bot", "url": url, "expected_bot": expected_bot})
        sm = re.search(r"[?&]start=([^&#]+)", url)
        start = sm.group(1) if sm else ""
        if lot and start.lower().startswith("rent_") and start.lower() != ("rent_" + lot).lower():
            bad.append({"kind": "rent", "url": url, "expected_start": "rent_" + lot})
    return bad


async def _try_album_caption_fallback(client, channel: str, msg, expected_bot: str):
    """On MessageIdInvalid, inspect only same grouped media and edit a real caption sibling."""
    grouped_id = getattr(msg, "grouped_id", None)
    if not grouped_id:
        return None
    ids = list(range(max(1, int(msg.id) - 12), int(msg.id) + 13))
    nearby = await client.get_messages(channel, ids=ids)
    candidates = _group_caption_candidates(nearby, grouped_id, int(msg.id))
    for candidate in candidates:
        text, _lot, new_entities, changed = _rewritten_entities_for_message(candidate, expected_bot)
        if not changed:
            continue
        try:
            await _edit_with_retry(client, channel, int(candidate.id), text, new_entities)
            verify = await client.get_messages(channel, ids=int(candidate.id))
            if _verify_routes(verify, expected_bot):
                continue
            return int(candidate.id)
        except MessageIdInvalidError:
            continue
    return None


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
    uneditable = []
    latest_samples = []
    targets = _target_ids_for(channel)

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
        can_migrate = do_migrate and (targets is None or int(msg.id) in targets)

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
                    if can_migrate and type(ent).__name__ == "MessageEntityTextUrl":
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
                        if can_migrate and type(ent).__name__ == "MessageEntityTextUrl":
                            cloned.url = _rewrite_rent_start(str(getattr(cloned, "url", "") or url), lot)
                            changed = True
            new_entities.append(cloned)

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
                await _edit_with_retry(client, channel, int(msg.id), text, new_entities)
                verify = await client.get_messages(channel, ids=int(msg.id))
                bad = _verify_routes(verify, expected_bot)
                if bad:
                    raise RuntimeError(f"Post-edit verification failed: {bad}")
                migrated.append(int(msg.id))
                log.info("routing migration edited and verified %s/%s", channel, msg.id)
                await _sleep(1.25)
            except MessageIdInvalidError as exc:
                diagnostic = _sample(msg)
                diagnostic["error"] = f"{type(exc).__name__}: {exc}"
                log.warning("direct edit invalid for %s/%s; inspecting album metadata=%s", channel, msg.id, diagnostic)
                try:
                    sibling_id = await _try_album_caption_fallback(client, channel, msg, expected_bot)
                except Exception as fallback_exc:
                    diagnostic["fallback_error"] = f"{type(fallback_exc).__name__}: {fallback_exc}"
                    sibling_id = None
                if sibling_id is not None:
                    migrated.append(int(sibling_id))
                    diagnostic["resolved_via_sibling_id"] = int(sibling_id)
                    log.info("routing migration resolved %s/%s via sibling %s", channel, msg.id, sibling_id)
                    await _sleep(1.25)
                else:
                    uneditable.append(diagnostic)
            except Exception as exc:
                failed.append({
                    "id": int(msg.id),
                    "error": f"{type(exc).__name__}: {exc}",
                    "metadata": _sample(msg),
                })
                log.warning("routing migration could not edit %s/%s: %s", channel, msg.id, exc)

    return {
        "expected_bot": expected_bot,
        "targets": sorted(targets) if targets is not None else None,
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
        "uneditable_count": len(uneditable),
        "uneditable": uneditable[:50],
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

# -*- coding: utf-8 -*-
"""Authoritative Cozy Asia bot routing by Telegram channel.

Permanent rule:
- large channel @samuirental -> @cozy_asia_bot for BOTH application and search CTAs;
- small channel @arenda_vill_samui -> @Cozyasia_villa_bot for BOTH application and search CTAs.

The migration edits existing listing messages in place via the authorized Premium
MTProto account and preserves their text, media and formatting entities. Telegram
deep-link destinations are corrected and, where an old listing has no application
or search CTA at all, the missing CTA is appended with the channel's assigned bot.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import re
from urllib.parse import urlsplit, urlunsplit

import publication_safety

log = logging.getLogger("channel-bot-routing")

BIG_CHANNEL = "samuirental"
BIG_BOT = "cozy_asia_bot"
SMALL_CHANNEL = "arenda_vill_samui"
SMALL_BOT = "Cozyasia_villa_bot"
CHANNEL_BOTS = {
    BIG_CHANNEL.lower(): BIG_BOT,
    SMALL_CHANNEL.lower(): SMALL_BOT,
}
KNOWN_BOTS = {BIG_BOT.lower(), SMALL_BOT.lower()}
ENV_FLAG = "FIX_CHANNEL_BOT_ROUTING"


def enabled() -> bool:
    return os.getenv(ENV_FLAG, "0").strip().lower() in {"1", "true", "yes", "on"}


def normalize_channel(channel: str) -> str:
    return str(channel or "").strip().lstrip("@").lower()


def bot_for_channel(channel: str) -> str:
    key = normalize_channel(channel)
    if key not in CHANNEL_BOTS:
        raise RuntimeError(f"No Cozy Asia bot routing rule for channel @{key}")
    return CHANNEL_BOTS[key]


def bot_url(channel: str, payload: str = "") -> str:
    bot = bot_for_channel(channel)
    suffix = f"?start={payload}" if payload else ""
    return f"https://t.me/{bot}{suffix}"


def _rewrite_deep_link(url: str, channel: str) -> tuple[str, bool]:
    raw = str(url or "").strip()
    if not raw:
        return raw, False
    try:
        parts = urlsplit(raw)
    except Exception:
        return raw, False
    host = (parts.netloc or "").lower()
    if host not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
        return raw, False
    query = parts.query or ""
    if not re.search(r"(?:^|&)start=(?:rent(?:_[^&]+)?|search)(?:&|$)", query, flags=re.I):
        return raw, False
    target = bot_for_channel(channel)
    path = "/" + target
    new_url = urlunsplit((parts.scheme or "https", "t.me", path, query, parts.fragment))
    return new_url, new_url != raw


def _deep_link_urls(entities) -> list[str]:
    out = []
    for ent in entities or []:
        url = str(getattr(ent, "url", "") or "")
        if url:
            out.append(url)
    return out


def _route_ok(url: str, channel: str) -> bool:
    raw = str(url or "")
    if not re.search(r"(?:^|[?&])start=(?:rent(?:_[^&]+)?|search)(?:&|$)", raw, flags=re.I):
        return True
    try:
        parts = urlsplit(raw)
    except Exception:
        return False
    if (parts.netloc or "").lower() not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
        return True
    return (parts.path or "").strip("/").lower() == bot_for_channel(channel).lower()


def _has_payload(urls: list[str], prefix: str) -> bool:
    if prefix == "rent":
        return any(re.search(r"(?:^|[?&])start=rent(?:_[^&]+)?(?:&|$)", u, flags=re.I) for u in urls)
    return any(re.search(r"(?:^|[?&])start=search(?:&|$)", u, flags=re.I) for u in urls)


def _rewrite_plain_bot_mentions(text: str, channel: str) -> tuple[str, bool]:
    target = bot_for_channel(channel)
    new_text = str(text or "")
    changed = False
    for old in (BIG_BOT, SMALL_BOT):
        if old.lower() == target.lower():
            continue
        pat = re.compile(r"@" + re.escape(old) + r"\b", flags=re.I)
        newer, n = pat.subn("@" + target, new_text)
        if n:
            new_text, changed = newer, True
    return new_text, changed


def _rewrite_entities(entities, channel: str):
    changed = False
    new_entities = []
    for ent in entities or []:
        cloned = copy.copy(ent)
        if hasattr(cloned, "url"):
            old = str(getattr(cloned, "url", "") or "")
            new, did = _rewrite_deep_link(old, channel)
            if did:
                cloned.url = new
                changed = True
        new_entities.append(cloned)
    return new_entities, changed


def _append_missing_ctas(text: str, entities, channel_name: str, lot: str, is_media: bool):
    """Append only missing application/search CTAs while preserving rich entities."""
    urls = _deep_link_urls(entities)
    missing_rent = not _has_payload(urls, "rent")
    missing_search = not _has_payload(urls, "search")
    if not missing_rent and not missing_search:
        return text, list(entities or []), False

    from telethon.extensions import html as telethon_html
    html_text = telethon_html.unparse(text, list(entities or []))
    additions = []
    if missing_rent:
        rent = bot_url(channel_name, f"rent_{lot}")
        additions.append(
            f'📝 <b>ОСТАВИТЬ ЗАЯВКУ</b> — '
            f'<a href="{rent}"><b>ЖМИ ЗДЕСЬ</b></a>'
        )
    if missing_search:
        search = bot_url(channel_name, "search")
        additions.append(
            f'🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — '
            f'<a href="{search}"><b>НАПИСАТЬ БОТУ</b></a> 🤖'
        )
    html_text = html_text.rstrip() + "\n\n" + "\n".join(additions)
    new_text, new_entities = telethon_html.parse(html_text)
    # These edits are sent through the authorized Premium MTProto account. The
    # two remaining historical media captions are already >1024 characters and
    # valid in Telegram; Premium captions allow up to 2048 characters.
    limit = 2048 if is_media else 4096
    if len(new_text) > limit:
        raise RuntimeError(
            f"Cannot append missing CTAs without exceeding Telegram limit: "
            f"len={len(new_text)} limit={limit} lot={lot}"
        )
    return new_text, new_entities, True


async def _edit_listing(client, channel_name: str, msg, lot: str):
    from telethon.errors import MessageNotModifiedError
    text = getattr(msg, "message", None) or ""
    entities = list(getattr(msg, "entities", None) or [])
    new_text, text_changed = _rewrite_plain_bot_mentions(text, channel_name)
    new_entities, entity_changed = _rewrite_entities(entities, channel_name)

    if text_changed:
        from telethon.extensions import html as telethon_html
        html_text = telethon_html.unparse(text, entities)
        target = bot_for_channel(channel_name)
        for old in (BIG_BOT, SMALL_BOT):
            if old.lower() == target.lower():
                continue
            html_text = re.sub(r"@" + re.escape(old) + r"\b", "@" + target, html_text, flags=re.I)

        def repl_href(m):
            old = m.group(1)
            new, _ = _rewrite_deep_link(old, channel_name)
            return f'href="{new}"'

        html_text = re.sub(r'href="([^"]+)"', repl_href, html_text, flags=re.I)
        new_text, new_entities = telethon_html.parse(html_text)

    new_text, new_entities, cta_changed = _append_missing_ctas(
        new_text,
        new_entities,
        channel_name,
        lot,
        bool(getattr(msg, "media", None)),
    )
    if not text_changed and not entity_changed and not cta_changed:
        return "unchanged"

    try:
        await client.edit_message(
            channel_name,
            int(msg.id),
            new_text,
            formatting_entities=new_entities,
            link_preview=False,
        )
    except MessageNotModifiedError:
        return "unchanged"
    return "edited"


async def _scan_channel(client, channel_name: str) -> dict:
    target_bot = bot_for_channel(channel_name)
    stats = {
        "channel": channel_name,
        "bot": target_bot,
        "messages_scanned": 0,
        "listing_posts": 0,
        "edited": 0,
        "unchanged": 0,
        "failed": 0,
        "missing_rent": [],
        "missing_search": [],
        "wrong_route_remaining": [],
    }
    async for msg in client.iter_messages(channel_name):
        stats["messages_scanned"] += 1
        text = getattr(msg, "message", None) or ""
        if not text:
            continue
        lot = publication_safety.lot_from_message(msg)
        if not lot:
            continue
        stats["listing_posts"] += 1
        try:
            result = await _edit_listing(client, channel_name, msg, lot)
            stats[result] += 1
            if result == "edited":
                await asyncio.sleep(0.38)
            verify = await client.get_messages(channel_name, ids=int(msg.id))
            urls = _deep_link_urls(getattr(verify, "entities", None) or [])
            if not _has_payload(urls, "rent"):
                stats["missing_rent"].append({"message_id": int(msg.id), "lot": lot})
            if not _has_payload(urls, "search"):
                stats["missing_search"].append({"message_id": int(msg.id), "lot": lot})
            bad = [u for u in urls if not _route_ok(u, channel_name)]
            if bad:
                stats["wrong_route_remaining"].append({"message_id": int(msg.id), "lot": lot, "urls": bad})
        except Exception as exc:
            stats["failed"] += 1
            log.exception("Bot-route edit failed @%s mid=%s lot=%s", channel_name, getattr(msg, "id", "?"), lot)
            if stats["failed"] >= 12:
                raise RuntimeError(f"Too many bot-routing failures in @{channel_name}: {stats['failed']}") from exc
    return stats


async def run(catalog) -> dict:
    if not enabled():
        return {"enabled": False}
    client = await __import__("mtproto_user_client")._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        results = []
        for channel in (BIG_CHANNEL, SMALL_CHANNEL):
            stats = await _scan_channel(client, channel)
            results.append(stats)
            log.info("CHANNEL_BOT_ROUTING_CHANNEL_DONE %s", json.dumps(stats, ensure_ascii=False))
        summary = {"enabled": True, "results": results}
        log.info("CHANNEL_BOT_ROUTING_DONE %s", json.dumps(summary, ensure_ascii=False))
        return summary
    finally:
        await client.disconnect()


def apply_to_standardizer(mod, catalog) -> None:
    """Force the catalog standardizer to use the channel's assigned bot, not the editing bot identity."""
    if getattr(mod, "_channel_bot_routing_applied", False):
        return
    original = mod.build_post

    def routed_build_post(row, _bot_username, links=None):
        return original(row, bot_for_channel(catalog.CATALOG_CHANNEL), links)

    mod.build_post = routed_build_post
    mod._channel_bot_routing_applied = True
    log.info(
        "Permanent CTA routing applied: @%s -> @%s",
        catalog.CATALOG_CHANNEL,
        bot_for_channel(catalog.CATALOG_CHANNEL),
    )

# -*- coding: utf-8 -*-
"""One-shot MTProto migration: move hashtag blocks below both CTA blocks.

The migration works directly against Telegram history, so it does not depend on
Google Sheets rows and preserves existing Premium Custom Emoji / link entities.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import os
import re

import mtproto_user_client as mt

log = logging.getLogger("hashtag-reorder")


def enabled() -> bool:
    return os.environ.get("MT_REORDER_HASHTAGS", "").strip().lower() in {"1", "true", "yes", "on"}


def target_channels(catalog) -> list[str]:
    raw = os.environ.get("MT_REORDER_CHANNELS", "arenda_vill_samui,samuirental")
    channels = []
    for item in raw.split(","):
        name = item.strip().lstrip("@")
        if name and name not in channels:
            channels.append(name)
    current = str(getattr(catalog, "CATALOG_CHANNEL", "") or "").strip().lstrip("@")
    if current and current not in channels:
        channels.insert(0, current)
    return channels


def _captured_entities(text: str, entities, start: int, end: int, prefix: str):
    base_u16 = mt._u16_len(text[:start])
    prefix_u16 = mt._u16_len(prefix)
    moved = []
    for ent in entities or []:
        try:
            s = mt._py_from_u16(text, int(ent.offset))
            e = mt._py_from_u16(text, int(ent.offset) + int(ent.length))
        except Exception:
            continue
        if s >= start and e <= end:
            cloned = copy.copy(ent)
            cloned.offset = prefix_u16 + int(ent.offset) - base_u16
            moved.append(cloned)
    return moved


def reorder_text(text: str, entities):
    """Move the final hashtag block from above CTA to below the bot CTA line."""
    if not text or "#" not in text or "ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ" not in text:
        return text, list(entities or []), False

    bot = re.search(r"(?m)^.*ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ.*$", text)
    if not bot:
        return text, list(entities or []), False

    # Only consider hashtag lines located before the CTA. The last such block is
    # the template hashtag block; hashtags inside descriptions are left untouched.
    candidates = list(re.finditer(r"(?m)^[ \t]*#[^\n]*(?:\n[ \t]*#[^\n]*)*", text[:bot.start()]))
    if not candidates:
        return text, list(entities or []), False
    tags = candidates[-1]

    # This guard makes the migration idempotent and limits it to Cozy Asia posts.
    between = text[tags.end():bot.end()]
    if "ЖМИ ЗДЕСЬ" not in between:
        return text, list(entities or []), False

    delete_end = tags.end()
    if text[delete_end:delete_end + 2] == "\n\n":
        delete_end += 2
    elif text[delete_end:delete_end + 1] == "\n":
        delete_end += 1

    tag_text = text[tags.start():tags.end()].strip("\n")
    insert_prefix = "\n\n"
    moved_entities = _captured_entities(text, entities, tags.start(), tags.end(), insert_prefix)

    replacements = [
        {"start": tags.start(), "end": delete_end, "text": "", "entities": []},
        {
            "start": bot.end(),
            "end": bot.end(),
            "text": insert_prefix + tag_text,
            "entities": moved_entities,
        },
    ]
    new_text, new_entities = mt._apply_replacements(text, entities or [], replacements)
    return new_text, new_entities, new_text != text


async def run(catalog):
    """Reorder all matching posts in configured channels and return per-channel stats."""
    from telethon.errors import FloodWaitError

    client = await mt._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")

    results = {}
    try:
        for channel_name in target_channels(catalog):
            scanned = edited = skipped = errors = 0
            try:
                channel = await client.get_entity(channel_name)
            except Exception as exc:
                log.exception("Could not resolve @%s", channel_name)
                results[channel_name] = {"scanned": 0, "edited": 0, "skipped": 0, "errors": 1, "error": type(exc).__name__}
                continue

            async for msg in client.iter_messages(channel):
                scanned += 1
                text = getattr(msg, "message", None) or ""
                if not text:
                    skipped += 1
                    continue
                try:
                    new_text, new_entities, changed = reorder_text(text, msg.entities or [])
                    if not changed:
                        skipped += 1
                        continue
                    while True:
                        try:
                            await client.edit_message(
                                channel,
                                msg.id,
                                new_text,
                                formatting_entities=new_entities,
                                link_preview=False,
                            )
                            edited += 1
                            break
                        except FloodWaitError as exc:
                            await asyncio.sleep(int(exc.seconds) + 1)
                    # Keep Telegram edits conservative. Google-backed channel capture
                    # handlers are disabled while this one-shot migration is active.
                    await asyncio.sleep(1.25)
                except Exception:
                    errors += 1
                    log.exception("Hashtag reorder failed @%s mid=%s", channel_name, getattr(msg, "id", None))

                if edited and edited % 20 == 0:
                    log.info(
                        "Hashtag reorder progress @%s: scanned=%s edited=%s skipped=%s errors=%s",
                        channel_name, scanned, edited, skipped, errors,
                    )

            results[channel_name] = {
                "scanned": scanned,
                "edited": edited,
                "skipped": skipped,
                "errors": errors,
            }
            log.info("Hashtag reorder done @%s: %s", channel_name, results[channel_name])

        log.info("Hashtag reorder all channels done: %s", results)
        return results
    finally:
        await client.disconnect()

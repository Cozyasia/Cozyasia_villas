# -*- coding: utf-8 -*-
"""One-shot migration: add 'Оператор: @cozy_asia' to every property listing in @samuirental."""
from __future__ import annotations

import asyncio
import copy
import json
import logging

from telethon.errors import FloodWaitError
from telethon.tl.types import MessageEntityMention

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("migrate-samuirental-operator")
CHANNEL = "samuirental"
OPERATOR_LINE = "Оператор: @cozy_asia"
OPERATOR_HANDLE = "@cozy_asia"


def _u16_len(text: str) -> int:
    return len((text or "").encode("utf-16-le")) // 2


def _is_listing(text: str) -> bool:
    t = text or ""
    if "ОПИСАНИЕ" not in t:
        return False
    if not ("УСЛОВИЯ АРЕНДЫ" in t.upper() or "THB/мес" in t or "THB/МЕС" in t.upper()):
        return False
    return (
        "ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ" in t
        or "ОСТАВИТЬ ЗАЯВКУ" in t
        or bool(publication_safety.lot_from_header_text(t))
    )


def _insertion_pos(text: str) -> int:
    targets = (
        "ОСТАВИТЬ ЗАЯВКУ",
        "ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ",
    )
    for target in targets:
        p = text.find(target)
        if p >= 0:
            line_start = text.rfind("\n", 0, p) + 1
            # Premium CTA may occupy two lines (ОСТАВИТЬ / ЗАЯВКУ).
            if target == "ОСТАВИТЬ ЗАЯВКУ":
                return line_start
            # If a separate premium "ОСТАВИТЬ" line exists just above, insert before it.
            before = text[:line_start].rstrip("\n")
            prev_start = before.rfind("\n") + 1
            prev = before[prev_start:].strip()
            if prev in {"ОСТАВИТЬ", "🔤🔤🔤🔤🔤🔤🔤🔤"}:
                return prev_start
            return line_start

    # Older posts without CTA: keep operator immediately above hashtag block.
    lines = text.splitlines(keepends=True)
    offset = 0
    for line in lines:
        if line.lstrip().startswith("#"):
            return offset
        offset += len(line)
    return len(text)


def _make_insert(text: str, pos: int) -> str:
    prefix = text[:pos]
    leading = "" if (not prefix or prefix.endswith("\n")) else "\n"
    # Keep one visual blank line around the operator when possible.
    if prefix.endswith("\n\n"):
        leading = ""
    elif prefix.endswith("\n"):
        leading = "\n"
    return leading + OPERATOR_LINE + "\n\n"


def _shift_entities(text: str, entities, pos: int, insert_text: str):
    pos16 = _u16_len(text[:pos])
    delta16 = _u16_len(insert_text)
    new_entities = copy.deepcopy(list(entities or []))
    for ent in new_entities:
        off = int(getattr(ent, "offset", 0))
        length = int(getattr(ent, "length", 0))
        if off >= pos16:
            ent.offset = off + delta16
        elif off < pos16 < off + length:
            ent.length = length + delta16

    mention_py = insert_text.find(OPERATOR_HANDLE)
    if mention_py >= 0:
        mention_off = pos16 + _u16_len(insert_text[:mention_py])
        new_entities.append(MessageEntityMention(offset=mention_off, length=_u16_len(OPERATOR_HANDLE)))
    new_entities.sort(key=lambda e: (int(getattr(e, "offset", 0)), -int(getattr(e, "length", 0))))
    return new_entities


async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")

    scanned = listings = edited = already = too_long = errors = 0
    too_long_ids = []
    error_ids = []
    edited_ids = []

    try:
        channel = await client.get_entity(CHANNEL)
        async for msg in client.iter_messages(channel, limit=None):
            scanned += 1
            text = getattr(msg, "message", None) or ""
            if not text or not _is_listing(text):
                continue
            listings += 1

            if OPERATOR_LINE in text:
                already += 1
                continue

            pos = _insertion_pos(text)
            insert_text = _make_insert(text, pos)
            new_text = text[:pos] + insert_text + text[pos:]

            media_name = type(getattr(msg, "media", None)).__name__
            max_len = 4096 if media_name in {"NoneType", "MessageMediaWebPage"} else 1024
            if len(new_text) > max_len:
                too_long += 1
                too_long_ids.append(int(msg.id))
                log.warning(
                    "OPERATOR_MIGRATION_TOO_LONG mid=%s old=%s new=%s limit=%s",
                    msg.id, len(text), len(new_text), max_len,
                )
                continue

            old_lot = publication_safety.lot_from_message(msg)
            entities = _shift_entities(text, getattr(msg, "entities", None), pos, insert_text)
            keep_preview = media_name == "MessageMediaWebPage"

            try:
                await client.edit_message(
                    channel,
                    int(msg.id),
                    new_text,
                    formatting_entities=entities,
                    link_preview=keep_preview,
                )
                verify = await client.get_messages(channel, ids=int(msg.id))
                live = getattr(verify, "message", None) or ""
                if OPERATOR_LINE not in live:
                    raise RuntimeError("operator line missing after read-back")
                if live.count(OPERATOR_LINE) != 1:
                    raise RuntimeError("operator line duplicated after read-back")
                if old_lot:
                    new_lot = publication_safety.lot_from_message(verify)
                    if new_lot != old_lot:
                        raise RuntimeError(f"lot changed during migration: {old_lot!r} -> {new_lot!r}")
                edited += 1
                edited_ids.append(int(msg.id))
                if edited % 10 == 0:
                    log.info(
                        "OPERATOR_MIGRATION_PROGRESS scanned=%s listings=%s edited=%s already=%s too_long=%s errors=%s",
                        scanned, listings, edited, already, too_long, errors,
                    )
                await asyncio.sleep(8.0)
            except FloodWaitError as exc:
                wait = int(getattr(exc, "seconds", 0) or 0) + 2
                log.warning("OPERATOR_MIGRATION_FLOOD_WAIT seconds=%s mid=%s", wait, msg.id)
                await asyncio.sleep(wait)
                try:
                    await client.edit_message(
                        channel,
                        int(msg.id),
                        new_text,
                        formatting_entities=entities,
                        link_preview=keep_preview,
                    )
                    verify = await client.get_messages(channel, ids=int(msg.id))
                    live = getattr(verify, "message", None) or ""
                    if OPERATOR_LINE not in live:
                        raise RuntimeError("operator line missing after retry read-back")
                    if old_lot and publication_safety.lot_from_message(verify) != old_lot:
                        raise RuntimeError("lot changed during retry migration")
                    edited += 1
                    edited_ids.append(int(msg.id))
                except Exception:
                    errors += 1
                    error_ids.append(int(msg.id))
                    log.exception("OPERATOR_MIGRATION_EDIT_FAILED_AFTER_WAIT mid=%s", msg.id)
            except Exception:
                errors += 1
                error_ids.append(int(msg.id))
                log.exception("OPERATOR_MIGRATION_EDIT_FAILED mid=%s", msg.id)

        result = {
            "channel": CHANNEL,
            "scanned": scanned,
            "listings": listings,
            "edited": edited,
            "already": already,
            "too_long": too_long,
            "too_long_ids": too_long_ids,
            "errors": errors,
            "error_ids": error_ids,
            "first_edited_id": min(edited_ids) if edited_ids else None,
            "last_edited_id": max(edited_ids) if edited_ids else None,
            "result": "complete" if not too_long and not errors else "partial",
        }
        log.info("MIGRATE_SAMUIRENTAL_OPERATOR_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

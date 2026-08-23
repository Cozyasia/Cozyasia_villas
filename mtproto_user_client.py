# -*- coding: utf-8 -*-
"""MTProto user-client for publishing Premium Custom Emoji in Telegram channels.

Why this exists:
Bot API accepts custom emoji entities but does not render our Premium alphabet pack
inside channels. This module logs in a real Premium user account through MTProto and
uses that account only to upgrade already-standardized channel posts visually.

Security:
- Never asks the user to paste SMS codes/passwords into ChatGPT.
- QR login is initiated from the private bot chat.
- The resulting StringSession is encrypted with MT_SESSION_KEY and stored in the
  same Google Sheet in worksheet MTProtoAuth.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

from telegram.ext import CommandHandler

import post_layout_v6_premium as premium

log = logging.getLogger("mtproto-user")

MT_API_ID = os.environ.get("MT_API_ID", "").strip()
MT_API_HASH = os.environ.get("MT_API_HASH", "").strip()
MT_SESSION_KEY = os.environ.get("MT_SESSION_KEY", "").strip()
MT_ADMIN_USERNAME = os.environ.get("MT_ADMIN_USERNAME", "Cozy_asia").strip().lstrip("@").lower()

_DAEMON_LOCK = threading.Lock()
_DAEMON_STARTED = False


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def configured_api() -> bool:
    return bool(MT_API_ID and MT_API_HASH and MT_SESSION_KEY)


def _admin_ok(update) -> bool:
    user = getattr(update, "effective_user", None)
    chat = getattr(update, "effective_chat", None)
    if not user or not chat or getattr(chat, "type", "") != "private":
        return False
    return (getattr(user, "username", None) or "").lower() == MT_ADMIN_USERNAME


def _fernet():
    from cryptography.fernet import Fernet
    digest = hashlib.sha256(MT_SESSION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _auth_ws(catalog):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        ws = sh.worksheet("MTProtoAuth")
    except Exception:
        ws = sh.add_worksheet(title="MTProtoAuth", rows=20, cols=5)
        ws.append_row(["key", "value", "updated_at", "account_id", "username"], value_input_option="RAW")
    return ws


def _save_session(catalog, session_string: str, me) -> None:
    encrypted = _fernet().encrypt(session_string.encode("utf-8")).decode("ascii")
    ws = _auth_ws(catalog)
    rows = ws.get_all_values()
    target = None
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == "session":
            target = i
            break
    payload = [[
        "session", encrypted, _now(), str(getattr(me, "id", "") or ""),
        str(getattr(me, "username", "") or ""),
    ]]
    if target:
        ws.update(f"A{target}:E{target}", payload, value_input_option="RAW")
    else:
        ws.append_row(payload[0], value_input_option="RAW")


def _load_session(catalog) -> str:
    if not configured_api():
        return ""
    try:
        ws = _auth_ws(catalog)
        for row in ws.get_all_values()[1:]:
            if row and row[0] == "session" and len(row) > 1 and row[1]:
                return _fernet().decrypt(row[1].encode("ascii")).decode("utf-8")
    except Exception:
        log.exception("Could not load/decrypt MTProto session")
    return ""


def _u16_len(text: str) -> int:
    return len((text or "").encode("utf-16-le")) // 2


def _py_from_u16(text: str, offset: int) -> int:
    used = 0
    for i, ch in enumerate(text):
        if used >= offset:
            return i
        used += _u16_len(ch)
    return len(text)


def _premium_lot_parts(lot: str):
    from telethon.tl.types import MessageEntityCustomEmoji
    text = ""
    entities = []

    def add_custom(cid: str, fallback: str):
        nonlocal text
        off = _u16_len(text)
        text += fallback
        entities.append(MessageEntityCustomEmoji(offset=off, length=_u16_len(fallback), document_id=int(cid)))

    for ch in "ЛОТ":
        add_custom(premium.LOT_IDS[ch], "🔤")
    text += " "
    add_custom(premium.LOT_IDS["№"], "🔤")
    text += " "
    for ch in str(lot or "").strip():
        key = "-" if ch in {"-", "–", "—"} else ch
        cid = premium.DIGIT_IDS.get(key)
        if cid:
            add_custom(cid, "➖" if key == "-" else key + "\ufe0f\u20e3")
        else:
            # Owner suffix letters are intentionally left plain until the
            # historical owner-code map is recovered.
            text += ch
    return text, entities


def _premium_cta_parts():
    from telethon.tl.types import MessageEntityCustomEmoji
    text = ""
    entities = []

    def add_custom(cid: str, fallback: str = "🔤"):
        nonlocal text
        off = _u16_len(text)
        text += fallback
        entities.append(MessageEntityCustomEmoji(offset=off, length=_u16_len(fallback), document_id=int(cid)))

    for ch in "ОСТАВИТЬ":
        add_custom(premium.CTA_IDS[ch])
    text += "\n"
    for ch in "ЗАЯВКУ":
        add_custom(premium.CTA_IDS[ch])
    return text, entities


def _intersects(a0, a1, b0, b1):
    return max(a0, b0) < min(a1, b1)


def _apply_replacements(text: str, old_entities, replacements):
    """Replace text ranges while preserving unrelated Telegram entities.

    replacements: list of dicts {start,end,text,entities} where entities are
    relative to replacement text in UTF-16 units.
    """
    replacements = sorted(replacements, key=lambda x: x["start"])
    out = []
    cursor = 0
    new_start_py = {}
    delta = 0
    for idx, op in enumerate(replacements):
        out.append(text[cursor:op["start"]])
        new_start_py[idx] = op["start"] + delta
        out.append(op["text"])
        delta += len(op["text"]) - (op["end"] - op["start"])
        cursor = op["end"]
    out.append(text[cursor:])
    new_text = "".join(out)

    new_entities = []
    for ent in old_entities or []:
        try:
            s = _py_from_u16(text, int(ent.offset))
            e = _py_from_u16(text, int(ent.offset) + int(ent.length))
        except Exception:
            continue
        if any(_intersects(s, e, op["start"], op["end"]) for op in replacements):
            continue
        shift = 0
        for op in replacements:
            if op["end"] <= s:
                shift += len(op["text"]) - (op["end"] - op["start"])
        ns, ne = s + shift, e + shift
        cloned = copy.copy(ent)
        cloned.offset = _u16_len(new_text[:ns])
        cloned.length = _u16_len(new_text[ns:ne])
        new_entities.append(cloned)

    for idx, op in enumerate(replacements):
        base = _u16_len(new_text[:new_start_py[idx]])
        for ent in op.get("entities") or []:
            cloned = copy.copy(ent)
            cloned.offset = base + int(ent.offset)
            new_entities.append(cloned)

    new_entities.sort(key=lambda x: (int(x.offset), int(x.length)))
    return new_text, new_entities


def upgrade_text(text: str, entities, lot: str):
    """Turn current V7 safe post into the Premium visual version."""
    if not text or "ЛОТ №" not in text:
        return text, list(entities or []), False

    top = re.search(r"^🏡\s*ЛОТ\s*№[^\n]*", text, flags=re.I)
    cta = re.search(r"^📝\s*ОСТАВИТЬ\s+ЗАЯВКУ\s*$", text, flags=re.I | re.M)
    if not top or not cta:
        return text, list(entities or []), False

    lot_text, lot_entities = _premium_lot_parts(lot)
    cta_text, cta_entities = _premium_cta_parts()
    replacements = [
        {"start": top.start(), "end": top.end(), "text": lot_text, "entities": lot_entities},
        {"start": cta.start(), "end": cta.end(), "text": cta_text, "entities": cta_entities},
    ]
    new_text, new_entities = _apply_replacements(text, entities, replacements)

    # Add the captured Premium custom emoji for the description bubble and CTA arrows.
    from telethon.tl.types import MessageEntityCustomEmoji
    for needle, cid in (("💬", premium.DESC_ID), ("👉", premium.RIGHT_ID), ("👈", premium.LEFT_ID)):
        pos = new_text.find(needle)
        if pos >= 0:
            new_entities.append(MessageEntityCustomEmoji(
                offset=_u16_len(new_text[:pos]),
                length=_u16_len(needle),
                document_id=int(cid),
            ))
    new_entities.sort(key=lambda x: (int(x.offset), int(x.length)))
    return new_text, new_entities, True


async def _new_client(catalog):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    session = await asyncio.to_thread(_load_session, catalog)
    if not session:
        return None
    client = TelegramClient(StringSession(session), int(MT_API_ID), MT_API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        return None
    return client


async def _upgrade_one(catalog, message_id: int, lot: str):
    from telethon.errors import FloodWaitError
    client = await _new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        channel = await client.get_entity(catalog.CATALOG_CHANNEL)
        msg = await client.get_messages(channel, ids=int(message_id))
        if not msg or not getattr(msg, "message", None):
            return {"result": "missing", "message_id": message_id, "lot": lot}
        # If the top line already has a custom emoji, do not rewrite it again.
        first_nl = msg.message.find("\n")
        top_u16 = _u16_len(msg.message[: first_nl if first_nl >= 0 else len(msg.message)])
        if any(type(e).__name__ == "MessageEntityCustomEmoji" and int(e.offset) < top_u16 for e in (msg.entities or [])):
            return {"result": "already", "message_id": message_id, "lot": lot}
        new_text, new_entities, changed = upgrade_text(msg.message, msg.entities or [], lot)
        if not changed:
            return {"result": "not_v7", "message_id": message_id, "lot": lot}
        while True:
            try:
                await client.edit_message(channel, int(message_id), new_text, formatting_entities=new_entities, link_preview=False)
                break
            except FloodWaitError as e:
                await asyncio.sleep(int(e.seconds) + 1)
        return {"result": "edited", "message_id": message_id, "lot": lot}
    finally:
        await client.disconnect()


def _rows_for_catalog(catalog):
    rows = catalog.load_catalog_rows()
    out = []
    seen = set()
    for row in rows:
        lot = str(row.get("lot_id") or "").strip()
        mid = str(row.get("telegram_message_id") or "").strip()
        if not lot or not mid.isdigit():
            continue
        key = int(mid)
        if key in seen:
            continue
        seen.add(key)
        out.append((key, lot))
    return sorted(out)


async def _bulk_upgrade(catalog, notify_message=None):
    from telethon.errors import FloodWaitError
    client = await _new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    edited = already = skipped = errors = 0
    try:
        channel = await client.get_entity(catalog.CATALOG_CHANNEL)
        rows = await asyncio.to_thread(_rows_for_catalog, catalog)
        total = len(rows)
        for index, (mid, lot) in enumerate(rows, start=1):
            try:
                msg = await client.get_messages(channel, ids=mid)
                if not msg or not getattr(msg, "message", None):
                    skipped += 1
                    continue
                first_nl = msg.message.find("\n")
                top_u16 = _u16_len(msg.message[: first_nl if first_nl >= 0 else len(msg.message)])
                if any(type(e).__name__ == "MessageEntityCustomEmoji" and int(e.offset) < top_u16 for e in (msg.entities or [])):
                    already += 1
                    continue
                new_text, new_entities, changed = upgrade_text(msg.message, msg.entities or [], lot)
                if not changed:
                    skipped += 1
                    continue
                while True:
                    try:
                        await client.edit_message(channel, mid, new_text, formatting_entities=new_entities, link_preview=False)
                        edited += 1
                        break
                    except FloodWaitError as e:
                        await asyncio.sleep(int(e.seconds) + 1)
                await asyncio.sleep(1.5)
            except Exception:
                errors += 1
                log.exception("MTProto premium upgrade failed mid=%s lot=%s", mid, lot)
            if notify_message and index % 10 == 0:
                try:
                    await notify_message.reply_text(
                        f"Premium MTProto: {index}/{total} · изменено {edited} · уже готово {already} · пропущено {skipped} · ошибок {errors}"
                    )
                except Exception:
                    pass
        result = {"total": total, "edited": edited, "already": already, "skipped": skipped, "errors": errors}
        log.info("MTProto Premium backfill done: %s", result)
        return result
    finally:
        await client.disconnect()


async def cmd_mtproto_status(update, context, catalog):
    if not _admin_ok(update):
        return
    if not configured_api():
        await update.effective_message.reply_text(
            "MTProto-код установлен, но в Render ещё нет MT_API_ID / MT_API_HASH. MT_SESSION_KEY уже подготовлен."
        )
        return
    session = await asyncio.to_thread(_load_session, catalog)
    if not session:
        await update.effective_message.reply_text("MTProto API настроен, но Premium-аккаунт ещё не авторизован. Используйте /mtproto_qr")
        return
    client = await _new_client(catalog)
    if not client:
        await update.effective_message.reply_text("Сохранённая MTProto-сессия больше не авторизована. Повторите /mtproto_qr")
        return
    try:
        me = await client.get_me()
        await update.effective_message.reply_text(
            f"✅ MTProto авторизован: @{getattr(me, 'username', '') or 'без username'} · id {getattr(me, 'id', '')}.\n"
            "Можно делать /premium_test 1179"
        )
    finally:
        await client.disconnect()


async def cmd_mtproto_qr(update, context, catalog):
    if not _admin_ok(update):
        return
    if not configured_api():
        await update.effective_message.reply_text(
            "Сначала добавьте в Render два значения: MT_API_ID и MT_API_HASH. После деплоя повторите /mtproto_qr."
        )
        return

    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
    import qrcode

    client = TelegramClient(StringSession(), int(MT_API_ID), MT_API_HASH)
    await client.connect()
    qr = await client.qr_login()
    buf = io.BytesIO()
    qrcode.make(qr.url).save(buf, format="PNG")
    buf.seek(0)
    await update.effective_message.reply_photo(
        photo=buf,
        caption=(
            "Отсканируйте QR вашим Premium-аккаунтом:\n"
            "Telegram → Настройки → Устройства → Подключить устройство.\n\n"
            "QR действует около 2 минут. Коды/пароли сюда присылать не нужно."
        ),
    )

    async def finish():
        try:
            await qr.wait(timeout=120)
            me = await client.get_me()
            session_string = client.session.save()
            await asyncio.to_thread(_save_session, catalog, session_string, me)
            await update.effective_message.reply_text(
                f"✅ Premium MTProto-сессия сохранена для @{getattr(me, 'username', '') or 'аккаунта'}.\n"
                "Теперь запустите /premium_test 1179"
            )
            ensure_daemon_started(catalog)
        except SessionPasswordNeededError:
            await update.effective_message.reply_text(
                "QR подтверждён, но Telegram запросил пароль двухэтапной защиты. Не присылайте пароль в чат. "
                "Я подготовлю отдельный защищённый способ завершить вход."
            )
        except asyncio.TimeoutError:
            await update.effective_message.reply_text("QR истёк. Просто повторите /mtproto_qr")
        except Exception as e:
            log.exception("MTProto QR auth failed")
            await update.effective_message.reply_text(f"MTProto-вход не завершён: {type(e).__name__}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    context.application.create_task(finish())


async def cmd_premium_test(update, context, catalog):
    if not _admin_ok(update):
        return
    lot = (context.args[0] if context.args else "1179").strip()
    rows = await asyncio.to_thread(catalog.load_catalog_rows)
    target = None
    for row in rows:
        if str(row.get("lot_id") or "").strip().lower() == lot.lower():
            mid = str(row.get("telegram_message_id") or "").strip()
            if mid.isdigit():
                target = (int(mid), str(row.get("lot_id") or lot))
    if not target:
        await update.effective_message.reply_text(f"Не нашёл message_id для лота {lot}")
        return
    try:
        result = await _upgrade_one(catalog, target[0], target[1])
        await update.effective_message.reply_text(f"MTProto test: {json.dumps(result, ensure_ascii=False)}")
    except Exception as e:
        log.exception("Premium test failed")
        await update.effective_message.reply_text(f"MTProto test error: {type(e).__name__}: {e}")


async def cmd_premium_backfill(update, context, catalog):
    if not _admin_ok(update):
        return
    await update.effective_message.reply_text("Запускаю Premium MTProto-проход. Буду сообщать прогресс каждые 10 постов.")

    async def run():
        try:
            result = await _bulk_upgrade(catalog, update.effective_message)
            await update.effective_message.reply_text(f"✅ Premium MTProto завершён: {json.dumps(result, ensure_ascii=False)}")
        except Exception as e:
            log.exception("Premium backfill failed")
            await update.effective_message.reply_text(f"Premium MTProto error: {type(e).__name__}: {e}")

    context.application.create_task(run())


def install(app, catalog):
    app.add_handler(CommandHandler("mtproto_status", lambda u, c: cmd_mtproto_status(u, c, catalog)), group=-90)
    app.add_handler(CommandHandler("mtproto_qr", lambda u, c: cmd_mtproto_qr(u, c, catalog)), group=-90)
    app.add_handler(CommandHandler("premium_test", lambda u, c: cmd_premium_test(u, c, catalog)), group=-90)
    app.add_handler(CommandHandler("premium_backfill", lambda u, c: cmd_premium_backfill(u, c, catalog)), group=-90)
    log.info("MTProto commands installed; api_configured=%s", configured_api())


def ensure_daemon_started(catalog):
    """Start a user-client listener that upgrades newly standardized V7 posts.

    It is deliberately inactive until a valid encrypted session exists.
    """
    global _DAEMON_STARTED
    with _DAEMON_LOCK:
        if _DAEMON_STARTED:
            return
        if not configured_api() or not _load_session(catalog):
            return
        _DAEMON_STARTED = True

    def runner():
        async def mainloop():
            from telethon import TelegramClient, events
            from telethon.sessions import StringSession
            session = await asyncio.to_thread(_load_session, catalog)
            client = TelegramClient(StringSession(session), int(MT_API_ID), MT_API_HASH)
            await client.start()
            channel = await client.get_entity(catalog.CATALOG_CHANNEL)

            async def maybe_upgrade(event):
                await asyncio.sleep(8)
                try:
                    msg = await client.get_messages(channel, ids=event.message.id)
                    if not msg or not msg.message or "🏡 ЛОТ №" not in msg.message:
                        return
                    first_nl = msg.message.find("\n")
                    top_u16 = _u16_len(msg.message[: first_nl if first_nl >= 0 else len(msg.message)])
                    if any(type(e).__name__ == "MessageEntityCustomEmoji" and int(e.offset) < top_u16 for e in (msg.entities or [])):
                        return
                    lot_match = re.search(r"ЛОТ\s*№\s*([A-Za-z0-9-]+)", msg.message, re.I)
                    if not lot_match:
                        return
                    lot = lot_match.group(1)
                    new_text, new_entities, changed = upgrade_text(msg.message, msg.entities or [], lot)
                    if changed:
                        await client.edit_message(channel, msg.id, new_text, formatting_entities=new_entities, link_preview=False)
                        log.info("Auto-upgraded new post via MTProto mid=%s lot=%s", msg.id, lot)
                except Exception:
                    log.exception("Automatic MTProto upgrade failed mid=%s", getattr(event.message, "id", None))

            client.add_event_handler(maybe_upgrade, events.NewMessage(chats=channel))
            client.add_event_handler(maybe_upgrade, events.MessageEdited(chats=channel))
            log.info("MTProto Premium daemon active for @%s", catalog.CATALOG_CHANNEL)
            await client.run_until_disconnected()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(mainloop())
        except Exception:
            log.exception("MTProto daemon stopped")
        finally:
            loop.close()

    threading.Thread(target=runner, name="mtproto-premium", daemon=True).start()

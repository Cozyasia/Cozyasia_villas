# -*- coding: utf-8 -*-
"""Dedicated MTProto authorization for Cozy Asia AI Manager."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import os
from datetime import datetime, timezone

from telegram.ext import CommandHandler

import cozy_traffic_manager as manager

log = logging.getLogger("ai-manager-auth")

AUTH_SHEET = "AIManagerAuth"
AUTH_HEADERS = ["key", "value", "updated_at", "account_id", "username"]
EXPECTED_USERNAME = os.getenv("AI_MANAGER_USERNAME", "CozyAsiaAI").strip()
MT_API_ID = os.getenv("MT_API_ID", "").strip()
MT_API_HASH = os.getenv("MT_API_HASH", "").strip()
MT_SESSION_KEY = os.getenv("MT_SESSION_KEY", "").strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_username(value) -> str:
    return str(value or "").strip().lstrip("@").lower()


def account_matches_expected(me, expected_username=EXPECTED_USERNAME) -> bool:
    actual = normalize_username(getattr(me, "username", None))
    expected = normalize_username(expected_username)
    return bool(actual and expected and actual == expected)


def configured_api() -> bool:
    return bool(MT_API_ID and MT_API_HASH and MT_SESSION_KEY)


def _fernet():
    from cryptography.fernet import Fernet

    digest = hashlib.sha256(MT_SESSION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _auth_ws(catalog):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        ws = sh.worksheet(AUTH_SHEET)
    except Exception:
        ws = sh.add_worksheet(title=AUTH_SHEET, rows=20, cols=5)
        ws.append_row(AUTH_HEADERS, value_input_option="RAW")
    return ws


def _save_session(catalog, session_string: str, me) -> None:
    if not account_matches_expected(me):
        raise RuntimeError("Wrong Telegram account for AI Manager session")
    encrypted = _fernet().encrypt(session_string.encode("utf-8")).decode("ascii")
    ws = _auth_ws(catalog)
    rows = ws.get_all_values()
    target = None
    for rownum, row in enumerate(rows[1:], start=2):
        if row and row[0] == "session":
            target = rownum
            break
    payload = [[
        "session",
        encrypted,
        _now(),
        str(getattr(me, "id", "") or ""),
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
        log.exception("Could not load/decrypt AI Manager MTProto session")
    return ""


async def new_client(catalog):
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
    me = await client.get_me()
    if not account_matches_expected(me):
        await client.disconnect()
        return None
    return client


async def cmd_manager_status(update, context, catalog):
    if not manager._admin_ok(update):
        return
    if not configured_api():
        await update.effective_message.reply_text(
            "AI Manager MTProto не настроен: нужны MT_API_ID / MT_API_HASH / MT_SESSION_KEY."
        )
        return
    client = await new_client(catalog)
    if not client:
        await update.effective_message.reply_text(
            f"AI Manager ещё не авторизован. Используйте /manager_connect и отсканируйте QR аккаунтом @{normalize_username(EXPECTED_USERNAME)}."
        )
        return
    try:
        me = await client.get_me()
        await update.effective_message.reply_text(
            f"✅ AI Manager подключён: @{getattr(me, 'username', '')} · id {getattr(me, 'id', '')}."
        )
    finally:
        await client.disconnect()


async def cmd_manager_connect(update, context, catalog):
    if not manager._admin_ok(update):
        return
    if not configured_api():
        await update.effective_message.reply_text(
            "Сначала настройте MT_API_ID / MT_API_HASH / MT_SESSION_KEY в Render."
        )
        return

    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    from telethon.sessions import StringSession
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
            f"Отсканируйте QR именно аккаунтом @{normalize_username(EXPECTED_USERNAME)}.\n\n"
            "Telegram → Настройки → Устройства → Подключить устройство.\n\n"
            "QR действует около 2 минут. Коды и пароли сюда не присылайте."
        ),
    )

    async def finish_login():
        try:
            await qr.wait(timeout=110)
            me = await client.get_me()
            if not account_matches_expected(me):
                await update.effective_message.reply_text(
                    f"❌ Отсканирован не тот аккаунт: @{getattr(me, 'username', '') or 'без username'}. "
                    f"Нужен @{normalize_username(EXPECTED_USERNAME)}. Сессия не сохранена."
                )
                return
            session_string = client.session.save()
            await asyncio.to_thread(_save_session, catalog, session_string, me)
            await update.effective_message.reply_text(
                f"✅ AI Manager подключён: @{getattr(me, 'username', '')}.\n"
                "Проверьте командой /manager_status."
            )
        except SessionPasswordNeededError:
            await update.effective_message.reply_text(
                "QR подтверждён, но Telegram запросил пароль двухэтапной защиты. Не присылайте пароль в чат. "
                "Сначала завершим вход защищённым способом."
            )
        except asyncio.TimeoutError:
            await update.effective_message.reply_text("QR истёк. Повторите /manager_connect.")
        except Exception:
            log.exception("AI Manager QR authorization failed")
            await update.effective_message.reply_text("Не удалось завершить авторизацию. Повторите /manager_connect.")
        finally:
            await client.disconnect()

    context.application.create_task(finish_login(), name="ai-manager-qr-login")


def install_handlers(app, catalog) -> None:
    app.add_handler(CommandHandler("manager_connect", lambda u, c: cmd_manager_connect(u, c, catalog)), group=-40)
    app.add_handler(CommandHandler("manager_status", lambda u, c: cmd_manager_status(u, c, catalog)), group=-40)
    log.info("AI Manager auth handlers installed; api_configured=%s", configured_api())

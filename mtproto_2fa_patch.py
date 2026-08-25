# -*- coding: utf-8 -*-
"""Secure 2FA completion for MTProto QR login.

The Telegram 2FA password is read only from the Render environment variable
MT_2FA_PASSWORD. It is never requested in Telegram chat and never logged.
After a successful QR + 2FA login the encrypted StringSession is persisted by
mtproto_user_client and MT_2FA_PASSWORD can be removed from Render immediately.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os

log = logging.getLogger("mtproto-2fa")


def apply(mt):
    async def cmd_mtproto_qr_2fa(update, context, catalog):
        if not mt._admin_ok(update):
            return
        if not mt.configured_api():
            await update.effective_message.reply_text(
                "MTProto API ещё не настроен."
            )
            return

        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.errors import (
            SessionPasswordNeededError,
            PasswordHashInvalidError,
        )
        import qrcode

        client = TelegramClient(StringSession(), int(mt.MT_API_ID), mt.MT_API_HASH)
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
                "Если включена двухэтапная защита, пароль будет взят только из защищённой переменной Render MT_2FA_PASSWORD. "
                "В чат пароль присылать не нужно."
            ),
        )

        async def finish():
            try:
                try:
                    await qr.wait(timeout=120)
                except SessionPasswordNeededError:
                    password = os.environ.get("MT_2FA_PASSWORD", "")
                    if not password:
                        await update.effective_message.reply_text(
                            "✅ QR подтверждён. Telegram требует пароль двухэтапной защиты.\n\n"
                            "Не присылайте пароль сюда. Добавьте его прямо в Render → Cozyasia_villas → Environment как MT_2FA_PASSWORD, "
                            "дождитесь деплоя и повторите /mtproto_qr. После успешного входа пароль можно сразу удалить из Render."
                        )
                        return
                    try:
                        await client.sign_in(password=password)
                    except PasswordHashInvalidError:
                        await update.effective_message.reply_text(
                            "Пароль двухэтапной защиты в MT_2FA_PASSWORD неверный. Исправьте значение в Render и повторите /mtproto_qr."
                        )
                        return

                me = await client.get_me()
                if not me:
                    raise RuntimeError("Telegram account was not authorized")
                session_string = client.session.save()
                await asyncio.to_thread(mt._save_session, catalog, session_string, me)
                await update.effective_message.reply_text(
                    f"✅ MTProto-сессия сохранена для @{getattr(me, 'username', '') or 'аккаунта'}.\n"
                    "Теперь можно удалить MT_2FA_PASSWORD из Render и запустить /premium_test 1179"
                )
                mt.ensure_daemon_started(catalog)
            except asyncio.TimeoutError:
                await update.effective_message.reply_text("QR истёк. Повторите /mtproto_qr")
            except Exception as e:
                log.exception("MTProto QR/2FA auth failed")
                await update.effective_message.reply_text(
                    f"MTProto-вход не завершён: {type(e).__name__}. Пароль в чат не присылайте."
                )
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        context.application.create_task(finish())

    mt.cmd_mtproto_qr = cmd_mtproto_qr_2fa
    log.info("MTProto secure 2FA patch enabled; password_configured=%s", bool(os.environ.get("MT_2FA_PASSWORD", "")))

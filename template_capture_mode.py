# -*- coding: utf-8 -*-
"""One-shot capture of a manually formatted channel post as the visual template.

Arm from a private chat with /capture_template. The next edited_channel_post in the
configured catalog channel is captured verbatim (including custom emoji entities)
and blocked from downstream auto-standardization.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from telegram.ext import ApplicationHandlerStop, CommandHandler, MessageHandler, filters

log = logging.getLogger("template-capture")
CONTROL_SHEET = "Control"
SAMPLE_SHEET = "TemplateSample"
KEY = "template_capture"
TTL_SECONDS = 20 * 60


def _open_or_create(catalog, title, rows=100, cols=12):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        return sh.worksheet(title)
    except Exception:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _ensure_control(catalog):
    ws = _open_or_create(catalog, CONTROL_SHEET, 50, 6)
    vals = ws.get_all_values()
    if not vals:
        ws.append_row(["key", "value", "chat_id", "armed_at", "expires_at"], value_input_option="RAW")
    return ws


def _arm(catalog, chat_id):
    ws = _ensure_control(catalog)
    vals = ws.get_all_values()
    now = int(time.time())
    exp = now + TTL_SECONDS
    rowno = None
    for i, row in enumerate(vals[1:], start=2):
        if row and row[0] == KEY:
            rowno = i
            break
    data = [[KEY, "ARMED", str(chat_id), str(now), str(exp)]]
    if rowno:
        ws.update(f"A{rowno}:E{rowno}", data, value_input_option="RAW")
    else:
        ws.append_rows(data, value_input_option="RAW")
    return exp


def _state(catalog):
    ws = _ensure_control(catalog)
    vals = ws.get_all_values()
    for i, row in enumerate(vals[1:], start=2):
        if row and row[0] == KEY:
            value = row[1] if len(row) > 1 else ""
            chat_id = row[2] if len(row) > 2 else ""
            exp = row[4] if len(row) > 4 else "0"
            try:
                exp_i = int(exp or 0)
            except Exception:
                exp_i = 0
            if value == "ARMED" and exp_i > int(time.time()):
                return ws, i, chat_id, exp_i
            if value == "ARMED":
                ws.update(f"B{i}:B{i}", [["EXPIRED"]], value_input_option="RAW")
            return ws, i, "", 0
    return ws, None, "", 0


def _disarm(ws, rowno, value="CAPTURED"):
    if rowno:
        ws.update(f"B{rowno}:B{rowno}", [[value]], value_input_option="RAW")


def _entity_dict(ent):
    d = {
        "type": str(getattr(ent, "type", "")),
        "offset": int(getattr(ent, "offset", 0) or 0),
        "length": int(getattr(ent, "length", 0) or 0),
    }
    for k in ("custom_emoji_id", "url", "language"):
        v = getattr(ent, k, None)
        if v is not None:
            d[k] = str(v)
    user = getattr(ent, "user", None)
    if user is not None:
        d["user_id"] = getattr(user, "id", None)
    return d


def _save_sample(catalog, msg):
    ws = _open_or_create(catalog, SAMPLE_SHEET, 200, 12)
    vals = ws.get_all_values()
    if not vals:
        ws.append_row([
            "captured_at", "channel", "message_id", "text", "entities_json",
            "custom_emoji_ids", "custom_emoji_count", "telegram_url"
        ], value_input_option="RAW")
    text = (getattr(msg, "text", None) or getattr(msg, "caption", None) or "")
    ents = list(getattr(msg, "entities", None) or []) + list(getattr(msg, "caption_entities", None) or [])
    entity_rows = [_entity_dict(e) for e in ents]
    custom = [x.get("custom_emoji_id") for x in entity_rows if x.get("custom_emoji_id")]
    mid = str(getattr(msg, "message_id", ""))
    channel = catalog.CATALOG_CHANNEL
    url = f"https://t.me/{channel}/{mid}" if mid else ""
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    ws.append_row([
        now, channel, mid, text,
        json.dumps(entity_rows, ensure_ascii=False),
        json.dumps(custom, ensure_ascii=False), str(len(custom)), url,
    ], value_input_option="RAW")
    return {"message_id": mid, "count": len(custom), "url": url, "custom_ids": custom}


def install(app, catalog):
    async def arm_cmd(update, context):
        chat = update.effective_chat
        if not chat:
            raise ApplicationHandlerStop
        await asyncio.to_thread(_arm, catalog, chat.id)
        await update.effective_message.reply_text(
            "🎯 Режим эталона включён на 20 минут.\n\n"
            f"Теперь вручную отредактируйте ОДИН пост в @{catalog.CATALOG_CHANNEL} ровно так, как должны выглядеть остальные, и нажмите «Сохранить».\n\n"
            "Я перехвачу именно эту правку, НЕ буду стандартизировать её обратно и сохраню Premium Emoji/структуру как образец."
        )
        raise ApplicationHandlerStop

    async def cancel_cmd(update, context):
        ws, rowno, _, _ = await asyncio.to_thread(_state, catalog)
        await asyncio.to_thread(_disarm, ws, rowno, "CANCELLED")
        await update.effective_message.reply_text("Режим эталона выключен.")
        raise ApplicationHandlerStop

    async def capture_edit(update, context):
        msg = getattr(update, "edited_channel_post", None)
        if msg is None:
            return
        chat = getattr(msg, "chat", None)
        username = (getattr(chat, "username", None) or "").lstrip("@").lower()
        if username != catalog.CATALOG_CHANNEL.lower():
            return
        ws, rowno, requester, _ = await asyncio.to_thread(_state, catalog)
        if not rowno or not requester:
            return
        result = await asyncio.to_thread(_save_sample, catalog, msg)
        await asyncio.to_thread(_disarm, ws, rowno, "CAPTURED")
        log.info("Captured manual template @%s mid=%s custom_emoji=%s", catalog.CATALOG_CHANNEL, result["message_id"], result["count"])
        try:
            await context.bot.send_message(
                chat_id=int(requester),
                text=(
                    f"✅ Эталон пойман: пост {result['message_id']}.\n"
                    f"Premium Custom Emoji найдено: {result['count']}.\n"
                    "Этот edit не передан автоматическому стандартизатору."
                ),
            )
        except Exception:
            log.exception("Could not notify template requester")
        # Critical: prevent catalog/standardizer handlers in later groups from touching this edit.
        raise ApplicationHandlerStop

    app.add_handler(CommandHandler("capture_template", arm_cmd), group=-80)
    app.add_handler(CommandHandler("capture_template_cancel", cancel_cmd), group=-80)
    app.add_handler(MessageHandler(filters.ALL, capture_edit), group=-79)
    log.info("Manual template capture handlers installed")

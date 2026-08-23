# -*- coding: utf-8 -*-
"""Capture Telegram Premium Custom Emoji IDs for the Cozy Asia listing alphabet."""
import json
import logging

from telegram.ext import ApplicationHandlerStop, CommandHandler, MessageHandler, filters

log = logging.getLogger("emoji-calibration")
LABELS = ["Л", "О", "Т", "№", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "I", "J", "S"]


def _custom_entities(msg):
    entities = list(getattr(msg, "entities", None) or []) + list(getattr(msg, "caption_entities", None) or [])
    out = []
    for ent in entities:
        typ = str(getattr(ent, "type", ""))
        cid = getattr(ent, "custom_emoji_id", None)
        if (typ.endswith("custom_emoji") or typ == "custom_emoji") and cid:
            out.append((int(getattr(ent, "offset", 0) or 0), str(cid)))
    out.sort(key=lambda x: x[0])
    return [cid for _, cid in out]


def _store(catalog, mapping):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        ws = sh.worksheet("EmojiMap")
    except Exception:
        ws = sh.add_worksheet(title="EmojiMap", rows=100, cols=4)
    ws.clear()
    rows = [["symbol", "custom_emoji_id"]] + [[k, v] for k, v in mapping.items()]
    ws.append_rows(rows, value_input_option="RAW")


def install(app, catalog):
    async def start(update, context):
        context.user_data["emoji_calibration_waiting"] = True
        await update.effective_message.reply_text(
            "Отправьте ОДНИМ следующим сообщением 18 Premium Custom Emoji строго в таком порядке:\n"
            "Л О Т № 0 1 2 3 4 5 6 7 8 9 A I J S\n\n"
            "Важно: именно эмодзи из нужного набора, а не обычные буквы/цифры."
        )
        raise ApplicationHandlerStop

    async def capture(update, context):
        if not context.user_data.get("emoji_calibration_waiting"):
            return
        msg = update.effective_message
        ids = _custom_entities(msg) if msg else []
        if len(ids) != len(LABELS):
            await msg.reply_text(
                f"Получил {len(ids)} custom emoji из {len(LABELS)}. Нужны ровно 18 в порядке:\n"
                "Л О Т № 0 1 2 3 4 5 6 7 8 9 A I J S"
            )
            raise ApplicationHandlerStop
        mapping = dict(zip(LABELS, ids))
        await context.application.run_in_thread(_store, catalog, mapping) if hasattr(context.application, "run_in_thread") else None
        if not hasattr(context.application, "run_in_thread"):
            import asyncio
            await asyncio.to_thread(_store, catalog, mapping)
        context.user_data.pop("emoji_calibration_waiting", None)
        log.info("Premium emoji map captured: %s", json.dumps(mapping, ensure_ascii=False))
        await msg.reply_text("✅ Premium Emoji набор сохранён. Можно использовать его для оформления лотов.")
        raise ApplicationHandlerStop

    app.add_handler(CommandHandler("emoji_map", start), group=-40)
    app.add_handler(MessageHandler(filters.ALL, capture), group=-39)
    log.info("Emoji calibration handlers installed")

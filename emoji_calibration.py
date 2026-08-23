# -*- coding: utf-8 -*-
"""Capture Telegram Premium Custom Emoji IDs for the Cozy Asia listing alphabet."""
import asyncio
import json
import logging

from telegram.ext import ApplicationHandlerStop, CommandHandler, MessageHandler, filters

log = logging.getLogger("emoji-calibration")
BASE_LABELS = ["Л", "О", "Т", "№", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
DEFAULT_SUFFIX_LABELS = ["A", "I", "J", "S"]


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


def _suffixes_from_args(args):
    raw = []
    for item in args or []:
        raw.extend(x for x in item.replace(",", " ").replace(";", " ").split() if x)
    if not raw:
        return DEFAULT_SUFFIX_LABELS[:]
    out = []
    for x in raw:
        up = x.strip().upper()
        if up and up not in out:
            out.append(up)
    return out


def install(app, catalog):
    async def start(update, context):
        suffixes = _suffixes_from_args(context.args)
        labels = BASE_LABELS + suffixes
        context.user_data["emoji_calibration_waiting"] = True
        context.user_data["emoji_calibration_labels"] = labels
        await update.effective_message.reply_text(
            f"Отправьте ОДНИМ следующим сообщением {len(labels)} Premium Custom Emoji строго в таком порядке:\n"
            + " ".join(labels)
            + "\n\nВажно: именно эмодзи из нужного набора, а не обычные буквы/цифры."
        )
        raise ApplicationHandlerStop

    async def capture(update, context):
        if not context.user_data.get("emoji_calibration_waiting"):
            return
        msg = update.effective_message
        labels = list(context.user_data.get("emoji_calibration_labels") or (BASE_LABELS + DEFAULT_SUFFIX_LABELS))
        ids = _custom_entities(msg) if msg else []
        if len(ids) != len(labels):
            await msg.reply_text(
                f"Получил {len(ids)} custom emoji из {len(labels)}. Нужны ровно {len(labels)} в порядке:\n"
                + " ".join(labels)
            )
            raise ApplicationHandlerStop
        mapping = dict(zip(labels, ids))
        await asyncio.to_thread(_store, catalog, mapping)
        context.user_data.pop("emoji_calibration_waiting", None)
        context.user_data.pop("emoji_calibration_labels", None)
        log.info("Premium emoji map captured: %s", json.dumps(mapping, ensure_ascii=False))
        await msg.reply_text("✅ Premium Emoji набор сохранён. Можно использовать его для оформления лотов.")
        raise ApplicationHandlerStop

    app.add_handler(CommandHandler("emoji_map", start), group=-40)
    app.add_handler(MessageHandler(filters.ALL, capture), group=-39)
    log.info("Emoji calibration handlers installed")

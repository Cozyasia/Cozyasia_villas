# -*- coding: utf-8 -*-
"""Control plane for the dedicated Cozy Lead Engine service.

Third-party Telegram access remains read-only. This module only sends control
messages to the authorized Cozy Asia admin and records admin decisions in the
shared Google Sheet.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

import cozy_traffic_manager as manager
import lead_contact_dry_run as lead_contact_dry_run
import lead_contact_flow
import lead_draft_store

log = logging.getLogger("cozy-lead-engine-control")
CONFIG_SHEET = "LeadEngineConfig"
CONFIG_HEADERS = ["key", "value", "updated_at"]
ACTIONS_SHEET = "LeadActions"
ACTION_HEADERS = ["key", "status", "updated_at", "admin_username"]
_MONITOR_STARTED = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _config_ws(catalog):
    return manager._worksheet(catalog, CONFIG_SHEET, CONFIG_HEADERS, 50)


def _actions_ws(catalog):
    return manager._worksheet(catalog, ACTIONS_SHEET, ACTION_HEADERS, 3000)


def _draft_ws(catalog):
    return manager._worksheet(catalog, lead_contact_flow.DRAFT_SHEET, lead_draft_store.DRAFT_HEADERS, 3000)


def _set_config(catalog, key: str, value: str) -> None:
    ws = _config_ws(catalog)
    rows = ws.get_all_values()
    for rownum, row in enumerate(rows[1:], start=2):
        if row and row[0] == key:
            ws.update(f"A{rownum}:C{rownum}", [[key, value, _now()]], value_input_option="RAW")
            return
    ws.append_row([key, value, _now()], value_input_option="RAW")


def _get_config(catalog, key: str) -> str:
    rows = _config_ws(catalog).get_all_values()
    for row in rows[1:]:
        if row and row[0] == key:
            return row[1] if len(row) > 1 else ""
    return ""


def _set_action(catalog, key: str, status: str, admin_username: str) -> None:
    ws = _actions_ws(catalog)
    rows = ws.get_all_values()
    payload = [key, status, _now(), admin_username]
    for rownum, row in enumerate(rows[1:], start=2):
        if row and row[0] == key:
            ws.update(f"A{rownum}:D{rownum}", [payload], value_input_option="RAW")
            return
    ws.append_row(payload, value_input_option="RAW")


def _existing_opportunity_keys(catalog) -> set[str]:
    rows = manager._opportunity_ws(catalog).get_all_values()
    return {row[0] for row in rows[1:] if row and row[0]}


def _lead_key(lead) -> str:
    return f"{lead.source_username}:{lead.message_id}"


def _callback_data(action: str, lead) -> str:
    source = str(lead.source_username).strip().lstrip("@")[:32]
    return f"lead:{action}:{source}:{lead.message_id}"


def _draft_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Отправить", callback_data=lead_draft_store.callback_data("send", key)),
            InlineKeyboardButton("✏️ Изменить", callback_data=lead_draft_store.callback_data("edit", key)),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data=lead_draft_store.callback_data("cancel", key))],
    ])


def _recipient_from_draft(record: dict[str, str]) -> lead_contact_dry_run.Recipient:
    return lead_contact_dry_run.Recipient(
        telegram_id=int(record.get("recipient_id") or 0),
        username=record.get("recipient_username", ""),
        display_name=record.get("recipient_name", ""),
    )


def _draft_preview_from_record(record: dict[str, str]) -> str:
    opportunity = {
        "source_username": record.get("source_username", ""),
        "message_id": record.get("message_id", ""),
    }
    return lead_contact_dry_run.build_dry_run_preview(
        opportunity,
        _recipient_from_draft(record),
        record.get("draft", ""),
    )


def _build_card_text(lead) -> str:
    details = []
    districts = list(getattr(lead, "districts", ()) or ())
    if districts:
        details.append("📍 " + ", ".join(districts))
    amount = getattr(lead, "budget_amount", None)
    currency = getattr(lead, "budget_currency", None)
    if amount is not None:
        details.append(f"💰 {amount} {currency or ''}".strip())
    bedrooms = getattr(lead, "bedrooms", None)
    if bedrooms is not None:
        details.append(f"🛏 {bedrooms} спальн.")
    date_text = getattr(lead, "date_text", None)
    duration_text = getattr(lead, "duration_text", None)
    if date_text or duration_text:
        details.append("📅 " + " · ".join(x for x in (date_text, duration_text) if x))
    occupants = getattr(lead, "occupants", None)
    if occupants is not None:
        details.append(f"👥 {occupants}")
    pets = getattr(lead, "pets", None)
    if pets is True:
        details.append("🐾 с питомцем")

    excerpt = " ".join(str(getattr(lead, "text", "") or "").split())[:900]
    lines = [
        f"🎯 {getattr(lead, 'band', '?')} {getattr(lead, 'score', '?')} · @{getattr(lead, 'source_username', '')}",
        str(getattr(lead, "source_title", "") or ""),
    ]
    if details:
        lines.extend(["", *details])
    if excerpt:
        lines.extend(["", "💬 " + excerpt])
    link = str(getattr(lead, "link", "") or "")
    if link:
        lines.extend(["", "🔗 " + link])
    return "\n".join(lines)[:3900]


async def _send_lead_card(bot, chat_id: int, lead) -> None:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Ответить", callback_data=_callback_data("approve", lead)), InlineKeyboardButton("❌ Пропустить", callback_data=_callback_data("skip", lead))]])
    await bot.send_message(chat_id=chat_id, text=_build_card_text(lead), reply_markup=keyboard, disable_web_page_preview=True)


async def cmd_start(update, context, catalog):
    if not manager._admin_ok(update):
        return
    chat_id = int(update.effective_chat.id)
    await asyncio.to_thread(_set_config, catalog, "admin_chat_id", str(chat_id))
    mode = lead_contact_dry_run.contact_mode()
    await update.effective_message.reply_text(
        "✅ Cozy Lead Engine подключён.\n\n"
        "Я буду мониторить approved-источники и присылать сюда новые HOT/WARM запросы. "
        "Первый контакт с человеком выполняется только после твоего подтверждения.\n\n"
        f"Контактный режим: {mode}.\n"
        "Команды: /traffic_sources /traffic_discover /traffic_scan /traffic_opportunities"
    )


async def cmd_lead_action(update, context, catalog):
    if not manager._admin_ok(update):
        return
    query = update.callback_query
    if not query or not query.data:
        return
    parts = query.data.split(":", 3)
    if len(parts) != 4 or parts[0] != "lead":
        return
    _, action, source, message_id = parts
    if action not in {"approve", "skip"}:
        return
    key = f"{source}:{message_id}"
    admin_username = (getattr(update.effective_user, "username", "") or "").lstrip("@")
    status = "approved_for_contact" if action == "approve" else "skipped"
    await asyncio.to_thread(_set_action, catalog, key, status, admin_username)

    if action == "skip":
        await query.answer("Лид пропущен")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    await query.answer("Готовлю AI-черновик…")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        prepared = await lead_contact_flow.prepare_dry_run(catalog, key, admin_username)
    except Exception as exc:
        log.exception("Lead dry-run preparation failed key=%s", key)
        await asyncio.to_thread(_set_action, catalog, key, "draft_failed", admin_username)
        await query.message.reply_text(
            f"❌ Не удалось подготовить DRY RUN для {key}.\nПричина: {exc}"
        )
        return

    preview = lead_contact_dry_run.build_dry_run_preview(
        prepared.opportunity,
        prepared.recipient,
        prepared.draft,
    )
    await query.message.reply_text(
        preview,
        reply_markup=_draft_keyboard(key),
        disable_web_page_preview=True,
    )


async def cmd_draft_action(update, context, catalog):
    if not manager._admin_ok(update):
        return
    query = update.callback_query
    if not query or not query.data:
        return
    try:
        action, key = lead_draft_store.parse_callback(query.data)
    except ValueError:
        return

    ws = await asyncio.to_thread(_draft_ws, catalog)
    record = await asyncio.to_thread(lead_draft_store.get_draft, ws, key)
    if not record:
        await query.answer("Черновик не найден", show_alert=True)
        return

    if action == "cancel":
        await asyncio.to_thread(lead_draft_store.update_status, ws, key, "canceled")
        if context.user_data.get("lead_draft_edit_key") == key:
            context.user_data.pop("lead_draft_edit_key", None)
        await query.answer("Отменено")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text("❌ Черновик отменён. Сообщение клиенту не отправлялось.")
        return

    if action == "edit":
        context.user_data["lead_draft_edit_key"] = key
        await query.answer("Жду новый текст")
        await query.message.reply_text(
            "✏️ Отправь следующим обычным сообщением полный новый текст. "
            "Он заменит текущий черновик; клиенту ничего не отправится."
        )
        return

    # Safety gate: this milestone is deliberately dry-run only.
    if lead_contact_dry_run.live_send_enabled():
        await asyncio.to_thread(lead_draft_store.update_status, ws, key, "live_blocked")
        await query.answer("LIVE SEND пока заблокирован", show_alert=True)
        await query.message.reply_text(
            "⚠️ LIVE SEND ещё не активирован в этом этапе. Сообщение НЕ отправлено. "
            "Сначала завершаем контрольный DRY RUN."
        )
        return

    await asyncio.to_thread(lead_draft_store.update_status, ws, key, "dry_run_approved")
    await query.answer("DRY RUN подтверждён")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.reply_text(
        "🧪 DRY RUN PASS: текст одобрен. @CozyAsiaAI ничего не отправлял. "
        "Статус сохранён как dry_run_approved."
    )


async def cmd_draft_edit_text(update, context, catalog):
    if not manager._admin_ok(update):
        return
    key = context.user_data.get("lead_draft_edit_key")
    if not key:
        return
    text = str(getattr(update.effective_message, "text", "") or "").strip()
    if not text:
        return
    if len(text) > 3000:
        await update.effective_message.reply_text("Текст слишком длинный. Ограничение для черновика — 3000 символов.")
        return

    ws = await asyncio.to_thread(_draft_ws, catalog)
    record = await asyncio.to_thread(lead_draft_store.get_draft, ws, key)
    if not record:
        context.user_data.pop("lead_draft_edit_key", None)
        await update.effective_message.reply_text("❌ Черновик не найден; режим редактирования сброшен.")
        return

    record["draft"] = text
    record["status"] = "draft_edited"
    await asyncio.to_thread(lead_draft_store.upsert_draft, ws, record)
    context.user_data.pop("lead_draft_edit_key", None)
    updated = await asyncio.to_thread(lead_draft_store.get_draft, ws, key)
    await update.effective_message.reply_text(
        _draft_preview_from_record(updated or record),
        reply_markup=_draft_keyboard(key),
        disable_web_page_preview=True,
    )


async def _monitor_loop(application, catalog) -> None:
    try:
        interval = max(300, min(int(os.getenv("COZY_TRAFFIC_MONITOR_INTERVAL", "900")), 21600))
    except Exception:
        interval = 900
    try:
        initial = max(10, min(int(os.getenv("COZY_TRAFFIC_MONITOR_INITIAL_DELAY", "30")), 600))
    except Exception:
        initial = 30
    await asyncio.sleep(initial)
    while True:
        try:
            existing = await asyncio.to_thread(_existing_opportunity_keys, catalog)
            leads = await manager._scan(catalog)
            seen = set()
            new_leads = []
            for lead in leads:
                key = _lead_key(lead)
                if key not in existing and key not in seen:
                    new_leads.append(lead)
                    seen.add(key)
            stats = await asyncio.to_thread(manager._save_opportunities, catalog, leads)
            chat_raw = await asyncio.to_thread(_get_config, catalog, "admin_chat_id")
            if stats.get("created", 0) and chat_raw:
                try:
                    chat_id = int(chat_raw)
                except Exception:
                    chat_id = 0
                if chat_id:
                    for lead in sorted(new_leads, key=lambda x: (x.score, x.message_date), reverse=True):
                        try:
                            await _send_lead_card(application.bot, chat_id, lead)
                        except Exception:
                            log.exception("Lead notification failed key=%s", _lead_key(lead))
            log.info("Lead Engine monitor cycle leads=%d new=%d duplicates=%d", len(leads), stats.get("created", 0), stats.get("duplicate", 0))
        except Exception:
            log.exception("Lead Engine monitor cycle failed")
        await asyncio.sleep(interval)


async def post_init(application, catalog) -> None:
    global _MONITOR_STARTED
    enabled = os.getenv("COZY_TRAFFIC_MONITOR", "1").strip().lower() in {"1", "true", "yes", "on"}
    if enabled and not _MONITOR_STARTED:
        _MONITOR_STARTED = True
        application.create_task(_monitor_loop(application, catalog), name="cozy-lead-monitor")
        log.info("Cozy Lead Engine monitor enabled")


def install_handlers(app, catalog) -> None:
    app.add_handler(CommandHandler("start", lambda u, c: cmd_start(u, c, catalog)), group=-30)
    app.add_handler(CallbackQueryHandler(lambda u, c: cmd_lead_action(u, c, catalog), pattern=r"^lead:(approve|skip):"), group=-30)
    app.add_handler(CallbackQueryHandler(lambda u, c: cmd_draft_action(u, c, catalog), pattern=r"^draft:(send|edit|cancel):"), group=-29)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: cmd_draft_edit_text(u, c, catalog)), group=-29)
    app.add_handler(CommandHandler("traffic_discover", lambda u, c: manager.cmd_traffic_discover(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_sources", lambda u, c: manager.cmd_traffic_sources(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_approve", lambda u, c: manager.cmd_traffic_approve(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_reject", lambda u, c: manager.cmd_traffic_reject(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_scan", lambda u, c: manager.cmd_traffic_scan(u, c, catalog)), group=-20)
    app.add_handler(CommandHandler("traffic_opportunities", lambda u, c: manager.cmd_traffic_opportunities(u, c, catalog)), group=-20)
    log.info("Cozy Lead Engine handlers installed; contact_mode=%s", lead_contact_dry_run.contact_mode())

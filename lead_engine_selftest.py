# -*- coding: utf-8 -*-
"""Synthetic DRY RUN for Cozy Lead Engine.

This command deliberately has no MTProto access and no real Telegram recipient.
It exercises AI drafting, persistent LeadDrafts storage, edit/cancel controls and
the dry-run approval button using a recipient that cannot be contacted.
"""
from __future__ import annotations

import asyncio
import time

from telegram.ext import CommandHandler

import cozy_traffic_manager as manager
import lead_contact_dry_run
import lead_draft_store
import lead_engine_control


async def cmd_traffic_dry_run_test(update, context, catalog):
    if not manager._admin_ok(update):
        return

    message_id = str(int(time.time()))
    key = f"selftest:{message_id}"
    opportunity = {
        "key": key,
        "source_username": "selftest",
        "source_title": "Synthetic Lead Engine Test",
        "message_id": message_id,
        "score": "99",
        "band": "TEST",
        "districts": "Lamai",
        "date_text": "с 1 ноября",
        "duration_text": "2 месяца",
        "budget": "110000 RUB/month",
        "bedrooms": "1",
        "occupants": "2",
        "pets": "no",
        "text": "Ищу жильё на Самуи в районе Ламай с 1 ноября на два месяца, бюджет около 110 000 рублей в месяц.",
        "link": "synthetic://lead-engine-selftest",
    }
    recipient = lead_contact_dry_run.Recipient(telegram_id=0, username="SELFTEST_ONLY", display_name="Synthetic recipient")

    await update.effective_message.reply_text(
        "🧪 SELF TEST: готовлю безопасный AI-черновик. Реального адресата у теста нет."
    )
    try:
        draft = await asyncio.to_thread(lead_contact_dry_run.generate_ai_draft, opportunity)
        ws = await asyncio.to_thread(lead_engine_control._draft_ws, catalog)
        admin_username = (getattr(update.effective_user, "username", "") or "").lstrip("@")
        record = {
            "key": key,
            "status": "test_draft_ready",
            "recipient_id": "0",
            "recipient_username": recipient.username,
            "recipient_name": recipient.display_name,
            "draft": draft,
            "source_username": opportunity["source_username"],
            "message_id": message_id,
            "admin_username": admin_username,
        }
        await asyncio.to_thread(lead_draft_store.upsert_draft, ws, record)
    except Exception as exc:
        await update.effective_message.reply_text(
            f"❌ SELF TEST не смог подготовить черновик: {exc.__class__.__name__}: {exc}"
        )
        return

    preview = lead_contact_dry_run.build_dry_run_preview(opportunity, recipient, draft)
    await update.effective_message.reply_text(
        "🧪 SELF TEST\n\n" + preview,
        reply_markup=lead_engine_control._draft_keyboard(key),
        disable_web_page_preview=True,
    )


def install_handlers(app, catalog) -> None:
    app.add_handler(
        CommandHandler("traffic_dry_run_test", lambda u, c: cmd_traffic_dry_run_test(u, c, catalog)),
        group=-28,
    )

# -*- coding: utf-8 -*-
"""Production entrypoint: legacy Cozy Asia bot + searchable property catalog."""
import asyncio
import json
import logging
import os
import re
import threading

from telegram.ext import CommandHandler, MessageHandler, filters

import legacy_main as legacy
import cozy_catalog
import catalog_fixes

catalog_fixes.apply(cozy_catalog)

log = logging.getLogger("villa-bot-wrapper")
_original_free_text = legacy.free_text
_original_catalog_parse = cozy_catalog.parse_property_query


def _parse_catalog_query_with_terse_support(text):
    """Treat compact criteria such as 'Ламай 2 спальни до 50 000' as a search."""
    spec = _original_catalog_parse(text)
    if spec.get("intent") != "other":
        return spec

    low = (text or "").lower()
    has_bedrooms = bool(
        re.search(
            r"\b(?:\d+|одна|один|две|два|три|четыре|пять|шесть)\s*(?:спальн|br\b)",
            low,
        )
    )
    has_pool = "бассейн" in low or "pool" in low
    has_price = bool(
        re.search(r"(?:до|бюджет|не\s+дороже)\s*[\d\s]+(?:тыс(?:яч)?|k|бат|thb)?", low)
        or re.search(r"\d[\d\s]{2,}\s*(?:бат|thb|тыс(?:яч)?|k)\b", low)
    )
    has_type = any(
        x in low
        for x in (
            "вилла",
            "дом",
            "бунгало",
            "таунхаус",
            "квартир",
            "апартамент",
            "студия",
            "кондо",
        )
    )
    has_district = any(
        x in low
        for x in (
            "ламай",
            "lamai",
            "маенам",
            "maenam",
            "чавенг",
            "chaweng",
            "бопхут",
            "bophut",
            "банграк",
            "bangrak",
            "плай лаем",
            "plai laem",
            "липа ной",
            "lipa noi",
            "натон",
            "nathon",
            "банг по",
            "bang po",
            "чонг мон",
            "choeng mon",
            "талинг нгам",
            "taling ngam",
            "на муанг",
            "na muang",
        )
    )
    hard = has_bedrooms or has_pool or has_price
    signal_count = sum((has_bedrooms, has_pool, has_price, has_type, has_district))
    if hard and signal_count >= 2:
        return _original_catalog_parse("Ищу " + (text or ""))
    return spec


cozy_catalog.parse_property_query = _parse_catalog_query_with_terse_support


def _log_google_service_account():
    raw = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        return
    try:
        email = (json.loads(raw).get("client_email") or "").strip()
        if email:
            log.info("Google service account: %s", email)
    except Exception:
        log.warning("Could not parse GOOGLE_CREDS_JSON client_email")


async def catalog_aware_free_text(update, context):
    text = (getattr(update.effective_message, "text", None) or "").strip()
    if text:
        try:
            answer = await asyncio.to_thread(cozy_catalog.answer_catalog_query, text)
            if answer:
                await update.effective_message.reply_text(answer, disable_web_page_preview=True)
                return
        except Exception:
            log.exception("Catalog search failed; falling back to GPT chat")
    return await _original_free_text(update, context)


def _bootstrap_catalog():
    try:
        stats = cozy_catalog.bootstrap_catalog()
        log.info("Catalog bootstrap: %s", stats)
    except Exception:
        log.exception("Catalog bootstrap failed")


def _install_catalog_handlers(app):
    app.add_handler(CommandHandler("catalog_import", cozy_catalog.cmd_catalog_import), group=-20)
    app.add_handler(CommandHandler("catalog_status", cozy_catalog.cmd_catalog_status), group=-20)
    app.add_handler(CommandHandler("find", cozy_catalog.cmd_find), group=-20)
    app.add_handler(CommandHandler("lot", cozy_catalog.cmd_lot), group=-20)
    app.add_handler(MessageHandler(filters.ALL, cozy_catalog.catch_catalog_updates), group=-10)
    log.info("Catalog handlers installed for @%s", cozy_catalog.CATALOG_CHANNEL)


def main():
    legacy._log_openai_env()
    legacy._probe_openai()
    _log_google_service_account()
    legacy.free_text = catalog_aware_free_text
    app = legacy.build_application()
    _install_catalog_handlers(app)
    threading.Thread(target=_bootstrap_catalog, name="catalog-bootstrap", daemon=True).start()
    legacy.run_webhook(app)


if __name__ == "__main__":
    main()

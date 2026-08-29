# -*- coding: utf-8 -*-
"""Production entrypoint: legacy Cozy Asia bot + searchable property catalog."""
import asyncio
import json
import logging
import os
import re
import threading
import time

from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, filters

import legacy_main as legacy
import cozy_catalog
import catalog_fixes
import catalog_feedback_patch
import lot_id_repair
import lot_parser_safety
import post_standardizer
import post_template_patch
import post_throttle_patch
import post_layout_v5
import post_layout_v6_premium
import post_layout_v7_safe
import emoji_calibration
import template_capture_mode
import channel_template_capture
import manual_edit_guard
import mtproto_user_client
import mtproto_2fa_patch
import samui_news_automation
import hashtag_reorder_patch
import publish_fb_1038134945777547
import correct_fb_1038134945777547
import publish_fb_1405490825011828
import publish_fb_28520466234226624
import publish_airbnb_1074551173034733330
import publish_fb_replies_20260828
import record_fb_scan_20260828_evening
import record_fb_scan_20260829_morning
import record_fb_scan_20260829_evening
import diagnose_samuirental_lots
import renumber_samuirental_lots

catalog_fixes.apply(cozy_catalog)
catalog_feedback_patch.apply(cozy_catalog)
lot_id_repair.apply(cozy_catalog)
lot_parser_safety.apply(cozy_catalog)
post_template_patch.apply(post_standardizer)
post_throttle_patch.apply(post_standardizer)
post_layout_v5.apply(post_standardizer, post_throttle_patch)
post_layout_v6_premium.apply(post_standardizer, post_throttle_patch)
# V7 is the production channel layout. It intentionally overrides V6 because
# our bot cannot render Premium custom emoji entities inside channel posts.
post_layout_v7_safe.apply(post_standardizer, post_throttle_patch)
manual_edit_guard.apply(post_standardizer)
mtproto_2fa_patch.apply(mtproto_user_client)

log = logging.getLogger("villa-bot-wrapper")
_original_free_text = legacy.free_text
_original_catalog_parse = cozy_catalog.parse_property_query
HASHTAG_REORDER_MODE = hashtag_reorder_patch.enabled()

legacy.START_GREETING = (
    "👋 Добро пожаловать в Cozy Asia!\n\n"
    "🏡 Можете сразу написать, какое жильё ищете — я подберу варианты из нашего каталога и дам ссылки на лоты.\n"
    "Например: «Дом или вилла, Ламай / Маенам / Чавенг, 2 спальни, бассейн, до 80 000 бат».\n\n"
    "📝 Если хотите оставить подробную заявку менеджеру — нажмите /rent.\n"
    "🌴 Также можете просто задавать вопросы о Самуи, районах и аренде."
)
SEARCH_GREETING = (
    "🏡 Подберу варианты из каталога Cozy Asia.\n\n"
    "Напишите одним сообщением, что ищете. Например:\n"
    "«Вилла или дом, Ламай / Маенам, 2 спальни, бассейн, до 80 000 бат»."
)


def _parse_catalog_query_with_terse_support(text):
    spec = _original_catalog_parse(text)
    if spec.get("intent") != "other": return spec
    low = (text or "").lower()
    has_bedrooms = bool(re.search(r"\b(?:\d+|одна|один|две|два|три|четыре|пять|шесть)\s*(?:спальн|br\b)", low))
    has_pool = "бассейн" in low or "pool" in low
    has_price = bool(re.search(r"(?:до|бюджет|не\s+дороже)\s*[\d\s]+(?:тыс(?:яч)?|k|бат|thb)?", low) or re.search(r"\d[\d\s]{2,}\s*(?:бат|thb|тыс(?:яч)?|k)\b", low))
    has_type = any(x in low for x in ("вилла","дом","бунгало","таунхаус","квартир","апартамент","студия","кондо"))
    has_district = any(x in low for x in ("ламай","lamai","маенам","maenam","чавенг","chaweng","бопхут","bophut","банграк","bangrak","плай лаем","plai laem","липа ной","lipa noi","натон","nathon","банг по","bang po","чонг мон","choeng mon","талинг нгам","taling ngam","на муанг","na muang"))
    hard = has_bedrooms or has_pool or has_price
    if hard and sum((has_bedrooms,has_pool,has_price,has_type,has_district)) >= 2:
        return _original_catalog_parse("Ищу " + (text or ""))
    return spec

cozy_catalog.parse_property_query = _parse_catalog_query_with_terse_support


def _log_google_service_account():
    raw=os.environ.get("GOOGLE_CREDS_JSON","").strip()
    if not raw:return
    try:
        email=(json.loads(raw).get("client_email") or "").strip()
        if email:log.info("Google service account: %s",email)
    except Exception:log.warning("Could not parse GOOGLE_CREDS_JSON client_email")


async def smart_start(update, context):
    payload="_".join(context.args or []).strip(); low=payload.lower()
    if low=="search":
        context.user_data.clear(); await update.effective_message.reply_text(SEARCH_GREETING); return ConversationHandler.END
    if low=="rent" or low.startswith("rent_"):
        lot=payload[5:].strip() if low.startswith("rent_") else ""; context.user_data.clear()
        if lot and re.fullmatch(r"[A-Za-z0-9_-]{1,40}",lot):
            context.user_data["lots"]=lot; context.user_data["lot_hint"]=lot; log.info("Deep-link application for lot=%s",lot)
        return await legacy.cmd_rent(update,context)
    if payload:
        normalized=legacy._normalize_start_payload(payload); context.user_data.clear(); context.user_data["lots"]=normalized; context.user_data["lot_hint"]=normalized
        return await legacy.cmd_rent(update,context)
    await update.effective_message.reply_text(legacy.START_GREETING); return ConversationHandler.END


async def catalog_aware_free_text(update, context):
    text=(getattr(update.effective_message,"text",None) or "").strip()
    if text:
        try:
            answer=await asyncio.to_thread(cozy_catalog.answer_catalog_query,text)
            if answer:
                await update.effective_message.reply_text(answer,disable_web_page_preview=True); return
        except Exception:log.exception("Catalog search failed; falling back to GPT chat")
    return await _original_free_text(update,context)


def _bootstrap_catalog():
    """Import without calling normalize_existing_rows again after lot repair."""
    try:
        if not cozy_catalog.CATALOG_BOOTSTRAP_IMPORT:
            stats={"disabled":True}
        elif cozy_catalog.CATALOG_BOOTSTRAP_FULL:
            stats=cozy_catalog.import_public_channel_all(False)
        else:
            stats=cozy_catalog.import_public_channel_latest(cozy_catalog.CATALOG_BOOTSTRAP_LIMIT,False)
        log.info("Catalog bootstrap: %s",stats)
    except Exception:log.exception("Catalog bootstrap failed")


def _standardize_existing():
    try:
        stats=post_standardizer.maybe_start_existing(cozy_catalog)
        if stats:log.info("Existing post standardization done: %s",stats)
    except Exception:log.exception("Existing post standardization failed")


def _reorder_hashtags_on_startup():
    # In migration mode the Google-backed channel-capture handlers are disabled,
    # so mass Telegram edits do not create a Sheets quota storm.
    time.sleep(5)
    try:
        result = asyncio.run(hashtag_reorder_patch.run(cozy_catalog))
        log.info("Hashtag reorder startup migration done: %s", result)
    except Exception:
        log.exception("Hashtag reorder startup migration failed")


def _publish_fb_1038134945777547_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(publish_fb_1038134945777547.run())
        if result.get("enabled"):
            log.info("Facebook one-shot publication complete: %s", result)
    except Exception:
        log.exception("Facebook one-shot publication failed")


def _correct_fb_1038134945777547_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(correct_fb_1038134945777547.run())
        if result.get("enabled"):
            log.info("Facebook in-place correction complete: %s", result)
    except Exception:
        log.exception("Facebook in-place correction failed")


def _publish_fb_1405490825011828_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(publish_fb_1405490825011828.run())
        if result.get("enabled"):
            log.info("Facebook Maenam publication complete: %s", result)
    except Exception:
        log.exception("Facebook Maenam publication failed")

def _publish_fb_28520466234226624_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(publish_fb_28520466234226624.run())
        if result.get("enabled"):
            log.info("Facebook Baan Tai publication complete: %s", result)
    except Exception:
        log.exception("Facebook Baan Tai publication failed")


def _publish_airbnb_1074551173034733330_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(publish_airbnb_1074551173034733330.run())
        if result.get("enabled"):
            log.info("Airbnb Aqua Jai publication complete: %s", result)
    except Exception:
        log.exception("Airbnb Aqua Jai publication failed")


def _publish_fb_replies_20260828_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(publish_fb_replies_20260828.run())
        if result.get("enabled"):
            log.info("Facebook owner-reply publications complete: %s", result)
    except Exception:
        log.exception("Facebook owner-reply publications failed")


def _record_fb_scan_20260828_evening_on_startup():
    time.sleep(8)
    try:
        result = record_fb_scan_20260828_evening.run()
        if result.get("enabled"):
            log.info("Facebook evening scan registry update complete: %s", result)
    except Exception:
        log.exception("Facebook evening scan registry update failed")


def _record_fb_scan_20260829_morning_on_startup():
    time.sleep(8)
    try:
        result = record_fb_scan_20260829_morning.run()
        if result.get("enabled"):
            log.info("Facebook morning scan registry update complete: %s", result)
    except Exception:
        log.exception("Facebook morning scan registry update failed")


def _record_fb_scan_20260829_evening_on_startup():
    time.sleep(8)
    try:
        result = record_fb_scan_20260829_evening.run()
        if result.get("enabled"):
            log.info("Facebook evening scan registry update complete: %s", result)
    except Exception:
        log.exception("Facebook evening scan registry update failed")


def _diagnose_samuirental_lots_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(diagnose_samuirental_lots.run())
        if result.get("enabled"):
            log.info("Samuirental lot diagnostic complete: %s", result)
    except Exception:
        log.exception("Samuirental lot diagnostic failed")


def _renumber_samuirental_lots_on_startup():
    time.sleep(8)
    try:
        result = asyncio.run(renumber_samuirental_lots.run())
        if result.get("enabled"):
            log.info("Samuirental in-place renumbering complete: %s", result)
    except Exception:
        log.exception("Samuirental in-place renumbering failed")


def _install_catalog_handlers(app):
    if not HASHTAG_REORDER_MODE:
        template_capture_mode.install(app,cozy_catalog)
        channel_template_capture.install(app,cozy_catalog)
        emoji_calibration.install(app,cozy_catalog)
    else:
        log.info("Hashtag reorder migration mode: channel capture handlers temporarily disabled")
    mtproto_user_client.install(app,cozy_catalog)
    app.add_handler(CommandHandler("catalog_import",cozy_catalog.cmd_catalog_import),group=-20)
    app.add_handler(CommandHandler("catalog_status",cozy_catalog.cmd_catalog_status),group=-20)
    app.add_handler(CommandHandler("find",cozy_catalog.cmd_find),group=-20)
    app.add_handler(CommandHandler("lot",cozy_catalog.cmd_lot),group=-20)
    if not HASHTAG_REORDER_MODE:
        app.add_handler(MessageHandler(filters.ALL,cozy_catalog.catch_catalog_updates),group=-10)
        post_standardizer.install(app,cozy_catalog)
    log.info("Catalog handlers installed for @%s; hashtag_reorder_mode=%s",cozy_catalog.CATALOG_CHANNEL,HASHTAG_REORDER_MODE)


def main():
    legacy._log_openai_env(); legacy._probe_openai(); _log_google_service_account()
    if not HASHTAG_REORDER_MODE:
        try:
            norm_stats=cozy_catalog.normalize_existing_rows(); log.info("Pre-repair normalize complete: %s",norm_stats)
        except Exception:log.exception("Pre-repair normalize failed")
        try:
            repair_stats=lot_id_repair.repair_sheet(cozy_catalog); log.info("Lot ID repair complete: %s",repair_stats)
        except Exception:log.exception("Lot ID repair failed")
    else:
        log.info("Skipping catalog normalization/repair during hashtag reorder migration")
    legacy.cmd_start=smart_start; legacy.free_text=catalog_aware_free_text
    app=legacy.build_application()
    if not correct_fb_1038134945777547.enabled() and not publish_fb_28520466234226624.enabled() and not publish_airbnb_1074551173034733330.enabled():
        _install_catalog_handlers(app)
    else:
        log.info("One-shot publication/correction mode: catalog/channel mutation handlers are disabled")
        if correct_fb_1038134945777547.enabled():
            threading.Thread(target=_correct_fb_1038134945777547_on_startup,name="correct-fb-1038134945777547",daemon=True).start()
    if publish_fb_1038134945777547.enabled():
        threading.Thread(target=_publish_fb_1038134945777547_on_startup,name="publish-fb-1038134945777547",daemon=True).start()
    if publish_fb_1405490825011828.enabled():
        threading.Thread(target=_publish_fb_1405490825011828_on_startup,name="publish-fb-1405490825011828",daemon=True).start()
    if publish_fb_28520466234226624.enabled():
        threading.Thread(target=_publish_fb_28520466234226624_on_startup,name="publish-fb-28520466234226624",daemon=True).start()
    if publish_airbnb_1074551173034733330.enabled():
        threading.Thread(target=_publish_airbnb_1074551173034733330_on_startup,name="publish-airbnb-1074551173034733330",daemon=True).start()
    if publish_fb_replies_20260828.enabled():
        threading.Thread(target=_publish_fb_replies_20260828_on_startup,name="publish-fb-replies-20260828",daemon=True).start()
    if record_fb_scan_20260828_evening.enabled():
        threading.Thread(target=_record_fb_scan_20260828_evening_on_startup,name="record-fb-scan-20260828-evening",daemon=True).start()
    if record_fb_scan_20260829_morning.enabled():
        threading.Thread(target=_record_fb_scan_20260829_morning_on_startup,name="record-fb-scan-20260829-morning",daemon=True).start()
    if record_fb_scan_20260829_evening.enabled():
        threading.Thread(target=_record_fb_scan_20260829_evening_on_startup,name="record-fb-scan-20260829-evening",daemon=True).start()
    if renumber_samuirental_lots.enabled():
        threading.Thread(target=_renumber_samuirental_lots_on_startup,name="renumber-samuirental-lots",daemon=True).start()
    if diagnose_samuirental_lots.enabled():
        threading.Thread(target=_diagnose_samuirental_lots_on_startup,name="diagnose-samuirental-lots",daemon=True).start()
    samui_news_automation.ensure_started(cozy_catalog)
    # Publishing is intentionally NEVER run from service startup. A deploy/restart
    # must not be able to create a Telegram post. New publications are prepared,
    # preflighted and sent explicitly exactly once.
    if HASHTAG_REORDER_MODE:
        threading.Thread(target=_reorder_hashtags_on_startup,name="hashtag-reorder",daemon=True).start()
    else:
        threading.Thread(target=_bootstrap_catalog,name="catalog-bootstrap",daemon=True).start()
        threading.Thread(target=_standardize_existing,name="post-standardizer",daemon=True).start()
    legacy.run_webhook(app)

if __name__=="__main__":main()

# -*- coding: utf-8 -*-
"""Protect intentional/Premium channel edits from automatic standardization."""
import logging

log = logging.getLogger("manual-edit-guard")


def _has_custom_emoji(msg) -> bool:
    for attr in ("entities", "caption_entities"):
        for ent in getattr(msg, attr, None) or []:
            typ = str(getattr(ent, "type", "") or "").lower()
            if "custom_emoji" in typ:
                return True
    text = (getattr(msg, "text", None) or getattr(msg, "caption", None) or "").strip()
    # Safety fallback for Telegram clients that expose only the fallback text.
    return text.startswith("🔤🔤🔤") and "ОПИСАНИЕ" in text


def apply(post_standardizer):
    original = post_standardizer.standardize_future
    original_external_links = post_standardizer._external_links

    def external_links_without_telegram(links, bot_username=""):
        # Channel captions may already contain older bot/deep links. They are CTA
        # links, not listing resources, so never re-insert them next to Maps/Drive.
        filtered = []
        for href, label in links or []:
            low = str(href or "").strip().lower()
            if low.startswith("tg://") or "t.me/" in low or "telegram.me/" in low:
                continue
            filtered.append((href, label))
        return original_external_links(filtered, bot_username)

    post_standardizer._external_links = external_links_without_telegram

    async def guarded(catalog, update, context):
        # A human administrator editing an existing channel post is authoritative.
        if getattr(update, "edited_channel_post", None) is not None:
            msg = update.edited_channel_post
            log.info(
                "Manual channel edit preserved @%s mid=%s",
                catalog.CATALOG_CHANNEL,
                getattr(msg, "message_id", "?"),
            )
            return

        # Premium Custom Emoji posts are already in the approved Cozy Asia visual
        # template. Bot-API standardization would downgrade the custom letters and
        # digits to ordinary Unicode, so preserve them exactly as published.
        msg = getattr(update, "channel_post", None) or getattr(update, "effective_message", None)
        if msg is not None and _has_custom_emoji(msg):
            log.info(
                "Premium channel post preserved @%s mid=%s",
                catalog.CATALOG_CHANNEL,
                getattr(msg, "message_id", "?"),
            )
            return

        return await original(catalog, update, context)

    post_standardizer.standardize_future = guarded
    log.info("Manual/Premium edit guard + Telegram-link filter applied")

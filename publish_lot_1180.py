# -*- coding: utf-8 -*-
"""One-shot edit-only repair for the Maenam Soi 5 album in @samuirental.

This module NEVER publishes media. It only corrects the existing album caption
(message 4925) after a full Premium/lot-number preflight.
"""
from __future__ import annotations

import logging
import os

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("correct-large-1184")

LARGE_CHANNEL = "samuirental"
LARGE_MESSAGE_ID = 4925
LARGE_LOT_ID = "1184"
BOT_USERNAME = "Cozyasia_villa_bot"


def _truthy(name: str) -> bool:
    return os.getenv(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def enabled() -> bool:
    return _truthy("CORRECT_LARGE_1184")


def _caption_html(lot: str) -> str:
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Полностью меблированная вилла с 2 спальнями и приватным бассейном в тихом районе Маенам, Soi 5. Современная кухня, Smart TV, Wi‑Fi и частная парковка.</blockquote>

📍 Район: Маенам, Soi 5
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 2
🏊 Бассейн: Да, приватный
🐾 Питомцы: Нет

💰 <b>Условия аренды</b>
💵 Цена: 60 000 THB/мес
🔐 Депозит: 50 000 THB
🤝 Комиссия: 5 000 THB
📅 Доступность: до 14 ноября 2026
⚡ Электричество: государственный тариф
💧 Вода: 800 THB/мес
🌊 Пляж Маенам: около 7 минут на авто

✨ Дополнительно: участок 152 м² · 3 кондиционера · холодильник · микроволновка · стиральная машина · уборка 1 раз/мес · бассейн 2 раза/нед · CCTV · 7-Eleven 5 мин · пирс Маенам 13 мин · Fisherman’s Village 15 мин

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Maenam #PoolVilla #KohSamuiRental #CozyAsia"""


def _final_caption(lot: str):
    # Build the COMPLETE final Telegram caption and all Premium entities locally
    # before opening a network connection or touching a channel message.
    from telethon.extensions import html as telethon_html

    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion did not match the expected template")
    preflight = publication_safety.validate_premium_caption(text, entities, lot)
    return text, entities, preflight


async def run() -> dict:
    if not enabled():
        return {"enabled": False}

    # Stage 1: complete offline preflight. No Telegram writes happen before this.
    text, entities, premium_check = _final_caption(LARGE_LOT_ID)

    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(LARGE_CHANNEL)

        # Stage 2: verify the live sequence independently for the big channel.
        lot_check = await publication_safety.assert_next_lot(
            client,
            channel,
            LARGE_LOT_ID,
            exclude_ids={LARGE_MESSAGE_ID},
        )

        # Stage 3: verify that we are editing the intended existing album only.
        msg = await client.get_messages(channel, ids=LARGE_MESSAGE_ID)
        current = getattr(msg, "message", None) or ""
        signature = ("Маенам", "60 000", "14 ноября 2026")
        if not msg or not all(term.lower() in current.lower() for term in signature):
            raise RuntimeError("Target message 4925 is not the Maenam Soi 5 listing; aborting")

        # If already correct, do nothing. Otherwise make exactly one in-place edit.
        current_lot = publication_safety.lot_from_message(msg)
        current_urls = [str(getattr(e, "url", "") or "") for e in (getattr(msg, "entities", None) or [])]
        already = current_lot == LARGE_LOT_ID and any(
            f"start=rent_{LARGE_LOT_ID}" in u for u in current_urls
        )
        if not already:
            await client.edit_message(
                channel,
                LARGE_MESSAGE_ID,
                text,
                formatting_entities=entities,
                link_preview=False,
            )

        # Stage 4: read back from Telegram and verify the final live state.
        verify = await client.get_messages(channel, ids=LARGE_MESSAGE_ID)
        final_lot = publication_safety.lot_from_message(verify)
        final_text = getattr(verify, "message", None) or ""
        final_urls = [str(getattr(e, "url", "") or "") for e in (getattr(verify, "entities", None) or [])]
        if final_lot != LARGE_LOT_ID:
            raise RuntimeError(f"Read-back lot mismatch: {final_lot!r}")
        if not any(f"start=rent_{LARGE_LOT_ID}" in u for u in final_urls):
            raise RuntimeError("Read-back deep link mismatch")
        if not all(term.lower() in final_text.lower() for term in signature):
            raise RuntimeError("Read-back listing signature mismatch")

        result = {
            "result": "already" if already else "edited_in_place",
            "channel": LARGE_CHANNEL,
            "message_id": LARGE_MESSAGE_ID,
            "lot": LARGE_LOT_ID,
            "lot_preflight": lot_check,
            "premium_preflight": premium_check,
        }
        log.info("Large-channel lot correction complete: %s", result)
        return result
    finally:
        await client.disconnect()

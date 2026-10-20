# -*- coding: utf-8 -*-
"""Restore the full Cozy Asia Premium caption template for the retained batch."""
from __future__ import annotations

import asyncio
import html
import json
import re

import cozy_catalog
import mtproto_user_client
import post_layout_v6_premium as premium

CHANNEL = "arenda_vill_samui"
BOT = "Cozyasia_villa_bot"
COMMISSION = 5000
TARGETS = {
    1711: "1221", 1721: "1222", 1731: "1223", 1741: "1224", 1751: "1225",
    1761: "1226", 1771: "1227", 1781: "1228", 1791: "1229", 1801: "1230",
}


def _esc(value: object, limit: int = 180) -> str:
    return html.escape(str(value or "").strip()[:limit])


def _value(row, key: str, fallback: str = "уточняется") -> str:
    value = str(row.get(key) or "").strip()
    return value if value else fallback


def _premium_lot(lot: str) -> str:
    parts = [premium._tg(premium.LOT_IDS[ch], "🔤") for ch in "ЛОТ"]
    parts += [" ", premium._tg(premium.LOT_IDS["№"], "🔤"), " "]
    for ch in lot:
        parts.append(premium._tg(premium.DIGIT_IDS[ch], ch + "️⃣"))
    return "".join(parts)


def _premium_word(word: str) -> str:
    return premium._premium_word(word, premium.CTA_IDS)


def _source_url(row: dict) -> str:
    source = str(row.get("исходный_текст") or "")
    found = re.search(r"https?://(?:www\.)?facebook\.com/[^\s<>]+", source)
    return found.group(0).rstrip(".,)") if found else "https://cozyasia-villas.onrender.com"


def build_caption(row: dict, lot: str) -> str:
    district = _value(row, "район")
    typ = _value(row, "тип", "вилла")
    bedrooms = _value(row, "спальни")
    bathrooms = _value(row, "ванные")
    pool = "приватный" if str(row.get("тип_бассейна") or "").lower() == "private" else _value(row, "бассейн")
    description = _value(row, "описание", f"Вилла с {bedrooms} спальнями в районе {district} на острове Самуи.")
    price = _value(row, "цена_месяц_thb")
    deposit = _value(row, "депозит_thb")
    availability = _value(row, "доступность", "подтверждается на указанные даты")
    electricity = _value(row, "электричество")
    water = _value(row, "вода")
    sea = _value(row, "до_моря_м")
    rent = f"https://t.me/{BOT}?start=rent_{lot}"
    search = f"https://t.me/{BOT}?start=search"
    source = _source_url(row)
    map_url = "https://www.google.com/maps/search/?api=1&query=" + html.escape(district) + "+Koh+Samui"
    return "\n".join([
        _premium_lot(lot), "",
        f'{premium._tg(premium.DESC_ID, "💬")} <b>ОПИСАНИЕ</b>',
        f"<blockquote>{_esc(description, 360)}</blockquote>", "",
        f"📍 Район: {_esc(district)}",
        f'🗺 <a href="{map_url}"><b>ГЕОЛОКАЦИЯ</b></a>',
        f"🏠 Тип: {_esc(typ)}",
        f"🛏 Спальни: {_esc(bedrooms)}",
        f"🛁 Ванные: {_esc(bathrooms)}",
        f"🏊 Бассейн: {_esc(pool)}",
        f"🐾 Питомцы: {_esc(_value(row, 'питомцы'))}", "",
        "💰 <b>УСЛОВИЯ АРЕНДЫ</b>",
        f"💵 Цена: {_esc(price)} THB/мес.",
        f"🤝 Комиссия Cozy Asia: {COMMISSION:,} THB",
        f"🔐 Депозит: {_esc(deposit)}",
        f"📅 Доступность: {_esc(availability)}",
        f"⚡ Электричество: {_esc(electricity)}",
        f"💧 Вода: {_esc(water)}",
        f"🧹 Уборка: уточняется",
        f"🌊 До моря: {_esc(sea)}", "",
        f'<a href="{html.escape(source, quote=True)}"><b>📸 ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>',
        '<a href="https://cozyasia-villas.onrender.com"><b>🌐 САЙТ COZY ASIA</b></a>', "",
        _premium_word("ОСТАВИТЬ"), _premium_word("ЗАЯВКУ"), "",
        f'{premium._tg(premium.RIGHT_ID, "👉")} <a href="{rent}"><b>ЖМИ ЗДЕСЬ</b></a> {premium._tg(premium.LEFT_ID, "👈")}', "",
        "Оператор: @cozy_asia", "",
        f'🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search}"><b>НАПИСАТЬ БОТУ</b></a> 🤖', "",
        "#АрендаСамуи #ВиллаСамуи #CozyAsia",
    ])


async def run() -> dict:
    cozy_catalog.CATALOG_CHANNEL = CHANNEL
    rows = {str(r.get("telegram_message_id") or ""): r for r in cozy_catalog.load_catalog_rows(True)}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    edited = []
    try:
        channel = await client.get_entity(f"@{CHANNEL}")
        from telethon.extensions import html as telethon_html
        for mid, lot in TARGETS.items():
            row = rows.get(str(mid))
            if not row:
                raise RuntimeError(f"Lots row not found for Telegram message {mid}")
            message = await client.get_messages(channel, ids=mid)
            if not message:
                raise RuntimeError(f"Telegram message {mid} not found")
            caption_html = build_caption(row, lot)
            text, entities = telethon_html.parse(caption_html)
            try:
                await client.edit_message(channel, mid, text, formatting_entities=entities, link_preview=False)
            except Exception as exc:
                if exc.__class__.__name__ != "MessageNotModifiedError":
                    raise
            check = await client.get_messages(channel, ids=mid)
            check_text = str(getattr(check, "message", "") or "")
            custom_count = sum(1 for ent in (getattr(check, "entities", None) or []) if type(ent).__name__ == "MessageEntityCustomEmoji")
            if not check or "ОПИСАНИЕ" not in check_text or custom_count < 10:
                raise RuntimeError(f"read-back failed for {mid}/{lot}")
            edited.append({"message_id": mid, "lot": lot, "caption_length": len(check_text), "custom_emoji_count": custom_count, "url": f"https://t.me/{CHANNEL}/{mid}"})
            await asyncio.sleep(0.7)
        return {"ok": True, "channel": CHANNEL, "edited": edited}
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    print("FB_BATCH_TEMPLATE_REPAIR=" + json.dumps(asyncio.run(run()), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    run_service_mode()

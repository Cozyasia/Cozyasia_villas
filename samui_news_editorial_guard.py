# -*- coding: utf-8 -*-
"""Strict editorial gate for Samui News.

The news channel is editorial, not a classifieds surface. This module blocks
commercial offers (rentals, sales, promotions and service ads) and removes the
old permissive rule that treated any long post from a regional chat as news.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time

log = logging.getLogger("samui-news-editorial-guard")

_COMMERCIAL_SOURCE_RE = re.compile(
    r"(?:объявлен|барахолк|недвижим|аренд[аы]\s+(?:вилл|дом|авто|байк)|"
    r"rentals?|property|real\s+estate|marketplace|classifieds?|buy\s*&?\s*sell|"
    r"куплю|продам|сдам|ให้เช่า|ซื้อขาย)",
    re.I,
)

_STRONG_OFFER_RE = re.compile(
    r"(?:\bfor\s+rent\b|\bfor\s+sale\b|\bavailable\s+for\s+rent\b|"
    r"\brent(?:al)?\s+(?:car|cars|bike|bikes|motorbike|motorbikes|scooter|villa|house|condo|room)\b|"
    r"\b(?:car|bike|motorbike|scooter|villa|house|condo|room)\s+rental\b|"
    r"\b(?:villa|house|condo|room|car|bike|motorbike|scooter)\s+for\s+rent\b|"
    r"аренда\s+(?:авто|автомобил|машин|байк|мото|скутер|вилл|дом|квартир|апартамент|студи|комнат)|"
    r"(?:вилл|дом|квартир|апартамент|студи|комнат|авто|машин|байк|мото|скутер).{0,40}(?:в\s+аренду|сда[её]тся|сдам)|"
    r"(?:прода[её]тся|продам).{0,50}(?:вилл|дом|квартир|авто|машин|байк|мото|земл)|"
    r"(?:вилл|дом|квартир|авто|машин|байк|мото|земл).{0,50}(?:прода[её]тся|продам)|"
    r"ให้เช่า|ขาย(?:บ้าน|รถ|ที่ดิน|คอนโด))",
    re.I | re.S,
)

_PRICE_PERIOD_RE = re.compile(
    r"(?:\d[\d\s.,]*\s*(?:thb|บาท|бат)|฿\s*\d[\d\s.,]*)"
    r"\s*(?:/|за\s+|per\s+)?(?:day|daily|night|month|monthly|день|сутк\w*|ноч\w*|мес\w*|วัน|คืน|เดือน)\b",
    re.I,
)

_MARKETING_RE = re.compile(
    r"(?:скидк|акци[яи]|промо|promotion|promo\b|book\s+now|заброниру|"
    r"пишите\s+в\s+(?:лич|лс)|whatsapp|line\s*[:@]|commission|комисси|deposit|депозит|"
    r"предлагается|предлагаем|свободн[аоы]\s+(?:с|на)|available\s+(?:now|from)|"
    r"цена\s+от|стоимость\s+от|от\s+\d[\d\s.,]*\s*(?:thb|бат|฿))",
    re.I,
)

_ASSET_OR_SERVICE_RE = re.compile(
    r"(?:вилл|дом\b|квартир|апартамент|студи|комнат|кондо|недвижим|"
    r"авто|автомобил|машин|байк|мото|скутер|трансфер|такси|экскурс|тур\b|"
    r"villa|house|condo|apartment|room|property|real\s+estate|car\b|cars\b|"
    r"bike|motorbike|scooter|transfer|taxi|tour\b|บริการ|บ้าน|รถ|มอเตอร์ไซค์|คอนโด)",
    re.I,
)

_NEWS_EVENT_RE = re.compile(
    r"(?:earthquake|tremor|seismic|warning|storm|flood|landslide|accident|crash|collision|"
    r"fire|blaze|explosion|police|arrest|charged|investigat|missing|rescue|drown|death|killed|injured|"
    r"immigration|visa|law\b|regulation|government|municipal|authorit|court|airport|flight|ferry|"
    r"boat\b|pier|road|traffic|closure|closed|reopen|resum|cancel|power\s+outage|water\s+outage|"
    r"electricity|weather|festival|public\s+event|tourism|tourist\s+arrivals?|statistics|record\s+number|"
    r"environment|pollution|beach\s+cleanup|waste|hospital|public\s+health|school|official|"
    r"землетряс|сейсм|предупреж|шторм|наводнен|ополз|авари|дтп|столкнов|пожар|взрыв|"
    r"полици|задерж|арест|обвин|расслед|пропал|розыск|спас|утон|погиб|ранен|"
    r"иммигра|виз|закон|регламент|правил|постановлен|власт|администрац|суд|аэропорт|рейс|паром|"
    r"лодк|пирс|дорог|движен|перекры|закры|возобнов|отмен|электр|отключ|водоснаб|погод|"
    r"фестивал|мероприят|туризм|турист(?:ов|ы)|статист|рекорд|эколог|загрязнен|пляж|мусор|"
    r"больниц|госпитал|здравоохран|школ|официальн|"
    r"แผ่นดินไหว|พายุ|น้ำท่วม|ดินถล่ม|อุบัติเหตุ|ไฟไหม้|ระเบิด|ตำรวจ|จับกุม|สอบสวน|สูญหาย|"
    r"กู้ภัย|เสียชีวิต|บาดเจ็บ|ตรวจคนเข้าเมือง|วีซ่า|กฎหมาย|เทศบาล|ศาล|สนามบิน|เที่ยวบิน|"
    r"เรือเฟอร์รี่|ท่าเรือ|ถนน|จราจร|ปิด|เปิดใหม่|ยกเลิก|ไฟฟ้าดับ|น้ำประปา|อากาศ|เทศกาล|"
    r"ท่องเที่ยว|สิ่งแวดล้อม|โรงพยาบาล|โรงเรียน|ประกาศ)",
    re.I,
)

_OPENING_WORD_RE = re.compile(
    r"(?:opened|opening|launch(?:ed)?|inaugurat|открыл(?:ся|ась|ось|ись)?|открытие|запустил|запуск|เปิด(?:ตัว|ให้บริการ)?|เปิดใหม่)",
    re.I,
)
_SIGNIFICANT_PLACE_RE = re.compile(
    r"(?:hotel|resort|restaurant|hospital|clinic|school|pier|airport|terminal|road|bridge|mall|museum|"
    r"отел|гостиниц|резорт|ресторан|госпитал|больниц|клиник|школ|пирс|аэропорт|терминал|дорог|мост|"
    r"торгов(?:ый|ого)\s+центр|музе|โรงแรม|รีสอร์ท|ร้านอาหาร|โรงพยาบาล|โรงเรียน|ท่าเรือ|สนามบิน|ถนน|สะพาน|ห้าง)",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_commercial_source(source_name: str) -> bool:
    return bool(_COMMERCIAL_SOURCE_RE.search(_norm(source_name)))


def is_commercial_offer(text: str, source_name: str = "") -> bool:
    text = _norm(text)
    if is_commercial_source(source_name):
        return True
    if _STRONG_OFFER_RE.search(text):
        return True
    has_asset = bool(_ASSET_OR_SERVICE_RE.search(text))
    has_period_price = bool(_PRICE_PERIOD_RE.search(text))
    has_marketing = bool(_MARKETING_RE.search(text))
    return has_asset and (has_period_price or has_marketing)


def is_editorial_news_text(text: str, source_name: str = "") -> bool:
    text = _norm(text)
    if len(text) < 25:
        return False
    if is_commercial_offer(text, source_name):
        return False
    if _NEWS_EVENT_RE.search(text):
        return True
    return bool(_OPENING_WORD_RE.search(text) and _SIGNIFICANT_PLACE_RE.search(text))


def is_editorial_item(item: dict) -> bool:
    text = " ".join(
        x for x in (item.get("title", ""), item.get("text", "")) if x
    )
    return is_editorial_news_text(text, item.get("source_name", ""))


def _parse_message_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for token in re.split(r"[;,\s]+", raw or ""):
        if not token.isdigit():
            continue
        value = int(token)
        if value > 0 and value not in ids:
            ids.append(value)
    return ids


async def _delete_retracted_messages(mt, catalog, channel: str, message_ids: list[int]):
    client = await mt._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session unavailable for Samui News retraction")
    try:
        entity = await client.get_entity(channel)
        await client.delete_messages(entity, message_ids, revoke=True)
        log.info("Retracted Samui News messages: channel=%s ids=%s", channel, message_ids)
    finally:
        await client.disconnect()


def _schedule_retractions(mt, catalog, channel: str):
    message_ids = _parse_message_ids(os.environ.get("SAMUI_NEWS_RETRACT_MESSAGE_IDS", ""))
    if not message_ids:
        return

    def worker():
        time.sleep(5)
        try:
            asyncio.run(_delete_retracted_messages(mt, catalog, channel, message_ids))
        except Exception:
            log.exception("Could not retract Samui News messages: ids=%s", message_ids)

    threading.Thread(target=worker, name="samui-news-retract", daemon=True).start()


def apply(news, source_patch, mt, catalog):
    """Install strict editorial filtering after the regional source patch."""
    if getattr(news, "_EDITORIAL_GUARD_V1", False):
        return
    news._EDITORIAL_GUARD_V1 = True

    source_patch._looks_newsworthy = is_editorial_news_text

    original_fetch = news._fetch_candidates
    original_compose = news._compose

    def strict_fetch():
        items = original_fetch()
        kept = [item for item in items if is_editorial_item(item)]
        blocked = len(items) - len(kept)
        if blocked:
            log.info("Editorial guard blocked %s non-news/commercial candidates", blocked)
        return kept

    def strict_compose(items, slot):
        kept = [item for item in items if is_editorial_item(item)]
        if not kept:
            raise RuntimeError("Editorial guard rejected all Samui News candidates")
        return original_compose(kept, slot)

    news._fetch_candidates = strict_fetch
    news._compose = strict_compose
    _schedule_retractions(mt, catalog, news.CHANNEL)
    log.info("Samui News strict editorial guard enabled: classifieds/rentals/sales/promotions blocked")

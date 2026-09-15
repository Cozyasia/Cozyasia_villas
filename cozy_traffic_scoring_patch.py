# -*- coding: utf-8 -*-
"""Precision-first scoring patch for Cozy Traffic lead detection.

The first live scan exposed two root causes:
1) generic substring matching treated `дом` inside words like `переводом` as housing;
2) listing/advertising copy could score as a lead without a real renter request.

This patch only changes lead classification. Telegram access stays read-only.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("cozy-traffic-scoring-patch")

HOUSING_RE = re.compile(
    r"(?<!\w)(?:жиль\w*|вилл\w*|дом(?:а|у|ом|е|ы|ов|ам|ами|ах)?|квартир\w*|"
    r"апартамент\w*|студи\w*|кондо|таунхаус\w*|недвижим\w*|спальн\w*|"
    r"bungalows?|villas?|houses?|condos?|apartments?|accommodations?|properties?)(?!\w)",
    re.I,
)

REQUEST_RE = re.compile(
    r"(?<!\w)(?:ищу|ищем|сниму|снимем|нужен|нужна|нужно|нужны|ищется|"
    r"подскажите|посоветуйте|порекомендуйте|рекомендуйте)(?!\w)|"
    r"\bкто\s+(?:сда(?:е|ё)т|может\s+сдать|знает)\b|"
    r"\bесть\s+ли\b|\bв\s+поиске\b|\blooking\s+for\b|\bneed\b",
    re.I,
)

# Strong advertising/listing markers. These are deliberately narrow so that
# a renter asking "подскажите стоимость" is not rejected just for that word.
OFFER_RE = re.compile(
    r"(?im)(?:^|\n)\s*(?:🔥\s*)?аренда\s*[:!]|"
    r"\b(?:property\s*id|код\s+объекта)\b|"
    r"\bпо\s+вопросам\s+(?:бронирования|аренды)\b|"
    r"\bпишите\s+в\s+(?:л/?с|личк\w*)\b|"
    r"\b(?:сутки|месяц)\s*:|"
    r"\bгодовой\s+контракт\b|"
    r"\bконтракт\s+(?:от|на)\s+\d|"
    r"\bпредлагается\s+в\s+аренду\b|"
    r"\bсдам\b|\bсда(?:е|ё)тся\b|"
    r"\bсвободн(?:а|о|ы|ен)\b"
)


def _score(runtime, text: str):
    n = runtime._norm(text)
    has_housing = bool(HOUSING_RE.search(n))
    has_intent = bool(REQUEST_RE.search(n))
    has_offer = bool(OFFER_RE.search(n))

    # v0.2 is precision-first: only explicit renter requests enter the queue.
    if not has_housing or not has_intent:
        return 0, "LOW", ("not_active_housing_request",)
    if has_offer:
        return 0, "LOW", ("promotional_or_listing_copy",)

    score = 50
    reasons = ["active_request", "housing"]
    if runtime._contains_any(n, runtime.SAMUI_TERMS):
        score += 15; reasons.append("samui")
    if runtime._contains_any(n, runtime.RENTAL_TERMS):
        score += 10; reasons.append("rental")
    if runtime.BUDGET_RE.search(n):
        score += 10; reasons.append("budget")
    if runtime.BEDROOM_RE.search(n):
        score += 5; reasons.append("bedrooms")
    if runtime.DATE_RE.search(n) or runtime.DURATION_RE.search(n):
        score += 5; reasons.append("dates_or_duration")
    if any(alias in n for aliases in runtime.DISTRICTS.values() for alias in aliases):
        score += 5; reasons.append("district")
    if re.search(r"\b(?:с\s+)?(?:собак|кот|кошк|питомц|животн)", n):
        score += 3; reasons.append("pets")
    if runtime.OCCUPANTS_RE.search(n):
        score += 2; reasons.append("occupants")

    score = min(100, score)
    band = "HOT" if score >= 70 else "WARM" if score >= 50 else "INTERESTING" if score >= 35 else "LOW"
    return score, band, tuple(reasons)


def apply(runtime) -> None:
    runtime.score_rental_request = lambda text: _score(runtime, text)
    log.info("Cozy Traffic precision scoring patch applied")

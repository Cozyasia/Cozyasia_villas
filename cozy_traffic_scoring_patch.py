# -*- coding: utf-8 -*-
"""Precision-first scoring patch for Cozy Traffic lead detection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
import re

log = logging.getLogger("cozy-traffic-scoring-patch")

HOUSING_RE = re.compile(
    r"(?<!\w)(?:жиль\w*|вилл\w*|дом(?:а|у|ом|е|ы|ов|ам|ами|ах)?|квартир\w*|"
    r"апартамент\w*|студи\w*|кондо|таунхаус\w*|недвижим\w*|спальн\w*|"
    r"bungalows?|villas?|houses?|condos?|apartments?|accommodations?|properties?)(?!\w)",
    re.I,
)

# Used only for request-to-object proximity. Ambiguous Russian "дома" is
# deliberately excluded because it often means "at home", not houses.
STRONG_HOUSING_RE = re.compile(
    r"(?<!\w)(?:жиль\w*|вилл\w*|дом|доме|дому|домом|домов|квартир\w*|"
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

RENTAL_SIGNAL_RE = re.compile(
    r"(?<!\w)(?:снять|сниму|снимем|арендовать|арендую|арендуем|аренда|rent|rental)(?!\w)",
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


def _request_near_housing(text: str, max_distance: int = 70) -> bool:
    requests = list(REQUEST_RE.finditer(text))
    housing = list(STRONG_HOUSING_RE.finditer(text))
    return any(abs(req.start() - obj.start()) <= max_distance for req in requests for obj in housing)


def _detail_count(runtime, text: str) -> int:
    count = 0
    if runtime.BUDGET_RE.search(text):
        count += 1
    if runtime.BEDROOM_RE.search(text):
        count += 1
    if runtime.DATE_RE.search(text) or runtime.DURATION_RE.search(text):
        count += 1
    if any(alias in text for aliases in runtime.DISTRICTS.values() for alias in aliases):
        count += 1
    return count


def _score(runtime, text: str):
    n = runtime._norm(text)
    has_housing = bool(HOUSING_RE.search(n))
    has_intent = bool(REQUEST_RE.search(n))
    has_offer = bool(OFFER_RE.search(n))
    has_rental_signal = bool(RENTAL_SIGNAL_RE.search(n))
    near_housing_request = _request_near_housing(n)
    detail_count = _detail_count(runtime, n)

    if not has_housing or not has_intent:
        return 0, "LOW", ("not_active_housing_request",)
    if has_offer:
        return 0, "LOW", ("promotional_or_listing_copy",)

    # Generic "ищу/нужна" plus a stray word "дом/жилье" is not enough.
    # Require explicit rental language, close request-to-housing proximity,
    # or at least two concrete rental details for longer natural requests.
    if not (has_rental_signal or near_housing_request or detail_count >= 2):
        return 0, "LOW", ("context_not_rental_housing",)

    score = 50
    reasons = ["active_request", "housing"]
    if runtime._contains_any(n, runtime.SAMUI_TERMS):
        score += 15; reasons.append("samui")
    if has_rental_signal or runtime._contains_any(n, runtime.RENTAL_TERMS):
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


def filter_recent(leads, max_age_days: int, *, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now.astimezone(timezone.utc) - timedelta(days=max(1, int(max_age_days)))
    kept = []
    for lead in leads:
        date = getattr(lead, "message_date", None)
        if not isinstance(date, datetime):
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if date.astimezone(timezone.utc) >= cutoff:
            kept.append(lead)
    return kept


def apply(runtime) -> None:
    if getattr(runtime, "_precision_scoring_patch_applied", False):
        return
    original_scan = runtime.scan_public_source
    runtime.score_rental_request = lambda text: _score(runtime, text)

    async def scan_public_source(*args, **kwargs):
        leads = await original_scan(*args, **kwargs)
        try:
            max_age_days = int(os.getenv("COZY_TRAFFIC_MAX_LEAD_AGE_DAYS", "30"))
        except Exception:
            max_age_days = 30
        return filter_recent(leads, max(1, min(max_age_days, 90)))

    runtime.scan_public_source = scan_public_source
    runtime._precision_scoring_patch_applied = True
    log.info("Cozy Traffic precision scoring patch applied")

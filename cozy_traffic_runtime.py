# -*- coding: utf-8 -*-
"""Read-only Telegram audience discovery and rental-intent scoring for Cozy Asia.

This module reuses an already-authorized Cozy Asia MTProto user session. It
contains no Telegram write/join/delete operations. All Telegram activity here
is limited to public source search, entity resolution and message reads.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
import re
import threading
import time
from typing import Any, Callable, Iterable

import mtproto_user_client

log = logging.getLogger("cozy-traffic")

DEFAULT_SEEDS = (
    "самуи", "самуи чат", "самуи аренда", "аренда самуи", "жилье самуи",
    "вилла самуи", "виллы самуи", "русские самуи", "самуи русские",
    "самуи объявления", "koh samui russian", "samui russian",
    "ламай самуи", "маенам самуи", "чавенг самуи", "бопхут самуи",
    "банграк самуи", "плай лаем самуи",
)
OWN_USERNAMES = {"samuirental", "arenda_vill_samui", "cozy_asia"}
SAMUI_TERMS = (
    "самуи", "samui", "koh samui", "ко самуи", "кох самуи",
    "ламай", "lamai", "маенам", "maenam", "чавенг", "chaweng",
    "бопхут", "bophut", "бо пхут", "банграк", "bangrak",
    "плай лаем", "plai laem", "чонг мон", "choeng mon",
    "липа ной", "lipa noi", "натон", "nathon", "банг по", "bang po",
    "талинг нгам", "taling ngam", "на муанг", "na muang",
)
HOUSING_TERMS = (
    "жиль", "вилл", "дом", "квартир", "апартамент", "студи", "кондо",
    "таунхаус", "недвижим", "bungalow", "villa", "house", "condo",
    "apartment", "accommodation", "property",
)
RENTAL_TERMS = (
    "аренд", "снять", "сниму", "снимем", "снимет", "rent", "rental",
    "ищу жиль", "ищем жиль", "ищу дом", "ищем дом", "ищу вил", "ищем вил",
)
NON_HOUSING_RENT_TERMS = (
    "байк", "скутер", "мото", "машин", "авто", "car rent", "bike rent",
    "обмен валют", "экскурс", "лодк", "катер",
)
INTENT_TERMS = (
    "ищу", "ищем", "сниму", "снимем", "нужен", "нужна", "нужно",
    "подскажите", "посоветуйте", "кто сда", "есть ли", "looking for", "need",
)
OFFER_TERMS = (
    "сдам", "сдается", "сдаётся", "доступна", "доступно", "available for rent",
    "предлагаем", "свободна вилла", "свободный дом",
)
CYRILLIC_RE = re.compile(r"[а-яё]", re.I)
ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)
WS_RE = re.compile(r"\s+")
_STARTED = False
_LOCK = threading.Lock()

DISTRICTS = {
    "Ламай": ("ламай", "lamai"),
    "Маенам": ("маенам", "maenam", "mae nam"),
    "Чавенг": ("чавенг", "chaweng"),
    "Бопхут": ("бопхут", "bophut", "бо пхут", "bo phut"),
    "Банграк": ("банграк", "bangrak", "bang rak"),
    "Плай Лаем": ("плай лаем", "plai laem"),
    "Чонг Мон": ("чонг мон", "choeng mon", "chong mon"),
    "Липа Ной": ("липа ной", "lipa noi"),
    "Натон": ("натон", "nathon"),
    "Банг По": ("банг по", "bang po"),
    "Талинг Нгам": ("талинг нгам", "taling ngam"),
    "На Муанг": ("на муанг", "na muang"),
}
MONTHS = "январ[ья]|феврал[ья]|март[ае]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[ае]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья]"
DATE_RE = re.compile(rf"\b(?:с\s+)?(\d{{1,2}}[./-]\d{{1,2}}(?:[./-]\d{{2,4}})?|\d{{1,2}}\s+(?:{MONTHS})|(?:{MONTHS}))\b", re.I)
DURATION_RE = re.compile(r"\b((?:\d+|один|одна|два|две|три|четыре|пять|шесть)\s+(?:дн(?:я|ей)|недел(?:ю|и|ь)|месяц(?:а|ев)?|год(?:а|ов)?))\b", re.I)
BUDGET_RE = re.compile(r"(?:бюджет\s*(?:до\s*)?|до\s+)(\d[\d\s.,]*?)\s*(бат|thb|฿|₽|руб(?:лей|ля)?|rub|\$|usd|€|eur)(?=\s|$|[,.;:!?])", re.I)
BEDROOM_RE = re.compile(r"\b(\d+)\s*(?:спальн(?:я|и|ь)|bed(?:room)?s?|br)\b", re.I)
OCCUPANTS_RE = re.compile(r"\b(?:нас\s*)?(\d+)\s*(?:человек(?:а)?|взросл(?:ых|ые)|гост(?:я|ей))\b", re.I)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _enabled(name: str) -> bool:
    return os.getenv(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def _norm(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip().lower().replace("ё", "е"))


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in terms)


def _russian_share(texts: Iterable[str]) -> float:
    total = russian = 0
    for text in texts:
        letters = ALPHA_RE.findall(text or "")
        if not letters:
            continue
        total += 1
        if len(CYRILLIC_RE.findall(text or "")) / len(letters) >= 0.50:
            russian += 1
    return (russian / total) if total else 0.0


@dataclass(frozen=True, slots=True)
class SourceFinding:
    telegram_id: int
    title: str
    username: str
    kind: str
    score: int
    russian_share: float
    recent_count: int
    recent_30d: int
    housing_points: int
    samui_points: int
    rental_points: int
    russian_points: int
    activity_points: int
    discussion_points: int
    penalty: int


@dataclass(frozen=True, slots=True)
class LeadFinding:
    source_username: str
    source_title: str
    message_id: int
    message_date: datetime
    text: str
    score: int
    band: str
    districts: tuple[str, ...]
    date_text: str | None
    duration_text: str | None
    budget_amount: int | None
    budget_currency: str | None
    bedrooms: int | None
    occupants: int | None
    pets: bool | None
    reasons: tuple[str, ...]

    @property
    def link(self) -> str:
        return f"https://t.me/{self.source_username}/{self.message_id}"


def _score_source(*, entity: Any, telegram_id: int, texts: list[str], dates: list[datetime]) -> SourceFinding:
    title = str(getattr(entity, "title", "") or "").strip()
    username = str(getattr(entity, "username", "") or "").strip()
    kind = "group" if bool(getattr(entity, "megagroup", False)) or entity.__class__.__name__.lower().startswith("chat") else "channel"
    corpus = "\n".join([title, username, *texts])
    housing_points = 20 if _contains_any(corpus, HOUSING_TERMS) else 0
    samui_points = 30 if _contains_any(corpus, SAMUI_TERMS) else 0
    rental_points = 20 if _contains_any(corpus, RENTAL_TERMS) else 0
    rus_share = _russian_share(texts)
    if rus_share >= 0.60:
        russian_points = 15
    elif rus_share >= 0.30:
        russian_points = 10
    elif CYRILLIC_RE.search(title):
        russian_points = 5
    else:
        russian_points = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent_30d = sum(1 for d in dates if d >= cutoff)
    if recent_30d >= 20:
        activity_points = 10
    elif recent_30d >= 10:
        activity_points = 8
    elif recent_30d >= 5:
        activity_points = 5
    elif recent_30d >= 1:
        activity_points = 3
    else:
        activity_points = 0
    discussion_points = 5 if kind == "group" else 0
    penalty = 0
    if _contains_any(corpus, NON_HOUSING_RENT_TERMS) and not _contains_any(corpus, HOUSING_TERMS):
        penalty += 35
    if username.lower() in OWN_USERNAMES:
        penalty += 100
    total = max(0, min(100, housing_points + samui_points + rental_points + russian_points + activity_points + discussion_points - penalty))
    return SourceFinding(telegram_id=telegram_id, title=title, username=username, kind=kind, score=total,
        russian_share=rus_share, recent_count=len(texts), recent_30d=recent_30d, housing_points=housing_points,
        samui_points=samui_points, rental_points=rental_points, russian_points=russian_points,
        activity_points=activity_points, discussion_points=discussion_points, penalty=penalty)


def _currency(raw: str) -> str:
    token = raw.lower()
    if token in {"бат", "thb", "฿"}: return "THB"
    if token in {"₽", "руб", "рубля", "рублей", "rub"}: return "RUB"
    if token in {"$", "usd"}: return "USD"
    return "EUR"


def _int_amount(raw: str) -> int:
    digits = re.sub(r"[^0-9]", "", raw or "")
    return int(digits) if digits else 0


def score_rental_request(text: str) -> tuple[int, str, tuple[str, ...]]:
    n = _norm(text); score = 0; reasons: list[str] = []
    has_housing = _contains_any(n, HOUSING_TERMS); has_intent = _contains_any(n, INTENT_TERMS)
    has_samui = _contains_any(n, SAMUI_TERMS); has_rental = _contains_any(n, RENTAL_TERMS)
    if _contains_any(n, OFFER_TERMS) and not has_intent:
        return 0, "LOW", ("offer_not_request",)
    if has_intent: score += 30; reasons.append("active_request")
    if has_housing: score += 20; reasons.append("housing")
    if has_samui: score += 15; reasons.append("samui")
    if has_rental: score += 10; reasons.append("rental")
    if BUDGET_RE.search(n): score += 10; reasons.append("budget")
    if BEDROOM_RE.search(n): score += 5; reasons.append("bedrooms")
    if DATE_RE.search(n) or DURATION_RE.search(n): score += 5; reasons.append("dates_or_duration")
    if any(alias in n for aliases in DISTRICTS.values() for alias in aliases): score += 5; reasons.append("district")
    if re.search(r"\b(?:с\s+)?(?:собак|кот|кошк|питомц|животн)", n): score += 3; reasons.append("pets")
    if OCCUPANTS_RE.search(n): score += 2; reasons.append("occupants")
    if not has_housing: score = min(score, 25)
    score = min(100, score)
    band = "HOT" if score >= 70 else "WARM" if score >= 50 else "INTERESTING" if score >= 35 else "LOW"
    return score, band, tuple(reasons)


def extract_request_fields(text: str) -> dict[str, Any]:
    n = _norm(text)
    districts = tuple(name for name, aliases in DISTRICTS.items() if any(alias in n for alias in aliases))
    date_m = DATE_RE.search(n); duration_m = DURATION_RE.search(n); budget_m = BUDGET_RE.search(n)
    bedroom_m = BEDROOM_RE.search(n); occupants_m = OCCUPANTS_RE.search(n)
    pets: bool | None = None
    if re.search(r"\bбез\s+(?:животных|питомцев|собаки|кота|кошки)\b", n): pets = False
    elif re.search(r"\b(?:с\s+)?(?:собак(?:ой|а)?|кот(?:ом|а)?|кошк(?:ой|а)|питомц(?:ем|ами)|животн(?:ым|ыми))\b", n): pets = True
    return {"districts": districts, "date_text": date_m.group(1) if date_m else None,
        "duration_text": duration_m.group(1) if duration_m else None,
        "budget_amount": _int_amount(budget_m.group(1)) if budget_m else None,
        "budget_currency": _currency(budget_m.group(2)) if budget_m else None,
        "bedrooms": int(bedroom_m.group(1)) if bedroom_m else None,
        "occupants": int(occupants_m.group(1)) if occupants_m else None, "pets": pets}


async def discover_public_sources(client: Any, *, seeds: Iterable[str] = DEFAULT_SEEDS, search_limit: int = 20,
    recent_limit: int = 30, max_candidates: int = 50,
    search_request_factory: Callable[[str, int], Any] | None = None, peer_id_fn: Callable[[Any], int] | None = None) -> list[SourceFinding]:
    if search_request_factory is None or peer_id_fn is None:
        from telethon import functions, utils
        search_request_factory = search_request_factory or (lambda q, limit: functions.contacts.SearchRequest(q=q, limit=limit))
        peer_id_fn = peer_id_fn or utils.get_peer_id
    candidates: dict[int, Any] = {}
    for seed in seeds:
        try: result = await client(search_request_factory(str(seed), int(search_limit)))
        except Exception as exc:
            log.warning("Traffic search failed for seed=%r: %s", seed, exc.__class__.__name__); continue
        for entity in getattr(result, "chats", ()) or ():
            title = getattr(entity, "title", None); username = getattr(entity, "username", None)
            if not title or not username: continue
            try: peer_id = int(peer_id_fn(entity))
            except Exception: continue
            candidates[peer_id] = entity
    def rough(entity: Any) -> int:
        text = f"{getattr(entity, 'title', '')} {getattr(entity, 'username', '')}"
        return (3 if _contains_any(text, SAMUI_TERMS) else 0) + (2 if _contains_any(text, HOUSING_TERMS) else 0) + (1 if CYRILLIC_RE.search(text) else 0)
    findings: list[SourceFinding] = []
    for peer_id, entity in sorted(candidates.items(), key=lambda kv: rough(kv[1]), reverse=True)[:max_candidates]:
        texts: list[str] = []; dates: list[datetime] = []
        try: messages = await client.get_messages(entity, limit=recent_limit)
        except Exception as exc:
            log.warning("Traffic read failed for @%s: %s", getattr(entity, "username", ""), exc.__class__.__name__); messages = []
        for message in messages or []:
            text = str(getattr(message, "message", "") or "").strip(); date = getattr(message, "date", None)
            if text: texts.append(text)
            if isinstance(date, datetime):
                if date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
                dates.append(date.astimezone(timezone.utc))
        findings.append(_score_source(entity=entity, telegram_id=peer_id, texts=texts, dates=dates))
    findings.sort(key=lambda item: (item.score, item.russian_share, item.recent_30d), reverse=True)
    return findings


async def scan_public_source(client: Any, *, username: str, title: str = "", limit: int = 50) -> list[LeadFinding]:
    entity = await client.get_entity(username); messages = await client.get_messages(entity, limit=limit); leads: list[LeadFinding] = []
    for message in messages or []:
        text = str(getattr(message, "message", "") or "").strip()
        if not text: continue
        score, band, reasons = score_rental_request(text)
        if score < 35: continue
        date = getattr(message, "date", None)
        if not isinstance(date, datetime): date = datetime.now(timezone.utc)
        elif date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
        fields = extract_request_fields(text)
        leads.append(LeadFinding(source_username=username.lstrip("@"), source_title=title or str(getattr(entity, "title", "") or ""),
            message_id=int(message.id), message_date=date.astimezone(timezone.utc), text=text, score=score, band=band,
            reasons=reasons, **fields))
    leads.sort(key=lambda item: (item.score, item.message_date), reverse=True)
    return leads


async def run_smoke(catalog: Any) -> list[SourceFinding]:
    client = await mtproto_user_client._new_client(catalog)
    if not client: raise RuntimeError("MTProto session is not authorized")
    try:
        findings = await discover_public_sources(client, search_limit=_env_int("COZY_TRAFFIC_SEARCH_LIMIT", 20, 5, 50),
            recent_limit=_env_int("COZY_TRAFFIC_RECENT_LIMIT", 30, 10, 100), max_candidates=_env_int("COZY_TRAFFIC_MAX_CANDIDATES", 50, 10, 100))
        topn = _env_int("COZY_TRAFFIC_TOPN", 20, 5, 50)
        log.info("TRAFFIC_SMOKE summary candidates=%s topn=%s", len(findings), min(topn, len(findings)))
        for idx, item in enumerate(findings[:topn], start=1):
            log.info("TRAFFIC_SMOKE #%02d score=%d kind=%s russian=%.0f%% active30=%d title=%r username=@%s",
                     idx, item.score, item.kind, item.russian_share * 100, item.recent_30d, item.title[:100], item.username)
        return findings
    finally: await client.disconnect()


def _startup_worker(catalog: Any) -> None:
    delay = _env_int("COZY_TRAFFIC_SMOKE_DELAY", 12, 0, 120)
    if delay: time.sleep(delay)
    try: asyncio.run(run_smoke(catalog))
    except Exception: log.exception("TRAFFIC_SMOKE failed")


def ensure_smoke_started(catalog: Any) -> bool:
    global _STARTED
    if not _enabled("COZY_TRAFFIC_SMOKE"): return False
    with _LOCK:
        if _STARTED: return False
        _STARTED = True
    threading.Thread(target=_startup_worker, args=(catalog,), name="cozy-traffic-smoke", daemon=True).start()
    log.info("TRAFFIC_SMOKE scheduled (read-only)")
    return True

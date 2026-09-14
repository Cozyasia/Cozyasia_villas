# -*- coding: utf-8 -*-
"""Read-only Telegram discovery for Russian-speaking Koh Samui rental audiences.

This module intentionally has no Telegram write operations. It reuses the
already-authorized Cozy Asia MTProto user session and only performs public
source search plus recent-message reads.
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
    "самуи",
    "самуи чат",
    "самуи аренда",
    "аренда самуи",
    "жилье самуи",
    "вилла самуи",
    "виллы самуи",
    "русские самуи",
    "самуи русские",
    "самуи объявления",
    "koh samui russian",
    "samui russian",
    "ламай самуи",
    "маенам самуи",
    "чавенг самуи",
    "бопхут самуи",
    "банграк самуи",
    "плай лаем самуи",
)

SAMUI_TERMS = (
    "самуи", "samui", "koh samui", "ко самуи", "кох самуи",
    "ламай", "lamai", "маенам", "maenam", "чавенг", "chaweng",
    "бопхут", "bophut", "бо пхут", "банграк", "bangrak",
    "плай лаем", "plai laem", "чонг мон", "choeng mon",
    "липа ной", "lipa noi", "натон", "nathon", "банг по", "bang po",
)
RENTAL_TERMS = (
    "аренд", "снять", "сниму", "снимем", "ищу дом", "ищем дом",
    "ищу вил", "ищем вил", "жиль", "вилл", "дом", "кондо", "студи",
    "апартамент", "rent", "rental", "villa", "house", "condo", "accommodation",
)
CYRILLIC_RE = re.compile(r"[а-яё]", re.I)
ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)
WS_RE = re.compile(r"\s+")
_STARTED = False
_LOCK = threading.Lock()


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _enabled() -> bool:
    return os.getenv("COZY_TRAFFIC_SMOKE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _norm(text: str) -> str:
    return WS_RE.sub(" ", (text or "").strip().lower().replace("ё", "е"))


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(term) in normalized for term in terms)


def _russian_share(texts: Iterable[str]) -> float:
    total = 0
    russian = 0
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
    samui_points: int
    rental_points: int
    russian_points: int
    activity_points: int
    discussion_points: int


def _score_source(*, entity: Any, telegram_id: int, texts: list[str], dates: list[datetime]) -> SourceFinding:
    title = str(getattr(entity, "title", "") or "").strip()
    username = str(getattr(entity, "username", "") or "").strip()
    kind = "group" if bool(getattr(entity, "megagroup", False)) or entity.__class__.__name__.lower().startswith("chat") else "channel"
    corpus = "\n".join([title, username, *texts])

    samui_points = 35 if _contains_any(corpus, SAMUI_TERMS) else 0
    rental_points = 25 if _contains_any(corpus, RENTAL_TERMS) else 0

    rus_share = _russian_share(texts)
    if rus_share >= 0.60:
        russian_points = 15
    elif rus_share >= 0.30:
        russian_points = 10
    elif CYRILLIC_RE.search(title):
        russian_points = 5
    else:
        russian_points = 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    recent_30d = sum(1 for d in dates if d >= cutoff)
    if recent_30d >= 20:
        activity_points = 15
    elif recent_30d >= 10:
        activity_points = 12
    elif recent_30d >= 5:
        activity_points = 8
    elif recent_30d >= 1:
        activity_points = 4
    else:
        activity_points = 0

    discussion_points = 10 if kind == "group" else 3
    total = min(100, samui_points + rental_points + russian_points + activity_points + discussion_points)
    return SourceFinding(
        telegram_id=telegram_id,
        title=title,
        username=username,
        kind=kind,
        score=total,
        russian_share=rus_share,
        recent_count=len(texts),
        recent_30d=recent_30d,
        samui_points=samui_points,
        rental_points=rental_points,
        russian_points=russian_points,
        activity_points=activity_points,
        discussion_points=discussion_points,
    )


async def discover_public_sources(
    client: Any,
    *,
    seeds: Iterable[str] = DEFAULT_SEEDS,
    search_limit: int = 20,
    recent_limit: int = 30,
    max_candidates: int = 50,
    search_request_factory: Callable[[str, int], Any] | None = None,
    peer_id_fn: Callable[[Any], int] | None = None,
) -> list[SourceFinding]:
    """Search public sources, read recent messages, score, and return best first."""
    if search_request_factory is None or peer_id_fn is None:
        from telethon import functions, utils
        search_request_factory = search_request_factory or (lambda q, limit: functions.contacts.SearchRequest(q=q, limit=limit))
        peer_id_fn = peer_id_fn or utils.get_peer_id

    candidates: dict[int, Any] = {}
    for seed in seeds:
        try:
            result = await client(search_request_factory(str(seed), int(search_limit)))
        except Exception as exc:
            log.warning("Traffic search failed for seed=%r: %s", seed, exc.__class__.__name__)
            continue
        for entity in getattr(result, "chats", ()) or ():
            title = getattr(entity, "title", None)
            username = getattr(entity, "username", None)
            if not title or not username:
                continue
            try:
                peer_id = int(peer_id_fn(entity))
            except Exception:
                continue
            candidates[peer_id] = entity

    def rough(entity: Any) -> int:
        text = f"{getattr(entity, 'title', '')} {getattr(entity, 'username', '')}"
        return (2 if _contains_any(text, SAMUI_TERMS) else 0) + (1 if _contains_any(text, RENTAL_TERMS) else 0) + (1 if CYRILLIC_RE.search(text) else 0)

    entities = sorted(candidates.items(), key=lambda kv: rough(kv[1]), reverse=True)[:max_candidates]
    findings: list[SourceFinding] = []
    for peer_id, entity in entities:
        texts: list[str] = []
        dates: list[datetime] = []
        try:
            messages = await client.get_messages(entity, limit=recent_limit)
        except Exception as exc:
            log.warning("Traffic read failed for @%s: %s", getattr(entity, "username", ""), exc.__class__.__name__)
            messages = []
        for message in messages or []:
            text = str(getattr(message, "message", "") or "").strip()
            date = getattr(message, "date", None)
            if text:
                texts.append(text)
            if isinstance(date, datetime):
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                dates.append(date.astimezone(timezone.utc))
        findings.append(_score_source(entity=entity, telegram_id=peer_id, texts=texts, dates=dates))

    findings.sort(key=lambda item: (item.score, item.russian_share, item.recent_30d), reverse=True)
    return findings


async def run_smoke(catalog: Any) -> list[SourceFinding]:
    client = await mtproto_user_client._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        findings = await discover_public_sources(
            client,
            search_limit=_env_int("COZY_TRAFFIC_SEARCH_LIMIT", 20, 5, 50),
            recent_limit=_env_int("COZY_TRAFFIC_RECENT_LIMIT", 30, 10, 100),
            max_candidates=_env_int("COZY_TRAFFIC_MAX_CANDIDATES", 50, 10, 100),
        )
        topn = _env_int("COZY_TRAFFIC_TOPN", 20, 5, 50)
        log.info("TRAFFIC_SMOKE summary candidates=%s topn=%s", len(findings), min(topn, len(findings)))
        for idx, item in enumerate(findings[:topn], start=1):
            log.info(
                "TRAFFIC_SMOKE #%02d score=%d kind=%s russian=%.0f%% active30=%d title=%r username=@%s",
                idx, item.score, item.kind, item.russian_share * 100, item.recent_30d,
                item.title[:100], item.username,
            )
        return findings
    finally:
        await client.disconnect()


def _startup_worker(catalog: Any) -> None:
    delay = _env_int("COZY_TRAFFIC_SMOKE_DELAY", 12, 0, 120)
    if delay:
        time.sleep(delay)
    try:
        asyncio.run(run_smoke(catalog))
    except Exception:
        log.exception("TRAFFIC_SMOKE failed")


def ensure_smoke_started(catalog: Any) -> bool:
    """Start one read-only smoke run when explicitly enabled by environment."""
    global _STARTED
    if not _enabled():
        return False
    with _LOCK:
        if _STARTED:
            return False
        _STARTED = True
    threading.Thread(target=_startup_worker, args=(catalog,), name="cozy-traffic-smoke", daemon=True).start()
    log.info("TRAFFIC_SMOKE scheduled (read-only)")
    return True

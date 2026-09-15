# -*- coding: utf-8 -*-
"""Discussion-first discovery patch for Cozy Traffic.

Broadens Telegram discovery from rental feeds to Russian-speaking Samui
communities and ranks sources by their likelihood of containing genuine user
questions and conversations. Telegram access remains read-only.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import re

EXPANDED_SEEDS = (
    "русские на самуи",
    "самуи русские чат",
    "самуи чат русские",
    "самуи общение",
    "самуи помощь",
    "самуи вопросы",
    "самуи советы",
    "самуи барахолка",
    "самуи объявления",
    "самуи экспаты",
    "самуи мамы",
    "самуи родители",
    "самуи дети",
    "samui russian community",
    "samui russian chat",
    "koh samui russian community",
    "samui expats",
    "koh samui expats",
)

DISCUSSION_RE = re.compile(
    r"\?|\bподскаж\w*|\bпосовету\w*|\bпорекоменду\w*|"
    r"\bкто\s+(?:знает|может|был|ездил|летал|сда(?:е|ё)т)|"
    r"\bможно\s+ли\b|\bгде\b|\bкак\b|\bищу\b|\bищем\b|\bнуж\w*",
    re.I,
)

PROMO_RE = re.compile(
    r"\bproperty\s*id\b|\bкод\s+объекта\b|\bстоимость\b|\bцена\b|"
    r"\bпишите\s+в\s+(?:л/?с|личк\w*)|\bпо\s+вопросам\s+бронирования\b|"
    r"\bwhats?app\b|\bконтракт\s+от\b|\bдоступн(?:а|о|ы|ен)\b|"
    r"\bсвободн(?:а|о|ы|ен)\b|\bсда(?:е|ё)тся\b|"
    r"(?:^|\n)\s*(?:🔥\s*)?аренда\s*[:!]",
    re.I,
)


def _ratio(texts, predicate):
    useful = [str(t or "").strip() for t in texts if str(t or "").strip()]
    if not useful:
        return 0.0
    return sum(1 for text in useful if predicate(text)) / len(useful)


def score_source(runtime, *, entity, telegram_id: int, texts: list[str], dates: list[datetime]):
    title = str(getattr(entity, "title", "") or "").strip()
    username = str(getattr(entity, "username", "") or "").strip()
    kind = "group" if bool(getattr(entity, "megagroup", False)) or entity.__class__.__name__.lower().startswith("chat") else "channel"
    corpus = "\n".join([title, username, *texts])

    housing_points = 10 if runtime._contains_any(corpus, runtime.HOUSING_TERMS) else 0
    samui_points = 25 if runtime._contains_any(corpus, runtime.SAMUI_TERMS) else 0
    rental_points = 5 if runtime._contains_any(corpus, runtime.RENTAL_TERMS) else 0

    rus_share = runtime._russian_share(texts)
    if rus_share >= 0.60:
        russian_points = 15
    elif rus_share >= 0.30:
        russian_points = 10
    elif runtime.CYRILLIC_RE.search(title):
        russian_points = 5
    else:
        russian_points = 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent_30d = 0
    for date in dates:
        if not isinstance(date, datetime):
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if date.astimezone(timezone.utc) >= cutoff:
            recent_30d += 1
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

    useful = [str(t or "").strip() for t in texts if str(t or "").strip()]
    question_ratio = _ratio(useful, lambda text: bool(DISCUSSION_RE.search(text)))
    promo_ratio = _ratio(useful, lambda text: bool(PROMO_RE.search(text)))
    short_ratio = _ratio(useful, lambda text: len(text) <= 500)
    unique_ratio = (len({runtime._norm(t) for t in useful}) / len(useful)) if useful else 0.0

    discussion_points = 0
    if kind == "group":
        discussion_points += 8
    if unique_ratio >= 0.75:
        discussion_points += 4
    if question_ratio >= 0.50:
        discussion_points += 14
    elif question_ratio >= 0.20:
        discussion_points += 8
    elif question_ratio >= 0.05:
        discussion_points += 4
    if short_ratio >= 0.60:
        discussion_points += 4
    discussion_points = min(30, discussion_points)

    penalty = 0
    if promo_ratio >= 0.50:
        penalty += 30
    elif promo_ratio >= 0.25:
        penalty += 18
    if kind == "channel":
        penalty += 12
    if runtime._contains_any(corpus, runtime.NON_HOUSING_RENT_TERMS) and not runtime._contains_any(corpus, runtime.HOUSING_TERMS):
        penalty += 25
    if username.lower() in runtime.OWN_USERNAMES:
        penalty += 100

    total = max(0, min(100,
        housing_points + samui_points + rental_points + russian_points +
        activity_points + discussion_points - penalty
    ))
    return runtime.SourceFinding(
        telegram_id=telegram_id,
        title=title,
        username=username,
        kind=kind,
        score=total,
        russian_share=rus_share,
        recent_count=len(useful),
        recent_30d=recent_30d,
        housing_points=housing_points,
        samui_points=samui_points,
        rental_points=rental_points,
        russian_points=russian_points,
        activity_points=activity_points,
        discussion_points=discussion_points,
        penalty=penalty,
    )


def apply(runtime) -> None:
    if getattr(runtime, "_discussion_discovery_patch_applied", False):
        return
    original_discover = runtime.discover_public_sources
    runtime.DEFAULT_SEEDS = tuple(dict.fromkeys((*runtime.DEFAULT_SEEDS, *EXPANDED_SEEDS)))
    runtime._score_source = lambda **kwargs: score_source(runtime, **kwargs)

    async def discover_public_sources(client, *, seeds=None, **kwargs):
        selected = runtime.DEFAULT_SEEDS if seeds is None else seeds
        return await original_discover(client, seeds=selected, **kwargs)

    runtime.discover_public_sources = discover_public_sources
    runtime._discussion_discovery_patch_applied = True

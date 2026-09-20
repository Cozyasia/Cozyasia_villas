# -*- coding: utf-8 -*-
"""Broader sources + cross-day semantic deduplication for Samui News."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import requests

log = logging.getLogger("samui-news-source-patch")

GOOGLE_QUERIES = (
    "Koh Samui news",
    "เกาะสมุย ข่าว",
    "Koh Samui immigration visa ferry airport weather police",
    "Koh Phangan news",
    "Koh Pha Ngan news",
    "เกาะพะงัน ข่าว",
    "Koh Phangan ferry police weather tourism",
    "Koh Tao news",
    "เกาะเต่า ข่าว",
    "Koh Tao ferry diving police weather",
    "Surat Thani news",
    "สุราษฎร์ธานี ข่าว",
    "Surat Thani province ferry airport tourism police",
)

_GEO_RE = re.compile(
    r"(?:koh\s*samui|ko\s*samui|samui|สมุย|самуи|"
    r"koh\s*(?:pha[\s-]*ngan|phangan)|ko\s*(?:pha[\s-]*ngan|phangan)|phangan|pha[\s-]*ngan|พะงัน|панган|"
    r"koh\s*tao|ko\s*tao|เกาะเต่า|ко\s*тао|кох\s*тао|"
    r"surat\s*thani|สุราษฎร์ธานี|сурат(?:т|тх)ани)",
    re.I,
)

_NEWS_TERMS = (
    "warning", "storm", "flood", "accident", "crash", "fire", "closed", "closure", "reopen",
    "police", "arrest", "charged", "immigration", "visa", "law", "rule", "airport", "flight",
    "ferry", "boat", "rescue", "missing", "weather", "festival", "event", "tourist", "tourism",
    "electricity", "power outage", "water outage", "road", "traffic", "hospital", "environment",
    "предупреж", "шторм", "наводнен", "авари", "пожар", "закры", "откры", "полици", "арест",
    "иммигра", "виз", "паром", "рейс", "аэропорт", "спас", "пропал", "погод", "фестивал",
    "พายุ", "น้ำท่วม", "อุบัติเหตุ", "ไฟไหม้", "ปิด", "เปิด", "ตำรวจ", "จับกุม", "ตรวจคนเข้าเมือง",
    "เรือเฟอร์รี่", "สนามบิน", "เที่ยวบิน", "กู้ภัย", "สูญหาย", "อากาศ", "เทศกาล",
)

_UPDATE_TERMS = (
    "update", "latest", "confirmed", "reopened", "resumed", "restored", "extended", "increased",
    "decreased", "arrested", "charged", "found", "rescued", "cancelled", "canceled", "closed",
    "обновлен", "подтвержд", "возобнов", "восстанов", "продлен", "увелич", "сниз", "задерж",
    "обвин", "найден", "спасен", "отмен", "закры", "เปิดแล้ว", "ยืนยัน", "กลับมา", "จับกุม",
)

_SPAM_TERMS = (
    "for rent", "villa for rent", "house for rent", "condo for rent", "property for sale", "real estate",
    "аренда вилл", "вилла в аренду", "продажа вилл", "недвижимость", "monthly rent", "commission",
)

_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "after", "before", "into", "over", "under",
    "about", "news", "koh", "ko", "island", "today", "samui", "phangan", "tao", "surat", "thani",
    "это", "как", "для", "или", "при", "после", "перед", "самуи", "панган", "тао", "сураттхани",
}

_RECENT_CHANNEL_POSTS: list[str] = []
_LAST_TG_SOURCES: list[str] = []


def _strip(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _geo_match(text: str) -> bool:
    return bool(_GEO_RE.search(text or ""))


def _split_env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [x.strip() for x in re.split(r"[;,\n]+", raw) if x.strip()]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[0-9A-Za-zА-Яа-яЁёก-๙]+", (text or "").lower())
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


def _similarity(a: str, b: str) -> float:
    aa, bb = _tokens(a), _tokens(b)
    jaccard = len(aa & bb) / max(1, len(aa | bb))
    seq = SequenceMatcher(
        None,
        re.sub(r"\s+", " ", (a or "").lower()),
        re.sub(r"\s+", " ", (b or "").lower()),
    ).ratio()
    return max(jaccard, seq * 0.78)


def _material_update(candidate: str, previous: str) -> bool:
    low_new, low_old = (candidate or "").lower(), (previous or "").lower()
    if any(term in low_new and term not in low_old for term in _UPDATE_TERMS):
        return True
    nums_new = set(re.findall(r"\b\d{1,4}(?::\d{2})?\b", low_new))
    nums_old = set(re.findall(r"\b\d{1,4}(?::\d{2})?\b", low_old))
    return bool(nums_new - nums_old)


def _fallback_novelty(item: dict, recent_posts: list[str]) -> str:
    candidate = " ".join(
        x for x in (item.get("title", ""), item.get("text", "")) if x
    ).strip()
    best = None
    best_score = 0.0
    for post in recent_posts:
        score = _similarity(candidate, post)
        if score > best_score:
            best_score, best = score, post
    if best is None:
        return "new"
    if best_score >= 0.24 and _material_update(candidate, best):
        return "update"
    if best_score < 0.42:
        return "new"
    return "duplicate"


def _looks_newsworthy(text: str, source_name: str = "") -> bool:
    low = (text or "").lower()
    if any(term in low for term in _SPAM_TERMS):
        return False
    if len(low.strip()) < 25:
        return False
    score = sum(1 for term in _NEWS_TERMS if term in low)
    return score >= 1 or (_geo_match(source_name) and len(low) >= 120)


def _importance_enhanced(item: dict) -> int:
    text = " ".join((item.get("title", ""), item.get("text", ""))).lower()
    critical = (
        "warning", "storm", "flood", "accident", "fire", "closed", "closure", "police", "arrest",
        "immigration", "visa", "law", "airport", "flight", "ferry", "rescue", "missing",
        "шторм", "наводнен", "авари", "пожар", "закры", "полици", "арест", "иммигра", "виз",
        "паром", "аэропорт", "спас", "пропал", "พายุ", "น้ำท่วม", "อุบัติเหตุ", "ไฟไหม้", "ตำรวจ",
        "จับกุม", "เรือเฟอร์รี่", "สนามบิน", "กู้ภัย",
    )
    useful = (
        "event", "festival", "weather", "tourist", "tourism", "business", "road", "traffic",
        "electricity", "water", "фестивал", "погод", "турист", "дорог", "электр", "вода",
        "เทศกาล", "อากาศ", "นักท่องเที่ยว",
    )
    score = sum(2 for x in critical if x in text) + sum(1 for x in useful if x in text)
    if _geo_match(text):
        score += 1
    if item.get("novelty") == "update":
        score += 2
    return score


def _history_state_factory(news, history_days: int = 14):
    def _history_state(catalog, day):
        posts = stories = 0
        last_post = None
        used_urls: set[str] = set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, history_days))
        try:
            for row in news._worksheet(catalog).get_all_values()[1:]:
                if not row:
                    continue
                kind = row[1] if len(row) > 1 else ""
                is_today = str(row[0]).startswith(day)
                created = None
                if len(row) > 5 and row[5]:
                    try:
                        created = datetime.fromisoformat(row[5])
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        else:
                            created = created.astimezone(timezone.utc)
                    except Exception:
                        created = None
                if is_today and kind == "post":
                    posts += 1
                elif is_today and kind == "story":
                    stories += 1
                if kind == "post" and created and (
                    last_post is None or created > last_post
                ):
                    last_post = created
                in_history = is_today or (
                    created is not None and created >= cutoff
                )
                if in_history and len(row) > 4:
                    used_urls.update(
                        x.strip() for x in row[4].splitlines() if x.strip()
                    )
        except Exception:
            log.exception("Could not build extended Samui News history state")
        return {
            "posts": posts,
            "stories": stories,
            "last_post": last_post,
            "used_urls": used_urls,
        }

    return _history_state


def _google_candidates() -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for query in GOOGLE_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": query + " when:2d", "hl": "en", "gl": "TH", "ceid": "TH:en"}
        )
        try:
            response = requests.get(
                url, timeout=20, headers={"User-Agent": "SamuiNews/3.0"}
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for node in root.findall(".//item")[:15]:
                title = _strip(node.findtext("title"))
                link = _strip(node.findtext("link"))
                date = _strip(node.findtext("pubDate"))
                desc = _strip(node.findtext("description"))
                source_node = node.find("source")
                source_name = _strip(
                    source_node.text if source_node is not None else ""
                )
                source_url = _strip(
                    source_node.attrib.get("url", "")
                    if source_node is not None
                    else ""
                )
                key = link or title.lower()
                body = f"{title} {desc}"
                if not title or not link or key in seen or not _geo_match(body):
                    continue
                seen.add(key)
                items.append(
                    {
                        "title": title,
                        "url": link,
                        "published": date,
                        "source_name": source_name or "Google News",
                        "source_url": source_url,
                        "source_kind": "google_news",
                        "text": desc or title,
                    }
                )
        except Exception:
            log.exception("Expanded news feed failed: %s", query)
    return items[:60]


def _clean_tg_ref(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"^https?://t\.me/", "", value, flags=re.I)
    value = value.strip("/@ ")
    return value.split("/", 1)[0]


async def _telegram_candidates(mt, catalog, target_channel: str):
    client = await mt._new_client(catalog)
    if not client:
        return [], [], []
    selected: dict[int, tuple[object, str, str]] = {}
    recent_posts: list[str] = []
    source_names: list[str] = []
    try:
        target_username = (target_channel or "").strip().lstrip("@").lower()
        explicit = [
            _clean_tg_ref(x) for x in _split_env_list("SAMUI_NEWS_TG_SOURCES")
        ]
        for ref in explicit:
            if not ref:
                continue
            try:
                entity = await client.get_entity(ref)
                username = getattr(entity, "username", None)
                if not username:
                    log.warning(
                        "Configured Telegram source is not public; skipping: %s", ref
                    )
                    continue
                name = getattr(entity, "title", None) or username
                selected[int(getattr(entity, "id", hash(ref)))] = (
                    entity,
                    name,
                    username,
                )
            except Exception:
                log.exception(
                    "Could not resolve configured Telegram news source: %s", ref
                )

        async for dialog in client.iter_dialogs(limit=250):
            entity = dialog.entity
            username = getattr(entity, "username", None)
            name = (
                getattr(dialog, "name", None)
                or getattr(entity, "title", None)
                or ""
            ).strip()
            if not username or username.lower() == target_username:
                continue
            if not (
                getattr(dialog, "is_group", False)
                or getattr(dialog, "is_channel", False)
            ):
                continue
            if not _geo_match(name):
                continue
            selected.setdefault(
                int(getattr(entity, "id", hash(username))),
                (entity, name, username),
            )

        try:
            target = await client.get_entity(target_channel)
            cutoff = datetime.now(timezone.utc) - timedelta(days=10)
            async for message in client.iter_messages(target, limit=60):
                text = (getattr(message, "message", "") or "").strip()
                dt = getattr(message, "date", None)
                if dt and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt and dt < cutoff:
                    break
                if text:
                    recent_posts.append(text[:1400])
        except Exception:
            log.exception(
                "Could not read recent Samui News posts for semantic deduplication"
            )

        items: list[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        max_sources = int(
            os.environ.get("SAMUI_NEWS_TG_SOURCE_LIMIT", "40") or 40
        )
        for entity, name, username in list(selected.values())[:max_sources]:
            source_names.append(name)
            try:
                async for message in client.iter_messages(entity, limit=35):
                    text = (getattr(message, "message", "") or "").strip()
                    dt = getattr(message, "date", None)
                    if dt and dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt and dt < cutoff:
                        break
                    if not text or not _looks_newsworthy(text, name):
                        continue
                    first_line = next(
                        (x.strip() for x in text.splitlines() if x.strip()), text
                    )
                    public_username = getattr(entity, "username", None) or username
                    if not public_username:
                        continue
                    url = f"https://t.me/{public_username}/{message.id}"
                    items.append(
                        {
                            "title": first_line[:220],
                            "url": url,
                            "published": (
                                dt.astimezone(timezone.utc).isoformat() if dt else ""
                            ),
                            "source_name": name,
                            "source_url": f"https://t.me/{public_username}",
                            "source_kind": "telegram",
                            "text": text[:1200],
                        }
                    )
            except Exception:
                log.exception("Telegram news source scan failed: %s", name)
        return items[:100], recent_posts, source_names
    finally:
        await client.disconnect()


def _facebook_graph_candidates() -> list[dict]:
    token = os.environ.get("SAMUI_NEWS_FACEBOOK_TOKEN", "").strip()
    source_ids = _split_env_list("SAMUI_NEWS_FACEBOOK_SOURCE_IDS")
    if not token or not source_ids:
        return []
    version = os.environ.get("SAMUI_NEWS_FACEBOOK_GRAPH_VERSION", "").strip().strip("/")
    items: list[dict] = []
    for source_id in source_ids[:30]:
        base = (
            f"https://graph.facebook.com/{version}"
            if version
            else "https://graph.facebook.com"
        )
        url = f"{base}/{source_id}/feed"
        try:
            response = requests.get(
                url,
                timeout=20,
                params={
                    "access_token": token,
                    "fields": "message,permalink_url,created_time,from",
                    "limit": 25,
                },
            )
            response.raise_for_status()
            for post in response.json().get("data", []):
                text = (post.get("message") or "").strip()
                if (
                    not text
                    or not _looks_newsworthy(text, "Facebook")
                    or not _geo_match(text)
                ):
                    continue
                source = (
                    (post.get("from") or {}).get("name")
                    or f"Facebook {source_id}"
                )
                permalink = post.get("permalink_url") or ""
                if not permalink:
                    continue
                first_line = next(
                    (x.strip() for x in text.splitlines() if x.strip()), text
                )
                items.append(
                    {
                        "title": first_line[:220],
                        "url": permalink,
                        "published": post.get("created_time") or "",
                        "source_name": source,
                        "source_url": permalink,
                        "source_kind": "facebook",
                        "text": text[:1200],
                    }
                )
        except Exception:
            log.exception("Facebook Graph news source scan failed: %s", source_id)
    return items[:80]


def _dedupe_candidate_list(items: list[dict]) -> list[dict]:
    result = []
    seen_urls, seen_titles = set(), set()
    for item in items:
        url = (item.get("url") or "").strip()
        title_key = re.sub(
            r"\W+", " ", (item.get("title") or "").lower()
        ).strip()
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        result.append(item)
    return result


def _llm_novelty(news, items: list[dict], recent_posts: list[str]) -> list[dict]:
    if not items or not recent_posts or not os.environ.get("OPENAI_API_KEY"):
        for item in items:
            item["novelty"] = _fallback_novelty(item, recent_posts)
        return [x for x in items if x.get("novelty") != "duplicate"]
    try:
        from openai import OpenAI

        candidates = [
            {
                "i": i,
                "title": x.get("title", "")[:260],
                "text": x.get("text", "")[:500],
                "source": x.get("source_name", "")[:120],
            }
            for i, x in enumerate(items[:36])
        ]
        history = [
            re.sub(r"\s+", " ", x)[:850] for x in recent_posts[:18]
        ]
        prompt = (
            "Ты проверяешь новости для Telegram-канала. Сравни кандидатов с уже опубликованными сообщениями. "
            "Для каждого кандидата верни verdict: new, update или duplicate. duplicate = то же событие без нового факта, "
            "даже если другой заголовок/язык/источник. update разрешён ТОЛЬКО если появился конкретный новый факт: "
            "смена статуса, официальное решение, новое число/время/дата, арест/обвинение, найден/спасён, открытие/закрытие, "
            "возобновление/отмена, новые последствия. Не считай перефразирование обновлением. Ответ только JSON-массив "
            "вида [{\"i\":0,\"verdict\":\"new\"}].\n\n"
            f"УЖЕ ОПУБЛИКОВАНО:\n{json.dumps(history, ensure_ascii=False)}\n\n"
            f"КАНДИДАТЫ:\n{json.dumps(candidates, ensure_ascii=False)}"
        )
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
        verdicts = {
            int(x["i"]): str(x["verdict"]).lower()
            for x in json.loads(raw)
            if "i" in x and "verdict" in x
        }
        out = []
        for i, item in enumerate(items):
            verdict = (
                verdicts.get(i)
                if i < 36
                else _fallback_novelty(item, recent_posts)
            )
            if verdict not in {"new", "update", "duplicate"}:
                verdict = _fallback_novelty(item, recent_posts)
            item["novelty"] = verdict
            if verdict != "duplicate":
                out.append(item)
        return out
    except Exception:
        log.exception("Semantic novelty gate failed; using deterministic fallback")
        for item in items:
            item["novelty"] = _fallback_novelty(item, recent_posts)
        return [x for x in items if x.get("novelty") != "duplicate"]


def _should_publish_enhanced(
    items, state, now, max_posts=5, min_gap_seconds=5400
):
    fresh = [
        x
        for x in items
        if x.get("url") not in state.get("used_urls", set())
        and x.get("novelty") != "duplicate"
    ]
    if not fresh or state.get("posts", 0) >= max_posts:
        return False, []
    last_post = state.get("last_post")
    if last_post and (
        datetime.now(timezone.utc) - last_post
    ).total_seconds() < min_gap_seconds:
        return False, []
    ranked = sorted(fresh, key=_importance_enhanced, reverse=True)
    best = _importance_enhanced(ranked[0])
    publish = (
        best >= 3
        or (best >= 2 and len(ranked) >= 2)
        or (18 <= now.hour <= 22 and best >= 2)
    )
    return publish, ranked[:5] if publish else []


def _compose_factory(news):
    def _compose(items, slot):
        from openai import OpenAI

        if not items:
            raise RuntimeError("No recent regional news candidates")
        payload = "\n".join(
            f"{i+1}. verdict={x.get('novelty','new')} | {x.get('title','')} | {x.get('published','')} | "
            f"source={x.get('source_name','')} | {x.get('url','')} | facts={x.get('text','')[:650]}"
            for i, x in enumerate(items)
        )
        prompt = f"""Ты — редактор русскоязычного Telegram-канала Samui News. Сейчас {slot} по местному времени.
География канала: Ко Самуи, Ко Панган, Ко Тао и провинция Сураттхани.
Выбери 1–3 действительно важных и разных события. Не выдумывай факты.
Кандидаты с verdict=update можно публиковать как продолжение старой темы ТОЛЬКО через новые факты из поля facts;
не пересказывай старую историю заново. Если это update, прямо обозначь «Обновление».
Сообщения из Telegram/Facebook — сигнальные источники: не превращай предположение автора группы в подтверждённый факт.
Для юридических, визовых, миграционных и экстренных сообщений используй осторожные формулировки и, если возможно,
отдавай приоритет официальному/медийному источнику из списка.

Сделай компактный пост на русском. Видимый текст — максимум {news.POST_CAPTION_TARGET_CHARS} знаков:
первая строка — тематический emoji + жирный заголовок в HTML;
каждый пункт: смысловой emoji, <b>короткий подзаголовок</b> и 1 короткое предложение;
после каждого пункта строка «Источник: <a href=\"URL\">название источника</a>»;
в конце: «🌊 Samui News — Самуи • Панган • Ко Тао • Сураттхани.» и 3–5 релевантных хэштегов.
Верни только готовый HTML; допустимы теги b, i, a. Не добавляй markdown.

Кандидаты:\n{payload}"""
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        result = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (result.choices[0].message.content or "").strip()
        text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text, flags=re.I)
        if not text:
            raise RuntimeError("OpenAI returned an empty regional news post")
        if len(news._plain(text)) > news.POST_CAPTION_TARGET_CHARS:
            compress = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Сожми HTML-пост до {news.POST_CAPTION_TARGET_CHARS} видимых знаков. Сохрани новые факты, источники, "
                            "финальную строку и 3–5 хэштегов. Не добавляй фактов. Верни только HTML.\n\n"
                            + text
                        ),
                    }
                ],
            )
            candidate = (compress.choices[0].message.content or "").strip()
            candidate = re.sub(
                r"^```(?:html)?\s*|\s*```$", "", candidate, flags=re.I
            )
            if candidate:
                text = candidate
        return text

    return _compose


def apply(news, mt, catalog):
    if getattr(news, "_REGIONAL_SOURCE_PATCH_V1", False):
        return
    news._REGIONAL_SOURCE_PATCH_V1 = True

    history_days = int(os.environ.get("SAMUI_NEWS_HISTORY_DAYS", "14") or 14)
    max_posts = int(os.environ.get("SAMUI_NEWS_MAX_POSTS_PER_DAY", "5") or 5)
    min_gap = int(
        os.environ.get("SAMUI_NEWS_MIN_POST_GAP_SECONDS", "5400") or 5400
    )

    news.MAX_POSTS_PER_DAY = max_posts
    news.MAX_STORIES_PER_DAY = int(
        os.environ.get("SAMUI_NEWS_MAX_STORIES_PER_DAY", "3") or 3
    )
    news.MIN_POST_GAP_SECONDS = min_gap
    news.SCAN_HOURS = range(6, 24)
    news._daily_state = _history_state_factory(news, history_days=history_days)
    news._should_publish = lambda items, state, now: _should_publish_enhanced(
        items, state, now, max_posts=max_posts, min_gap_seconds=min_gap
    )
    news._compose = _compose_factory(news)

    def _fetch_candidates_enhanced():
        global _RECENT_CHANNEL_POSTS, _LAST_TG_SOURCES
        google = _google_candidates()
        facebook = _facebook_graph_candidates()
        telegram, recent, sources = [], [], []
        try:
            telegram, recent, sources = asyncio.run(
                _telegram_candidates(mt, catalog, news.CHANNEL)
            )
        except Exception:
            log.exception("Telegram regional source scan failed")
        if recent:
            _RECENT_CHANNEL_POSTS = recent
        _LAST_TG_SOURCES = sources
        combined = _dedupe_candidate_list(google + telegram + facebook)
        novel = _llm_novelty(news, combined, _RECENT_CHANNEL_POSTS)
        log.info(
            "Regional news scan: google=%s telegram=%s facebook=%s public_tg_sources=%s recent_channel_posts=%s novel=%s",
            len(google),
            len(telegram),
            len(facebook),
            len(sources),
            len(_RECENT_CHANNEL_POSTS),
            len(novel),
        )
        return sorted(novel, key=_importance_enhanced, reverse=True)[:40]

    news._fetch_candidates = _fetch_candidates_enhanced
    log.info(
        "Samui News regional source patch enabled: Samui + Phangan + Koh Tao + Surat Thani; "
        "history=%sd max_posts=%s min_gap=%ss; Telegram public-group autodiscovery=on; Facebook Graph=%s",
        history_days,
        max_posts,
        min_gap,
        bool(os.environ.get("SAMUI_NEWS_FACEBOOK_TOKEN")),
    )

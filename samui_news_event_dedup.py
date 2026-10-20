"""Deterministic event identity and freshness checks for Samui News.

This module is intentionally dependency-free so the publication gate can run
before OpenAI composition, image generation, and Telegram delivery.
"""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

LOCAL_TZ = timezone(timedelta(hours=7))

_WEATHER_RE = re.compile(
    r"(?:weather|forecast|rain|storm|flood|landslide|typhoon|monsoon|"
    r"погод|дожд|ливн|шторм|наводнен|ополз|тайфун|муссон|"
    r"อากาศ|ฝน|พายุ|น้ำท่วม|ดินถล่ม)",
    re.I,
)
_CATEGORY_PATTERNS = (
    ("incident", r"(?:accident|crash|collision|fire|explosion|police|arrest|rescue|missing|drown|"
                 r"авари|дтп|столкнов|пожар|взрыв|полици|арест|спас|пропал|утон|"
                 r"อุบัติเหตุ|ไฟไหม้|ระเบิด|ตำรวจ|จับกุม|กู้ภัย|สูญหาย)"),
    ("transport", r"(?:ferry|boat|pier|airport|flight|road|traffic|closure|reopen|cancel|"
                   r"паром|лодк|пирс|аэропорт|рейс|дорог|движен|перекры|закры|отмен|"
                   r"เรือเฟอร์รี่|สนามบิน|เที่ยวบิน|ถนน|จราจร|ปิด|ยกเลิก)"),
    ("visa_law", r"(?:visa|immigration|law|regulation|government|court|"
                  r"виз|иммигра|закон|правил|постановлен|власт|суд|"
                  r"วีซ่า|ตรวจคนเข้าเมือง|กฎหมาย|ศาล)"),
    ("environment", r"(?:environment|pollution|waste|ecology|эколог|загрязнен|мусор|"
                    r"สิ่งแวดล้อม|มลพิษ|ขยะ)"),
)
_GEO_ALIASES = (
    ("samui", r"(?:koh\s+samui|ko\s+samui|samui|самуи|เกาะสมุย)"),
    ("phangan", r"(?:koh\s+phangan|ko\s+phangan|koh\s+pha.?ngan|панган|пханган|เกาะพะงัน)"),
    ("tao", r"(?:koh\s+tao|ko\s+tao|ко\s+тао|тао|เกาะเต่า)"),
    ("surat_thani", r"(?:surat\s+thani|สุราษฎร์ธานี|суратт?хани|суратт?ани)"),
)

_STOPWORDS = {
    "the", "and", "for", "with", "from", "after", "before", "into", "this", "that",
    "новости", "новость", "сообщил", "сообщает", "сообщают", "район", "провинция",
    "сегодня", "вчера", "который", "после", "из-за", "из", "на", "и", "в", "во",
    "на", "по", "у", "для", "что", "как", "это", "также", "the",
    "ข่าว", "วันนี้", "เมื่อ", "และ", "ของ", "ใน", "ที่",
}
_UPDATE_RE = re.compile(
    r"(?:обновлен|возобнов|отмен|закрыт|открыт|изменил|новые данные|новое число|"
    r"подтвердил|официальн|задержан|арестован|спасен|найден|погиб|ранен|последств|"
    r"resum|reopen|reopen|cancel|new data|updated|official|arrested|rescued|"
    r"confirmed|новых последств|"
    r"ยืนยัน|เปิดอีกครั้ง|ยกเลิก|ข้อมูลใหม่)",
    re.I,
)


def normalize(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"https?://\S+|www\.\S+", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip().lower()


def canonical_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))
    except Exception:
        return raw


def _parse_datetime(value: str):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        value = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
    except Exception:
        try:
            dt = parsedate_to_datetime(raw)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def item_datetime(item: dict):
    return (
        _parse_datetime(str(item.get("event_date") or ""))
        or _parse_datetime(str(item.get("published") or ""))
        or _parse_datetime(str(item.get("date") or ""))
    )


def is_fresh(item: dict, now: datetime | None = None, max_age_hours: int = 48) -> bool:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    published = item_datetime(item)
    if published is None:
        return False
    age = (now - published).total_seconds()
    return 0 <= age <= max_age_hours * 3600


def geo_bucket(item: dict | str) -> str:
    text = normalize(item if isinstance(item, str) else " ".join(
        str(item.get(key) or "") for key in ("title", "text", "source_name")
    ))
    for bucket, pattern in _GEO_ALIASES:
        if re.search(pattern, text, re.I):
            return bucket
    return "regional"


def category_bucket(item: dict | str) -> str:
    text = normalize(item if isinstance(item, str) else " ".join(
        str(item.get(key) or "") for key in ("title", "text")
    ))
    if _WEATHER_RE.search(text):
        return "weather"
    for category, pattern in _CATEGORY_PATTERNS:
        if re.search(pattern, text, re.I):
            return category
    return "general"


def _tokens(item: dict | str) -> set[str]:
    text = normalize(item if isinstance(item, str) else " ".join(
        str(item.get(key) or "") for key in ("title", "text")
    ))
    words = set(re.findall(r"[a-zа-яё]{3,}|[ก-๙]{3,}", text, re.I))
    return {word for word in words if word not in _STOPWORDS and not word.isdigit()}


def event_day(item: dict, now: datetime | None = None) -> str:
    dt = item_datetime(item) or now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).date().isoformat()


def event_signature(item: dict, now: datetime | None = None) -> str:
    category = category_bucket(item)
    geo = geo_bucket(item)
    day = event_day(item, now)
    if category == "weather":
        return f"{category}|{geo}|{day}|weather"
    tokens = sorted(_tokens(item))
    # Keep the signature bounded and stable for storage in the existing state sheet.
    core = " ".join(tokens[:24]) or "unclassified"
    return f"{category}|{geo}|{day}|{core}"


def build_event_key(item: dict, now: datetime | None = None) -> str:
    signature = event_signature(item, now)
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:20]
    return f"event:{digest}"


def _signature_parts(signature: str):
    parts = (signature or "").split("|", 3)
    if len(parts) != 4:
        return "", "", "", set()
    return parts[0], parts[1], parts[2], set(parts[3].split()) - {"weather", "unclassified"}


def _similar_signature(candidate: str, existing: str) -> bool:
    c_cat, c_geo, c_day, c_tokens = _signature_parts(candidate)
    e_cat, e_geo, e_day, e_tokens = _signature_parts(existing)
    if not c_cat or (c_cat, c_geo, c_day) != (e_cat, e_geo, e_day):
        return False
    if c_cat == "weather":
        return True
    if not c_tokens or not e_tokens:
        return False
    return len(c_tokens & e_tokens) / max(1, len(c_tokens | e_tokens)) >= 0.60


def is_material_update(item: dict) -> bool:
    text = " ".join(str(item.get(key) or "") for key in ("title", "text"))
    return str(item.get("novelty") or "").lower() == "update" and bool(_UPDATE_RE.search(text))


def dedupe_decision(item: dict, state: dict, now: datetime | None = None):
    url = canonical_url(str(item.get("url") or ""))
    used_urls = {canonical_url(str(x)) for x in state.get("used_urls", set()) if x}
    if url and url in used_urls:
        return False, "duplicate:source_url"
    if not is_fresh(item, now=now, max_age_hours=int(state.get("max_age_hours", 48))):
        return False, "stale:published_at"
    key = build_event_key(item, now)
    signature = event_signature(item, now)
    known_keys = set(state.get("event_keys", set())) | set(state.get("recent_event_keys", set()))
    known_signatures = set(state.get("event_signatures", set()))
    if key in known_keys or any(_similar_signature(signature, x) for x in known_signatures):
        if is_material_update(item):
            return True, "update:material"
        return False, "duplicate:event"
    return True, "new:event"


__all__ = [
    "build_event_key",
    "canonical_url",
    "category_bucket",
    "dedupe_decision",
    "event_day",
    "event_signature",
    "geo_bucket",
    "is_fresh",
    "is_material_update",
    "normalize",
]

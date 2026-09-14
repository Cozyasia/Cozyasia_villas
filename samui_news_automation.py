# -*- coding: utf-8 -*-
"""Event-driven Samui News posts and Telegram channel stories via MTProto.

Publication invariant: every channel news post must carry an image. The publisher
prefers a relevant article preview image (Open Graph/Twitter metadata). If no safe,
usable source image is available, it creates a branded Samui News card from the
lead story instead of publishing a text-only post.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import io
import logging
import os
import random
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

import requests

import mtproto_user_client

log = logging.getLogger("samui-news")
CHANNEL = os.environ.get("SAMUI_NEWS_CHANNEL", "samui_news_ru").strip().lstrip("@")
TZ = timezone(timedelta(hours=7))
SCAN_HOURS = range(7, 23)
MAX_POSTS_PER_DAY = 3
MAX_STORIES_PER_DAY = 2
MIN_POST_GAP_SECONDS = 2 * 60 * 60
STATE_SHEET = "SamuiNewsAutomation"
_STARTED = False
_LOCK = threading.Lock()

# Media rules for the main channel post.
POST_IMAGE_SIZE = (1280, 720)
POST_IMAGE_TIMEOUT_SECONDS = 15
POST_IMAGE_MAX_BYTES = 8 * 1024 * 1024
POST_IMAGE_MIN_WIDTH = 480
POST_IMAGE_MIN_HEIGHT = 270
POST_CAPTION_TARGET_CHARS = 900

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 SamuiNews/2.0"
    ),
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8,ru;q=0.7",
}

QUERIES = (
    "Koh Samui news",
    "เกาะสมุย ข่าว",
    "Koh Samui immigration visa",
    "Koh Samui weather ferry airport",
    "Koh Samui event restaurant opening",
)


class _ImageMetaParser(HTMLParser):
    """Collect article preview-image URLs from common HTML metadata."""

    META_KEYS = {
        "og:image",
        "og:image:url",
        "og:image:secure_url",
        "twitter:image",
        "twitter:image:src",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.candidates: list[str] = []

    def _add(self, value):
        value = (value or "").strip()
        if value and value not in self.candidates:
            self.candidates.append(value)

    def handle_starttag(self, tag, attrs):
        data = {str(k).lower(): (v or "") for k, v in attrs}
        tag = (tag or "").lower()
        if tag == "meta":
            key = (data.get("property") or data.get("name") or "").strip().lower()
            if key in self.META_KEYS:
                self._add(data.get("content"))
        elif tag == "link":
            rel = (data.get("rel") or "").strip().lower()
            if "image_src" in rel:
                self._add(data.get("href"))


def _worksheet(catalog):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        return sh.worksheet(STATE_SHEET)
    except Exception:
        ws = sh.add_worksheet(title=STATE_SHEET, rows=1000, cols=6)
        ws.append_row(
            ["slot", "kind", "content_hash", "message_id", "source_urls", "created_at"],
            value_input_option="RAW",
        )
        return ws


def _completed(catalog, slot, kind):
    try:
        return any(
            len(r) > 1 and r[0] == slot and r[1] == kind
            for r in _worksheet(catalog).get_all_values()[1:]
        )
    except Exception:
        log.exception("Could not read Samui News state")
        return False


def _daily_state(catalog, day):
    posts = stories = 0
    last_post = None
    used_urls = set()
    try:
        for row in _worksheet(catalog).get_all_values()[1:]:
            if not row or not row[0].startswith(day):
                continue
            if len(row) > 1 and row[1] == "post":
                posts += 1
                if len(row) > 5 and row[5]:
                    try:
                        created = datetime.fromisoformat(row[5])
                        last_post = max(
                            last_post or datetime.min.replace(tzinfo=timezone.utc), created
                        )
                    except Exception:
                        pass
            elif len(row) > 1 and row[1] == "story":
                stories += 1
            if len(row) > 4:
                used_urls.update(x.strip() for x in row[4].splitlines() if x.strip())
    except Exception:
        log.exception("Could not build Samui News daily state")
    return {
        "posts": posts,
        "stories": stories,
        "last_post": last_post,
        "used_urls": used_urls,
    }


def _mark(catalog, slot, kind, content, message_id, urls):
    _worksheet(catalog).append_row(
        [
            slot,
            kind,
            hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
            str(message_id or ""),
            "\n".join(urls)[:4000],
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ],
        value_input_option="RAW",
    )


def _strip(value):
    return re.sub(
        r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    ).strip()


def _fetch_candidates():
    items, seen = [], set()
    for query in QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": query + " when:3d", "hl": "en", "gl": "TH", "ceid": "TH:en"}
        )
        try:
            response = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "SamuiNews/2.0"},
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for node in root.findall(".//item")[:15]:
                title = _strip(node.findtext("title"))
                link = _strip(node.findtext("link"))
                date = _strip(node.findtext("pubDate"))
                source_node = node.find("source")
                source_name = _strip(source_node.text if source_node is not None else "")
                source_url = _strip(
                    source_node.attrib.get("url", "") if source_node is not None else ""
                )
                key = title.lower()
                if title and link and key not in seen:
                    seen.add(key)
                    items.append(
                        {
                            "title": title,
                            "url": link,
                            "published": date,
                            "source_name": source_name,
                            "source_url": source_url,
                        }
                    )
        except Exception:
            log.exception("News feed failed: %s", query)
    samui = [x for x in items if re.search(r"samui|สมุย", x["title"], re.I)]
    return (samui or items)[:24]


def _importance(item):
    title = item["title"].lower()
    score = 0
    critical = (
        "warning",
        "storm",
        "flood",
        "accident",
        "closed",
        "closure",
        "police",
        "arrest",
        "immigration",
        "visa",
        "law",
        "rule",
        "airport",
        "ferry",
        "พายุ",
        "น้ำท่วม",
        "ตำรวจ",
        "ตรวจคนเข้าเมือง",
    )
    useful = (
        "samui",
        "สมุย",
        "event",
        "festival",
        "opening",
        "weather",
        "tourist",
        "business",
        "flight",
    )
    score += sum(2 for word in critical if word in title)
    score += sum(1 for word in useful if word in title)
    return score


def _should_publish(items, state, now):
    fresh = [x for x in items if x["url"] not in state["used_urls"]]
    if not fresh or state["posts"] >= MAX_POSTS_PER_DAY:
        return False, []
    if state["last_post"] and (
        datetime.now(timezone.utc) - state["last_post"]
    ).total_seconds() < MIN_POST_GAP_SECONDS:
        return False, []
    best = max(_importance(x) for x in fresh)
    # Major developments go out quickly. Normal news needs enough substance;
    # 19:00–21:59 is the fallback digest window, never an obligation to post.
    publish = (
        best >= 5
        or (best >= 3 and len(fresh) >= 2)
        or (19 <= now.hour <= 21 and len(fresh) >= 3)
    )
    return publish, sorted(fresh, key=_importance, reverse=True)[:18]


def _compose(items, slot):
    from openai import OpenAI

    if not items:
        raise RuntimeError("No recent Samui news candidates")
    payload = "\n".join(
        f"{i+1}. {x['title']} | {x['published']} | {x['url']}"
        for i, x in enumerate(items)
    )
    prompt = f"""Ты — редактор русскоязычного Telegram-канала Samui News. Сейчас {slot} по Самуи.
Из списка выбери 2–3 действительно важные и разные новости про Ко Самуи. Не выдумывай факты.
Если заголовок не подтверждает деталь, не утверждай её. Юридические, визовые и миграционные сведения
подавай осторожно: укажи, что перед действиями нужно сверить официальный первоисточник.

Сделай дорогой, компактный пост на русском. Видимый текст — максимум {POST_CAPTION_TARGET_CHARS} знаков,
потому что публикация обязательно идёт подписью к фотографии:
первая строка — тематический emoji + жирный заголовок в HTML;
каждый пункт начинается со смыслового emoji, затем <b>короткий подзаголовок</b> и 1 короткое предложение;
после каждого пункта строка «Источник: <a href=\"URL\">название СМИ</a>»;
в конце: «🌊 Samui News — главное об острове без информационного шума.» и 3–5 релевантных хэштегов.
Верни только готовый HTML, допустимы только теги b, i, a. Не добавляй markdown.

Кандидаты:\n{payload}"""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    result = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.25,
        messages=[{"role": "user", "content": prompt}],
    )
    text = (result.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text, flags=re.I)
    if not text:
        raise RuntimeError("OpenAI returned an empty news post")

    # Telegram photo captions have tighter limits than ordinary messages. Ask for a
    # one-pass compression if the model ignored the requested length.
    if len(_plain(text)) > POST_CAPTION_TARGET_CHARS:
        compress_prompt = f"""Сожми этот готовый HTML-пост Samui News так, чтобы видимый текст был строго не длиннее
{POST_CAPTION_TARGET_CHARS} знаков. Сохрани все фактические смыслы, ссылки-источники, финальную строку Samui News
и 3–5 хэштегов. Не добавляй новых фактов. Допустимы только теги b, i, a. Верни только HTML.\n\n{text}"""
        compressed = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.1,
            messages=[{"role": "user", "content": compress_prompt}],
        )
        candidate = (compressed.choices[0].message.content or "").strip()
        candidate = re.sub(r"^```(?:html)?\s*|\s*```$", "", candidate, flags=re.I)
        if candidate:
            text = candidate
    return text


def _plain(html_text):
    return _strip(html_text.replace("<br>", "\n").replace("</p>", "\n"))


def _font(size, bold=False):
    from PIL import ImageFont

    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap_lines(draw, text, font, max_width, max_lines=None):
    words = (text or "").split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if not line or draw.textlength(test, font=font) <= max_width:
            line = test
            continue
        lines.append(line)
        line = word
        if max_lines and len(lines) >= max_lines:
            break
    if line and (not max_lines or len(lines) < max_lines):
        lines.append(line)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


def _source_image_to_jpeg(raw: bytes):
    """Validate and normalize a source article image to a Telegram-friendly JPEG."""
    from PIL import Image, ImageOps

    if not raw or len(raw) > POST_IMAGE_MAX_BYTES:
        return None
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source = ImageOps.exif_transpose(source)
            width, height = source.size
            if width < POST_IMAGE_MIN_WIDTH or height < POST_IMAGE_MIN_HEIGHT:
                return None
            source = source.convert("RGB")
            resampling = getattr(Image, "Resampling", Image).LANCZOS
            image = ImageOps.fit(
                source,
                POST_IMAGE_SIZE,
                method=resampling,
                centering=(0.5, 0.5),
            )
            buf = io.BytesIO()
            image.save(buf, "JPEG", quality=90, optimize=True)
            buf.seek(0)
            buf.name = "samui-news-source.jpg"
            return buf
    except Exception:
        return None


def _image_candidates_from_page(page_url: str):
    """Resolve OG/Twitter preview images from a news article or Google News redirect."""
    if not page_url:
        return []
    try:
        response = requests.get(
            page_url,
            timeout=POST_IMAGE_TIMEOUT_SECONDS,
            headers=_HTTP_HEADERS,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" not in content_type and "xml" not in content_type:
            return []
        parser = _ImageMetaParser()
        parser.feed(response.text[:2_000_000])
        base = response.url or page_url
        result = []
        for value in parser.candidates:
            value = html.unescape(value).strip()
            absolute = urllib.parse.urljoin(base, value)
            if absolute.lower().startswith(("http://", "https://")) and absolute not in result:
                result.append(absolute)
        return result[:8]
    except Exception as exc:
        log.info("Samui News image metadata unavailable url=%s error=%s", page_url, exc)
        return []


def _download_image_url(image_url: str, referer: str = ""):
    headers = dict(_HTTP_HEADERS)
    if referer:
        headers["Referer"] = referer
    try:
        response = requests.get(
            image_url,
            timeout=POST_IMAGE_TIMEOUT_SECONDS,
            headers=headers,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if not content_type.startswith("image/"):
            return None
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > POST_IMAGE_MAX_BYTES:
                    return None
            except Exception:
                pass
        return _source_image_to_jpeg(response.content)
    except Exception as exc:
        log.info("Samui News source image download failed url=%s error=%s", image_url, exc)
        return None


def _article_image(item):
    """Try the article URL first; avoid unrelated publisher-homepage artwork."""
    pages = []
    for page in (item.get("url"),):
        page = (page or "").strip()
        if page and page not in pages:
            pages.append(page)
    for page_url in pages:
        for image_url in _image_candidates_from_page(page_url):
            image = _download_image_url(image_url, referer=page_url)
            if image:
                return image, image_url
    return None, ""


def _fallback_post_image(title, subtitle=""):
    """Create a branded 16:9 image so text-only news can never be published."""
    from PIL import Image, ImageDraw

    width, height = POST_IMAGE_SIZE
    image = Image.new("RGB", POST_IMAGE_SIZE, "#071b35")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        draw.line(
            (0, y, width, y),
            fill=(int(7 + 8 * t), int(27 + 75 * t), int(53 + 95 * t)),
        )

    label_font = _font(34, bold=True)
    title_font = _font(58, bold=True)
    body_font = _font(30)
    brand_font = _font(30, bold=True)

    draw.rounded_rectangle((70, 58, 470, 130), radius=30, fill="#0b74b8")
    draw.text((270, 94), "SAMUI NEWS • СЕГОДНЯ", font=label_font, anchor="mm", fill="white")

    draw.ellipse((1010, 70, 1200, 260), fill="#109bd1", outline="#f4c84a", width=8)
    draw.text((1105, 165), "SN", font=_font(62, bold=True), anchor="mm", fill="white")

    clean_title = _strip(title) or "Главное на Самуи"
    y = 225
    for line in _wrap_lines(draw, clean_title.upper(), title_font, 1000, max_lines=4):
        draw.text((76, y), line, font=title_font, fill="white")
        y += 73

    clean_subtitle = _strip(subtitle)
    if clean_subtitle:
        y += 20
        for line in _wrap_lines(draw, clean_subtitle, body_font, 1020, max_lines=3):
            draw.text((76, y), line, font=body_font, fill="#d9eff8")
            y += 43

    draw.rounded_rectangle((70, 620, 650, 684), radius=26, fill="#f4c84a")
    draw.text(
        (360, 652),
        "ГЛАВНОЕ ОБ ОСТРОВЕ • @samui_news_ru",
        font=brand_font,
        anchor="mm",
        fill="#08203b",
    )

    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92, optimize=True)
    buf.seek(0)
    buf.name = "samui-news-card.jpg"
    return buf


def _story_image(title, subtitle):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1080, 1920), "#071b35")
    draw = ImageDraw.Draw(image)
    for y in range(1920):
        t = y / 1919
        draw.line(
            (0, y, 1080, y),
            fill=(int(7 + 8 * t), int(27 + 83 * t), int(53 + 100 * t)),
        )
    bold = _font(82, bold=True)
    body = _font(48)
    small = _font(38, bold=True)
    draw.rounded_rectangle((70, 85, 1010, 245), 44, fill="#0b74b8")
    draw.text((540, 165), "SAMUI NEWS  •  СЕГОДНЯ", font=small, anchor="mm", fill="white")
    draw.ellipse((380, 350, 700, 670), fill="#109bd1", outline="#f4c84a", width=14)
    draw.text((540, 510), "SN", font=bold, anchor="mm", fill="white")
    y = 810
    for line in _wrap_lines(draw, title.upper(), bold, 900, max_lines=4):
        draw.text((540, y), line, font=bold, anchor="mm", fill="white")
        y += 105
    y += 55
    for line in _wrap_lines(draw, subtitle, body, 860, max_lines=5):
        draw.text((540, y), line, font=body, anchor="mm", fill="#d9eff8")
        y += 68
    draw.rounded_rectangle((160, 1650, 920, 1770), 50, fill="#f4c84a")
    draw.text((540, 1710), "ПОДРОБНОСТИ В КАНАЛЕ  →", font=small, anchor="mm", fill="#08203b")
    draw.text((540, 1840), "@samui_news_ru", font=small, anchor="mm", fill="white")
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    buf.seek(0)
    buf.name = "samui-news-story.jpg"
    return buf


def _story_copy(post):
    plain = _plain(post)
    lines = [x.strip() for x in plain.splitlines() if x.strip()]
    title = re.sub(r"^[^\wА-Яа-я]+", "", lines[0] if lines else "Новости Самуи")
    subtitle = next(
        (
            x
            for x in lines[1:]
            if not x.startswith("Источник") and not x.startswith("#")
        ),
        "Главное об острове — коротко и по делу",
    )
    return title[:90], subtitle[:180]


def _post_image(items, post):
    """Return (BytesIO, provenance) for a guaranteed main-post image."""
    # Prefer images from the highest-ranked candidates. A digest has one cover image;
    # it is tied to its lead/highest-priority story rather than a generic stock photo.
    for item in items[:5]:
        image, source_url = _article_image(item)
        if image:
            log.info(
                "Samui News selected source image title=%s image=%s",
                item.get("title", "")[:120],
                source_url,
            )
            return image, "source"

    title, subtitle = _story_copy(post)
    log.info("Samui News using branded fallback image for slot lead=%s", title[:120])
    return _fallback_post_image(title, subtitle), "branded_fallback"


async def _send_post_with_required_image(client, channel, post, items, slot):
    """Publish a channel post without any text-only fallback path."""
    image, image_kind = await asyncio.to_thread(_post_image, items, post)
    try:
        msg = await client.send_file(
            channel,
            image,
            caption=post,
            parse_mode="html",
            force_document=False,
        )
        return msg, image_kind
    except Exception:
        # A publisher image can be rejected despite successful local decoding. Retry
        # once with our own deterministic JPEG. Never degrade to a bare send_message.
        if image_kind == "source":
            log.exception("Samui News source-image send failed; retrying branded image")
            title, subtitle = _story_copy(post)
            fallback = _fallback_post_image(title, subtitle)
            msg = await client.send_file(
                channel,
                fallback,
                caption=post,
                parse_mode="html",
                force_document=False,
            )
            return msg, "branded_fallback_after_send_error"
        raise


async def _publish(catalog, slot, items, state):
    post = await asyncio.to_thread(_compose, items, slot)
    urls = [x["url"] for x in items[:8]]
    client = await mtproto_user_client._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        message_id = ""
        if not await asyncio.to_thread(_completed, catalog, slot, "post"):
            msg, image_kind = await _send_post_with_required_image(
                client, channel, post, items, slot
            )
            message_id = msg.id
            await asyncio.to_thread(
                _mark, catalog, slot, "post", post, message_id, urls
            )
            log.info(
                "Samui News post published with image: slot=%s mid=%s image=%s",
                slot,
                message_id,
                image_kind,
            )
        if (
            state["stories"] < MAX_STORIES_PER_DAY
            and not await asyncio.to_thread(_completed, catalog, slot, "story")
        ):
            from telethon.tl import functions, types

            title, subtitle = _story_copy(post)
            media_file = await client.upload_file(
                _story_image(title, subtitle), file_name=f"samui-news-{slot}.jpg"
            )
            media = types.InputMediaUploadedPhoto(file=media_file)
            result = await client(
                functions.stories.SendStoryRequest(
                    peer=channel,
                    media=media,
                    privacy_rules=[types.InputPrivacyValueAllowAll()],
                    random_id=random.randint(1, 2**63 - 1),
                    caption="🌊 Samui News — главное об острове.\n\n👉 @samui_news_ru",
                )
            )
            await asyncio.to_thread(
                _mark,
                catalog,
                slot,
                "story",
                title + "\n" + subtitle,
                getattr(result, "id", ""),
                urls,
            )
        log.info("Samui News slot published: %s", slot)
    finally:
        await client.disconnect()


def ensure_started(catalog):
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True

    def runner():
        last_scan_hour = None
        while True:
            try:
                now = datetime.now(TZ)
                scan_key = now.strftime("%Y-%m-%d-%H")
                if now.hour in SCAN_HOURS and scan_key != last_scan_hour:
                    last_scan_hour = scan_key
                    state = _daily_state(catalog, now.strftime("%Y-%m-%d"))
                    items = _fetch_candidates()
                    publish, selected = _should_publish(items, state, now)
                    if publish:
                        slot = f"{scan_key}-{state['posts'] + 1}"
                        asyncio.run(_publish(catalog, slot, selected, state))
                    else:
                        log.info(
                            "Samui News scan complete; no publication warranted: %s",
                            scan_key,
                        )
            except Exception:
                log.exception("Samui News scheduled publication failed")
            time.sleep(60)

    threading.Thread(
        target=runner, name="samui-news-scheduler", daemon=True
    ).start()
    log.info(
        "Samui News event-driven automation active: hourly 07:00-22:00 Asia/Bangkok; "
        "max 3 posts/2 stories; image_required=1"
    )

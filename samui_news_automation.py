# -*- coding: utf-8 -*-
"""Twice-daily Samui News posts and Telegram channel stories via MTProto."""
from __future__ import annotations

import asyncio
import hashlib
import html
import io
import json
import logging
import os
import random
import re
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

import mtproto_user_client

log = logging.getLogger("samui-news")
CHANNEL = os.environ.get("SAMUI_NEWS_CHANNEL", "samui_news_ru").strip().lstrip("@")
TZ = timezone(timedelta(hours=7))
RUN_HOURS = (8, 19)
STATE_SHEET = "SamuiNewsAutomation"
_STARTED = False
_LOCK = threading.Lock()

QUERIES = (
    "Koh Samui news",
    "เกาะสมุย ข่าว",
    "Koh Samui immigration visa",
    "Koh Samui weather ferry airport",
    "Koh Samui event restaurant opening",
)


def _worksheet(catalog):
    sh = catalog._client().open_by_key(catalog.SHEET_ID)
    try:
        return sh.worksheet(STATE_SHEET)
    except Exception:
        ws = sh.add_worksheet(title=STATE_SHEET, rows=1000, cols=6)
        ws.append_row(["slot", "kind", "content_hash", "message_id", "source_urls", "created_at"], value_input_option="RAW")
        return ws


def _completed(catalog, slot, kind):
    try:
        return any(len(r) > 1 and r[0] == slot and r[1] == kind for r in _worksheet(catalog).get_all_values()[1:])
    except Exception:
        log.exception("Could not read Samui News state")
        return False


def _mark(catalog, slot, kind, content, message_id, urls):
    _worksheet(catalog).append_row([
        slot, kind, hashlib.sha256(content.encode("utf-8")).hexdigest()[:16], str(message_id or ""),
        "\n".join(urls)[:4000], datetime.now(timezone.utc).isoformat(timespec="seconds")
    ], value_input_option="RAW")


def _strip(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _fetch_candidates():
    items, seen = [], set()
    for query in QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
            "q": query + " when:3d", "hl": "en", "gl": "TH", "ceid": "TH:en"
        })
        try:
            response = requests.get(url, timeout=20, headers={"User-Agent": "SamuiNews/1.0"})
            response.raise_for_status()
            root = ET.fromstring(response.content)
            for node in root.findall(".//item")[:15]:
                title = _strip(node.findtext("title"))
                link = _strip(node.findtext("link"))
                date = _strip(node.findtext("pubDate"))
                key = title.lower()
                if title and link and key not in seen:
                    seen.add(key)
                    items.append({"title": title, "url": link, "published": date})
        except Exception:
            log.exception("News feed failed: %s", query)
    samui = [x for x in items if re.search(r"samui|สมุย", x["title"], re.I)]
    return (samui or items)[:24]


def _compose(items, slot):
    from openai import OpenAI
    if not items:
        raise RuntimeError("No recent Samui news candidates")
    payload = "\n".join(f"{i+1}. {x['title']} | {x['published']} | {x['url']}" for i, x in enumerate(items))
    prompt = f"""Ты — редактор русскоязычного Telegram-канала Samui News. Сейчас {slot} по Самуи.
Из списка выбери 2–4 действительно важные и разные новости про Ко Самуи. Не выдумывай факты.
Если заголовок не подтверждает деталь, не утверждай её. Юридические, визовые и миграционные сведения
подавай осторожно: укажи, что перед действиями нужно сверить официальный первоисточник.

Сделай дорогой, компактный пост на русском до 1800 знаков:
первая строка — тематический emoji + жирный заголовок в HTML;
каждый пункт начинается со смыслового emoji, затем <b>короткий подзаголовок</b> и 1–2 предложения;
после каждого пункта строка «Источник: <a href="URL">название СМИ</a>»;
в конце: «🌊 Samui News — главное об острове без информационного шума.» и 4–6 релевантных хэштегов.
Верни только готовый HTML, допустимы только теги b, i, a.

Кандидаты:\n{payload}"""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    result = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.25,
        messages=[{"role": "user", "content": prompt}],
    )
    text = (result.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:html)?\s*|\s*```$", "", text, flags=re.I)
    if not text:
        raise RuntimeError("OpenAI returned an empty news post")
    return text


def _plain(html_text):
    return _strip(html_text.replace("<br>", "\n").replace("</p>", "\n"))


def _story_image(title, subtitle):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1080, 1920), "#071b35")
    draw = ImageDraw.Draw(image)
    for y in range(1920):
        t = y / 1919
        draw.line((0, y, 1080, y), fill=(int(7+8*t), int(27+83*t), int(53+100*t)))
    try:
        bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 82)
        body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
    except Exception:
        bold = body = small = ImageFont.load_default()
    draw.rounded_rectangle((70, 85, 1010, 245), 44, fill="#0b74b8")
    draw.text((540, 165), "SAMUI NEWS  •  СЕГОДНЯ", font=small, anchor="mm", fill="white")
    draw.ellipse((380, 350, 700, 670), fill="#109bd1", outline="#f4c84a", width=14)
    draw.text((540, 510), "SN", font=bold, anchor="mm", fill="white")
    def wrapped(text, font, width):
        words, lines, line = text.split(), [], ""
        for word in words:
            test = (line + " " + word).strip()
            if draw.textlength(test, font=font) <= width: line = test
            else:
                if line: lines.append(line)
                line = word
        if line: lines.append(line)
        return lines
    y = 810
    for line in wrapped(title.upper(), bold, 900)[:4]:
        draw.text((540, y), line, font=bold, anchor="mm", fill="white"); y += 105
    y += 55
    for line in wrapped(subtitle, body, 860)[:5]:
        draw.text((540, y), line, font=body, anchor="mm", fill="#d9eff8"); y += 68
    draw.rounded_rectangle((160, 1650, 920, 1770), 50, fill="#f4c84a")
    draw.text((540, 1710), "ПОДРОБНОСТИ В КАНАЛЕ  →", font=small, anchor="mm", fill="#08203b")
    draw.text((540, 1840), "@samui_news_ru", font=small, anchor="mm", fill="white")
    buf = io.BytesIO(); image.save(buf, "JPEG", quality=92); buf.seek(0); return buf


def _story_copy(post):
    plain = _plain(post)
    lines = [x.strip() for x in plain.splitlines() if x.strip()]
    title = re.sub(r"^[^\wА-Яа-я]+", "", lines[0] if lines else "Новости Самуи")
    subtitle = next((x for x in lines[1:] if not x.startswith("Источник") and not x.startswith("#")), "Главное об острове — коротко и по делу")
    return title[:90], subtitle[:180]


async def _publish(catalog, slot):
    items = await asyncio.to_thread(_fetch_candidates)
    post = await asyncio.to_thread(_compose, items, slot)
    urls = [x["url"] for x in items[:8]]
    client = await mtproto_user_client._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        message_id = ""
        if not await asyncio.to_thread(_completed, catalog, slot, "post"):
            msg = await client.send_message(channel, post, parse_mode="html", link_preview=False)
            message_id = msg.id
            await asyncio.to_thread(_mark, catalog, slot, "post", post, message_id, urls)
        if not await asyncio.to_thread(_completed, catalog, slot, "story"):
            from telethon.tl import functions, types
            title, subtitle = _story_copy(post)
            media_file = await client.upload_file(_story_image(title, subtitle), file_name=f"samui-news-{slot}.jpg")
            media = types.InputMediaUploadedPhoto(file=media_file)
            result = await client(functions.stories.SendStoryRequest(
                peer=channel, media=media,
                privacy_rules=[types.InputPrivacyValueAllowAll()],
                random_id=random.randint(1, 2**63 - 1),
                caption="🌊 Samui News — главное об острове.\n\n👉 @samui_news_ru",
            ))
            await asyncio.to_thread(_mark, catalog, slot, "story", title + "\n" + subtitle, getattr(result, "id", ""), urls)
        log.info("Samui News slot published: %s", slot)
    finally:
        await client.disconnect()


def _current_slot(now):
    if now.hour >= RUN_HOURS[1]: return now.strftime("%Y-%m-%d") + "-evening"
    if now.hour >= RUN_HOURS[0]: return now.strftime("%Y-%m-%d") + "-morning"
    return None


def ensure_started(catalog):
    global _STARTED
    with _LOCK:
        if _STARTED: return
        _STARTED = True
    def runner():
        # A due slot is published immediately after deploy; state makes restarts harmless.
        while True:
            try:
                slot = _current_slot(datetime.now(TZ))
                if slot and (not _completed(catalog, slot, "post") or not _completed(catalog, slot, "story")):
                    asyncio.run(_publish(catalog, slot))
            except Exception:
                log.exception("Samui News scheduled publication failed")
            time.sleep(60)
    threading.Thread(target=runner, name="samui-news-scheduler", daemon=True).start()
    log.info("Samui News automation active: 08:00 and 19:00 Asia/Bangkok")

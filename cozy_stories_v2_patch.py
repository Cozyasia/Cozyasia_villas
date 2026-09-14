# -*- coding: utf-8 -*-
"""Production visual/hero-photo patch for Cozy Asia Telegram Stories."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import random
import re
import threading
from datetime import datetime

log = logging.getLogger("cozy-stories-v2")
_ALBUMS = {}


def _font(size, bold=False):
    from PIL import ImageFont
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _fit_font(draw, text, max_width, start, minimum=20, bold=True):
    size = start
    while size > minimum:
        f = _font(size, bold)
        if draw.textlength(text, font=f) <= max_width:
            return f
        size -= 2
    return _font(minimum, bold)


def _wrap(draw, text, font, max_width, max_lines=2):
    words = _clean(text).split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if not line or draw.textlength(test, font=font) <= max_width:
            line = test
            continue
        lines.append(line)
        line = word
        if len(lines) >= max_lines:
            break
    if line and len(lines) < max_lines:
        lines.append(line)
    return lines[:max_lines]


def _listing(meta):
    return bool(meta.get("lot") or re.search(r"(?i)вилл|дом|апартамент|студи|villa|house|condo", meta.get("text", "")))


async def _pick(mod, client, channel, catalog, channel_name, now):
    used = await asyncio.to_thread(mod._used, catalog, channel_name, now)
    msgs = await client.get_messages(channel, limit=max(mod.RECENT * 6, 90))
    groups, order = {}, []
    for msg in msgs:
        if not msg or not getattr(msg, "photo", None):
            continue
        gid = int(getattr(msg, "grouped_id", 0) or 0)
        key = ("g", gid) if gid else ("m", int(msg.id))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(msg)

    pool = []
    for key in order:
        members = sorted(groups[key], key=lambda x: int(x.id))
        source = meta = None
        for msg in members:
            candidate = mod._meta(msg)
            if _listing(candidate):
                source, meta = msg, candidate
                if candidate.get("lot"):
                    break
        if source is None:
            continue
        pool.append((source, meta, members))
        if len(pool) >= mod.RECENT:
            break

    fresh = [x for x in pool if int(x[0].id) not in used] or pool
    promos = [x for x in fresh if x[1].get("promo")]
    chosen = random.choice(promos) if promos and random.random() < 0.45 else (random.choice(fresh[: min(12, len(fresh))]) if fresh else None)
    if not chosen:
        return None, None
    source, meta, members = chosen
    _ALBUMS[id(source)] = members
    return source, meta


async def _download(client, msg):
    from PIL import Image, ImageOps
    try:
        raw = await client.download_media(msg, file=bytes)
        with Image.open(io.BytesIO(raw)) as im:
            return ImageOps.exif_transpose(im).convert("RGB")
    except Exception:
        log.exception("Cozy Stories V2 photo download failed mid=%s", getattr(msg, "id", ""))
        return None


def _vision_index(images):
    if len(images) <= 1:
        return 0
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return 1
    try:
        from openai import OpenAI
        from PIL import Image
        content = [{
            "type": "text",
            "text": (
                "Choose the best HERO photo for a premium real-estate Telegram Story. "
                "Strongly prefer a genuine indoor LIVING ROOM/lounge/open-plan living-dining photo. "
                "Second choice dining/kitchen connected to living area, third bedroom. "
                "Strongly avoid pool-only, exterior, facade, terrace-only, bathroom and empty-view photos. "
                "Prefer bright spacious interiors. Return ONLY the photo number."
            ),
        }]
        for i, image in enumerate(images):
            thumb = image.copy()
            thumb.thumbnail((640, 640), getattr(Image, "Resampling", Image).LANCZOS)
            buf = io.BytesIO(); thumb.save(buf, "JPEG", quality=75, optimize=True)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            content += [
                {"type": "text", "text": "PHOTO %d" % (i + 1)},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + data, "detail": "low"}},
            ]
        resp = OpenAI(api_key=api_key, timeout=30).chat.completions.create(
            model=os.getenv("COZY_STORIES_VISION_MODEL", "gpt-4o-mini"),
            temperature=0,
            max_tokens=8,
            messages=[{"role": "user", "content": content}],
        )
        m = re.search(r"\d+", (resp.choices[0].message.content or "").strip())
        if m:
            idx = int(m.group()) - 1
            if 0 <= idx < len(images):
                return idx
    except Exception:
        log.exception("Cozy Stories V2 living-room ranking failed")
    return 1 if len(images) > 1 else 0


async def _photo(client, msg):
    members = _ALBUMS.pop(id(msg), None) or [msg]
    images, mids = [], []
    for member in members[:10]:
        image = await _download(client, member)
        if image is not None:
            images.append(image); mids.append(int(member.id))
    if not images:
        return None
    idx = await asyncio.to_thread(_vision_index, images[:8])
    idx = min(idx, len(images) - 1)
    log.info("COZY_STORY_V2_HERO source_mid=%s hero_mid=%s position=%s/%s", msg.id, mids[idx], idx + 1, len(images))
    return images[idx]


def _pin(draw, x, y):
    draw.ellipse((x, y, x + 40, y + 40), fill=(235, 68, 67))
    draw.polygon([(x + 11, y + 31), (x + 29, y + 31), (x + 20, y + 55)], fill=(235, 68, 67))
    draw.ellipse((x + 13, y + 13, x + 27, y + 27), fill=(255, 255, 255))


def _money(draw, x, y):
    draw.rounded_rectangle((x + 5, y + 8, x + 50, y + 43), 7, fill=(73, 177, 99))
    draw.rounded_rectangle((x, y + 3, x + 45, y + 38), 7, fill=(111, 210, 126))
    draw.ellipse((x + 13, y + 11, x + 31, y + 29), fill=(245, 230, 130))
    draw.text((x + 22, y + 20), "$", font=_font(16, True), anchor="mm", fill=(35, 110, 60))


def _calendar(draw, x, y):
    draw.rounded_rectangle((x, y + 4, x + 47, y + 47), 8, fill=(247, 248, 250))
    draw.rounded_rectangle((x, y + 4, x + 47, y + 17), 7, fill=(232, 75, 76))
    draw.rectangle((x + 8, y, x + 13, y + 10), fill=(220, 224, 230))
    draw.rectangle((x + 34, y, x + 39, y + 10), fill=(220, 224, 230))
    for ry in (24, 34):
        for rx in (10, 22, 34):
            draw.ellipse((x + rx, y + ry, x + rx + 4, y + ry + 4), fill=(100, 112, 126))


def _weather_icon(draw, x, y):
    draw.ellipse((x + 4, y + 2, x + 30, y + 28), fill=(247, 188, 56))
    draw.ellipse((x + 18, y + 18, x + 52, y + 43), fill=(190, 215, 232))
    draw.ellipse((x + 4, y + 24, x + 43, y + 48), fill=(218, 232, 241))
    for dx in (13, 28, 43):
        draw.line((x + dx, y + 51, x + dx - 4, y + 61), fill=(68, 158, 219), width=4)


def _icon(draw, kind, x, y):
    {"pin": _pin, "money": _money, "calendar": _calendar}[kind](draw, x, y)


def _strip_label(value, label=None):
    value = re.sub(r"^[^\wА-Яа-я0-9]+", "", _clean(value))
    if label:
        value = re.sub(r"(?i)^" + label + r"\s*:\s*", "", value)
    return value.strip()


def _property_image(photo, meta, weather, channel):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    R = getattr(Image, "Resampling", Image).LANCZOS
    blurred = ImageOps.fit(photo, (1080, 1920), method=R).filter(ImageFilter.GaussianBlur(14))
    blurred = ImageEnhance.Brightness(blurred).enhance(0.66)
    hero = ImageOps.fit(photo, (1080, 1920), method=R, centering=(0.5, 0.48))
    base = Image.blend(blurred, hero, 0.9).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0)); d = ImageDraw.Draw(overlay)
    d.rectangle((0, 0, 1080, 500), fill=(3, 18, 31, 172))
    d.rectangle((0, 1218, 1080, 1920), fill=(3, 18, 31, 226))
    d.rectangle((0, 1218, 1080, 1230), fill=(221, 174, 73, 175))
    image = Image.alpha_composite(base, overlay); d = ImageDraw.Draw(image)

    tag = "АКЦИЯ" if meta.get("promo") else "ПРЕДЛОЖЕНИЕ ДНЯ"
    header = "COZY ASIA • " + tag
    d.rounded_rectangle((58, 62, 1022, 175), 42, fill=(238, 183, 70, 245))
    d.text((540, 119), header, font=_fit_font(d, header, 875, 40, 28, True), anchor="mm", fill=(8, 31, 48))

    lot = str(meta.get("lot") or "—")
    d.text((70, 226), lot, font=_font(92, True), fill="white")
    d.text((72, 344), "KOH SAMUI", font=_font(31, True), fill=(220, 231, 238))

    district = _strip_label(meta.get("district", ""), "район")
    price = _strip_label(meta.get("price", ""))
    avail = _strip_label(meta.get("avail", ""))
    rows = []
    if district: rows.append(("pin", "Район: " + district))
    if price:
        rows.append(("money", price if re.search(r"(?i)^(цена|от\s+\d|стоимость|аренда)", price) else "Цена: " + price))
    if avail:
        rows.append(("calendar", avail if "доступ" in avail.lower() else "Доступность: " + avail))

    y = 1280; f = _font(42, True)
    for kind, text in rows[:3]:
        lines = _wrap(d, text, f, 855, 2); _icon(d, kind, 64, y + 4); ly = y
        for line in lines:
            d.text((132, ly), line, font=f, fill="white"); ly += 54
        y = ly + 18

    weather = re.sub(r"^[^\wА-Яа-я0-9]+", "", _clean(weather))
    d.rounded_rectangle((58, 1660, 1022, 1760), 44, fill=(250, 252, 253, 244))
    _weather_icon(d, 92, 1678)
    d.text((590, 1710), weather, font=_fit_font(d, weather, 800, 34, 26, True), anchor="mm", fill=(8, 39, 61))
    d.rounded_rectangle((58, 1800, 1022, 1895), 42, outline=(238, 183, 70), width=4, fill=(4, 25, 42, 155))
    cta = "СМОТРЕТЬ ЛОТ → @" + channel
    d.text((540, 1848), cta, font=_fit_font(d, cta, 875, 34, 25, True), anchor="mm", fill="white")

    buf = io.BytesIO(); image.convert("RGB").save(buf, "JPEG", quality=92, optimize=True); buf.seek(0); buf.name = "cozy-property-story-v2.jpg"
    return buf


async def _delete_v1_today(mod, catalog, day):
    from telethon.tl import functions
    rows = await asyncio.to_thread(mod._state, catalog)
    targets = {}
    for row in rows:
        if len(row) >= 7 and row[0] == day and row[2] == "property" and not str(row[6]).startswith("v2:") and str(row[4]).isdigit():
            targets.setdefault(row[1], []).append(int(row[4]))
    if not targets:
        return
    client = await mod.mtproto_user_client._new_client(catalog)
    if not client:
        return
    try:
        for name, ids in targets.items():
            try:
                channel = await client.get_entity(name)
                await client(functions.stories.DeleteStoriesRequest(peer=channel, id=ids))
                log.info("COZY_STORY_V1_REMOVED @%s ids=%s", name, ids)
            except Exception:
                log.exception("Could not remove V1 story @%s ids=%s", name, ids)
    finally:
        await client.disconnect()


def apply(mod):
    if getattr(mod, "_COZY_V2_PATCHED", False):
        return
    mod._COZY_V2_PATCHED = True
    rebuild_day = os.getenv("COZY_STORIES_REBUILD_DAY", "").strip()
    original_done, original_mark, original_ensure = mod._done, mod._mark, mod.ensure_started

    async def pick(client, channel, catalog, channel_name, now):
        return await _pick(mod, client, channel, catalog, channel_name, now)

    def done(catalog, day, channel, kind):
        if rebuild_day and day == rebuild_day and kind == "property":
            return any(
                len(r) >= 7 and r[0] == day and r[1] == channel and r[2] == "property" and str(r[6]).startswith("v2:")
                for r in mod._state(catalog)
            )
        return original_done(catalog, day, channel, kind)

    def mark(catalog, day, channel, kind, mid, sid, note=""):
        if rebuild_day and day == rebuild_day and kind == "property" and not str(note).startswith("v2:"):
            note = "v2:" + str(note or "")
        return original_mark(catalog, day, channel, kind, mid, sid, note)

    def ensure_started(catalog):
        if rebuild_day:
            def rebuild():
                try:
                    now = datetime.now(mod.TZ); day = now.strftime("%Y-%m-%d")
                    if day != rebuild_day:
                        return
                    asyncio.run(_delete_v1_today(mod, catalog, day))
                    asyncio.run(mod._properties(catalog, day, now))
                except Exception:
                    log.exception("Cozy Stories V2 one-time rebuild failed")
            threading.Thread(target=rebuild, name="cozy-stories-v2-rebuild", daemon=True).start()
        return original_ensure(catalog)

    mod._pick = pick
    mod._photo = _photo
    mod._property_image = _property_image
    mod._done = done
    mod._mark = mark
    mod.ensure_started = ensure_started
    log.info("Cozy Stories V2 patch applied: graphic icons, full header, living-room hero preference")

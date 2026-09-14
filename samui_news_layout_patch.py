# -*- coding: utf-8 -*-
"""Safe Samui News fallback-card layout + one-time repair for the 2026-09-14 post.

This patch is intentionally small and isolated. It fixes three production issues:
- preserve logical line breaks when deriving card copy from an HTML caption;
- fit headline/subtitle/pills inside strict safe areas with adaptive typography;
- replace the already-published overflowing fallback media in place, keeping the
  existing Telegram post/caption/message id intact.
"""
from __future__ import annotations

import asyncio
import html
import io
import logging
import re
import threading
import time

log = logging.getLogger("samui-news-layout-patch")
PATCH_SLOT = "repair-2026-09-14-fallback-overflow-v2"


def _shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: max(1, limit - 1)].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    return cut + "…"


def _caption_lines(post: str) -> list[str]:
    value = post or ""
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    out: list[str] = []
    for raw in value.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            out.append(line)
    return out


def _clean_leading_symbol(value: str) -> str:
    return re.sub(r"^[^0-9A-Za-zА-Яа-яЁё]+", "", value or "").strip()


def _safe_story_copy(post: str):
    lines = _caption_lines(post)
    if not lines:
        return "Новости Самуи", "Главное об острове — коротко и по делу"

    title = _clean_leading_symbol(lines[0]) or "Новости Самуи"
    # Normalize the most common generated phrase for a cleaner card headline.
    title = re.sub(r"\bНовости\s+Ко\s+Самуи\b", "Новости Самуи", title, flags=re.I)

    subtitle = "Главное об острове — коротко и по делу"
    for line in lines[1:]:
        low = line.lower()
        if low.startswith("источник:") or low.startswith("http") or line.startswith("#"):
            continue
        if "samui news — главное об острове" in low:
            continue
        candidate = _clean_leading_symbol(line)
        if candidate:
            subtitle = candidate
            break

    return _shorten(title, 64), _shorten(subtitle, 96)


def _wrap(draw, text, font, max_width):
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if not current or draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_block(news, draw, text, max_width, max_height, start_size, min_size, max_lines, bold=True):
    for size in range(start_size, min_size - 1, -2):
        font = news._font(size, bold=bold)
        lines = _wrap(draw, text, font, max_width)
        line_h = int(size * 1.22)
        if len(lines) <= max_lines and len(lines) * line_h <= max_height:
            return font, lines, line_h

    font = news._font(min_size, bold=bold)
    lines = _wrap(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last or "").rstrip(" .,:;-") + "…"
    return font, lines, int(min_size * 1.22)


def _safe_fallback_factory(news):
    def _safe_fallback_post_image(title, subtitle=""):
        from PIL import Image, ImageDraw

        width, height = news.POST_IMAGE_SIZE
        image = Image.new("RGB", (width, height), "#071b35")
        draw = ImageDraw.Draw(image)

        # Deep-blue to teal gradient, deliberately quiet behind copy.
        for y in range(height):
            t = y / max(height - 1, 1)
            draw.line(
                (0, y, width, y),
                fill=(int(7 + 6 * t), int(27 + 66 * t), int(53 + 90 * t)),
            )

        # Subtle island/wave silhouettes on the right; never under the main copy.
        draw.polygon(
            [(805, 565), (900, 505), (980, 540), (1070, 470), (1160, 515), (1280, 450), (1280, 720), (805, 720)],
            fill="#0b496c",
        )
        draw.ellipse((870, 565, 1450, 900), fill="#0a3e5d")

        left = 70
        safe_right = 965

        # Top label: width is measured from the actual copy, so it cannot overflow.
        label = "SAMUI NEWS • СЕГОДНЯ"
        label_font = news._font(28, bold=True)
        label_w = int(draw.textlength(label, font=label_font))
        pill_right = min(safe_right, left + label_w + 58)
        draw.rounded_rectangle((left, 48, pill_right, 112), radius=28, fill="#0b83c6")
        draw.text((left + 29, 80), label, font=label_font, anchor="lm", fill="white")

        # Fixed brand mark in its own reserved area.
        draw.ellipse((1050, 48, 1204, 202), fill="#109bd1", outline="#f4c84a", width=7)
        draw.text((1127, 125), "SN", font=news._font(52, bold=True), anchor="mm", fill="white")

        clean_title = _shorten(re.sub(r"\s+", " ", title or "").strip() or "Новости Самуи", 72)
        title_font, title_lines, title_h = _fit_block(
            news, draw, clean_title.upper(), safe_right - left, 245, 58, 38, 4, True
        )

        y = 178
        for line in title_lines:
            draw.text((left, y), line, font=title_font, fill="white")
            y += title_h

        clean_subtitle = _shorten(re.sub(r"\s+", " ", subtitle or "").strip(), 110)
        if clean_subtitle:
            y += 16
            body_font, body_lines, body_h = _fit_block(
                news, draw, clean_subtitle, safe_right - left, 98, 30, 24, 2, False
            )
            for line in body_lines:
                draw.text((left, y), line, font=body_font, fill="#d9eff8")
                y += body_h

        # Footer is deliberately short. No long sentence is ever placed inside it.
        handle = "@samui_news_ru"
        footer_font = news._font(28, bold=True)
        footer_w = int(draw.textlength(handle, font=footer_font))
        footer_right = min(670, left + footer_w + 62)
        draw.rounded_rectangle((left, 620, footer_right, 680), radius=25, fill="#f4c84a")
        draw.text((left + 31, 650), handle, font=footer_font, anchor="lm", fill="#08203b")

        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=92, optimize=True)
        buf.seek(0)
        buf.name = "samui-news-card-safe.jpg"
        return buf

    return _safe_fallback_post_image


async def _repair_current_post(catalog, news, mt):
    try:
        if await asyncio.to_thread(news._completed, catalog, PATCH_SLOT, "repair"):
            log.info("Samui News overflow repair already completed")
            return
    except Exception:
        log.exception("Could not read Samui News repair state; continuing with guarded scan")

    client = await mt._new_client(catalog)
    if not client:
        raise RuntimeError("MTProto session is not authorized")

    try:
        channel = await client.get_entity(news.CHANNEL)
        target = None
        async for message in client.iter_messages(channel, limit=30):
            body = (getattr(message, "message", "") or "").lower()
            if (
                "14 сентября 2026" in body
                and "проблем" in body
                and "турист" in body
            ):
                target = message
                break

        if not target:
            log.warning("Samui News overflow repair target not found in latest 30 messages")
            return

        title, subtitle = news._story_copy(target.message or "")
        replacement = news._fallback_post_image(title, subtitle)
        await client.edit_message(
            channel,
            target.id,
            text=target.message or "",
            file=replacement,
            formatting_entities=getattr(target, "entities", None),
            force_document=False,
        )
        await asyncio.to_thread(
            news._mark,
            catalog,
            PATCH_SLOT,
            "repair",
            target.message or "",
            target.id,
            [],
        )
        log.info("Samui News overflow media repaired in place: mid=%s", target.id)
    finally:
        await client.disconnect()


def apply(news, mt, catalog):
    """Install safe copy/layout functions and launch one-time in-place media repair."""
    if getattr(news, "_SAFE_LAYOUT_PATCH_V2", False):
        return
    news._SAFE_LAYOUT_PATCH_V2 = True
    news._story_copy = _safe_story_copy
    news._fallback_post_image = _safe_fallback_factory(news)
    log.info("Samui News safe fallback layout patch v2 enabled")

    def runner():
        # Let the web service finish basic startup before MTProto edit traffic.
        time.sleep(6)
        try:
            asyncio.run(_repair_current_post(catalog, news, mt))
        except Exception:
            log.exception("Samui News one-time overflow media repair failed")

    threading.Thread(target=runner, name="samui-news-media-repair-v2", daemon=True).start()

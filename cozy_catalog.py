# -*- coding: utf-8 -*-
"""Cozy Asia property catalog layer."""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import threading
import unicodedata
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("villa-catalog")

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "").strip()
GOOGLE_CREDS_RAW = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
LOTS_WORKSHEET_NAME = os.environ.get("LOTS_WORKSHEET_NAME", "Lots").strip() or "Lots"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_PROJECT = os.environ.get("OPENAI_PROJECT", "").strip()
OPENAI_ORG = os.environ.get("OPENAI_ORG", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
CATALOG_CHANNEL = os.environ.get("CATALOG_CHANNEL", "arenda_vill_samui").strip().lstrip("@")
CATALOG_BOOTSTRAP_LIMIT = int(os.environ.get("CATALOG_BOOTSTRAP_LIMIT", "20") or "20")
CATALOG_BOOTSTRAP_IMPORT = os.environ.get("CATALOG_BOOTSTRAP_IMPORT", "1").strip().lower() not in {"0", "false", "no", "off"}

CATALOG_HEADERS = [
    "lot_id", "telegram_message_id", "telegram_url", "published_at", "status",
    "тип", "район", "спальни", "ванные", "бассейн", "тип_бассейна",
    "цена_месяц_thb", "цена_сутки_thb", "депозит_thb", "комиссия_thb",
    "до_моря_м", "доступность", "питомцы", "электричество", "вода",
    "контакт_собственника", "описание", "исходный_текст", "extracted_at",
    "confidence", "needs_review",
]

_sheet_lock = threading.RLock()
_catalog_bootstrap_done = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _gspread_client():
    if not SHEET_ID or not GOOGLE_CREDS_RAW:
        raise RuntimeError("Google Sheets catalog disabled: credentials are missing")
    import gspread
    from google.oauth2.service_account import Credentials
    info = json.loads(GOOGLE_CREDS_RAW)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


def ensure_lots_sheet():
    with _sheet_lock:
        client = _gspread_client()
        book = client.open_by_key(SHEET_ID)
        try:
            ws = book.worksheet(LOTS_WORKSHEET_NAME)
        except Exception:
            ws = book.add_worksheet(title=LOTS_WORKSHEET_NAME, rows=2000, cols=max(30, len(CATALOG_HEADERS)))
            ws.append_row(CATALOG_HEADERS, value_input_option="RAW")
            log.info("Created worksheet %s", LOTS_WORKSHEET_NAME)
            return ws
        values = ws.get_all_values()
        if not values:
            ws.append_row(CATALOG_HEADERS, value_input_option="RAW")
        else:
            current = list(values[0])
            changed = False
            for h in CATALOG_HEADERS:
                if h not in current:
                    current.append(h)
                    changed = True
            if changed:
                ws.update("A1", [current], value_input_option="RAW")
        return ws


def _rows_as_dicts(ws) -> List[Dict[str, str]]:
    vals = ws.get_all_values()
    if not vals:
        return []
    headers = vals[0]
    rows = []
    for row in vals[1:]:
        padded = row + [""] * max(0, len(headers) - len(row))
        rows.append(dict(zip(headers, padded)))
    return rows


def _normalize_emoji_digits(text: str) -> str:
    s = (text or "").replace("\ufe0f", "").replace("\u20e3", "")
    s = s.replace("➖", "-").replace("–", "-").replace("—", "-").replace("−", "-")
    s = unicodedata.normalize("NFKC", s)
    out = []
    for ch in s:
        try:
            d = unicodedata.digit(ch)
        except (TypeError, ValueError):
            out.append(ch)
        else:
            out.append(str(int(d)))
    return "".join(out)


def extract_lot_id(text: str) -> str:
    raw = text or ""
    normalized = _normalize_emoji_digits(raw)
    first_lines = [x.strip() for x in normalized.splitlines()[:4] if x.strip()]
    head = "\n".join(first_lines)
    patterns = [
        r"(?i)(?:лот|lot)\s*(?:№|#|n[oо]\.?)?\s*[:\-]?\s*(\d{3,7})",
        r"(?:№|#)\s*(\d{3,7})",
    ]
    for pat in patterns:
        m = re.search(pat, head)
        if m:
            return m.group(1).lstrip("0") or "0"
    if first_lines:
        original_first = (raw.splitlines() or [""])[0]
        first = first_lines[0]
        looks_decorative = ("\u20e3" in original_first or "🔤" in original_first or "№" in first or "лот" in first.lower() or "lot" in first.lower())
        if looks_decorative:
            groups = re.findall(r"(?<!\d)(\d{3,7})(?!\d)", first)
            if groups:
                return groups[-1].lstrip("0") or "0"
    return ""


def _is_listing_candidate(text: str, lot_id: str = "") -> bool:
    if lot_id:
        return True
    t = (text or "").lower()
    housing = any(k in t for k in ("вилла", "дом", "апартамент", "квартира", "студия", "villa", "house", "apartment", "condo", "bungalow"))
    money = any(k in t for k in ("бат", "thb", "฿", "стоимость", "аренд"))
    return housing and money


def _clean_number(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    s = str(value).strip()
    if not s:
        return ""
    digits = re.sub(r"[^\d.]", "", s)
    return digits or s


def _fallback_extract(text: str) -> Dict[str, str]:
    t = text or ""
    low = t.lower()
    result = {
        "lot_id": extract_lot_id(t), "тип": "", "район": "", "спальни": "", "ванные": "",
        "бассейн": "unknown", "тип_бассейна": "unknown", "цена_месяц_thb": "",
        "цена_сутки_thb": "", "депозит_thb": "", "комиссия_thb": "", "до_моря_м": "",
        "доступность": "", "питомцы": "unknown", "электричество": "", "вода": "",
        "контакт_собственника": "", "описание": "", "confidence": "low", "needs_review": "yes",
    }
    if "вилла" in low or "villa" in low:
        result["тип"] = "вилла"
    elif "апартамент" in low or "квартир" in low or "condo" in low or "apartment" in low:
        result["тип"] = "апартаменты"
    elif "дом" in low or "house" in low:
        result["тип"] = "дом"
    m = re.search(r"(?i)(\d+)\s*(?:[-–—]?\s*)?(?:спальн|bedroom|br\b)", t) or re.search(r"(?i)спальн\w*\s*[:\-]?\s*(\d+)", t)
    if m:
        result["спальни"] = m.group(1)
    m = re.search(r"(?i)(\d+)\s*(?:ванн|сануз|bathroom)", t) or re.search(r"(?i)(?:ванн|сануз)\w*\s*[:\-]?\s*(\d+)", t)
    if m:
        result["ванные"] = m.group(1)
    if "бассейн" in low or "pool" in low:
        result["бассейн"] = "yes"
        if any(k in low for k in ("приват", "частн", "private pool", "собственн")):
            result["тип_бассейна"] = "private"
        elif "общий бассейн" in low or "shared pool" in low:
            result["тип_бассейна"] = "shared"
    m = re.search(r"(?i)(?:стоимость|аренда|цена)[^\n]{0,30}?([\d\s'.,]{4,})\s*(?:бат|thb|฿)[^\n]{0,20}?(?:месяц|мес)", t)
    if m:
        result["цена_месяц_thb"] = re.sub(r"\D", "", m.group(1))
    return result


def _openai_extract(text: str) -> Dict[str, str]:
    if not OPENAI_API_KEY:
        return _fallback_extract(text)
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY, project=OPENAI_PROJECT or None, organization=OPENAI_ORG or None, timeout=45)
    system = """
Ты извлекаешь факты из объявления Cozy Asia об аренде недвижимости на Самуи. Верни ТОЛЬКО JSON-объект.
Ничего не додумывай. Если факта нет, ставь пустую строку или unknown.
Не считай @cozy_asia, оператора, менеджера или контакты Cozy Asia контактом собственника.
контакт_собственника заполняй ТОЛЬКО если текст явно говорит, что это собственник/хозяин/landlord/owner.
Если бассейн не упомянут: бассейн=unknown. Если расстояние до моря не указано: до_моря_м="".
Числовые цены возвращай цифрами без пробелов и валюты. тип_бассейна: private/shared/unknown.
питомцы: yes/no/discuss/unknown. needs_review=yes при неоднозначности, иначе no. confidence: high/medium/low.
Ключи JSON: lot_id, тип, район, спальни, ванные, бассейн, тип_бассейна, цена_месяц_thb,
цена_сутки_thb, депозит_thb, комиссия_thb, до_моря_м, доступность, питомцы,
электричество, вода, контакт_собственника, описание, confidence, needs_review.
описание — 1-2 предложения только об объекте, без рекламы и контактов.
"""
    normalized = _normalize_emoji_digits(text)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": "Исходный пост:\n" + text + "\n\nНормализованный заголовок:\n" + "\n".join(normalized.splitlines()[:4])}],
        response_format={"type": "json_object"}, temperature=0, max_tokens=900,
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    return {str(k): "" if v is None else str(v).strip() for k, v in data.items()}


def extract_listing(text: str) -> Dict[str, str]:
    deterministic_lot = extract_lot_id(text)
    try:
        data = _openai_extract(text)
    except Exception as e:
        log.warning("OpenAI extraction failed, using fallback: %s", e)
        data = _fallback_extract(text)
    if deterministic_lot:
        data["lot_id"] = deterministic_lot
    data.setdefault("lot_id", "")
    data.setdefault("confidence", "medium" if deterministic_lot else "low")
    data.setdefault("needs_review", "no" if deterministic_lot else "yes")
    for key in ("цена_месяц_thb", "цена_сутки_thb", "депозит_thb", "комиссия_thb", "до_моря_м"):
        if key in data:
            data[key] = _clean_number(data[key])
    return data


def _existing_by_message_id(ws) -> Tuple[Dict[str, Tuple[int, Dict[str, str]]], Dict[str, int]]:
    headers = ws.row_values(1)
    hmap = {h: i for i, h in enumerate(headers)}
    rows = ws.get_all_values()
    out = {}
    for sheet_row_num, row in enumerate(rows[1:], start=2):
        padded = row + [""] * max(0, len(headers) - len(row))
        d = dict(zip(headers, padded))
        mid = d.get("telegram_message_id", "").strip()
        if mid:
            out[mid] = (sheet_row_num, d)
    return out, hmap


def upsert_listing(*, text: str, message_id: str, telegram_url: str, published_at: str = "", force: bool = False) -> Dict[str, str]:
    with _sheet_lock:
        ws = ensure_lots_sheet()
        existing, _ = _existing_by_message_id(ws)
        current = existing.get(str(message_id))
        if current and not force:
            _, old = current
            if old.get("исходный_текст", "") == (text or ""):
                return {"action": "skipped", "lot_id": old.get("lot_id", ""), "message_id": str(message_id)}
        parsed = extract_listing(text)
        record = {h: "" for h in CATALOG_HEADERS}
        record.update(parsed)
        record["telegram_message_id"] = str(message_id)
        record["telegram_url"] = telegram_url
        record["published_at"] = published_at
        record["status"] = "active"
        record["исходный_текст"] = text or ""
        record["extracted_at"] = _now_iso()
        if current:
            _, old = current
            if old.get("контакт_собственника", "").strip():
                record["контакт_собственника"] = old["контакт_собственника"].strip()
            if old.get("status", "").strip():
                record["status"] = old["status"].strip()
        headers = ws.row_values(1)
        row_values = [record.get(h, "") for h in headers]
        if current:
            row_num, _ = current
            ws.update(f"A{row_num}", [row_values], value_input_option="USER_ENTERED")
            action = "updated"
        else:
            ws.append_row(row_values, value_input_option="USER_ENTERED")
            action = "inserted"
        log.info("Catalog %s message=%s lot=%s", action, message_id, record.get("lot_id") or "—")
        return {"action": action, "lot_id": record.get("lot_id", ""), "message_id": str(message_id)}


def _parse_public_channel_html(channel: str) -> List[Dict[str, str]]:
    url = f"https://t.me/s/{channel}"
    r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 (compatible; CozyAsiaCatalog/1.0)", "Accept-Language": "ru,en;q=0.8"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for msg in soup.select(".tgme_widget_message"):
        data_post = (msg.get("data-post") or "").strip()
        if not data_post or "/" not in data_post:
            continue
        _, mid = data_post.rsplit("/", 1)
        if not mid.isdigit():
            continue
        text_node = msg.select_one(".tgme_widget_message_text")
        if text_node is None:
            continue
        text = html.unescape(text_node.get_text("\n", strip=True)).strip()
        if not text:
            continue
        time_node = msg.select_one("time")
        published_at = (time_node.get("datetime") or "").strip() if time_node is not None else ""
        date_link = msg.select_one("a.tgme_widget_message_date")
        post_url = (date_link.get("href") or "").strip() if date_link is not None else ""
        if not post_url:
            post_url = f"https://t.me/{channel}/{mid}"
        items.append({"message_id": mid, "telegram_url": post_url, "published_at": published_at, "text": text})
    items.sort(key=lambda x: int(x["message_id"]))
    return items


def import_public_channel_latest(limit: int = 20, force: bool = False) -> Dict[str, object]:
    limit = max(1, min(int(limit or 20), 50))
    ws = ensure_lots_sheet()
    existing, _ = _existing_by_message_id(ws)
    posts = _parse_public_channel_html(CATALOG_CHANNEL)
    inspected = posts[-limit:]
    stats = {"channel": CATALOG_CHANNEL, "inspected": len(inspected), "listing_candidates": 0, "inserted": 0, "updated": 0, "skipped": 0, "needs_review": 0, "errors": 0, "lots": []}
    for post in inspected:
        try:
            lot_id = extract_lot_id(post["text"])
            if not _is_listing_candidate(post["text"], lot_id):
                continue
            stats["listing_candidates"] += 1
            old = existing.get(post["message_id"])
            if old and not force and old[1].get("исходный_текст", "") == post["text"]:
                stats["skipped"] += 1
                old_lot = old[1].get("lot_id", "")
                if old_lot:
                    stats["lots"].append(old_lot)
                continue
            result = upsert_listing(text=post["text"], message_id=post["message_id"], telegram_url=post["telegram_url"], published_at=post["published_at"], force=force)
            action = result.get("action", "")
            if action in stats:
                stats[action] += 1
            if result.get("lot_id"):
                stats["lots"].append(result["lot_id"])
            existing, _ = _existing_by_message_id(ws)
        except Exception as e:
            stats["errors"] += 1
            log.exception("Failed importing public post %s: %s", post.get("message_id"), e)
    current, _ = _existing_by_message_id(ws)
    for post in inspected:
        row = current.get(post["message_id"])
        if row and row[1].get("needs_review", "").lower() == "yes":
            stats["needs_review"] += 1
    stats["lots"] = list(dict.fromkeys(stats["lots"]))
    return stats


def catalog_status() -> Dict[str, object]:
    ws = ensure_lots_sheet()
    rows = _rows_as_dicts(ws)
    active = [r for r in rows if r.get("status", "active").strip().lower() != "inactive"]
    review = [r for r in rows if r.get("needs_review", "").strip().lower() == "yes"]
    last = [r.get("lot_id") or f"msg:{r.get('telegram_message_id')}" for r in rows[-5:]]
    return {"rows": len(rows), "active": len(active), "needs_review": len(review), "last": last}


async def cmd_catalog_import(update, context):
    limit = CATALOG_BOOTSTRAP_LIMIT
    if getattr(context, "args", None):
        try:
            limit = int(context.args[0])
        except Exception:
            pass
    limit = max(1, min(limit, 50))
    msg = update.effective_message
    await msg.reply_text(f"Импортирую последние {limit} публикаций из @{CATALOG_CHANNEL}…")
    try:
        stats = await asyncio.to_thread(import_public_channel_latest, limit, False)
        await msg.reply_text("Каталог обновлён.\n" f"Проверено постов: {stats['inspected']}\n" f"Объявлений: {stats['listing_candidates']}\n" f"Добавлено: {stats['inserted']}, обновлено: {stats['updated']}, без изменений: {stats['skipped']}\n" f"Нужна проверка: {stats['needs_review']}, ошибок: {stats['errors']}\n" f"Лоты: {', '.join(stats['lots'][:20]) or '—'}")
    except Exception as e:
        log.exception("Manual catalog import failed")
        await msg.reply_text(f"Импорт не выполнен: {type(e).__name__}: {e}")


async def cmd_catalog_status(update, context):
    try:
        s = await asyncio.to_thread(catalog_status)
        await update.effective_message.reply_text("Каталог Lots:\n" f"Всего строк: {s['rows']}\n" f"Активных: {s['active']}\n" f"Нужна проверка: {s['needs_review']}\n" f"Последние: {', '.join(s['last']) or '—'}")
    except Exception as e:
        await update.effective_message.reply_text(f"Каталог недоступен: {type(e).__name__}: {e}")


async def catch_catalog_updates(update, context):
    msg = getattr(update, "channel_post", None) or getattr(update, "edited_channel_post", None)
    if msg is None:
        return
    chat = getattr(msg, "chat", None)
    username = (getattr(chat, "username", "") or "").lstrip("@")
    if username.lower() != CATALOG_CHANNEL.lower():
        return
    text = (getattr(msg, "text", None) or getattr(msg, "caption", None) or "").strip()
    if not text:
        return
    lot_id = extract_lot_id(text)
    if not _is_listing_candidate(text, lot_id):
        return
    url = f"https://t.me/{CATALOG_CHANNEL}/{msg.message_id}"
    published_at = ""
    if getattr(msg, "date", None):
        try:
            published_at = msg.date.astimezone(timezone.utc).isoformat(timespec="seconds")
        except Exception:
            published_at = str(msg.date)
    try:
        await asyncio.to_thread(upsert_listing, text=text, message_id=str(msg.message_id), telegram_url=url, published_at=published_at, force=True)
    except Exception:
        log.exception("Failed to ingest channel post %s", msg.message_id)


def install_handlers(app) -> None:
    if getattr(app, "_cozy_catalog_handlers_installed", False):
        return
    from telegram.ext import CommandHandler, MessageHandler, filters
    app.add_handler(CommandHandler("catalog_import", cmd_catalog_import), group=-20)
    app.add_handler(CommandHandler("catalog_status", cmd_catalog_status), group=-20)
    app.add_handler(MessageHandler(filters.ALL, catch_catalog_updates), group=-10)
    setattr(app, "_cozy_catalog_handlers_installed", True)
    log.info("Catalog handlers installed for @%s", CATALOG_CHANNEL)


async def post_initialize(app) -> None:
    global _catalog_bootstrap_done
    if _catalog_bootstrap_done:
        return
    _catalog_bootstrap_done = True
    try:
        await asyncio.to_thread(ensure_lots_sheet)
        log.info("Lots worksheet ready")
    except Exception:
        log.exception("Could not initialize Lots worksheet")
        return
    if not CATALOG_BOOTSTRAP_IMPORT:
        return
    try:
        stats = await asyncio.to_thread(import_public_channel_latest, CATALOG_BOOTSTRAP_LIMIT, False)
        log.info("Bootstrap catalog import: %s", stats)
    except Exception:
        log.exception("Bootstrap public-channel import failed")

"""Safe lookup of a Cozy Asia lot's internal owner card for VillaBot leads.

The public Telegram post contains only a lot number.  This module resolves the
number against the private registry only when the result is unambiguous.  It
never returns an arbitrary owner for a duplicate historical lot number.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple


log = logging.getLogger("villa-lead-context")

REGISTRY_SHEET_ID = os.environ.get(
    "COZY_VILLA_REGISTRY_SHEET_ID",
    "1AUXHak2TrKH-r3U_J4_pmUF6r8VjS1loa4SSGmcy2JE",
).strip()
REGISTRY_WORKSHEET = os.environ.get(
    "COZY_VILLA_REGISTRY_WORKSHEET", "Полный реестр — все каналы"
).strip()
CACHE_SECONDS = max(0, int(os.environ.get("COZY_VILLA_REGISTRY_CACHE_SECONDS", "60")))

SMALL_CHANNEL = "a"
LARGE_CHANNEL = "b"
_PAYLOAD_RE = re.compile(r"^rent_v_([ab])_(\d{1,12})_([A-Za-z0-9-]{1,40})$", re.I)
_LEGACY_LOT_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

_cached_rows: List[Dict[str, str]] = []
_cache_until = 0.0


@dataclass(frozen=True)
class LeadLotIdentity:
    lot_id: str = ""
    channel: str = ""
    message_id: str = ""


@dataclass(frozen=True)
class OwnerContext:
    status: str
    text: str
    fields: Mapping[str, str]


def parse_rent_payload(payload: str) -> LeadLotIdentity:
    """Accept historical ``rent_<lot>`` links and precise v2 deep links."""
    raw = (payload or "").strip()
    match = _PAYLOAD_RE.fullmatch(raw)
    if match:
        return LeadLotIdentity(lot_id=match.group(3), channel=match.group(1).lower(), message_id=match.group(2))
    if raw.lower().startswith("rent_"):
        lot_id = raw[5:].strip()
        if _LEGACY_LOT_RE.fullmatch(lot_id):
            return LeadLotIdentity(lot_id=lot_id)
    return LeadLotIdentity()


def _value(row: Mapping[str, str], name: str) -> str:
    return (row.get(name) or "").strip()


def _load_registry_rows() -> List[Dict[str, str]]:
    global _cached_rows, _cache_until
    now = time.monotonic()
    if _cached_rows and now < _cache_until:
        return _cached_rows

    raw_creds = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
    if not REGISTRY_SHEET_ID or not raw_creds:
        log.warning("Owner-card lookup unavailable: registry or Google credentials are missing")
        return []
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        credentials = Credentials.from_service_account_info(
            json.loads(raw_creds),
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        worksheet = gspread.authorize(credentials).open_by_key(REGISTRY_SHEET_ID).worksheet(REGISTRY_WORKSHEET)
        rows = worksheet.get_all_records(default_blank="")
        _cached_rows = [{str(k): str(v) for k, v in row.items()} for row in rows]
        _cache_until = now + CACHE_SECONDS
        return _cached_rows
    except Exception as exc:  # fail closed: no private data if the registry cannot be read
        log.error("Owner-card lookup failed: %s", exc)
        return []


def _by_message(rows: Iterable[Dict[str, str]], identity: LeadLotIdentity) -> List[Dict[str, str]]:
    column = "Ссылка — малый канал" if identity.channel == SMALL_CHANNEL else "Ссылка — большой канал"
    needle = f"/{identity.message_id}"
    return [row for row in rows if needle in _value(row, column)]


def _by_lot(rows: Iterable[Dict[str, str]], identity: LeadLotIdentity) -> List[Dict[str, str]]:
    column = "№ лота — малый канал" if identity.channel != LARGE_CHANNEL else "№ лота — большой канал"
    wanted = identity.lot_id.casefold()
    return [row for row in rows if _value(row, column).casefold() == wanted]


def _missing(reason: str, status: str = "не найден") -> OwnerContext:
    return OwnerContext(status=status, text=f"🔒 Внутренняя карточка объекта\nСтатус: {status}\n{reason}", fields={})


def _format_row(row: Mapping[str, str]) -> OwnerContext:
    names: Tuple[Tuple[str, str], ...] = (
        ("Внутренний ID", "ID"),
        ("Статус контакта", "Статус контакта"),
        ("Имя собственника / агента", "Собственник / агент"),
        ("WhatsApp собственника", "WhatsApp"),
        ("Телефон собственника", "Телефон"),
        ("Альтернативный контакт", "Альтернативный контакт"),
        ("Facebook-профиль", "Facebook"),
        ("Исходное объявление", "Исходное объявление"),
        ("Источник контакта", "Источник контакта"),
    )
    fields = {label: _value(row, source) for source, label in names}
    lines = ["🔒 Внутренняя карточка объекта"]
    for label in ("ID", "Статус контакта", "Собственник / агент", "WhatsApp", "Телефон", "Альтернативный контакт", "Facebook", "Исходное объявление", "Источник контакта"):
        if fields[label]:
            lines.append(f"{label}: {fields[label]}")
    if len(lines) == 1:
        lines.append("Статус: требует проверки — карточка есть, но внутренних контактов нет")
    status = fields.get("Статус контакта") or "требует проверки"
    return OwnerContext(status=status, text="\n".join(lines), fields=fields)


def resolve_owner_context(identity: LeadLotIdentity) -> OwnerContext:
    if not identity.lot_id:
        return _missing("Лот в ссылке не указан.", "требует проверки")
    rows = _load_registry_rows()
    if not rows:
        return _missing("Реестр недоступен или пока пуст.", "требует проверки")

    if identity.channel and identity.message_id:
        matches = _by_message(rows, identity)
        if len(matches) == 1:
            return _format_row(matches[0])
        if len(matches) > 1:
            return _missing("Найдено несколько карточек по ссылке на пост; нужна ручная проверка.", "требует проверки")

    matches = _by_lot(rows, identity)
    if len(matches) == 1:
        return _format_row(matches[0])
    if len(matches) > 1:
        return _missing(
            f"Номер лота {identity.lot_id} встречается в нескольких исторических карточках. Контакт не подставлен автоматически.",
            "требует проверки",
        )
    return _missing(f"Лот {identity.lot_id} не найден в едином реестре.")

def resolve_lot_post_links(identity: LeadLotIdentity) -> List[str]:
    """Return only verified Telegram post URLs from the shared registry.

    Prefer an exact channel/message match. Legacy lot numbers are accepted
    only when the matching registry rows yield one unambiguous URL.
    """
    rows = _load_registry_rows()
    if not rows:
        return []
    channel_columns = {
        SMALL_CHANNEL: "Ссылка — малый канал",
        LARGE_CHANNEL: "Ссылка — большой канал",
    }
    if identity.channel in channel_columns and identity.message_id:
        column = channel_columns[identity.channel]
        exact = [
            _value(row, column) for row in rows
            if re.search(r"/" + re.escape(identity.message_id) + r"(?:\?|$|/)", _value(row, column))
        ]
        exact = list(dict.fromkeys(url for url in exact if _valid_telegram_post(url)))
        if len(exact) == 1:
            return exact
        if len(exact) > 1:
            return []
    lot_ids = [part.strip() for part in re.split(r"[,;\s]+", identity.lot_id) if part.strip()]
    result = []
    for lot in lot_ids:
        urls = set()
        for row in rows:
            for channel, column in channel_columns.items():
                if identity.channel and channel != identity.channel:
                    continue
                number_column = "№ лота — малый канал" if channel == SMALL_CHANNEL else "№ лота — большой канал"
                if _value(row, number_column).casefold() == lot.casefold():
                    url = _value(row, column)
                    if _valid_telegram_post(url):
                        urls.add(url)
        if len(urls) == 1:
            result.append(next(iter(urls)))
    return list(dict.fromkeys(result))


def _valid_telegram_post(url: str) -> bool:
    return bool(re.fullmatch(r"https://t\.me/(?:arenda_vill_samui|samuirental)/\d+(?:\?single)?", url, re.I))

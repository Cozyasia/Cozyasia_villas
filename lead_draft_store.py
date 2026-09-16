# -*- coding: utf-8 -*-
"""Persistent Lead Engine draft records and compact callback helpers."""
from datetime import datetime, timezone
from typing import Mapping

DRAFT_HEADERS = [
    "key",
    "status",
    "created_at",
    "updated_at",
    "recipient_id",
    "recipient_username",
    "recipient_name",
    "draft",
    "source_username",
    "message_id",
    "admin_username",
]
_ALLOWED_ACTIONS = {"send", "edit", "cancel"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def callback_data(action: str, key: str) -> str:
    action = str(action).strip().lower()
    if action not in _ALLOWED_ACTIONS:
        raise ValueError("invalid draft action")
    source, sep, message_id = str(key).partition(":")
    if not sep or not source or not message_id:
        raise ValueError("invalid draft key")
    source = source.strip().lstrip("@")[:32]
    payload = f"draft:{action}:{source}:{message_id}"
    if len(payload.encode("utf-8")) > 64:
        raise ValueError("callback payload is too long")
    return payload


def parse_callback(payload: str) -> tuple[str, str]:
    parts = str(payload or "").split(":", 3)
    if len(parts) != 4 or parts[0] != "draft" or parts[1] not in _ALLOWED_ACTIONS:
        raise ValueError("invalid draft callback")
    action, source, message_id = parts[1], parts[2], parts[3]
    if not source or not message_id:
        raise ValueError("invalid draft callback")
    return action, f"{source}:{message_id}"


def _row_dict(row: list[str]) -> dict[str, str]:
    padded = list(row) + [""] * max(0, len(DRAFT_HEADERS) - len(row))
    return dict(zip(DRAFT_HEADERS, padded[:len(DRAFT_HEADERS)]))


def get_draft(ws, key: str) -> dict[str, str] | None:
    for row in ws.get_all_values()[1:]:
        if row and row[0] == key:
            return _row_dict(row)
    return None


def upsert_draft(ws, record: Mapping[str, object], *, now: str | None = None) -> dict[str, str]:
    timestamp = now or utc_now()
    key = str(record.get("key") or "").strip()
    if not key:
        raise ValueError("draft key is required")
    rows = ws.get_all_values()
    target_row = None
    existing: dict[str, str] | None = None
    for rownum, row in enumerate(rows[1:], start=2):
        if row and row[0] == key:
            target_row = rownum
            existing = _row_dict(row)
            break

    created_at = (existing or {}).get("created_at") or timestamp
    merged = dict(existing or {})
    for header in DRAFT_HEADERS:
        if header in record:
            merged[header] = str(record.get(header) or "")
    merged["key"] = key
    merged["created_at"] = created_at
    merged["updated_at"] = timestamp
    payload = [merged.get(header, "") for header in DRAFT_HEADERS]
    if target_row:
        last_col = chr(ord("A") + len(DRAFT_HEADERS) - 1)
        ws.update(f"A{target_row}:{last_col}{target_row}", [payload], value_input_option="RAW")
    else:
        ws.append_row(payload, value_input_option="RAW")
    return dict(zip(DRAFT_HEADERS, payload))


def update_status(ws, key: str, status: str, *, now: str | None = None) -> bool:
    current = get_draft(ws, key)
    if not current:
        return False
    current["status"] = str(status)
    upsert_draft(ws, current, now=now)
    return True

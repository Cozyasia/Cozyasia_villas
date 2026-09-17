# -*- coding: utf-8 -*-
"""Orchestration for preparing a Lead Engine contact draft without sending it."""
from dataclasses import dataclass
import asyncio
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlparse

DRAFT_SHEET = "LeadDrafts"
_PUBLIC_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{4,32}$")


class ContactFlowError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DraftPreparation:
    opportunity: dict[str, str]
    recipient: Any
    draft: str


@dataclass(frozen=True, slots=True)
class RealDraftPreparation:
    lead: Any
    opportunity: dict[str, str]
    recipient: Any
    draft: str


def parse_public_message_link(value: str) -> tuple[str, int]:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "t.me", "www.t.me", "telegram.me", "www.telegram.me"
    }:
        raise ContactFlowError("Нужна публичная ссылка вида https://t.me/source/message_id")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 3 and parts[0].lower() == "s":
        parts = parts[1:]
    if len(parts) != 2 or parts[0].lower() == "c":
        raise ContactFlowError("Поддерживаются только публичные t.me-ссылки")
    source = parts[0].lstrip("@")
    if not _PUBLIC_USERNAME_RE.fullmatch(source):
        raise ContactFlowError("Некорректный username источника")
    try:
        message_id = int(parts[1])
    except Exception as exc:
        raise ContactFlowError("Некорректный message_id") from exc
    if message_id <= 0:
        raise ContactFlowError("Некорректный message_id")
    return source, message_id


def build_real_message_lead(
    source_username: str,
    source_title: str,
    message: Any,
    *,
    traffic_module=None,
):
    if traffic_module is None:
        import cozy_traffic_runtime as traffic_module
    text = str(getattr(message, "message", "") or "").strip()
    if not text:
        raise ContactFlowError("В исходном сообщении нет текста")
    score, band, reasons = traffic_module.score_rental_request(text)
    if score < 35:
        raise ContactFlowError(f"Сообщение не прошло lead-filter: score={score}")
    fields = traffic_module.extract_request_fields(text)
    date = getattr(message, "date", None)
    if not isinstance(date, datetime):
        date = datetime.now(timezone.utc)
    elif date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    try:
        message_id = int(getattr(message, "id", 0) or 0)
    except Exception as exc:
        raise ContactFlowError("Некорректный message_id") from exc
    if message_id <= 0:
        raise ContactFlowError("Некорректный message_id")
    return traffic_module.LeadFinding(
        source_username=str(source_username or "").strip().lstrip("@"),
        source_title=str(source_title or "").strip(),
        message_id=message_id,
        message_date=date.astimezone(timezone.utc),
        text=text,
        score=score,
        band=band,
        reasons=reasons,
        **fields,
    )


def _lead_to_opportunity(lead: Any) -> dict[str, str]:
    amount = getattr(lead, "budget_amount", None)
    currency = getattr(lead, "budget_currency", None)
    budget = "" if amount is None else f"{amount} {currency or ''}".strip()
    pets = getattr(lead, "pets", None)
    if pets is True:
        pets_text = "yes"
    elif pets is False:
        pets_text = "no"
    else:
        pets_text = ""
    return {
        "key": f"{getattr(lead, 'source_username', '')}:{getattr(lead, 'message_id', '')}",
        "source_username": str(getattr(lead, "source_username", "") or ""),
        "source_title": str(getattr(lead, "source_title", "") or ""),
        "message_id": str(getattr(lead, "message_id", "") or ""),
        "message_date": getattr(lead, "message_date", datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "score": str(getattr(lead, "score", "") or ""),
        "band": str(getattr(lead, "band", "") or ""),
        "districts": ", ".join(getattr(lead, "districts", ()) or ()),
        "date_text": str(getattr(lead, "date_text", "") or ""),
        "duration_text": str(getattr(lead, "duration_text", "") or ""),
        "budget": budget,
        "bedrooms": "" if getattr(lead, "bedrooms", None) is None else str(getattr(lead, "bedrooms")),
        "occupants": "" if getattr(lead, "occupants", None) is None else str(getattr(lead, "occupants")),
        "pets": pets_text,
        "reasons": ",".join(getattr(lead, "reasons", ()) or ()),
        "text": str(getattr(lead, "text", "") or ""),
        "link": str(getattr(lead, "link", "") or ""),
    }


def _opportunity_by_key(manager_module, catalog, key: str) -> dict[str, str] | None:
    ws = manager_module._opportunity_ws(catalog)
    headers = list(manager_module.OPPORTUNITY_HEADERS)
    for row in ws.get_all_values()[1:]:
        if row and row[0] == key:
            padded = list(row) + [""] * max(0, len(headers) - len(row))
            return dict(zip(headers, padded[:len(headers)]))
    return None


def _draft_ws(manager_module, catalog, store_module):
    return manager_module._worksheet(catalog, DRAFT_SHEET, store_module.DRAFT_HEADERS, 3000)


async def prepare_dry_run(
    catalog,
    key: str,
    admin_username: str,
    *,
    manager_module=None,
    auth_module=None,
    contact_module=None,
    store_module=None,
) -> DraftPreparation:
    if manager_module is None:
        import cozy_traffic_manager as manager_module
    opportunity = await asyncio.to_thread(_opportunity_by_key, manager_module, catalog, key)
    if not opportunity:
        raise ContactFlowError(f"Opportunity not found: {key}")

    if auth_module is None:
        import ai_manager_auth as auth_module
    if contact_module is None:
        import lead_contact_dry_run as contact_module
    if store_module is None:
        import lead_draft_store as store_module

    client = await auth_module.new_client(catalog)
    if not client:
        raise ContactFlowError("AI Manager is not authorized")
    try:
        try:
            message_id = int(opportunity.get("message_id") or 0)
        except Exception as exc:
            raise ContactFlowError("Opportunity has invalid message_id") from exc
        try:
            recipient = await contact_module.resolve_recipient(
                client,
                opportunity.get("source_username", ""),
                message_id,
            )
        except Exception as exc:
            if isinstance(exc, ContactFlowError):
                raise
            raise ContactFlowError(f"Recipient resolution failed: {exc}") from exc
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    try:
        draft = await asyncio.to_thread(contact_module.generate_ai_draft, opportunity)
    except Exception as exc:
        raise ContactFlowError(f"AI draft generation failed: {exc}") from exc

    ws = await asyncio.to_thread(_draft_ws, manager_module, catalog, store_module)
    record = {
        "key": key,
        "status": "draft_ready",
        "recipient_id": str(getattr(recipient, "telegram_id", "") or ""),
        "recipient_username": str(getattr(recipient, "username", "") or ""),
        "recipient_name": str(getattr(recipient, "display_name", "") or ""),
        "draft": draft,
        "source_username": opportunity.get("source_username", ""),
        "message_id": opportunity.get("message_id", ""),
        "admin_username": str(admin_username or ""),
    }
    await asyncio.to_thread(store_module.upsert_draft, ws, record)
    return DraftPreparation(opportunity=opportunity, recipient=recipient, draft=draft)


async def prepare_real_message_dry_run(
    catalog,
    message_link: str,
    admin_username: str,
    *,
    manager_module=None,
    auth_module=None,
    contact_module=None,
    store_module=None,
    traffic_module=None,
) -> RealDraftPreparation:
    source, message_id = parse_public_message_link(message_link)
    if manager_module is None:
        import cozy_traffic_manager as manager_module
    if auth_module is None:
        import ai_manager_auth as auth_module
    if contact_module is None:
        import lead_contact_dry_run as contact_module
    if store_module is None:
        import lead_draft_store as store_module
    if traffic_module is None:
        import cozy_traffic_runtime as traffic_module

    approved = await asyncio.to_thread(manager_module._approved_sources, catalog, 200)
    source_row = next(
        (row for row in approved if str(row.get("username") or "").strip().lower().lstrip("@") == source.lower()),
        None,
    )
    if not source_row:
        raise ContactFlowError(f"Источник @{source} не approved")

    client = await auth_module.new_client(catalog)
    if not client:
        raise ContactFlowError("AI Manager is not authorized")
    try:
        try:
            entity = await client.get_entity(source)
            message = await client.get_messages(entity, ids=message_id)
        except Exception as exc:
            raise ContactFlowError(f"Не удалось загрузить исходное сообщение: {exc.__class__.__name__}") from exc
        if not message:
            raise ContactFlowError("Исходное сообщение не найдено")
        lead = build_real_message_lead(
            source,
            source_row.get("title") or str(getattr(entity, "title", "") or ""),
            message,
            traffic_module=traffic_module,
        )
        try:
            recipient = await contact_module.resolve_recipient(client, source, message_id)
        except Exception as exc:
            raise ContactFlowError(f"Recipient resolution failed: {exc}") from exc
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    opportunity = _lead_to_opportunity(lead)
    try:
        draft = await asyncio.to_thread(contact_module.generate_ai_draft, opportunity)
    except Exception as exc:
        raise ContactFlowError(f"AI draft generation failed: {exc}") from exc

    key = opportunity["key"]
    ws = await asyncio.to_thread(_draft_ws, manager_module, catalog, store_module)
    record = {
        "key": key,
        "status": "real_draft_ready",
        "recipient_id": str(getattr(recipient, "telegram_id", "") or ""),
        "recipient_username": str(getattr(recipient, "username", "") or ""),
        "recipient_name": str(getattr(recipient, "display_name", "") or ""),
        "draft": draft,
        "source_username": opportunity.get("source_username", ""),
        "message_id": opportunity.get("message_id", ""),
        "admin_username": str(admin_username or ""),
    }
    await asyncio.to_thread(store_module.upsert_draft, ws, record)
    return RealDraftPreparation(
        lead=lead,
        opportunity=opportunity,
        recipient=recipient,
        draft=draft,
    )

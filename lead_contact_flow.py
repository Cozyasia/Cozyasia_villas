# -*- coding: utf-8 -*-
"""Orchestration for preparing a Lead Engine contact draft without sending it."""
from dataclasses import dataclass
import asyncio
from typing import Any

DRAFT_SHEET = "LeadDrafts"


class ContactFlowError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DraftPreparation:
    opportunity: dict[str, str]
    recipient: Any
    draft: str


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

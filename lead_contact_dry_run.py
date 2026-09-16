# -*- coding: utf-8 -*-
"""Pure helpers for Cozy Lead Engine contact drafting and dry-run previews."""

from dataclasses import dataclass
import os
from typing import Any, Mapping


class RecipientResolutionError(RuntimeError):
    pass


class DraftGenerationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Recipient:
    telegram_id: int
    username: str
    display_name: str

    @property
    def label(self) -> str:
        if self.username:
            return f"@{self.username}"
        if self.display_name:
            return f"{self.display_name} · id {self.telegram_id}"
        return f"id {self.telegram_id}"


def contact_mode() -> str:
    raw = os.getenv("COZY_LEAD_CONTACT_MODE", "dry_run").strip().lower()
    return raw if raw in {"dry_run", "live"} else "dry_run"


def live_send_enabled() -> bool:
    return contact_mode() == "live"


def _fact_lines(opportunity: Mapping[str, Any]) -> list[str]:
    pairs = [
        ("Исходный запрос", opportunity.get("text")),
        ("Район", opportunity.get("districts")),
        ("Бюджет", opportunity.get("budget")),
        ("Спальни", opportunity.get("bedrooms")),
        ("Дата", opportunity.get("date_text")),
        ("Срок", opportunity.get("duration_text")),
        ("Гости", opportunity.get("occupants")),
        ("Питомцы", opportunity.get("pets")),
        ("Источник", opportunity.get("link")),
    ]
    return [f"{label}: {value}" for label, value in pairs if str(value or "").strip()]


def build_draft_prompt(opportunity: Mapping[str, Any]) -> tuple[str, str]:
    system = (
        "Ты менеджер Cozy Asia по аренде жилья на Самуи. Напиши только первое личное сообщение потенциальному клиенту. "
        "Сообщение должно быть естественным, коротким и персонализированным под исходный запрос, без ощущения массовой рассылки. "
        "Пиши на языке исходного запроса. Представься от Cozy Asia ненавязчиво. "
        "Не выдумывай цены, свободные объекты, availability/доступность, характеристики, даты или обещания, которых нет в фактах. "
        "Если важного параметра не хватает, задай максимум один полезный уточняющий вопрос. "
        "Не добавляй ссылки, если они не нужны для ответа на исходный запрос. Не используй канцелярит и агрессивные продажи."
    )
    facts = "\n".join(_fact_lines(opportunity))
    user = (
        "Подготовь первое сообщение для этого лида. Используй только известные факты ниже.\n\n"
        f"{facts}\n\n"
        "Верни только готовый текст сообщения без комментариев, кавычек и служебных пометок."
    )
    return system, user


def generate_ai_draft(
    opportunity: Mapping[str, Any],
    *,
    client: Any | None = None,
    model: str | None = None,
) -> str:
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise DraftGenerationError("OPENAI_API_KEY is not configured")
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    selected_model = (model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    system, user = build_draft_prompt(opportunity)
    result = client.chat.completions.create(
        model=selected_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.35,
        max_tokens=280,
    )
    try:
        text = str(result.choices[0].message.content or "").strip()
    except Exception as exc:
        raise DraftGenerationError("OpenAI returned no draft text") from exc
    if not text:
        raise DraftGenerationError("OpenAI returned an empty draft")
    return text


async def resolve_recipient(client: Any, source_username: str, message_id: int) -> Recipient:
    try:
        entity = await client.get_entity(str(source_username).strip().lstrip("@"))
        message = await client.get_messages(entity, ids=int(message_id))
    except Exception as exc:
        raise RecipientResolutionError(f"Could not load source message: {exc.__class__.__name__}") from exc
    if not message:
        raise RecipientResolutionError("Source message not found")

    sender = None
    getter = getattr(message, "get_sender", None)
    if callable(getter):
        try:
            sender = await getter()
        except Exception:
            sender = None
    if sender is None:
        sender_id = getattr(message, "sender_id", None)
        if sender_id:
            try:
                sender = await client.get_entity(sender_id)
            except Exception as exc:
                raise RecipientResolutionError(f"Could not resolve sender: {exc.__class__.__name__}") from exc
    if sender is None:
        raise RecipientResolutionError("Message sender is unavailable")
    if bool(getattr(sender, "bot", False)):
        raise RecipientResolutionError("Message sender is a bot")

    telegram_id = int(getattr(sender, "id", 0) or 0)
    if not telegram_id:
        raise RecipientResolutionError("Message sender has no Telegram id")
    username = str(getattr(sender, "username", "") or "").strip().lstrip("@")
    display_name = " ".join(
        part for part in (
            str(getattr(sender, "first_name", "") or "").strip(),
            str(getattr(sender, "last_name", "") or "").strip(),
        ) if part
    ).strip()
    return Recipient(telegram_id=telegram_id, username=username, display_name=display_name)


def build_dry_run_preview(
    opportunity: Mapping[str, Any],
    recipient: Recipient,
    draft: str,
) -> str:
    source = str(opportunity.get("source_username") or "").strip().lstrip("@")
    message_id = str(opportunity.get("message_id") or "").strip()
    source_label = f"@{source}/{message_id}" if source and message_id else str(opportunity.get("link") or "источник")
    return (
        "🧪 DRY RUN — сообщение НЕ отправлено\n\n"
        "От: @CozyAsiaAI\n"
        f"Кому: {recipient.label}\n"
        f"Источник: {source_label}\n\n"
        "Текст:\n"
        f"{str(draft).strip()}"
    )[:3900]

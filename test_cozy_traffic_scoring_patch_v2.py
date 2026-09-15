# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
import re
import types

import cozy_traffic_scoring_patch as patch


class Runtime:
    SAMUI_TERMS = ("самуи", "ламай", "бопхут")
    RENTAL_TERMS = ("аренд", "снять", "сниму", "снимем", "rent")
    BUDGET_RE = re.compile(r"бюджет\s+до\s+\d+")
    BEDROOM_RE = re.compile(r"\d+\s*спаль")
    DATE_RE = re.compile(r"\b(?:ноябр|декабр|январ)\w*")
    DURATION_RE = re.compile(r"\d+\s+месяц")
    OCCUPANTS_RE = re.compile(r"нас\s+\d+")
    DISTRICTS = {"Ламай": ("ламай",), "Бопхут": ("бопхут",)}

    @staticmethod
    def _norm(text):
        return (text or "").lower().replace("ё", "е")

    @classmethod
    def _contains_any(cls, text, terms):
        normalized = cls._norm(text)
        return any(cls._norm(term) in normalized for term in terms)


FALSE_POSITIVES = [
    "Ищу подработку догситтером. Также принимаю собак у себя дома. Если нужен догситтер — пишите в личные сообщения.",
    "Добрый день! Ищу на Самуи опытного репетитора-воспитателя оффлайн, который готов по будням приезжать к нам в дом и обучать ребенка.",
    "Таиланд ужесточает DTV: подавать можно только дома, нужна справка о несудимости.",
    "На них нужно нажать чтобы перейти в нужный документ. FAQ про релокацию: работа, жилье, банки.",
]


def test_contextual_false_positives_are_rejected():
    for text in FALSE_POSITIVES:
        score, band, _ = patch._score(Runtime, text)
        assert score == 0 and band == "LOW", text


def test_real_housing_requests_still_pass():
    examples = [
        "Ищу дом на Самуи, Ламай, на 2 месяца, бюджет до 80000 бат",
        "Подскажите, где можно снять квартиру на Бопхуте на декабрь?",
        "Ищу на Самуи с ноября на 2 месяца, бюджет до 80000 бат, желательно Ламай, дом с бассейном",
    ]
    for text in examples:
        score, band, _ = patch._score(Runtime, text)
        assert score >= 50 and band in {"WARM", "HOT"}, (text, score, band)


def test_old_leads_are_filtered_out():
    now = datetime.now(timezone.utc)
    leads = [
        types.SimpleNamespace(message_date=now - timedelta(days=5), text="recent"),
        types.SimpleNamespace(message_date=now - timedelta(days=31), text="old"),
    ]
    kept = patch.filter_recent(leads, 30, now=now)
    assert [item.text for item in kept] == ["recent"]

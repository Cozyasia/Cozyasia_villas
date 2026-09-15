# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import re

import cozy_traffic_discovery_patch as patch


class Entity:
    def __init__(self, title, username, megagroup=True):
        self.title = title
        self.username = username
        self.megagroup = megagroup


class Finding:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Runtime:
    SAMUI_TERMS = ("самуи", "samui", "ламай", "maenam", "чавенг")
    HOUSING_TERMS = ("жиль", "вилл", "дом", "квартир", "недвижим")
    RENTAL_TERMS = ("аренд", "снять", "rent")
    NON_HOUSING_RENT_TERMS = ("байк", "скутер", "машин")
    OWN_USERNAMES = {"arenda_vill_samui", "samuirental"}
    CYRILLIC_RE = re.compile(r"[а-яё]", re.I)
    SourceFinding = Finding

    @staticmethod
    def _norm(text):
        return (text or "").strip().lower().replace("ё", "е")

    @classmethod
    def _contains_any(cls, text, terms):
        normalized = cls._norm(text)
        return any(cls._norm(term) in normalized for term in terms)

    @staticmethod
    def _russian_share(texts):
        return 1.0 if texts else 0.0


NOW = datetime.now(timezone.utc)


def _score(title, username, texts, megagroup=True):
    return patch.score_source(
        Runtime,
        entity=Entity(title, username, megagroup),
        telegram_id=-1001,
        texts=texts,
        dates=[NOW] * len(texts),
    )


def test_general_russian_samui_discussion_group_scores_high():
    texts = [
        "Ребята, подскажите хорошую школу на Самуи?",
        "Кто знает, где сегодня лучше менять валюту?",
        "Посоветуйте кафе на Ламае для семьи",
        "Можно ли сейчас продлить визу на острове?",
        "Ищу мастера по кондиционеру, есть контакты?",
        "Спасибо! А где парковаться у Fisherman's Village?",
        "Кто был на Маенаме сегодня, море спокойное?",
        "Подскажите, пожалуйста, хорошего врача",
    ]
    finding = _score("Русские на Самуи | Чат", "samui_russian_chat", texts)
    assert finding.score >= 75
    assert finding.discussion_points >= 20


def test_promotional_real_estate_feed_is_penalized():
    texts = [
        "🔥 АРЕНДА: вилла 3 спальни. Стоимость 120 000 THB. Пишите в ЛС. Property ID 551",
        "Свободна вилла на Бопхуте. Контракт от 6 месяцев. Цена 80 000 THB",
        "Аренда апартаментов на Самуи. Код объекта 991. По вопросам бронирования пишите в ЛС",
        "Новая вилла. Стоимость аренды 95 000 THB/месяц. WhatsApp +66...",
    ]
    finding = _score("Самуи аренда вилл", "rent_feed", texts)
    assert finding.score < 65
    assert finding.penalty >= 20


def test_expanded_seeds_include_general_community_queries():
    seeds = set(patch.EXPANDED_SEEDS)
    assert "русские на самуи" in seeds
    assert "самуи помощь" in seeds
    assert "самуи вопросы" in seeds
    assert "самуи экспаты" in seeds

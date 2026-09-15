# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime, timedelta, timezone

import cozy_traffic_runtime as traffic
import cozy_traffic_scoring_patch

cozy_traffic_scoring_patch.apply(traffic)


class Entity:
    def __init__(self, peer_id, title, username, megagroup=True):
        self.id = peer_id; self.title = title; self.username = username; self.megagroup = megagroup


class Message:
    def __init__(self, text, message_id=1, days_ago=1):
        self.message = text; self.id = message_id; self.date = datetime.now(timezone.utc) - timedelta(days=days_ago)


class SearchResult:
    def __init__(self, chats): self.chats = chats


class FakeClient:
    def __init__(self):
        self.house = Entity(1, "Самуи чат Недвижимость Аренда", "samui_house_ru", True)
        self.bike = Entity(2, "Аренда байков Самуи", "samui_bikes_ru", True)
        self.own = Entity(3, "Аренда вилл и домов Самуи | Cozy Asia", "arenda_vill_samui", False)
    async def __call__(self, request): return SearchResult([self.house, self.bike, self.own])
    async def get_messages(self, entity, limit):
        if entity is self.house: return [Message("Ищу виллу на Самуи Ламай 2 спальни бюджет до 70000 бат на 2 месяца", 1)] * 10
        if entity is self.bike: return [Message("Аренда байков на Самуи", 2)] * 10
        return [Message("Вилла Самуи аренда", 3)] * 10
    async def get_entity(self, username): return self.house


def test_source_scoring_prefers_housing_and_excludes_own():
    findings = asyncio.run(traffic.discover_public_sources(FakeClient(), seeds=("самуи",), search_request_factory=lambda q, limit: (q, limit), peer_id_fn=lambda e: e.id))
    scores = {x.username: x.score for x in findings}
    assert scores["samui_house_ru"] >= 80
    assert scores["samui_bikes_ru"] < 60
    assert scores["arenda_vill_samui"] == 0


def test_lead_scoring_and_extraction():
    text = "Ищу виллу на Самуи, Ламай, 2 спальни, с 10 декабря на 2 месяца, бюджет до 70000 бат. Нас 3 человека, с собакой."
    score, band, _ = traffic.score_rental_request(text); fields = traffic.extract_request_fields(text)
    assert band == "HOT" and score >= 80
    assert fields["bedrooms"] == 2 and fields["budget_amount"] == 70000 and fields["budget_currency"] == "THB"
    assert fields["occupants"] == 3 and fields["pets"] is True and "Ламай" in fields["districts"]


def test_offer_is_not_a_lead():
    score, band, _ = traffic.score_rental_request("Сдам виллу на Самуи, свободна с декабря, 70000 бат")
    assert score == 0 and band == "LOW"


def test_listing_from_real_scan_is_not_a_lead():
    text = "Аренда: Новая 2-спальная вилла на Бопхуте. Контракт от 6 месяцев. Стоимость 65 000 THB в месяц. По вопросам бронирования пишите в ЛС."
    score, band, _ = traffic.score_rental_request(text)
    assert score == 0 and band == "LOW"


def test_restaurant_ad_with_doma_is_not_housing_lead():
    text = "На Самуи сырники из домашнего творога, как дома. Кафе на Ламаи. Хотите попробовать?"
    score, band, _ = traffic.score_rental_request(text)
    assert score == 0 and band == "LOW"


def test_driving_licence_post_with_perevodom_is_not_housing_lead():
    text = "Какие документы нужны: водительские права с английским переводом. Не нужно сдавать экзамен."
    score, band, _ = traffic.score_rental_request(text)
    assert score == 0 and band == "LOW"


def test_terse_real_housing_request_still_qualifies():
    text = "Нужна 2-спальная вилла на Бопхуте с ноября на 3 месяца, бюджет до 80000 бат."
    score, band, _ = traffic.score_rental_request(text)
    assert score >= 70 and band == "HOT"


def test_runtime_has_no_telegram_write_calls():
    source = open("cozy_traffic_runtime.py", encoding="utf-8").read()
    forbidden = ("send_message(", "edit_message(", "delete_messages(", "SendMessageRequest", "JoinChannelRequest", "InviteToChannelRequest")
    assert not [needle for needle in forbidden if needle in source]

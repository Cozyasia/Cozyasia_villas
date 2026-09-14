# -*- coding: utf-8 -*-
import asyncio
from datetime import datetime, timedelta, timezone

import cozy_traffic_runtime as traffic


class Entity:
    def __init__(self, peer_id, title, username, megagroup=True):
        self.id = peer_id
        self.title = title
        self.username = username
        self.megagroup = megagroup


class Message:
    def __init__(self, text, days_ago=1):
        self.message = text
        self.date = datetime.now(timezone.utc) - timedelta(days=days_ago)


class SearchResult:
    def __init__(self, chats):
        self.chats = chats


class FakeClient:
    def __init__(self):
        self.ru = Entity(100, "Самуи | Аренда и чат", "samui_rent_ru", True)
        self.en = Entity(200, "Samui Weather", "samui_weather", False)
        self.private = Entity(300, "Самуи приват", "", True)

    async def __call__(self, request):
        return SearchResult([self.ru, self.en, self.private])

    async def get_messages(self, entity, limit):
        if entity is self.ru:
            return [
                Message("Ищу виллу на Самуи, Ламай, на два месяца", 1),
                Message("Сдам дом на Маенаме, долгосрочная аренда", 2),
                Message("Кто сейчас живет на Самуи?", 3),
            ]
        return [Message("Sunny weather today in Koh Samui", 1)]


def test_discovery_prefers_relevant_russian_public_group():
    findings = asyncio.run(traffic.discover_public_sources(
        FakeClient(),
        seeds=("самуи",),
        search_request_factory=lambda q, limit: (q, limit),
        peer_id_fn=lambda entity: entity.id,
    ))
    assert [x.username for x in findings] == ["samui_rent_ru", "samui_weather"]
    assert findings[0].score > findings[1].score
    assert findings[0].score >= 85
    assert findings[0].kind == "group"
    assert findings[0].russian_share >= 0.99


def test_runtime_has_no_telegram_write_calls():
    source = open("cozy_traffic_runtime.py", encoding="utf-8").read()
    forbidden = (
        "send_message(", "edit_message(", "delete_messages(",
        "SendMessageRequest", "JoinChannelRequest", "InviteToChannelRequest",
    )
    assert not [needle for needle in forbidden if needle in source]

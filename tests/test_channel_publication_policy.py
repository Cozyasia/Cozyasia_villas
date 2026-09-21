# -*- coding: utf-8 -*-
import os
import unittest
from types import SimpleNamespace

import channel_publication_policy as policy
import channel_bot_routing_audit as routing_audit


class MessageEntityTextUrl(SimpleNamespace):
    pass


class MessageEntityBlockquote(SimpleNamespace):
    pass


def _u16_len(s):
    return len(s.encode("utf-16-le")) // 2


def _ent_for(text, needle, url=None, cls=MessageEntityTextUrl):
    start = text.index(needle)
    return cls(offset=_u16_len(text[:start]), length=_u16_len(needle), url=url or "")


def _good_text():
    return (
        "LOT 1204\n\n"
        "💬 ОПИСАНИЕ\n"
        "Уютная студия рядом с пляжем.\n\n"
        "💰 УСЛОВИЯ АРЕНДЫ\n"
        "💵 24 000 THB/мес\n\n"
        "👉 ЖМИ ЗДЕСЬ 👈\n\n\n"
        "Оператор: @cozy_asia\n"
        "🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — НАПИСАТЬ БОТУ 🤖\n\n"
        "#АрендаСамуи #CozyAsia"
    )


def _good_entities(channel="samuirental", lot="1204"):
    text = _good_text()
    bot = policy.bot_for_channel(channel)
    desc = "Уютная студия рядом с пляжем."
    return [
        _ent_for(text, desc, cls=MessageEntityBlockquote),
        _ent_for(text, "ЖМИ ЗДЕСЬ", f"https://t.me/{bot}?start=rent_{lot}"),
        _ent_for(text, "НАПИСАТЬ БОТУ", f"https://t.me/{bot}?start=search"),
    ]


class PolicyTests(unittest.TestCase):
    def test_big_channel_routes_both_ctas_to_big_bot(self):
        out = policy.validate_listing_caption(_good_text(), _good_entities(), "1204", "samuirental")
        self.assertEqual(out["bot"], "cozy_asia_bot")

    def test_small_channel_rejects_big_bot(self):
        with self.assertRaisesRegex(RuntimeError, "Cozyasia_villa_bot"):
            policy.validate_listing_caption(
                _good_text(), _good_entities("samuirental"), "1204", "arenda_vill_samui"
            )

    def test_rejects_wrong_lot_deep_link(self):
        entities = _good_entities()
        entities[1].url = "https://t.me/cozy_asia_bot?start=rent_1203"
        with self.assertRaisesRegex(RuntimeError, "rent_1204"):
            policy.validate_listing_caption(_good_text(), entities, "1204", "samuirental")

    def test_description_must_be_blockquote(self):
        entities = _good_entities()[1:]
        with self.assertRaisesRegex(RuntimeError, "blockquote"):
            policy.validate_listing_caption(_good_text(), entities, "1204", "samuirental")

    def test_requires_manual_spacing_pattern(self):
        bad = _good_text().replace(
            "👉 ЖМИ ЗДЕСЬ 👈\n\n\nОператор", "👉 ЖМИ ЗДЕСЬ 👈\n\nОператор"
        )
        entities = [
            _ent_for(bad, "Уютная студия рядом с пляжем.", cls=MessageEntityBlockquote),
            _ent_for(bad, "ЖМИ ЗДЕСЬ", "https://t.me/cozy_asia_bot?start=rent_1204"),
            _ent_for(bad, "НАПИСАТЬ БОТУ", "https://t.me/cozy_asia_bot?start=search"),
        ]
        with self.assertRaisesRegex(RuntimeError, "blank lines"):
            policy.validate_listing_caption(bad, entities, "1204", "samuirental")

    def test_visible_lot_uses_first_line_not_body_numbers(self):
        text = (
            "🔤🔤🔤 🔤 1️⃣2️⃣0️⃣4️⃣\n\n"
            "💬 ОПИСАНИЕ\nСтудия 25,9 м².\n"
            "💵 24 000 THB/мес\n💧 Вода: 100 THB"
        )
        self.assertEqual(routing_audit._visible_lot_from_text(text), "1204")

    def test_visible_lot_preserves_legacy_prefixed_lot(self):
        text = "🔤🔤🔤 🔤 0️⃣1️⃣➖1️⃣0️⃣6️⃣0️⃣\n\n💬 ОПИСАНИЕ\n2026 год"
        self.assertEqual(routing_audit._visible_lot_from_text(text), "01-1060")

    def test_visible_lot_does_not_infer_year_from_body(self):
        text = "🌴 Вилла у моря\n\n💬 ОПИСАНИЕ\nДоступна на сезон 2026/27"
        self.assertEqual(routing_audit._visible_lot_from_text(text), "")

    def test_rewrite_rent_start_preserves_other_query_parts(self):
        url = "https://t.me/cozy_asia_bot?foo=1&start=rent_100&bar=2"
        self.assertEqual(
            routing_audit._rewrite_rent_start(url, "1204"),
            "https://t.me/cozy_asia_bot?foo=1&start=rent_1204&bar=2",
        )

    def test_target_filter_is_scoped_by_channel(self):
        old = os.environ.get("CHANNEL_BOT_ROUTING_TARGETS")
        os.environ["CHANNEL_BOT_ROUTING_TARGETS"] = (
            '{"samuirental":[5134,5124],"arenda_vill_samui":[1133]}'
        )
        try:
            self.assertEqual(routing_audit._target_ids_for("samuirental"), {5134, 5124})
            self.assertEqual(routing_audit._target_ids_for("arenda_vill_samui"), {1133})
        finally:
            if old is None:
                os.environ.pop("CHANNEL_BOT_ROUTING_TARGETS", None)
            else:
                os.environ["CHANNEL_BOT_ROUTING_TARGETS"] = old

    def test_group_candidates_keep_only_same_album_caption_siblings(self):
        messages = [
            SimpleNamespace(id=10, grouped_id=77, message="", entities=[]),
            SimpleNamespace(id=11, grouped_id=77, message="caption", entities=[SimpleNamespace(url="x")]),
            SimpleNamespace(id=12, grouped_id=88, message="other", entities=[SimpleNamespace(url="x")]),
            SimpleNamespace(id=13, grouped_id=77, message="no links", entities=[]),
        ]
        candidates = routing_audit._group_caption_candidates(messages, grouped_id=77, original_id=10)
        self.assertEqual([m.id for m in candidates], [11])


class RepairRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_flood_wait_retries_same_edit_after_waiting(self):
        class FakeFloodWaitError(Exception):
            def __init__(self, seconds):
                self.seconds = seconds

        class FakeClient:
            def __init__(self):
                self.calls = 0

            async def edit_message(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise FakeFloodWaitError(7)
                return SimpleNamespace(id=args[1])

        waits = []

        async def fake_sleep(seconds):
            waits.append(seconds)

        old_error = getattr(routing_audit, "FloodWaitError", None)
        old_sleep = getattr(routing_audit, "_sleep", None)
        routing_audit.FloodWaitError = FakeFloodWaitError
        routing_audit._sleep = fake_sleep
        client = FakeClient()
        try:
            out = await routing_audit._edit_with_retry(
                client, "samuirental", 5134, "text", [], max_attempts=3
            )
        finally:
            if old_error is None:
                delattr(routing_audit, "FloodWaitError")
            else:
                routing_audit.FloodWaitError = old_error
            if old_sleep is None:
                delattr(routing_audit, "_sleep")
            else:
                routing_audit._sleep = old_sleep

        self.assertEqual(client.calls, 2)
        self.assertEqual(waits, [10])
        self.assertEqual(out.id, 5134)


if __name__ == "__main__":
    unittest.main()

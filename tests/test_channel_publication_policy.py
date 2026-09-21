# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace

import channel_publication_policy as policy


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


if __name__ == "__main__":
    unittest.main()

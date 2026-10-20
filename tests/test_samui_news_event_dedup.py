import unittest
from datetime import datetime, timezone

from samui_news_event_dedup import (
    build_event_key,
    dedupe_decision,
    is_fresh,
)


class EventDedupTests(unittest.TestCase):
    def test_two_headlines_for_same_weather_event_share_key(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        first = {
            "title": "Сильные дожди и наводнения в Сураттхани",
            "text": "В провинции Сураттхани идут сильные дожди, местами подтоплены дороги.",
            "published": "2026-10-20T08:00:00+00:00",
        }
        second = {
            "title": "Сильные дожди и оползни в Сураттхани",
            "text": "Из-за дождей в Сураттхани сообщают об оползнях и сложной обстановке.",
            "published": "2026-10-20T09:00:00+00:00",
        }
        self.assertEqual(build_event_key(first, now), build_event_key(second, now))

    def test_cross_day_hazard_headlines_share_key_at_bangkok_midnight(self):
        now = datetime(2026, 10, 20, 17, 30, tzinfo=timezone.utc)
        first = {
            "title": "Сильные дожди и наводнения в Сураттхани",
            "text": "Подтоплены дороги, власти предупреждают об опасной обстановке.",
            "published": "2026-10-20T10:00:00+00:00",
        }
        second = {
            "title": "Сильные дожди и оползни в Сураттхани",
            "text": "Оползни повредили дороги после продолжительных дождей.",
            "url": "https://source.example/landslides",
            "published": "2026-10-20T17:00:00+00:00",
        }
        self.assertEqual(build_event_key(first, now), build_event_key(second, now))
        allowed, reason = dedupe_decision(
            second,
            {
                "used_urls": set(),
                "event_keys": {build_event_key(first, now)},
                "event_signatures": set(),
            },
            now=now,
        )
        self.assertFalse(allowed)
        self.assertIn("duplicate", reason)

    def test_cross_day_material_hazard_update_is_allowed(self):
        now = datetime(2026, 10, 20, 17, 30, tzinfo=timezone.utc)
        first = {
            "title": "Сильные дожди и наводнения в Сураттхани",
            "text": "Подтоплены дороги, власти предупреждают об опасной обстановке.",
            "published": "2026-10-20T10:00:00+00:00",
        }
        update = {
            "title": "Обновление: оползни перекрыли дорогу в Сураттхани",
            "text": "Официально подтверждено новое последствие: дорогу закрыли из-за оползня.",
            "url": "https://source.example/official-update",
            "published": "2026-10-20T17:00:00+00:00",
            "novelty": "update",
        }
        allowed, reason = dedupe_decision(
            update,
            {
                "used_urls": set(),
                "event_keys": {build_event_key(first, now)},
                "event_signatures": set(),
            },
            now=now,
        )
        self.assertTrue(allowed, reason)
        self.assertEqual(reason, "update:material")

    def test_ordinary_weather_briefing_can_be_published_on_a_new_day(self):
        now = datetime(2026, 10, 20, 17, 30, tzinfo=timezone.utc)
        first = {
            "title": "Прогноз погоды на Самуи",
            "text": "В течение дня ожидается переменная облачность.",
            "published": "2026-10-20T10:00:00+00:00",
        }
        second = {
            "title": "Прогноз погоды на Самуи на 21 октября",
            "text": "На острове ожидаются кратковременные дожди и ветер.",
            "url": "https://source.example/forecast-21",
            "published": "2026-10-20T17:00:00+00:00",
        }
        self.assertNotEqual(build_event_key(first, now), build_event_key(second, now))
        allowed, reason = dedupe_decision(
            second,
            {
                "used_urls": set(),
                "event_keys": {build_event_key(first, now)},
                "event_signatures": set(),
            },
            now=now,
        )
        self.assertTrue(allowed, reason)

    def test_different_events_in_same_region_are_allowed(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        ferry = {
            "title": "Паромы Самуи — Панган временно отменены",
            "text": "Оператор отменил рейсы из-за технической проверки судна.",
            "published": "2026-10-20T09:00:00+00:00",
        }
        road = {
            "title": "Полиция перекрыла дорогу на Самуи после ДТП",
            "text": "Движение направили в объезд, пострадавших доставили в больницу.",
            "published": "2026-10-20T09:30:00+00:00",
        }
        self.assertNotEqual(build_event_key(ferry, now), build_event_key(road, now))
        allowed, reason = dedupe_decision(
            road,
            {"used_urls": set(), "event_keys": {build_event_key(ferry, now)}, "event_signatures": set()},
            now=now,
        )
        self.assertTrue(allowed, reason)

    def test_same_event_is_blocked_even_with_a_different_url(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        item = {
            "title": "Сильные дожди и оползни в Сураттхани",
            "text": "Из-за дождей в Сураттхани сообщают об оползнях и сложной обстановке.",
            "url": "https://source.example/second",
            "published": "2026-10-20T09:00:00+00:00",
        }
        state = {
            "used_urls": set(),
            "event_keys": {build_event_key(item, now)},
            "event_signatures": set(),
        }
        allowed, reason = dedupe_decision(item, state, now=now)
        self.assertFalse(allowed)
        self.assertIn("duplicate", reason)

    def test_material_update_is_allowed(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        item = {
            "title": "Паромное сообщение Самуи — Панган возобновлено",
            "text": "Оператор официально возобновил рейсы в 19:30 после отмены из-за шторма.",
            "published": "2026-10-20T10:00:00+00:00",
            "novelty": "update",
        }
        state = {
            "used_urls": set(),
            "event_keys": {build_event_key(item, now)},
            "event_signatures": set(),
        }
        allowed, reason = dedupe_decision(item, state, now=now)
        self.assertTrue(allowed, reason)

    def test_stale_item_is_rejected(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        item = {
            "title": "Старое сообщение о погоде на Самуи",
            "text": "Архивная сводка без новых данных.",
            "published": "2026-10-17T08:00:00+00:00",
        }
        self.assertFalse(is_fresh(item, now=now, max_age_hours=48))
        allowed, reason = dedupe_decision(item, {"used_urls": set(), "event_keys": set(), "event_signatures": set()}, now=now)
        self.assertFalse(allowed)
        self.assertIn("stale", reason)

    def test_same_event_is_idempotently_blocked_on_retry(self):
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        item = {
            "title": "Полиция перекрыла дорогу на Самуи после ДТП",
            "text": "Движение направили в объезд после аварии.",
            "url": "https://source.example/road",
            "published": "2026-10-20T09:30:00+00:00",
        }
        state = {"used_urls": {item["url"]}, "event_keys": set(), "event_signatures": set()}
        allowed, reason = dedupe_decision(item, state, now=now)
        self.assertFalse(allowed)
        self.assertIn("url", reason)


if __name__ == "__main__":
    unittest.main()

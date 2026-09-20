import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import samui_news_source_patch as patch


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return self.rows


class PatchTests(unittest.TestCase):
    def test_geo_match_covers_extended_area(self):
        for text in [
            "Koh Samui ferry disruption",
            "Full Moon Party Koh Phangan rules",
            "Koh Pha-ngan ferry disruption",
            "Koh Tao diving boat incident",
            "Surat Thani airport closure",
            "ข่าว เกาะพะงัน สุราษฎร์ธานี",
        ]:
            self.assertTrue(patch._geo_match(text), text)

    def test_old_url_is_remembered_across_days(self):
        rows = [
            ["slot", "kind", "content_hash", "message_id", "source_urls", "created_at"],
            [
                "2026-09-12-10-1",
                "post",
                "x",
                "1",
                "https://example.com/a",
                "2026-09-12T03:00:00+00:00",
            ],
            [
                "2026-09-20-10-1",
                "post",
                "y",
                "2",
                "https://example.com/b",
                "2026-09-20T03:00:00+00:00",
            ],
        ]
        fake_news = SimpleNamespace(_worksheet=lambda catalog: FakeWorksheet(rows))
        state_fn = patch._history_state_factory(fake_news, history_days=14)
        state = state_fn(object(), "2026-09-20")
        self.assertIn("https://example.com/a", state["used_urls"])
        self.assertIn("https://example.com/b", state["used_urls"])
        self.assertEqual(1, state["posts"])

    def test_duplicate_filter_blocks_same_story_but_allows_material_update(self):
        recent = [
            "Паром Самуи — Панган отменён из-за шторма. Рейсы приостановлены до 18:00."
        ]
        duplicate = {
            "title": "Storm cancels Samui–Phangan ferry services",
            "text": "Паром Самуи — Панган отменён из-за шторма до 18:00.",
        }
        update = {
            "title": "Samui–Phangan ferry service resumes after storm",
            "text": "Паромное сообщение Самуи — Панган возобновлено в 19:30 после шторма.",
        }
        self.assertEqual("duplicate", patch._fallback_novelty(duplicate, recent))
        self.assertEqual("update", patch._fallback_novelty(update, recent))

    def test_publish_rule_accepts_one_strong_fresh_story(self):
        now = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)
        state = {
            "posts": 0,
            "stories": 0,
            "last_post": None,
            "used_urls": set(),
        }
        items = [
            {
                "title": "Koh Tao ferry closed after storm warning",
                "url": "https://example.com/new",
                "text": "Koh Tao ferry closed after storm warning",
                "novelty": "new",
            }
        ]
        publish, selected = patch._should_publish_enhanced(
            items, state, now, max_posts=5, min_gap_seconds=5400
        )
        self.assertTrue(publish)
        self.assertEqual(items, selected)


if __name__ == "__main__":
    unittest.main()

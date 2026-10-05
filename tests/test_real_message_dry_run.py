import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import lead_contact_flow as flow


class _FakeLeadFinding:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def link(self):
        return f"https://t.me/{self.source_username}/{self.message_id}"


class _FakeTraffic:
    LeadFinding = _FakeLeadFinding

    @staticmethod
    def score_rental_request(text):
        if "нерелевант" in text:
            return 20, "LOW", ("low",)
        return 82, "HOT", ("active_request", "housing", "district")

    @staticmethod
    def extract_request_fields(text):
        return {
            "districts": ("Чавенг",),
            "date_text": "24.09",
            "duration_text": None,
            "budget_amount": 15000,
            "budget_currency": "THB",
            "bedrooms": 1,
            "occupants": 2,
            "pets": False,
        }


class PublicMessageLinkTests(unittest.TestCase):
    def test_parses_public_tme_message_link(self):
        self.assertTrue(hasattr(flow, "parse_public_message_link"))
        parse = getattr(flow, "parse_public_message_link")
        self.assertEqual(parse("https://t.me/samui5/131661"), ("samui5", 131661))
        self.assertEqual(parse("https://t.me/samui5/131661?single"), ("samui5", 131661))

    def test_rejects_private_or_malformed_links(self):
        self.assertTrue(hasattr(flow, "parse_public_message_link"))
        parse = getattr(flow, "parse_public_message_link")
        for value in (
            "https://t.me/c/123456/789",
            "https://example.com/samui5/131661",
            "https://t.me/samui5/not-a-number",
            "samui5/131661",
        ):
            with self.subTest(value=value):
                with self.assertRaises(flow.ContactFlowError):
                    parse(value)


class RealMessageLeadTests(unittest.TestCase):
    def test_builds_lead_from_exact_message_using_scoring_pipeline(self):
        self.assertTrue(hasattr(flow, "build_real_message_lead"))
        build = getattr(flow, "build_real_message_lead")
        message = SimpleNamespace(
            id=131661,
            message="Ищу жильё с 24.09, Чавенг, бюджет 15 т.б., 1 спальня",
            date=datetime(2026, 9, 17, 3, 23, tzinfo=timezone.utc),
        )
        lead = build(
            "samui5",
            "Самуи чат",
            message,
            traffic_module=_FakeTraffic,
        )
        self.assertEqual(lead.source_username, "samui5")
        self.assertEqual(lead.message_id, 131661)
        self.assertEqual(lead.score, 82)
        self.assertEqual(lead.band, "HOT")
        self.assertEqual(lead.districts, ("Чавенг",))
        self.assertEqual(lead.budget_amount, 15000)
        self.assertEqual(lead.bedrooms, 1)
        self.assertEqual(lead.link, "https://t.me/samui5/131661")

    def test_blocks_message_below_interesting_threshold(self):
        self.assertTrue(hasattr(flow, "build_real_message_lead"))
        build = getattr(flow, "build_real_message_lead")
        message = SimpleNamespace(
            id=10,
            message="нерелевант",
            date=datetime.now(timezone.utc),
        )
        with self.assertRaises(flow.ContactFlowError):
            build("samui5", "Самуи чат", message, traffic_module=_FakeTraffic)


class ControlPlaneWiringTests(unittest.TestCase):
    def test_real_dry_run_command_is_wired(self):
        source = Path("lead_engine_control.py").read_text(encoding="utf-8")
        self.assertIn("cmd_traffic_real_dry_run", source)
        self.assertIn('CommandHandler("traffic_real_dry_run"', source)
        self.assertIn("prepare_real_message_dry_run", source)


if __name__ == "__main__":
    unittest.main()

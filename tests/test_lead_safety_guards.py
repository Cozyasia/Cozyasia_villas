import unittest
from pathlib import Path
from types import SimpleNamespace

import lead_contact_dry_run as contact


class _FakeCompletions:
    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = 0

    def create(self, **kwargs):
        text = self._texts[self.calls]
        self.calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        )


class _FakeClient:
    def __init__(self, texts):
        self.chat = SimpleNamespace(completions=_FakeCompletions(texts))


class PlaceholderGuardTests(unittest.TestCase):
    def test_detects_common_name_placeholders(self):
        self.assertTrue(hasattr(contact, "contains_placeholder"))
        for text in (
            "Здравствуйте! Меня зовут [Ваше имя]",
            "Hello, my name is <name>",
            "Привет, я {name} из Cozy Asia",
            "YOUR NAME from Cozy Asia",
            "Здравствуйте, [Имя]!",
        ):
            with self.subTest(text=text):
                self.assertTrue(contact.contains_placeholder(text))

    def test_allows_normal_human_text(self):
        self.assertTrue(hasattr(contact, "contains_placeholder"))
        self.assertFalse(
            contact.contains_placeholder(
                "Здравствуйте! Увидел ваш запрос по жилью на Самуи. Я из Cozy Asia."
            )
        )

    def test_generate_ai_draft_retries_once_when_first_draft_has_placeholder(self):
        client = _FakeClient([
            "Здравствуйте! Меня зовут [Ваше имя], я из Cozy Asia.",
            "Здравствуйте! Я из Cozy Asia. Подскажите, на какие даты ищете жильё?",
        ])
        draft = contact.generate_ai_draft(
            {"text": "Ищу жильё на Самуи", "districts": "Ламай"},
            client=client,
            model="test-model",
        )
        self.assertEqual(client.chat.completions.calls, 2)
        self.assertNotIn("[Ваше имя]", draft)
        self.assertFalse(contact.contains_placeholder(draft))

    def test_generate_ai_draft_blocks_second_placeholder_result(self):
        client = _FakeClient([
            "Здравствуйте! Меня зовут [Ваше имя].",
            "Здравствуйте! Я <name> из Cozy Asia.",
        ])
        with self.assertRaises(contact.DraftGenerationError):
            contact.generate_ai_draft(
                {"text": "Ищу дом"}, client=client, model="test-model"
            )
        self.assertEqual(client.chat.completions.calls, 2)


class RecipientProbePreviewTests(unittest.TestCase):
    def test_preview_identifies_real_recipient_without_contacting_them(self):
        self.assertTrue(hasattr(contact, "build_recipient_probe_preview"))
        recipient = contact.Recipient(
            telegram_id=123456789,
            username="sample_user",
            display_name="Sample User",
        )
        preview = contact.build_recipient_probe_preview(
            "samui_group", 321, recipient
        )
        self.assertIn("@samui_group/321", preview)
        self.assertIn("@sample_user", preview)
        self.assertIn("123456789", preview)
        self.assertIn("Sample User", preview)
        self.assertIn("НЕ отправлено", preview)

    def test_control_plane_wires_admin_recipient_test_command(self):
        source = Path("lead_engine_control.py").read_text(encoding="utf-8")
        self.assertIn("cmd_traffic_recipient_test", source)
        self.assertIn('CommandHandler("traffic_recipient_test"', source)


if __name__ == "__main__":
    unittest.main()

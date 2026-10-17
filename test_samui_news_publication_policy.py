import unittest
from unittest.mock import patch
import samui_news_publication_policy as policy

class PublicationPolicyTests(unittest.TestCase):
    def test_remove_attribution(self):
        self.assertEqual(policy.clean('Заголовок\nИсточник: <a href="https://example.com">СМИ</a>'), 'Заголовок')
    def test_strip_url(self):
        self.assertEqual(policy.clean('Новость https://example.com/story'), 'Новость')
    def test_plain_russian(self):
        self.assertEqual(policy.clean('Новый полицейский участок в Сураттхани'), 'Новый полицейский участок в Сураттхани')
    def test_thai_requires_translation(self):
        with patch.dict('sys.modules', {'openai': None}):
            with self.assertRaises(ImportError):
                policy.clean('ข่าวไทย')

if __name__ == '__main__':
    unittest.main()

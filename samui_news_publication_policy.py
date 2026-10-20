"""Samui News final publication gate."""
import html
import os
import re

THAI = re.compile("[\u0e00-\u0e7f]")
URL = re.compile(r"https?://[^\s<>]+|www\.[^\s<>]+", re.I)
SOURCE = re.compile(r"^\s*(?:Источник|Источники|Source|Sources)\s*:", re.I)
ENGLISH = re.compile(r"\b[A-Za-z]{3,}(?:[ -]+[A-Za-z]{3,})+\b")

def clean(text):
    text = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", text, flags=re.I | re.S)
    text = "\n".join(line for line in text.splitlines() if not SOURCE.match(html.unescape(re.sub(r"<[^>]+>", "", line))))
    text = URL.sub("", text).strip()
    if THAI.search(text) or ENGLISH.search(re.sub(r"<[^>]+>", "", text)):
        from openai import OpenAI
        response = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")).chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[{"role": "user", "content": "Перепиши весь текст на естественном литературном русском языке для русскоязычного новостного Telegram-канала. Переводи тайские и английские предложения непосредственно на русский, без английского оригинала и без дублирования переводов в скобках. Географические названия и названия организаций передавай по-русски; исходное написание допускается только для короткого официального имени, если без него нельзя идентифицировать объект. Заголовок, основной текст, подписи и хэштеги должны быть русскоязычными. Удали англоязычные дубли и машинные конструкции. Не добавляй фактов, ссылок или источников. Сохрани HTML b/i и хэштеги. Верни только текст.\n" + text}],
        )
        text = (response.choices[0].message.content or "").strip()
        text = "\n".join(line for line in text.splitlines() if not SOURCE.match(html.unescape(re.sub(r"<[^>]+>", "", line))))
        text = URL.sub("", text).strip()
    visible = html.unescape(re.sub(r"<[^>]+>", "", text))
    # Never publish untranslated English headlines or sentences.
    # Short official names and isolated proper nouns are permitted.
    if THAI.search(text) or ENGLISH.search(visible) or URL.search(text) or not visible.strip() or len(visible) > 900:
        raise ValueError("Samui News: publication contains unsupported script, URL or empty text")
    return text

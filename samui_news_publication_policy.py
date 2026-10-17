"""Samui News final publication gate."""
import html
import os
import re

THAI = re.compile("[\u0e00-\u0e7f]")
URL = re.compile(r"https?://[^\s<>]+|www\.[^\s<>]+", re.I)
SOURCE = re.compile(r"^\s*(?:Источник|Источники|Source|Sources)\s*:", re.I)

def clean(text):
    text = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", text, flags=re.I | re.S)
    text = "\n".join(line for line in text.splitlines() if not SOURCE.match(html.unescape(re.sub(r"<[^>]+>", "", line))))
    text = URL.sub("", text)
    if THAI.search(text):
        from openai import OpenAI
        response = OpenAI(api_key=os.environ.get("OPENAI_API_KEY")).chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[{"role": "user", "content": "Переведи все тайские фрагменты на английский с русским переводом в скобках. Остальной русский текст сохрани. Не добавляй фактов, ссылок или источников. Сохрани HTML b/i и хэштеги. Верни только текст.\n" + text}],
        )
        text = (response.choices[0].message.content or "").strip()
        text = URL.sub("", text)
    if THAI.search(text) or URL.search(text) or not text:
        raise ValueError("Samui News: publication contains unsupported script, URL or empty text")
    return text

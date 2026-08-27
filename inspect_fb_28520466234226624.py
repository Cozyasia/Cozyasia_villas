# -*- coding: utf-8 -*-
"""Read-only Facebook Marketplace probe for item 28520466234226624."""
from __future__ import annotations

import html
import json
import logging
import os
import re

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("inspect-fb-28520466234226624")
ITEM_ID = "28520466234226624"
URLS = (
    f"https://www.facebook.com/marketplace/item/{ITEM_ID}/",
    f"https://m.facebook.com/marketplace/item/{ITEM_ID}/",
    f"https://mbasic.facebook.com/marketplace/item/{ITEM_ID}/",
    f"https://www.facebook.com/marketplace/item/{ITEM_ID}/?locale=en_US",
)
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
)


def enabled():
    return os.getenv("INSPECT_FB_28520466234226624", "0").strip().lower() in {"1", "true", "yes", "on"}


def _clean(value):
    if not value:
        return ""
    value = html.unescape(str(value))
    value = value.replace("\\/", "/").replace("\\u0026", "&")
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)
    value = value.replace("\\\"", '"')
    return value.strip()


def _matches(text, pattern, limit=20):
    out = []
    for m in re.finditer(pattern, text, flags=re.I | re.S):
        value = _clean(m.group(1))
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


def _extract(response, label):
    body = response.text or ""
    soup = BeautifulSoup(body, "html.parser")
    meta = {}
    for key in ("og:title", "og:description", "og:image", "og:url", "twitter:title", "twitter:description", "twitter:image"):
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            meta[key] = _clean(tag.get("content"))
    image_urls = _matches(body, r'\"(?:uri|url)\"\s*:\s*\"(https?:\\/\\/[^\"]+(?:scontent|fbcdn)[^\"]*)\"', 60)
    for candidate in re.findall(r'https?:\\/\\/[^\"\\s]{20,900}', body):
        value = _clean(candidate)
        if "scontent" in value and value not in image_urls:
            image_urls.append(value)
        if len(image_urls) >= 60:
            break
    return {
        "label": label,
        "status": response.status_code,
        "final_url": response.url,
        "html_len": len(body),
        "page_title": _clean(soup.title.string if soup.title and soup.title.string else ""),
        "meta": meta,
        "listing_titles": _matches(body, r'\"(?:marketplace_listing_title|listing_title|title)\"\s*:\s*\"([^\"]{3,300})\"', 30),
        "prices": _matches(body, r'\"(?:formatted_amount|formatted_price|listing_price|price)\"\s*:\s*\"([^\"]{1,120})\"', 30),
        "descriptions": _matches(body, r'\"(?:redacted_description|description|listing_description)\"\s*:\s*\"([^\"]{8,1600})\"', 30),
        "locations": _matches(body, r'\"(?:location_text|reverse_geocode|city|marketplace_listing_location)\"\s*:\s*\"([^\"]{2,300})\"', 30),
        "image_urls": image_urls,
    }


def _has_listing_signal(extraction):
    if extraction["listing_titles"] or extraction["prices"] or extraction["descriptions"] or extraction["locations"]:
        return True
    if any(k in extraction["meta"] for k in ("og:title", "og:description", "og:image")):
        return True
    return any("scontent" in u for u in extraction["image_urls"])


def run():
    if not enabled():
        return {"enabled": False}
    attempts = []
    session = requests.Session()
    for url in URLS:
        for ua in USER_AGENTS:
            label = ("externalhit" if ua.startswith("facebookexternalhit") else "browser") + " " + url
            try:
                r = session.get(
                    url,
                    headers={
                        "User-Agent": ua,
                        "Accept-Language": "en-US,en;q=0.9,th;q=0.8,ru;q=0.7",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    },
                    timeout=25,
                    allow_redirects=True,
                )
                extraction = _extract(r, label)
                attempts.append(extraction)
                compact = dict(extraction)
                compact["image_urls"] = [u for u in extraction["image_urls"] if "scontent" in u][:15]
                log.info("FB285_PROBE %s", json.dumps(compact, ensure_ascii=False))
                if _has_listing_signal(extraction):
                    return {"enabled": True, "success": True, "attempt": extraction}
            except Exception as exc:
                attempts.append({"label": label, "error": f"{type(exc).__name__}: {exc}"})
    summary = [{"label": a.get("label"), "status": a.get("status"), "title": a.get("page_title"), "len": a.get("html_len"), "error": a.get("error")} for a in attempts]
    log.info("FB285_PROBE_ALL_FAILED %s", json.dumps(summary, ensure_ascii=False))
    return {"enabled": True, "success": False, "attempts": summary}

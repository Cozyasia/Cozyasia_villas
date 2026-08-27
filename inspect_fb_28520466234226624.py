# -*- coding: utf-8 -*-
"""Read-only Facebook Marketplace probe for item 28520466234226624.

Never publishes or mutates Telegram. It only fetches the public Marketplace page
from Render and logs a compact extraction so the final one-shot publisher can be
built from the live source when the local browser connector is unavailable.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("inspect-fb-28520466234226624")
SOURCE_URL = "https://www.facebook.com/marketplace/item/28520466234226624?referralSurface=messenger_banner&referralCode=2&ref=messenger_banner"


def enabled():
    return os.getenv("INSPECT_FB_28520466234226624", "0").strip().lower() in {"1", "true", "yes", "on"}


def _clean(value):
    if not value:
        return ""
    value = html.unescape(value)
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


def run():
    if not enabled():
        return {"enabled": False}
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 16; SM-F936N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,th;q=0.8,ru;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    }
    r = requests.get(SOURCE_URL, headers=headers, timeout=25, allow_redirects=True)
    body = r.text or ""
    soup = BeautifulSoup(body, "html.parser")
    meta = {}
    for key in ("og:title", "og:description", "og:image", "twitter:title", "twitter:description", "twitter:image"):
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            meta[key] = _clean(tag.get("content"))

    extraction = {
        "status": r.status_code,
        "final_url": r.url,
        "html_len": len(body),
        "page_title": _clean(soup.title.string if soup.title and soup.title.string else ""),
        "meta": meta,
        "listing_titles": _matches(body, r'\"(?:marketplace_listing_title|listing_title|title)\"\s*:\s*\"([^\"]{3,300})\"', 30),
        "prices": _matches(body, r'\"(?:formatted_amount|formatted_price|listing_price|price)\"\s*:\s*\"([^\"]{1,120})\"', 30),
        "descriptions": _matches(body, r'\"(?:redacted_description|description|listing_description)\"\s*:\s*\"([^\"]{8,1200})\"', 30),
        "locations": _matches(body, r'\"(?:location_text|reverse_geocode|city|marketplace_listing_location)\"\s*:\s*\"([^\"]{2,300})\"', 30),
        "image_urls": _matches(body, r'\"(?:uri|url)\"\s*:\s*\"(https?:\\/\\/[^\"]+(?:scontent|fbcdn|facebook)[^\"]*)\"', 40),
    }
    # Additional common encoded CDN URLs from inline Relay payloads.
    for candidate in re.findall(r'https?:\\/\\/[^\"\\s]{20,800}', body):
        value = _clean(candidate)
        if any(x in value for x in ("scontent", "fbcdn")) and value not in extraction["image_urls"]:
            extraction["image_urls"].append(value)
        if len(extraction["image_urls"]) >= 40:
            break

    log.info("FB285_PROBE %s", json.dumps(extraction, ensure_ascii=False))
    return {"enabled": True, "status": r.status_code, "html_len": len(body), "found_images": len(extraction["image_urls"])}

# -*- coding: utf-8 -*-
"""Read-only diagnostic for Facebook Marketplace item 2236326640522113."""
from __future__ import annotations
import asyncio, json, logging, os, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("diagnose-fb-2236326640522113")
ITEM = "2236326640522113"
URLS = [
    f"https://www.facebook.com/marketplace/item/{ITEM}/?locale=en_US",
    f"https://m.facebook.com/marketplace/item/{ITEM}/?locale=en_US",
]


def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}


def _fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=40, allow_redirects=True)
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    metas = {}
    for prop in ("og:title","og:description","og:image","twitter:title","twitter:description","twitter:image"):
        tag = soup.find("meta", attrs={"property":prop}) or soup.find("meta", attrs={"name":prop})
        if tag and tag.get("content"):
            metas[prop] = tag.get("content")
    raw=[]
    for tag in soup.find_all(["img","source"]):
        for attr in ("src","data-src","data-original","srcset","data-srcset"):
            v=tag.get(attr)
            if not v: continue
            for part in str(v).split(","):
                u=part.strip().split(" ")[0]
                if u.startswith("//"): u="https:"+u
                elif u.startswith("/"): u=urljoin(r.url,u)
                if u.startswith("http"): raw.append(u)
    for m in re.findall(r'https?:\\?/\\?/[^"\\s<>]+?(?:\\.jpg|\\.jpeg|\\.png|\\.webp)(?:\\?[^"\\s<>]*)?', html, re.I):
        raw.append(m.replace("\\/","/"))
    seen=[]
    for u in raw:
        if u not in seen: seen.append(u)
    imgs=[u for u in seen if any(x in u.lower() for x in ("fbcdn","scontent","lookaside","facebook"))]
    return {
        "requested":url,
        "status":r.status_code,
        "final_url":r.url,
        "html_len":len(html),
        "title": soup.title.get_text(" ",strip=True)[:300] if soup.title else "",
        "metas": metas,
        "image_count":len(imgs),
        "images":imgs[:80],
        "contains_item": ITEM in html,
        "login_wall": any(x in html.lower() for x in ("log in to facebook","login_form","you must log in")),
        "snippet": re.sub(r"\s+"," ",soup.get_text(" ",strip=True))[:1200],
    }


async def run():
    if not enabled(): return {"enabled":False}
    results=[]
    for u in URLS:
        try:
            results.append(await asyncio.to_thread(_fetch,u))
        except Exception as e:
            results.append({"requested":u,"error":repr(e)})
    out={"enabled":True,"item":ITEM,"results":results}
    log.info("DIAGNOSE_FB_2236326640522113_DONE %s",json.dumps(out,ensure_ascii=False))
    return out

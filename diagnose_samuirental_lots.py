# -*- coding: utf-8 -*-
"""Temporary read-only diagnostic for The Terraza Samui image sources."""
import asyncio, json, logging, os, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

log=logging.getLogger("diagnose-samuirental-lots")
URLS=(
    "https://www.samuitimes.com/property-rent/studio-condo-for-rent-at-the-terraza-samui-in-maret-surat-thani-u6714134",
    "https://www.kaibaanthai.com/en/property-rent/studio-condo-for-rent-at-the-terraza-samui-in-maret-surat-thani-u6714134",
    "https://www.fazwaz.com/property-rent/studio-condo-for-rent-at-the-terraza-samui-in-maret-surat-thani-u6714134",
)

def enabled(): return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

def _one(url):
    r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=30)
    r.raise_for_status(); html=r.text
    soup=BeautifulSoup(html,"html.parser")
    raw=[]
    for tag in soup.find_all(["img","source"]):
        for attr in ("src","data-src","data-original","srcset","data-srcset"):
            v=tag.get(attr)
            if not v: continue
            for part in str(v).split(","):
                u=part.strip().split(" ")[0]
                if u: raw.append(urljoin(url,u))
    # Also capture image-like URLs embedded in JSON/script payloads.
    for m in re.findall(r'https?:\\?/\\?/[^"\\s<>]+?(?:\\.jpg|\\.jpeg|\\.png|\\.webp)(?:\\?[^"\\s<>]*)?',html,re.I):
        raw.append(m.replace('\\/','/'))
    seen=[]
    for u in raw:
        if u not in seen: seen.append(u)
    candidates=[u for u in seen if any(x in u.lower() for x in ("fazwaz","property","image","cdn","cloudfront","static","storage"))]
    return {"url":url,"status":r.status_code,"html_len":len(html),"count":len(seen),"candidates":candidates[:120]}

async def run():
    if not enabled(): return {"enabled":False}
    result={"enabled":True,"pages":[await asyncio.to_thread(_one,u) for u in URLS]}
    log.info("DIAGNOSE_TERRAZA_IMAGES_DONE %s",json.dumps(result,ensure_ascii=False))
    return result

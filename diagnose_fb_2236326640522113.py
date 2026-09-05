# -*- coding: utf-8 -*-
"""Read-only source diagnostic for Marketplace item 2236326640522113 and matching mirror."""
from __future__ import annotations
import asyncio, json, logging, os, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

log=logging.getLogger("diagnose-fb-2236326640522113")
ITEM="2236326640522113"
URLS=[
 "https://www.facebook.com/marketplace/item/2236326640522113/?locale=en_US",
 "https://m.facebook.com/marketplace/item/2236326640522113/?locale=en_US",
 "https://propertyhub.in.th/en/listings/sea-view-2-bedroom-villa-for-rent-near-chaweng-5587827---5327189",
 "https://www.fazwaz.co.th/en/property-rent/2-bedroom-villa-for-rent-at-chaweng-modern-villas-in-bo-phut-surat-thani-u5587827",
 "https://www.samuitimes.com/property-rent/2-bedroom-villa-for-rent-at-chaweng-modern-villas-in-bo-phut-surat-thani-u5587827",
 "https://www.kaibaanthai.com/en/property-rent/2-bedroom-villa-for-rent-at-chaweng-modern-villas-in-bo-phut-surat-thani-u5587827",
 "https://www.property-hua-hin.com/property-rent/2-bedroom-villa-for-rent-at-chaweng-modern-villas-in-bo-phut-surat-thani-u5587827",
 "https://www.108siam.com/en/property-rent/2-bedroom-villa-for-rent-at-chaweng-modern-villas-in-bo-phut-surat-thani-u5587827",
 "https://www.livephuket.com/property-rent/2-bedroom-villa-for-rent-at-chaweng-modern-villas-in-bo-phut-surat-thani-u5587827",
]

def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

def _fetch(url):
    h={"User-Agent":"Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 Chrome/128.0 Mobile Safari/537.36","Accept-Language":"en-US,en;q=0.9,th;q=0.8"}
    r=requests.get(url,headers=h,timeout=45,allow_redirects=True)
    html=r.text; soup=BeautifulSoup(html,"html.parser")
    metas={}
    for prop in ("og:title","og:description","og:image","twitter:title","twitter:description","twitter:image"):
        tag=soup.find("meta",attrs={"property":prop}) or soup.find("meta",attrs={"name":prop})
        if tag and tag.get("content"): metas[prop]=tag.get("content")
    raw=[]
    for tag in soup.find_all(["img","source"]):
        for attr in ("src","data-src","data-original","data-lazy-src","srcset","data-srcset"):
            v=tag.get(attr)
            if not v: continue
            for part in str(v).split(","):
                u=part.strip().split(" ")[0]
                if u.startswith("//"): u="https:"+u
                elif u.startswith("/"): u=urljoin(r.url,u)
                if u.startswith("http"): raw.append(u)
    # Capture encoded/JSON image URLs too.
    for pat in [
        r'https?:\\?/\\?/[^"\\s<>]+?(?:\\.jpg|\\.jpeg|\\.png|\\.webp)(?:\\?[^"\\s<>]*)?',
        r'https?:\\u002F\\u002F[^"\\s<>]+?(?:jpg|jpeg|png|webp)[^"\\s<>]*'
    ]:
        for m in re.findall(pat,html,re.I):
            raw.append(m.replace("\\u002F","/").replace("\\/","/"))
    seen=[]
    for u in raw:
        u=u.replace("&amp;","&")
        if u not in seen: seen.append(u)
    useful=[u for u in seen if not any(x in u.lower() for x in ("logo","icon","avatar","sprite","favicon"))]
    text=re.sub(r"\s+"," ",soup.get_text(" ",strip=True))
    return {"requested":url,"status":r.status_code,"final_url":r.url,"html_len":len(html),
            "title":soup.title.get_text(" ",strip=True)[:300] if soup.title else "",
            "metas":metas,"image_count":len(useful),"images":useful[:120],
            "snippet":text[:2500]}

async def run():
    if not enabled(): return {"enabled":False}
    out={"enabled":True,"item":ITEM,"results":[]}
    for u in URLS:
        try: out["results"].append(await asyncio.to_thread(_fetch,u))
        except Exception as e: out["results"].append({"requested":u,"error":repr(e)})
    log.info("DIAGNOSE_FB_2236326640522113_DONE %s",json.dumps(out,ensure_ascii=False))
    return out

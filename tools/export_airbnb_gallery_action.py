from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from airbnb_photo_backfill_core import extract_muscache_candidates, filter_listing_photo_urls, rewrite_url_host

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
HOSTS = ["www.airbnb.ca", "www.airbnb.co.uk", "www.airbnb.com"]
LOTS = {
    "1201": "1259009506231059461",
    "1202": "20470786",
    "1203": "1424526292630741009",
    "1204": "20901998",
    "1205": "1764938638907964460",
    "1206": "1525859637375407453",
    "1207": "1380289917461504669",
}


def get_gallery(room_id: str):
    base = f"https://www.airbnb.com/rooms/{room_id}"
    headers = {
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    errors = []
    for host in HOSTS:
        source = rewrite_url_host(base, host)
        seen = set()
        urls = []
        info = []
        try:
            with requests.Session() as s:
                s.headers.update(headers)
                for page in (source, source + "?modal=PHOTO_TOUR_SCROLLABLE"):
                    r = s.get(page, timeout=60, allow_redirects=True)
                    info.append({"url": page, "status": r.status_code, "final_url": r.url, "bytes": len(r.content)})
                    r.raise_for_status()
                    for u in filter_listing_photo_urls(extract_muscache_candidates(r.text)):
                        if u not in seen:
                            seen.add(u)
                            urls.append(u)
            if len(urls) >= 10:
                return source, urls, info
            errors.append({"host": host, "count": len(urls), "info": info})
        except Exception as exc:
            errors.append({"host": host, "error": repr(exc), "info": info})
    raise RuntimeError(f"No usable Airbnb source for room {room_id}: {errors}")


def image_bytes(url: str, referer: str) -> tuple[bytes, str]:
    headers = {"User-Agent": UA, "Referer": referer}
    last = None
    for suffix in ("?im_w=720", "?im_w=1080", ""):
        try:
            r = requests.get(url + suffix, headers=headers, timeout=90)
            r.raise_for_status()
            ctype = (r.headers.get("content-type") or "").lower()
            if "image" not in ctype:
                raise RuntimeError(f"not image: {ctype}")
            raw = r.content
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()
            return raw, ctype
        except Exception as exc:
            last = exc
    raise RuntimeError(f"Could not download {url}: {last!r}")


def export_lot(lot: str, room_id: str, root: Path):
    source, urls, page_info = get_gallery(room_id)
    out = root / lot
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "lot": lot,
        "room_id": room_id,
        "source": source,
        "source_total": len(urls),
        "page_info": page_info,
        "files": [],
    }
    for i, url in enumerate(urls, 1):
        raw, ctype = image_bytes(url, source)
        ext = Path(urlsplit(url).path).suffix.lower() or ".jpg"
        if ext == ".jpeg":
            ext = ".jpg"
        token = Path(urlsplit(url).path).stem[-36:]
        name = f"source_{i:03d}_{token}{ext}"
        (out / name).write_bytes(raw)
        manifest["files"].append({
            "index": i,
            "name": name,
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "content_type": ctype,
        })
        if i % 25 == 0 or i == len(urls):
            print(f"lot={lot} downloaded={i}/{len(urls)}", flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"EXPORT_DONE lot={lot} source_total={len(urls)} source={source}", flush=True)


def main():
    root = Path(os.getenv("EXPORT_ROOT", "photo_exports"))
    root.mkdir(parents=True, exist_ok=True)
    for lot, room_id in LOTS.items():
        export_lot(lot, room_id, root)


if __name__ == "__main__":
    main()

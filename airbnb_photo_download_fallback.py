from __future__ import annotations

import time

import requests

from airbnb_photo_backfill_core import dhash_bytes, image_download_variants

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def download_full_image(url: str, source: str) -> bytes:
    """Download a validated Airbnb gallery image using bounded CDN fallbacks.

    Some muscache originals do not expose every resize transform (notably 1600),
    while the 720 transform used by the source hash gate is available. Try the
    preferred larger transforms first, then the known-good 720 transform and the
    canonical URL. Every successful response is decoded by the same image hash
    routine before it can be uploaded to Drive.
    """
    errors: list[str] = []
    for candidate in image_download_variants(url):
        for attempt in range(2):
            try:
                with requests.get(
                    candidate,
                    headers={"User-Agent": UA, "Referer": source},
                    timeout=90,
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    content_type = (response.headers.get("content-type") or "").lower()
                    if "image" not in content_type:
                        raise RuntimeError(f"non-image response content_type={content_type!r}")
                    raw = response.content
                if not raw:
                    raise RuntimeError("empty image response")
                dhash_bytes(raw)
                return raw
            except Exception as exc:
                errors.append(f"{candidate} attempt={attempt + 1}: {exc!r}")
                if attempt == 0:
                    time.sleep(1)
    tail = errors[-6:]
    raise RuntimeError(f"Could not download validated image {url}; recent errors={tail}")

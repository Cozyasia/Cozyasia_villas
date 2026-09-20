from __future__ import annotations

import html as html_lib
import io
import re
from typing import Sequence
from urllib.parse import urlsplit, urlunsplit

from PIL import Image

_IMG_EXT_RE = re.compile(r'\.(?:jpe?g|png|webp)(?:\?|$)', re.I)
_EXCLUDE_PATH_MARKERS = (
    '/airbnb-platform-assets/',
    '/airbnbplatformassets/',
    '/userprofile/',
    '/favicons/',
    '/maps/',
)


def _decode_url_token(token: str) -> str:
    value = html_lib.unescape(token)
    value = value.replace('\\u002F', '/').replace('\\u002f', '/')
    value = value.replace('\\u003A', ':').replace('\\u003a', ':')
    value = value.replace('\\/', '/')
    value = value.rstrip('\\')
    return value


def _canonical_image_url(url: str) -> str | None:
    url = _decode_url_token(url)
    if not url.lower().startswith('https://a0.muscache.com/im/pictures/'):
        return None
    parts = urlsplit(url)
    path_low = parts.path.lower()
    if any(marker in path_low for marker in _EXCLUDE_PATH_MARKERS):
        return None
    if not _IMG_EXT_RE.search(parts.path):
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))


def extract_muscache_candidates(raw_html: str) -> list[str]:
    """Extract unique Airbnb-hosted image URLs in source order.

    Runtime validation must still verify that archived Telegram references match
    the candidate set before any Drive write.
    """
    if not raw_html:
        return []
    prepared = raw_html.replace('\\u002F', '/').replace('\\u002f', '/')
    prepared = prepared.replace('\\u003A', ':').replace('\\u003a', ':')
    prepared = prepared.replace('\\/', '/')
    prepared = html_lib.unescape(prepared)
    broad = re.compile(r'https://a0\.muscache\.com/im/pictures/[^\"\'<>\s]+', re.I)
    out: list[str] = []
    seen: set[str] = set()
    for match in broad.finditer(prepared):
        token = match.group(0).rstrip('\\,]}')
        canonical = _canonical_image_url(token)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        out.append(canonical)
    return out


def dhash_bytes(data: bytes, hash_size: int = 8) -> int:
    if not data:
        raise ValueError('empty image bytes')
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert('L').resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        pixels = list(im.get_flattened_data())
    value = 0
    width = hash_size + 1
    for y in range(hash_size):
        row = y * width
        for x in range(hash_size):
            value = (value << 1) | int(pixels[row + x] > pixels[row + x + 1])
    return value


def hamming_distance(a: int, b: int) -> int:
    return int(a ^ b).bit_count()


def choose_additional_candidates(
    reference_images: Sequence[bytes],
    candidates: Sequence[tuple[str, bytes]],
    *,
    threshold: int = 5,
) -> list[tuple[str, bytes]]:
    """Return unique candidate photos not visually matching archived references."""
    ref_hashes: list[int] = []
    for raw in reference_images:
        h = dhash_bytes(raw)
        if h not in ref_hashes:
            ref_hashes.append(h)

    accepted: list[tuple[str, bytes]] = []
    accepted_hashes: list[int] = []
    for url, raw in candidates:
        h = dhash_bytes(raw)
        if any(hamming_distance(h, ref) <= threshold for ref in ref_hashes):
            continue
        if any(hamming_distance(h, old) <= threshold for old in accepted_hashes):
            continue
        accepted.append((url, raw))
        accepted_hashes.append(h)
    return accepted


def reference_match_count(
    reference_images: Sequence[bytes],
    candidates: Sequence[tuple[str, bytes]],
    *,
    threshold: int = 5,
) -> tuple[int, int]:
    """Return (matched unique reference hashes, unique reference hashes)."""
    ref_hashes: list[int] = []
    for raw in reference_images:
        h = dhash_bytes(raw)
        if h not in ref_hashes:
            ref_hashes.append(h)
    candidate_hashes = [dhash_bytes(raw) for _, raw in candidates]
    matched = sum(
        1 for ref in ref_hashes
        if any(hamming_distance(ref, cand) <= threshold for cand in candidate_hashes)
    )
    return matched, len(ref_hashes)


def insert_additional_photos_line(text: str, drive_url: str) -> str:
    """Insert the visible link label immediately before the final hashtag block."""
    label = '📸 Дополнительные фото'
    if label in (text or ''):
        return text
    source = (text or '').rstrip()
    lines = source.splitlines()
    first_hash = None
    for i, line in enumerate(lines):
        if line.strip().startswith('#'):
            first_hash = i
            break
    if first_hash is None:
        prefix = source
        suffix = ''
    else:
        prefix = '\n'.join(lines[:first_hash]).rstrip()
        suffix = '\n'.join(lines[first_hash:]).lstrip()
    parts = [prefix, label]
    if suffix:
        parts.append(suffix)
    return '\n\n'.join(p for p in parts if p)

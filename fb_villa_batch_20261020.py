# -*- coding: utf-8 -*-
"""Prepared Facebook Marketplace villa batch for the Cozy Asia small channel.

The module is deliberately import-safe: importing it never logs in, sends a
message, changes Render state, or contacts Telegram.  Publication is only
entered through the explicit service-mode flag in main.py.
"""
from __future__ import annotations

import asyncio
import html
import json
import os
import tempfile
import threading
import urllib.request
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


CHANNEL = "arenda_vill_samui"
BOT = "Cozyasia_villa_bot"
DATES = "24.12.2026–24.01.2027"
NIGHTS = 31
MAX_CAPTION_LENGTH = 1024
MAX_PHOTOS = 10


@dataclass(frozen=True)
class ListingSpec:
    lot_id: str
    title: str
    district: str
    source_url: str
    seller_url: str
    bedrooms: int
    price_thb: int
    price_terms: str
    photo_paths: tuple[str, ...] = ()
    photo_urls: tuple[str, ...] = ()
    notes: str = ""


def _source_id(url: str) -> str:
    marker = "/item/"
    if marker in url:
        return url.split(marker, 1)[1].split("/", 1)[0]
    return url.rsplit("/", 1)[-1] or "unknown"


def validate_manifest(entries: Iterable[ListingSpec]) -> list[ListingSpec]:
    items = list(entries)
    if not items:
        raise ValueError("manifest is empty")
    seen_lots: set[str] = set()
    seen_sources: set[str] = set()
    for item in items:
        if not isinstance(item, ListingSpec):
            raise ValueError("manifest entries must be ListingSpec")
        if not item.lot_id or item.lot_id in seen_lots:
            raise ValueError(f"duplicate lot_id: {item.lot_id}")
        if not item.source_url or "/marketplace/item/" not in item.source_url:
            raise ValueError("source_url must be a Facebook Marketplace item URL")
        if item.source_url in seen_sources:
            raise ValueError(f"duplicate source_url: {item.source_url}")
        if not item.seller_url:
            raise ValueError(f"seller_url is required for {item.lot_id}")
        if item.bedrooms != 4:
            raise ValueError(f"{item.lot_id} must have exactly 4 bedrooms")
        if item.price_thb <= 0:
            raise ValueError(f"{item.lot_id} price must be positive")
        if len(item.photo_paths) > MAX_PHOTOS or len(item.photo_urls) > MAX_PHOTOS:
            raise ValueError(f"{item.lot_id} has at most 10 photos")
        seen_lots.add(item.lot_id)
        seen_sources.add(item.source_url)
    return items


def render_caption(item: ListingSpec, lot_id: str | None = None) -> str:
    lot = lot_id or item.lot_id
    safe_title = html.escape(item.title)
    safe_district = html.escape(item.district)
    safe_terms = html.escape(item.price_terms)
    safe_notes = html.escape(item.notes or "Details and final holiday-season total to be confirmed.")
    source_id = html.escape(_source_id(item.source_url))
    rent_url = f"https://t.me/{BOT}?start=rent_{html.escape(lot)}"
    search_url = f"https://t.me/{BOT}?start=search"
    site_url = "https://cozyasia-villas.onrender.com"
    map_url = "https://www.google.com/maps/search/?api=1&query=" + html.escape(item.district) + "+Koh+Samui"
    caption = (
        f"🏝 <b>ЛОТ {html.escape(lot)} · {safe_title}</b>\n"
        f"📍 {safe_district}\n\n"
        f"💬 <b>ОПИСАНИЕ</b>\n"
        f"<blockquote>🛏 4 спальни • бассейн • Самуи\n"
        f"📅 {DATES} · {NIGHTS} ночей\n"
        f"💰 В объявлении: {item.price_thb:,} THB/мес.\n"
        f"{safe_terms}\n{safe_notes}\n"
        f"💳 Депозит, коммунальные платежи, уборка и итог за сезон — уточняются.</blockquote>\n\n"
        f"📸 <a href=\"{html.escape(item.source_url, quote=True)}\">Все дополнительные фото и исходное объявление</a>\n"
        f"🌐 <a href=\"{site_url}\">Сайт Cozy Asia</a> · 🗺 <a href=\"{map_url}\">Карта района</a>\n"
        f"🔗 Facebook Marketplace #{source_id}\n\n"
        f"<a href=\"{rent_url}\"><b>ЖМИ ЗДЕСЬ — ОСТАВИТЬ ЗАЯВКУ</b></a>\n"
        f"Оператор: @cozy_asia\n\n"
        f"🔎 <a href=\"{search_url}\"><b>НАПИСАТЬ БОТУ</b></a> — подобрать другие варианты\n\n"
        f"#Самуи #вилла #4спальни #CozyAsia"
    )
    if len(caption) > MAX_CAPTION_LENGTH:
        raise ValueError(f"{lot} caption exceeds Telegram limit")
    return caption


DEFAULT_LISTINGS: tuple[ListingSpec, ...] = (
    ListingSpec("V01", "Plai Laem Pool Villa", "Plai Laem",
        "https://www.facebook.com/marketplace/item/2130864267516279/",
        "https://www.facebook.com/profile.php?id=100065431604518", 4, 130000,
        "Monthly asking price; exact 31-night total and New Year supplement requested.",
        notes="Private pool; 4 bathrooms; January 2027 availability was shown."),
    ListingSpec("V02", "Bang Rak Private Pool Townhouse", "Bang Rak",
        "https://www.facebook.com/marketplace/item/1119348020492770/",
        "https://www.facebook.com/profile.php?id=61593132805963", 4, 88000,
        "Monthly asking price; short-stay availability requested.",
        notes="Private pool; 4 bathrooms."),
    ListingSpec("V03", "Lamai Private Pool Villa", "Lamai",
        "https://www.facebook.com/marketplace/item/1626335235816577/",
        "https://www.facebook.com/profile.php?id=61562995933412", 4, 120000,
        "Monthly asking price; shorter terms shown as possible.",
        notes="Private pool; 4 bathrooms."),
    ListingSpec("V04", "Four Bedroom Pool House", "Samui",
        "https://www.facebook.com/marketplace/item/1747779776320483/",
        "https://www.facebook.com/profile.php?id=61570073618869", 4, 98000,
        "Monthly asking price; listing said long-term only.",
        notes="Availability for the requested dates must be confirmed."),
    ListingSpec("V05", "Chaweng Sea View Pool Villa", "Chaweng",
        "https://www.facebook.com/marketplace/item/1394618565855668/",
        "https://www.facebook.com/profile.php?id=100090554544659", 4, 100000,
        "Monthly asking price; holiday-season total requested.",
        notes="Sea view and private pool shown."),
    ListingSpec("V06", "Plai Laem Pool Villa", "Plai Laem",
        "https://www.facebook.com/marketplace/item/2304437457076333/",
        "https://www.facebook.com/profile.php?id=588505707", 4, 120000,
        "120,000 THB/month shown; exact 31-night New Year total requested.",
        notes="4 bedrooms, 3 bathrooms and private pool shown."),
    ListingSpec("V07", "Baan Tai Pool Villa", "Baan Tai",
        "https://www.facebook.com/marketplace/item/1105732308647467/",
        "https://www.facebook.com/profile.php?id=507153554", 4, 90000,
        "85,000–90,000 THB/month shown; water and Wi-Fi were described as included.",
        notes="Pool shown; exact utilities and cleaning terms requested."),
    ListingSpec("V08", "Bophut Hills Pool Villa", "Bophut",
        "https://www.facebook.com/marketplace/item/955219133976612/",
        "https://www.facebook.com/profile.php?id=100011921717098", 4, 85000,
        "75,000 THB long-term / 85,000 THB for 1–3 months shown.",
        notes="Private pool; one-month deposit shown."),
    ListingSpec("V09", "Plai Laem Short-Stay Pool Villa", "Plai Laem",
        "https://www.facebook.com/marketplace/item/1723855948709204/",
        "https://www.facebook.com/profile.php?id=100001102788489", 4, 125000,
        "125,000 THB until mid-December shown; exact holiday total requested.",
        notes="Private pool; short and long stays were shown."),
    ListingSpec("V10", "Elegance Four Bedroom Pool Villa", "Plai Laem / Thongson Bay",
        "https://www.facebook.com/marketplace/item/4326694470928730/",
        "https://www.facebook.com/profile.php?id=100000518494719", 4, 90000,
        "85,000 THB long-term / 90,000 THB short-term shown.",
        notes="Pool villa; exact holiday-season total requested."),
    ListingSpec("V11", "Tongson Bay Pool Villa", "Plai Laem / Tongson Bay",
        "https://www.facebook.com/marketplace/item/2114143385803669/",
        "https://www.facebook.com/profile.php?id=100084915255509", 4, 110000,
        "110,000 THB/month shown; one-month deposit shown.",
        notes="Private pool and private beach shown."),
)


def _photo_files(item: ListingSpec) -> list[Path]:
    files = [Path(p) for p in item.photo_paths]
    if len(files) > MAX_PHOTOS:
        raise ValueError(f"{item.lot_id} has at most 10 photos")
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"{item.lot_id} photo files missing: {missing}")
    return files


def _photo_media(item: ListingSpec) -> list[str | Path]:
    if item.photo_urls:
        if len(item.photo_urls) != MAX_PHOTOS:
            raise ValueError(f"{item.lot_id} requires exactly 10 photo URLs")
        root = Path(tempfile.mkdtemp(prefix=f"cozy-{item.lot_id.lower()}-"))
        files: list[Path] = []
        for index, url in enumerate(item.photo_urls, start=1):
            target = root / f"{index:02d}.jpg"
            urllib.request.urlretrieve(url, target)
            if not target.is_file() or target.stat().st_size < 1000:
                raise ValueError(f"downloaded photo is invalid: {url[:100]}")
            files.append(target)
        return files
    return _photo_files(item)


async def run_batch(entries: Sequence[ListingSpec], dry_run: bool = True, *, client_factory=None, duplicate_checker=None, allow_text_only: bool = False) -> list[dict]:
    items = validate_manifest(entries)
    if dry_run:
        return [
            {"lot_id": item.lot_id, "status": "dry_run",
             "caption_length": len(render_caption(item)),
             "source_url": item.source_url}
            for item in items
        ]

    # Keep all Telegram-specific imports lazy so tests and normal web startup
    # cannot accidentally authenticate or publish.
    if client_factory is None:
        from mtproto_user_client import _new_client
        import cozy_catalog
        async def client_factory():
            client = await _new_client(cozy_catalog)
            if client is None:
                raise RuntimeError("MTProto session is not authorized")
            return client
    if duplicate_checker is None:
        from publication_safety import find_duplicate_listing
        duplicate_checker = find_duplicate_listing

    client = await client_factory()
    results: list[dict] = []
    try:
        channel = await client.get_entity(f"@{CHANNEL}")
        for item in items:
            try:
                files = _photo_media(item)
                if not files and not allow_text_only:
                    raise ValueError("publication requires at least one prepared photo")
                caption = render_caption(item)
                duplicate = await duplicate_checker(
                    client, channel, ["facebook marketplace", _source_id(item.source_url)]
                )
                if duplicate is not None:
                    results.append({"lot_id": item.lot_id, "status": "duplicate_skipped", "message_id": getattr(duplicate, "id", None)})
                    continue
                if files:
                    sent = await client.send_file(channel, files, caption=caption, album=True)
                else:
                    sent = await client.send_message(channel, caption, link_preview=False)
                message_ids = [getattr(message, "id", None) for message in (sent if isinstance(sent, list) else [sent])]
                verified = []
                for message_id in message_ids:
                    verified.append(await client.get_messages(channel, ids=message_id))
                if not all(verified):
                    raise RuntimeError("Telegram read-back verification failed")
                results.append({"lot_id": item.lot_id, "status": "published", "message_ids": message_ids})
            except Exception as exc:
                results.append({"lot_id": item.lot_id, "status": "failed", "error": str(exc)})
    finally:
        disconnect = getattr(client, "disconnect", None)
        if disconnect is not None:
            maybe = disconnect()
            if asyncio.iscoroutine(maybe):
                await maybe
    return results


def run_service_mode() -> None:
    dry_run = os.getenv("FB_VILLA_BATCH_DRY_RUN", "1").strip() != "0"
    text_only = os.getenv("FB_VILLA_BATCH_TEXT_ONLY", "0").strip().lower() in {"1", "true", "yes", "on"}
    results = asyncio.run(run_batch(DEFAULT_LISTINGS, dry_run=dry_run, allow_text_only=text_only))
    print({"channel": CHANNEL, "dry_run": dry_run, "results": results})


def run_manifest_receiver() -> None:
    """Temporary authenticated-by-deployment receiver for the browser photo manifest."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path != "/manifest-form":
                self.send_error(404)
                return
            body = b'''<!doctype html><meta charset="utf-8"><title>Cozy Asia manifest</title><form method="post" action="/publish-photo-manifest"><textarea name="manifest" style="width:95vw;height:70vh"></textarea><br><button>Publish 11 albums</button></form>'''
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):  # noqa: N802
            if self.path != "/publish-photo-manifest":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                raw = self.rfile.read(length).decode("utf-8")
                if self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
                    manifest = json.loads(parse_qs(raw).get("manifest", [""])[0])
                else:
                    manifest = json.loads(raw)
                if not isinstance(manifest, dict) or set(manifest) != {item.source_url for item in DEFAULT_LISTINGS}:
                    raise ValueError("manifest must contain all 11 source URLs")
                entries = [
                    ListingSpec(**{**item.__dict__, "photo_urls": tuple(manifest[item.source_url][:MAX_PHOTOS])})
                    for item in DEFAULT_LISTINGS
                ]
                def publish_background():
                    results = asyncio.run(run_batch(entries, dry_run=False, allow_text_only=False))
                    print({"background_results": results}, flush=True)
                threading.Thread(target=publish_background, daemon=True).start()
                payload = json.dumps({"accepted": True, "lots": len(entries)}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        def log_message(self, *_args):
            return
    server = HTTPServer(("0.0.0.0", int(os.getenv("PORT", "10000"))), Handler)
    print({"receiver": "ready", "channel": CHANNEL}, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_service_mode()



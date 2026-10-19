# -*- coding: utf-8 -*-
"""Prepared Facebook Marketplace villa batch for the Cozy Asia small channel.

The module is deliberately import-safe: importing it never logs in, sends a
message, changes Render state, or contacts Telegram.  Publication is only
entered through the explicit service-mode flag in main.py.
"""
from __future__ import annotations

import asyncio
import html
import os
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
        if len(item.photo_paths) > MAX_PHOTOS:
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
    caption = (
        f"🏝 <b>{safe_title}</b> — {safe_district}\n\n"
        f"<b>ОПИСАНИЕ</b>\n"
        f"<blockquote>4 спальни • Самуи • частный бассейн (если указан в объявлении)\n"
        f"Период: {DATES} ({NIGHTS} ночей)\n"
        f"Цена в объявлении: {item.price_thb:,} THB/мес.\n"
        f"{safe_terms}\n"
        f"{safe_notes}</blockquote>\n\n"
        f"Источник: Facebook Marketplace #{source_id}\n\n"
        f"<a href=\"{rent_url}\">ЖМИ ЗДЕСЬ</a>\n\n\n"
        f"Оператор: @cozy_asia (Cozy Asia)\n\n"
        f"<a href=\"{search_url}\">ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ</a>\n\n"
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
    ListingSpec("V06", "Plai Laem Soi 8 Villa", "Plai Laem",
        "https://www.facebook.com/marketplace/item/4292405310896501/",
        "https://www.facebook.com/profile.php?id=596701893", 4, 77000,
        "Monthly asking price; listing said long-term only.",
        notes="Pool and sea view shown."),
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


async def run_batch(entries: Sequence[ListingSpec], dry_run: bool = True) -> list[dict]:
    items = validate_manifest(entries)
    if dry_run:
        return [
            {"lot_id": item.lot_id, "status": "dry_run",
             "caption_length": len(render_caption(item)),
             "source_url": item.source_url}
            for item in items
        ]

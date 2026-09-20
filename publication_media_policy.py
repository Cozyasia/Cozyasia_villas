# -*- coding: utf-8 -*-
"""Permanent media policy for Cozy Asia property publications.

Public Telegram listing rule:
- one listing = one Telegram media album + its caption;
- show at most 10 selected/best property photos in Telegram;
- when more than 10 photos exist, publish exactly 10 featured photos and place every remaining photo in a public Google Drive folder;
- include a visible "Дополнительные фото" Google Drive link in the same listing caption;
- never publish follow-up Telegram albums/messages like "Фотографии к лоту ..." for overflow media.
"""
from __future__ import annotations

TELEGRAM_FEATURED_PHOTO_LIMIT = 10
ADDITIONAL_PHOTOS_LABEL = "Дополнительные фото"


def validate_media_policy(*, total_photos: int, featured_photos: int, additional_drive_url: str = "") -> dict:
    total = int(total_photos or 0)
    featured = int(featured_photos or 0)
    drive = str(additional_drive_url or "").strip()
    if total < 1:
        raise RuntimeError("A property publication must contain at least one photo")
    if featured < 1 or featured > TELEGRAM_FEATURED_PHOTO_LIMIT:
        raise RuntimeError(f"Telegram featured photos must be 1..{TELEGRAM_FEATURED_PHOTO_LIMIT}, got {featured}")
    if total > TELEGRAM_FEATURED_PHOTO_LIMIT:
        if featured != TELEGRAM_FEATURED_PHOTO_LIMIT:
            raise RuntimeError(
                f"Listings with >{TELEGRAM_FEATURED_PHOTO_LIMIT} photos must publish exactly "
                f"{TELEGRAM_FEATURED_PHOTO_LIMIT} selected photos in Telegram"
            )
        if not drive.startswith("https://drive.google.com/"):
            raise RuntimeError("Overflow photos require a public Google Drive URL")
    return {
        "total_photos": total,
        "telegram_featured_photos": featured,
        "overflow_photos": max(0, total - featured),
        "drive_required": total > TELEGRAM_FEATURED_PHOTO_LIMIT,
        "drive_url": drive,
    }

# -*- coding: utf-8 -*-
"""One-shot registry update for the 2026-08-28 evening Facebook scan."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import cozy_catalog

log = logging.getLogger("fb-marketplace-evening-scan-20260828")

ITEMS = [
    {
        "source_id": "facebook_marketplace_38081924314755659",
        "source_url": "https://www.facebook.com/marketplace/item/38081924314755659/",
        "owner_url": "https://www.facebook.com/marketplace/profile/100084852596290/?product_id=38081924314755659",
        "owner": "Sakdadet Bunchuai",
        "price": "22000",
        "district": "Bophut / Bangrak, Replay Samui",
        "type": "apartment/condo",
        "bedrooms": 1,
        "bathrooms": 1,
        "pool": "shared, pool view",
        "availability": "Advertised available now; owner confirmation pending",
        "deposit": "10,000 THB",
        "utilities": "Wi-Fi included; electricity 7 THB/unit; water 70 THB/unit",
        "minimum_stay": "Listing text is inconsistent: 22,000/month and 23,000/month for 3+ months; clarify",
        "restrictions": "Not specified",
        "original_text": "Replay Samui condominium in Bophut near Bangrak Beach. Modern furnished unit with pool view; swimming pool, sauna, gym/yoga room, basketball, tennis and table tennis. Advertised 22,000 THB/month; text also says 23,000 THB/month for 3+ months. Deposit 10,000 THB; Wi-Fi free; electricity 7 THB/unit; water 70 THB/unit.",
    },
    {
        "source_id": "facebook_marketplace_885761544392604",
        "source_url": "https://www.facebook.com/marketplace/item/885761544392604/",
        "owner_url": "https://www.facebook.com/marketplace/profile/100084852596290/?product_id=885761544392604",
        "owner": "Sakdadet Bunchuai",
        "price": "60000",
        "district": "Chaweng / Bophut",
        "type": "private pool villa",
        "bedrooms": 3,
        "bathrooms": 2,
        "pool": "private",
        "availability": "Advertised available; owner confirmation pending",
        "deposit": "1 month",
        "utilities": "Water and electricity at government rates",
        "minimum_stay": "1 month advertised; 60,000/year, 65,000/6 months, 70,000/1-5 months",
        "restrictions": "Pet friendly",
        "original_text": "Luxury modern furnished pool villa, 3 bedrooms, 2 bathrooms, 2 living rooms, kitchen, storage, private pool and covered parking. Rates: 60,000 THB/month for 1 year, 65,000 for 6 months, 70,000 for 1-5 months. Deposit 1 month. Water and electricity at government rates. Pets allowed.",
    },
    {
        "source_id": "facebook_marketplace_28439178889019465",
        "source_url": "https://www.facebook.com/marketplace/item/28439178889019465/",
        "owner_url": "https://www.facebook.com/marketplace/profile/61583258641155/?product_id=28439178889019465",
        "owner": "Kess Samui",
        "price": "75000",
        "district": "Maenam Soi 5",
        "type": "private pool villa",
        "bedrooms": 3,
        "bathrooms": 2,
        "pool": "private",
        "availability": "Advertised available; owner confirmation pending",
        "deposit": "75,000 THB",
        "utilities": "Internet, TV, pool/garden maintenance and well water included; electricity government rate; gas refills excluded",
        "minimum_stay": "Monthly; long-term prepayment discount mentioned but not quantified",
        "restrictions": "No smoking, no pets, no subletting, owner says no agents/middlemen",
        "original_text": "Large furnished 3-bedroom pool villa in Maenam Soi 5. Western kitchen, private pool, gated parking for 3 cars, garden. 75,000 THB/month; deposit 75,000 THB. Internet, TV, pool/garden maintenance and well water included. Electricity at government rate and gas refills excluded. No smoking, pets or subletting. Listing explicitly says no agents or middlemen.",
    },
    {
        "source_id": "facebook_marketplace_1753824879276783",
        "source_url": "https://www.facebook.com/marketplace/item/1753824879276783/",
        "owner_url": "https://www.facebook.com/marketplace/profile/100065378491465/?product_id=1753824879276783",
        "owner": "Apilada Ketkaew",
        "price": "90000",
        "district": "Chaweng",
        "type": "private pool villa",
        "bedrooms": 3,
        "bathrooms": 3,
        "pool": "private",
        "availability": "Advertised available; owner confirmation pending",
        "deposit": "45,000 THB",
        "utilities": "Wi-Fi included; water and electricity at government rates; monthly cleaning and linen change included",
        "minimum_stay": "Not specified; intended for long-term living",
        "restrictions": "No pets; no subletting",
        "original_text": "3-bedroom, 3-bathroom private pool villa in Chaweng with modern kitchen, poolside dining and parking. Advertised 90,000 THB/month; deposit 45,000 THB. Wi-Fi included; water and electricity at government rates; cleaning and linen change once per month. No pets and no subletting.",
    },
]


def enabled():
    return os.getenv("RECORD_FB_SCAN_20260828_EVENING", "0").strip().lower() in {"1", "true", "yes", "on"}


def _sheet(book, title, header):
    try:
        return book.worksheet(title)
    except Exception:
        ws = book.add_worksheet(title=title, rows=1000, cols=max(12, len(header)))
        ws.append_row(header, value_input_option="RAW")
        return ws


def run():
    if not enabled():
        return {"enabled": False}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    book = cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    src = _sheet(book, "SourceRegistry", [
        "created_at", "source_id", "source_url", "owner_url", "original_price_thb",
        "original_description", "availability", "channels_json", "lots_json",
        "message_ids_json", "status", "notes",
    ])
    own = _sheet(book, "OwnersAvailability", [
        "checked_at", "source_id", "owner", "source_url", "owner_url", "availability",
        "owner_price_thb", "deposit", "utilities", "reservation", "status", "notes",
    ])
    src_rows = src.get_all_values()
    own_rows = own.get_all_values()
    src_index = {row[1]: idx for idx, row in enumerate(src_rows[1:], start=2) if len(row) > 1}
    own_index = {row[1]: idx for idx, row in enumerate(own_rows[1:], start=2) if len(row) > 1}
    added = []
    updated = []
    for item in ITEMS:
        notes = json.dumps({
            "district": item["district"], "type": item["type"], "bedrooms": item["bedrooms"],
            "bathrooms": item["bathrooms"], "pool": item["pool"], "minimum_stay": item["minimum_stay"],
            "restrictions": item["restrictions"], "last_checked": now,
            "contact_status": "not_sent_facebook_identity_restriction",
        }, ensure_ascii=False)
        src_row = [
            now, item["source_id"], item["source_url"], item["owner_url"], item["price"],
            item["original_text"], item["availability"], "[]", "{}", "{}",
            "new_needs_owner_reply", notes,
        ]
        if item["source_id"] in src_index:
            src.update(f"A{src_index[item['source_id']]}:L{src_index[item['source_id']]}", [src_row], value_input_option="RAW")
            updated.append(item["source_id"])
        else:
            src.append_row(src_row, value_input_option="RAW")
            added.append(item["source_id"])
        own_notes = json.dumps({
            "district": item["district"], "type": item["type"], "bedrooms": item["bedrooms"],
            "bathrooms": item["bathrooms"], "pool": item["pool"], "restrictions": item["restrictions"],
            "original_listing_text": item["original_text"],
            "ru_summary": item["original_text"],
            "last_reply": None, "conversation_url": None,
        }, ensure_ascii=False)
        own_row = [
            now, item["source_id"], item["owner"], item["source_url"], item["owner_url"],
            item["availability"], item["price"], item["deposit"], item["utilities"],
            "Advance/payment method and booking point require owner confirmation",
            "awaiting_contact", own_notes,
        ]
        if item["source_id"] in own_index:
            own.update(f"A{own_index[item['source_id']]}:L{own_index[item['source_id']]}", [own_row], value_input_option="RAW")
        else:
            own.append_row(own_row, value_input_option="RAW")
    result = {"enabled": True, "added": added, "updated": updated, "count": len(ITEMS)}
    log.info("RECORD_FB_SCAN_20260828_EVENING_DONE %s", json.dumps(result, ensure_ascii=False))
    return result

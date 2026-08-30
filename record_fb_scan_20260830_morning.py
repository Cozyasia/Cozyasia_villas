# -*- coding: utf-8 -*-
"""One-shot registry update for the 2026-08-30 morning Facebook scan."""
from __future__ import annotations
import json, logging, os
from datetime import datetime, timezone
import cozy_catalog

log=logging.getLogger("fb-marketplace-morning-scan-20260830")
ITEM={
 "source_id":"facebook_marketplace_2499439770481318",
 "source_url":"https://www.facebook.com/marketplace/item/2499439770481318/",
 "owner_url":"https://www.facebook.com/marketplace/profile/1785642699/?product_id=2499439770481318",
 "owner":"Mattani Yingyong",
 "contact":"WhatsApp hidden in listing / Messenger",
 "price":"18000",
 "district":"Chaweng (PF Pool Villa)",
 "type":"private one-bedroom house / villa unit",
 "bedrooms":1,
 "bathrooms":1,
 "pool":"shared",
 "availability":"Advertised available now on 2026-08-30; exact dates require owner confirmation",
 "deposit":"1 month",
 "utilities":"Wi-Fi included; electricity 9 THB/unit; water 300 THB/person/month; cleaning excluded",
 "minimum_stay":"20,000 THB/month below 6 months; 18,000 THB/month for 12+ months; exact 6-11 month rate unclear",
 "restrictions":"No pets",
 "original_text":"PF Pool Villa (P), Chaweng: private 1-bedroom, 1-bathroom house with living area, equipped kitchen, parking and shared pool. Available now. 20,000 THB/month for stays under six months; 18,000 THB/month for one year or longer. Deposit one month. Wi-Fi included; electricity 9/unit, water 300/person/month; cleaning excluded."
}
EXCLUSIONS=[
 {"source_id":"facebook_marketplace_1574066387850449","status":"duplicate","duplicate_of":"facebook_marketplace_1244049307857070","reason":"same seller, text, map, contact, price and specifications; exact repost"},
 {"source_id":"facebook_marketplace_1601549094899877","status":"out_of_scope","reason":"massage-shop business sale, not a residential rental"},
 {"source_id":"facebook_marketplace_4598177793749295","status":"out_of_scope","reason":"apartment, outside requested villas/houses/townhouses"},
 {"source_id":"facebook_marketplace_3170182426518923","status":"out_of_scope","reason":"property for sale, not rent"}
]

def enabled(): return os.getenv("RECORD_FB_SCAN_20260830_MORNING","0").strip().lower() in {"1","true","yes","on"}

def _sheet(book,title,header):
    try:return book.worksheet(title)
    except Exception:
        ws=book.add_worksheet(title=title,rows=1000,cols=max(12,len(header)))
        ws.append_row(header,value_input_option="RAW")
        return ws

def run():
    if not enabled(): return {"enabled":False}
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    book=cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    src=_sheet(book,"SourceRegistry",["created_at","source_id","source_url","owner_url","original_price_thb","original_description","availability","channels_json","lots_json","message_ids_json","status","notes"])
    own=_sheet(book,"OwnersAvailability",["checked_at","source_id","owner","source_url","owner_url","availability","owner_price_thb","deposit","utilities","reservation","status","notes"])
    sr=src.get_all_values(); ora=own.get_all_values()
    si={r[1]:i for i,r in enumerate(sr[1:],2) if len(r)>1}; oi={r[1]:i for i,r in enumerate(ora[1:],2) if len(r)>1}
    x=ITEM
    notes=json.dumps({
      "district":x["district"],"type":x["type"],"bedrooms":x["bedrooms"],"bathrooms":x["bathrooms"],"pool":x["pool"],
      "minimum_stay":x["minimum_stay"],"restrictions":x["restrictions"],"contact_internal":x["contact"],"last_checked":now,
      "contact_status":"not_sent_noninteractive_browser_action_requires_confirmation",
      "dedupe_note":"Same PF Pool Villa complex as facebook_marketplace_1740140500658750, but different seller, price and entirely different photo set; retained as a distinct unit.",
      "scan_exclusions":EXCLUSIONS
    },ensure_ascii=False)
    row=[now,x["source_id"],x["source_url"],x["owner_url"],x["price"],x["original_text"],x["availability"],"[]","{}","{}","new_needs_owner_reply",notes]
    added=[]; updated=[]
    if x["source_id"] in si:
        src.update(f"A{si[x['source_id']]}:L{si[x['source_id']]}",[row],value_input_option="RAW"); updated.append(x["source_id"])
    else:
        src.append_row(row,value_input_option="RAW"); added.append(x["source_id"])
    onotes=json.dumps({
      "district":x["district"],"type":x["type"],"bedrooms":x["bedrooms"],"bathrooms":x["bathrooms"],"pool":x["pool"],
      "restrictions":x["restrictions"],"original_listing_text":x["original_text"],"ru_summary":"Отдельный дом с 1 спальней в PF Pool Villa, Чавенг; общий бассейн; заявлено свободно сейчас.",
      "original_message":None,"translation_ru":None,"free_periods":x["availability"],"occupied_periods":"not provided",
      "seasonal_prices":x["minimum_stay"],"minimum_stay":x["minimum_stay"],
      "booking_terms":"Exact September-November and December-January dates, 6-11 month rate, advance, payment method/deadline, cancellation and booking point require owner confirmation",
      "last_reply":None,"conversation_url":None,"contact_internal":x["contact"],"last_checked":now
    },ensure_ascii=False)
    orow=[now,x["source_id"],x["owner"],x["source_url"],x["owner_url"],x["availability"],x["price"],x["deposit"],x["utilities"],"Advance/payment method, cancellation and booking point require owner confirmation","awaiting_contact",onotes]
    if x["source_id"] in oi: own.update(f"A{oi[x['source_id']]}:L{oi[x['source_id']]}",[orow],value_input_option="RAW")
    else: own.append_row(orow,value_input_option="RAW")
    result={"enabled":True,"added":added,"updated":updated,"count":1,"bedrooms":{"1":1,"2":0,"3":0},"exclusions":EXCLUSIONS}
    log.info("RECORD_FB_SCAN_20260830_MORNING_DONE %s",json.dumps(result,ensure_ascii=False))
    return result

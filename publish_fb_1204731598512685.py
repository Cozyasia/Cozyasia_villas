# -*- coding: utf-8 -*-
"""One-shot Telethon publication for Facebook Marketplace item 1204731598512685."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import tempfile
from pathlib import Path

import requests

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-fb-1204731598512685")
SOURCE_ID = "facebook_marketplace_1204731598512685"
SOURCE_URL = "https://www.facebook.com/marketplace/item/1204731598512685/"
DRIVE_URL = "https://drive.google.com/drive/u/1/folders/1p9XtpDiTWLy4UPzDI8dHcVD9LgW7xLZz"
CHANNELS = ("samuirental", "arenda_vill_samui")
PHOTOS = (
    "https://scontent-den2-1.xx.fbcdn.net/v/t39.84726-6/768667766_904459872732617_7820206241365710132_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=107&ccb=1-7&_nc_sid=92e707&_nc_ohc=sd3zTAJ0p10Q7kNvwHawkoT&_nc_oc=Adq6kVbBcWakAsibcn9NML1co1feeex9USJvTNdOSEQgqKBo5E22QI5VOC_tyxjSJEy4Gd03lI4-hcIDc3WPGJiz&_nc_zt=14&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQPQQjpKzj5xVQlGSHWXU0i0Ln8re-_N355IR0I623JKqw&oe=6ADEC54B",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/766184451_1617523223223738_6568654579475004443_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=103&ccb=1-7&_nc_sid=247b10&_nc_ohc=R_RaYWeK98kQ7kNvwH2d7zW&_nc_oc=AdrJrT6641TSr-ZWlPL1W3TPnX-GpQ7Vg53FoPQ1U4Y_a9ZirhpIJL2VQbpnmKOHNmk6aGoLyVoDVRSAseSRPTmc&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQP9GyDXHYjX_TbViFWoo3Xr3bfFl-ZchgYnEDDCy22ReQ&oe=6ADEDE68",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/773189159_1756337755504702_5099215269902126823_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=106&ccb=1-7&_nc_sid=247b10&_nc_ohc=e9dxrQGFj9oQ7kNvwEmpHCY&_nc_oc=Adp5SpGZWzrlewnyFNCSGLT4NacLcOysKTqD82TY2xNX5d5dajxLVQrBy0yZo9-IULC-a7-ILQL-2l7Ob9MY8Wl7&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQMbTP9ZyH1XmF-jL5UJuwRA-DkjEDJj45JoJmqNgcx75Q&oe=6ADEECCF",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/773066890_2623193488138498_7477955279504564715_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=103&ccb=1-7&_nc_sid=247b10&_nc_ohc=N1Wt9JiZvwAQ7kNvwFW4FR6&_nc_oc=AdpbqwZu7rJks9tfxaZNLlszvlPY68bQbkmLhxE1EbsUybgv8gA9c_5CekR377VSG6ZLiExjuaODhhh0-qddBQQf&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQP-FdLye3HQLpefeVtyLdtxkNle-bsazNfTx9zGCVK4UA&oe=6ADEBD3A",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/769459670_1959258461449971_8438776538421391740_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=111&ccb=1-7&_nc_sid=247b10&_nc_ohc=d4mWKDug6P4Q7kNvwHw2fOu&_nc_oc=AdociQx2xHYIyMMcT7GoDUrJiJIbBc0ZzjWlyWb72oSgQRbnT4PCoiQEO1djH5E1clOTBVla1XoCELXmaxMfJ3lG&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQOWGnfQGe-Njd4GDUHyxJWbdMxmQV7jeS5CZxdi4C-H3A&oe=6ADEDBDE",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/773074929_1379626497458837_4571925318837449997_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=102&ccb=1-7&_nc_sid=247b10&_nc_ohc=H6931uzZNjQQ7kNvwFc2JXI&_nc_oc=AdrKzD0zz-uZl8NEAu4B-RaKOGLwNDsClsmAdbsU8FI77tPt2BHlPQyXCaLjfDlNCA8HqX2ll-XsYATcBxuEuckL&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQMJlgmxdZ3aoJn8CqpgHn2xt9atBsiiDqrAYMrbB4o2Jg&oe=6ADEC074",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/773067226_1326825582621557_730829977385398200_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=106&ccb=1-7&_nc_sid=247b10&_nc_ohc=44KZ9sf38koQ7kNvwH4_Vw-&_nc_oc=Adpr_s_pYcfPNYrei6PlJzgPkkmbTz6LciLsoCt3by584wNFg3rXsZEQsosNrAp5t60AQj2ghJMrJKhjF6Z8yXEe&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQMs3JzWvuknS44Hyc9yLDgen6kjvocT91EEwyHEPhEKNQ&oe=6ADEE2F1",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/765188610_1059137999844380_1845833367539753936_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=111&ccb=1-7&_nc_sid=247b10&_nc_ohc=R0lw8-ciXQgQ7kNvwH2dX7A&_nc_oc=AdqpGTfFgnBdIF6umhkIObrly2RpgPcze-HkLk1WE3ApnQY_Qg7dqSsEaaWulb8RmKMw2bpowzMwTipkHL_D65md&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQMejQiKCQyulS4ZG4BoySBb00EF7iFakdQNnJk2S_T74Q&oe=6ADECD4B",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/773233805_1596665548621842_7203974048161363668_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=108&ccb=1-7&_nc_sid=247b10&_nc_ohc=c0VXQicZ2SkQ7kNvwE12Cuh&_nc_oc=AdoKkmFf03roLjiTs_lwe28EVRvAII5DdhbaWLcwHYWnDC_vDkhcfStCqQesduDj4xZNCEFUpIES9Jg3PFyxy8nK&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQONWDs1D_b5SZ_aBhmufdTWctZExAOyQ1fasG2QX4n4dQ&oe=6ADEED78",
    "https://scontent-den2-1.xx.fbcdn.net/v/t45.5328-4/773273093_1777078476639536_4160679874876614998_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=110&ccb=1-7&_nc_sid=247b10&_nc_ohc=aqHXTMjGl30Q7kNvwHs0Ca2&_nc_oc=Ado37kQCMDgC0byz-56WhHM2NK4Omvm_bNRmHgkJbda-6z4eRMe9rVB1aAfoC7CzJ0m0W13AEDawQoJoo-bNLeut&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=88SCV1QYpFTastp3tU3d0w&_nc_ss=722a8&oh=00_AQOimEMGxv2dWLNX-5qVbm0C1WtWFMUH5dLsfZyPLYsmmg&oe=6ADEC135",
)

def _caption_html(lot: str, channel: str) -> str:
    rent_url = channel_publication_policy.bot_url(channel, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(channel, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современный дом в тихом и безопасном районе Huathanon на юге Самуи. Просторная гостиная с открытой кухней, 2 спальни, 2 санузла, приватный бассейн и терраса. До пляжей Ламаи, ресторанов и международных школ — около 10 минут на машине.</blockquote>

📍 Район: Huathanon, Koh Samui
🗺 <a href="https://www.google.com/maps/search/?api=1&amp;query=Huathanon+Koh+Samui"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: дом
🛏 Спальни: 2
🛁 Ванные: 2
🏊 Бассейн: приватный
🐾 Питомцы: уточняется

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 65 000 THB/мес — при контракте 12 месяцев
🤝 Комиссия Cozy Asia: 5 000 THB
🔐 Депозит: уточняется
📅 Доступность: свободен сейчас
⚡ Электричество: уточняется
💧 Вода: уточняется

✨ Терраса · открытая кухня-гостиная · тихий безопасный район
📸 <a href="{DRIVE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Huathanon #KohSamuiRental #CozyAsia"""

def _final_caption(lot: str, channel: str):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(lot, channel))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    channel_publication_policy.validate_listing_caption(text, entities, lot, channel)
    if channel == "samuirental":
        publication_safety.validate_premium_caption(text, entities, lot)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities

def _download_photos(directory: str) -> list[str]:
    photo_dir = Path(directory) / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.facebook.com/"}
    paths = []
    for index, url in enumerate(PHOTOS, start=1):
        response = requests.get(url, headers=headers, timeout=90)
        response.raise_for_status()
        target = photo_dir / f"{index:02d}.jpg"
        target.write_bytes(response.content)
        if target.stat().st_size < 10_000:
            raise RuntimeError(f"Marketplace photo {index} is unexpectedly small")
        paths.append(str(target))
    return paths

async def _latest_lot(client, channel):
    entity = await client.get_entity(channel)
    async for msg in client.iter_messages(entity, limit=300):
        lot = publication_safety.lot_from_message(msg)
        if channel == "arenda_vill_samui" and re.fullmatch(r"\d{1,2}-\d{3,7}", lot):
            return lot
        if channel == "samuirental" and re.fullmatch(r"\d{3,7}", lot):
            return lot
    return ""

def _next_lot(previous: str, channel: str) -> str:
    if channel == "arenda_vill_samui":
        match = re.fullmatch(r"(\d{1,2})-(\d{3,7})", previous)
        if not match:
            raise RuntimeError(f"Unexpected small-channel lot format: {previous!r}")
        return f"{match.group(1)}-{int(match.group(2)) + 1}"
    return str(int(previous) + 1)

async def _existing(client, channel: str):
    entity = await client.get_entity(channel)
    async for msg in client.iter_messages(entity, limit=300):
        text = (getattr(msg, "message", None) or "").lower()
        if all(term in text for term in ("huathanon", "65 000", "2 спальни", "приватный")):
            return msg
    return None

def _verify_message(msg, lot: str, channel: str):
    live = getattr(msg, "message", None) or ""
    decoded = publication_safety.lot_from_message(msg)
    if decoded != lot:
        raise RuntimeError(f"Read-back lot mismatch: expected {lot}, got {decoded}")
    for signature in ("Huathanon", "65 000", "5 000", "Оператор: @cozy_asia"):
        if signature not in live:
            raise RuntimeError(f"Read-back signature missing: {signature}")
    if DRIVE_URL not in live:
        raise RuntimeError("Read-back Drive gallery link missing")
    if "Jerome" in live or "+66 92 574 7876" in live or "facebook.com/marketplace" in live:
        raise RuntimeError("Private owner/source data leaked into public caption")
    channel_publication_policy.validate_listing_caption(live, getattr(msg, "entities", None) or [], lot, channel)

async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    results = []
    try:
        for channel in CHANNELS:
            existing = await _existing(client, channel)
            if existing:
                verify = existing
                lot = publication_safety.lot_from_message(existing)
                result = "already"
                album_count = 10
            else:
                previous = await _latest_lot(client, channel)
                if not previous:
                    raise RuntimeError(f"Could not determine previous lot in @{channel}")
                lot = _next_lot(previous, channel)
                if channel == "samuirental":
                    await publication_safety.assert_next_lot(client, await client.get_entity(channel), lot)
                text, entities = _final_caption(lot, channel)
                with tempfile.TemporaryDirectory(prefix="fb-1204731598512685-") as directory:
                    photos = await asyncio.to_thread(_download_photos, directory)
                    sent = await client.send_file(
                        await client.get_entity(channel), photos, caption=text,
                        formatting_entities=entities, link_preview=False,
                    )
                messages = sent if isinstance(sent, list) else [sent]
                if len(messages) != 10:
                    raise RuntimeError(f"Expected 10 album messages in @{channel}, got {len(messages)}")
                group_ids = {int(getattr(m, "grouped_id", 0) or 0) for m in messages}
                if len(group_ids) != 1 or 0 in group_ids:
                    raise RuntimeError(f"Album grouping invalid in @{channel}: {group_ids}")
                verify = next((m for m in messages if getattr(m, "message", None)), messages[0])
                verify = await client.get_messages(await client.get_entity(channel), ids=int(verify.id))
                result = "published"
                album_count = len(messages)
            _verify_message(verify, lot, channel)
            item = {"channel": channel, "lot": lot, "message_id": int(verify.id),
                    "telegram_url": f"https://t.me/{channel}/{verify.id}",
                    "result": result, "photos": album_count}
            results.append(item)
            log.info("PUBLISH_FB_1204731598512685_ITEM %s", json.dumps(item, ensure_ascii=False))
            await asyncio.sleep(2)
        final = {"source": SOURCE_ID, "source_url": SOURCE_URL, "results": results}
        log.info("PUBLISH_FB_1204731598512685_DONE %s", json.dumps(final, ensure_ascii=False))
        return final
    finally:
        await client.disconnect()

def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    print("PUBLISH_FB_1204731598512685_RESULT=" + json.dumps(asyncio.run(run()), ensure_ascii=False))

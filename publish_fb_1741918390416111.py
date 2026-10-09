# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 1741918390416111."""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path

import requests

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety


log = logging.getLogger("publish-fb-1741918390416111")
SOURCE_ID = "facebook_marketplace_1741918390416111"
SOURCE_URL = "https://www.facebook.com/marketplace/item/1741918390416111/"
CHANNEL = "arenda_vill_samui"
SMALL_CHANNEL_URL = "https://t.me/arenda_vill_samui"
MAP_URL = "https://www.google.com/maps/search/?api=1&query=The+Seasons+Bangrak+Sanam+Bin+Koh+Samui"

PHOTO_URLS = (
    "https://scontent-dfw5-2.xx.fbcdn.net/v/t39.30808-6/823829399_1791222572190300_8329224611902979449_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=107&ccb=1-7&_nc_sid=454cf4&_nc_ohc=gbRdw0I3JL8Q7kNvwET67eJ&_nc_oc=AdqW0FMBdqbddwQUMoES-3TY-t02vO3m0L-fup5uWy5N0R5yGIpSN30XqyMi_FNFqLftRS-b6KLCizn3XFeR83qz&_nc_zt=23&_nc_ht=scontent-dfw5-2.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQOiJvAH3Cyz9SAzSTHgfRZMnObxNR8--88YoMXBSSVEOg&oe=6ACE93CA",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/814691762_1791216542190903_7816206761345849386_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=108&ccb=1-7&_nc_sid=946e27&_nc_ohc=obsfw_j-EIUQ7kNvwHRZwBx&_nc_oc=Ado7irUhNoZ1W90MdLpcLipAPdXgMSdikxQshEaTVY_koma7u_NTqGTaS3yTmXoNHyYV1NPA6avWay9KWnUdhEyI&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQPQg7_s9yfCSOjtZ_S-ontYuiHTRuCdsIR1KoUoV-bh1g&oe=6ACEA5BA",
    "https://scontent-dfw6-1.xx.fbcdn.net/v/t39.30808-6/800780366_1791216378857586_3015690601221687487_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=101&ccb=1-7&_nc_sid=946e27&_nc_ohc=dy2Qv124CT8Q7kNvwENcXoJ&_nc_oc=AdqzgPtv6WUXnCDeLLoTNeclp394aKfiyPkx6EafE7B2nKPWoiqR8XlBV6FtuY5ZdpzLNcWx94qHket8rFT5V2KM&_nc_zt=23&_nc_ht=scontent-dfw6-1.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQOAR0hVyMwcJfxN3vUYCLDWxiYdxQbsD1e_Mmevgckkjg&oe=6ACE8FEF",
    "https://scontent-dfw6-1.xx.fbcdn.net/v/t39.30808-6/799868346_1791216262190931_522749991216573829_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=s9HUjhDwBZAQ7kNvwHwljXp&_nc_oc=Adrgz1PvERYxKH2tAjIyO_oqvAHxEAJ3yb2OUHSMjGu7b1Io5Bu7lFjW2Qn506qBO5IFxuj9OSqbWBLLH2nDDueS&_nc_zt=23&_nc_ht=scontent-dfw6-1.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQNXS2nRAnMttl3rk1wV5XdnncFCIGI1Zjw_2UqK8sz9-g&oe=6ACEABE6",
    "https://scontent-dfw5-1.xx.fbcdn.net/v/t39.30808-6/810051575_1791216418857582_2491680783986718255_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=105&ccb=1-7&_nc_sid=946e27&_nc_ohc=NiaCt_mbI6gQ7kNvwFeNV8z&_nc_oc=AdqkuNkOMDRIZROjVk0vys4nm80aq1eNK2vkFOApHZhobE9AOFJZ-X31zK_ucCPTI5rnVSR44Lxx4LGACsQYTk2I&_nc_zt=23&_nc_ht=scontent-dfw5-1.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQMYU9J1OZxI43zZFBLiDOnTfRLuKTuvTOFz5MsL_CQ2Tw&oe=6ACE9C61",
    "https://scontent-dfw6-1.xx.fbcdn.net/v/t39.30808-6/799839341_1791216562190901_8732185523837168397_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=9CePk6ZLpdkQ7kNvwECZk3k&_nc_oc=Adpln29QP8Xd_McimaUTegrS4OnhhlnlLGTQrkJGkGyd6xBeNatoXjj5HNZRYJJWKQ0lQd4yOD3zEsq-CD5Q-r1f&_nc_zt=23&_nc_ht=scontent-dfw6-1.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQMnGoflFQ6sM97krhQ5QgHr4T7GXbbDYIWP0xU6GaHj9A&oe=6ACE8A55",
    "https://scontent-dfw5-2.xx.fbcdn.net/v/t39.30808-6/819882582_1791216332190924_8745216181299134259_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=104&ccb=1-7&_nc_sid=946e27&_nc_ohc=4c-qwvbKyBsQ7kNvwGndNok&_nc_oc=AdonO_bwPaBwV8U5JwFyQWqnOPpOMEh-8by5PM16pj3jn4i_Kjgnmw6XlN70LTOVYGWEItL-bgn6RYUObSpmMYw-&_nc_zt=23&_nc_ht=scontent-dfw5-2.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQMtTh5EqQI0vd1Ub40BW-nUf9kfl7aOFWe8Uv8BtkwySQ&oe=6ACE9E78",
    "https://scontent-dfw5-2.xx.fbcdn.net/v/t39.30808-6/807797469_1791216522190905_7119466569466600205_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=104&ccb=1-7&_nc_sid=946e27&_nc_ohc=7EgqTYaVmfIQ7kNvwF5Xeuo&_nc_oc=AdoZZ4QzSh16fgQv_dapSZ0q43QZovzJd_X5-saAcKiRupdMt1paf0b15rGuQQeJQ2A7CwwqGvlQoEs9LHNDm2IR&_nc_zt=23&_nc_ht=scontent-dfw5-2.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQOVomDw_DvSwskM9XOZBoJh7KKnNt9LogmltvJl1sLL-A&oe=6ACE7F08",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/800642889_1791216552190902_2308150720918335780_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=110&ccb=1-7&_nc_sid=946e27&_nc_ohc=wUR__C0ph6cQ7kNvwHrqOl3&_nc_oc=Adq2443SKS1UsW5vaBMUd6toEoLQrfVYW7DlIDLWvKdkthNwQhcN_IbJLQHJRO1TyekTzVLbizxNaiWd0T3_lyp8&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQONGw7TSyCe_8Qu4F6cy0TfR9cFQXzArXr3arqL8qJ-MA&oe=6ACE99D7",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/817176678_1791216575524233_4235260169676133304_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=108&ccb=1-7&_nc_sid=946e27&_nc_ohc=7h1Viri2lP4Q7kNvwGHIxWV&_nc_oc=AdoaVa0Z_hkNlqvKWKZD-32puBovOgl74gtwA3T4p7-0Rnk1eKYMGY4AQ88pXiGnSUr9BsHzxcUlDCVf6TRk38PD&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=CyCmTL0v0Og2FStT4FHkHQ&_nc_ss=7c2a8&oh=00_AQMeuw09jcvUxDBxgiQydKjCualOdQ6bJFtOwB7rgnFHJg&oe=6ACE78CD",
)


def _caption_html(lot: str) -> str:
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современный таунхаус в The Seasons Bangrak Sanam Bin — удобный вариант для длительной аренды на Самуи. В комплексе есть общий бассейн и спортзал; рядом аэропорт, рынок Bangrak, Big Buddha, храмы и пляжи северо-восточного побережья.</blockquote>

📍 Район: Банграк, The Seasons
🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: таунхаус
🛏 Спальни: 2
🛁 Ванные: 2
🏊 Бассейн: общий
🏋️ Спортзал: общий
📶 Wi‑Fi: высокоскоростной AIS Fiber — включён
🧺 Стиральная машина
🚗 Парковка
🐾 Питомцы: нельзя

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 50 000 THB/мес — аренда от 6 месяцев
🤝 Комиссия Cozy Asia: 5 000 THB включена в цену
🔐 Депозит: уточняется
📅 Доступность: свободен сейчас
⚡ Электричество: по государственному тарифу
💧 Вода: по тарифу юридического лица
✨ Включено: интернет, общий бассейн, спортзал, вывоз мусора и охрана 24/7

📸 <a href="{SOURCE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>
🏡 <a href="{SMALL_CHANNEL_URL}"><b>БОЛЬШЕ ВИЛЛ — В МАЛОМ КАНАЛЕ</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Банграк #ТаунхаусСамуи #АрендаОт6Месяцев #CozyAsia"""


def _final_caption(lot: str):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    channel_publication_policy.validate_listing_caption(text, entities, lot, CHANNEL)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities


def _download_photos(directory: str) -> list[str]:
    photo_dir = Path(directory) / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.facebook.com/"}
    paths = []
    for index, url in enumerate(PHOTO_URLS, start=1):
        response = requests.get(url, headers=headers, timeout=90)
        response.raise_for_status()
        target = photo_dir / f"{index:02d}.jpg"
        target.write_bytes(response.content)
        if target.stat().st_size < 10_000:
            raise RuntimeError(f"Marketplace photo {index} is unexpectedly small")
        paths.append(str(target))
    return paths


async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("The Seasons", "50 000", "Bangrak", "6 месяцев"), limit=300
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {"channel": CHANNEL, "lot": lot, "message_id": int(duplicate.id), "result": "already", "source": SOURCE_ID}
            log.info("PUBLISH_FB_1741918390416111_DONE %s", json.dumps(result, ensure_ascii=False))
            return {"enabled": True, "result": result}

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine previous live lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)
        text, entities = _final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-1741918390416111-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory)
            sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)
        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        for signature in ("Банграк", "50 000", "5 000", "6 месяцев", SMALL_CHANNEL_URL):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back listing signature missing: {signature}")
        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id), "result": "published", "photos": len(photos), "source": SOURCE_ID}
        log.info("PUBLISH_FB_1741918390416111_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    result = asyncio.run(run())
    print("PUBLISH_FB_1741918390416111_RESULT=" + json.dumps(result, ensure_ascii=False))

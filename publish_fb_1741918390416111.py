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
CHANNEL = "samuirental"
SMALL_CHANNEL_URL = "https://t.me/arenda_vill_samui"
MAP_URL = "https://maps.app.goo.gl/K3ojMKSwZ4zx8HFr8"

PHOTO_URLS = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/823829399_1791222572190300_8329224611902979449_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=107&ccb=1-7&_nc_sid=454cf4&_nc_ohc=u-rEhkXpxxUQ7kNvwGVeNJT&_nc_oc=AdrC5GRp-NnC9ykuYinfxochw0Pm8FpE20o9u4cT5L19djWZoz7aWAgiSmDdNyFMLIthRpGxOcu6WmSk7ZJeDt6p&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQMjxdUwJCEMlrymYAzgKKMUvt8g0b50odeslsbVXTtoKw&oe=6AD67CCA",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/814691762_1791216542190903_7816206761345849386_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=108&ccb=1-7&_nc_sid=946e27&_nc_ohc=2xYmlr0KICQQ7kNvwGW8k7w&_nc_oc=AdrVkVZ5u3KrkA9_r_L9YUerAwngvZk_Hoc4J4EQP1s5YQh_1zuGk0K09Cre4HcrDnkKtxEO22UhF9pV7nFOUlHh&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQNHMpUibIluIwdGyhbv-smdrwtS3bTMzIJn_86k3WHqGQ&oe=6AD68EBA",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/800780366_1791216378857586_3015690601221687487_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=101&ccb=1-7&_nc_sid=946e27&_nc_ohc=27sFUgbcQLwQ7kNvwGe-d18&_nc_oc=AdpJG3fOi8ahgOHVBF6UPt54NqvSXaXL6OXWRvaLaRsCn0dOZ0FQDf5ur2A46oTJjiWpR65z_PY2oCVVukSBDcRA&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQOdZPvbDCa8kE4ZkNSEUCFd2r2eyExhDmchzNVCPB6F8Q&oe=6AD678EF",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/799868346_1791216262190931_522749991216573829_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=KGpU07X67BYQ7kNvwGu6zBy&_nc_oc=Adr3AO3FL5l3by7xZFcvZU-qICiYXjKwmbgBrQGhj8hoBc55_xw9gEnxHoa8PJn-7W6qTbxO8DMoxzy82SutVixm&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQOoGduudp1CGwHJpJRKMujH4VlTnB86zOMLEzwMDM3f1Q&oe=6AD65CA6",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/810051575_1791216418857582_2491680783986718255_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=105&ccb=1-7&_nc_sid=946e27&_nc_ohc=1jjtysiDj-IQ7kNvwGxhAO4&_nc_oc=Adqwq_N7g1pEIMsqPuN301RyZ0gfuVK7uBj0yjWkIuLbQNFKBGQz4J9a_e3xv_q9641A-Fq5VR63gelThD-MKDsI&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQPKzglPahfKnY3vyoYGqGxJQfDtfusxVBGemQ4uYIofcQ&oe=6AD68561",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/799839341_1791216562190901_8732185523837168397_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=weHynKjqEG8Q7kNvwHWouku&_nc_oc=Adrff2G4driAx5-5if79mKuxXDNWi28ZBAEtCpYmnnsaA35jLB39MSrRme53HLC8laAtal3chXFq5-_AUhiDyXgX&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQMCTs_u6prE_NkLDQHsHWCTr4WcZmGS6YHxqvGZ1lEsbQ&oe=6AD67355",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/796968298_1791216595524231_5333357789775488480_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=111&ccb=1-7&_nc_sid=946e27&_nc_ohc=0Mex2Lgd2n4Q7kNvwFSXuU5&_nc_oc=Ado28cDwfufjv77hrUgHoI6V7X1qbERGVDx7jaSU0xk6gCFsgzPnf9q2a1yX8yml14C1TJT0MpGdBUYqBHt8UGvI&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQNfXPk3CfasEuTPFL_2np8I2FujRCBUpOMMfggby7GiGw&oe=6AD66398",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/794646906_1791216588857565_7390204900992596543_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=BIk26X3_zK8Q7kNvwF7Tokr&_nc_oc=AdqXoQsWzXl7H0H2qZK3FS4JAzxZIBqZycVeBAv2I09Flm-ytJ7p8iJmtCgMq_6MxoL0b20J8-V8hWn2jdE7cWlR&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQPl6f4Bhz4BMPAH3dt-A18g9iNlLULaYEUtQjjwAb6a_w&oe=6AD661AD",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/807673272_1791216288857595_5391353195705569220_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=TOWTklrvy50Q7kNvwHVbg3U&_nc_oc=Adrkac9-j0VHOImTerbQlDDVx27wkN1B_i5uXrV8qWVDXDeryy5IujkwE7Txg9D9sAeWGr_T6v_qtHz1GjfaEIz5&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQM7N-D_czjK9Md2CFsQ5icKmJV3OOcBX-G-e8WG2M1wpg&oe=6AD667C9",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/819580868_1791216268857597_3014116215479715819_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=101&ccb=1-7&_nc_sid=946e27&_nc_ohc=yIa-yVkFu4MQ7kNvwFhOUZL&_nc_oc=Adq9H-0OzxLEab4XYGdoKLoWxdvLCwaNdsYtWxF6Q0WSy1i6XDlik7Rd0IBLfWPbeDSZpFXekz3RPp6iXJwGAZ0N&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=Xc7v-oFmmF0Y2PYNEgTL0A&_nc_ss=7c2a8&oh=00_AQO66qn6URlkMOYNPZ5ZEbyIQeJ8jwY8-EJ99Wmji2J2NQ&oe=6AD6874A",
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
🤝 Комиссия Cozy Asia: 4 000 THB
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
        for signature in ("Банграк", "50 000", "4 000", "6 месяцев"):
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

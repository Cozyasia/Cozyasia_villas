# -*- coding: utf-8 -*-
"""One-shot publication of Facebook Marketplace item 3525763387738681."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

import requests

import channel_publication_policy
import cozy_catalog
import mtproto_user_client
import publication_safety


log = logging.getLogger("publish-fb-3525763387738681")
SOURCE_ID = "facebook_marketplace_3525763387738681"
SOURCE_URL = "https://www.facebook.com/marketplace/item/3525763387738681/"
CHANNEL = "samuirental"
BOT_USERNAME = "cozy_asia_bot"
SMALL_CHANNEL_URL = "https://t.me/arenda_vill_samui"
MAP_URL = "https://maps.app.goo.gl/E7FujCNftjVi1ZNN7"

# Ten unique, informative property photos from the public Marketplace gallery.
PHOTO_URLS = (
    "https://scontent-dfw5-1.xx.fbcdn.net/v/t39.30808-6/474099077_485958837880092_4519149082426784269_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=106&ccb=1-7&_nc_sid=946e27&_nc_ohc=sMqp4xuSQZsQ7kNvwHhweOt&_nc_oc=AdpPJxUH_gV_40sPPyRSwg5VFGh0nHCSTFkxFgK-dDhhqhuy2xVtbDYdqy9z3ta96L8jW8n-vDK777mPZnJdMF25&_nc_zt=23&_nc_ht=scontent-dfw5-1.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQOCQ_Mjn7wUmczkK7_BJwjGl-yn5q6779_OhLd_nEPUzQ&oe=6ACE8878",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/474230798_485958554546787_6576186335258513990_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=110&ccb=1-7&_nc_sid=946e27&_nc_ohc=MeIvdXDdsHoQ7kNvwFH4ADW&_nc_oc=Adqm8XsrByXzF9_P1ceIi4bYfwqD97Nz34QPsCbKsayhgyfS-J82bMfMnJ9bRo-vrpnuIKIal9GvGa9SIai2yJE3&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQMvDHmDO7U8X1huGdxmuFau1TOvx2Pb4m0NKmdCDR1Dlw&oe=6ACE7EE9",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/474328512_485958964546746_7009371092839194056_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=110&ccb=1-7&_nc_sid=946e27&_nc_ohc=_loN_mzsW9AQ7kNvwGvdF-K&_nc_oc=AdpqRgWcvHsX0TkbMJ9WziGVXzvyM1V_7eNyjQ1tQj-vWSKVyy3N2VzEf9U5k9aIPZqBVH6OFiyLbAM5vohKsg-N&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQN0hlTpMq93rcmnVOsUAWSnU4ztKo4QVjXKu08WNXCjvg&oe=6ACE8A48",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/473753649_485958857880090_130149658775240885_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=109&ccb=1-7&_nc_sid=946e27&_nc_ohc=k2aeNqgfX7oQ7kNvwHq7lNb&_nc_oc=AdqZmH7CMutLd96XyRSVGFJQIdadP7CADsG-7Udwg6O56Krl_Mlrhv22bfBNjWrRVIJ7_PJBkD9DBY9NbcO3aPy3&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQP19avl-2c-SNi40aR_uS_xkttLVhcjet_p4dTOTLZn2g&oe=6ACE7E28",
    "https://scontent-dfw5-1.xx.fbcdn.net/v/t39.30808-6/474479023_485958641213445_3658633984294519495_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=106&ccb=1-7&_nc_sid=946e27&_nc_ohc=7e3zbcvXiPgQ7kNvwE7llc3&_nc_oc=AdpsGcPaJ0q7R9JnLfBcuR2gnYIscxoJMmp3Dv3bwPdYL4LZmBi7un6tRHofqkGZY0ayrsge-BRy1g8O4r_u-S8x&_nc_zt=23&_nc_ht=scontent-dfw5-1.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQOAm-AkKe_TrVfAV6HpM3iKkCBefX2dHw4IMO0GkMfsjQ&oe=6ACE8175",
    "https://scontent-dfw5-2.xx.fbcdn.net/v/t39.30808-6/474374360_485958704546772_8483658870700587808_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=100&ccb=1-7&_nc_sid=946e27&_nc_ohc=1Vr1VjBvf6YQ7kNvwFxrSLL&_nc_oc=Adrrb6W87xAVAMet1x9ICtviDAeQsbppcS5yABicMzFAcRhr90lRGD0IbMfzNXF0mEnARHqTHBi3Tcp7f6DklchF&_nc_zt=23&_nc_ht=scontent-dfw5-2.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQMq8DTR4X1RIKtTsqDQA72rs8B-qhanz-aOxnLlTOXPLw&oe=6ACE95AB",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/474506168_485958927880083_752848750939644466_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=110&ccb=1-7&_nc_sid=946e27&_nc_ohc=tlMoSqYq9OgQ7kNvwGIVDvs&_nc_oc=AdpB0k_NhNHU7Ih7XIgXoj7OQDXoNRc951ThOxGTUFj_-H3C9uvyhVdZkM-ImoaYZEpcmmKzg2_l9ZLaJjK7ODQS&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQMkxge6FQJtBHmCAbi7QhsGk7avgKOZld3CBaGkkCl3Gg&oe=6ACE8F28",
    "https://scontent-dfw6-1.xx.fbcdn.net/v/t39.30808-6/474507542_485958694546773_1575693933654033034_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=SS7qyhWuwfsQ7kNvwHGzE88&_nc_oc=AdqTycbed3nDjdLxK8psT6zC3FrCPlcftVn9xLklrydrWpsGeo97IwqnIu7g3Y7OFDxQVEcBlRDmDe42zlgH2BWV&_nc_zt=23&_nc_ht=scontent-dfw6-1.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQP2Vj--lji0-UW-oammV0LGUtcyx2YHMt9vcJBSa5ffaQ&oe=6ACE9345",
    "https://scontent-dfw5-1.xx.fbcdn.net/v/t39.30808-6/474063666_485958951213414_2399219882277204953_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=106&ccb=1-7&_nc_sid=946e27&_nc_ohc=8pfroX3tRo0Q7kNvwF3gRR-&_nc_oc=Adqp_5DXk2bQfTtNdp82KM9E25Gw948mrIi4br5wXvm2qZUwtcRyKXdYcpLiGsaFI_8hfn26uQ1MWn1YSECRQkOn&_nc_zt=23&_nc_ht=scontent-dfw5-1.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQNdYy8VJ7Ee9kS1H5FeRwkVuAeZu6N67m_cCQg8o2yokA&oe=6ACE9DE0",
    "https://scontent-dfw6-2.xx.fbcdn.net/v/t39.30808-6/474260076_485958644546778_2336469801098343272_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=108&ccb=1-7&_nc_sid=946e27&_nc_ohc=etTTQEAQXI4Jcqu3-z4595sx9B-5FQGtrAWGnreKff6LH15Ms-pAaZnoN3OJTxclxw2zcnvoiMY4JpUWGwD7mufE&_nc_zt=23&_nc_ht=scontent-dfw6-2.xx&_nc_gid=F3JJ9YszHQeHsk2sP79gPg&_nc_ss=7c2a8&oh=00_AQMf6Tr15g50bAZ_fwjLMOZUxfri9KBCbBmcAPu0PS8K3A&oe=6ACE917B",
)


def _caption_html(lot: str) -> str:
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Современная 2-bedroom вилла с приватным бассейном и джакузи в центре Чавенга. Просторная гостиная, оборудованная кухня, две спальни, две ванные комнаты, Smart TV, Wi‑Fi и парковка. Подходит для пары, семьи или длительного проживания.</blockquote>

📍 Район: Чавенг
🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 2
🏊 Бассейн: приватный, с джакузи
📐 Площадь: 240 м²
🧹 Уборка дома и бассейна: 1 раз в неделю
📶 Wi‑Fi: включён
🚗 Парковка: есть

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 60 000 THB/мес
🔐 Депозит: уточняется
🤝 Комиссия Cozy Asia: 5 000 THB
📅 Доступность: сейчас; возможна посуточная, помесячная и годовая аренда
⚡ Электричество: уточняется
💧 Вода: уточняется
🐾 Питомцы: уточняется

📸 <a href="{SOURCE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>
🏡 <a href="{SMALL_CHANNEL_URL}"><b>БОЛЬШЕ ВИЛЛ — В МАЛОМ КАНАЛЕ</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #Чавенг #ВиллаСамуи #Бассейн #PoolVilla #KohSamuiRental #CozyAsia"""


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
    bundled_dir = Path(__file__).resolve().parent / "publication_assets" / SOURCE_ID
    bundled = sorted(bundled_dir.glob("*.jpg"))
    if len(bundled) < 10:
        raise RuntimeError(f"Bundled Marketplace photo set is incomplete: {bundled_dir}")
    paths = []
    for index, source in enumerate(bundled[:10], start=1):
        target = photo_dir / f"{index:02d}.jpg"
        shutil.copyfile(source, target)
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
            client, channel, ("Чавенг", "60 000", "240 м²", "джакузи"), limit=300
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {"channel": CHANNEL, "lot": lot, "message_id": int(duplicate.id), "result": "already", "source": SOURCE_ID}
            log.info("PUBLISH_FB_3525763387738681_DONE %s", json.dumps(result, ensure_ascii=False))
            return {"enabled": True, "result": result}

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine previous live lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)

        text, entities = _final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-3525763387738681-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory)
            sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)

        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        for signature in ("Чавенг", "60 000", "5 000", SMALL_CHANNEL_URL):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back listing signature missing: {signature}")
        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id), "result": "published", "photos": len(PHOTO_URLS), "source": SOURCE_ID}
        log.info("PUBLISH_FB_3525763387738681_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()


def run_service_mode() -> None:
    result = asyncio.run(run())
    print("PUBLISH_FB_3525763387738681_RESULT=" + json.dumps(result, ensure_ascii=False))


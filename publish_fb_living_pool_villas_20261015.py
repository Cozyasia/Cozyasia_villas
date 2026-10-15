# -*- coding: utf-8 -*-
"""Publish The Living Pool Villas Koh Samui listing from Facebook."""
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

log = logging.getLogger("publish-fb-living-pool-villas")
SOURCE_ID = "facebook_share_1CzgVG657t"
SOURCE_URL = "https://www.facebook.com/TheLivingPoolVillasKohSamui/posts/pfbid02JFHUFP1uf6fLjjt1owZKGWpFNixDN1oFW3UhpRSqXFAEHpP8Z1BfW4puJfpmU3Mdl?rdid=7MUQsRQBcuystaFy"
CHANNEL = "samuirental"
SMALL_CHANNEL_URL = "https://t.me/arenda_vill_samui"
MAP_URL = "https://maps.app.goo.gl/E7FujCNftjVi1ZNN7"

# The first two source images were excluded: one is a person/selfie and one is illustrative.
# These five URLs are the actual property photos from the source post.
PHOTO_URLS = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/600906184_1365131708745984_7279814146317985633_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=111&ccb=1-7&_nc_sid=833d8c&_nc_ohc=rvIutj1dTxkQ7kNvwGywV29&_nc_oc=AdpfhiRGv_6q8FbGoQuHgQfJuxihq2-rNoKfq3SAB7elV41F41U27qxp28EihnPeUaK_UNGN_4xL4bcB7ECJGA42&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=iz1mv_--UdMFfuNlGN21lg&_nc_ss=7c2a8&oh=00_AQMVuj6rX-PBrgWPIWJUcTPQ7uEwY7eSlir3Jn-EOFFvzg&oe=6AD6A4F7",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/598070017_1365132022079286_6347035220067870309_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=8Ws8UONLlDEQ7kNvwF5fXuA&_nc_oc=AdputRDfpziWUjanvTS0QJpGfOqQX5vA-IN4mZ5K5WGP2IGlwmyMzCJBz2L6O6SKSwK4yRutTfFt20PAMTgs-qu&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=iz1mv_--UdMFfuNlGN21lg&_nc_ss=7c2a8&oh=00_AQN_oi8XZjR9dP1ke76uozJU9E0i_izQvugi8SPiCIP_GA&oe=6AD6A62B",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/601977393_1365134828745672_5509892367080032674_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=105&ccb=1-7&_nc_sid=833d8c&_nc_ohc=0Tl8My1zNj0Q7kNvwGIQm9b&_nc_oc=AdrS_lRFD-wheoa91pLMrLILYunu8RSLIXiyGHnZHHHMUW_qsq_bw5f2qWLaPCzO-Zrho8SlsrE6Cq897OKcLADK&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=iz1mv_--UdMFfuNlGN21lg&_nc_ss=7c2a8&oh=00_AQNCdpMiHyaV4RDLHby8LQ3WfjuaYFtr5q9cCPpkI_bfaA&oe=6AD6B3C9",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/597996481_1365134668745688_7622045648775811937_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=Dym_bV-JzU8Q7kNvwEnEY-l&_nc_oc=AdptSPVApKcfpmY3Q5x_H-GfO3yXp3xVBI0KsRmYRDxsiEliTP5_6opkK3e-AihxGXxbviJSGFA0Isg3QRG7Q1Yd&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=iz1mv_--UdMFfuNlGN21lg&_nc_ss=7c2a8&oh=00_AQNukr2RB8BMZBL2UrXW1c_MEMXFi8zKODC2TPMrMzWkeg&oe=6AD68C38",
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.30808-6/600341844_1365132452079243_3054366396884928363_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s590x590&_nc_cat=103&ccb=1-7&_nc_sid=833d8c&_nc_ohc=OUQPRqr6iMUQ7kNvwGZhSl_&_nc_oc=Adqv6p3K3qA3qy2v0k-pu5X2uIUXVyiTZlE3RIoMpxL2e5wYMaCWkyIJ3PhWWLY-g7FodJEKHonqdn10T9U6wfRQ&_nc_zt=23&_nc_ht=scontent-msp1-1.xx&_nc_gid=iz1mv_--UdMFfuNlGN21lg&_nc_ss=7c2a8&oh=00_AQPQEot2-zEC8mLmwpYOYEl7N3fg68H6YIsbPd58f7J0eQ&oe=6AD683AA",
)

def _caption_html(lot: str) -> str:
    rent_url = channel_publication_policy.bot_url(CHANNEL, f"rent_{lot}")
    search_url = channel_publication_policy.bot_url(CHANNEL, "search")
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Двухкомнатная вилла с приватным бассейном и джакузи в районе Чавенг. Подходит для посуточной, помесячной и годовой аренды.</blockquote>

📍 Район: Чавенг, The Living Pool Villas
🗺 <a href="{MAP_URL}"><b>ГЕОЛОКАЦИЯ</b></a>
🏠 Тип: вилла
🛏 Спальни: 2
🛁 Ванные: 2, ванна и горячая вода
🏊 Приватный бассейн с джакузи + общий бассейн отеля
📏 Площадь: 240 м²
❄️ Кондиционеры · 📶 Wi‑Fi · 📺 Smart TV (Netflix/YouTube)
🍳 Полностью оборудованная кухня
🧹 Уборка виллы и бассейна раз в неделю, включая хлорирование
🚗 Парковка · 💧 вода включена
☕ THONG JAN 55 Café & Bar и общая зона отеля

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена: 85 000 THB/мес
🤝 Комиссия Cozy Asia: 5 000 THB
🔐 Депозит: 10 000 THB, возвратный
⚡ Электричество: 8 THB/единица
📅 Доступность: посуточно, помесячно и на год

📸 <a href="{SOURCE_URL}"><b>ДОПОЛНИТЕЛЬНЫЕ ФОТО</b></a>
🏡 <a href="{SMALL_CHANNEL_URL}"><b>БОЛЬШЕ ВАРИАНТОВ — В МАЛОМ КАНАЛЕ</b></a>

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="{rent_url}"><b>ЖМИ ЗДЕСЬ</b></a> 👈


Оператор: @cozy_asia
🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search_url}"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ВиллаСамуи #Чавенг #СнятьВиллуСамуи #CozyAsia"""

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
            raise RuntimeError(f"Facebook photo {index} is unexpectedly small")
        paths.append(str(target))
    return paths

async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("Living Pool", "85 000", "Чавенг", "2 спальни"), limit=300
        )
        if duplicate:
            lot = publication_safety.lot_from_message(duplicate)
            result = {"channel": CHANNEL, "lot": lot, "message_id": int(duplicate.id), "result": "already", "source": SOURCE_ID}
            log.info("PUBLISH_FB_LIVING_POOL_DONE %s", json.dumps(result, ensure_ascii=False))
            return {"enabled": True, "result": result}
        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine previous live lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)
        text, entities = _final_caption(lot)
        with tempfile.TemporaryDirectory(prefix="fb-living-pool-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory)
            sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities, link_preview=False)
        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        for signature in ("Чавенг", "85 000", "5 000", "10 000"):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back listing signature missing: {signature}")
        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id), "result": "published", "photos": len(photos), "source": SOURCE_ID}
        log.info("PUBLISH_FB_LIVING_POOL_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

def run_service_mode() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", force=True)
    result = asyncio.run(run())
    print("PUBLISH_FB_LIVING_POOL_RESULT=" + json.dumps(result, ensure_ascii=False))

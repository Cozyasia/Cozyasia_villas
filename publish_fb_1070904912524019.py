# -*- coding: utf-8 -*-
"""One-shot idempotent publication of Facebook Marketplace item 1070904912524019 to the small channel."""
from __future__ import annotations
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import requests

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-fb-1070904912524019")
SOURCE_ID = "facebook_marketplace_1070904912524019"
SOURCE_URL = "https://www.facebook.com/marketplace/item/1070904912524019/"
OWNER_URL = "https://www.facebook.com/marketplace/profile/100041309793649/?product_id=1070904912524019"
CHANNEL = "arenda_vill_samui"
BOT_USERNAME = "Cozyasia_villa_bot"
PHOTO_URLS = [
"https://scontent-hel3-1.xx.fbcdn.net/v/t39.84726-6/790491630_1970255523683153_1305250495082771070_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=108&ccb=1-7&_nc_sid=92e707&_nc_ohc=a5MnlgdUH2MQ7kNvwEMmPTJ&_nc_oc=AdrTN-TZTYTDLMLXpu1_4K4cpRFBpv-6FKLUTPNwVcMqnd6ROXYNlCJBtEKWW5VROxGKZwFnvcWdNf3WI4WPGBWI&_nc_zt=14&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQKi_okyFqRy0RcgT14HgrlVBYTpHMmFtL3KC3AuzuxXGg&oe=6AB426F1",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/792070745_1814000176303578_4964462588211606744_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=102&ccb=1-7&_nc_sid=247b10&_nc_ohc=P6f0zfpWDJ8Q7kNvwFB2grT&_nc_oc=Adow5VhRN4289RUn8_Sa4BFhxiXQ1jkEJrruBfbm4TpE9_Lzem167xEMKF8BTbCdYAJnXYnA-_m02iGbuguVC_r-&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQJvo7ZBaEJ-c9VzjtSvlF-WxCSxYWSifQmbLwI-9OEoBw&oe=6AB43A3C",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/793142334_2269685757163911_2821466522130286478_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=109&ccb=1-7&_nc_sid=247b10&_nc_ohc=_Yl-ZegzPLQQ7kNvwGn38Hh&_nc_oc=AdqeRW-TQIvJrznS0auFK9Y7oWTQ3-2qvJJ58CkU_Jo99Ee78Iw9ZMhimfq6xN4IgwykpQLwwbStlIgN9aH0F-C5&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQIsvX3qb-qSC_A_d5BgQ3s1quiQoCtvjExyqlAzD51w6w&oe=6AB44AF6",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/793091955_1584587379801123_8637402677759939937_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=101&ccb=1-7&_nc_sid=247b10&_nc_ohc=TpAMkCnPrWQQ7kNvwGJ_Qg4&_nc_oc=Adqwua3-4gQL52g4J9pt5UzEkA1iagprTr7qiDhaejpdNA0Yx4ROgm07Esn45mWSus-m3UmKOLsQNOA5owxElyMi&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQIT_AFpWobYETroj1RSBHqvUUqaNUetEqoggzOzP4YKbg&oe=6AB42A82",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/791960583_1101451572453365_8666913200677222492_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=105&ccb=1-7&_nc_sid=247b10&_nc_ohc=MrE7K7lgr5IQ7kNvwFKcVau&_nc_oc=AdrbRorDcKgYV196Yf_LpvY-zaeXel_FQNBT6QhotrIc4qvlcrXap161HhkqPb5cJl5oV7IL1ENCYeX6Nq4UI_Fs&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQINZ_PWzYwsEFREXqqGgAJr5IRMXoJk7l8PEBR-BSM_QA&oe=6AB44E71",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/792506576_2360014068085886_3973761207602450717_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=110&ccb=1-7&_nc_sid=247b10&_nc_ohc=KieiMIxXgnIQ7kNvwFUCb5Q&_nc_oc=Adp-eJLpSuP7auoW2a0-zAOWislFjBoxANrQm_M7MFULrBd8uxA1_HElhcMeh8j0W_-9bQofqXzFyKe_2hwcHuy8&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQJKqAswe88WOj2A45JJ1oyr9u60Q39zt5NnT3DhQB5gEw&oe=6AB422FC",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/792520901_27488432427499151_4487655602278563859_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=100&ccb=1-7&_nc_sid=247b10&_nc_ohc=UR3KIdglS5QQ7kNvwE1kFpz&_nc_oc=Adqu4XiP98O3KtvUQBytO3Z0yjaSwVTfrQMySLTFJYQt_pxMdHsynb452MVP7MNrSjiFOBwPeXYRrEcNVzqWlCgZ&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQJ6T-OszywwvEAl-GgEhJomKJjbpzfQBjg-jATae27CPQ&oe=6AB43E0D",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/793458033_1458282366137473_4812754660831042359_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=104&ccb=1-7&_nc_sid=247b10&_nc_ohc=uHRju9JhlhcQ7kNvwEMjsER&_nc_oc=AdoJE1qOaAHhcEPVLqQFV4d7hOx6DIgAfHQL83_9_h1DRnU0_Y9aaz6BMjWOhNLZiPOxZIjMg_LuDpblF_t6GzcN&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQL0KnUmSo7298UI4dUdIPUGqERmdXi4YxK5wICGOu9BCQ&oe=6AB425DC",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/789844740_1718744849201289_3855143633966196864_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=108&ccb=1-7&_nc_sid=247b10&_nc_ohc=4W8NUkgTIg0Q7kNvwGLM26T&_nc_oc=AdoPvxNunQLI1U4D112QJeDyRVXDThov_JHbQR85tjbwNGdDEOv4LhUPUEmXQjA1j7x2E_QXu4FpOaDaEKDVSdQH&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQLPEVnKmJPKvM-zuaeWpBC7-zYNzk_vWDdO_BNXQ0HSyg&oe=6AB449E0",
"https://scontent-hel3-1.xx.fbcdn.net/v/t45.5328-4/792120183_1043835028531468_7532497328230728910_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=105&ccb=1-7&_nc_sid=247b10&_nc_ohc=r_ZAJ-lqxC8Q7kNvwHTYXhd&_nc_oc=Adq1r0mVMrlRnlvNdyQ-2Ve11fW3Z0XEcb19XMAzdQwXhpD8okykff_K23YOqEuLGN4iRqzokInvaniGSgWuSFNy&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=zPwTPzDXbvKHvGtLqjzkTw&_nc_ss=7c2a8&oh=00_AQIp2_MkPSqCwoBlAUdLZ1bdQ8sM8wFGHnalTZXuVOebrA&oe=6AB4455C"
]

def _caption_html(lot: str) -> str:
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>Просторная двухэтажная вилла в Чавенг Ной с панорамным видом на море, приватным инфинити-бассейном и большими террасами. Подходит для семьи или компании до 6 гостей.</blockquote>

📍 Район: Чавенг Ной
🏠 Тип: вилла
🛏 Спальни: 3
🛁 Ванные: 4
🏊 Бассейн: приватный инфинити
🌊 Панорамный вид на море
🏖 До пляжа Чавенг Ной: менее 2 км
🚗 Парковка
❄️ Кондиционеры
📶 Высокоскоростной Wi-Fi
🔥 Зона BBQ

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
💵 Цена на новогодний период: 260 000 THB
🤝 Комиссия агентства: 10 000 THB
📅 Доступность: новогодний период 2026/27 — доступна
🔐 Депозит: по запросу
⚡ Электричество и вода: по условиям собственника

✨ Включено: менеджер виллы · уборка 2 раза в неделю · смена белья 1 раз в неделю · охрана 24/7 · Wi-Fi

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>ЖМИ ЗДЕСЬ</b></a> 👈

Оператор: @cozy_asia

🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="https://t.me/{BOT_USERNAME}?start=search"><b>НАПИСАТЬ БОТУ</b></a> 🤖

#АрендаСамуи #ЧавенгНой #ВиллаСамуи #НовыйГодНаСамуи #Бассейн #ВидНаМоре #KohSamuiRental #CozyAsia"""

def _final_caption(lot: str):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities

def _download_photos(directory: str) -> list[str]:
    out = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for i, url in enumerate(PHOTO_URLS, 1):
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        path = Path(directory) / f"{i:02d}.jpg"
        path.write_bytes(response.content)
        out.append(str(path))
    return out

def _update_registry(result: dict) -> None:
    sh = cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    ws = sh.worksheet("SourceRegistry")
    rows = ws.get_all_values()
    for rn, row in enumerate(rows[1:], start=2):
        if len(row) > 1 and row[1] == SOURCE_ID:
            channels = json.dumps([CHANNEL], ensure_ascii=False)
            lots = json.dumps({CHANNEL: result["lot"]}, ensure_ascii=False)
            mids = json.dumps({CHANNEL: result["message_id"]}, ensure_ascii=False)
            ws.update(f"G{rn}:L{rn}", [[
                "Новогодний период 2026/27 — доступна",
                channels, lots, mids, "published",
                "Public price 260000 THB; Cozy Asia commission 10000 THB. Owner Alina Home. Public owner contacts removed."
            ]], value_input_option="RAW")
            return

async def run() -> dict:
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    try:
        channel = await client.get_entity(CHANNEL)
        duplicate = await publication_safety.find_duplicate_listing(
            client, channel, ("260 000", "Чавенг Ной", "инфинити"), limit=300
        )
        if duplicate:
            result = {"channel": CHANNEL, "lot": publication_safety.lot_from_message(duplicate),
                      "message_id": int(duplicate.id), "result": "already"}
            await asyncio.to_thread(_update_registry, result)
            return {"enabled": True, "result": result}

        previous = await publication_safety.latest_numeric_lot(client, channel, limit=300)
        if not previous:
            raise RuntimeError("Could not determine previous live lot")
        lot = str(int(previous) + 1)
        await publication_safety.assert_next_lot(client, channel, lot)
        text, entities = _final_caption(lot)

        with tempfile.TemporaryDirectory(prefix="fb-1070904912524019-") as directory:
            photos = await asyncio.to_thread(_download_photos, directory)
            sent = await client.send_file(
                channel, photos, caption=text, formatting_entities=entities, link_preview=False
            )

        messages = sent if isinstance(sent, list) else [sent]
        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
        verify = await client.get_messages(channel, ids=int(caption_msg.id))
        if publication_safety.lot_from_message(verify) != lot:
            raise RuntimeError("Read-back lot mismatch")
        publication_safety.validate_premium_caption(verify.message, verify.entities, lot)
        for signature in ("260 000", "10 000", "Чавенг Ной", "новогодний период 2026/27"):
            if signature not in (verify.message or ""):
                raise RuntimeError(f"Read-back signature missing: {signature}")
        result = {"channel": CHANNEL, "lot": lot, "message_id": int(caption_msg.id),
                  "result": "published", "photos": len(PHOTO_URLS)}
        await asyncio.to_thread(_update_registry, result)
        log.info("PUBLISH_FB_1070904912524019_DONE %s", json.dumps(result, ensure_ascii=False))
        return {"enabled": True, "result": result}
    finally:
        await client.disconnect()

def start_once() -> None:
    def worker():
        import time
        time.sleep(10)
        try:
            result = asyncio.run(run())
            log.info("PUBLISH_FB_1070904912524019_STARTUP_DONE %s", json.dumps(result, ensure_ascii=False))
        except Exception:
            log.exception("PUBLISH_FB_1070904912524019_STARTUP_FAILED")
    import threading
    threading.Thread(target=worker, name="publish-fb-1070904912524019", daemon=True).start()

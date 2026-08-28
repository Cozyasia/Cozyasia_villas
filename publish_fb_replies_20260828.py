# -*- coding: utf-8 -*-
"""One-shot publication of owner-confirmed Facebook replies from 2026-08-28."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import cozy_catalog
import mtproto_user_client
import publication_safety

log = logging.getLogger("publish-fb-replies-20260828")
BOT_USERNAME = "Cozyasia_villa_bot"

LISTINGS = [
    {
        "source_id": "facebook_marketplace_1684743666202124",
        "source_url": "https://www.facebook.com/marketplace/item/1684743666202124/",
        "owner_url": "https://www.facebook.com/marketplace/profile/1424676909/?product_id=1684743666202124",
        "owner": "Kit Ua-wanapaksa",
        "original_price": "46000",
        "channels": ("samuirental",),
        "duplicate_terms": ("SEASON FIVE", "Банграк", "55 000"),
        "description": "Современный таунхаус SEASON FIVE BANGRAK для долгосрочной аренды. Полностью меблирован, отдельная дополнительная комната с диваном-кроватью, кухня, стиральная машина и частная парковка.",
        "facts": "📍 Район: Банграк\n🏠 Тип: таунхаус, 68 м²\n🛏 Спальня: 1 + дополнительная комната\n🛁 Ванные: 2\n🏊 Бассейн: общий\n🏋️ Тренажёрный зал и охрана 24/7\n🐾 Питомцы: разрешены",
        "terms": "💵 56 000 THB/мес — договор 6 месяцев\n💵 55 000 THB/мес — договор 12 месяцев\n🔐 Депозит: 1 месяц; с питомцем — 2 месяца\n🤝 Комиссия: 5 000 THB\n📅 Доступность: свободен сейчас\n⚡ Электричество: государственный тариф\n💧 Вода: по запросу\n📶 Wi‑Fi: включён",
        "map_url": "https://maps.app.goo.gl/8qKREu9tgTLBs6Wg7?g_st=ipc",
        "notes": "Owner confirmed current availability, 6/12-month rates, deposit, pet deposit, Wi-Fi and government electricity rate on 2026-08-28.",
        "photos": [
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/707693801_10243621009527191_8005504117002410324_n.jpg?stp=dst-jpg_tt6&cstp=mx1080x1620&ctp=s960x960&_nc_cat=100&ccb=1-7&_nc_sid=454cf4&_nc_ohc=NiaGic14qksQ7kNvwFFMdd5&_nc_oc=Adq8Omauv4e-Z2LU982-HfvGX1EaGsD5fOfeCJFDIbRVB9fL020mtWOI9TYd9HNp6wVYSct1AgKMWrjXYJhczltC&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=iK-WdoYa1Ke3rwA_La074Q&_nc_ss=7c2a8&oh=00_AQG6gUHmxYRxlPDReiczJJwxG297h-BGMWrBK7PMcOIGGQ&oe=6A975332",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/682156732_10243188061663765_1185534848046413173_n.jpg?stp=cp6_dst-jpg_tt6&cstp=mx1080x1620&ctp=s960x960&_nc_cat=100&ccb=1-7&_nc_sid=946e27&_nc_ohc=0Od0l6K3QK4Q7kNvwFroA3P&_nc_oc=AdoiE20Ni0K2C87dzEL_tHGE0QwWPJQ_632Ko27iVOk_kWOagALmQtmHV6CxaqzUBUjvPsqS7pHB-Ozgbw4YEqNv&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=iK-WdoYa1Ke3rwA_La074Q&_nc_ss=7c2a8&oh=00_AQGkIBvCMPG1Ao7tHXef6VuIdHXHRDQQDsNDwm0PJ005yQ&oe=6A974714",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/683139387_10243188060223729_3682527210677902521_n.jpg?stp=cp6_dst-jpg_tt6&cstp=mx1080x1620&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=ixrkG-wF4kIQ7kNvwFkGV34&_nc_oc=Adrdjuuy1Trkv7QT2b207ffU1mIjeGnsbFzPkIqE79X7SMu0VBiA_vyuzWs3D7VIxahawsrzh0KX0QPiJkxDrluq&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=iK-WdoYa1Ke3rwA_La074Q&_nc_ss=7c2a8&oh=00_AQGvvrnLX_bCAyz9LE73ybneCaeAJ0eF7w0fhtO6d2EZrw&oe=6A97720B",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/682685462_10243188061703766_1403778978751550911_n.jpg?stp=dst-jpg_tt6&cstp=mx1365x2048&ctp=s960x960&_nc_cat=108&ccb=1-7&_nc_sid=946e27&_nc_ohc=BYEDhZO-in4Q7kNvwFy_ZEA&_nc_oc=AdrFd85rZ50SJ9Nj-uTgfMfFrARSyuhkwGInKw8UIIoZrFM4_240IUU60l1KlUf0Fz_9-VYcip6LcBZ87Bs-MUni&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=iK-WdoYa1Ke3rwA_La074Q&_nc_ss=7c2a8&oh=00_AQFJ5zPptWvdNANsDm1mgNRMlIdHTPbM6szoOJJhLTMnMA&oe=6A976E8B",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/682208423_10243188060903746_8365701035592891475_n.jpg?stp=cp6_dst-jpg_tt6&cstp=mx1477x1108&ctp=s960x960&_nc_cat=105&ccb=1-7&_nc_sid=946e27&_nc_ohc=R8T0L9O8Bj0Q7kNvwHszs7i&_nc_oc=AdrILBRINuCG6gzBGvB-AH9_uGKYvBy6I7K0D4d8rwGsFQ8Qfw_ZNIFw4-9o3F6I7vjfDywf88_pfJ4dUS10khrE&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=iK-WdoYa1Ke3rwA_La074Q&_nc_ss=7c2a8&oh=00_AQEtsJPwU3fez9UEUQb7RhRgMm2Ynmn_A0vcmVbdWt5A2Q&oe=6A97619B",
        ],
    },
    {
        "source_id": "facebook_marketplace_1317783953621260",
        "source_url": "https://www.facebook.com/marketplace/item/1317783953621260/",
        "owner_url": "https://www.facebook.com/marketplace/profile/100000153443361/?product_id=1317783953621260",
        "owner": "Khanit Yingyong",
        "original_price": "30000",
        "channels": ("samuirental",),
        "duplicate_terms": ("Lotus Chaweng", "40 000", "9 THB"),
        "description": "Чистый меблированный дом рядом с Lotus Chaweng: тихая улица, гостиная, оборудованная кухня, бассейн и удобная парковка. До пляжа Чавенг и аэропорта можно быстро добраться.",
        "facts": "📍 Район: Чавенг, рядом с Lotus\n🏠 Тип: дом\n🛏 Спальни: 2\n🛁 Ванные: 2\n🏊 Бассейн: да\n🚗 Парковка: да\n🐾 Питомцы: нельзя",
        "terms": "💵 45 000 THB/мес — аренда на 1–3 месяца\n💵 40 000 THB/мес — аренда на 6–12 месяцев\n🔐 Депозит: 1 месяц\n🤝 Комиссия: 5 000 THB\n📅 Доступность: свободен сейчас\n⚡ Электричество: 9 THB/кВт·ч\n💧 Вода: 200 THB с человека",
        "map_url": "https://maps.google.com/?q=Lotus%27s+Chaweng+Koh+Samui",
        "notes": "Owner confirmed 1/3/6/12-month rates, deposit, water, electricity and reservation by deposit on 2026-08-28.",
        "photos": [
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/713929183_28169484209306650_5086593839031461263_n.jpg?stp=dst-jpg_tt6&cstp=mx1536x2048&ctp=s960x960&_nc_cat=102&ccb=1-7&_nc_sid=454cf4&_nc_ohc=ZBfL0BEq5KEQ7kNvwELDjiC&_nc_oc=AdqQmAnjfLrDYh7rINjliTD2b_jED1LDttBpTGkUuqmaikIS9a7K6orGMFjabK2vehYJT-Jk6SdTMQFgZc0a1yot&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=b5BW4a5xYbk-BOg0LaZbag&_nc_ss=7c2a8&oh=00_AQGOwyYgPwhsBgnigm0or5jJA53sNEFLRrFqfmjrDEAZnw&oe=6A976200",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/687042839_27793990530189355_6067597222620133204_n.jpg?stp=dst-jpg_tt6&cstp=mx1536x2048&ctp=s960x960&_nc_cat=109&ccb=1-7&_nc_sid=946e27&_nc_ohc=MVS_oPSCEksQ7kNvwFoXU2w&_nc_oc=AdpBYnC741y1SomDqkFAr_IqKZxm5X2urIoaDdqIhtdI9kOcXoFEkst85m8BNlFJyKKTdwqzjZSElBT6gqDH-ur2&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=b5BW4a5xYbk-BOg0LaZbag&_nc_ss=7c2a8&oh=00_AQHTWtqD-_PTwRgRCAZMhkZlBJCZHBwy4R6Cidxny0ANew&oe=6A9748C3",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/687773075_27793990516856023_1634295734147705736_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=106&ccb=1-7&_nc_sid=946e27&_nc_ohc=4PChpPOfOxcQ7kNvwGq7V0-&_nc_oc=AdrTTWooU1F28EOlmcAGm0mz5QNKm5wjvyDKLbUOwvs0wecuWKYl5gihG3HiQjKYnR0DoOws1vwE7GMeyZRtCWEC&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=b5BW4a5xYbk-BOg0LaZbag&_nc_ss=7c2a8&oh=00_AQG4AEhy0yCPXtAh-VVm2v-gdn2Ev0kmF2VZKvgHI0oToA&oe=6A974B6A",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/686917726_27793990523522689_7870288755067780079_n.jpg?stp=dst-jpg_tt6&cstp=mx1536x2048&ctp=s960x960&_nc_cat=105&ccb=1-7&_nc_sid=946e27&_nc_ohc=bSmcJLH20kYQ7kNvwG3uZns&_nc_oc=AdqfEDsOjVtn_VJEqpcQ8UAcwrm8iDglXO78J33FEg4xvZ_rfTstNSiELiWRwcT7J57zsftWMY5wn-AXYXV3L48c&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=b5BW4a5xYbk-BOg0LaZbag&_nc_ss=7c2a8&oh=00_AQHP7NspxFMBVmDe_EQjIVZ429VeL_67aqwFxwhExssqvg&oe=6A976FBA",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/687566329_27793989570189451_5341279841280411921_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=101&ccb=1-7&_nc_sid=946e27&_nc_ohc=Ta5b1IrzmRMQ7kNvwGxDCq2&_nc_oc=Adq1jbWLU8fEyXJMDdf8zxzmU82sReFS6wGFlFi1iL_lMGl57CxcuWK8jwhKmwI0PjgrgJqFHPlp6UIVfPGwvXWm&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=b5BW4a5xYbk-BOg0LaZbag&_nc_ss=7c2a8&oh=00_AQFxZIjqflhlBsu_ViaAolQBhktpRX7MFVxqEgf3pBgU-w&oe=6A9775AD",
        ],
    },
    {
        "source_id": "facebook_marketplace_1425759509611301",
        "source_url": "https://www.facebook.com/marketplace/item/1425759509611301/",
        "owner_url": "https://www.facebook.com/marketplace/profile/100005766250301/?product_id=1425759509611301",
        "owner": "Rawadee Salangam",
        "original_price": "25000",
        "channels": ("samuirental",),
        "duplicate_terms": ("Маенам Soi 5", "9–23 сентября", "35 000"),
        "description": "Уютная вилла в тихой резиденции Маенама с приватным бассейном. Полностью меблирована: просторная гостиная, кухня, Smart TV, стиральная машина, три кондиционера и собственная парковка.",
        "facts": "📍 Район: Маенам, Soi 5\n🏠 Тип: вилла, участок 152 м²\n🛏 Спальни: 2\n🛁 Ванные: 2\n🏊 Бассейн: приватный\n🚗 Парковка: частная\n🐾 Питомцы: нельзя",
        "terms": "💵 Цена: 35 000 THB за период 9–23 сентября 2026\n🔐 Депозит: 10 000 THB\n🤝 Комиссия: 5 000 THB\n📅 Другие даты: по запросу\n⚡ Электричество: 6 THB/кВт·ч\n💧 Вода: 1 000 THB\n📶 Wi‑Fi, уборка и обслуживание бассейна включены",
        "map_url": "https://maps.google.com/?q=Maenam+Soi+5+Koh+Samui",
        "notes": "Owner confirmed 9-23 September 2026 for 25,000 THB; electricity 6 THB/unit and water 1,000 THB on 2026-08-28.",
        "photos": [
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/763213555_3309471822588327_4023326023690025799_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=106&ccb=1-7&_nc_sid=454cf4&_nc_ohc=-LyHcRO2bnwQ7kNvwGJqLQw&_nc_oc=AdpKEepU0DoIP0_7_9VQeTy61qe8sR1lV1Q5WLFU3QcHLyBu0sRSdFBH9YfZcpQ_ELOYKC0ZGcu_ciEOOl2wuwOc&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=e0yJNySXuyIsU5qb1djfxA&_nc_ss=7c2a8&oh=00_AQF_cYB73myEAqVS-uCn6gWjcZI9Sfa00eRpZ4YNLYVhnQ&oe=6A97455E",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/766914634_3309467555922087_6632650863430129123_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1536&ctp=s960x960&_nc_cat=101&ccb=1-7&_nc_sid=946e27&_nc_ohc=2Av1MsxZ5zwQ7kNvwHOJqMy&_nc_oc=AdoRUpGY3fqof34NC2BdHzaGbnP7Pu3xTmmRHN9_n3BXBejes9hAMcH9gKf4V3NbIL6fJEYtuI0b5lblmHjv5Uts&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=e0yJNySXuyIsU5qb1djfxA&_nc_ss=7c2a8&oh=00_AQHCS8TfFK7C6yWuU4a0eM3MHhlEAbRW5qPhRotDWDFGMQ&oe=6A976B2D",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/767032090_3309467569255419_1112539661286084093_n.jpg?stp=dst-jpg_tt6&cstp=mx1536x2048&ctp=s960x960&_nc_cat=102&ccb=1-7&_nc_sid=946e27&_nc_ohc=7D6hksqr97cQ7kNvwE7c98p&_nc_oc=Adrf69UlFOw131twMDj5GZFXR4pNOcFN4LU6rLhreYOkGIncYqQE2cMpi5koZ4VMH_5W2paualN0sSHdjVHmhnMZ&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=e0yJNySXuyIsU5qb1djfxA&_nc_ss=7c2a8&oh=00_AQEIXIrAQIe5CdtjmpviWjOTO9W83OhjeOnw-7fibIik2w&oe=6A975914",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/766953004_3309467549255421_7756540000335208243_n.jpg?stp=dst-jpg_tt6&cstp=mx1434x2048&ctp=s960x960&_nc_cat=103&ccb=1-7&_nc_sid=946e27&_nc_ohc=qkxEVWA_nY0Q7kNvwFy5sDg&_nc_oc=AdqJui0wp3t2PjnVWslCL2vFYnQEN5tpFDD95VhpTQ6F4Hv-NRNzuhwlwnt0257xxb2RNlmjIG1PgDonijPeYOj1&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=e0yJNySXuyIsU5qb1djfxA&_nc_ss=7c2a8&oh=00_AQFlhxm_4yhyp9wr0QGhO8O1nPokg21XJtgb9fClksyqvQ&oe=6A976DA0",
            "https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/764907060_3309467592588750_7244715512427861517_n.jpg?stp=dst-jpg_tt6&cstp=mx1536x2048&ctp=s960x960&_nc_cat=102&ccb=1-7&_nc_sid=946e27&_nc_ohc=EQ0OVBRxh4EQ7kNvwF6zdg0&_nc_oc=AdoGTZLWRDQtVNWeywUyE684H5YlFUqmfSZQ4atAL4UF4cRAUDnVX1Hv2Y0DHt9z3fjHfK-F1IgAXHAem8WmSHGh&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=e0yJNySXuyIsU5qb1djfxA&_nc_ss=7c2a8&oh=00_AQFVvRdk9sm1k1B_6cVZpWJ7XQ_tVxmJGKngAGQwf4Tr_w&oe=6A9768AA",
        ],
    },
    {
        "source_id": "facebook_marketplace_1709916616744641",
        "source_url": "https://www.facebook.com/marketplace/item/1709916616744641/",
        "owner_url": "https://www.facebook.com/marketplace/item/1709916616744641/#seller",
        "owner": "Natty Natty",
        "original_price": "40000",
        "channels": ("samuirental", "arenda_vill_samui"),
        "duplicate_terms": ("вилла на возвышенности", "9–23 сентября", "50 000"),
        "description": "Эффектная вилла на возвышенности с красивым открытым видом. Подходит для короткого отдыха: две спальни, два санузла и приватная атмосфера.",
        "facts": "📍 Район: Ко Самуи, точная локация по запросу\n🏠 Тип: вилла на возвышенности\n🛏 Спальни: 2\n🛁 Ванные: 2\n🌅 Панорамный вид\n🐾 Питомцы: по запросу",
        "terms": "💵 Цена: 50 000 THB за период 9–23 сентября 2026\n🔐 Депозит: по запросу\n🤝 Комиссия: 5 000 THB\n📅 Другие даты: по запросу\n⚡ Коммунальные платежи: по запросу",
        "map_url": "https://maps.google.com/?q=Koh+Samui",
        "notes": "Owner confirmed 9-23 September 2026 for 40,000 THB on 2026-08-28. High-season owner price discussed at 100,000-120,000 THB; 90,000 THB may be negotiable.",
        "photos": ["https://scontent-hel3-1.xx.fbcdn.net/v/t39.30808-6/778835543_122301029726024030_4824280670956326806_n.jpg?stp=dst-jpg_tt6&cstp=mx2048x1537&ctp=s960x960&_nc_cat=108&ccb=1-7&_nc_sid=454cf4&_nc_ohc=EB4vEyZf2ecQ7kNvwFgdE-2&_nc_oc=AdqDGtD__jrCTNdgIxSmWb6YlktA9zfzurrIpRdLaYeERkLnJypyAfu3lsX1LrrCuKd-IN085sgFTjJdwmPpNF0V&_nc_zt=23&_nc_ht=scontent-hel3-1.xx&_nc_gid=Rh1ECLOE_H0ijgtzFXrtNg&_nc_ss=7c2a8&oh=00_AQEia6Dh8-3LNxlSZ1hqrO51OJoD9aevoO5r5cubszT4cw&oe=6A977267"],
    },
]


def enabled():
    return os.getenv("PUBLISH_FB_REPLIES_20260828", "0").strip().lower() in {"1", "true", "yes", "on"}


def _caption_html(item, lot):
    return f"""🏡 <b>ЛОТ №{lot}</b>

💬 <b>ОПИСАНИЕ</b>
<blockquote>{item['description']}</blockquote>

{item['facts']}
🗺 <a href="{item['map_url']}"><b>ГЕОЛОКАЦИЯ</b></a>

💰 <b>УСЛОВИЯ АРЕНДЫ</b>
{item['terms']}

📝 <b>ОСТАВИТЬ ЗАЯВКУ</b>
👉 <a href="https://t.me/{BOT_USERNAME}?start=rent_{lot}"><b>НАПИСАТЬ БОТУ</b></a> 👈

#АрендаСамуи #ВиллаСамуи #ДомСамуи #KohSamuiRental #CozyAsia"""


def _final_caption(item, lot):
    from telethon.extensions import html as telethon_html
    text, entities = telethon_html.parse(_caption_html(item, lot))
    text, entities, changed = mtproto_user_client.upgrade_text(text, entities, lot)
    if not changed:
        raise RuntimeError("Premium conversion failed")
    publication_safety.validate_premium_caption(text, entities, lot)
    if len(text) > 1024:
        raise RuntimeError(f"Album caption too long: {len(text)}")
    return text, entities


def _download_photos(item, root):
    out = []
    for idx, url in enumerate(item["photos"], 1):
        path = Path(root) / f"{item['source_id']}_{idx:02d}.jpg"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as src, path.open("wb") as dst:
            dst.write(src.read())
        if path.stat().st_size < 10_000:
            raise RuntimeError(f"Downloaded image is too small: {path}")
        out.append(str(path))
    return out


def _store_source(item, results):
    sh = cozy_catalog._client().open_by_key(cozy_catalog.SHEET_ID)
    try:
        ws = sh.worksheet("SourceRegistry")
    except Exception:
        ws = sh.add_worksheet(title="SourceRegistry", rows=500, cols=12)
        ws.append_row(["created_at", "source_id", "source_url", "owner_url", "original_price_thb", "original_description", "availability", "channels_json", "lots_json", "message_ids_json", "status", "notes"], value_input_option="RAW")
    if not any(len(r) > 1 and r[1] == item["source_id"] for r in ws.get_all_values()[1:]):
        ws.append_row([
            datetime.now(timezone.utc).isoformat(timespec="seconds"), item["source_id"], item["source_url"], item["owner_url"], item["original_price"],
            item["description"], "Confirmed by owner 2026-08-28", json.dumps([r["channel"] for r in results], ensure_ascii=False),
            json.dumps({r["channel"]: r["lot"] for r in results}, ensure_ascii=False), json.dumps({r["channel"]: r["message_id"] for r in results}, ensure_ascii=False),
            "published", item["owner"] + ". " + item["notes"],
        ], value_input_option="RAW")
    try:
        av = sh.worksheet("OwnersAvailability")
    except Exception:
        av = sh.add_worksheet(title="OwnersAvailability", rows=500, cols=12)
        av.append_row(["checked_at", "source_id", "owner", "source_url", "owner_url", "availability", "owner_price_thb", "deposit", "utilities", "reservation", "status", "notes"], value_input_option="RAW")
    if not any(len(r) > 1 and r[1] == item["source_id"] for r in av.get_all_values()[1:]):
        av.append_row([datetime.now(timezone.utc).isoformat(timespec="seconds"), item["source_id"], item["owner"], item["source_url"], item["owner_url"], "Confirmed 2026-08-28", item["original_price"], "See publication/source reply", "See publication/source reply", "Deposit / owner confirmation", "published", item["notes"]], value_input_option="RAW")


async def run():
    if not enabled():
        return {"enabled": False}
    client = await mtproto_user_client._new_client(cozy_catalog)
    if not client:
        raise RuntimeError("MTProto Premium session is not authorized")
    published = []
    try:
        with tempfile.TemporaryDirectory(prefix="fb-replies-") as tmp:
            for item in LISTINGS:
                photos = await asyncio.to_thread(_download_photos, item, tmp)
                item_results = []
                for channel_name in item["channels"]:
                    channel = await client.get_entity(channel_name)
                    duplicate = await publication_safety.find_duplicate_listing(client, channel, item["duplicate_terms"], limit=220)
                    if duplicate:
                        result = {"channel": channel_name, "lot": publication_safety.lot_from_message(duplicate), "message_id": int(duplicate.id), "result": "already"}
                    else:
                        previous = await publication_safety.latest_numeric_lot(client, channel, limit=220)
                        if not previous:
                            raise RuntimeError(f"Could not determine latest lot for @{channel_name}")
                        lot = str(int(previous) + 1)
                        await publication_safety.assert_next_lot(client, channel, lot)
                        text, entities = _final_caption(item, lot)
                        sent = await client.send_file(channel, photos, caption=text, formatting_entities=entities)
                        messages = sent if isinstance(sent, list) else [sent]
                        caption_msg = next((m for m in messages if getattr(m, "message", None)), messages[0])
                        verify = await client.get_messages(channel, ids=int(caption_msg.id))
                        if publication_safety.lot_from_message(verify) != lot:
                            raise RuntimeError(f"Read-back lot mismatch in @{channel_name}")
                        result = {"channel": channel_name, "lot": lot, "message_id": int(caption_msg.id), "result": "published"}
                        await asyncio.sleep(2)
                    item_results.append(result)
                    published.append({"source_id": item["source_id"], **result})
                await asyncio.to_thread(_store_source, item, item_results)
        log.info("PUBLISH_FB_REPLIES_20260828_DONE %s", json.dumps(published, ensure_ascii=False))
        return {"enabled": True, "results": published}
    finally:
        await client.disconnect()

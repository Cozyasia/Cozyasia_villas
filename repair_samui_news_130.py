"""One-shot repair of Samui News message 130. Safe to rerun."""
import asyncio
import logging
import cozy_catalog
import mtproto_user_client
from samui_news_automation import _fallback_post_image

log = logging.getLogger("samui-news-repair-130")
CAPTION = ("🚨 <b>Полицейская погоня в Сураттхани: у водителя обнаружили оружие</b>\n\n"
"📍 Район Чайя, провинция Сураттхани.\n\n"
"Полиция задержала водителя, который попытался скрыться от проверки на дороге. "
"После преследования автомобиль съехал с трассы.\n\n"
"🔍 При проверке автомобиля полицейские обнаружили две единицы огнестрельного оружия. "
"Обстоятельства происшествия выясняются.\n\n"
"🌊 Samui News — новости Самуи и юга Таиланда.\n"
"#Сураттхани #Таиланд #Полиция")

async def repair():
    catalog = cozy_catalog.CozyCatalog()
    client = await mtproto_user_client._new_client(catalog)
    if client is None:
        raise RuntimeError("MTProto authorization unavailable")
    try:
        channel = await client.get_entity("samui_news_ru")
        old = await client.get_messages(channel, ids=130)
        if old is None:
            raise RuntimeError("Message 130 not found: no new publication made")
        if "Полицейская погоня в Сураттхани: у водителя обнаружили оружие" in (old.raw_text or ""):
            log.info("SAMUI_NEWS_REPAIR_130_ALREADY_DONE")
            return
        image = _fallback_post_image("ПОЛИЦЕЙСКАЯ ПОГОНЯ В СУРАТТХАНИ", "В районе Чайя задержан водитель. Обнаружены две единицы оружия.")
        await client.edit_message(channel, 130, text=CAPTION, file=image, parse_mode="html")
        log.info("SAMUI_NEWS_REPAIR_130_SUCCESS message=130")
    finally:
        await client.disconnect()

def run_service_mode():
    logging.basicConfig(level=logging.INFO)
    asyncio.run(repair())

# -*- coding: utf-8 -*-
"""Cozy Asia V5 listing layout: one field per line + emoji lot/CTA."""
import html
import re
import post_template_patch as tpl


def _emoji_lot(value):
    s = str(value or "").strip()
    if not s or s == "—":
        return "—"
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(ch + "\ufe0f\u20e3")
        elif ch in {"-", "–", "—"}:
            out.append("➖")
        else:
            out.append(ch)
    return "".join(out)


def apply(mod, throttle):
    # This marker is used by future-post protection and by the resumable migration
    # to distinguish the new V5 layout from the previous compact V4 layout.
    mod.MARKER = "📝✨ ОСТАВИТЬ ЗАЯВКУ"
    throttle.DONE_MARKER = "__STANDARDIZATION_DONE_V5__"
    throttle.OK_PREFIX = "__STD_V5__:"
    throttle.EXC_PREFIX = "__STD_V5_EXCEPTION__:"

    def build_post(row, bot_username, links=None):
        lot = mod._shown(row.get("lot_id"), "—", 30)
        district = mod._shown(row.get("район"))
        typ = mod._shown(row.get("тип"))
        bedrooms = mod._shown(row.get("спальни"), "Не указано", 30)
        bathrooms = mod._shown(row.get("ванные"), "Не указано", 30)
        availability = mod._shown(row.get("доступность"), "Не указано", 70)
        electricity = mod._shown(row.get("электричество"), "Не указано", 55)
        water = mod._shown(row.get("вода"), "Не указано", 55)
        desc = mod._shown(row.get("описание"), "", 230) or "Подробности по объекту уточняйте у менеджера Cozy Asia."
        source = str(row.get("исходный_текст") or "")
        details = tpl._features(source)
        tags = tpl._hashtags(source)
        bot = bot_username.lstrip("@")
        rent = f"https://t.me/{bot}?start=rent_{lot}" if lot != "—" else f"https://t.me/{bot}?start=rent"
        search = f"https://t.me/{bot}?start=search"

        def compose(desc_text, details_text, tags_text):
            lines = [
                f"🏡 <b>ЛОТ №{mod._esc(_emoji_lot(lot))}</b>",
                f"📍 Район: <b>{mod._esc(district)}</b>",
                f"🏠 Тип: {mod._esc(typ)}",
                f"🛏 Спальни: {mod._esc(bedrooms)}",
                f"🛁 Ванные: {mod._esc(bathrooms)}",
                f"🏊 Бассейн: {mod._esc(mod._pool(row))}",
                f"🐾 Питомцы: {mod._esc(mod._yesno(row.get('питомцы')))}",
                "",
                "💰 <b>Условия аренды</b>",
                f"💵 Цена: <b>{mod._esc(mod._price(row))}</b>",
                f"🔐 Депозит: {mod._esc(mod._money(row.get('депозит_thb')))}",
                f"🤝 Комиссия: {mod._esc(mod._money(row.get('комиссия_thb')))}",
                f"📅 Доступность: {mod._esc(availability)}",
                f"⚡ Электричество: {mod._esc(electricity)}",
                f"💧 Вода: {mod._esc(water)}",
                f"🌊 До моря: {mod._esc(mod._distance(row.get('до_моря_м')))}",
                "",
                f"📝 <b>Описание:</b> {mod._esc(desc_text)}",
            ]
            if details_text:
                lines += ["", f"✨ <b>Дополнительно:</b> {mod._esc(details_text)}"]
            for title, href in mod._external_links(links, bot)[:2]:
                lines.append(f'<a href="{html.escape(href, quote=True)}">{mod._esc(title)}</a>')
            if tags_text:
                lines += ["", mod._esc(tags_text)]
            lines += [
                "",
                f'📝✨ <b>ОСТАВИТЬ ЗАЯВКУ — <a href="{rent}">ЖМИ ЗДЕСЬ</a></b> 👇',
                f'🔎🏡 <b>ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{search}">НАПИСАТЬ БОТУ</a></b> 🤖',
            ]
            return "\n".join(lines)

        text = compose(desc, details, tags)
        plain = re.sub(r"<[^>]+>", "", text)
        if len(plain) > 990 and details:
            details = details[:120].rstrip() + "…"
            text = compose(desc, details, tags)
            plain = re.sub(r"<[^>]+>", "", text)
        if len(plain) > 990:
            desc = desc[:110].rstrip() + "…"
            text = compose(desc, details, tags)
            plain = re.sub(r"<[^>]+>", "", text)
        if len(plain) > 990:
            text = compose(desc, details, "")
        return text

    mod.build_post = build_post

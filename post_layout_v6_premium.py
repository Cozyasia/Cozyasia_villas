# -*- coding: utf-8 -*-
"""V6: reproduce the manually captured Cozy Asia visual template with Premium Custom Emoji."""
from __future__ import annotations

import html
import re
import post_template_patch as tpl

# Captured from the owner's reference post @arenda_vill_samui/872.
LOT_IDS = {
    "Л": "5474517911374668774",
    "О": "5449645429346020359",
    "Т": "5442819107110004737",
    "№": "5256029914255076855",
}
DIGIT_IDS = {
    "0": "5393480373944459905",
    "1": "5382322671679708881",
    "2": "5381990043642502553",
    "3": "5381879959335738545",
    "4": "5382054253403577563",
    "5": "5391197405553107640",
    "6": "5390966190283694453",
    "7": "5382132232829804982",
    "8": "5391038994274329680",
    "9": "5391234698754138414",
    "-": "5382261056078881010",
}
CTA_IDS = {
    "О": "5449645429346020359",
    "С": "5463032576119679082",
    "Т": "5442819107110004737",
    "А": "5442667851246742007",
    "В": "5449413294953606262",
    "И": "5449768699202381205",
    "Ь": "5472419270094760054",
    "З": "5472327074326786286",
    "Я": "5204256643302303428",
    "К": "5456289915551622074",
    "У": "5188633966051076002",
}
DESC_ID = "5474587738952975936"  # reference Premium 💬
RIGHT_ID = "5471978009449731768"  # reference Premium 👉
LEFT_ID = "5469735272017043817"   # reference Premium 👈


def _tg(cid: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{cid}">{fallback}</tg-emoji>'


def _premium_word(word: str, mapping: dict[str, str]) -> str:
    out = []
    for ch in word:
        if ch == " ":
            out.append(" ")
        elif ch in mapping:
            out.append(_tg(mapping[ch], "🔤"))
        else:
            out.append(html.escape(ch))
    return "".join(out)


def _premium_lot(lot: str) -> str:
    prefix = "".join(_tg(LOT_IDS[ch], "🔤") for ch in "ЛОТ")
    prefix += " " + _tg(LOT_IDS["№"], "🔤") + " "
    rendered = []
    for ch in str(lot or "").strip():
        key = "-" if ch in {"-", "–", "—"} else ch
        cid = DIGIT_IDS.get(key)
        if cid:
            fallback = "➖" if key == "-" else key + "\ufe0f\u20e3"
            rendered.append(_tg(cid, fallback))
        else:
            # Owner suffix is deliberately not invented. If a known suffix is later
            # restored in the catalog it can be mapped separately.
            rendered.append(html.escape(ch))
    return prefix + "".join(rendered)


def _clean_details(value: str) -> str:
    s = re.sub(r"\s+", " ", str(value or "")).strip()
    s = re.sub(r"^(?:✨\s*)?(?:Дополнительно\s*:\s*)+", "", s, flags=re.I)
    return s.strip(" ·")


def apply(mod, throttle):
    mod.RUN_EXISTING = True
    # This marker exists in the captured reference and is absent from V5 posts.
    mod.MARKER = "💬 ОПИСАНИЕ"
    throttle.DONE_MARKER = "__STANDARDIZATION_DONE_V6_PREMIUM__"
    throttle.OK_PREFIX = "__STD_V6_PREMIUM__:"
    throttle.EXC_PREFIX = "__STD_V6_PREMIUM_EXCEPTION__:"

    def build_post(row, bot_username, links=None):
        lot = mod._shown(row.get("lot_id"), "—", 30)
        district = mod._shown(row.get("район"))
        typ = mod._shown(row.get("тип"))
        bedrooms = mod._shown(row.get("спальни"), "Не указано", 30)
        bathrooms = mod._shown(row.get("ванные"), "Не указано", 30)
        availability = mod._shown(row.get("доступность"), "Не указано", 70)
        electricity = mod._shown(row.get("электричество"), "Не указано", 55)
        water = mod._shown(row.get("вода"), "Не указано", 55)
        desc = mod._shown(row.get("описание"), "", 235) or "Подробности по объекту уточняйте у менеджера Cozy Asia."
        source = str(row.get("исходный_текст") or "")
        details = _clean_details(tpl._features(source))
        tags = tpl._hashtags(source)
        bot = bot_username.lstrip("@")
        rent = f"https://t.me/{bot}?start=rent_{lot}" if lot != "—" else f"https://t.me/{bot}?start=rent"
        search = f"https://t.me/{bot}?start=search"

        def compose(desc_text: str, details_text: str, tags_text: str) -> str:
            lines = [
                _premium_lot(lot),
                "",
                f"{_tg(DESC_ID, '💬')} <b>ОПИСАНИЕ</b>",
                f"<blockquote>{mod._esc(desc_text)}</blockquote>",
                "",
                f"📍 Район: {mod._esc(district)}",
                f"🏠 Тип: {mod._esc(typ)}",
                f"🛏 Спальни: {mod._esc(bedrooms)}",
                f"🛁 Ванные: {mod._esc(bathrooms)}",
                f"🏊 Бассейн: {mod._esc(mod._pool(row))}",
                f"🐾 Питомцы: {mod._esc(mod._yesno(row.get('питомцы')))}",
                "",
                "💰 <b>Условия аренды</b>",
                f"💵 Цена: {mod._esc(mod._price(row))}",
                f"🔐 Депозит: {mod._esc(mod._money(row.get('депозит_thb')))}",
                f"🤝 Комиссия: {mod._esc(mod._money(row.get('комиссия_thb')))}",
                f"📅 Доступность: {mod._esc(availability)}",
                f"⚡ Электричество: {mod._esc(electricity)}",
                f"💧 Вода: {mod._esc(water)}",
                f"🌊 До моря: {mod._esc(mod._distance(row.get('до_моря_м')))}",
            ]
            if details_text:
                lines += ["", f"✨ Дополнительно: {mod._esc(details_text)}"]
            for title, href in mod._external_links(links, bot)[:2]:
                lines.append(f'<a href="{html.escape(href, quote=True)}">{mod._esc(title)}</a>')
            if tags_text:
                lines += ["", mod._esc(tags_text)]

            cta1 = _premium_word("ОСТАВИТЬ", CTA_IDS)
            cta2 = _premium_word("ЗАЯВКУ", CTA_IDS)
            right = _tg(RIGHT_ID, "👉")
            left = _tg(LEFT_ID, "👈")
            lines += [
                "",
                cta1,
                cta2,
                "",
                f'{right} <a href="{html.escape(rent, quote=True)}"><b>ЖМИ ЗДЕСЬ</b></a> {left}',
                "",
                f'🔎🏡 ПОДОБРАТЬ ДРУГИЕ ВАРИАНТЫ — <a href="{html.escape(search, quote=True)}"><b>НАПИСАТЬ БОТУ</b></a> 🤖',
            ]
            return "\n".join(lines)

        text = compose(desc, details, tags)
        plain = re.sub(r"<[^>]+>", "", text)
        if len(plain) > 990 and details:
            details = details[:120].rstrip() + "…"
            text = compose(desc, details, tags)
            plain = re.sub(r"<[^>]+>", "", text)
        if len(plain) > 990:
            desc = desc[:135].rstrip() + "…"
            text = compose(desc, details, tags)
            plain = re.sub(r"<[^>]+>", "", text)
        if len(plain) > 990:
            text = compose(desc, details, "")
        return text

    mod.build_post = build_post

# -*- coding: utf-8 -*-
"""Data-quality and search-safety fixes layered over cozy_catalog.

The base catalog module stays untouched.  This patch:
- preserves compound lot IDs such as 1020-1 and 01-1132;
- normalizes common Samui district aliases;
- treats literal "пусто" as an empty extracted value;
- keeps generic search focused on recent inventory;
- supports multi-value bedroom/price fields.
"""
import os
import re
from datetime import datetime, timedelta, timezone


def apply(c):
    original_extract_lot_id = c.extract_lot_id
    original_canonical = c.canonical
    original_parse_query = c.parse_property_query
    original_blank = c._blank
    original_norm_district = c.norm_district

    def blank(v):
        s = str(v or "").strip()
        if s.lower() == "пусто":
            return ""
        return original_blank(v)

    def norm_district(v):
        s = blank(v)
        if not s:
            return ""
        low = re.sub(r"\s+", " ", s.lower().replace("_", " ")).strip()
        exact = {
            "ламаи": "Ламай",
            "ламая": "Ламай",
            "банг рак": "Банграк",
            "банкрак": "Банграк",
            "бо пхут": "Бопхут",
            "май нам": "Маенам",
            "мае нам 2": "Маенам",
            "bong por": "Банг По",
            "талинг нам": "Талинг Нгам",
            "чонгмон": "Чонг Мон",
            "бантай": "Бан Тай",
            "липа-ной": "Липа Ной",
            "huathanon": "Хуа Танон",
            "hua tanon": "Хуа Танон",
            "naton": "Натон",
            "maret": "Ламай",
            "марет": "Ламай",
            "bang-po": "Банг По",
            "bang po": "Банг По",
            "na-muang": "На Муанг",
            "namuang": "На Муанг",
            "на-муанг": "На Муанг",
        }
        if low in {"cozy asia", "тихий"}:
            return ""
        if low in exact:
            return exact[low]
        return original_norm_district(s)

    def _clean_lot_token(token):
        token = re.sub(r"\s+", "", str(token or ""))
        token = token.strip("-")
        if not token:
            return ""
        if "-" in token:
            # Compound IDs are significant: do not collapse 01-1132 into 1132.
            return token
        return token.lstrip("0") or "0"

    def extract_lot_id(text):
        norm = c._digits(text or "")
        lines = [x.strip() for x in norm.splitlines()[:35] if x.strip()]
        head = "\n".join(lines[:18])

        # Explicit textual marker has highest priority.
        m = re.search(
            r"(?i)(?:лот|lot)\s*(?:№|#|no\.?)?\s*[:\-]?\s*"
            r"(\d{1,7}(?:\s*-\s*\d{1,7})?)",
            head,
        )
        if m:
            return _clean_lot_token(m.group(1))

        # Telegram web often splits emoji digits onto separate lines.
        # 1 / 0 / 2 / 0 / - / 1 -> 1020-1
        # 0 / 1 / - / 1 / 1 / 3 / 2 -> 01-1132
        for i, line in enumerate(lines[:18]):
            if line != "-":
                continue
            before = []
            j = i - 1
            while j >= 0 and re.fullmatch(r"\d", lines[j]):
                before.append(lines[j])
                j -= 1
            before = list(reversed(before))

            after = []
            j = i + 1
            while j < len(lines) and re.fullmatch(r"\d", lines[j]):
                after.append(lines[j])
                j += 1

            left = "".join(before)
            right = "".join(after)
            if left == "01" and len(right) >= 3:
                token = f"01-{right}"
                if j < len(lines) and lines[j] == "-":
                    k = j + 1
                    tail = []
                    while k < len(lines) and re.fullmatch(r"\d", lines[k]):
                        tail.append(lines[k])
                        k += 1
                    if tail:
                        token += "-" + "".join(tail)
                return token
            if len(left) >= 3 and 1 <= len(right) <= 3:
                return f"{left.lstrip('0') or '0'}-{right.lstrip('0') or '0'}"

        # Same forms when the digits remain on one line.
        m = re.search(
            r"(?<!\d)(01-\d{3,7}(?:-\d{1,3})?|\d{3,7}-\d{1,3})(?!\d)",
            re.sub(r"\s+", "", head),
        )
        if m:
            return _clean_lot_token(m.group(1))

        return original_extract_lot_id(text)

    def explicit_bathrooms(source):
        t = source or ""
        patterns = [
            r"(?i)(\d+(?:[.,]\d+)?)\s*(?:ванн(?:ая|ые|ых|ой|ую|ыми)?\s*(?:комнат(?:а|ы|ах|ы)?|комнат)?|санузл(?:а|ов|ы)?|bathrooms?\b)",
            r"(?i)(?:ванн(?:ая|ые|ых|ой|ую)?\s*(?:комнат(?:а|ы|ах)?|комнат)?|санузл(?:а|ов|ы)?|bathrooms?\b)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)",
        ]
        for p in patterns:
            m = re.search(p, t)
            if m:
                return m.group(1).replace(".", ",")
        return ""

    def source_pool_type(source):
        low = (source or "").lower()
        if re.search(
            r"(?:инфинити|infinity)[-\s]*(?:бассейн|pool)|(?:бассейн|pool).{0,25}(?:инфинити|infinity)",
            low,
            re.S,
        ):
            return "infinity"
        if re.search(
            r"(?:приватн|частн|собственн).{0,25}(?:бассейн|pool)|(?:бассейн|pool).{0,25}(?:приватн|частн|собственн|private)",
            low,
            re.S,
        ):
            return "private"
        if re.search(
            r"(?:общ(?:ий|его)|shared|communal).{0,25}(?:бассейн|pool)|(?:бассейн|pool).{0,25}(?:общ(?:ий|его)|shared|communal)",
            low,
            re.S,
        ):
            return "shared"
        return ""

    def canonical(rec, source=""):
        out = original_canonical(rec, source)
        if source:
            lot = extract_lot_id(source)
            if lot:
                out["lot_id"] = lot

            baths = explicit_bathrooms(source)
            current = str(out.get("ванные") or "").replace(" ", "")
            try:
                bad = bool(current) and float(current.replace(",", ".")) > 30
            except Exception:
                bad = False
            if baths and (bad or not current or "," in baths):
                out["ванные"] = baths

            pt = source_pool_type(source)
            if pt:
                out["тип_бассейна"] = pt
                out["бассейн"] = "yes"

        out["район"] = norm_district(out.get("район", ""))
        return out

    def parse_property_query(text):
        raw = text or ""
        m = re.search(
            r"(?i)\b(?:лот|lot)\s*(?:№|#)?\s*"
            r"(\d{1,7}(?:\s*-\s*\d{1,7})?)\b",
            raw,
        )
        if m:
            return {"intent": "lot", "lot_id": _clean_lot_token(m.group(1))}
        return original_parse_query(text)

    def _dt(v):
        s = blank(v)
        if not s:
            return None
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            return None

    def _fresh(rows):
        try:
            days = int(os.getenv("CATALOG_MAX_AGE_DAYS", "365") or 365)
        except Exception:
            days = 365
        if days <= 0:
            return list(rows)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent_dated = []
        for r in rows:
            d = _dt(r.get("published_at"))
            mid = c._int(r.get("telegram_message_id"))
            if d is not None and d >= cutoff and mid is not None:
                recent_dated.append(mid)
        fallback_mid = min(recent_dated) if recent_dated else None

        out = []
        for r in rows:
            d = _dt(r.get("published_at"))
            if d is not None:
                if d >= cutoff:
                    out.append(r)
                continue
            mid = c._int(r.get("telegram_message_id"))
            if fallback_mid is not None and mid is not None and mid >= fallback_mid:
                out.append(r)
        return out

    def _bedroom_options(v):
        vals = []
        for x in re.findall(r"\d+(?:[.,]\d+)?", blank(v)):
            try:
                n = float(x.replace(",", "."))
            except Exception:
                continue
            if 0 < n <= 20:
                vals.append(int(n) if n.is_integer() else n)
        return vals

    def _price_options(v):
        vals = []
        for x in re.findall(r"\d+(?:[.,]\d+)?", blank(v)):
            try:
                n = int(float(x.replace(",", ".")))
            except Exception:
                continue
            # Filters out contract-duration keys (1-3 / 3-6 / 6+) from tiered prices.
            if n >= 1000:
                vals.append(n)
        return vals

    def search_catalog(spec, limit=5):
        all_rows = [
            r
            for r in c._latest(c.load_catalog_rows())
            if c.norm_status(r.get("status")) not in {"archived", "rented"}
        ]

        # Direct lot lookup remains available for older inventory.
        if spec.get("intent") == "lot":
            wanted = str(spec.get("lot_id") or "").strip()
            matches = [r for r in all_rows if str(r.get("lot_id") or "").strip() == wanted]
            matches.sort(
                key=lambda r: int(r.get("telegram_message_id") or 0),
                reverse=True,
            )
            return matches[:limit], False

        rows = _fresh(all_rows)
        types = [c.norm_type(x) for x in spec.get("types", []) if c.norm_type(x)]
        districts = [
            c.norm_district(x)
            for x in spec.get("districts", [])
            if c.norm_district(x)
        ]
        try:
            bmin = int(spec["bedrooms_min"]) if spec.get("bedrooms_min") is not None else None
        except Exception:
            bmin = None
        try:
            bmax = int(spec["bedrooms_max"]) if spec.get("bedrooms_max") is not None else None
        except Exception:
            bmax = None

        max_price = c._int(spec.get("max_price_thb"))
        max_dist = c._int(spec.get("max_distance_sea_m"))
        pool = str(spec.get("pool") or "any")
        pets = str(spec.get("pets") or "any")
        district_required = bool(spec.get("district_required", True))

        def score(r, relax=False):
            sc = 0.0
            typ = c.norm_type(r.get("тип"))
            bedrooms = _bedroom_options(r.get("спальни"))
            prices = _price_options(r.get("цена_месяц_thb"))
            price = min(prices) if prices else None
            dist = c._int(r.get("до_моря_м"))
            row_pool = c.norm_pool(r.get("бассейн"))
            row_pets = c.norm_pets(r.get("питомцы"))

            if types:
                if typ not in types:
                    return None
                sc += 4

            if districts:
                ok = c._dmatch(r.get("район", ""), districts)
                if district_required and not relax and not ok:
                    return None
                sc += 5 if ok else -2

            if bmin is not None or bmax is not None:
                if not bedrooms:
                    return None
                good = [
                    b for b in bedrooms
                    if (bmin is None or b >= bmin) and (bmax is None or b <= bmax)
                ]
                if not good:
                    return None
                sc += 4

            if pool == "yes" and row_pool != "yes":
                return None
            if pool == "no" and row_pool != "no":
                return None
            if pool != "any":
                sc += 5

            if max_price is not None and (price is None or price > max_price):
                return None
            if max_price is not None:
                sc += 2

            if max_dist is not None and (dist is None or dist > max_dist):
                return None
            if max_dist is not None:
                sc += 3

            if pets == "yes" and row_pets != "yes":
                return None
            if pets == "yes":
                sc += 3

            return sc + min(2, int(r.get("telegram_message_id") or 0) / 100000)

        arr = [(score(r), r) for r in rows]
        arr = [x for x in arr if x[0] is not None]
        relaxed = False

        if not arr and districts:
            relaxed = True
            arr = [(score(r, True), r) for r in rows]
            arr = [x for x in arr if x[0] is not None]

        arr.sort(
            key=lambda x: (x[0], int(x[1].get("telegram_message_id") or 0)),
            reverse=True,
        )
        return [r for _, r in arr[:limit]], relaxed

    # Patch module globals used by the base functions.
    c._blank = blank
    c.norm_district = norm_district
    c.extract_lot_id = extract_lot_id
    c.canonical = canonical
    c.parse_property_query = parse_property_query
    c.search_catalog = search_catalog

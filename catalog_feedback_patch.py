# -*- coding: utf-8 -*-
"""Prevent the bot's own standardized Telegram posts from overwriting rich catalog data."""

MARKER = "🤖 Подобрать другие варианты"


def apply(mod):
    original_import = mod._import

    def guarded_import(posts, force=False):
        if force:
            return original_import(posts, force)
        try:
            ws = mod.ensure_lots_sheet()
            existing, _ = mod._existing(ws)
        except Exception:
            return original_import(posts, force)

        keep = []
        protected = []
        for p in posts:
            mid = str(p.get("message_id") or "")
            text = str(p.get("text") or "")
            cur = existing.get(mid)
            if cur and MARKER in text:
                protected.append(cur[1])
            else:
                keep.append(p)

        stats = original_import(keep, force)
        if protected:
            stats["inspected"] = int(stats.get("inspected", 0)) + len(protected)
            stats["listing_candidates"] = int(stats.get("listing_candidates", 0)) + len(protected)
            stats["skipped"] = int(stats.get("skipped", 0)) + len(protected)
            lots = list(stats.get("lots") or [])
            lots.extend(r.get("lot_id", "") for r in protected if r.get("lot_id"))
            stats["lots"] = list(dict.fromkeys(lots))
            stats["protected_standardized"] = len(protected)
            mod.log.info("Protected %s standardized posts from catalog re-extraction", len(protected))
        return stats

    mod._import = guarded_import

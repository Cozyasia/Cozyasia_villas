# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

Ordinary starts disable the historical accidental one-shot publisher. Gated
maintenance/publication jobs are explicit and isolated from normal startup.
"""
from __future__ import annotations
import os


def _villa_santi_mode() -> bool:
    return os.getenv("PUBLISH_VILLA_SANTI_20260921", "0").strip().lower() in {"1", "true", "yes", "on"}


def _channel_bot_routing_mode() -> bool:
    return os.getenv("CHANNEL_BOT_ROUTING_MODE", "").strip().lower() in {"audit", "migrate"}


def _publication_mode() -> bool:
    return os.getenv("PUBLISH_PREPARED_THREE_VILLAS", "0").strip().lower() in {"1", "true", "yes", "on"}


def _photo_backfill_mode() -> bool:
    return os.getenv("BACKFILL_SMALL_LOTS_PHOTOS_1201_1207", "0").strip().lower() in {"1", "true", "yes", "on"}


def _drive_link_edit_mode() -> bool:
    return os.getenv("EDIT_SMALL_LOTS_DRIVE_LINKS_1201_1207", "0").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__" and _villa_santi_mode():
    import publish_villa_santi_20260921 as _villa_santi

    # The 29 additional photos are preloaded through the connected Drive user.
    # Render's service account can read the source ZIP but cannot create files
    # inside this user-owned folder, so publication must not attempt re-upload.
    _villa_santi._ensure_additional_photos = (
        lambda root, manifest: [
            f"preloaded-{idx:02d}"
            for idx, _ in enumerate(manifest.get("additional_photos") or [], start=1)
        ]
    )
    _villa_santi.run_service_mode()
elif __name__ == "__main__" and _channel_bot_routing_mode():
    import channel_bot_routing_audit as _channel_bot_routing
    _channel_bot_routing.run_service_mode()
elif __name__ == "__main__" and _drive_link_edit_mode():
    import edit_small_lots_drive_links_1201_1207 as _drive_link_edit
    _drive_link_edit.run_service_mode()
elif __name__ == "__main__" and _photo_backfill_mode():
    import backfill_small_lots_photos_1201_1207 as _photo_backfill
    from airbnb_photo_download_fallback import download_full_image as _download_full_image

    # Keep the production backfill module stable while providing a narrowly
    # scoped CDN-size fallback only for this explicit maintenance mode.
    _photo_backfill._download_full_image = _download_full_image
    _photo_backfill.run_service_mode()
elif __name__ == "__main__" and _publication_mode():
    import publish_prepared_three_bootstrap_20260920 as _prepared
    _prepared.run_service_mode()
else:
    from main_legacy import *  # noqa: F401,F403
    import main_legacy as _entry
    import channel_bot_routing as _permanent_channel_routing

    # Permanent rule: the bot used by generated CTAs is selected from the
    # destination channel, never from whichever Telegram bot happens to be
    # running the standardizer.
    _permanent_channel_routing.apply_to_standardizer(
        _entry.post_standardizer,
        _entry.cozy_catalog,
    )

    def _disable_accidental_startup_publishers() -> None:
        try:
            _entry.publish_fb_1070904912524019.start_once = lambda: None
        except Exception:
            pass

    def _run_drive_permission_probe_if_requested() -> None:
        try:
            import drive_public_permission_once as _drive_public
            if _drive_public.enabled():
                _drive_public.run()
        except Exception:
            import logging
            logging.getLogger("drive-public-permission").exception("Drive public permission probe failed")

    if __name__ == "__main__":
        _disable_accidental_startup_publishers()
        _run_drive_permission_probe_if_requested()
        # Temporary read-only recovery: run alongside the normal bot, emit compact evidence.
        def _start_lot_recovery_once() -> None:
            import threading
            def _scan() -> None:
                try:
                    import asyncio
                    import json
                    import os
                    os.environ["LOT_RECOVERY_TARGETS"] = "1169,965,966,994,01-011,996,997,1170,1147,1072,1109,1157,1039,1004,1018,1019,1111,1102,1041,1042,905,929,984,729,985,01-003,1020,1063,1064,1068,1069,1075,1080,1089,1092,1095,1115,1114,1101,1100,1110,1113,1117,1118,1119,1122,1123,1124,1192,972,977,991,911,908,930,957,941,1052,1051,936,937,938,1049,1053,950"
                    import recover_lots_20260928 as _recovery
                    result = asyncio.run(_recovery.run())
                    for lot, items in sorted(result["found"].items()):
                        for item in items:
                            print("LOT_RECOVERY_HIT=" + json.dumps({
                                "lot": lot, "channel": item["channel"],
                                "message_id": item["message_id"], "url": item["url"],
                                "first_line": item["text"].splitlines()[0] if item["text"] else "",
                            }, ensure_ascii=False), flush=True)
                    print("LOT_RECOVERY_SUMMARY=" + json.dumps({
                        "channels": result["channels"], "missing": result["missing"],
                        "found_lots": len(result["found"]),
                    }, ensure_ascii=False), flush=True)
                except Exception:
                    import logging
                    logging.getLogger("lot-recovery").exception("LOT_RECOVERY_FAILED")
            threading.Thread(target=_scan, name="lot-recovery-20260929", daemon=True).start()

        _start_lot_recovery_once()
        _entry.main()

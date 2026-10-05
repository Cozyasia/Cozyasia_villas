# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

Ordinary starts disable the historical accidental one-shot publisher. Gated
maintenance/publication jobs are explicit and isolated from normal startup.
"""
from __future__ import annotations
import os


def _maenam_skygym_mode() -> bool:
    return os.getenv("PUBLISH_MAENAM_SKYGYM_20261005", "0").strip().lower() in {"1", "true", "yes", "on"}


def _bangrak_garden_mode() -> bool:
    return os.getenv("PUBLISH_BANGRAK_GARDEN_20261005", "0").strip().lower() in {"1", "true", "yes", "on"}


def _montra_mode() -> bool:
    return os.getenv("PUBLISH_MONTRA_20261005", "0").strip().lower() in {"1", "true", "yes", "on"}


def _choengmon_1205_mode() -> bool:
    return os.getenv("PUBLISH_CHOENGMON_1205", "0").strip().lower() in {"1", "true", "yes", "on"}


def _website_media_backfill_mode() -> bool:
    return os.getenv("BACKFILL_WEBSITE_MEDIA_20260929", "0").strip().lower() in {"1", "true", "yes", "on"}


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


if __name__ == "__main__" and _maenam_skygym_mode():
    import publish_maenam_skygym_20261005 as _maenam_skygym
    _maenam_skygym.run_service_mode()
elif __name__ == "__main__" and _bangrak_garden_mode():
    import publish_bangrak_garden_20261005 as _bangrak_garden
    _bangrak_garden.run_service_mode()
elif __name__ == "__main__" and _montra_mode():
    import publish_montra_20261005 as _montra
    _montra.run_service_mode()
elif __name__ == "__main__" and _choengmon_1205_mode():
    import publish_choengmon_1205 as _choengmon
    _choengmon.run_service_mode()
elif __name__ == "__main__" and _website_media_backfill_mode():
    import backfill_website_media_20260929 as _wm
    _wm.main()
elif __name__ == "__main__" and _villa_santi_mode():
    import publish_villa_santi_20260921 as _villa_santi
    _villa_santi._ensure_additional_photos = (
        lambda root, manifest: [f"preloaded-{idx:02d}" for idx, _ in enumerate(manifest.get("additional_photos") or [], start=1)]
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
    _photo_backfill._download_full_image = _download_full_image
    _photo_backfill.run_service_mode()
elif __name__ == "__main__" and _publication_mode():
    import publish_prepared_three_bootstrap_20260920 as _prepared
    _prepared.run_service_mode()
else:
    from main_legacy import *  # noqa: F401,F403
    import main_legacy as _entry
    import channel_bot_routing as _permanent_channel_routing
    _permanent_channel_routing.apply_to_standardizer(_entry.post_standardizer, _entry.cozy_catalog)

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
        _entry.main()

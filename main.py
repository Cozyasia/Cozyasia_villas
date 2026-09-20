# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

Ordinary starts disable the historical accidental one-shot publisher. Gated
maintenance/publication jobs are explicit and isolated from normal startup.
"""
from __future__ import annotations
import os


def _publication_mode() -> bool:
    return os.getenv("PUBLISH_PREPARED_THREE_VILLAS", "0").strip().lower() in {"1", "true", "yes", "on"}


def _photo_backfill_mode() -> bool:
    return os.getenv("BACKFILL_SMALL_LOTS_PHOTOS_1201_1207", "0").strip().lower() in {"1", "true", "yes", "on"}


def _drive_link_edit_mode() -> bool:
    return os.getenv("EDIT_SMALL_LOTS_DRIVE_LINKS_1201_1207", "0").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__" and _drive_link_edit_mode():
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

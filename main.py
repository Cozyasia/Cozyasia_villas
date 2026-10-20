# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

Ordinary starts disable the historical accidental one-shot publisher. Gated
maintenance/publication jobs are explicit and isolated from normal startup.
"""
from __future__ import annotations
import os



def _renumber_price_fb_batch_mode() -> bool:
    return os.getenv("RENUMBER_PRICE_FB_BATCH_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _audit_lot_duplicates_mode() -> bool:
    return os.getenv("AUDIT_LOT_DUPLICATES_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_villa_batch_delete_mode() -> bool:
    return os.getenv("DELETE_FB_VILLA_BATCH_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_villa_batch_mode() -> bool:
    return os.getenv("PUBLISH_FB_VILLA_BATCH_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _delete_current_fb_villa_mode() -> bool:
    return os.getenv("DELETE_CURRENT_FB_VILLA_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _cleanup_malformed_fb_villa_mode() -> bool:
    return os.getenv("CLEANUP_MALFORMED_FB_VILLA_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_villa_manifest_receiver_mode() -> bool:
    return os.getenv("FB_VILLA_MANIFEST_RECEIVER_20261020", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_1548741747291928_mode() -> bool:
    return os.getenv("PUBLISH_FB_1548741747291928", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_3525763387738681_mode() -> bool:
    return os.getenv("PUBLISH_FB_3525763387738681", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_1741918390416111_mode() -> bool:
    return os.getenv("PUBLISH_FB_1741918390416111", "0").strip().lower() in {"1", "true", "yes", "on"}


def _fb_living_pool_mode() -> bool:
    return os.getenv("PUBLISH_FB_LIVING_POOL_20261015", "0").strip().lower() in {"1", "true", "yes", "on"}


def _cleanup_living_pool_duplicate_mode() -> bool:
    return os.getenv("CLEANUP_FB_LIVING_POOL_DUPLICATE_20261015", "0").strip().lower() in {"1", "true", "yes", "on"}


def _repair_latest_premium_mode() -> bool:
    return os.getenv("REPAIR_LATEST_PREMIUM", "0").strip().lower() in {"1", "true", "yes", "on"}


def _repair_living_pool_1210_mode() -> bool:
    return os.getenv("REPAIR_FB_LIVING_POOL_1210_20261015", "0").strip().lower() in {"1", "true", "yes", "on"}


def _aom_bophut_reorder_mode() -> bool:
    return os.getenv("REORDER_AOM_BOPHUT_PHOTOS_20261006", "0").strip().lower() in {"1", "true", "yes", "on"}


def _aom_bophut_media_mode() -> bool:
    return os.getenv("UPDATE_AOM_BOPHUT_MEDIA_20261006", "0").strip().lower() in {"1", "true", "yes", "on"}


def _aom_bophut_mode() -> bool:
    return os.getenv("PUBLISH_AOM_BOPHUT_20261006", "0").strip().lower() in {"1", "true", "yes", "on"}


def _maenam_skygym_mode() -> bool:
    return os.getenv("PUBLISH_MAENAM_SKYGYM_20261005", "0").strip().lower() in {"1", "true", "yes", "on"}


def _bangrak_garden_mode() -> bool:
    return os.getenv("PUBLISH_BANGRAK_GARDEN_20261005", "0").strip().lower() in {"1", "true", "yes", "on"}


def _montra_mode() -> bool:
    return os.getenv("PUBLISH_MONTRA_20261005", "0").strip().lower() in {"1", "true", "yes", "on"}


def _choengmon_1205_mode() -> bool:
    return os.getenv("PUBLISH_CHOENGMON_1205", "0").strip().lower() in {"1", "true", "yes", "on"}


def _airbnb_sgphb3_1205_mode() -> bool:
    return os.getenv("PUBLISH_AIRBNB_SGPHB3_1205", "0").strip().lower() in {"1", "true", "yes", "on"}


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


if __name__ == "__main__" and _renumber_price_fb_batch_mode():
    import renumber_price_fb_batch_20261020 as _renumber_price_fb_batch
    _renumber_price_fb_batch.run_service_mode()
elif __name__ == "__main__" and _audit_lot_duplicates_mode():
    import audit_lot_duplicates_20261020 as _audit_lot_duplicates
    _audit_lot_duplicates.run_service_mode()
if __name__ == "__main__" and _fb_villa_manifest_receiver_mode():
    import fb_villa_batch_20261020 as _fb_villa_batch
    _fb_villa_batch.run_manifest_receiver()
elif __name__ == "__main__" and _delete_current_fb_villa_mode():
    import audit_malformed_small_channel_20261020 as _audit_malformed
    _audit_malformed.run_service_mode()
elif __name__ == "__main__" and _cleanup_malformed_fb_villa_mode():
    import audit_malformed_small_channel_20261020 as _audit_malformed
    _audit_malformed.run_service_mode()
elif __name__ == "__main__" and _fb_villa_batch_delete_mode():
    import fb_villa_batch_20261020 as _fb_villa_batch
    _fb_villa_batch.run_delete_mode()
elif __name__ == "__main__" and _fb_villa_batch_mode():
    import fb_villa_batch_20261020 as _fb_villa_batch
    _fb_villa_batch.run_service_mode()
elif __name__ == "__main__" and os.getenv("REPAIR_SAMUI_NEWS_130", "0") == "1":
    import repair_samui_news_130
    repair_samui_news_130.run_service_mode()
elif __name__ == "__main__" and _fb_1548741747291928_mode():
    import publish_fb_1548741747291928 as _fb_1548741747291928
    _fb_1548741747291928.run_service_mode()
elif __name__ == "__main__" and _fb_3525763387738681_mode():
    import publish_fb_3525763387738681 as _fb_3525763387738681
    _fb_3525763387738681.run_service_mode()
elif __name__ == "__main__" and _fb_1741918390416111_mode():
    import publish_fb_1741918390416111 as _fb_1741918390416111
    _fb_1741918390416111.run_service_mode()
elif __name__ == "__main__" and _fb_living_pool_mode():
    import publish_fb_living_pool_villas_20261015 as _fb_living_pool
    _fb_living_pool.run_service_mode()
elif __name__ == "__main__" and _cleanup_living_pool_duplicate_mode():
    import cleanup_fb_living_pool_duplicate_20261015 as _cleanup_living_pool
    _cleanup_living_pool.run_service_mode()
elif __name__ == "__main__" and _repair_latest_premium_mode():
    import repair_latest_premium as _repair_latest_premium
    _repair_latest_premium.run_service_mode()
    # Continue as a normal web service after the one-shot edit.
    import main_legacy as _legacy_after_repair
    _legacy_after_repair.main()
elif __name__ == "__main__" and _repair_living_pool_1210_mode():
    import repair_fb_living_pool_1210_20261015 as _repair_living_pool_1210
    _repair_living_pool_1210.run_service_mode()
elif __name__ == "__main__" and _aom_bophut_reorder_mode():
    import reorder_aom_bophut_photos_20261006 as _aom_bophut_reorder
    _aom_bophut_reorder.run_service_mode()
elif __name__ == "__main__" and _aom_bophut_media_mode():
    import update_aom_bophut_media_20261006 as _aom_bophut_media
    _aom_bophut_media.run_service_mode()
elif __name__ == "__main__" and _aom_bophut_mode():
    import publish_aom_bophut_20261006 as _aom_bophut
    _aom_bophut.run_service_mode()
elif __name__ == "__main__" and _maenam_skygym_mode():
    import publish_maenam_skygym_20261005 as _maenam_skygym
    _maenam_skygym.run_service_mode()
elif __name__ == "__main__" and _bangrak_garden_mode():
    import publish_bangrak_garden_20261005 as _bangrak_garden
    _bangrak_garden.run_service_mode()
elif __name__ == "__main__" and _montra_mode():
    import publish_montra_20261005 as _montra
    _montra.run_service_mode()
elif __name__ == "__main__" and _airbnb_sgphb3_1205_mode():
    import publish_airbnb_sgphb3_1205 as _airbnb_sgphb3
    _airbnb_sgphb3.run_service_mode()
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




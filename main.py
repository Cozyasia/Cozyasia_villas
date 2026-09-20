# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

Ordinary starts disable the historical accidental one-shot publisher. The
prepared three-villa publication is available only behind an explicit Render
flag and runs through a separate bootstrap path. A separate Drive permission
probe may run once before ordinary startup when explicitly configured.
"""
from __future__ import annotations
import os


def _publication_mode() -> bool:
    return os.getenv("PUBLISH_PREPARED_THREE_VILLAS", "0").strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__" and _publication_mode():
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

# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

Ordinary starts disable the historical accidental one-shot publisher. The
prepared three-villa publication is available only behind an explicit Render
flag and runs through a separate bootstrap path.
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

    if __name__ == "__main__":
        _disable_accidental_startup_publishers()
        _entry.main()

# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint.

The legacy module still contains one historical unconditional one-shot publisher.
Disable only that startup hook here so ordinary deploys/restarts cannot create a
Telegram post accidentally. Explicit publication flows are invoked separately.
"""
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

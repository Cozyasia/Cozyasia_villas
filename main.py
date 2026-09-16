# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint."""
from main_legacy import *  # noqa: F401,F403
import main_legacy as _entry


if __name__ == "__main__":
    _entry.main()

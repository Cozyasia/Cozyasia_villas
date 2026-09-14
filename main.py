# -*- coding: utf-8 -*-
"""Thin production wrapper around the preserved Cozy Asia entrypoint.

The existing application remains in main_legacy.py bit-for-bit. This wrapper
only schedules the optional read-only traffic discovery smoke run and then
starts the original application.
"""
from main_legacy import *  # noqa: F401,F403 - compatibility for code importing main
import main_legacy as _entry
import cozy_catalog
import cozy_traffic_runtime


if __name__ == "__main__":
    cozy_traffic_runtime.ensure_smoke_started(cozy_catalog)
    _entry.main()

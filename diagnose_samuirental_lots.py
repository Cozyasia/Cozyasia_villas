# -*- coding: utf-8 -*-
"""Temporary one-shot launcher for The Terraza Samui publication.

Uses the existing DIAGNOSE_SAMUIRENTAL_LOTS startup slot so main.py does not need
a permanent publication hook. This file is restored after verified publication.
"""
import os

import publish_terraza_20260902


def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS", "0").strip().lower() in {"1", "true", "yes", "on"}


async def run():
    if not enabled():
        return {"enabled": False}
    os.environ["PUBLISH_TERRAZA_20260902"] = "1"
    return await publish_terraza_20260902.run()

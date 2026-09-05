# -*- coding: utf-8 -*-
"""Temporary one-shot launcher for Facebook Marketplace 797602026547213.

Uses the existing DIAGNOSE_SAMUIRENTAL_LOTS startup slot. Restore this file
after verified publication so future deploys cannot create Telegram posts.
"""
import os

import publish_fb_797602026547213


def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS", "0").strip().lower() in {"1", "true", "yes", "on"}


async def run():
    if not enabled():
        return {"enabled": False}
    return await publish_fb_797602026547213.run()

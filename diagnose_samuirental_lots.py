# -*- coding: utf-8 -*-
"""Temporary read-only launcher for Facebook 2236326640522113 diagnostic."""
import os
import diagnose_fb_2236326640522113

def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled():
        return {"enabled":False}
    return await diagnose_fb_2236326640522113.run()

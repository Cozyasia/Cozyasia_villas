# -*- coding: utf-8 -*-
"""Temporary one-shot launcher for Facebook 1791905108663402 publication."""
import os
import publish_fb_1791905108663402

def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled():
        return {"enabled":False}
    return await publish_fb_1791905108663402.run()

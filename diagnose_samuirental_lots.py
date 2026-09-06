# -*- coding: utf-8 -*-
import os
import fix_small_lots_1200_1207_premium_cta

def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled():
        return {"enabled":False}
    return await fix_small_lots_1200_1207_premium_cta.run()

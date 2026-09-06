# -*- coding: utf-8 -*-
import os
import reprice_small_lots_1200_1207

def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled():
        return {"enabled":False}
    return await reprice_small_lots_1200_1207.run()

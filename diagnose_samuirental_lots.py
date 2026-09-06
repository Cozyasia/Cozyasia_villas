# -*- coding: utf-8 -*-
import os
import migrate_samuirental_operator

def enabled():
    return os.getenv("DIAGNOSE_SAMUIRENTAL_LOTS","0").strip().lower() in {"1","true","yes","on"}

async def run():
    if not enabled():
        return {"enabled":False}
    return await migrate_samuirental_operator.run()

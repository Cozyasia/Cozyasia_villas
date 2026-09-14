# -*- coding: utf-8 -*-
"""Temporary one-shot launcher for the confirmed Bophut Larnthong publication."""
import publish_bophut_larnthong_20260914


def enabled():
    return True


async def run():
    return await publish_bophut_larnthong_20260914.run()

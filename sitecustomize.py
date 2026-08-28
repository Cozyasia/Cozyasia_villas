# -*- coding: utf-8 -*-
"""Early runtime hook for Cozy Asia channel-specific bot routing.

Python imports sitecustomize automatically on service startup. We use that to
wrap the active post layout after it is applied and, only when explicitly
enabled, run the one-shot historical CTA migration.
"""
from __future__ import annotations

import asyncio
import threading
import time
import traceback

try:
    import channel_bot_routing as routing
    import post_layout_v7_safe

    _original_v7_apply = post_layout_v7_safe.apply

    def _routed_v7_apply(mod, throttle):
        _original_v7_apply(mod, throttle)
        import cozy_catalog
        routing.apply_to_standardizer(mod, cozy_catalog)

    post_layout_v7_safe.apply = _routed_v7_apply

    if routing.enabled():
        def _migration_worker():
            # Allow main.py to finish imports and initialize the MTProto runtime.
            time.sleep(12)
            try:
                import cozy_catalog
                result = asyncio.run(routing.run(cozy_catalog))
                print("CHANNEL_BOT_ROUTING_STARTUP_DONE", result, flush=True)
            except Exception:
                print("CHANNEL_BOT_ROUTING_STARTUP_FAILED", flush=True)
                traceback.print_exc()

        threading.Thread(
            target=_migration_worker,
            name="channel-bot-routing-migration",
            daemon=True,
        ).start()
except Exception:
    print("CHANNEL_BOT_ROUTING_HOOK_FAILED", flush=True)
    traceback.print_exc()

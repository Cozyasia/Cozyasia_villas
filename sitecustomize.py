# -*- coding: utf-8 -*-
"""Temporary read-only startup probe for the approved Facebook listing."""
import json
import threading
import time

import inspect_fb_28520466234226624 as _fb285


def _run_fb285_probe():
    time.sleep(6)
    try:
        result = _fb285.run()
        if result.get("enabled"):
            print("FB285_PROBE_DONE " + json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as exc:
        print(f"FB285_PROBE_ERROR {type(exc).__name__}: {exc}", flush=True)


if _fb285.enabled():
    threading.Thread(target=_run_fb285_probe, name="fb285-probe", daemon=True).start()

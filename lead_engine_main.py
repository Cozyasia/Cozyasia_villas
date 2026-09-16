# -*- coding: utf-8 -*-
"""Dedicated Cozy Lead Engine Render entrypoint."""
from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import threading

from telegram.ext import Application

import ai_manager_auth
import cozy_catalog
import cozy_traffic_runtime
import cozy_traffic_scoring_patch
import cozy_traffic_discovery_patch
import lead_engine_control

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("cozy-lead-engine")

cozy_traffic_scoring_patch.apply(cozy_traffic_runtime)
cozy_traffic_discovery_patch.apply(cozy_traffic_runtime)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({"status": "ok", "service": "cozy-lead-engine"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A003
        return


def _required_token() -> str:
    token = os.getenv("COZY_LEAD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("COZY_LEAD_BOT_TOKEN is required")
    return token


def _start_health_server() -> None:
    port = int(os.getenv("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    threading.Thread(target=server.serve_forever, name="lead-health", daemon=True).start()
    log.info("Health server listening on port %s", port)


def _ensure_event_loop_for_polling() -> None:
    """Install a current loop for python-telegram-bot under Python 3.14+."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def main() -> None:
    token = _required_token()

    async def _post_init(application):
        await lead_engine_control.post_init(application, cozy_catalog)

    app = Application.builder().token(token).post_init(_post_init).build()
    lead_engine_control.install_handlers(app, cozy_catalog)
    ai_manager_auth.install_handlers(app, cozy_catalog)
    _start_health_server()
    _ensure_event_loop_for_polling()
    log.info("Cozy Lead Engine starting polling")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()

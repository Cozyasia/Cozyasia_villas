# -*- coding: utf-8 -*-
"""Production entrypoint: legacy Cozy Asia bot + property catalog."""
import logging
import threading

from telegram.ext import CommandHandler, MessageHandler, filters

import legacy_main as legacy
import cozy_catalog

log = logging.getLogger("villa-bot-wrapper")


def _bootstrap_catalog():
    try:
        cozy_catalog.ensure_lots_sheet()
        log.info("Lots worksheet ready")
        if cozy_catalog.CATALOG_BOOTSTRAP_IMPORT:
            stats = cozy_catalog.import_public_channel_latest(
                cozy_catalog.CATALOG_BOOTSTRAP_LIMIT, False
            )
            log.info("Bootstrap catalog import: %s", stats)
    except Exception:
        log.exception("Catalog bootstrap failed")


def _install_catalog_handlers(app):
    # Explicit wiring: Application uses __slots__, so do not attach custom flags.
    app.add_handler(CommandHandler("catalog_import", cozy_catalog.cmd_catalog_import), group=-20)
    app.add_handler(CommandHandler("catalog_status", cozy_catalog.cmd_catalog_status), group=-20)
    app.add_handler(MessageHandler(filters.ALL, cozy_catalog.catch_catalog_updates), group=-10)
    log.info("Catalog handlers installed for @%s", cozy_catalog.CATALOG_CHANNEL)


def main():
    legacy._log_openai_env()
    legacy._probe_openai()

    app = legacy.build_application()
    _install_catalog_handlers(app)

    # Do not block Render port binding while old posts are parsed.
    threading.Thread(
        target=_bootstrap_catalog,
        name="catalog-bootstrap",
        daemon=True,
    ).start()

    legacy.run_webhook(app)


if __name__ == "__main__":
    main()

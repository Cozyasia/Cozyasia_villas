# -*- coding: utf-8 -*-
"""
Non-invasive catalog hook for the legacy Cozy Asia villa bot.

Python imports sitecustomize automatically.  We use that to add the new catalog
layer without rewriting the existing /rent flow in main.py.
"""
import logging

log = logging.getLogger("villa-catalog-hook")

try:
    from telegram.ext import Application, ApplicationBuilder
    import cozy_catalog

    if not getattr(ApplicationBuilder, "_cozy_catalog_patched", False):
        _original_build = ApplicationBuilder.build

        def _build_with_catalog(self):
            app = _original_build(self)
            try:
                cozy_catalog.install_handlers(app)
            except Exception:
                log.exception("Failed to install Cozy catalog handlers")
            return app

        ApplicationBuilder.build = _build_with_catalog
        ApplicationBuilder._cozy_catalog_patched = True

    if not getattr(Application, "_cozy_catalog_initialize_patched", False):
        _original_initialize = Application.initialize

        async def _initialize_with_catalog(self):
            await _original_initialize(self)
            try:
                await cozy_catalog.post_initialize(self)
            except Exception:
                log.exception("Cozy catalog post-initialize failed")

        Application.initialize = _initialize_with_catalog
        Application._cozy_catalog_initialize_patched = True

except Exception:
    # Never prevent the production bot from starting because of the optional
    # catalog layer.  Any error will be visible in Render logs.
    log.exception("Cozy catalog hook was not installed")

# -*- coding: utf-8 -*-
"""Production wrapper preserving the historical Cozy Asia entrypoint bit-for-bit."""
from main_legacy import *  # noqa: F401,F403
import main_legacy as _entry
import cozy_catalog
import cozy_traffic_runtime
import cozy_traffic_scoring_patch

cozy_traffic_scoring_patch.apply(cozy_traffic_runtime)

import cozy_traffic_manager

_original_install = _entry._install_catalog_handlers


def _install_catalog_handlers_with_traffic(app):
    _original_install(app)
    cozy_traffic_manager.install(app, cozy_catalog)


_entry._install_catalog_handlers = _install_catalog_handlers_with_traffic

if __name__ == "__main__":
    cozy_traffic_runtime.ensure_smoke_started(cozy_catalog)
    _entry.main()

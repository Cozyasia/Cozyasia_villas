# -*- coding: utf-8 -*-
"""Gated bootstrap for the prepared 2026-09-20 three-villa publication."""
from __future__ import annotations

import importlib
import json
import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path


_TRUTHY = {"1", "true", "yes", "on"}


def enabled() -> bool:
    return os.getenv("PUBLISH_PREPARED_THREE_VILLAS", "0").strip().lower() in _TRUTHY


def preloaded_additional_mode() -> bool:
    """Use already-preloaded overflow photos instead of writing to Drive."""
    return os.getenv("PREPARED_SKIP_ADDITIONAL_UPLOAD", "0").strip().lower() in _TRUTHY


def diagnostic_mode() -> bool:
    return os.getenv("PREPARED_PACKAGE_DIAGNOSTIC", "0").strip().lower() in _TRUTHY


def _preloaded_additional_ids(record) -> list[str]:
    """Return stable placeholders for overflow photos already present in Drive."""
    values = []
    keys = ("additional_photos", "additional_files", "additional", "extra_photos")
    if isinstance(record, dict):
        for key in keys:
            candidate = record.get(key)
            if candidate:
                values = candidate
                break
    else:
        for key in keys:
            candidate = getattr(record, key, None)
            if candidate:
                values = candidate
                break
    return [f"preloaded-{idx:02d}" for idx, _ in enumerate(values or [], start=1)]


def _materialize_package() -> Path:
    file_id = os.getenv("PREPARED_THREE_DRIVE_FILE_ID", "").strip()
    if not file_id:
        raise RuntimeError("PREPARED_THREE_DRIVE_FILE_ID is missing")
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON is missing")

    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession

    work = Path("/tmp/cozy_prepared_three_20260920")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    archive = work / "package.zip"
    root = work / "package"
    root.mkdir()

    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    response = AuthorizedSession(creds).get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media", timeout=180
    )
    response.raise_for_status()
    archive.write_bytes(response.content)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(root)
    if not (root / "prepared_three_runtime.py").is_file():
        raise RuntimeError("prepared_three_runtime.py is missing from the package")
    return root


def _log_retry_diagnostics(root: Path) -> None:
    """Log only package structure and generic runtime code around the lot guard."""
    log = logging.getLogger("prepared-publication-diagnostic")
    paths = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    log.info("PACKAGE_FILES %s", json.dumps(paths, ensure_ascii=False))
    runtime_path = root / "prepared_three_runtime.py"
    lines = runtime_path.read_text(encoding="utf-8").splitlines()
    start = max(0, 175 - 1)
    end = min(len(lines), 220)
    numbered = [f"{idx + 1}: {lines[idx]}" for idx in range(start, end)]
    log.info("RUNTIME_LINES_175_220\n%s", "\n".join(numbered))


def run_service_mode() -> None:
    if not enabled():
        raise RuntimeError("Prepared publication bootstrap is not enabled")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    root = _materialize_package()
    if diagnostic_mode():
        _log_retry_diagnostics(root)
        return
    sys.path.insert(0, str(root))
    runtime = importlib.import_module("prepared_three_runtime")
    if preloaded_additional_mode():
        logging.getLogger("prepared-publication-bootstrap").info(
            "Using preloaded additional-photo mode; Drive writes are disabled"
        )
        runtime._ensure_additional = _preloaded_additional_ids
    runtime.run_service_mode()

# -*- coding: utf-8 -*-
"""Gated bootstrap for the prepared 2026-09-20 three-villa publication."""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path


def enabled() -> bool:
    return os.getenv("PUBLISH_PREPARED_THREE_VILLAS", "0").strip().lower() in {"1", "true", "yes", "on"}


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


def run_service_mode() -> None:
    if not enabled():
        raise RuntimeError("Prepared publication bootstrap is not enabled")
    root = _materialize_package()
    sys.path.insert(0, str(root))
    runtime = importlib.import_module("prepared_three_runtime")
    runtime.run_service_mode()

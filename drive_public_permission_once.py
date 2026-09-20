# -*- coding: utf-8 -*-
"""Idempotent permission probe/helper for Drive files owned by the connected user.

When a user-owned Drive file is shared to the Cozy Asia service account as writer,
this helper asks Drive to add an `anyone/reader` permission. It is gated by
DRIVE_PUBLIC_PERMISSION_FILE_ID and safe to repeat.
"""
from __future__ import annotations
import json
import logging
import os

log = logging.getLogger("drive-public-permission")


def enabled() -> bool:
    return bool(os.getenv("DRIVE_PUBLIC_PERMISSION_FILE_ID", "").strip())


def run() -> dict:
    file_id = os.getenv("DRIVE_PUBLIC_PERMISSION_FILE_ID", "").strip()
    if not file_id:
        return {"enabled": False}
    raw = os.getenv("GOOGLE_CREDS_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_CREDS_JSON missing")
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import AuthorizedSession
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive"]
    )
    session = AuthorizedSession(creds)
    meta = session.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"fields":"id,name,permissions(id,type,role,emailAddress,allowFileDiscovery)"},
        timeout=60,
    )
    meta.raise_for_status()
    permissions = meta.json().get("permissions") or []
    if not any(p.get("type") == "anyone" and p.get("role") == "reader" for p in permissions):
        r = session.post(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
            params={"sendNotificationEmail":"false"},
            json={"type":"anyone","role":"reader","allowFileDiscovery":False},
            timeout=60,
        )
        if not r.ok:
            log.error("DRIVE_PUBLIC_PERMISSION_ERROR status=%s body=%s", r.status_code, r.text[:1000])
            r.raise_for_status()
    verify = session.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"fields":"id,name,webViewLink,permissions(id,type,role,emailAddress,allowFileDiscovery)"},
        timeout=60,
    )
    verify.raise_for_status()
    data = verify.json()
    public = any(p.get("type") == "anyone" and p.get("role") == "reader" for p in (data.get("permissions") or []))
    result = {"enabled": True, "file_id": file_id, "public_reader": public, "webViewLink": data.get("webViewLink")}
    log.info("DRIVE_PUBLIC_PERMISSION_RESULT %s", json.dumps(result, ensure_ascii=False))
    if not public:
        raise RuntimeError("Anyone-reader permission was not observed after write")
    return result

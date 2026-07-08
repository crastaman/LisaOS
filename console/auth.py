"""Tailscale-identity authentication for Lisa Console (Phase C4).

No application passwords, no session cookies, no login form. Deployment
(Phase C5) uses `tailscale serve`, which injects a `Tailscale-User-Login`
header identifying the requesting tailnet device's owner. This module's
entire job is: check that header against an explicit allowlist and audit
every access attempt, granted or denied.

Fail closed: an empty or unset LISA_CONSOLE_OWNER_IDENTITY means the
allowlist is empty, so *every* request is denied until it is configured --
never "allow everyone" as a default.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, request

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
AUDIT_LOG = LISA_BASE / "reports" / "console" / "audit.jsonl"

IDENTITY_HEADER = "Tailscale-User-Login"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(record: dict, audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def allowed_identities(raw: str | None = None) -> set[str]:
    """Parse LISA_CONSOLE_OWNER_IDENTITY as a comma-separated allowlist.

    An unset or empty value yields an empty set -- fail closed, not
    fail open.
    """
    raw = raw if raw is not None else os.environ.get("LISA_CONSOLE_OWNER_IDENTITY", "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def check_access(*, audit_path: Path | None = None) -> None:
    """Flask before_request hook. Aborts with 403 if the requesting
    identity is not on the allowlist. Audits every attempt, granted or
    denied, per the explicit "audit all access attempts" requirement --
    this is the only place in the Console that ever runs before any
    route handler.
    """
    identity = (request.headers.get(IDENTITY_HEADER) or "").strip()
    allowed = allowed_identities()
    granted = bool(identity) and identity in allowed

    _append_audit(
        {
            "event": "access_granted" if granted else "access_denied",
            "identity": identity or None,
            "path": request.path,
            "method": request.method,
            "at": _now_iso(),
        },
        audit_path or AUDIT_LOG,
    )

    g.identity = identity or None

    if not granted:
        abort(403)


def init_app(app: Flask, *, audit_path: Path | None = None) -> None:
    """Register the identity check as a before_request hook on `app`."""

    @app.before_request
    def _check() -> None:  # pragma: no cover -- exercised via check_access() tests
        check_access(audit_path=audit_path)

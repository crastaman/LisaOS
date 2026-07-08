"""ntfy push notification delivery for Executive Brief availability.

Lisa Console v1, Phase C3. See docs/LISAOS/CONSOLE/03_NTFY_NOTIFICATION_SPEC.md.

Notification channel only. This module cannot execute, approve, reject,
schedule, or trigger anything -- it sends a small pointer notification and
nothing more. Tapping the notification opens the Console (Phase C4); the
Console, not the notification, remains the authoritative source of truth
for brief availability and decisions. No LisaOS runtime imports (core/,
engines/) -- same advisory-only boundary as the rest of advisors/,
verified by grep.

Payload allowlist (the core security property of this module): the
outbound payload is built field-by-field from a fixed, named set --
brief_id, headline, recommendation_summary, confidence, priority,
timestamp, console_deep_link -- via build_payload(). Nothing else on an
Executive Brief or Decision Bundle (evidence, key_risks detail,
missing_information, worker identities, file paths, bundle contents,
logs, stack traces) is ever read into the payload, because build_payload()
never passes any dict through wholesale -- it only ever assigns from six
named brief fields into six named payload keys.  headline and
recommendation_summary are GPT-authored and therefore bundle-*informed*
(that's their purpose), but they are the two fields the approved
requirements explicitly allow onto the wire; nothing raw or structured
crosses with them.

Delivery: bounded retry with backoff (never an unbounded retry storm),
timeout handling, and unreachable-server handling all funnel through one
provider function, _send_once() -- the only piece that needs to change to
migrate to a self-hosted ntfy instance or a different push provider.
Everything else (payload construction, retry, duplicate suppression,
audit logging) is provider-agnostic.

Failure handling: send_notification() never raises for a delivery
failure -- ntfy being unavailable must never block brief generation or
Console usability. Every outcome (sent, failed, duplicate_suppressed) is
returned as a NotificationResult and, for failures, recorded to
reports/console/audit.jsonl -- audit only, nothing more.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
NOTIFICATIONS_DIR = LISA_BASE / "reports" / "console" / "notifications"
AUDIT_LOG = LISA_BASE / "reports" / "console" / "audit.jsonl"

DEFAULT_NTFY_SERVER = "https://ntfy.sh"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 0.5

CATEGORY_UNAVAILABLE = "unavailable"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_RATE_LIMITED = "rate_limited"
CATEGORY_INVALID_RESPONSE = "invalid_response"
CATEGORY_NOT_CONFIGURED = "not_configured"

_ALLOWED_PRIORITIES = {"min", "low", "default", "high", "urgent"}

PublishFn = Callable[..., None]


class _NotifyAPIError(Exception):
    """Internal: one publish attempt failed. `category` drives retry/audit."""

    def __init__(self, message: str, *, category: str):
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class NotificationResult:
    status: str  # "sent" | "failed" | "duplicate_suppressed"
    brief_id: str
    category: str | None = None
    reason: str | None = None
    attempts: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Payload construction -- the allowlist boundary
# --------------------------------------------------------------------------- #

def _compute_priority(brief: dict) -> str:
    """Computed from full brief detail (key_risks, escalation level) but
    only the resulting label -- never the detail itself -- reaches the
    payload.
    """
    if brief.get("status") == "degraded":
        return "default"
    if brief.get("recommendation") == "reject":
        return "high"
    escalation = brief.get("escalation_recommendation") or {}
    level = escalation.get("level")
    if level == "urgent":
        return "urgent"
    if level == "recommended":
        return "high"
    if brief.get("key_risks"):
        return "high"
    return "default"


def _recommendation_summary(brief: dict) -> str:
    if brief.get("status") == "degraded":
        return "GPT summary unavailable -- raw bundle ready for review"
    rec = brief.get("recommendation")
    return f"Recommendation: {rec}" if rec else "No recommendation available"


def _fallback_headline(brief: dict) -> str:
    if brief.get("status") == "degraded":
        return "Decision pending -- GPT summary unavailable"
    return "Executive Brief ready for review"


def build_payload(brief: dict, *, base_url: str | None = None) -> dict:
    """Build the ntfy-bound payload from an Executive Brief.

    Allowlist-only: this function assigns from exactly six named brief
    fields (headline, recommendation, confidence, escalation_recommendation,
    key_risks -- the last two only to compute priority, never copied
    through) into exactly seven named payload keys. It never does
    `payload.update(brief)` or any wholesale copy. See module docstring.
    """
    brief_id = brief.get("brief_id")
    if not brief_id:
        raise ValueError("brief has no brief_id")

    base_url = base_url if base_url is not None else os.environ.get("LISA_CONSOLE_BASE_URL", "").strip()
    deep_link = f"{base_url.rstrip('/')}/brief/{brief_id}" if base_url else None

    headline = brief.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        headline = _fallback_headline(brief)

    return {
        "brief_id": brief_id,
        "headline": headline[:140],
        "recommendation_summary": _recommendation_summary(brief),
        "confidence": brief.get("confidence"),
        "priority": _compute_priority(brief),
        "timestamp": _now_iso(),
        "console_deep_link": deep_link,
    }


# --------------------------------------------------------------------------- #
# Provider (the one piece that changes for a different push backend)
# --------------------------------------------------------------------------- #

def _safe_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        return "<no response body>"


def _send_once(
    *, server: str, topic: str, token: str | None, payload: dict, timeout_seconds: float,
) -> None:
    """Publish one ntfy message via ntfy's HTTP publish API.

    This is the provider-specific piece -- swap this function (and only
    this function) to migrate to a self-hosted ntfy instance (a different
    `server`) or a different push provider entirely (a different
    request shape). Payload construction, retry, duplicate suppression,
    and audit logging never need to change.
    """
    url = f"{server.rstrip('/')}/{topic}"
    body = payload["recommendation_summary"]
    if payload.get("confidence"):
        body += f" (confidence: {payload['confidence']})"

    priority = payload["priority"] if payload["priority"] in _ALLOWED_PRIORITIES else "default"
    headers = {
        "Title": f"[LisaOS] {payload['headline']}",
        "Priority": priority,
        "Tags": "robot,warning" if priority in ("high", "urgent") else "robot",
    }
    if payload.get("console_deep_link"):
        headers["Click"] = payload["console_deep_link"]
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body.encode("utf-8"), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = _safe_error_detail(exc)
        if exc.code == 429:
            raise _NotifyAPIError(f"ntfy rate limited (429): {detail}", category=CATEGORY_RATE_LIMITED) from None
        if exc.code >= 500:
            raise _NotifyAPIError(f"ntfy unavailable ({exc.code}): {detail}", category=CATEGORY_UNAVAILABLE) from None
        raise _NotifyAPIError(f"ntfy error ({exc.code}): {detail}", category=CATEGORY_INVALID_RESPONSE) from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            raise _NotifyAPIError(f"ntfy timed out: {reason}", category=CATEGORY_TIMEOUT) from None
        raise _NotifyAPIError(f"ntfy unavailable: {reason}", category=CATEGORY_UNAVAILABLE) from None
    except TimeoutError as exc:
        raise _NotifyAPIError(f"ntfy timed out: {exc}", category=CATEGORY_TIMEOUT) from None


# --------------------------------------------------------------------------- #
# Duplicate suppression (persisted marker -- survives across process runs)
# --------------------------------------------------------------------------- #

def _marker_path(brief_id: str, notifications_dir: Path) -> Path:
    return notifications_dir / f"{brief_id}.json"


def _already_sent(brief_id: str, notifications_dir: Path) -> bool:
    return _marker_path(brief_id, notifications_dir).is_file()


def _record_sent_marker(brief_id: str, notifications_dir: Path, *, priority: str) -> None:
    notifications_dir.mkdir(parents=True, exist_ok=True)
    marker = _marker_path(brief_id, notifications_dir)
    tmp = marker.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"brief_id": brief_id, "sent_at": _now_iso(), "priority": priority}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, marker)


# --------------------------------------------------------------------------- #
# Audit logging (Console's shared audit.jsonl -- append-only, matching the
# reports/lisa/*.jsonl evidence-log convention)
# --------------------------------------------------------------------------- #

def _append_audit(record: dict, audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def send_notification(
    brief: dict,
    *,
    server: str | None = None,
    topic: str | None = None,
    token: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    publish_fn: PublishFn | None = None,
    notifications_dir: Path | None = None,
    audit_path: Path | None = None,
) -> NotificationResult:
    """Send (or suppress, or fail) one ntfy notification for a brief.

    Never raises for a delivery failure or missing configuration -- ntfy
    being unavailable must never block brief generation or Console
    usability. Every outcome is recorded to `audit_path` and returned as
    a NotificationResult; the brief itself is never modified.
    """
    brief_id = brief.get("brief_id")
    if not brief_id:
        raise ValueError("brief has no brief_id")

    notifications_dir = notifications_dir or NOTIFICATIONS_DIR
    audit_path = audit_path or AUDIT_LOG
    publish_fn = publish_fn or _send_once

    if _already_sent(brief_id, notifications_dir):
        _append_audit(
            {"event": "ntfy_duplicate_suppressed", "brief_id": brief_id, "at": _now_iso()}, audit_path
        )
        return NotificationResult(status="duplicate_suppressed", brief_id=brief_id)

    topic = topic if topic is not None else os.environ.get("LISA_CONSOLE_NTFY_TOPIC", "").strip()
    if not topic:
        reason = "LISA_CONSOLE_NTFY_TOPIC is not set"
        _append_audit(
            {"event": "ntfy_failed", "brief_id": brief_id, "at": _now_iso(),
             "category": CATEGORY_NOT_CONFIGURED, "reason": reason, "attempts": 0},
            audit_path,
        )
        return NotificationResult(
            status="failed", brief_id=brief_id, category=CATEGORY_NOT_CONFIGURED, reason=reason, attempts=0
        )

    server = server if server is not None else (
        os.environ.get("LISA_CONSOLE_NTFY_SERVER", "").strip() or DEFAULT_NTFY_SERVER
    )
    token = token if token is not None else (os.environ.get("LISA_CONSOLE_NTFY_TOKEN", "").strip() or None)

    payload = build_payload(brief, base_url=base_url)

    last_category: str | None = None
    last_reason: str | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            publish_fn(server=server, topic=topic, token=token, payload=payload, timeout_seconds=timeout_seconds)
        except _NotifyAPIError as exc:
            last_category, last_reason = exc.category, str(exc)
            if attempt < max_attempts:
                sleep_fn(backoff_seconds * attempt)
            continue
        else:
            _record_sent_marker(brief_id, notifications_dir, priority=payload["priority"])
            _append_audit(
                {"event": "ntfy_sent", "brief_id": brief_id, "at": _now_iso(),
                 "priority": payload["priority"], "attempt": attempt},
                audit_path,
            )
            return NotificationResult(status="sent", brief_id=brief_id, attempts=attempt)

    _append_audit(
        {"event": "ntfy_failed", "brief_id": brief_id, "at": _now_iso(),
         "category": last_category, "reason": last_reason, "attempts": max_attempts},
        audit_path,
    )
    return NotificationResult(
        status="failed", brief_id=brief_id, category=last_category, reason=last_reason, attempts=max_attempts
    )

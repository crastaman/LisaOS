"""The Safe Action Model (Lisa Console v1, Phase C4).

record_decision() is the *only* write path in the Console beyond the
audit log (console.auth.check_access also writes audit entries; nothing
else in this package writes anything). It writes exactly one field --
`decision` -- on an existing, already-exported bundle. It does not, and
structurally cannot, execute anything:

  * No import of core.dispatcher, core.workforce_resolver, or any
    engines/* module anywhere in this package (verified by grep).
  * There is no code path from a decision back into job execution --
    LisaOS job packets are documentation-only today (see
    docs/LISAOS/CONSOLE/01_DECISION_BUNDLE_SPEC.md), so there is nothing
    for a decision to trigger even if this module wanted to trigger
    something. Decision storage (a bundle's `decision` field) is
    entirely separate from execution logic (core/dispatcher.py), by
    construction, not by convention.
  * The only two choices are "approve" and "reject" -- there is no
    "run", "execute", "retry", or "force" action anywhere in this
    module or in console/app.py's routes.

Every decision requires a non-empty rationale, for both approve and
reject. A bundle that already has a `decision` refuses a second one
(AlreadyDecidedError) -- this is a check-then-write guard, not
OS-level compare-and-swap file locking, which is a proportionate choice
for a single-operator local tool (documented, not hidden).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
BUNDLES_DIR = LISA_BASE / "reports" / "console" / "bundles"
AUDIT_LOG = LISA_BASE / "reports" / "console" / "audit.jsonl"

_VALID_CHOICES = {"approve", "reject"}


class ActionError(Exception):
    """Base class for Safe Action Model errors."""


class BundleNotFoundError(ActionError):
    pass


class AlreadyDecidedError(ActionError):
    """The bundle already has a decision -- refuses a second write."""


class InvalidDecisionError(ActionError):
    """Bad choice value or missing rationale."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(record: dict[str, Any], audit_path: Path) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def record_decision(
    bundle_id: str,
    *,
    choice: str,
    actor: str,
    note: str,
    bundles_dir: Path | None = None,
    audit_path: Path | None = None,
) -> dict[str, Any]:
    """Approve or reject a bundle. Returns the updated bundle dict.

    Raises BundleNotFoundError, InvalidDecisionError, or
    AlreadyDecidedError rather than silently doing something unexpected
    -- callers (console/app.py's route handler) are expected to turn
    these into a 404/400/409 response, never to retry with different
    semantics.
    """
    if choice not in _VALID_CHOICES:
        raise InvalidDecisionError(f"choice must be one of {sorted(_VALID_CHOICES)}, got {choice!r}")
    if not note or not note.strip():
        raise InvalidDecisionError("a non-empty rationale is required for every decision")
    if not actor or not actor.strip():
        raise InvalidDecisionError("actor (the authenticated identity) is required")

    bundles_dir = bundles_dir or BUNDLES_DIR
    bundle_path = bundles_dir / bundle_id / "bundle.json"
    if not bundle_path.is_file():
        raise BundleNotFoundError(f"no such bundle: {bundle_id}")

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    if bundle.get("decision") is not None:
        raise AlreadyDecidedError(
            f"bundle {bundle_id} already has a decision: {bundle['decision']!r}"
        )

    decided_at = _now_iso()
    bundle["decision"] = {
        "choice": choice,
        "by": actor,
        "at": decided_at,
        "note": note.strip(),
    }

    tmp_path = bundle_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, bundle_path)

    _append_audit(
        {
            "event": "decision_recorded",
            "bundle_id": bundle_id,
            "choice": choice,
            "actor": actor,
            "note": note.strip(),
            "at": decided_at,
        },
        audit_path or AUDIT_LOG,
    )

    return bundle

"""LisaOS Work Product evidence layer (Phase 3 -- LISA-I005).

Closes the gap between "a worker executed" and "here is exactly what it
produced". Before this module LisaOS recorded *dispatch* facts only
(assignment, model, run_id, tokens, success). It had no deterministic
representation of the engineering work itself, so any downstream review had
to re-derive it from conversation history or OpenClaw logs.

THE TRUST BOUNDARY (the central design decision)
------------------------------------------------
The only entity that knows what engineering happened is the worker, and the
worker is outside LisaOS's trust boundary -- exactly like the Phase 2 plan
proposer. A Work Product is therefore split in two, and the split is
structural, not stylistic:

  * OBSERVED  -- derived by LisaOS itself from the repository, around the
                 executor call: branch, base/head commit, files changed,
                 the patch and its sha256. A worker cannot fabricate this,
                 and it is captured whether or not the worker cooperates.
  * DECLARED  -- supplied by the worker: summary, tests executed, results,
                 risks, warnings, deferred work. Untrusted and OPTIONAL.
                 Validated when present; its absence is recorded, never
                 silently tolerated.
  * DISCREPANCIES -- where the two disagree, both are kept and the conflict
                 is recorded. OBSERVATION WINS. Nothing is reconciled away.

"Capture first, interpret later": this module records evidence and performs
NO synthesis, summarisation, or judgement of the engineering work.

WHERE CAPTURE HAPPENS
---------------------
`work_product_recording_executor()` wraps any Dispatcher ExecutorFn, exactly
as `core.capacity_ledger.ledger_recording_executor` does. This means:

  * no change to core/dispatcher.py or core/openclaw_bridge.py (both
    authoritative and protected);
  * NO parallel execution path -- the dispatcher remains the sole execution
    authority and capture is a passive observer around it;
  * provenance is INHERITED from the inner executor, never invented (a
    wrapper must not launder attribution -- see core/dispatcher.py r4/B3).

Capture is strictly non-fatal: any failure to observe the repository or write
evidence is recorded on the artifact as `capture_error` and never converts a
successful execution into a failed one, nor crashes a dispatch batch.

STORAGE
-------
Under the EXISTING `reports/lisa/orchestration/` evidence tree established in
Phases 1-2. No parallel ledger is introduced:

  work_products/<package_id>__<run>.json    the artifact
  work_products/<package_id>__<run>.patch   the patch (sha256 recorded in JSON)
  work_products/index.jsonl                 append-only discovery index
  work_products/declared/<package_id>.json  worker-written declaration (input)

The patch lives beside the JSON rather than inside it so artifacts stay small
and greppable while the full diff remains byte-exact and hash-verified.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = "lisa-work-product/1"

LISA_BASE = Path(__file__).resolve().parent.parent
DEFAULT_STORE = LISA_BASE / "reports" / "lisa" / "orchestration" / "work_products"
INDEX_NAME = "index.jsonl"
DECLARED_DIRNAME = "declared"

STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_NO_EXECUTION = "no_execution"
VALID_STATUSES = (STATUS_COMPLETED, STATUS_FAILED, STATUS_NO_EXECUTION)

TEST_RESULTS = ("pass", "fail", "error", "skipped")

# Keys a worker is permitted to declare. Anything else is rejected rather than
# quietly ignored, so a worker cannot smuggle fields (e.g. its own "status")
# into evidence that LisaOS is responsible for observing.
DECLARED_KEYS = frozenset(
    {"summary", "tests", "risks", "warnings", "deferred", "notes"}
)

_GIT_TIMEOUT = 30


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class WorkProductError(Exception):
    """Capture/transport fault (repository unreadable, store unwritable)."""


class WorkProductValidationError(Exception):
    """A Work Product was rejected. `.errors` lists every violation found."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = list(errors or [])


# --------------------------------------------------------------------------- #
# Git observation (LisaOS-derived -- the authoritative half)
# --------------------------------------------------------------------------- #

def _git(repo: str | Path, *args: str) -> tuple[int, str, str]:
    """Run one git command in `repo`. Never raises on git failure."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 128, "", f"git invocation failed: {exc}"
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class RepoState:
    """A point-in-time observation of a repository. Purely factual."""

    repo: str
    available: bool = False
    branch: str | None = None
    commit: str | None = None
    dirty: list[str] = field(default_factory=list)
    capture_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_repo_state(repo: str | Path) -> RepoState:
    """Observe `repo` now. Fails soft: an unusable repo yields available=False
    with a reason, never an exception -- capture must never break execution."""
    repo_str = str(repo)
    state = RepoState(repo=repo_str)
    if not Path(repo_str).is_dir():
        state.capture_error = f"not a directory: {repo_str}"
        return state

    rc, out, err = _git(repo_str, "rev-parse", "--is-inside-work-tree")
    if rc != 0 or out.strip() != "true":
        state.capture_error = f"not a git work tree: {err.strip() or out.strip()}"
        return state

    rc, out, err = _git(repo_str, "rev-parse", "HEAD")
    if rc != 0:
        state.capture_error = f"cannot read HEAD: {err.strip()}"
        return state
    state.commit = out.strip()

    rc, out, _ = _git(repo_str, "rev-parse", "--abbrev-ref", "HEAD")
    state.branch = out.strip() if rc == 0 else None

    rc, out, _ = _git(repo_str, "status", "--porcelain")
    state.dirty = [ln for ln in out.splitlines() if ln.strip()] if rc == 0 else []
    state.available = True
    return state


def _parse_name_status(text: str) -> list[dict[str, str]]:
    """Parse `git diff --name-status` into {status, path} records."""
    changes: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        # Rename/copy records carry two paths (R100\told\tnew); keep the new one
        # as the path and preserve the original in `from_path`.
        record = {"status": parts[0].strip(), "path": parts[-1].strip()}
        if len(parts) >= 3:
            record["from_path"] = parts[1].strip()
        changes.append(record)
    return changes


def _dirty_paths(porcelain: list[str]) -> set[str]:
    """Paths from `git status --porcelain` lines (handles renames: 'A -> B')."""
    paths: set[str] = set()
    for line in porcelain:
        entry = line[3:].strip() if len(line) > 3 else ""
        if not entry:
            continue
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1].strip()
        paths.add(entry.strip('"'))
    return paths


def observe_changes(
    repo: str | Path,
    base_commit: str | None,
    *,
    pre_existing_dirty: Iterable[str] = (),
) -> dict[str, Any]:
    """Diff `base_commit` against the CURRENT working tree of `repo`.

    Uses `git diff <base>` (not `<base>..HEAD`) so uncommitted work is captured
    too -- a worker that edits without committing has still produced evidence.

    ATTRIBUTION HAZARD (found in review, LISA-I005): a repository that was
    already dirty before execution would otherwise have that pre-existing work
    credited to the worker, because a diff against the base commit cannot tell
    who made an edit or when. `pre_existing_dirty` is the working-tree state
    observed BEFORE the worker ran; paths in it are recorded and excluded from
    `attributed_files_changed`. The raw `files_changed` is still reported in
    full -- nothing is hidden, but nothing is falsely attributed either.

    Untracked files cannot appear in a git diff; they are enumerated separately
    and that limitation is stated on the artifact rather than hidden.
    """
    observation: dict[str, Any] = {
        "files_changed": [],
        "attributed_files_changed": [],
        "pre_existing_dirty": sorted(set(pre_existing_dirty)),
        "untracked_files": [],
        "patch_text": "",
        "changed": False,
        "patch_covers_untracked": False,
        "capture_error": None,
    }
    if not base_commit:
        observation["capture_error"] = "no base commit observed before execution"
        return observation

    rc, out, err = _git(repo, "diff", "--name-status", base_commit)
    if rc != 0:
        observation["capture_error"] = f"git diff --name-status failed: {err.strip()}"
        return observation
    observation["files_changed"] = _parse_name_status(out)

    rc, patch, err = _git(repo, "diff", base_commit)
    if rc != 0:
        observation["capture_error"] = f"git diff failed: {err.strip()}"
        return observation
    observation["patch_text"] = patch

    rc, out, _ = _git(repo, "status", "--porcelain")
    if rc == 0:
        already = set(observation["pre_existing_dirty"])
        observation["untracked_files"] = [
            ln[3:].strip() for ln in out.splitlines()
            if ln.startswith("??") and ln[3:].strip() not in already
        ]

    # Attribution: only changes NOT already present before execution.
    stale = set(observation["pre_existing_dirty"])
    observation["attributed_files_changed"] = [
        change for change in observation["files_changed"]
        if change.get("path") not in stale
    ]

    # `changed` reflects what is ATTRIBUTABLE to this execution, so a package
    # that touched nothing is never recorded as having changed the repository
    # merely because the tree was dirty when it started.
    observation["changed"] = bool(
        observation["attributed_files_changed"] or observation["untracked_files"]
    )
    return observation


# --------------------------------------------------------------------------- #
# Declared evidence (worker-supplied -- the untrusted half)
# --------------------------------------------------------------------------- #

def declared_path(package_id: str, *, store: str | Path = DEFAULT_STORE) -> Path:
    """Deterministic path at which a worker may write its declaration."""
    return Path(store) / DECLARED_DIRNAME / f"{_safe_component(package_id)}.json"


def load_declared(package_id: str, *, store: str | Path = DEFAULT_STORE) -> tuple[dict | None, str | None]:
    """Read a worker declaration if present.

    Returns (declared, problem). A missing declaration is NOT an error -- it is
    a recorded fact (the observed half stands alone). Malformed or
    out-of-vocabulary content yields declared=None plus a problem string, so a
    worker can never inject unvalidated structure into evidence.
    """
    path = declared_path(package_id, store=store)
    if not path.is_file():
        return None, "no worker declaration was written"
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"worker declaration unreadable: {exc}"
    if not isinstance(raw, dict):
        return None, "worker declaration is not a JSON object"
    unknown = sorted(set(raw) - DECLARED_KEYS)
    if unknown:
        return None, f"worker declaration has unpermitted key(s): {unknown}"
    return raw, None


# --------------------------------------------------------------------------- #
# The artifact
# --------------------------------------------------------------------------- #

def _safe_component(value: str) -> str:
    """Filesystem-safe path component (never traverses, never empty)."""
    cleaned = "".join(c if (c.isalnum() or c in "._-") else "-" for c in str(value))
    cleaned = cleaned.strip("-.") or "unnamed"
    return cleaned[:96]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_work_product(
    *,
    package_id: str,
    status: str,
    worker: dict[str, Any],
    observed: dict[str, Any],
    declared: dict[str, Any] | None = None,
    discrepancies: Iterable[str] = (),
    context: dict[str, Any] | None = None,
    capture_error: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> dict[str, Any]:
    """Assemble a Work Product dict. Pure: no I/O, no interpretation."""
    return {
        "schema_version": SCHEMA_VERSION,
        "work_product_id": uuid.uuid4().hex,
        "package_id": package_id,
        "status": status,
        "created_at": _utc_now(),
        "started_at": started_at,
        "ended_at": ended_at,
        "worker": dict(worker),
        "observed": dict(observed),
        "declared": dict(declared) if declared is not None else None,
        "discrepancies": list(discrepancies),
        "context": dict(context or {}),
        "capture_error": capture_error,
    }


# --------------------------------------------------------------------------- #
# Validation -- fail closed
# --------------------------------------------------------------------------- #

_TOP_LEVEL_KEYS = frozenset({
    "schema_version", "work_product_id", "package_id", "status", "created_at",
    "started_at", "ended_at", "worker", "observed", "declared",
    "discrepancies", "context", "capture_error",
})

_OBSERVED_KEYS = frozenset({
    "repo", "branch", "base_commit", "head_commit", "files_changed",
    "attributed_files_changed", "pre_existing_dirty",
    "untracked_files", "patch_path", "patch_sha256", "patch_bytes",
    "changed", "patch_covers_untracked", "available", "capture_error",
})


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_test_evidence(entry: Any, idx: int) -> list[str]:
    """Validate one declared test record. Structural only -- never judges
    whether the tests were adequate, only whether the evidence is well formed."""
    errors: list[str] = []
    tag = f"T[{idx}]"
    if not isinstance(entry, dict):
        return [f"{tag}: test evidence must be an object, got {type(entry).__name__}"]
    if not _is_nonempty_str(entry.get("command")):
        errors.append(f"{tag}: 'command' must be a non-empty string")
    result = entry.get("result")
    if result not in TEST_RESULTS:
        errors.append(f"{tag}: 'result' {result!r} must be one of {TEST_RESULTS}")
    duration = entry.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
        errors.append(f"{tag}: 'duration_seconds' must be a non-negative number")
    for count_key in ("passed", "failed", "skipped"):
        count = entry.get(count_key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(f"{tag}: {count_key!r} must be a non-negative integer")
    if not _is_nonempty_str(entry.get("environment")):
        errors.append(f"{tag}: 'environment' must be a non-empty string")
    # Internal coherence: a declared pass cannot carry failures.
    if result == "pass" and isinstance(entry.get("failed"), int) and entry["failed"] > 0:
        errors.append(f"{tag}: result 'pass' contradicts failed={entry['failed']}")
    return errors


def validate_work_product(
    work_product: Any, *, store: str | Path = DEFAULT_STORE, verify_patch: bool = True
) -> dict[str, Any]:
    """Return the Work Product if valid; raise WorkProductValidationError with
    EVERY violation otherwise. Fail closed -- incomplete evidence is rejected,
    never partially accepted."""
    errors: list[str] = []

    if not isinstance(work_product, dict):
        raise WorkProductValidationError(
            "work product must be an object",
            [f"V0: top level must be a dict, got {type(work_product).__name__}"],
        )

    # V1 schema
    if work_product.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"V1: unknown schema_version {work_product.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION!r}"
        )
    # V10 no unknown top-level keys
    unknown = sorted(set(work_product) - _TOP_LEVEL_KEYS)
    if unknown:
        errors.append(f"V10: unknown top-level key(s): {unknown}")

    # V2 package id
    if not _is_nonempty_str(work_product.get("package_id")):
        errors.append("V2: 'package_id' is required and must be a non-empty string")
    if not _is_nonempty_str(work_product.get("work_product_id")):
        errors.append("V2: 'work_product_id' is required and must be a non-empty string")

    # V3 status
    status = work_product.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"V3: invalid status {status!r}; must be one of {VALID_STATUSES}")

    # V9 timestamps
    if not _is_nonempty_str(work_product.get("created_at")):
        errors.append("V9: 'created_at' is required")

    # V4 worker identity
    worker = work_product.get("worker")
    if not isinstance(worker, dict):
        errors.append("V4: 'worker' must be an object")
    else:
        if not _is_nonempty_str(worker.get("employee")):
            errors.append("V4: worker.employee is required")
        # agent_id is legitimately absent for simulated execution, but then the
        # provenance must say so -- an unattributed real execution is invalid.
        provenance = worker.get("provenance")
        if not _is_nonempty_str(worker.get("agent_id")) and provenance == "worker-real":
            errors.append(
                "V4: worker.agent_id is required when provenance is 'worker-real'"
            )

    # V5-V7 observation
    observed = work_product.get("observed")
    if not isinstance(observed, dict):
        errors.append("V5: 'observed' must be an object")
        observed = {}
    else:
        unknown_obs = sorted(set(observed) - _OBSERVED_KEYS)
        if unknown_obs:
            errors.append(f"V5: unknown observed key(s): {unknown_obs}")
        if not _is_nonempty_str(observed.get("repo")):
            errors.append("V5: observed.repo is required")
        if observed.get("available") is False and not _is_nonempty_str(
            observed.get("capture_error")
        ):
            errors.append(
                "V5: observed.available is false but no capture_error explains why"
            )

    files_changed = observed.get("files_changed")
    untracked = observed.get("untracked_files", [])
    if not isinstance(files_changed, list):
        errors.append("V6: observed.files_changed must be a list")
        files_changed = []
    else:
        for i, item in enumerate(files_changed):
            if not isinstance(item, dict) or not _is_nonempty_str(item.get("path")):
                errors.append(f"V6: files_changed[{i}] must be an object with a 'path'")
    if not isinstance(untracked, list):
        errors.append("V6: observed.untracked_files must be a list")
        untracked = []

    # Attribution: what this execution is actually credited with. Defaults to
    # files_changed for artifacts written before attribution existed.
    attributed = observed.get("attributed_files_changed")
    if attributed is None:
        attributed = files_changed
    elif not isinstance(attributed, list):
        errors.append("V6: observed.attributed_files_changed must be a list")
        attributed = []
    if not isinstance(observed.get("pre_existing_dirty", []), list):
        errors.append("V6: observed.pre_existing_dirty must be a list")

    # A claim of change with nothing changed (or vice versa) is incoherent
    # evidence -- this is the "missing files changed" rejection. It is checked
    # against ATTRIBUTED changes, so pre-existing repository dirt can neither
    # invent nor mask a claim of work.
    changed = observed.get("changed")
    if isinstance(changed, bool):
        actually = bool(attributed or untracked)
        if changed != actually:
            errors.append(
                f"V6: observed.changed={changed} contradicts "
                f"{len(attributed)} attributed file(s) and {len(untracked)} untracked"
            )
    else:
        errors.append("V6: observed.changed must be a boolean")

    # V7 patch reference integrity
    patch_path = observed.get("patch_path")
    if files_changed:
        if not _is_nonempty_str(patch_path):
            errors.append("V7: files were changed but no patch_path was recorded")
        elif verify_patch:
            resolved = Path(patch_path)
            if not resolved.is_absolute():
                resolved = Path(store) / resolved
            if not resolved.is_file():
                errors.append(f"V7: patch reference does not resolve: {patch_path}")
            else:
                digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if digest != observed.get("patch_sha256"):
                    errors.append(
                        "V7: patch sha256 mismatch -- recorded "
                        f"{observed.get('patch_sha256')!r}, actual {digest!r}"
                    )
                size = resolved.stat().st_size
                if observed.get("patch_bytes") != size:
                    errors.append(
                        f"V7: patch_bytes {observed.get('patch_bytes')!r} != actual {size}"
                    )
    elif patch_path:
        errors.append("V7: patch_path recorded but no files were changed")

    # V8/V11 declared evidence (untrusted, optional)
    declared = work_product.get("declared")
    if declared is not None:
        if not isinstance(declared, dict):
            errors.append("V11: 'declared' must be an object or null")
        else:
            unknown_declared = sorted(set(declared) - DECLARED_KEYS)
            if unknown_declared:
                errors.append(f"V11: unpermitted declared key(s): {unknown_declared}")
            tests = declared.get("tests")
            if tests is not None:
                if not isinstance(tests, list):
                    errors.append("V8: declared.tests must be a list")
                else:
                    for i, entry in enumerate(tests):
                        errors.extend(validate_test_evidence(entry, i))
            for list_key in ("risks", "warnings", "deferred"):
                value = declared.get(list_key)
                if value is not None and not (
                    isinstance(value, list) and all(isinstance(x, str) for x in value)
                ):
                    errors.append(f"V11: declared.{list_key} must be a list of strings")
            summary = declared.get("summary")
            if summary is not None and not isinstance(summary, str):
                errors.append("V11: declared.summary must be a string")

    # V12 discrepancies
    discrepancies = work_product.get("discrepancies")
    if not isinstance(discrepancies, list) or not all(
        isinstance(x, str) for x in discrepancies
    ):
        errors.append("V12: 'discrepancies' must be a list of strings")

    if errors:
        raise WorkProductValidationError(
            f"work product rejected ({len(errors)} violation(s))", errors
        )
    return work_product


# --------------------------------------------------------------------------- #
# Reconciliation -- observation wins, disagreement is recorded
# --------------------------------------------------------------------------- #

def reconcile(observed: dict[str, Any], declared: dict[str, Any] | None) -> list[str]:
    """Compare declared claims against observed reality.

    Returns discrepancy strings. This NEVER edits either side: the point is to
    surface conflict for a later reviewer, not to resolve it.
    """
    notes: list[str] = []
    if declared is None:
        return notes

    changed = bool(observed.get("changed"))
    summary = declared.get("summary")
    if isinstance(summary, str) and summary.strip() and not changed:
        notes.append(
            "worker declared a summary of work but no repository change was observed"
        )

    tests = declared.get("tests")
    if isinstance(tests, list) and tests:
        failing = [t for t in tests if isinstance(t, dict) and t.get("result") in ("fail", "error")]
        if failing:
            notes.append(
                f"worker declared {len(failing)} failing/erroring test run(s)"
            )
    elif changed:
        notes.append("repository changed but the worker declared no test evidence")

    return notes


# --------------------------------------------------------------------------- #
# Storage -- reuses the existing orchestration evidence tree
# --------------------------------------------------------------------------- #

def _index_path(store: str | Path) -> Path:
    return Path(store) / INDEX_NAME


def write_work_product(
    work_product: dict[str, Any],
    *,
    patch_text: str = "",
    store: str | Path = DEFAULT_STORE,
    validate: bool = True,
) -> dict[str, str]:
    """Persist the artifact (+ patch) and append one index line.

    The patch is written FIRST so the artifact's hash/size reference is true at
    the moment the artifact is validated and stored -- an artifact never points
    at a patch that does not yet exist.
    """
    store_dir = Path(store)
    store_dir.mkdir(parents=True, exist_ok=True)

    package = _safe_component(work_product.get("package_id", "unknown"))
    run_ref = _safe_component(
        (work_product.get("worker") or {}).get("run_id")
        or work_product.get("work_product_id", "norun")
    )[:12]
    stem = f"{package}__{run_ref}"

    observed = work_product.setdefault("observed", {})
    if patch_text:
        patch_file = store_dir / f"{stem}.patch"
        data = patch_text.encode("utf-8")
        patch_file.write_bytes(data)
        observed["patch_path"] = str(patch_file)
        observed["patch_sha256"] = hashlib.sha256(data).hexdigest()
        observed["patch_bytes"] = len(data)
    else:
        observed.setdefault("patch_path", None)
        observed.setdefault("patch_sha256", None)
        observed.setdefault("patch_bytes", 0)

    if validate:
        validate_work_product(work_product, store=store_dir)

    artifact = store_dir / f"{stem}.json"
    artifact.write_text(json.dumps(work_product, indent=2, sort_keys=False))

    # Discovery index: one append-only line, keyed on every axis a human or a
    # later phase might search by (package / job / sprint / worker).
    context = work_product.get("context") or {}
    worker = work_product.get("worker") or {}
    index_record = {
        "work_product_id": work_product.get("work_product_id"),
        "package_id": work_product.get("package_id"),
        "job_id": context.get("job_id"),
        "sprint": context.get("sprint"),
        "request_id": context.get("request_id"),
        "employee": worker.get("employee"),
        "agent_id": worker.get("agent_id"),
        "run_id": worker.get("run_id"),
        "status": work_product.get("status"),
        "changed": bool(observed.get("changed")),
        "created_at": work_product.get("created_at"),
        "artifact_path": str(artifact),
        "patch_path": observed.get("patch_path"),
    }
    with open(_index_path(store_dir), "a") as fh:
        fh.write(json.dumps(index_record) + "\n")

    return {"artifact_path": str(artifact), "patch_path": observed.get("patch_path") or ""}


def load_work_product(path: str | Path) -> dict[str, Any]:
    """Load one artifact from disk (no validation -- call validate separately)."""
    try:
        return json.loads(Path(path).read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise WorkProductError(f"cannot load work product {path}: {exc}") from exc


def find_work_products(
    *,
    package_id: str | None = None,
    job_id: str | None = None,
    sprint: str | None = None,
    employee: str | None = None,
    agent_id: str | None = None,
    store: str | Path = DEFAULT_STORE,
) -> list[dict[str, Any]]:
    """Query the discovery index. Any combination of axes; all are ANDed."""
    index = _index_path(store)
    if not index.is_file():
        return []
    wanted = {
        "package_id": package_id, "job_id": job_id, "sprint": sprint,
        "employee": employee, "agent_id": agent_id,
    }
    wanted = {k: v for k, v in wanted.items() if v is not None}
    matches: list[dict[str, Any]] = []
    for line in index.read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # a corrupt line must not hide the rest of the evidence
        if all(record.get(k) == v for k, v in wanted.items()):
            matches.append(record)
    return matches


# --------------------------------------------------------------------------- #
# Review handoff -- assembly, NOT synthesis
# --------------------------------------------------------------------------- #

def build_review_bundle(
    work_product: dict[str, Any],
    *,
    store: str | Path = DEFAULT_STORE,
    include_patch_text: bool = True,
    max_patch_bytes: int = 512_000,
) -> dict[str, Any]:
    """Assemble everything a reviewer needs so it never has to rediscover the
    implementation from conversation history or OpenClaw logs.

    Deliberately performs NO interpretation: it selects and arranges existing
    evidence. Any summarising belongs to a later phase.

    The bundle is fail-closed: an invalid Work Product cannot be handed to
    review at all.
    """
    validate_work_product(work_product, store=store)

    observed = work_product.get("observed") or {}
    declared = work_product.get("declared")
    patch_text = None
    patch_truncated = False

    if include_patch_text and observed.get("patch_path"):
        patch_file = Path(observed["patch_path"])
        if not patch_file.is_absolute():
            patch_file = Path(store) / patch_file
        if patch_file.is_file():
            raw = patch_file.read_bytes()
            if len(raw) > max_patch_bytes:
                raw = raw[:max_patch_bytes]
                patch_truncated = True
            patch_text = raw.decode("utf-8", errors="replace")

    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_created_at": _utc_now(),
        "package_id": work_product.get("package_id"),
        "work_product_id": work_product.get("work_product_id"),
        "status": work_product.get("status"),
        "worker": work_product.get("worker"),
        "context": work_product.get("context"),
        "change": {
            "repo": observed.get("repo"),
            "branch": observed.get("branch"),
            "base_commit": observed.get("base_commit"),
            "head_commit": observed.get("head_commit"),
            "files_changed": observed.get("files_changed", []),
            "attributed_files_changed": observed.get(
                "attributed_files_changed", observed.get("files_changed", [])),
            "pre_existing_dirty": observed.get("pre_existing_dirty", []),
            "untracked_files": observed.get("untracked_files", []),
            "patch_path": observed.get("patch_path"),
            "patch_sha256": observed.get("patch_sha256"),
            "patch_text": patch_text,
            "patch_truncated": patch_truncated,
            "patch_covers_untracked": observed.get("patch_covers_untracked", False),
        },
        "declared": {
            "summary": (declared or {}).get("summary"),
            "tests": (declared or {}).get("tests", []),
            "risks": (declared or {}).get("risks", []),
            "warnings": (declared or {}).get("warnings", []),
            "deferred": (declared or {}).get("deferred", []),
        },
        "declaration_present": declared is not None,
        "discrepancies": work_product.get("discrepancies", []),
        "capture_error": work_product.get("capture_error"),
    }


# --------------------------------------------------------------------------- #
# The capture point: a Dispatcher ExecutorFn wrapper
# --------------------------------------------------------------------------- #

def work_product_recording_executor(
    inner: Callable | None = None,
    *,
    repo: str | Path | None = None,
    store: str | Path = DEFAULT_STORE,
    context: dict[str, Any] | None = None,
) -> Callable:
    """Wrap a Dispatcher ExecutorFn so every executed package yields evidence.

    Mirrors `core.capacity_ledger.ledger_recording_executor` exactly, so it
    composes with it and requires NO dispatcher change:

        executor = work_product_recording_executor(
            ledger_recording_executor(ledger, inner=real_executor), repo=...)

    Guarantees:
      * provenance is INHERITED from `inner`, never invented;
      * the inner ExecutionResult is returned UNMODIFIED -- capture is a
        passive observer and can neither pass nor fail a package;
      * no capture failure can escape: evidence problems are recorded on the
        artifact (or dropped with a printed warning) rather than crashing a
        dispatch batch after real spend.
    """
    if inner is None:
        raise ValueError(
            "work_product_recording_executor requires an explicit inner executor"
        )

    from core.dispatcher import executor_provenance, mark_executor

    inner_provenance = executor_provenance(inner)
    if inner_provenance is None:
        raise ValueError(
            "work_product_recording_executor requires an inner executor with a "
            "declared provenance -- wrap it with core.dispatcher.mark_executor("
            "fn, WORKER_REAL | WORKER_SIMULATED | MAIN_INLINE) first. Wrapping "
            "must never invent an attribution the inner executor did not claim."
        )

    repo_path = str(repo) if repo is not None else os.getcwd()

    def _executor(work_package, assignment):
        started_at = _utc_now()
        before = capture_repo_state(repo_path)

        # The inner executor owns success/failure entirely. Capture never
        # interferes with it, before or after.
        result = inner(work_package, assignment)

        try:
            _record(
                work_package=work_package,
                assignment=assignment,
                result=result,
                before=before,
                repo_path=repo_path,
                store=store,
                context=context,
                started_at=started_at,
                provenance=inner_provenance,
            )
        except Exception as exc:  # capture must never break a dispatch batch
            print(
                f"WARNING: work product capture failed for "
                f"{getattr(work_package, 'id', '?')}: {exc!r}"
            )
        return result

    return mark_executor(_executor, inner_provenance)


def _record(
    *, work_package, assignment, result, before: RepoState, repo_path: str,
    store: str | Path, context: dict[str, Any] | None, started_at: str,
    provenance: str,
) -> dict[str, str]:
    """Build, validate and persist the Work Product for one executed package."""
    ended_at = _utc_now()
    after = capture_repo_state(repo_path)
    # Pass the PRE-execution dirty set so ambient repository state is never
    # attributed to this worker (see observe_changes' attribution hazard note).
    changes = observe_changes(
        repo_path, before.commit, pre_existing_dirty=_dirty_paths(before.dirty),
    )

    capture_error = before.capture_error or after.capture_error or changes.get("capture_error")

    observed = {
        "repo": repo_path,
        "branch": after.branch or before.branch,
        "base_commit": before.commit,
        "head_commit": after.commit,
        "files_changed": changes["files_changed"],
        "attributed_files_changed": changes["attributed_files_changed"],
        "pre_existing_dirty": changes["pre_existing_dirty"],
        "untracked_files": changes["untracked_files"],
        "changed": changes["changed"],
        "patch_covers_untracked": False,  # git diff cannot include untracked files
        "available": bool(before.available and after.available),
        "capture_error": capture_error,
    }

    package_id = getattr(work_package, "id", "unknown")
    declared, declared_problem = load_declared(package_id, store=store)

    discrepancies = reconcile(observed, declared)
    if declared_problem:
        discrepancies.append(declared_problem)
    if observed["untracked_files"]:
        discrepancies.append(
            f"{len(observed['untracked_files'])} untracked file(s) are not "
            "represented in the patch (git diff cannot include them)"
        )
    if observed["pre_existing_dirty"]:
        discrepancies.append(
            f"repository was already dirty before execution "
            f"({len(observed['pre_existing_dirty'])} path(s)); those changes are "
            "excluded from attribution but remain visible in the patch"
        )

    if getattr(result, "success", False):
        status = STATUS_COMPLETED
    elif result is None:
        status = STATUS_NO_EXECUTION
    else:
        status = STATUS_FAILED

    worker = {
        "employee": getattr(assignment, "employee", None) or "unknown",
        "logical": getattr(assignment, "resolved_logical", None),
        "agent_id": getattr(result, "agent_id", None),
        "run_id": getattr(result, "run_id", None),
        "model": getattr(result, "observed_model", None)
                 or getattr(assignment, "physical_model", None),
        "provider": getattr(result, "observed_provider", None)
                    or getattr(assignment, "provider_id", None),
        "runtime": getattr(result, "actual_runtime", None)
                   or getattr(assignment, "resolved_runtime", None),
        "provenance": provenance,
        "execution_error": getattr(result, "error", None),
    }

    work_product = build_work_product(
        package_id=package_id,
        status=status,
        worker=worker,
        observed=observed,
        declared=declared,
        discrepancies=discrepancies,
        context=context,
        capture_error=capture_error,
        started_at=started_at,
        ended_at=ended_at,
    )
    return write_work_product(
        work_product, patch_text=changes["patch_text"], store=store
    )

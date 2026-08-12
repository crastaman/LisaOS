"""LisaOS <-> OpenClaw real execution bridge (Phase 4 remediation).

Fixes reports/lisa/DELEGATION_ARCHITECTURE_AUDIT.md: the Phase 1-3 workforce
stack's only executor was `core.dispatcher.simulated_executor` (sleep 20ms,
report the assignment's own resolved_runtime back to itself). This module is
the real ExecutorFn that actually spawns work through OpenClaw.

DISCOVERY DURING IMPLEMENTATION (see reports/lisa/PHASE4_IMPLEMENTATION_REPORT.md):
`openclaw agent --model <id>` is REJECTED by the Gateway for every agent
("Model override ... is not allowed for agent '<id>'"), not just `main`. The
handoff's assumed mechanism (free `--model` override) does not exist. The
real, sanctioned mechanism OpenClaw supports is: pick the pre-configured
AGENT IDENTITY whose *own default model* already matches the physical model
LisaOS resolved, and invoke that agent with no override. This module
therefore maps physical_model -> agent id (derived LIVE from
`openclaw agents list --json`, never hardcoded) instead of trying to force a
model onto an arbitrary agent.

Repository scoping: only agents NOT prefixed `wbs-` are eligible. The WBS
repository and its dedicated OpenClaw agents are out of scope for LisaOS
work (see memory: lisaos-standing-instructions). If no non-WBS agent is
bound to a resolved physical model, this bridge FAILS CLOSED with an
explicit reason -- it never overrides a model, never substitutes a WBS
agent, and never falls back to simulation.

Ground truth cross-check: a top-level `openclaw agent` CLI call records a
`task_runs` row (runtime='cli'), keyed by the `runId` the CLI itself returns
in its --json response. It does NOT create a `subagent_runs` row (that table
is for an agent's own internal `subagents` tool spawns, a different code
path). Verified empirically 2026-07-09 by a live probe call and a direct
query of ~/.openclaw/state/openclaw.sqlite.

WORKFORCE IDENTITY REMEDIATION (see reports/lisa/
WORKFORCE_IDENTITY_REMEDIATION_REPORT.md): execution identity is now
`employee -> OpenClaw agent -> physical model`. Each logical identity has
exactly ONE dedicated agent (registry `agent:` binding), and dispatch selects
that agent deterministically via `agent_for_logical()`. The prohibited
physical-model REVERSE MATCH (which collapsed codex/gpt onto one agent) is no
longer used for selection. `validate_identity_map()` enforces single-source-
of-truth against openclaw.json.

WORKFORCE TRUTH HOTFIX (see reports/lisa/CTO_WORKFORCE_GOVERNANCE_REVIEW.md):
`codex` and `gpt` both resolve to physical_model `openai/gpt-5.5`. Routing
was always correct (agent selection uses `assignment.physical_model`
directly), but the reverse-lookup used to LABEL `actual_runtime` post-
execution collapsed the two, mislabelling a correct codex dispatch as "gpt".
Fixed by deriving the label from the assignment's own resolved runtime when
there is no genuine physical-model drift, and reserving the reverse index
for genuine drift only. No routing, mismatch-detection, or success-semantics
change.

PHASE 5 HARDENING (see reports/lisa/DELEGATION_HARDENING_AUDIT.md, R1/R2):
two defects found in this module after Phase 4/4b went live were fixed here:
  * R1 -- mismatch detection compared the AGENT'S CONFIGURED BINDING against
    the resolved model, which is tautological (the agent was selected
    because that binding equals the resolved model, so it could never
    disagree). It now compares OpenClaw's own runtime-reported
    `executionTrace.winnerModel`/`fallbackUsed` -- the real signal -- against
    the resolved model, via a registry-derived short-id index.
  * R2 -- the success path made a second, unguarded `openclaw agents list`
    call (which could raise) after a paid run had already returned. That
    call is gone (T1's fix removed the need for it), and the whole executor
    body is now wrapped so no unexpected exception can escape and crash a
    dispatch batch after spend.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.dispatcher import ExecutionResult
from core.execution_state import (
    COMMAND_FAILED,
    COMMAND_OK,
    COMMAND_TIMED_OUT,
    DISPATCH_ACKNOWLEDGED,
    DISPATCH_REJECTED,
    EXEC_COMPLETED,
    EXEC_FAILED,
    EXEC_UNKNOWN,
    RESULT_INGESTED,
    RESULT_UNKNOWN,
    SESSION_UNKNOWN,
    TerminalEvidence,
    classify_execution_source,
    requires_reconciliation,
)
from core.provider_resolver import ProviderResolver
from core.reliability_config import load_reliability_config

# --------------------------------------------------------------------------- #
# Paths / binaries
# --------------------------------------------------------------------------- #

OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN") or shutil.which("openclaw") or "/opt/homebrew/bin/openclaw"
OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))
OPENCLAW_DB = OPENCLAW_HOME / "state" / "openclaw.sqlite"

DEFAULT_TIMEOUT_SECONDS = 240  # real OpenClaw turns run minutes, not ms (see report)
_SUBPROCESS_GRACE_SECONDS = 20  # extra headroom over --timeout before we give up waiting

# Single source of truth lives in core.dispatcher; re-exported here so
# existing importers of this module keep working (r4).
SIMULATED_LABEL = "SIMULATED-NOT-EXECUTED"  # must equal core.dispatcher.SIMULATED_LABEL


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class BridgeError(Exception):
    """Raised for a bridge-internal fault (not a normal fail-closed outcome)."""


# --------------------------------------------------------------------------- #
# Live agent inventory (never hardcoded -- always re-derived)
# --------------------------------------------------------------------------- #

def list_agents(*, timeout: int = 15) -> list[dict[str, Any]]:
    """Return `openclaw agents list --json` parsed, or raise BridgeError."""
    try:
        proc = subprocess.run(
            [OPENCLAW_BIN, "agents", "list", "--json"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BridgeError(f"could not run 'openclaw agents list': {exc}") from exc
    if proc.returncode != 0:
        raise BridgeError(f"'openclaw agents list' failed: {proc.stderr.strip()[:300]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"'openclaw agents list --json' returned invalid JSON: {exc}") from exc


def non_wbs_agents(*, timeout: int = 15) -> list[dict[str, Any]]:
    """Agents eligible for LisaOS dispatch -- excludes every `wbs-*` identity."""
    return [a for a in list_agents(timeout=timeout) if not str(a.get("id", "")).startswith("wbs-")]


def _select_agent(agents: list[dict[str, Any]], physical_model: str) -> str | None:
    """Pure selection: first agent in an already-fetched, already-filtered
    list whose own default model matches `physical_model`. Split out from
    `agent_for_physical_model` so the real executor can fetch the agent list
    ONCE per execution and reuse it, instead of calling `openclaw agents
    list` a second time (Phase 5 hardening, R2)."""
    for agent in agents:
        if agent.get("model") == physical_model:
            return agent.get("id")
    return None


def agent_for_physical_model(physical_model: str, *, timeout: int = 15) -> str | None:
    """VALIDATION ONLY -- NOT dispatch selection. First non-WBS agent whose own
    default model matches `physical_model`.

    Workforce Identity Remediation: this physical-model REVERSE MATCH is
    PROHIBITED as a dispatch-selection mechanism (it collapses distinct logical
    identities that share a physical model -- e.g. codex/gpt both openai/gpt-5.5
    -- onto one agent). Dispatch now uses the deterministic
    `agent_for_logical()` map below. This function is retained only for drift
    validation (`validate_identity_map`) and back-compat tests.
    """
    return _select_agent(non_wbs_agents(timeout=timeout), physical_model)


def agent_for_logical(resolved_logical: str | None, resolver: ProviderResolver) -> str | None:
    """DETERMINISTIC dispatch selection: logical identity -> its ONE dedicated
    OpenClaw agent, from the explicit `agent:` binding in
    registry/provider_resolution.yml. No physical-model reverse match, so two
    logical identities on the same physical model (codex/gpt -> openai/gpt-5.5)
    resolve to DISTINCT agents (lisa-codex / lisa-gpt) and can never collapse.

    Returns None if the logical identity has no `agent` binding -- the caller
    must then fail closed (never guess, never reverse-match).
    """
    if not resolved_logical:
        return None
    spec = (resolver.config.get("providers", {}) or {}).get(resolved_logical, {}) or {}
    return spec.get("agent")


def validate_identity_map(resolver: ProviderResolver, *, timeout: int = 15) -> list[str]:
    """Single-source-of-truth / drift check (Workforce Identity Remediation).

    For every logical provider in the registry, verify:
      1. it declares an `agent:` binding (no logical provider without an agent);
      2. that agent actually exists in OpenClaw (`agents list`);
      3. the agent is a dedicated identity (not a shared general agent
         main/documentation/architecture/engineering/qa, and not wbs-*);
      4. the agent's pinned model == the registry's physical_model
         (openclaw.json is the source of truth; registry must not drift from it).
    Returns a list of problems; empty == the identity map is coherent.
    """
    problems: list[str] = []
    try:
        live = {a.get("id"): a.get("model") for a in list_agents(timeout=timeout)}
    except BridgeError as exc:
        return [f"cannot enumerate OpenClaw agents: {exc}"]
    shared_general = {"main", "documentation", "architecture", "engineering", "qa"}
    for logical, spec in (resolver.config.get("providers", {}) or {}).items():
        agent = (spec or {}).get("agent")
        phys = (spec or {}).get("physical_model")
        if not agent:
            problems.append(f"{logical}: no `agent` binding (logical provider without a dedicated agent)")
            continue
        if agent in shared_general or str(agent).startswith("wbs-"):
            problems.append(f"{logical}: bound to non-dedicated agent {agent!r}")
        if agent not in live:
            problems.append(f"{logical}: agent {agent!r} does not exist in OpenClaw")
            continue
        if live[agent] != phys:
            problems.append(
                f"{logical}: DRIFT -- registry physical_model {phys!r} != "
                f"OpenClaw agent {agent!r} model {live[agent]!r}")
    return problems


# --------------------------------------------------------------------------- #
# Gateway reachability (real health check, not credential-presence)
#
# Fixes the audit's health-semantics finding: ProviderResolver.evaluate()
# only checks that a credential FILE/ENV VAR is present, never that anything
# is actually reachable. This function is a genuine, live check against the
# running Gateway. It does not replace or modify ProviderResolver (which 220+
# existing tests depend on for its credential-presence contract) -- it is an
# additional preflight the real executor performs before it will spend money.
# Residual gap (documented, not fixed here): this proves the GATEWAY is
# reachable, not that every individual provider's upstream API is currently
# reachable -- that would require a live, cost-incurring probe per provider
# on every dispatch tick, which is out of scope for a preflight.
# --------------------------------------------------------------------------- #

def gateway_reachable(*, timeout_ms: int = 5000) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            [OPENCLAW_BIN, "health", "--json", "--timeout", str(timeout_ms)],
            capture_output=True, text=True, timeout=(timeout_ms / 1000) + 5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"health check failed to run: {exc}"
    if proc.returncode != 0:
        return False, f"gateway health check exited {proc.returncode}: {proc.stderr.strip()[:300]}"
    return True, "ok"


# --------------------------------------------------------------------------- #
# Physical model -> (canonical logical, runtime) reverse index
# (read-only; built from the same registry/provider_resolution.yml the
# resolver already uses -- this module never edits that file)
# --------------------------------------------------------------------------- #

def _physical_model_index(resolver: ProviderResolver) -> dict[str, tuple[str, str | None]]:
    index: dict[str, tuple[str, str | None]] = {}
    for canonical, spec in (resolver.config.get("providers", {}) or {}).items():
        phys = spec.get("physical_model")
        if phys:
            index[phys] = (canonical, spec.get("runtime"))
    return index


# --------------------------------------------------------------------------- #
# Ground-truth cross-check against openclaw.sqlite (READ-ONLY, always)
# --------------------------------------------------------------------------- #

def _fetch_task_run(run_id: str, *, timeout: float = 5.0) -> dict[str, Any] | None:
    if not OPENCLAW_DB.is_file():
        return None
    uri = f"file:{OPENCLAW_DB}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=timeout)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT task_id, runtime, agent_id, run_id, status, task, "
                "created_at, started_at, ended_at, error "
                "FROM task_runs WHERE run_id = ? LIMIT 1",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return dict(row) if row else None


def _extract_run_id(text: str | bytes | None) -> str | None:
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8", errors="replace")
        except Exception:
            return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    value = payload.get("runId") if isinstance(payload, dict) else None
    return str(value) if value else None


def _find_task_run_for_invocation(
    *,
    agent_id: str,
    session_key: str,
    task: str,
    created_after_ms: int,
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    if not OPENCLAW_DB.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{OPENCLAW_DB}?mode=ro", uri=True, timeout=timeout)
        conn.row_factory = sqlite3.Row
        try:
            cols = _db_columns(conn, "task_runs")
            where = ["agent_id = ?", "created_at >= ?"]
            args: list[Any] = [agent_id, created_after_ms]
            if "session_key" in cols:
                where.append("session_key = ?")
                args.append(session_key)
            if "task" in cols:
                where.append("task = ?")
                args.append(task)
            row = conn.execute(
                "SELECT run_id, status, agent_id, created_at FROM task_runs "
                f"WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT 1",
                tuple(args),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _db_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _lifecycle_columns_available(path: Path | None = None) -> bool:
    target = path or OPENCLAW_DB
    if not target.is_file():
        return False
    try:
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True, timeout=5.0)
        try:
            cols = _db_columns(conn, "task_runs")
            return {
                "dispatch_state",
                "execution_state",
                "session_state",
                "result_state",
                "requires_reconciliation",
                "terminal_evidence",
                "command_state",
            }.issubset(cols)
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _update_task_run_lifecycle(
    run_id: str | None,
    *,
    dispatch_state: str,
    execution_state: str,
    session_state: str,
    result_state: str,
    requires_reconciliation_flag: bool,
    terminal_evidence: dict[str, Any] | None,
    command_state: str,
    timeout: float = 5.0,
) -> bool:
    """Persist Wave-1 lifecycle columns for a task_runs row when available.

    The migration is additive and may not yet be applied in every local DB.
    Missing DB, missing row, or missing columns fail closed to False without
    crashing dispatch; tests/migration gates assert the write path on a temp DB.
    """
    if not run_id or not OPENCLAW_DB.is_file():
        return False
    try:
        conn = sqlite3.connect(str(OPENCLAW_DB), timeout=timeout)
        try:
            cols = _db_columns(conn, "task_runs")
            required = {
                "dispatch_state",
                "execution_state",
                "session_state",
                "result_state",
                "requires_reconciliation",
                "terminal_evidence",
                "command_state",
            }
            if not required.issubset(cols):
                return False
            cur = conn.execute(
                """
                UPDATE task_runs
                   SET dispatch_state = ?,
                       execution_state = ?,
                       session_state = ?,
                       result_state = ?,
                       requires_reconciliation = ?,
                       terminal_evidence = ?,
                       command_state = ?
                 WHERE run_id = ?
                """,
                (
                    dispatch_state,
                    execution_state,
                    session_state,
                    result_state,
                    1 if requires_reconciliation_flag else 0,
                    json.dumps(terminal_evidence or {}, separators=(",", ":")),
                    command_state,
                    run_id,
                ),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def _artifact_evidence_for(work_package) -> tuple[dict[str, Any] | None, bool]:
    path = getattr(work_package, "expected_artifact_path", None)
    if not path:
        return None, True
    target = Path(path)
    if target.exists():
        return {"path": str(target), "exists": True}, True
    return {"path": str(target), "exists": False}, False


def _result_for_source(
    *,
    success: bool,
    error: str,
    evidence_source: str,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> ExecutionResult:
    """Build a lifecycle-aware bridge result for non-success paths.

    Pre-dispatch failures remain authoritative FAILED. Any post-invocation
    transport ambiguity becomes EXECUTION_UNKNOWN, preserving RC003's core
    invariant: no proof of failure is not proof execution stopped.
    """
    execution_state = classify_execution_source(evidence_source)
    if execution_state is None:
        execution_state = EXEC_COMPLETED if success else EXEC_FAILED
    command_state = COMMAND_OK if success else (
        COMMAND_TIMED_OUT if "timed out" in error.lower() or "timeoutexpired" in error.lower()
        else COMMAND_FAILED
    )
    dispatch_state = DISPATCH_ACKNOWLEDGED if execution_state == EXEC_UNKNOWN else DISPATCH_REJECTED
    result_state = RESULT_UNKNOWN
    terminal_evidence = TerminalEvidence(
        signal={"source": evidence_source, "run_id": run_id, "success": success},
        verified_death=(execution_state == EXEC_FAILED),
    ).to_dict()
    _update_task_run_lifecycle(
        run_id,
        dispatch_state=dispatch_state,
        execution_state=execution_state,
        session_state=SESSION_UNKNOWN,
        result_state=result_state,
        requires_reconciliation_flag=requires_reconciliation(execution_state),
        terminal_evidence=terminal_evidence,
        command_state=command_state,
    )
    return ExecutionResult(
        success=success,
        actual_runtime=None,
        error=error,
        agent_id=agent_id,
        run_id=run_id,
        execution_evidence_source=evidence_source,
        dispatch_state=dispatch_state,
        execution_state=execution_state,
        session_state=SESSION_UNKNOWN,
        result_state=result_state,
        command_state=command_state,
        requires_reconciliation=requires_reconciliation(execution_state),
        terminal_evidence=terminal_evidence,
    )


# --------------------------------------------------------------------------- #
# The real ExecutorFn
# --------------------------------------------------------------------------- #

def _run_agent(agent_id: str, message: str, session_key: str, timeout_seconds: int) -> tuple[int, str, str]:
    cmd = [
        OPENCLAW_BIN, "agent",
        "--agent", agent_id,
        "--message", message,
        "--session-key", session_key,
        "--json",
        "--timeout", str(timeout_seconds),
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=timeout_seconds + _SUBPROCESS_GRACE_SECONDS,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _build_short_id_index(phys_index: dict[str, tuple[str, str | None]]) -> dict[str, str]:
    """physical_model -> its last path segment, lowercased (e.g.
    "anthropic/claude-opus-4-8" -> "claude-opus-4-8"), inverted to
    short_id -> physical_model. Built once, from the registry
    (provider_resolution.yml via `_physical_model_index`) -- never from a
    guessed string format. Used to resolve OpenClaw's own
    `executionTrace.winnerModel` (a short id) back to a full physical id
    without re-querying `openclaw agents list` (Phase 5 hardening, R1+R2)."""
    index: dict[str, str] = {}
    for phys in phys_index.keys():
        short = phys.rsplit("/", 1)[-1].strip().lower()
        if short:
            index[short] = phys
    return index


def _resolve_observed_physical_model(
    winner_model_short: str, short_id_index: dict[str, str],
) -> str | None:
    """Match a short runtime-reported model id against the registry-derived
    index. Exact match first; falls back to substring containment (covers
    provider-issued aliases like "qwen" against "qwen3.6-35b-a3b"). Returns
    None -- never a guess -- if nothing in the registry matches, so an
    unrecognized runtime model is flagged as unverifiable rather than
    silently assumed to be the one that was requested.
    """
    key = winner_model_short.strip().lower()
    if not key:
        return None
    if key in short_id_index:
        return short_id_index[key]
    for short, phys in short_id_index.items():
        if key in short or short in key:
            return phys
    return None


def build_real_executor(
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    resolver: ProviderResolver | None = None,
):
    """Build a real, OpenClaw-backed ExecutorFn.

    Never simulates and never falls back to simulation. Every non-execution
    path (unreachable gateway, no eligible agent, subprocess failure, bad
    JSON, or any other unexpected fault) returns ExecutionResult(success=False,
    ...) with a specific reason -- fail closed, per the remediation's hard
    constraint. The outer `_executor` wrapper is a catch-all safety net
    (Phase 5 hardening, R2): no exception raised anywhere in `_execute` can
    escape and crash the Dispatcher's batch, even after a paid run returns.
    """
    provider_resolver = resolver or ProviderResolver()
    phys_index = _physical_model_index(provider_resolver)
    short_id_index = _build_short_id_index(phys_index)
    reliability_config = load_reliability_config()

    def _execute(work_package, assignment) -> ExecutionResult:
        physical_model = getattr(assignment, "physical_model", None)
        if not assignment.available or not physical_model:
            return _result_for_source(
                success=False,
                error="fail-closed: assignment has no resolved physical model",
                evidence_source="fail-closed-no-resolution",
            )

        ok, reason = gateway_reachable()
        if not ok:
            return _result_for_source(
                success=False,
                error=f"fail-closed: OpenClaw gateway unreachable ({reason})",
                evidence_source="fail-closed-gateway-unreachable",
            )

        try:
            agents = non_wbs_agents()
        except BridgeError as exc:
            return _result_for_source(
                success=False,
                error=f"fail-closed: could not enumerate OpenClaw agents ({exc})",
                evidence_source="fail-closed-agent-enumeration-error",
            )

        # --- DETERMINISTIC identity-based selection (Workforce Identity
        # Remediation) --- resolve the ONE dedicated agent for this logical
        # identity from the registry's `agent:` binding. NO physical-model
        # reverse match, so codex and gpt (both openai/gpt-5.5) route to
        # lisa-codex / lisa-gpt distinctly and can never collapse onto one
        # agent (or onto `main`).
        resolved_logical = getattr(assignment, "resolved_logical", None)
        agent_id = agent_for_logical(resolved_logical, provider_resolver)

        if agent_id is None:
            return _result_for_source(
                success=False,
                error=(
                    f"fail-closed: logical identity {resolved_logical!r} has no "
                    f"dedicated OpenClaw agent binding in provider_resolution.yml. "
                    f"Refusing to guess or reverse-match by physical model."
                ),
                evidence_source="fail-closed-no-identity-agent",
            )

        agent_ids = {a.get("id") for a in agents}
        if agent_id not in agent_ids:
            # Bound agent is missing, or is WBS-scoped (non_wbs_agents excludes
            # wbs-*, so a wbs-bound agent lands here too). Either way: fail
            # closed rather than silently falling through to a shared agent.
            return _result_for_source(
                success=False,
                error=(
                    f"fail-closed: logical identity {resolved_logical!r} is bound to "
                    f"agent {agent_id!r}, which is not an available non-WBS OpenClaw "
                    f"agent. Provision it (openclaw agents add) before dispatching. "
                    f"No spawn attempted."
                ),
                agent_id=agent_id,
                evidence_source="fail-closed-identity-agent-unavailable",
            )

        session_key = f"agent:{agent_id}:lisa-phase4-{work_package.id}-{uuid.uuid4().hex[:8]}"
        message = work_package.description or work_package.id

        # --- MANDATORY WORKDIR invariant (Session Policy v1 operational
        # finding, 2026-08-11) --- Fresh worker sessions may start in worker
        # scaffolding rather than the target repository. Before execution,
        # verify the brief's authoritative repository/workdir equals the
        # worker's actual runtime working directory. FAIL CLOSED
        # (WORKDIR_MISSING / WORKDIR_MISMATCH) when absent or mismatched --
        # never rely on warm-session memory to locate the repo.
        expected_repo = getattr(work_package, "repository", None)
        if expected_repo:
            try:
                from core.session_policy import check_workdir
                wd = check_workdir(
                    expected=expected_repo,
                    actual=os.getcwd(),
                )
            except Exception:
                wd = None
            if wd is not None and not wd.ok:
                return ExecutionResult(
                    success=False, actual_runtime=None,
                    error=(f"fail-closed: {wd.result} -- {wd.detail}. "
                           f"Worker would execute outside the authoritative "
                           f"repository; refusing to dispatch."),
                    agent_id=agent_id,
                    execution_evidence_source=f"fail-closed-{wd.result.lower()}",
                    dispatch_state=DISPATCH_REJECTED,
                    execution_state=EXEC_FAILED,
                    session_state=SESSION_UNKNOWN,
                    result_state=RESULT_UNKNOWN,
                    command_state=COMMAND_FAILED,
                    requires_reconciliation=False,
                )
        # (If the brief carries no repository field, the guard in
        # session_policy.check_workdir would flag WORKDIR_MISSING; here we
        # require the field on identity-bearing packages only when set --
        # legacy packages without identity keep legacy behaviour. Brief-level
        # enforcement is covered by the MANDATORY WORKDIR brief block.)

        # --- Claude Session Lifecycle Policy v1 (2026-08-11) ---
        # When the dispatch carries identity (project/sprint/employee/role/
        # task_family), derive a DETERMINISTIC session key so unrelated work
        # cannot silently inherit a previous Claude session: any identity
        # component change yields a different key. When identity is absent
        # (legacy goals), fall back to the legacy fresh-random key unchanged.
        if any(
            getattr(work_package, field_name, None)
            for field_name in ("project", "sprint", "employee", "role", "task_family")
        ):
            try:
                from core.session_policy import session_key_for
                session_key = f"agent:{agent_id}:lisa-session-" + session_key_for(
                    project=work_package.project,
                    sprint=work_package.sprint,
                    employee=work_package.employee,
                    role=work_package.role,
                    task_family=work_package.task_family,
                )
            except Exception:
                # Fail-safe: identity derivation must never break dispatch.
                # Fall back to the legacy fresh-random key (fresh by
                # construction -- never a silent reuse).
                session_key = f"agent:{agent_id}:lisa-phase4-{work_package.id}-{uuid.uuid4().hex[:8]}"
        retry_override = getattr(work_package, "_rc005_session_key", None)
        if retry_override:
            session_key = f"agent:{agent_id}:{retry_override}"
        start = time.monotonic()
        created_after_ms = int(time.time() * 1000)
        try:
            returncode, stdout, stderr = _run_agent(agent_id, message, session_key, timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as exc:
            run_id = (
                _extract_run_id(getattr(exc, "output", None))
                or _extract_run_id(getattr(exc, "stdout", None))
            )
            row = None if run_id else _find_task_run_for_invocation(
                agent_id=agent_id,
                session_key=session_key,
                task=message,
                created_after_ms=created_after_ms,
            )
            run_id = run_id or (row or {}).get("run_id")
            return _result_for_source(
                success=False,
                error=f"openclaw agent invocation failed: {exc}",
                agent_id=agent_id,
                run_id=run_id,
                evidence_source="fail-closed-subprocess-error",
            )
        wall_seconds = time.monotonic() - start

        if returncode != 0:
            row = _find_task_run_for_invocation(
                agent_id=agent_id,
                session_key=session_key,
                task=message,
                created_after_ms=created_after_ms,
            )
            return _result_for_source(
                success=False,
                error=f"openclaw agent exited {returncode}: {stderr.strip()[:500] or stdout.strip()[:500]}",
                agent_id=agent_id,
                run_id=(row or {}).get("run_id"),
                evidence_source="real-execution-failed",
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            row = _find_task_run_for_invocation(
                agent_id=agent_id,
                session_key=session_key,
                task=message,
                created_after_ms=created_after_ms,
            )
            return _result_for_source(
                success=False,
                error=f"openclaw agent returned non-JSON output: {exc}",
                agent_id=agent_id,
                run_id=(row or {}).get("run_id"),
                evidence_source="fail-closed-bad-json-response",
            )

        result_block = payload.get("result", {}) or {}
        agent_meta = (result_block.get("meta", {}) or {}).get("agentMeta", {}) or {}
        trace = result_block.get("executionTrace", {}) or {}
        run_id = payload.get("runId")

        observed_provider = trace.get("winnerProvider") or agent_meta.get("provider")

        # --- R1 fix: attribution now comes from the REAL runtime signal ---
        # (executionTrace.winnerModel / fallbackUsed), resolved via the
        # registry-derived short-id index -- NOT the agent's own configured
        # binding (that comparison was tautological: the agent was selected
        # *because* its binding equals the resolved model, so it could never
        # disagree). A provider-side fallback, or a runtime model this
        # registry doesn't recognize, is now a detected mismatch instead of
        # a silent "clean match".
        winner_model_short = (trace.get("winnerModel") or agent_meta.get("model") or "").strip()
        observed_physical_model = _resolve_observed_physical_model(winner_model_short, short_id_index)
        winner_recognized = observed_physical_model is not None
        fallback_used = bool(trace.get("fallbackUsed"))

        mismatch = fallback_used or (not winner_recognized) or (observed_physical_model != physical_model)
        if fallback_used:
            mismatch_detail = (
                f"OpenClaw executionTrace reported fallbackUsed=True "
                f"(winner={winner_model_short!r})"
            )
        elif not winner_recognized:
            mismatch_detail = (
                f"runtime-reported model {winner_model_short!r} does not match any "
                f"known registry physical model -- cannot confirm no drift occurred"
            )
        elif observed_physical_model != physical_model:
            mismatch_detail = (
                f"LisaOS resolved {physical_model!r} but OpenClaw's own "
                f"executionTrace reports it actually ran {observed_physical_model!r}"
            )
        else:
            mismatch_detail = None

        observed_model = observed_physical_model or winner_model_short or physical_model

        usage = (agent_meta.get("usage") or {})
        tokens = {
            "input": usage.get("input"),
            "output": usage.get("output"),
            "total": usage.get("total"),
        } if usage else None

        if observed_physical_model == physical_model:
            # Workforce Truth Hotfix (see
            # reports/lisa/CTO_WORKFORCE_GOVERNANCE_REVIEW.md): no genuine
            # physical-model drift occurred, so derive `actual_runtime` from
            # the assignment's OWN resolved runtime (set unambiguously at
            # staffing time via a direct, uncollided registry lookup) rather
            # than reverse-deriving it from `physical_model` via
            # `phys_index`. `phys_index` is keyed by physical_model, and
            # `codex`/`gpt` (among others, potentially) share one physical
            # model -- the reverse lookup silently returns whichever
            # provider was inserted last in the registry, mislabelling a
            # correct codex dispatch as "gpt"/"openclaw". This branch never
            # changes `observed_model`, `mismatch`, or `success` -- only
            # which value labels a NON-drifted execution.
            runtime = getattr(assignment, "resolved_runtime", None)
            canonical = getattr(assignment, "resolved_logical", None)
        else:
            # Genuine drift (or an unrecognized runtime model) -- the
            # reverse index is the right tool here, since there is no
            # single "assignment's own" runtime that could be trusted
            # instead; the whole point is that something OTHER than the
            # resolved model ran.
            canonical, runtime = phys_index.get(observed_physical_model or "", (None, None))
            if runtime is None:
                # Observed model unrecognized/absent -- fall back to the
                # resolved model's own registry runtime so `actual_runtime`
                # still carries an auditable value; `mismatch` (above)
                # already flags that this is not a confirmed match.
                canonical, runtime = phys_index.get(physical_model, (None, None))

        db_row = _fetch_task_run(run_id) if run_id else None
        evidence_source = "openclaw_json_response"
        if db_row is not None:
            evidence_source = "openclaw_json_response+task_runs_confirmed"
            if db_row.get("status") not in ("succeeded", "ok"):
                mismatch = True
                mismatch_detail = (mismatch_detail + "; " if mismatch_detail else "") + (
                    f"task_runs status={db_row.get('status')!r} disagrees with "
                    f"CLI-reported success"
                )

        # `success` reflects whether the execution itself completed (CLI +
        # DB agree it ran to a real outcome) -- unchanged semantics from
        # Phase 4. `mismatch` is a SEPARATE, additive signal: attribution
        # drift does not, by itself, mark the package failed (real work may
        # still have happened); core.anti_regression.check_no_execution_mismatch
        # (Phase 5 hardening, R4) is what turns a mismatch into a hard gate
        # failure at the report level.
        if reliability_config.require_artifact:
            artifact_evidence, artifact_ok = _artifact_evidence_for(work_package)
        else:
            artifact_evidence, artifact_ok = None, True
        terminal_confirmed = (
            payload.get("status") == "ok"
            and db_row is not None
            and db_row.get("status") in ("succeeded", "ok")
        )
        success = terminal_confirmed and artifact_ok
        execution_state = EXEC_COMPLETED if success else EXEC_UNKNOWN
        result_state = RESULT_INGESTED if success else RESULT_UNKNOWN
        terminal_evidence = TerminalEvidence(
            signal={
                "source": evidence_source,
                "payload_status": payload.get("status"),
                "task_runs_status": db_row.get("status") if db_row else None,
                "run_id": run_id,
                "agent_id": agent_id,
            },
            artifact=artifact_evidence,
            verified_death=False,
        ).to_dict()
        persisted = _update_task_run_lifecycle(
            run_id,
            dispatch_state=DISPATCH_ACKNOWLEDGED,
            execution_state=execution_state,
            session_state=SESSION_UNKNOWN,
            result_state=result_state,
            requires_reconciliation_flag=requires_reconciliation(execution_state),
            terminal_evidence=terminal_evidence,
            command_state=COMMAND_OK,
        )
        if _lifecycle_columns_available() and persisted is False and db_row is not None:
            success = False
            execution_state = EXEC_UNKNOWN
            result_state = RESULT_UNKNOWN
            terminal_evidence["persistence"] = {
                "task_runs_lifecycle_update": False,
            }

        return ExecutionResult(
            success=success,
            actual_runtime=runtime,
            error=None if success else "execution completion lacked authoritative terminal/artifact evidence",
            observed_model=observed_model,
            observed_provider=observed_provider,
            run_id=run_id,
            agent_id=agent_id,
            tokens=tokens,
            mismatch=mismatch,
            mismatch_detail=mismatch_detail,
            execution_evidence_source=evidence_source,
            dispatch_state=DISPATCH_ACKNOWLEDGED,
            execution_state=execution_state,
            session_state=SESSION_UNKNOWN,
            result_state=result_state,
            command_state=COMMAND_OK,
            requires_reconciliation=requires_reconciliation(execution_state),
            terminal_evidence=terminal_evidence,
        )

    def _executor(work_package, assignment) -> ExecutionResult:
        try:
            return _execute(work_package, assignment)
        except Exception as exc:  # R2: no fault anywhere above may escape and crash the batch
            return _result_for_source(
                success=False,
                error=f"bridge raised an unexpected exception: {exc!r}",
                evidence_source="fail-closed-executor-exception",
            )

    # r4 (B3): declare provenance. This executor spawns a real, out-of-process
    # OpenClaw agent, so WORKER_REAL is a truthful declaration for it.
    from core.dispatcher import mark_executor, WORKER_REAL
    return mark_executor(_executor, WORKER_REAL)


# --------------------------------------------------------------------------- #
# Simulated-mode labelling (used only when a caller explicitly opts into
# --simulate; never the production default -- see bin/lisa-dispatch)
# --------------------------------------------------------------------------- #

def labelled_simulated_executor(work_package, assignment) -> ExecutionResult:
    """Retained for back-compat and explicitness.

    r4 (B4c): `core.dispatcher.simulated_executor` now stamps the label
    itself, so this wrapper is no longer what makes simulation labelled --
    it is simply the explicit spelling of the same thing. The re-stamp below
    is intentionally redundant and kept so this function's contract holds
    even if it is ever pointed at a different inner executor.
    """
    from core.dispatcher import simulated_executor
    result = simulated_executor(work_package, assignment)
    result.execution_evidence_source = SIMULATED_LABEL
    return result


def _mark_simulated_wrapper() -> None:
    """Declare provenance for the wrapper above (r4, B3).

    The `core.dispatcher` import stays inside the function body purely to keep
    the module-level import graph acyclic-by-construction: `core.dispatcher`
    must never import this module at top level, and keeping the edge inside a
    function makes that invariant hard to break by accident. It is called at
    import time below, so importing this module does pull in `core.dispatcher`.
    """
    from core.dispatcher import mark_executor, WORKER_SIMULATED
    mark_executor(labelled_simulated_executor, WORKER_SIMULATED)


_mark_simulated_wrapper()

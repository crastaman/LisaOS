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
from core.provider_resolver import ProviderResolver

# --------------------------------------------------------------------------- #
# Paths / binaries
# --------------------------------------------------------------------------- #

OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN") or shutil.which("openclaw") or "/opt/homebrew/bin/openclaw"
OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))
OPENCLAW_DB = OPENCLAW_HOME / "state" / "openclaw.sqlite"

DEFAULT_TIMEOUT_SECONDS = 240  # real OpenClaw turns run minutes, not ms (see report)
_SUBPROCESS_GRACE_SECONDS = 20  # extra headroom over --timeout before we give up waiting

SIMULATED_LABEL = "SIMULATED-NOT-EXECUTED"


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
    """First non-WBS agent whose OWN default model matches `physical_model`.

    Returns None if no such agent exists -- the caller must fail closed, not
    guess or override (`--model` override is rejected by the Gateway; see
    module docstring).
    """
    return _select_agent(non_wbs_agents(timeout=timeout), physical_model)


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

    def _execute(work_package, assignment) -> ExecutionResult:
        physical_model = getattr(assignment, "physical_model", None)
        if not assignment.available or not physical_model:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error="fail-closed: assignment has no resolved physical model",
                execution_evidence_source="fail-closed-no-resolution",
            )

        ok, reason = gateway_reachable()
        if not ok:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=f"fail-closed: OpenClaw gateway unreachable ({reason})",
                execution_evidence_source="fail-closed-gateway-unreachable",
            )

        try:
            agents = non_wbs_agents()
        except BridgeError as exc:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=f"fail-closed: could not enumerate OpenClaw agents ({exc})",
                execution_evidence_source="fail-closed-agent-enumeration-error",
            )
        agent_id = _select_agent(agents, physical_model)

        if agent_id is None:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=(
                    f"fail-closed: no non-WBS OpenClaw agent is bound to physical "
                    f"model {physical_model!r}. `--model` override is rejected by "
                    f"the Gateway for every agent (verified empirically); the only "
                    f"agents currently bound to this model are out of LisaOS scope "
                    f"(wbs-* identities) or none exist. This is not simulated -- "
                    f"no spawn was attempted."
                ),
                execution_evidence_source="fail-closed-no-eligible-agent",
            )

        session_key = f"agent:{agent_id}:lisa-phase4-{work_package.id}-{uuid.uuid4().hex[:8]}"
        message = work_package.description or work_package.id

        start = time.monotonic()
        try:
            returncode, stdout, stderr = _run_agent(agent_id, message, session_key, timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=f"openclaw agent invocation failed: {exc}",
                agent_id=agent_id, execution_evidence_source="fail-closed-subprocess-error",
            )
        wall_seconds = time.monotonic() - start

        if returncode != 0:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=f"openclaw agent exited {returncode}: {stderr.strip()[:500] or stdout.strip()[:500]}",
                agent_id=agent_id, execution_evidence_source="real-execution-failed",
            )

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=f"openclaw agent returned non-JSON output: {exc}",
                agent_id=agent_id, execution_evidence_source="fail-closed-bad-json-response",
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
        success = payload.get("status") == "ok" and (db_row is None or db_row.get("status") in ("succeeded", "ok"))

        return ExecutionResult(
            success=success,
            actual_runtime=runtime,
            error=None if success else "execution completed but status was not ok",
            observed_model=observed_model,
            observed_provider=observed_provider,
            run_id=run_id,
            agent_id=agent_id,
            tokens=tokens,
            mismatch=mismatch,
            mismatch_detail=mismatch_detail,
            execution_evidence_source=evidence_source,
        )

    def _executor(work_package, assignment) -> ExecutionResult:
        try:
            return _execute(work_package, assignment)
        except Exception as exc:  # R2: no fault anywhere above may escape and crash the batch
            return ExecutionResult(
                success=False, actual_runtime=None,
                error=f"bridge raised an unexpected exception: {exc!r}",
                execution_evidence_source="fail-closed-executor-exception",
            )

    return _executor


# --------------------------------------------------------------------------- #
# Simulated-mode labelling (used only when a caller explicitly opts into
# --simulate; never the production default -- see bin/lisa-dispatch)
# --------------------------------------------------------------------------- #

def labelled_simulated_executor(work_package, assignment) -> ExecutionResult:
    from core.dispatcher import simulated_executor
    result = simulated_executor(work_package, assignment)
    result.execution_evidence_source = SIMULATED_LABEL
    return result

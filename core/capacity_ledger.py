"""LisaOS Capacity Ledger (Phase 3).

A PERSISTENT record of what LisaOS has actually observed about each logical
provider's runtime health, layered on top of (never replacing) Phase 0/1's
live, fail-closed `ProviderResolver` credential check.

The distinction matters:
  * ProviderResolver answers "is this provider CREDENTIALED right now?" --
    a point-in-time auth check, no memory.
  * CapacityLedger answers "what have we HISTORICALLY observed about this
    provider's health/quota/reliability?" -- persisted across runs, so a
    provider that started failing/exhausting quota an hour ago is still
    known to be unhealthy even though its credentials still check out.

Design guarantees:
  * FAIL CLOSED ON HEALTH. unavailable/disabled capacity is never usable.
    exhausted capacity is never usable UNLESS a caller explicitly allows it
    (the mode-level `allow_exhausted_capacity` escape hatch -- see
    core/workforce_modes.py). Probationary capacity is only usable for
    risk == "low" work, never mode-overridable.
  * NO GUESSING. If a reset time is unknown, it is recorded as None/"unknown"
    -- the ledger never fabricates a recovery time. Auto-recovery from
    "exhausted" only happens once `exhausted_until` has both been recorded
    AND has actually passed.
  * PERSISTENT. Entries are stored as JSON under reports/lisa/ (gitignored,
    like the evidence logs) so health/quota memory survives process restarts.
    Every unit test injects an in-memory (non-persisting) ledger -- no test
    ever touches the real on-disk ledger.
  * THREAD SAFE. Dispatcher work packages execute on worker threads; a ledger
    shared across a dispatch run may be mutated concurrently, so all mutating
    operations are guarded by a lock.

This module has no dependency on core.dispatcher or core.workforce_resolver
(duck-typed integration only), keeping it usable standalone or from any
executor.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Health states
# --------------------------------------------------------------------------- #

HEALTHY = "healthy"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
EXHAUSTED = "exhausted"
PROBATIONARY = "probationary"
DISABLED = "disabled"

VALID_HEALTH_STATES = (HEALTHY, DEGRADED, UNAVAILABLE, EXHAUSTED, PROBATIONARY, DISABLED)

# Capacity/cost classes (matches core.dispatcher._COST_PRIORITY's taxonomy so
# the ledger and the scheduler's admission ordering never disagree about what
# "subscription" vs "metered" means).
SUBSCRIPTION_ABUNDANT = "subscription-abundant"
SUBSCRIPTION_SCARCE = "subscription-scarce"
SUBSCRIPTION_PROBATION = "subscription-probation"
ELASTIC_API = "elastic-api"

# Seed values mirroring registry/provider_resolution.yml's ground truth
# (README.md "Providers configured & authenticated" table + registry probation
# flags). Any logical provider not listed here seeds as elastic-api / healthy
# -- a conservative default that costs more, not one that trusts more.
_SEED_COST_CLASS: dict[str, str] = {
    "deepseek": ELASTIC_API,
    "claude-opus": SUBSCRIPTION_SCARCE,
    "claude-sonnet": SUBSCRIPTION_ABUNDANT,
    "claude-haiku": SUBSCRIPTION_ABUNDANT,
    "codex": SUBSCRIPTION_ABUNDANT,
    "gpt": SUBSCRIPTION_ABUNDANT,
    "qwen-deepinfra": ELASTIC_API,
    "glm": SUBSCRIPTION_PROBATION,
    "glm-turbo": SUBSCRIPTION_PROBATION,
}
_SEED_PROBATION = frozenset({"glm", "glm-turbo"})

_MAX_FAILURE_HISTORY = 20

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
DEFAULT_LEDGER_PATH = LISA_BASE / "reports" / "lisa" / "capacity_ledger.json"


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


# --------------------------------------------------------------------------- #
# Ledger entry
# --------------------------------------------------------------------------- #

@dataclass
class LedgerEntry:
    """Everything LisaOS has observed about one logical provider's health."""

    logical_provider: str
    health_state: str = HEALTHY
    cost_class: str = ELASTIC_API
    probationary: bool = False
    exhausted_until: str | None = None       # ISO8601, or None = unknown/not exhausted
    next_available_at: str | None = None     # ISO8601, or None = unknown
    last_checked_at: str | None = None
    last_success_at: str | None = None
    last_success_runtime: str | None = None
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    failure_history: list[dict[str, str]] = field(default_factory=list)
    reliability_status: str = "unknown"      # unknown | reliable | degraded | unreliable | probation
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LedgerEntry":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)

    @classmethod
    def seed(cls, logical_provider: str) -> "LedgerEntry":
        probation = logical_provider in _SEED_PROBATION
        return cls(
            logical_provider=logical_provider,
            health_state=PROBATIONARY if probation else HEALTHY,
            cost_class=_SEED_COST_CLASS.get(logical_provider, ELASTIC_API),
            probationary=probation,
            reliability_status="probation" if probation else "unknown",
        )


# --------------------------------------------------------------------------- #
# Capacity ledger
# --------------------------------------------------------------------------- #

class CapacityLedger:
    """Persistent, thread-safe health/quota/reliability memory per provider."""

    def __init__(self, path: Path | None = None, *, persist: bool = True):
        self._persist = persist
        self.path = path if path is not None else (DEFAULT_LEDGER_PATH if persist else None)
        self._lock = threading.Lock()
        self.entries: dict[str, LedgerEntry] = {}
        if self._persist and self.path is not None and self.path.is_file():
            self._load_from_disk()

    # ---- construction helpers ----------------------------------------------

    @classmethod
    def in_memory(cls) -> "CapacityLedger":
        """A ledger that never reads or writes disk -- for tests and hermetic use."""
        return cls(path=None, persist=False)

    @classmethod
    def at_path(cls, path: Path) -> "CapacityLedger":
        """A ledger persisted to an explicit path (tests use a tmp path; never
        the real default so unit tests can't corrupt operator state)."""
        return cls(path=path, persist=True)

    # ---- persistence ---------------------------------------------------------

    def _load_from_disk(self) -> None:
        try:
            raw = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for logical, data in (raw or {}).items():
            self.entries[logical] = LedgerEntry.from_dict(data)

    def save(self) -> None:
        if not self._persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {logical: entry.to_dict() for logical, entry in self.entries.items()}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    # ---- lookup / seeding ----------------------------------------------------

    def get(self, logical_provider: str) -> LedgerEntry:
        with self._lock:
            return self._get_locked(logical_provider)

    def _get_locked(self, logical_provider: str) -> LedgerEntry:
        entry = self.entries.get(logical_provider)
        if entry is None:
            entry = LedgerEntry.seed(logical_provider)
            self.entries[logical_provider] = entry
        return entry

    # ---- health transitions (mutating; each persists) -------------------------

    def record_success(self, logical_provider: str, *, runtime: str | None = None,
                       at: datetime | None = None) -> LedgerEntry:
        with self._lock:
            entry = self._get_locked(logical_provider)
            now = _now_iso(at)
            entry.consecutive_failures = 0
            entry.total_successes += 1
            entry.last_success_at = now
            entry.last_success_runtime = runtime
            entry.last_checked_at = now
            if entry.health_state in (DEGRADED, UNAVAILABLE, EXHAUSTED):
                entry.health_state = PROBATIONARY if entry.probationary else HEALTHY
                entry.exhausted_until = None
                entry.next_available_at = None
            entry.reliability_status = (
                "probation" if entry.probationary
                else "reliable" if entry.total_successes >= 3
                else entry.reliability_status
            )
            self.save()
            return entry

    def record_failure(self, logical_provider: str, *, reason: str = "",
                       at: datetime | None = None) -> LedgerEntry:
        with self._lock:
            entry = self._get_locked(logical_provider)
            now = _now_iso(at)
            entry.consecutive_failures += 1
            entry.total_failures += 1
            entry.last_checked_at = now
            entry.failure_history.append({"at": now, "reason": reason})
            if len(entry.failure_history) > _MAX_FAILURE_HISTORY:
                entry.failure_history = entry.failure_history[-_MAX_FAILURE_HISTORY:]
            if entry.consecutive_failures >= 3:
                if entry.health_state not in (DISABLED, EXHAUSTED):
                    entry.health_state = UNAVAILABLE
                entry.reliability_status = "unreliable"
            elif entry.health_state not in (DISABLED, EXHAUSTED, UNAVAILABLE):
                entry.health_state = DEGRADED
                entry.reliability_status = "degraded"
            self.save()
            return entry

    def record_exhaustion(self, logical_provider: str, *, exhausted_until: str | None = None,
                          at: datetime | None = None) -> LedgerEntry:
        """Mark a provider quota-exhausted. `exhausted_until` (ISO8601) is the
        known reset time; pass None if unknown -- the ledger will NOT guess a
        recovery time and the provider stays exhausted until an explicit
        record_success() (a real successful call) or enable() clears it.
        """
        with self._lock:
            entry = self._get_locked(logical_provider)
            now = _now_iso(at)
            entry.health_state = EXHAUSTED
            entry.exhausted_until = exhausted_until
            entry.next_available_at = exhausted_until
            entry.last_checked_at = now
            self.save()
            return entry

    def quarantine(self, logical_provider: str, *, reason: str = "",
                   at: datetime | None = None) -> LedgerEntry:
        """Dynamically place a provider on probation (distinct from the
        static `probation:` flag in provider_resolution.yml) -- e.g. after a
        pattern of concerning-but-not-yet-failing behaviour observed at
        runtime.
        """
        with self._lock:
            entry = self._get_locked(logical_provider)
            entry.health_state = PROBATIONARY
            entry.probationary = True
            entry.reliability_status = "probation"
            entry.last_checked_at = _now_iso(at)
            entry.notes = reason or entry.notes
            self.save()
            return entry

    def disable(self, logical_provider: str, *, reason: str = "",
               at: datetime | None = None) -> LedgerEntry:
        with self._lock:
            entry = self._get_locked(logical_provider)
            entry.health_state = DISABLED
            entry.notes = reason or entry.notes
            entry.last_checked_at = _now_iso(at)
            self.save()
            return entry

    def enable(self, logical_provider: str, *, at: datetime | None = None) -> LedgerEntry:
        """Manual recovery override -- clears disabled/unavailable/exhausted."""
        with self._lock:
            entry = self._get_locked(logical_provider)
            entry.health_state = PROBATIONARY if entry.probationary else HEALTHY
            entry.consecutive_failures = 0
            entry.exhausted_until = None
            entry.next_available_at = None
            entry.last_checked_at = _now_iso(at)
            self.save()
            return entry

    # ---- forecasting / effective health ---------------------------------------

    def effective_health(self, logical_provider: str, *, now: datetime | None = None) -> str:
        """The health state after applying any known, elapsed auto-recovery.

        Only auto-recovers from EXHAUSTED, and only when `exhausted_until` is
        both known and has actually passed -- an unknown reset time never
        auto-recovers (no guessing).
        """
        with self._lock:
            entry = self._get_locked(logical_provider)
            if entry.health_state == EXHAUSTED and entry.exhausted_until:
                now = now or datetime.now(timezone.utc)
                try:
                    until = datetime.fromisoformat(entry.exhausted_until)
                except ValueError:
                    return entry.health_state
                if now >= until:
                    entry.health_state = PROBATIONARY if entry.probationary else HEALTHY
                    entry.exhausted_until = None
                    entry.next_available_at = None
                    entry.consecutive_failures = 0
                    entry.last_checked_at = _now_iso(now)
                    self.save()
            return entry.health_state

    # ---- usability decision ----------------------------------------------------

    def is_usable(self, logical_provider: str, *, risk: str = "normal",
                  allow_exhausted: bool = False) -> tuple[bool, str]:
        """Should this logical provider be considered at all for this work?

        Does NOT check live credentials -- that remains ProviderResolver's
        job. This answers only "does recorded health/quota/probation history
        rule it out?"
        """
        state = self.effective_health(logical_provider)
        entry = self.get(logical_provider)
        if state in (UNAVAILABLE, DISABLED):
            return False, f"health_state={state}"
        if state == EXHAUSTED:
            if allow_exhausted:
                return True, "exhausted capacity explicitly allowed"
            return False, f"exhausted (reset={entry.exhausted_until or 'unknown'})"
        if state == PROBATIONARY:
            if risk == "low":
                return True, "probationary capacity permitted for low-risk work"
            return False, "probationary capacity restricted to low-risk work"
        return True, "ok"

    # ---- reporting -------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {logical: entry.to_dict() for logical, entry in self.entries.items()}


# --------------------------------------------------------------------------- #
# Executor integration (Phase 2 ExecutorFn-compatible; duck-typed, no import
# of core.dispatcher so the dependency stays one-directional)
# --------------------------------------------------------------------------- #

def ledger_recording_executor(ledger: CapacityLedger, inner: Any = None) -> Any:
    """Wrap any Dispatcher ExecutorFn so real execution outcomes feed the
    ledger. Plugs into core.dispatcher.Dispatcher(executor=...) unchanged --
    the Dispatcher's scheduling loop requires no modification for the
    scheduler to become capacity-ledger-aware.
    """
    if inner is None:
        from core.dispatcher import simulated_executor as inner  # local import: avoid a hard, always-on dep

    def _executor(work_package, assignment):
        result = inner(work_package, assignment)
        logical = getattr(assignment, "resolved_logical", None)
        if logical:
            if result.success:
                ledger.record_success(logical, runtime=result.actual_runtime)
            else:
                ledger.record_failure(logical, reason=result.error or "execution failed")
        return result

    return _executor

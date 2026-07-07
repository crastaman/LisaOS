"""LisaOS Anti-Regression Gates (Phase 1).

Enforceable checks that stop Lisa sliding back into old habits after Workforce
Intelligence lands. See docs/LISAOS/V3/19_ANTI_REGRESSION_FRAMEWORK.md.

Each check is a PURE function returning a GateResult, so it is trivially
testable and free to run. Severities:
  * OK   — passed.
  * WARN — recorded; escalates to FAIL on repetition.
  * FAIL — hard fail; a sprint containing this must not be accepted.

Covered fail conditions (from the framework):
  F1 no silent fallback            -> check_no_silent_fallback           (FAIL)
  F2 main not majority of work     -> check_main_not_majority            (FAIL/WARN)
  F3 intended provider == actual   -> check_intended_matches_actual      (FAIL)
  F4 stale alias must not resolve  -> check_no_stale_alias               (FAIL)
  --  DeepSeek must not be a gravity well -> check_deepseek_not_gravity_well (FAIL)
  --  workers not idle while ready  -> check_no_idle_while_ready          (FAIL)
  F5 context overflow              -> check_context_safety               (FAIL)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"

# Aliases retired in Phase 0 that must never resolve again.
RETIRED_ALIASES = ("qwen", "qwen-alibaba", "ali-qwen", "qwen-modelstudio", "alibaba-qwen")


@dataclass
class GateResult:
    name: str
    severity: str            # OK | WARN | FAIL
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.severity != FAIL


@dataclass
class GateReport:
    results: list[GateResult] = field(default_factory=list)

    def add(self, result: GateResult) -> "GateReport":
        self.results.append(result)
        return self

    @property
    def failures(self) -> list[GateResult]:
        return [r for r in self.results if r.severity == FAIL]

    @property
    def warnings(self) -> list[GateResult]:
        return [r for r in self.results if r.severity == WARN]

    @property
    def passed(self) -> bool:
        return not self.failures


# --------------------------------------------------------------------------- #
# Individual gates
# --------------------------------------------------------------------------- #

_DEEPSEEK_TOKENS = ("deepseek",)


def _looks_like_deepseek(value: str | None) -> bool:
    return bool(value) and any(tok in value.lower() for tok in _DEEPSEEK_TOKENS)


def check_no_silent_fallback(assignment: Any) -> GateResult:
    """F1. A fallback (resolved != intended) is only legitimate if it was
    explicitly recorded (fallback_from + fallback_reason). An implicit or
    unexplained substitution — especially onto DeepSeek — is a hard fail.
    """
    intended = getattr(assignment, "intended_model", None)
    resolved = getattr(assignment, "resolved_logical", None)
    fb_from = getattr(assignment, "fallback_from", None)
    fb_reason = getattr(assignment, "fallback_reason", None)

    if resolved is None:
        return GateResult("no_silent_fallback", OK, "no resolution to check")

    # Resolved differs from intended => a fallback happened.
    if resolved != intended:
        if not fb_from or not fb_reason:
            sink = " onto DeepSeek" if _looks_like_deepseek(resolved) else ""
            return GateResult(
                "no_silent_fallback", FAIL,
                f"silent fallback{sink}: intended {intended!r} -> resolved "
                f"{resolved!r} with no recorded fallback_from/reason",
            )
    # A recorded fallback must actually carry a reason.
    if fb_from and not fb_reason:
        return GateResult("no_silent_fallback", FAIL,
                          f"fallback_from={fb_from!r} without a fallback_reason")
    return GateResult("no_silent_fallback", OK, "no silent fallback")


def check_intended_matches_actual(assignment: Any) -> GateResult:
    """F3. Once a packet has executed, the runtime that actually ran must match
    the runtime that was resolved. Drift = a provider label not backed by
    runtime evidence.
    """
    actual = getattr(assignment, "actual_runtime", None)
    resolved_runtime = getattr(assignment, "resolved_runtime", None)
    if actual is None:
        return GateResult("intended_matches_actual", OK, "not yet executed")
    if actual != resolved_runtime:
        return GateResult(
            "intended_matches_actual", FAIL,
            f"runtime drift: resolved {resolved_runtime!r} but actual {actual!r}",
        )
    return GateResult("intended_matches_actual", OK, "actual runtime matches resolved")


def check_main_not_majority(main_work_ratio: float,
                            fail_threshold: float = 0.50,
                            warn_threshold: float = 0.40) -> GateResult:
    """F2. The main agent must not perform the majority of delegable work."""
    if main_work_ratio > fail_threshold:
        return GateResult("main_not_majority", FAIL,
                          f"main did {main_work_ratio:.0%} of delegable work (> "
                          f"{fail_threshold:.0%}); it must delegate")
    if main_work_ratio > warn_threshold:
        return GateResult("main_not_majority", WARN,
                          f"main did {main_work_ratio:.0%} of delegable work "
                          f"(> {warn_threshold:.0%}); trending high")
    return GateResult("main_not_majority", OK,
                      f"main did {main_work_ratio:.0%} of delegable work")


def check_no_stale_alias(provider_resolver: Any,
                         aliases: Iterable[str] = RETIRED_ALIASES) -> GateResult:
    """F4. No retired alias may resolve to a provider anymore."""
    resolving = [a for a in aliases if provider_resolver.normalise(a) is not None]
    if resolving:
        return GateResult("no_stale_alias", FAIL,
                          f"retired aliases still resolve: {resolving}")
    return GateResult("no_stale_alias", OK,
                      f"all {len(tuple(aliases))} retired aliases fail closed")


def check_deepseek_not_gravity_well(provider_usage: dict[str, int],
                                    threshold: float = 0.80) -> GateResult:
    """DeepSeek must not absorb a dominant share of packets (monoculture)."""
    total = sum(provider_usage.values())
    if total <= 0:
        return GateResult("deepseek_not_gravity_well", OK, "no usage recorded")
    ds = sum(n for k, n in provider_usage.items() if _looks_like_deepseek(k))
    share = ds / total
    if share > threshold:
        return GateResult("deepseek_not_gravity_well", FAIL,
                          f"DeepSeek share {share:.0%} > {threshold:.0%} "
                          f"(monoculture regression)")
    return GateResult("deepseek_not_gravity_well", OK,
                      f"DeepSeek share {share:.0%}")


def check_no_idle_while_ready(idle_capable_count: int,
                             ready_unassigned_count: int) -> GateResult:
    """Workers must not sit idle while ready, unassigned work exists."""
    if idle_capable_count > 0 and ready_unassigned_count > 0:
        return GateResult("no_idle_while_ready", FAIL,
                          f"{idle_capable_count} capable employee(s) idle while "
                          f"{ready_unassigned_count} ready packet(s) unassigned")
    return GateResult("no_idle_while_ready", OK, "no idle-while-ready condition")


def check_context_safety(tokens_used: int, budget: int) -> GateResult:
    """F5. A large generation must stay within its context budget. Call this
    BEFORE emitting a large report.
    """
    if budget <= 0:
        return GateResult("context_safety", FAIL, "no context budget set")
    if tokens_used > budget:
        return GateResult("context_safety", FAIL,
                          f"context overflow: {tokens_used} > budget {budget}")
    return GateResult("context_safety", OK,
                      f"within budget ({tokens_used}/{budget})")


# --------------------------------------------------------------------------- #
# Aggregators
# --------------------------------------------------------------------------- #

def assignment_gates(assignment: Any) -> GateReport:
    """Gates that apply to a single work assignment."""
    return (GateReport()
            .add(check_no_silent_fallback(assignment))
            .add(check_intended_matches_actual(assignment)))


def run_pre_sprint_gates(provider_resolver: Any,
                         retired_aliases: Iterable[str] = RETIRED_ALIASES) -> GateReport:
    """Gates runnable before a sprint starts (Phase 1 subset)."""
    return GateReport().add(check_no_stale_alias(provider_resolver, retired_aliases))


def run_post_sprint_gates(assignments: Iterable[Any],
                          main_work_ratio: float,
                          provider_usage: dict[str, int],
                          idle_capable_count: int = 0,
                          ready_unassigned_count: int = 0) -> GateReport:
    """Gates evaluated after a sprint completes."""
    report = GateReport()
    for a in assignments:
        report.add(check_no_silent_fallback(a))
        report.add(check_intended_matches_actual(a))
    report.add(check_main_not_majority(main_work_ratio))
    report.add(check_deepseek_not_gravity_well(provider_usage))
    report.add(check_no_idle_while_ready(idle_capable_count, ready_unassigned_count))
    return report

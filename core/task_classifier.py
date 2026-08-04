"""LisaOS deterministic task classifier.

Maps a natural-language mission string to one of three routing outcomes:
  DIRECT    — conversational / explanatory; no structural work implied.
  GOVERNED  — requires a validated WorkPackage graph before execution.
  BLOCKED   — cannot be routed at all (empty input, etc.).

Pure function: no I/O, no network, no LLM calls, no file reads.
On any unexpected internal exception the classifier returns GOVERNED with
rule INTERNAL_ERROR_DEFAULT_GOVERNED (fail toward governance).

Rule evaluation order
---------------------
1. B1_EMPTY_MISSION     — empty/whitespace-only → BLOCKED (short-circuit).
2. GOVERNED rules       — G5, G1, G2, G3, G4 (ALL evaluated; ANY match → GOVERNED).
3. DIRECT rules         — D1 (only when no G rule matched).
4. DEFAULT_GOVERNED_AMBIGUOUS — nothing else matched → GOVERNED.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── GOVERNED keyword lists ──────────────────────────────────────────────────

_G1_WORDS = [
    "implement", "write", "edit", "create", "delete", "patch", "commit",
    "refactor", "fix", "modify", "migrate", "deploy", "install", "upgrade",
    "rename",
]

_G2_PHRASES = [
    "run tests", "build", "execute", "exec", "insert", "update", "drop",
    "alter", "truncate", "wp-cli", "migration",
]

_G3_PHRASES = [
    "audit", "production-readiness", "production readiness",
    "readiness review", "independent review", "architecture decision",
    "security review", "release", "benchmark", "investigation",
]

_G4_DOMAIN_NOUNS = {
    "lifecycle", "permission", "notification", "payment", "test", "booking",
    "appointment", "schema", "migration", "api", "capacity", "evidence",
    "report", "review",
}

_D1_WORDS = [
    "explain", "what", "how", "why", "describe", "summarize", "summarise",
    "show", "list", "status", "help",
]

# ── Pre-compiled patterns ────────────────────────────────────────────────────

_G5_RE = re.compile(
    r"\bS0\d\d[a-zA-Z]?\b|\bWP-\d+\b|\bsprint\b|\bLISA-I\d+\b",
    re.IGNORECASE,
)

_G1_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _G1_WORDS) + r")\b",
    re.IGNORECASE,
)

# G2 phrases are mixed (some multi-word); test with simple substring for
# multi-word ones and word-boundary for single-word ones.
_G2_MULTI = [p for p in _G2_PHRASES if " " in p or "-" in p]
_G2_SINGLE_RE = re.compile(
    r"\b(?:" + "|".join(
        re.escape(p) for p in _G2_PHRASES if p not in _G2_MULTI
    ) + r")\b",
    re.IGNORECASE,
)

_G3_MULTI = [p for p in _G3_PHRASES if " " in p or "-" in p]
_G3_SINGLE_RE = re.compile(
    r"\b(?:" + "|".join(
        re.escape(p) for p in _G3_PHRASES if p not in _G3_MULTI
    ) + r")\b",
    re.IGNORECASE,
)

_D1_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _D1_WORDS) + r")\b",
    re.IGNORECASE,
)


# ── Public data model ────────────────────────────────────────────────────────

@dataclass
class Classification:
    classification: str          # "DIRECT" | "GOVERNED" | "BLOCKED"
    matched_rules: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "classification": self.classification,
            "matched_rules": self.matched_rules,
            "reason": self.reason,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _check_g5(mission: str) -> bool:
    return bool(_G5_RE.search(mission))


def _check_g1(mission: str) -> bool:
    return bool(_G1_RE.search(mission))


def _check_g2(mission: str) -> bool:
    lower = mission.lower()
    if _G2_SINGLE_RE.search(mission):
        return True
    return any(phrase in lower for phrase in _G2_MULTI)


def _check_g3(mission: str) -> bool:
    lower = mission.lower()
    if _G3_SINGLE_RE.search(mission):
        return True
    return any(phrase in lower for phrase in _G3_MULTI)


def _count_g4_domains(mission: str) -> int:
    lower = mission.lower()
    return sum(1 for noun in _G4_DOMAIN_NOUNS if re.search(r"\b" + noun + r"\b", lower))


def _check_d1(mission: str) -> bool:
    return bool(_D1_RE.search(mission))


# ── Main classifier ──────────────────────────────────────────────────────────

def classify(mission: str, context: dict | None = None) -> Classification:
    """Classify a mission string; never raises."""
    try:
        return _classify_inner(mission, context)
    except Exception as exc:  # pylint: disable=broad-except
        return Classification(
            classification="GOVERNED",
            matched_rules=["INTERNAL_ERROR_DEFAULT_GOVERNED"],
            reason=f"Internal classifier error ({exc!r}); defaulting to GOVERNED for safety.",
        )


def _classify_inner(mission: str, context: dict | None) -> Classification:
    if not isinstance(mission, str):
        raise TypeError(f"mission must be a str, got {type(mission).__name__!r}")
    # 1. B1 — empty/whitespace
    if not mission.strip():
        return Classification(
            classification="BLOCKED",
            matched_rules=["B1_EMPTY_MISSION"],
            reason="Mission is empty or whitespace-only; nothing to route.",
        )

    # 2. GOVERNED rules (evaluate ALL; collect every matching rule)
    governed_rules: list[str] = []

    if _check_g5(mission):
        governed_rules.append("G5_SPRINT_REFERENCE")
    if _check_g1(mission):
        governed_rules.append("G1_REPO_WRITE")
    if _check_g2(mission):
        governed_rules.append("G2_EXECUTION_MUTATION")
    if _check_g3(mission):
        governed_rules.append("G3_WORK_TYPE")
    domain_count = _count_g4_domains(mission)
    if domain_count >= 3:
        governed_rules.append("G4_MULTI_DOMAIN")

    if governed_rules:
        rule_names = ", ".join(governed_rules)
        return Classification(
            classification="GOVERNED",
            matched_rules=governed_rules,
            reason=f"Mission matched GOVERNED rule(s): {rule_names}.",
        )

    # 3. DIRECT rules
    if _check_d1(mission):
        return Classification(
            classification="DIRECT",
            matched_rules=["D1_EXPLANATORY"],
            reason="Mission is explanatory/interrogative and contains no GOVERNED signals.",
        )

    # 4. Default
    return Classification(
        classification="GOVERNED",
        matched_rules=["DEFAULT_GOVERNED_AMBIGUOUS"],
        reason="Mission matched no specific rule; defaulting to GOVERNED for safety.",
    )

"""LisaOS Context Budget (CWO-001).

Context budgeting for worker dispatch -- implements the principle:

    MAIN KNOWS BROADLY.  WORKERS KNOW NARROWLY.

A work packet should preferentially contain ONLY:
    MISSION
    RELEVANT CURRENT STATE
    RELEVANT CONSTRAINTS
    EXACT TASK
    FILES / AREAS TO INSPECT
    DEPENDENCIES
    REQUIRED EVIDENCE
    ACCEPTANCE CONDITION
    STOP CONDITIONS

and should NOT routinely copy:
    full sprint histories, old worker conversations, unrelated findings,
    entire governance documents, giant prior reports, stale reasoning,
    large chat transcripts.

Instead: REFERENCE authoritative repository artifacts when workers can inspect
them directly (reference_not_copy).

Design guarantees:
  * BOUNDED. build_work_packet() assembles only the defined sections;
    is_within_budget() enforces a hard character bound.
  * NO COPIES. reference_not_copy() converts a candidate verbatim block into
    a path reference when the artifact is inspectable in-repo.
  * PREMIUM CONTEXT PROTECTION. premium_prep() recommends a cheaper worker to
    narrow the problem first (locate/reproduce/identify tests/constraints ->
    concise evidence packet) before premium dispatch. NOT mechanically forced.
  * FAIL OPEN ON TELEMETRY. No network calls, no spend; pure text assembly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default context budget for one worker packet (chars). Conservative: a
# bounded packet keeps worker context narrow. Adjust per deployment.
DEFAULT_PACKET_BUDGET_CHARS = 12_000

# Sections that make up a bounded work packet (ordered).
PACKET_SECTIONS = (
    "mission",
    "current_state",
    "constraints",
    "task",
    "files_areas",
    "dependencies",
    "required_evidence",
    "acceptance",
    "stop_conditions",
)

# Paths that are inspectable in-repo (reference, don't copy).
REPO_ARTIFACT_HINTS = (
    "docs/",
    "reports/",
    "registry/",
    "tests/",
    "core/",
    "README",
    "MANIFEST",
)


@dataclass
class WorkPacket:
    """A bounded worker dispatch packet."""

    mission: str = ""
    current_state: str = ""
    constraints: str = ""
    task: str = ""
    files_areas: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render the packet as text, skipping empty sections."""
        parts: list[str] = []
        if self.mission:
            parts.append(f"MISSION\n{self.mission}")
        if self.current_state:
            parts.append(f"RELEVANT CURRENT STATE\n{self.current_state}")
        if self.constraints:
            parts.append(f"RELEVANT CONSTRAINTS\n{self.constraints}")
        if self.task:
            parts.append(f"EXACT TASK\n{self.task}")
        if self.files_areas:
            parts.append("FILES / AREAS TO INSPECT\n" + "\n".join(
                f"- {f}" for f in self.files_areas))
        if self.dependencies:
            parts.append("DEPENDENCIES\n" + "\n".join(
                f"- {d}" for d in self.dependencies))
        if self.required_evidence:
            parts.append("REQUIRED EVIDENCE\n" + "\n".join(
                f"- {e}" for e in self.required_evidence))
        if self.acceptance:
            parts.append("ACCEPTANCE CONDITION\n" + "\n".join(
                f"- [ ] {a}" for a in self.acceptance))
        if self.stop_conditions:
            parts.append("STOP CONDITIONS\n" + "\n".join(
                f"- {s}" for s in self.stop_conditions))
        return "\n\n".join(parts)

    def char_count(self) -> int:
        return len(self.render())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission": self.mission,
            "current_state": self.current_state,
            "constraints": self.constraints,
            "task": self.task,
            "files_areas": self.files_areas,
            "dependencies": self.dependencies,
            "required_evidence": self.required_evidence,
            "acceptance": self.acceptance,
            "stop_conditions": self.stop_conditions,
        }


def build_work_packet(
    *,
    mission: str = "",
    current_state: str = "",
    constraints: str = "",
    task: str = "",
    files_areas: list[str] | None = None,
    dependencies: list[str] | None = None,
    required_evidence: list[str] | None = None,
    acceptance: list[str] | None = None,
    stop_conditions: list[str] | None = None,
    budget_chars: int = DEFAULT_PACKET_BUDGET_CHARS,
) -> WorkPacket:
    """Assemble a bounded work packet.

    Raises ValueError if the assembled packet exceeds the budget -- the
    dispatcher must narrow scope rather than ship an oversized packet.
    """
    packet = WorkPacket(
        mission=mission,
        current_state=current_state,
        constraints=constraints,
        task=task,
        files_areas=list(files_areas or []),
        dependencies=list(dependencies or []),
        required_evidence=list(required_evidence or []),
        acceptance=list(acceptance or []),
        stop_conditions=list(stop_conditions or []),
    )
    if packet.char_count() > budget_chars:
        raise ValueError(
            f"work packet exceeds context budget: {packet.char_count()} > "
            f"{budget_chars} chars. Narrow the packet (context is a budget).")
    return packet


def is_within_budget(packet: WorkPacket, budget_chars: int = DEFAULT_PACKET_BUDGET_CHARS) -> bool:
    """Hard bound check."""
    return packet.char_count() <= budget_chars


def reference_not_copy(text: str) -> str:
    """Convert a candidate verbatim block into a path reference when possible.

    Mission: "Reference authoritative repository artifacts instead when workers
    can inspect them directly." If `text` is (or starts with) a path that is
    inspectable in-repo, return the reference form; otherwise return text
    unchanged.
    """
    candidate = text.strip()
    # Strip markdown fences / bullet prefixes if present.
    candidate = re.sub(r"^```[a-z]*\s*", "", candidate)
    candidate = re.sub(r"^[-*]\s+", "", candidate)
    candidate = candidate.strip()
    if candidate.startswith(REPO_ARTIFACT_HINTS):
        return f"SEE REPO ARTIFACT (do not copy): {candidate}"
    return text


def premium_prep_recommendation(
    task_type: str,
    *,
    identity_registry=None,
) -> dict[str, Any] | None:
    """Recommend cheaper-worker pre-narrowing before premium dispatch.

    Returns None when no cheaper prep opportunity exists (direct premium
    dispatch is clearly more efficient) or when identity info is unavailable
    (graceful degradation). Never mechanically forces the pipeline.
    """
    if identity_registry is None:
        from core.workforce_identity import get_identity_registry
        identity_registry = get_identity_registry()
    return identity_registry.premium_prep_opportunity(task_type)


__all__ = [
    "WorkPacket",
    "build_work_packet",
    "is_within_budget",
    "reference_not_copy",
    "premium_prep_recommendation",
    "DEFAULT_PACKET_BUDGET_CHARS",
    "PACKET_SECTIONS",
]

class Planner:

    def __init__(self):
        self.workflows = {
            "review implementation": [
                "architecture-review",
                "migration-audit",
                "regression-risk",
                "docs-review"
            ],
            "prepare release": [
                "architecture-review",
                "docs-review"
            ],
            "review architecture": [
                "architecture-review"
            ]
        }

    def create_plan(self, intent: str):
        intent = intent.lower()

        for trigger, workflow in self.workflows.items():
            if trigger in intent:
                return workflow

        return ["architecture-review"]


# ── Phase 2: Natural Language Mission Planner ────────────────────────────────
#
# THE LLM PROPOSES, LISA DECIDES.
#
# Pipeline: mission → classifier (GOVERNED) → PROPOSER (untrusted LLM) →
#           VALIDATOR (deterministic, Lisa) → goal.json-compatible artifact →
#           existing dispatcher.
#
# Nothing the proposer returns reaches the dispatcher without passing every
# validation gate.  Fail closed on any violation.
#
# Public surface:
#   PlanError, PlanValidationError, MissionPlan, ProposerFn
#   build_prompt(), parse_plan_text(), known_capabilities(), validate_plan(),
#   plan_mission(), build_openclaw_proposer()
# ─────────────────────────────────────────────────────────────────────────────

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_PACKAGES = 20
MAX_DESCRIPTION_CHARS = 2000
MIN_DESCRIPTION_CHARS = 20
MAX_ID_CHARS = 64
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

_PLANNER_ALLOWED_KEYS = frozenset(
    {"id", "description", "required_capabilities", "risk", "mode", "depends_on"}
)


# ── Exceptions ────────────────────────────────────────────────────────────────

class PlanError(Exception):
    """Proposer or transport failure (not a schema/validation failure)."""


class PlanValidationError(Exception):
    """Plan rejected by Lisa's governance gate.

    `errors` is the full, ordered list of every violation found — all
    collected before raising, never stops at the first.
    """

    def __init__(self, message: str, errors: list) -> None:
        super().__init__(message)
        self.errors: list = list(errors)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MissionPlan:
    """Validated, normalized plan artifact ready for the dispatcher."""

    packages: list          # goal.json-compatible package dicts
    mission: str
    proposer_id: str        # e.g. "openclaw:lisa-claude-sonnet" or "stub"
    raw_response: str       # exactly what the proposer returned

    def to_goal_json(self) -> str:
        """Return a bare JSON array (byte-loadable by bin/lisa + lisa-dispatch)."""
        return json.dumps(self.packages, indent=2)


# ProposerFn: (prompt, context) -> raw text
ProposerFn = Callable[[str, dict], str]


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(mission: str, capabilities: list, modes: list) -> str:
    """Build the instruction prompt sent to the LLM proposer.

    Instructs the model to return ONLY a JSON array; enumerates the exact
    allowed capability vocabulary and mode list (injected, never hardcoded);
    states structural limits; forbids naming workers, models, agents, or
    providers (capabilities only — staffing is the dispatcher's job).
    """
    caps_str = ", ".join(json.dumps(c) for c in sorted(capabilities))
    modes_str = ", ".join(json.dumps(m) for m in sorted(modes))
    return (
        "You are a work-package decomposition engine for LisaOS.\n\n"
        "Your output MUST be ONLY a valid JSON array of work packages. "
        "No prose, no explanation, no markdown — just the array.\n\n"
        "## Mission\n"
        f"{mission}\n\n"
        "## Schema\n"
        "Each element must be a JSON object with these exact keys:\n"
        f'- "id": string — lowercase alphanumeric plus . _ - only, must start with '
        f"[a-z0-9], max {MAX_ID_CHARS} chars, unique within the plan\n"
        f'- "description": string — {MIN_DESCRIPTION_CHARS}–{MAX_DESCRIPTION_CHARS} chars; '
        "must be independently executable by a worker with NO shared conversational "
        "context (self-contained)\n"
        '- "required_capabilities": non-empty list of strings — MUST be chosen from '
        "the allowed vocabulary below\n"
        '- "risk": one of ["low", "normal", "critical"] (default: "normal")\n'
        f'- "mode": one of [{modes_str}] (default: "balanced")\n'
        '- "depends_on": list of ids of packages in THIS plan that must complete '
        "first; must be acyclic (default: [])\n\n"
        "No other keys are allowed.\n\n"
        f"## Allowed capability vocabulary (ONLY these values)\n"
        f"[{caps_str}]\n\n"
        f"## Allowed mode values\n"
        f"[{modes_str}]\n\n"
        "## Constraints\n"
        f"- Maximum {MAX_PACKAGES} packages.\n"
        "- Every package description must be independently executable by a worker "
        "with no shared conversational context.\n"
        "- `depends_on` must only reference `id` values in this same plan and must "
        "be acyclic.\n"
        "- DO NOT name any worker, model, agent, or provider. Use only capability "
        "strings. Staffing is the dispatcher's job.\n\n"
        "Return ONLY the JSON array, nothing else."
    )


# ── JSON extractor ────────────────────────────────────────────────────────────

def _extract_first_balanced_array(text: str) -> str:
    """Extract the first balanced top-level [...] from text.

    Returns the extracted substring or empty string if not found.
    """
    start = text.find("[")
    if start == -1:
        return ""
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return ""


def parse_plan_text(text: str) -> list:
    """Tolerant JSON extraction from LLM output.

    Accepts:
      - bare JSON array
      - ```json fenced block
      - ``` fenced block (no language tag)
      - JSON array preceded/followed by prose (extract first balanced [...])

    Never eval().  Never repairs semantics — only strips wrapping.
    Raises PlanValidationError if no JSON array can be extracted.
    """
    # 1. Try fenced code block (```json ... ``` or ``` ... ```)
    fence_match = re.search(
        r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE
    )
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass  # fall through to balanced extraction

    # 2. Extract first balanced [...] from the full text
    array_text = _extract_first_balanced_array(text)
    if array_text:
        try:
            result = json.loads(array_text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    raise PlanValidationError(
        "No valid JSON array found in proposer output.",
        errors=["proposer output contains no parseable JSON array"],
    )


# ── Capability vocabulary ─────────────────────────────────────────────────────

def known_capabilities(registry=None) -> list:
    """Derive the live capability vocabulary from employees.yml.

    Unions Employee.capabilities across EmployeeRegistry().employees,
    EXCLUDING employees where is_deterministic is True (routing/infra
    employees never execute work).

    Never hardcodes a capability list.  Never reads the legacy agents registry.
    """
    from core.workforce_resolver import EmployeeRegistry

    reg = registry if registry is not None else EmployeeRegistry()
    caps: set = set()
    for emp in reg.employees.values():
        if not emp.is_deterministic:
            caps.update(emp.capabilities)
    return sorted(caps)


# ── Governance gate ───────────────────────────────────────────────────────────

def validate_plan(
    packages,
    *,
    employee_registry=None,
    mode_registry=None,
) -> list:
    """Governance gate: validate and normalize a proposer plan.

    Collects ALL errors before raising (never stops at the first violation).
    Returns the normalized package list on success.
    Raises PlanValidationError(errors=[...]) on any failure.

    Rules P1–P12 (see docs/LISAOS/LISA_PLANNER_PHASE2.md).
    """
    from core.workforce_resolver import EmployeeRegistry, WorkPackage, VALID_RISK
    from core.workforce_modes import WorkforceModeRegistry, WorkforceModeError
    from core.dependency_graph import DependencyGraph, GraphError

    emp_reg = employee_registry if employee_registry is not None else EmployeeRegistry()
    mode_reg = mode_registry if mode_registry is not None else WorkforceModeRegistry()
    caps_vocab = set(known_capabilities(emp_reg))

    errors: list = []

    # P1: top level is a list; length ≥ 1 and ≤ MAX_PACKAGES
    if not isinstance(packages, list):
        raise PlanValidationError(
            "Plan top level is not a list.",
            errors=["P1: top level must be a list"],
        )
    if len(packages) < 1:
        errors.append("P1: plan must contain at least 1 package (got 0)")
    if len(packages) > MAX_PACKAGES:
        errors.append(
            f"P1: plan has {len(packages)} packages; maximum is {MAX_PACKAGES}"
        )

    seen_ids: set = set()
    structurally_valid: list = []  # packages that cleared all per-item checks

    for i, item in enumerate(packages):
        pkg_errors: list = []

        # P2: every element is a dict
        if not isinstance(item, dict):
            errors.append(
                f"P2[{i}]: element is not a dict (got {type(item).__name__!r})"
            )
            continue  # cannot check further without a dict

        # P11: no unknown keys (checked early so id/desc errors are reported cleanly)
        unknown_keys = set(item.keys()) - _PLANNER_ALLOWED_KEYS
        if unknown_keys:
            pkg_errors.append(
                f"P11[{i}]: unknown key(s): {sorted(unknown_keys)!r}"
            )

        # P3: id
        pkg_id = item.get("id")
        id_ok = False
        if pkg_id is None:
            pkg_errors.append(f"P3[{i}]: 'id' is missing")
        elif not isinstance(pkg_id, str) or not pkg_id.strip():
            pkg_errors.append(f"P3[{i}]: 'id' must be a non-empty string")
        else:
            if not _ID_RE.match(pkg_id):
                pkg_errors.append(
                    f"P3[{i}]: 'id' {pkg_id!r} does not match ^[a-z0-9][a-z0-9._-]*$"
                )
            elif len(pkg_id) > MAX_ID_CHARS:
                pkg_errors.append(
                    f"P3[{i}]: 'id' {pkg_id!r} exceeds {MAX_ID_CHARS} chars"
                )
            elif pkg_id in seen_ids:
                pkg_errors.append(f"P3[{i}]: duplicate id {pkg_id!r}")
            else:
                seen_ids.add(pkg_id)
                id_ok = True

        # P4: description
        desc = item.get("description")
        if desc is None:
            pkg_errors.append(f"P4[{i}]: 'description' is missing")
        elif not isinstance(desc, str):
            pkg_errors.append(f"P4[{i}]: 'description' must be a string")
        else:
            if len(desc) < MIN_DESCRIPTION_CHARS:
                pkg_errors.append(
                    f"P4[{i}]: 'description' is too short "
                    f"({len(desc)} chars; minimum is {MIN_DESCRIPTION_CHARS})"
                )
            if len(desc) > MAX_DESCRIPTION_CHARS:
                pkg_errors.append(
                    f"P4[{i}]: 'description' is too long "
                    f"({len(desc)} chars; maximum is {MAX_DESCRIPTION_CHARS})"
                )

        # P5: required_capabilities present and non-empty
        caps = item.get("required_capabilities")
        caps_ok = False
        if caps is None:
            pkg_errors.append(f"P5[{i}]: 'required_capabilities' is missing")
        elif not isinstance(caps, list) or len(caps) == 0:
            pkg_errors.append(
                f"P5[{i}]: 'required_capabilities' must be a non-empty list"
            )
        else:
            # P6: all capabilities in known vocabulary (rejects hallucinated caps)
            hallucinated = [c for c in caps if c not in caps_vocab]
            if hallucinated:
                pkg_errors.append(
                    f"P6[{i}]: hallucinated capability/ies: {hallucinated!r}; "
                    f"allowed vocabulary has {len(caps_vocab)} entries"
                )
            else:
                caps_ok = True
                # P7: staffable (only checked when caps are all valid)
                candidates = emp_reg.candidates_for(list(caps))
                if not candidates:
                    pkg_errors.append(
                        f"P7[{i}]: no employee can staff "
                        f"required_capabilities={caps!r}"
                    )

        # P8: risk
        risk = item.get("risk", "normal")
        if risk not in VALID_RISK:
            pkg_errors.append(
                f"P8[{i}]: invalid risk {risk!r}; must be one of {VALID_RISK!r}"
            )

        # P9: mode resolves without raising
        mode = item.get("mode", "balanced")
        try:
            mode_reg.get(mode)
        except Exception:
            pkg_errors.append(f"P9[{i}]: unknown mode {mode!r}")

        # P10: depends_on is a list[str]
        depends_on = item.get("depends_on", [])
        if not isinstance(depends_on, list):
            pkg_errors.append(
                f"P10[{i}]: 'depends_on' must be a list "
                f"(got {type(depends_on).__name__!r})"
            )

        errors.extend(pkg_errors)

        # Track structurally valid packages for the graph check (P12)
        if not pkg_errors and id_ok:
            structurally_valid.append(item)

    # P12: graph integrity — only when all per-item checks passed
    if not errors and structurally_valid:
        try:
            wp_objects = []
            for pkg in structurally_valid:
                wp = WorkPackage(
                    id=pkg["id"],
                    description=pkg.get("description", ""),
                    required_capabilities=list(pkg.get("required_capabilities", [])),
                    risk=pkg.get("risk", "normal"),
                    mode=pkg.get("mode", "balanced"),
                    depends_on=list(pkg.get("depends_on", [])),
                )
                wp_objects.append(wp)
            DependencyGraph.from_packages(wp_objects)
        except GraphError as exc:
            errors.append(f"P12: dependency graph error: {exc}")

    if errors:
        raise PlanValidationError(
            f"Plan rejected: {len(errors)} violation(s) found.",
            errors=errors,
        )

    # Normalize: fill defaults, enforce canonical key order
    normalized: list = []
    for pkg in packages:
        normalized.append({
            "id": pkg["id"],
            "description": pkg["description"],
            "required_capabilities": list(pkg["required_capabilities"]),
            "risk": pkg.get("risk", "normal"),
            "mode": pkg.get("mode", "balanced"),
            "depends_on": list(pkg.get("depends_on", [])),
        })
    return normalized


# ── Mission planner ───────────────────────────────────────────────────────────

def plan_mission(
    mission: str,
    *,
    proposer: ProposerFn,
    context=None,
    employee_registry=None,
    mode_registry=None,
    proposer_id: str = "unknown",
) -> MissionPlan:
    """Orchestrate: proposer → parse_plan_text → validate_plan → MissionPlan.

    Never returns an unvalidated plan.
    Any proposer exception is caught and re-raised as PlanError.
    parse_plan_text and validate_plan raise PlanValidationError on failure
    and that propagates unchanged.
    """
    from core.workforce_modes import WorkforceModeRegistry

    mode_reg = mode_registry if mode_registry is not None else WorkforceModeRegistry()

    caps = known_capabilities(employee_registry)
    modes = sorted(mode_reg.modes.keys())
    prompt = build_prompt(mission, caps, modes)
    ctx = context if context is not None else {}

    try:
        raw_response = proposer(prompt, ctx)
    except PlanError:
        raise
    except Exception as exc:
        raise PlanError(f"Proposer failed: {exc}") from exc

    # PlanValidationError propagates unchanged from here
    packages_raw = parse_plan_text(raw_response)
    packages = validate_plan(
        packages_raw,
        employee_registry=employee_registry,
        mode_registry=mode_reg,
    )

    return MissionPlan(
        packages=packages,
        mission=mission,
        proposer_id=proposer_id,
        raw_response=raw_response,
    )


# ── OpenClaw proposer factory ─────────────────────────────────────────────────

def build_openclaw_proposer(
    logical: str = "claude-sonnet",
    *,
    timeout_seconds: int = 300,
) -> ProposerFn:
    """Build a ProposerFn backed by a single OpenClaw agent subprocess call.

    Resolves the agent via the EXISTING agent_for_logical() + ProviderResolver.
    If no `agent:` binding is found for `logical`, raises PlanError immediately
    (fail closed — never guess, never fall back to 'main' or a 'wbs-*' agent,
    never reverse-match by physical model).

    Subprocess: openclaw agent --agent <id> --message <prompt> --json --timeout N
    Text extraction: result.payloads[0].text, then
                     result.meta.finalAssistantVisibleText.
    Non-zero exit / bad JSON / missing text → PlanError.
    Does NOT import core.dispatcher and does NOT build a second dispatch engine.
    This is a single meta-call that happens BEFORE a graph exists.
    """
    import os
    import shutil

    from core.openclaw_bridge import agent_for_logical
    from core.provider_resolver import ProviderResolver

    resolver = ProviderResolver()
    agent_id = agent_for_logical(logical, resolver)
    if agent_id is None:
        raise PlanError(
            f"No OpenClaw agent binding found for logical identity {logical!r}. "
            "Failing closed: cannot build proposer without a dedicated agent. "
            "Check the `agent:` field in registry/provider_resolution.yml."
        )

    openclaw_bin = (
        os.environ.get("OPENCLAW_BIN")
        or shutil.which("openclaw")
        or "/opt/homebrew/bin/openclaw"
    )

    def _propose(prompt: str, context: dict) -> str:
        cmd = [
            openclaw_bin, "agent",
            "--agent", agent_id,
            "--message", prompt,
            "--json",
            "--timeout", str(timeout_seconds),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PlanError(f"openclaw agent subprocess failed: {exc}") from exc

        if proc.returncode != 0:
            snippet = (proc.stderr.strip() or proc.stdout.strip())[:500]
            raise PlanError(
                f"openclaw agent exited {proc.returncode}: {snippet}"
            )

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise PlanError(
                f"openclaw agent returned non-JSON output: {exc}"
            ) from exc

        result_block = payload.get("result", {}) or {}

        # Primary: result.payloads[0].text
        payloads = result_block.get("payloads", []) or []
        if payloads:
            text = (payloads[0] or {}).get("text", "")
            if text:
                return text

        # Fallback: result.meta.finalAssistantVisibleText
        meta = result_block.get("meta", {}) or {}
        text = meta.get("finalAssistantVisibleText", "")
        if text:
            return text

        raise PlanError(
            "openclaw agent response contains no assistant text "
            "(checked result.payloads[0].text and "
            "result.meta.finalAssistantVisibleText)"
        )

    return _propose

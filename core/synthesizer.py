"""LisaOS deterministic evidence synthesis (Phase 5 -- LISA-I007).

Converts a VALIDATED review bundle (Phase 3/4) into an engineering report for
a human operator.

WHAT THIS IS NOT
----------------
This is not an LLM, and not a summariser. It contains no model call, no
heuristic, no scoring and no judgement of engineering quality. It ASSEMBLES
evidence that already exists and labels where each statement came from.

The four prohibitions from the sprint brief are structural here, not stylistic:

  * it never INFERS   -- every statement is copied from, or counted out of, the
                         bundle; nothing is deduced about what "probably" happened;
  * it never INVENTS  -- absent evidence produces a MISSING statement, never a
                         plausible filler;
  * it never SUPPRESSES -- every discrepancy in the bundle reaches the report;
  * it never REPAIRS  -- a declaration that contradicts observation is printed
                         as a conflict, with both sides intact and no winner.

SINGLE SOURCE OF TRUTH
----------------------
The review bundle. This module never reads OpenClaw conversations, model
transcripts, chat or prompt history, session logs, or the raw worker output --
it has no code path to any of them, and imports nothing that does.

READ-ONLY
---------
Synthesis never modifies evidence. Inputs are deep-copied before anything is
placed in a report, so a caller cannot observe mutation of the bundle it
passed in, and a report cannot alias live evidence structures.

DETERMINISM
-----------
Running synthesis twice over identical bundles produces byte-identical output.
There is deliberately NO `generated_at`, no uuid, no run counter and no other
hidden state: the report is a pure function of the bundle. Any collection
derived from a set is sorted before it reaches the output. This is enforced by
tests, not merely intended -- a timestamp here would silently destroy the
guarantee the whole phase exists to provide.
"""

from __future__ import annotations

import copy
import json
from typing import Any

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPORT_SCHEMA_VERSION = "lisa-synthesis-report/1"

# Evidence labels. These are ARCHITECTURAL: they must never be merged, and no
# statement may carry more than one. A reader must always be able to tell what
# LisaOS saw for itself from what a worker claimed.
LABEL_OBSERVED = "OBSERVED"      # LisaOS derived this itself; authoritative
LABEL_DECLARED = "DECLARED"      # the worker claimed this; untrusted
LABEL_VERIFIED = "VERIFIED"      # a claim LisaOS independently confirmed
LABEL_UNVERIFIED = "UNVERIFIED"  # a claim LisaOS has no means to confirm
LABEL_CONFLICT = "CONFLICT"      # observation and declaration disagree
LABEL_MISSING = "MISSING"        # the evidence does not exist

VALID_LABELS = (
    LABEL_OBSERVED, LABEL_DECLARED, LABEL_VERIFIED,
    LABEL_UNVERIFIED, LABEL_CONFLICT, LABEL_MISSING,
)

# Review dispositions. Derived from explicit evidence rules below -- these are
# classifications of the EVIDENCE STATE, never opinions about the engineering.
REVIEW_NO_EXECUTION = "NO_EXECUTION"
REVIEW_EXECUTION_FAILED = "EXECUTION_FAILED"
REVIEW_CONFLICTS_PRESENT = "CONFLICTS_PRESENT"
REVIEW_EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
REVIEW_EVIDENCE_COMPLETE = "EVIDENCE_COMPLETE"

SECTION_ORDER = (
    "executive_summary", "work_completed", "observed_changes",
    "worker_declarations", "validation_outcome", "discrepancies",
    "tests_observed", "tests_declared", "risks", "deferred_work",
    "review_outcome", "outstanding_uncertainties",
)

SECTION_TITLES = {
    "executive_summary": "1. Executive summary",
    "work_completed": "2. Work completed",
    "observed_changes": "3. Observed changes",
    "worker_declarations": "4. Worker declarations",
    "validation_outcome": "5. Validation outcome",
    "discrepancies": "6. Structured discrepancies",
    "tests_observed": "7. Tests observed",
    "tests_declared": "8. Tests declared",
    "risks": "9. Risks",
    "deferred_work": "10. Deferred work",
    "review_outcome": "11. Review outcome",
    "outstanding_uncertainties": "12. Outstanding uncertainties",
}


class SynthesisError(Exception):
    """The input is not a usable review bundle. Fail closed; never guess."""


# --------------------------------------------------------------------------- #
# Statements -- the atom of a report
# --------------------------------------------------------------------------- #

def statement(label: str, text: str, source: str) -> dict[str, str]:
    """One labelled, traceable statement.

    `source` is a dotted path into the review bundle, so every line of a report
    can be checked against the evidence it came from. A statement with no
    traceable source is a defect, not a convenience -- hence both are required.
    """
    if label not in VALID_LABELS:
        raise SynthesisError(f"invalid evidence label {label!r}; expected one of {VALID_LABELS}")
    return {"label": label, "text": text, "source": source}


# --------------------------------------------------------------------------- #
# Input validation -- only validated bundles may be synthesised
# --------------------------------------------------------------------------- #

_REQUIRED_BUNDLE_KEYS = ("package_id", "status", "change", "declared", "discrepancies")


def _require_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise SynthesisError(
            f"review bundle must be an object, got {type(bundle).__name__}")
    missing = [k for k in _REQUIRED_BUNDLE_KEYS if k not in bundle]
    if missing:
        raise SynthesisError(
            f"malformed review bundle: missing required key(s) {missing}")
    if not isinstance(bundle.get("change"), dict):
        raise SynthesisError("malformed review bundle: 'change' must be an object")
    if not isinstance(bundle.get("discrepancies"), list):
        raise SynthesisError("malformed review bundle: 'discrepancies' must be a list")
    declared = bundle.get("declared")
    if declared is not None and not isinstance(declared, dict):
        raise SynthesisError("malformed review bundle: 'declared' must be an object or null")
    return bundle


# --------------------------------------------------------------------------- #
# Helpers (pure)
# --------------------------------------------------------------------------- #

def _declaration_state(bundle: dict[str, Any]) -> dict[str, Any]:
    """The declaration validation outcome, tolerating Phase 3 bundles."""
    outcome = bundle.get("declaration")
    if isinstance(outcome, dict):
        return outcome
    present = bool(bundle.get("declaration_present"))
    return {"present": present, "valid": present, "errors": [], "expected": True}


def _conflicts(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        d for d in bundle["discrepancies"]
        if isinstance(d, dict) and d.get("severity") == "conflict"
    ]


def _path_list(changes: Any) -> list[str]:
    """Paths from a files_changed list, in the order the evidence recorded them."""
    if not isinstance(changes, list):
        return []
    return [c.get("path", "?") for c in changes if isinstance(c, dict)]


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

def _section_executive_summary(bundle, decl) -> list[dict[str, str]]:
    change = bundle["change"]
    attributed = _path_list(change.get("attributed_files_changed",
                                       change.get("files_changed")))
    untracked = change.get("untracked_files") or []
    conflicts = _conflicts(bundle)

    out = [
        statement(LABEL_OBSERVED,
                  f"Package '{bundle.get('package_id')}' finished with execution "
                  f"status '{bundle.get('status')}'.",
                  "bundle.status"),
        statement(LABEL_OBSERVED,
                  f"{len(attributed)} file(s) changed and {len(untracked)} "
                  f"untracked file(s) were attributed to this execution.",
                  "bundle.change.attributed_files_changed"),
    ]
    if decl["present"] and decl["valid"]:
        out.append(statement(LABEL_DECLARED,
                             "The worker supplied a declaration and it passed validation.",
                             "bundle.declaration"))
    elif decl["present"]:
        out.append(statement(LABEL_CONFLICT,
                             f"The worker supplied a declaration and it was REJECTED "
                             f"({len(decl.get('errors') or [])} violation(s)).",
                             "bundle.declaration.errors"))
    else:
        out.append(statement(LABEL_MISSING,
                             "The worker supplied no declaration.",
                             "bundle.declaration.present"))

    if conflicts:
        out.append(statement(LABEL_CONFLICT,
                             f"{len(conflicts)} conflict-level discrepancy/ies remain unresolved.",
                             "bundle.discrepancies"))
    else:
        out.append(statement(LABEL_OBSERVED,
                             "No conflict-level discrepancies were recorded.",
                             "bundle.discrepancies"))
    return out


def _section_work_completed(bundle, decl) -> list[dict[str, str]]:
    """What was done -- observed first, declared second, never merged."""
    if bundle.get("status") == "no_execution":
        refusal = bundle.get("no_execution") or {}
        return [
            statement(LABEL_OBSERVED,
                      "No work was performed: LisaOS refused to begin execution "
                      f"({refusal.get('reason')}).",
                      "bundle.no_execution.reason"),
            statement(LABEL_OBSERVED,
                      str(refusal.get("detail") or "no further detail recorded"),
                      "bundle.no_execution.detail"),
            statement(LABEL_OBSERVED,
                      "No worker was engaged, therefore no patch exists and no "
                      "declaration is expected.",
                      "bundle.no_execution.execution_started"),
        ]
    change = bundle["change"]
    attributed = _path_list(change.get("attributed_files_changed",
                                       change.get("files_changed")))
    untracked = change.get("untracked_files") or []
    out: list[dict[str, str]] = []

    if attributed or untracked:
        out.append(statement(LABEL_OBSERVED,
                             f"Repository work was observed: {len(attributed)} tracked "
                             f"file(s) modified, {len(untracked)} file(s) added untracked.",
                             "bundle.change"))
    else:
        out.append(statement(LABEL_OBSERVED,
                             "No repository change was attributed to this execution.",
                             "bundle.change.attributed_files_changed"))

    declared = bundle.get("declared") or {}
    summary = declared.get("summary")
    if decl["present"] and decl["valid"] and isinstance(summary, str) and summary.strip():
        # The worker's own account. Labelled DECLARED, never restated as fact.
        out.append(statement(LABEL_DECLARED, summary.strip(), "bundle.declared.summary"))
        if attributed or untracked:
            out.append(statement(
                LABEL_VERIFIED,
                "The worker's claim that work was performed is corroborated by "
                "observed repository change.",
                "bundle.change + bundle.declared.summary"))
        else:
            out.append(statement(
                LABEL_UNVERIFIED,
                "The worker's account cannot be corroborated: no repository change "
                "was observed. This is expected for read-only work and unexplained "
                "for implementation work; LisaOS does not distinguish the two.",
                "bundle.change + bundle.declared.summary"))
    elif decl["present"]:
        out.append(statement(LABEL_MISSING,
                             "No usable worker account: the declaration was rejected.",
                             "bundle.declaration.valid"))
    else:
        out.append(statement(LABEL_MISSING,
                             "No worker account of the work was supplied.",
                             "bundle.declaration.present"))
    return out


def _section_observed_changes(bundle) -> dict[str, Any]:
    change = bundle["change"]
    attributed = _path_list(change.get("attributed_files_changed",
                                       change.get("files_changed")))
    statements = [
        statement(LABEL_OBSERVED,
                  f"Repository {change.get('repo')} on branch {change.get('branch')}, "
                  f"base commit {change.get('base_commit')}, head commit "
                  f"{change.get('head_commit')}.",
                  "bundle.change"),
    ]
    if change.get("patch_sha256"):
        statements.append(statement(
            LABEL_VERIFIED,
            f"A patch is recorded and its integrity was checked against sha256 "
            f"{change.get('patch_sha256')}.",
            "bundle.change.patch_sha256"))
    else:
        statements.append(statement(
            LABEL_MISSING, "No patch was recorded for this package.",
            "bundle.change.patch_path"))
    if change.get("patch_truncated"):
        statements.append(statement(
            LABEL_OBSERVED,
            "The patch text in this bundle is TRUNCATED; the stored patch file is complete.",
            "bundle.change.patch_truncated"))
    if change.get("pre_existing_dirty"):
        statements.append(statement(
            LABEL_OBSERVED,
            f"{len(change['pre_existing_dirty'])} path(s) were already modified before "
            "execution and are excluded from attribution.",
            "bundle.change.pre_existing_dirty"))
    if change.get("untracked_files") and not change.get("patch_covers_untracked", False):
        statements.append(statement(
            LABEL_OBSERVED,
            f"{len(change['untracked_files'])} untracked file(s) are NOT represented "
            "in the patch.",
            "bundle.change.untracked_files"))
    return {
        "statements": statements,
        "files_changed": copy.deepcopy(change.get("attributed_files_changed",
                                                  change.get("files_changed", []))),
        "files_changed_paths": attributed,
        "untracked_files": list(change.get("untracked_files") or []),
        "pre_existing_dirty": list(change.get("pre_existing_dirty") or []),
        "patch_path": change.get("patch_path"),
        "patch_sha256": change.get("patch_sha256"),
    }


def _section_worker_declarations(bundle, decl) -> dict[str, Any]:
    declared = bundle.get("declared") or {}
    statements: list[dict[str, str]] = []
    if not decl.get("expected", True):
        statements.append(statement(
            LABEL_OBSERVED,
            "No declaration is expected: execution never began, so no worker "
            "existed to write one. This is NOT missing evidence.",
            "bundle.declaration.expected"))
    elif not decl["present"]:
        statements.append(statement(LABEL_MISSING,
                                    "Worker supplied no declaration.",
                                    "bundle.declaration.present"))
    elif not decl["valid"]:
        statements.append(statement(LABEL_CONFLICT,
                                    "Worker supplied a declaration that violated the "
                                    "declaration contract; its content is not admitted "
                                    "as evidence.",
                                    "bundle.declaration.errors"))
    else:
        for key in ("summary", "notes"):
            value = declared.get(key)
            if isinstance(value, str) and value.strip():
                statements.append(statement(LABEL_DECLARED, value.strip(),
                                            f"bundle.declared.{key}"))
        for key in ("assumptions", "warnings"):
            for item in declared.get(key) or []:
                statements.append(statement(LABEL_DECLARED, str(item),
                                            f"bundle.declared.{key}"))
        if not statements:
            statements.append(statement(LABEL_MISSING,
                                        "The declaration was valid but carried no "
                                        "narrative content.",
                                        "bundle.declared"))
    return {
        "statements": statements,
        "present": decl["present"],
        "valid": decl["valid"],
        "content": copy.deepcopy(declared) if (decl["present"] and decl["valid"]) else None,
    }


def _section_validation_outcome(bundle, decl) -> dict[str, Any]:
    statements = [
        statement(LABEL_VERIFIED,
                  "The work product passed LisaOS work-product validation; an invalid "
                  "work product cannot reach synthesis.",
                  "bundle (validated by build_review_bundle)"),
    ]
    if not decl.get("expected", True):
        statements.append(statement(
            LABEL_OBSERVED,
            "Declaration validation did not run, and was not required: no worker "
            "was engaged.",
            "bundle.declaration.expected"))
    elif not decl["present"]:
        statements.append(statement(LABEL_MISSING,
                                    "Declaration validation did not run: nothing was declared.",
                                    "bundle.declaration.present"))
    elif decl["valid"]:
        statements.append(statement(LABEL_VERIFIED,
                                    "The worker declaration passed contract validation.",
                                    "bundle.declaration.valid"))
    else:
        statements.append(statement(LABEL_CONFLICT,
                                    "The worker declaration FAILED contract validation.",
                                    "bundle.declaration.valid"))
        for err in decl.get("errors") or []:
            statements.append(statement(LABEL_CONFLICT, str(err),
                                        "bundle.declaration.errors"))
    if bundle.get("capture_error"):
        statements.append(statement(LABEL_OBSERVED,
                                    f"Evidence capture reported a problem: "
                                    f"{bundle['capture_error']}",
                                    "bundle.capture_error"))
    return {
        "statements": statements,
        "work_product_valid": True,
        "declaration_present": decl["present"],
        "declaration_valid": decl["valid"],
        "declaration_errors": list(decl.get("errors") or []),
    }


def _section_discrepancies(bundle) -> dict[str, Any]:
    """Every discrepancy, in evidence order. None is dropped, merged or ranked."""
    records = bundle["discrepancies"]
    statements: list[dict[str, str]] = []
    for item in records:
        if isinstance(item, str):  # Phase 3 legacy form
            statements.append(statement(LABEL_OBSERVED, item, "bundle.discrepancies"))
            continue
        if not isinstance(item, dict):
            continue
        severity = item.get("severity")
        label = LABEL_CONFLICT if severity == "conflict" else LABEL_OBSERVED
        statements.append(statement(
            label, f"[{severity}] {item.get('code')}: {item.get('detail')}",
            "bundle.discrepancies"))
    if not statements:
        statements.append(statement(LABEL_OBSERVED, "No discrepancies were recorded.",
                                    "bundle.discrepancies"))
    return {
        "statements": statements,
        "records": copy.deepcopy(records),
        "conflict_count": len(_conflicts(bundle)),
        "total_count": len(records),
    }


def _section_tests_observed(bundle) -> dict[str, Any]:
    """LisaOS does not observe test execution. Say so, every time.

    This section exists precisely so the absence is explicit rather than being
    quietly filled with the worker's declared tests -- which is exactly the
    substitution this whole architecture is designed to prevent.
    """
    return {
        "statements": [statement(
            LABEL_MISSING,
            "LisaOS observes no test execution. No test result in this report is "
            "independently verified; see 'Tests declared' for the worker's own "
            "account.",
            "not collected by the evidence pipeline")],
        "tests": [],
    }


def _section_tests_declared(bundle, decl) -> dict[str, Any]:
    declared = bundle.get("declared") or {}
    tests = declared.get("tests") if (decl["present"] and decl["valid"]) else None
    statements: list[dict[str, str]] = []
    if not decl.get("expected", True):
        statements.append(statement(
            LABEL_OBSERVED,
            "No declared tests: execution never began, so none is expected.",
            "bundle.declaration.expected"))
    elif not decl["present"]:
        statements.append(statement(LABEL_MISSING,
                                    "No declaration, therefore no declared tests.",
                                    "bundle.declaration.present"))
    elif not decl["valid"]:
        statements.append(statement(LABEL_MISSING,
                                    "The declaration was rejected; its test claims are "
                                    "not admitted as evidence.",
                                    "bundle.declaration.valid"))
    elif not tests:
        statements.append(statement(LABEL_MISSING,
                                    "The worker declared no test evidence.",
                                    "bundle.declared.tests"))
    else:
        for entry in tests:
            if not isinstance(entry, dict):
                continue
            statements.append(statement(
                LABEL_UNVERIFIED,
                f"{entry.get('command')} -> {entry.get('result')} "
                f"(passed={entry.get('passed')}, failed={entry.get('failed')}, "
                f"skipped={entry.get('skipped')}, {entry.get('duration_seconds')}s, "
                f"env={entry.get('environment')})",
                "bundle.declared.tests"))
    return {"statements": statements, "tests": copy.deepcopy(tests or [])}


def _section_string_list(bundle, decl, key: str, empty_text: str) -> dict[str, Any]:
    declared = bundle.get("declared") or {}
    items = declared.get(key) if (decl["present"] and decl["valid"]) else None
    statements: list[dict[str, str]] = []
    if not decl.get("expected", True):
        statements.append(statement(
            LABEL_OBSERVED,
            f"No declared {key}: execution never began, so none is expected.",
            f"bundle.declared.{key}"))
    elif not decl["present"] or not decl["valid"]:
        statements.append(statement(LABEL_MISSING,
                                    f"No admissible declaration, therefore no declared {key}.",
                                    f"bundle.declared.{key}"))
    elif not items:
        statements.append(statement(LABEL_MISSING, empty_text, f"bundle.declared.{key}"))
    else:
        for item in items:
            statements.append(statement(LABEL_DECLARED, str(item), f"bundle.declared.{key}"))
    return {"statements": statements, "items": list(items or [])}


def _review_outcome(bundle, decl) -> dict[str, Any]:
    """Classify the EVIDENCE STATE by explicit rules.

    This is a classification of what evidence exists, not an opinion about the
    engineering and not an approval decision (approvals are out of scope). The
    rules are listed on the report so a reader can re-derive the disposition.
    """
    rules = [
        "NO_EXECUTION         if LisaOS refused before execution began",
        "EXECUTION_FAILED     if execution began and did not complete",
        "CONFLICTS_PRESENT    if any discrepancy has severity 'conflict'",
        "EVIDENCE_INCOMPLETE  if a declaration was expected but none is valid",
        "EVIDENCE_COMPLETE    otherwise",
    ]
    conflicts = _conflicts(bundle)
    if bundle.get("status") == "no_execution":
        refusal = bundle.get("no_execution") or {}
        return {
            "statements": [
                statement(LABEL_OBSERVED,
                          f"{REVIEW_NO_EXECUTION}: LisaOS refused to begin execution "
                          f"({refusal.get('reason')}): {refusal.get('detail')}",
                          "bundle.no_execution"),
                statement(LABEL_OBSERVED,
                          "No worker was engaged, so there is no patch, no test "
                          "evidence and no declaration to expect. This is distinct "
                          "from an execution that began and failed.",
                          "bundle.no_execution.execution_started"),
                statement(LABEL_OBSERVED,
                          "This disposition classifies the EVIDENCE STATE only. It is "
                          "not an approval, and not a judgement of engineering quality.",
                          "synthesizer rule set"),
            ],
            "disposition": REVIEW_NO_EXECUTION,
            "rules": rules,
        }
    if bundle.get("status") != "completed":
        disposition = REVIEW_EXECUTION_FAILED
        label, detail = LABEL_OBSERVED, (
            f"Execution status is '{bundle.get('status')}', not 'completed'.")
    elif conflicts:
        disposition = REVIEW_CONFLICTS_PRESENT
        label, detail = LABEL_CONFLICT, (
            f"{len(conflicts)} conflict-level discrepancy/ies are unresolved.")
    elif decl.get("expected", True) and not (decl["present"] and decl["valid"]):
        disposition = REVIEW_EVIDENCE_INCOMPLETE
        label, detail = LABEL_MISSING, (
            "No admissible worker declaration accompanies the observed evidence.")
    else:
        disposition = REVIEW_EVIDENCE_COMPLETE
        label, detail = LABEL_OBSERVED, (
            "Observed evidence and an admissible declaration are both present, with "
            "no conflict-level discrepancies.")
    return {
        "statements": [
            statement(label, f"{disposition}: {detail}", "derived from bundle by rule"),
            statement(LABEL_OBSERVED,
                      "This disposition classifies the EVIDENCE STATE only. It is not "
                      "an approval, and not a judgement of engineering quality.",
                      "synthesizer rule set"),
        ],
        "disposition": disposition,
        "rules": rules,
    }


def _section_uncertainties(bundle, decl) -> dict[str, Any]:
    """Everything a reader must not assume. Deterministic order."""
    items: list[dict[str, str]] = [
        statement(LABEL_UNVERIFIED,
                  "No test result is independently verified: LisaOS does not observe "
                  "test execution.",
                  "not collected by the evidence pipeline"),
        statement(LABEL_UNVERIFIED,
                  "Change attribution is temporal, not causal: any change made in the "
                  "repository during this execution window is attributed to it.",
                  "bundle.change (attribution model)"),
    ]
    change = bundle["change"]
    if not decl["present"]:
        items.append(statement(LABEL_MISSING,
                               "The worker's intent, risks and deferred work are unknown: "
                               "nothing was declared.",
                               "bundle.declaration.present"))
    elif not decl["valid"]:
        items.append(statement(LABEL_MISSING,
                               "The worker's account is unavailable: its declaration was "
                               "rejected and is not admitted as evidence.",
                               "bundle.declaration.valid"))
    if change.get("untracked_files") and not change.get("patch_covers_untracked", False):
        items.append(statement(LABEL_UNVERIFIED,
                               "The content of untracked files is not captured in the "
                               "patch and cannot be reviewed from this report.",
                               "bundle.change.untracked_files"))
    if change.get("patch_truncated"):
        items.append(statement(LABEL_UNVERIFIED,
                               "The patch shown here is truncated; review the stored "
                               "patch file for the complete diff.",
                               "bundle.change.patch_truncated"))
    if change.get("pre_existing_dirty"):
        items.append(statement(LABEL_UNVERIFIED,
                               "The repository was already modified before execution; "
                               "authorship of those paths is unknown to LisaOS.",
                               "bundle.change.pre_existing_dirty"))
    if bundle.get("capture_error"):
        items.append(statement(LABEL_MISSING,
                               "Evidence capture reported a problem, so the observed "
                               "half may be incomplete.",
                               "bundle.capture_error"))
    return {"statements": items}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def synthesize(bundle: dict[str, Any]) -> dict[str, Any]:
    """Assemble a validated review bundle into a structured engineering report.

    Pure and deterministic: identical bundles produce identical reports. The
    input is never mutated.
    """
    bundle = _require_bundle(bundle)
    source = copy.deepcopy(bundle)  # read-only guarantee
    decl = _declaration_state(source)

    sections: dict[str, Any] = {
        "executive_summary": {"statements": _section_executive_summary(source, decl)},
        "work_completed": {"statements": _section_work_completed(source, decl)},
        "observed_changes": _section_observed_changes(source),
        "worker_declarations": _section_worker_declarations(source, decl),
        "validation_outcome": _section_validation_outcome(source, decl),
        "discrepancies": _section_discrepancies(source),
        "tests_observed": _section_tests_observed(source),
        "tests_declared": _section_tests_declared(source, decl),
        "risks": _section_string_list(source, decl, "risks",
                                      "The worker declared no risks."),
        "deferred_work": _section_string_list(source, decl, "deferred",
                                              "The worker declared no deferred work."),
        "review_outcome": _review_outcome(source, decl),
        "outstanding_uncertainties": _section_uncertainties(source, decl),
    }

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "package_id": source.get("package_id"),
        "work_product_id": source.get("work_product_id"),
        "execution": {
            "status": source.get("status"),
            "worker": copy.deepcopy(source.get("worker") or {}),
            "context": copy.deepcopy(source.get("context") or {}),
        },
        "section_order": list(SECTION_ORDER),
        "sections": sections,
    }


def render_report(report: dict[str, Any]) -> str:
    """Render a structured report as deterministic plain text.

    Every line carries its evidence label, so observed and declared material
    stay distinguishable in the human-readable form too.
    """
    if not isinstance(report, dict) or "sections" not in report:
        raise SynthesisError("render_report requires a report from synthesize()")

    execution = report.get("execution") or {}
    worker = execution.get("worker") or {}
    context = execution.get("context") or {}
    lines: list[str] = [
        "=" * 78,
        f"LisaOS Engineering Report — package '{report.get('package_id')}'",
        "=" * 78,
        f"work product : {report.get('work_product_id')}",
        f"status       : {execution.get('status')}",
        f"worker       : {worker.get('employee')} / {worker.get('agent_id')} "
        f"({worker.get('model')})",
        f"job / sprint : {context.get('job_id')} / {context.get('sprint')}",
        "",
        "Evidence labels: OBSERVED (LisaOS-derived, authoritative) · DECLARED "
        "(worker-supplied)",
        "                 VERIFIED (confirmed) · UNVERIFIED (unconfirmable) · "
        "CONFLICT · MISSING",
        "",
    ]

    for key in report.get("section_order", SECTION_ORDER):
        section = report["sections"].get(key) or {}
        lines.append(SECTION_TITLES.get(key, key))
        lines.append("-" * 78)
        for item in section.get("statements", []):
            lines.append(f"  [{item['label']:<10}] {item['text']}")
            lines.append(f"               ↳ source: {item['source']}")
        if key == "observed_changes":
            for path in section.get("files_changed_paths", []):
                lines.append(f"  [OBSERVED  ] changed: {path}")
            for path in section.get("untracked_files", []):
                lines.append(f"  [OBSERVED  ] added (untracked): {path}")
        if key == "review_outcome":
            lines.append("  rules:")
            for rule in section.get("rules", []):
                lines.append(f"    - {rule}")
        lines.append("")

    lines.append("=" * 78)
    lines.append("Generated by the LisaOS deterministic synthesizer from a validated")
    lines.append("review bundle only. No conversation, transcript or chat history was")
    lines.append("consulted. No fact in this report was inferred or invented.")
    lines.append("=" * 78)
    return "\n".join(lines)


def report_to_json(report: dict[str, Any]) -> str:
    """Stable JSON rendering (sorted keys) for diffing and archival."""
    return json.dumps(report, indent=2, sort_keys=True)

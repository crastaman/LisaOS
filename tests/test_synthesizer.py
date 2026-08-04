"""Proof-of-work tests for the LisaOS deterministic synthesizer (Phase 5).

Run:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_synthesizer -v

Fully hermetic: pure functions over in-memory bundles, plus real throwaway git
repos where an end-to-end bundle is needed. No network, no OpenClaw, no spend.

Covers: complete bundles, missing declarations, validation failure, conflicting
evidence, missing evidence, multiple discrepancies, byte-identical repeatability,
malformed bundles, and the guarantee that synthesis never mutates evidence.
"""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.dispatcher import ExecutionResult, WORKER_SIMULATED, mark_executor
from core.synthesizer import (
    LABEL_CONFLICT, LABEL_DECLARED, LABEL_MISSING, LABEL_OBSERVED,
    LABEL_UNVERIFIED, LABEL_VERIFIED, REPORT_SCHEMA_VERSION,
    REVIEW_CONFLICTS_PRESENT, REVIEW_EVIDENCE_COMPLETE,
    REVIEW_EVIDENCE_INCOMPLETE, REVIEW_EXECUTION_FAILED, SECTION_ORDER,
    SynthesisError, render_report, report_to_json, statement, synthesize,
)
from core.work_product import (
    DECLARATION_SCHEMA_VERSION, build_review_bundle, declared_path,
    find_work_products, load_work_product, work_product_recording_executor,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _bundle(**overrides):
    """A complete, valid review bundle."""
    bundle = {
        "schema_version": "lisa-work-product/1",
        "package_id": "pkg-1",
        "work_product_id": "wp-abc",
        "status": "completed",
        "worker": {"employee": "implementation-engineer",
                   "agent_id": "lisa-claude-sonnet",
                   "model": "anthropic/claude-sonnet-4-6"},
        "context": {"job_id": "job-1", "sprint": "LISA-I007"},
        "change": {
            "repo": "/tmp/repo", "branch": "main",
            "base_commit": "a" * 40, "head_commit": "b" * 40,
            "files_changed": [{"status": "M", "path": "app.py"}],
            "attributed_files_changed": [{"status": "M", "path": "app.py"}],
            "pre_existing_dirty": [], "untracked_files": [],
            "patch_path": "/tmp/store/pkg-1.patch",
            "patch_sha256": "c" * 64, "patch_text": "diff --git a/app.py\n+x\n",
            "patch_truncated": False, "patch_covers_untracked": False,
        },
        "declared": {
            "summary": "Implemented the change described in the brief.",
            "tests": [{"command": "python3 -m unittest discover tests",
                       "result": "pass", "duration_seconds": 12.0,
                       "passed": 10, "failed": 0, "skipped": 1,
                       "environment": "python3.14 darwin"}],
            "risks": ["touches the cache layer"],
            "warnings": ["config reload required"],
            "deferred": ["docs not updated"],
            "assumptions": ["fixture data is representative"],
            "notes": "check the boundary case",
        },
        "declaration": {"present": True, "valid": True, "errors": [],
                        "schema_version": DECLARATION_SCHEMA_VERSION},
        "declaration_present": True,
        "discrepancies": [],
        "capture_error": None,
    }
    bundle.update(overrides)
    return bundle


def _labels(section):
    return [s["label"] for s in section["statements"]]


def _texts(section):
    return " | ".join(s["text"] for s in section["statements"])


# --------------------------------------------------------------------------- #
# Input handling
# --------------------------------------------------------------------------- #

class TestBundleValidation(unittest.TestCase):

    def test_complete_bundle_synthesises(self):
        report = synthesize(_bundle())
        self.assertEqual(report["schema_version"], REPORT_SCHEMA_VERSION)
        self.assertEqual(report["package_id"], "pkg-1")

    def test_all_twelve_sections_present_and_ordered(self):
        report = synthesize(_bundle())
        self.assertEqual(tuple(report["section_order"]), SECTION_ORDER)
        self.assertEqual(len(SECTION_ORDER), 12)
        for key in SECTION_ORDER:
            self.assertIn(key, report["sections"], key)

    def test_non_dict_rejected(self):
        for bad in ("string", ["list"], None, 42):
            with self.assertRaises(SynthesisError):
                synthesize(bad)

    def test_missing_required_key_rejected(self):
        for key in ("package_id", "status", "change", "declared", "discrepancies"):
            bundle = _bundle()
            del bundle[key]
            with self.assertRaises(SynthesisError, msg=key):
                synthesize(bundle)

    def test_malformed_change_rejected(self):
        with self.assertRaises(SynthesisError):
            synthesize(_bundle(change="not an object"))

    def test_malformed_discrepancies_rejected(self):
        with self.assertRaises(SynthesisError):
            synthesize(_bundle(discrepancies={"not": "a list"}))

    def test_malformed_declared_rejected(self):
        with self.assertRaises(SynthesisError):
            synthesize(_bundle(declared="a summary string"))

    def test_invalid_label_rejected(self):
        with self.assertRaises(SynthesisError):
            statement("PROBABLY", "text", "source")


# --------------------------------------------------------------------------- #
# Read-only guarantee
# --------------------------------------------------------------------------- #

class TestReadOnly(unittest.TestCase):

    def test_synthesis_never_mutates_the_bundle(self):
        bundle = _bundle()
        before = copy.deepcopy(bundle)
        synthesize(bundle)
        self.assertEqual(bundle, before)

    def test_report_does_not_alias_bundle_structures(self):
        bundle = _bundle()
        report = synthesize(bundle)
        report["sections"]["observed_changes"]["files_changed"].append({"path": "x"})
        report["sections"]["risks"]["items"].append("injected")
        self.assertEqual(len(bundle["change"]["attributed_files_changed"]), 1)
        self.assertEqual(bundle["declared"]["risks"], ["touches the cache layer"])


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #

class TestDeterminism(unittest.TestCase):

    def test_repeated_synthesis_is_byte_identical(self):
        bundle = _bundle()
        first = report_to_json(synthesize(bundle))
        second = report_to_json(synthesize(bundle))
        self.assertEqual(first, second)

    def test_separate_equal_bundles_produce_identical_reports(self):
        self.assertEqual(report_to_json(synthesize(_bundle())),
                         report_to_json(synthesize(_bundle())))

    def test_rendered_text_is_byte_identical(self):
        bundle = _bundle()
        self.assertEqual(render_report(synthesize(bundle)),
                         render_report(synthesize(bundle)))

    def test_report_contains_no_timestamp_or_identifier_drift(self):
        """A generated_at or uuid would silently destroy determinism."""
        text = report_to_json(synthesize(_bundle()))
        for forbidden in ("generated_at", "created_at", "synthesised_at",
                          "synthesized_at", "timestamp"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_determinism_holds_for_degenerate_bundles(self):
        for bundle in (
            _bundle(declared=None, declaration={"present": False, "valid": False,
                                                "errors": [], "schema_version": "x"}),
            _bundle(status="failed"),
            _bundle(discrepancies=[{"code": "X", "severity": "conflict", "detail": "d"}]),
        ):
            self.assertEqual(report_to_json(synthesize(bundle)),
                             report_to_json(synthesize(bundle)))


# --------------------------------------------------------------------------- #
# Evidence labelling -- observed and declared must never merge
# --------------------------------------------------------------------------- #

class TestEvidenceLabels(unittest.TestCase):

    def test_worker_summary_is_labelled_declared_not_observed(self):
        section = synthesize(_bundle())["sections"]["work_completed"]
        declared = [s for s in section["statements"] if s["label"] == LABEL_DECLARED]
        self.assertTrue(declared)
        self.assertIn("Implemented the change", declared[0]["text"])

    def test_repository_facts_are_labelled_observed(self):
        section = synthesize(_bundle())["sections"]["observed_changes"]
        self.assertIn(LABEL_OBSERVED, _labels(section))

    def test_patch_integrity_is_verified(self):
        section = synthesize(_bundle())["sections"]["observed_changes"]
        verified = [s for s in section["statements"] if s["label"] == LABEL_VERIFIED]
        self.assertTrue(any("sha256" in s["text"] for s in verified))

    def test_declared_tests_are_unverified_never_verified(self):
        section = synthesize(_bundle())["sections"]["tests_declared"]
        self.assertEqual(set(_labels(section)), {LABEL_UNVERIFIED})
        self.assertNotIn(LABEL_VERIFIED, _labels(section))

    def test_corroborated_work_is_verified(self):
        section = synthesize(_bundle())["sections"]["work_completed"]
        self.assertIn(LABEL_VERIFIED, _labels(section))

    def test_uncorroborated_summary_is_unverified_not_conflict(self):
        """Read-only work legitimately changes nothing; that is not a conflict."""
        bundle = _bundle()
        bundle["change"]["attributed_files_changed"] = []
        bundle["change"]["files_changed"] = []
        section = synthesize(bundle)["sections"]["work_completed"]
        self.assertIn(LABEL_UNVERIFIED, _labels(section))
        self.assertNotIn(LABEL_VERIFIED, _labels(section))

    def test_every_statement_has_a_valid_label_and_source(self):
        report = synthesize(_bundle())
        for key in SECTION_ORDER:
            for item in report["sections"][key].get("statements", []):
                self.assertIn(item["label"],
                              (LABEL_OBSERVED, LABEL_DECLARED, LABEL_VERIFIED,
                               LABEL_UNVERIFIED, LABEL_CONFLICT, LABEL_MISSING))
                self.assertTrue(item["source"].strip(), f"{key}: empty source")
                self.assertTrue(item["text"].strip(), f"{key}: empty text")

    def test_declared_assumptions_and_notes_reach_the_report(self):
        """Regression (LISA-I007): declared evidence must never be dropped."""
        section = synthesize(_bundle())["sections"]["worker_declarations"]
        text = _texts(section)
        self.assertIn("fixture data is representative", text)
        self.assertIn("check the boundary case", text)
        self.assertIn("config reload required", text)

    def test_rendered_text_shows_labels(self):
        text = render_report(synthesize(_bundle()))
        self.assertIn("[OBSERVED", text)
        self.assertIn("[DECLARED", text)
        self.assertIn("source:", text)


# --------------------------------------------------------------------------- #
# Missing evidence stays missing
# --------------------------------------------------------------------------- #

class TestMissingEvidence(unittest.TestCase):

    def _no_declaration(self):
        return _bundle(declared=None, declaration_present=False,
                       declaration={"present": False, "valid": False, "errors": [
                           "no worker declaration was written"],
                           "schema_version": DECLARATION_SCHEMA_VERSION})

    def test_missing_declaration_is_stated_not_filled(self):
        report = synthesize(self._no_declaration())
        self.assertIn(LABEL_MISSING, _labels(report["sections"]["worker_declarations"]))
        self.assertIn("no declaration",
                      _texts(report["sections"]["worker_declarations"]).lower())

    def test_missing_declaration_leaves_risks_and_deferred_missing(self):
        report = synthesize(self._no_declaration())
        for key in ("risks", "deferred_work"):
            self.assertEqual(set(_labels(report["sections"][key])), {LABEL_MISSING})
            self.assertEqual(report["sections"][key]["items"], [])

    def test_missing_declaration_leaves_declared_tests_missing(self):
        report = synthesize(self._no_declaration())
        self.assertEqual(set(_labels(report["sections"]["tests_declared"])),
                         {LABEL_MISSING})
        self.assertEqual(report["sections"]["tests_declared"]["tests"], [])

    def test_observed_tests_always_missing(self):
        """LisaOS observes no tests; declared tests must never fill the gap."""
        report = synthesize(_bundle())
        section = report["sections"]["tests_observed"]
        self.assertEqual(set(_labels(section)), {LABEL_MISSING})
        self.assertEqual(section["tests"], [])
        self.assertIn("observes no test execution", _texts(section))

    def test_absent_patch_is_reported_missing(self):
        bundle = _bundle()
        bundle["change"]["patch_path"] = None
        bundle["change"]["patch_sha256"] = None
        section = synthesize(bundle)["sections"]["observed_changes"]
        self.assertTrue(any(s["label"] == LABEL_MISSING and "No patch" in s["text"]
                            for s in section["statements"]))

    def test_capture_error_surfaces_as_uncertainty(self):
        bundle = _bundle(capture_error="git diff failed")
        report = synthesize(bundle)
        self.assertIn("capture", _texts(report["sections"]["validation_outcome"]).lower())
        self.assertIn("incomplete",
                      _texts(report["sections"]["outstanding_uncertainties"]).lower())

    def test_empty_declaration_content_reported_missing(self):
        bundle = _bundle(declared={"summary": "   "})
        section = synthesize(bundle)["sections"]["worker_declarations"]
        self.assertIn(LABEL_MISSING, _labels(section))


# --------------------------------------------------------------------------- #
# Conflicts stay visible
# --------------------------------------------------------------------------- #

class TestConflicts(unittest.TestCase):

    def _rejected_declaration(self):
        return _bundle(
            declared=None, declaration_present=True,
            declaration={"present": True, "valid": False,
                         "errors": ["D1: 'files_changed' is observed by LisaOS "
                                    "and must not be declared by a worker"],
                         "schema_version": DECLARATION_SCHEMA_VERSION},
            discrepancies=[{"code": "DECLARATION_INVALID", "severity": "conflict",
                            "detail": "worker declaration was rejected"}])

    def test_rejected_declaration_is_a_conflict(self):
        report = synthesize(self._rejected_declaration())
        self.assertIn(LABEL_CONFLICT, _labels(report["sections"]["worker_declarations"]))
        self.assertIn(LABEL_CONFLICT, _labels(report["sections"]["validation_outcome"]))

    def test_validation_errors_are_reproduced_verbatim(self):
        report = synthesize(self._rejected_declaration())
        self.assertIn("D1: 'files_changed' is observed by LisaOS",
                      _texts(report["sections"]["validation_outcome"]))

    def test_rejected_declaration_content_is_not_admitted(self):
        report = synthesize(self._rejected_declaration())
        self.assertIsNone(report["sections"]["worker_declarations"]["content"])

    def test_conflict_is_never_resolved_or_averaged(self):
        """Both sides must survive; no winner is chosen, no hedge is offered."""
        bundle = _bundle(discrepancies=[{
            "code": "SUMMARY_WITHOUT_CHANGE", "severity": "conflict",
            "detail": "worker declared work but no change was observed"}])
        bundle["change"]["attributed_files_changed"] = []
        bundle["change"]["files_changed"] = []
        report = synthesize(bundle)
        text = render_report(report)
        # observed side present
        self.assertIn("No repository change was attributed", text)
        # declared side present, verbatim
        self.assertIn("Implemented the change described in the brief.", text)
        # no hedging language
        for weasel in ("probably", "likely", "appears to", "presumably", "seems"):
            self.assertNotIn(weasel, text.lower(), weasel)

    def test_multiple_discrepancies_all_survive_in_order(self):
        records = [
            {"code": "A", "severity": "conflict", "detail": "first"},
            {"code": "B", "severity": "warning", "detail": "second"},
            {"code": "C", "severity": "info", "detail": "third"},
            {"code": "D", "severity": "warning", "detail": "fourth"},
        ]
        section = synthesize(_bundle(discrepancies=records))["sections"]["discrepancies"]
        self.assertEqual(section["total_count"], 4)
        self.assertEqual(section["conflict_count"], 1)
        rendered = [s["text"] for s in section["statements"]]
        self.assertEqual(len(rendered), 4)
        for order, code in enumerate(("A", "B", "C", "D")):
            self.assertIn(code, rendered[order])

    def test_legacy_string_discrepancies_still_reported(self):
        section = synthesize(
            _bundle(discrepancies=["a phase 3 string discrepancy"]))["sections"]["discrepancies"]
        self.assertIn("phase 3 string", _texts(section))

    def test_no_discrepancies_is_stated_explicitly(self):
        section = synthesize(_bundle())["sections"]["discrepancies"]
        self.assertIn("No discrepancies", _texts(section))


# --------------------------------------------------------------------------- #
# Review outcome (evidence-state classification)
# --------------------------------------------------------------------------- #

class TestReviewOutcome(unittest.TestCase):

    def _disposition(self, bundle):
        return synthesize(bundle)["sections"]["review_outcome"]["disposition"]

    def test_complete_evidence(self):
        self.assertEqual(self._disposition(_bundle()), REVIEW_EVIDENCE_COMPLETE)

    def test_failed_execution_dominates(self):
        bundle = _bundle(status="failed", discrepancies=[
            {"code": "X", "severity": "conflict", "detail": "d"}])
        self.assertEqual(self._disposition(bundle), REVIEW_EXECUTION_FAILED)

    def test_conflicts_present(self):
        bundle = _bundle(discrepancies=[
            {"code": "X", "severity": "conflict", "detail": "d"}])
        self.assertEqual(self._disposition(bundle), REVIEW_CONFLICTS_PRESENT)

    def test_incomplete_without_declaration(self):
        bundle = _bundle(declared=None, declaration={
            "present": False, "valid": False, "errors": [], "schema_version": "x"})
        self.assertEqual(self._disposition(bundle), REVIEW_EVIDENCE_INCOMPLETE)

    def test_rules_are_published_with_the_outcome(self):
        section = synthesize(_bundle())["sections"]["review_outcome"]
        # One rule per disposition; NO_EXECUTION was added in LISA-I012.
        self.assertEqual(len(section["rules"]), 5)
        for disposition in ("NO_EXECUTION", "EXECUTION_FAILED", "CONFLICTS_PRESENT",
                            "EVIDENCE_INCOMPLETE", "EVIDENCE_COMPLETE"):
            self.assertTrue(any(disposition in r for r in section["rules"]), disposition)

    def test_outcome_disclaims_being_an_approval(self):
        section = synthesize(_bundle())["sections"]["review_outcome"]
        self.assertIn("not an approval", _texts(section).lower())


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

class TestRendering(unittest.TestCase):

    def test_render_requires_a_report(self):
        for bad in ({"no": "sections"}, "text", None):
            with self.assertRaises(SynthesisError):
                render_report(bad)

    def test_render_includes_every_section_title(self):
        text = render_report(synthesize(_bundle()))
        for number in range(1, 13):
            self.assertIn(f"{number}. ", text)

    def test_render_lists_changed_files(self):
        text = render_report(synthesize(_bundle()))
        self.assertIn("changed: app.py", text)

    def test_render_states_its_own_provenance(self):
        text = render_report(synthesize(_bundle()))
        self.assertIn("No conversation, transcript or chat history was", text)

    def test_json_rendering_is_stable(self):
        report = synthesize(_bundle())
        self.assertEqual(report_to_json(report), report_to_json(report))
        json.loads(report_to_json(report))


# --------------------------------------------------------------------------- #
# End to end: real work product -> bundle -> report
# --------------------------------------------------------------------------- #

class TestEndToEnd(unittest.TestCase):

    def _repo(self, tmp):
        repo = Path(tmp) / "repo"
        repo.mkdir()
        for args in (["init", "-q", "-b", "main"],
                     ["config", "user.email", "t@lisaos.local"],
                     ["config", "user.name", "LisaOS Test"]):
            subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
        (repo / "seed.txt").write_text("seed\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"],
                       capture_output=True)
        return str(repo)

    def test_captured_evidence_synthesises_into_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            store = Path(tmp) / "store"
            path = declared_path("pkg-e2e", store=store)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "schema_version": DECLARATION_SCHEMA_VERSION,
                "summary": "Added the implementation module.",
                "tests": [{"command": "unittest", "result": "pass",
                           "duration_seconds": 1.0, "passed": 2, "failed": 0,
                           "skipped": 0, "environment": "py3.14"}],
                "risks": ["none identified"], "deferred": ["docs"],
            }))

            def _fn(pkg, assignment):
                (Path(repo) / "impl.py").write_text("# implementation\n")
                return ExecutionResult(success=True, actual_runtime="claude-cli",
                                       agent_id="lisa-claude-sonnet", run_id="run-e2e")

            class _Pkg:
                id = "pkg-e2e"
                description = "implement the module"

            class _Assignment:
                employee = "implementation-engineer"
                resolved_logical = "claude-sonnet"
                physical_model = "anthropic/claude-sonnet-4-6"
                provider_id = "anthropic"
                resolved_runtime = "claude-cli"

            wrapped = work_product_recording_executor(
                mark_executor(_fn, WORKER_SIMULATED), repo=repo, store=store)
            wrapped(_Pkg(), _Assignment())

            wp = load_work_product(
                find_work_products(package_id="pkg-e2e", store=store)[0]["artifact_path"])
            bundle = build_review_bundle(wp, store=store)
            report = synthesize(bundle)
            text = render_report(report)

            # observed half
            self.assertIn("impl.py", text)
            # declared half, verbatim and labelled
            self.assertIn("Added the implementation module.", text)
            self.assertIn("[DECLARED", text)
            # declared tests never presented as verified
            self.assertEqual(
                set(_labels(report["sections"]["tests_declared"])), {LABEL_UNVERIFIED})
            # observed tests always missing
            self.assertEqual(
                set(_labels(report["sections"]["tests_observed"])), {LABEL_MISSING})
            # deterministic
            self.assertEqual(report_to_json(synthesize(bundle)),
                             report_to_json(synthesize(bundle)))


if __name__ == "__main__":
    unittest.main()

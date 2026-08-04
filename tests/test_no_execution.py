"""Tests for LISA-I012: No-Execution Work Products (DEFECT-3 repair).

Run:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_no_execution -v

Fully hermetic: real throwaway git repos and tempdir evidence stores, the
simulated executor only. No network, no OpenClaw, no spend.

Covers the sprint's six scenarios -- no capable employee, policy denial,
capacity refusal, worker success, worker failure, and a mixed graph containing
all three lifecycle states -- plus the review-bundle and synthesis behaviour
each must produce.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.dispatcher import ExecutionResult, WORKER_SIMULATED, mark_executor
from core.synthesizer import (
    REVIEW_EVIDENCE_COMPLETE, REVIEW_EXECUTION_FAILED, REVIEW_NO_EXECUTION,
    render_report, synthesize,
)
from core.work_product import (
    STATUS_COMPLETED, STATUS_FAILED, STATUS_NO_EXECUTION,
    WorkProductValidationError, build_no_execution_work_product,
    build_review_bundle, find_work_products, load_work_product,
    validate_work_product, work_product_recording_executor, write_work_product,
)


def _repo(tmp):
    repo = Path(tmp) / "repo"
    repo.mkdir()
    for args in (["init", "-q", "-b", "main"],
                 ["config", "user.email", "t@lisaos.local"],
                 ["config", "user.name", "LisaOS Test"]):
        subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], capture_output=True)
    return str(repo)


def _assignment(reason="no_capable_employee", detail="no employee provides ['architecture']"):
    """A staffing-failure assignment, shaped exactly as the dispatcher records it."""
    return {
        "work_package_id": "pkg-refused", "employee": None, "available": False,
        "auth_result": reason, "fallback_reason": detail, "mode": "economy",
        "risk": "low", "routed_by": "workforce_resolver",
        "resolved_logical": None, "execution_provenance": None,
    }


class _Pkg:
    def __init__(self, pkg_id="pkg-1"):
        self.id = pkg_id
        self.description = "do a bounded thing"


class _Assignment:
    employee = "implementation-engineer"
    resolved_logical = "claude-sonnet"
    physical_model = "anthropic/claude-sonnet-4-6"
    provider_id = "anthropic"
    resolved_runtime = "claude-cli"


# --------------------------------------------------------------------------- #
# The no-execution evidence model
# --------------------------------------------------------------------------- #

class TestNoExecutionModel(unittest.TestCase):

    def _build(self, tmp, **kw):
        return build_no_execution_work_product(
            package_id="pkg-refused", assignment=_assignment(**kw),
            repo=_repo(tmp), context={"job_id": "job-1", "sprint": "LISA-I012"})

    def test_scenario_no_capable_employee(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._build(tmp)
            validate_work_product(wp, verify_patch=False)
            self.assertEqual(wp["status"], STATUS_NO_EXECUTION)
            self.assertEqual(wp["no_execution"]["reason"], "no_capable_employee")
            self.assertFalse(wp["no_execution"]["execution_started"])

    def test_scenario_policy_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._build(tmp, reason="policy_denied",
                             detail="mode 'economy' forbids employee 'chief-architect'")
            validate_work_product(wp, verify_patch=False)
            self.assertEqual(wp["no_execution"]["reason"], "policy_denied")
            self.assertIn("economy", wp["no_execution"]["detail"])

    def test_scenario_capacity_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._build(tmp, reason="capacity_exhausted",
                             detail="capacity ledger reports provider exhausted")
            validate_work_product(wp, verify_patch=False)
            self.assertEqual(wp["no_execution"]["reason"], "capacity_exhausted")

    def test_nothing_is_fabricated(self):
        """No worker, no patch, no declaration, no change -- all genuinely absent."""
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._build(tmp)
            self.assertIsNone(wp["worker"]["agent_id"])
            self.assertIsNone(wp["worker"]["run_id"])
            self.assertIsNone(wp["worker"]["provenance"])
            self.assertIsNone(wp["declared"])
            self.assertIsNone(wp["observed"]["patch_path"])
            self.assertFalse(wp["observed"]["changed"])
            self.assertEqual(wp["observed"]["attributed_files_changed"], [])

    def test_declaration_is_not_expected_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._build(tmp)
            self.assertFalse(wp["declaration"]["expected"])
            self.assertEqual(wp["declaration"]["errors"], [])
            codes = [d["code"] for d in wp["discrepancies"]]
            self.assertIn("NO_EXECUTION", codes)
            self.assertNotIn("DECLARATION_MISSING", codes)


class TestNoExecutionValidation(unittest.TestCase):
    """V14: a no-execution record cannot also claim engineering happened."""

    def _wp(self, tmp):
        return build_no_execution_work_product(
            package_id="pkg-refused", assignment=_assignment(), repo=_repo(tmp))

    def _reject(self, wp, fragment):
        with self.assertRaises(WorkProductValidationError) as ctx:
            validate_work_product(wp, verify_patch=False)
        self.assertIn(fragment, " | ".join(ctx.exception.errors))

    def test_cannot_claim_repository_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._wp(tmp)
            wp["observed"]["changed"] = True
            wp["observed"]["attributed_files_changed"] = [{"status": "M", "path": "a.py"}]
            self._reject(wp, "V14")

    def test_cannot_carry_a_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._wp(tmp)
            wp["declared"] = {"summary": "I did the work"}
            self._reject(wp, "cannot carry a declaration")

    def test_cannot_carry_execution_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._wp(tmp)
            wp["worker"]["provenance"] = "worker-real"
            self._reject(wp, "execution provenance")

    def test_requires_a_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._wp(tmp)
            wp["no_execution"]["reason"] = ""
            self._reject(wp, "no_execution.reason is required")

    def test_execution_started_must_be_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._wp(tmp)
            wp["no_execution"]["execution_started"] = True
            self._reject(wp, "execution_started must be false")

    def test_refusal_block_invalid_on_executed_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = self._wp(tmp)
            wp["status"] = STATUS_COMPLETED
            wp["worker"]["employee"] = "someone"
            self._reject(wp, "only valid with status 'no_execution'")


# --------------------------------------------------------------------------- #
# Review bundle + synthesis
# --------------------------------------------------------------------------- #

class TestNoExecutionReporting(unittest.TestCase):

    def _bundle(self, tmp):
        store = Path(tmp) / "store"
        wp = build_no_execution_work_product(
            package_id="pkg-refused", assignment=_assignment(), repo=_repo(tmp),
            context={"job_id": "job-1", "sprint": "LISA-I012"})
        write_work_product(wp, store=store)
        return build_review_bundle(wp, store=store), wp

    def test_bundle_is_produced_and_carries_the_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            self.assertEqual(bundle["status"], STATUS_NO_EXECUTION)
            self.assertEqual(bundle["no_execution"]["reason"], "no_capable_employee")

    def test_synthesis_disposition_is_no_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            report = synthesize(bundle)
            self.assertEqual(report["sections"]["review_outcome"]["disposition"],
                             REVIEW_NO_EXECUTION)

    def test_synthesis_states_the_three_required_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            text = render_report(synthesize(bundle)).lower()
            self.assertIn("refused to begin execution", text)
            self.assertIn("no patch", text)
            self.assertIn("no declaration is expected", text)

    def test_synthesis_never_calls_it_missing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            report = synthesize(bundle)
            decls = report["sections"]["worker_declarations"]["statements"]
            self.assertTrue(all(s["label"] != "MISSING" for s in decls), decls)

    def test_no_execution_is_distinct_from_execution_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            self.assertEqual(synthesize(bundle)["sections"]["review_outcome"]["disposition"],
                             REVIEW_NO_EXECUTION)
            failed = dict(bundle)
            failed["status"] = "failed"
            failed["no_execution"] = None
            self.assertEqual(synthesize(failed)["sections"]["review_outcome"]["disposition"],
                             REVIEW_EXECUTION_FAILED)

    def test_synthesis_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            self.assertEqual(render_report(synthesize(bundle)),
                             render_report(synthesize(bundle)))

    def test_rules_published_include_both_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle, _ = self._bundle(tmp)
            rules = synthesize(bundle)["sections"]["review_outcome"]["rules"]
            joined = " ".join(rules)
            self.assertIn("NO_EXECUTION", joined)
            self.assertIn("EXECUTION_FAILED", joined)


# --------------------------------------------------------------------------- #
# Existing lifecycles must be unchanged, and all three must coexist
# --------------------------------------------------------------------------- #

class TestExistingLifecyclesIntact(unittest.TestCase):

    def _run(self, tmp, success=True, pkg="pkg-x"):
        repo, store = _repo(tmp), Path(tmp) / "store"

        def _fn(p, a):
            if success:
                (Path(repo) / "impl.py").write_text("# work\n")
            return ExecutionResult(success=success, actual_runtime="claude-cli",
                                   agent_id="lisa-haiku", run_id="run-1",
                                   error=None if success else "worker failed")
        wrapped = work_product_recording_executor(
            mark_executor(_fn, WORKER_SIMULATED), repo=repo, store=store)
        wrapped(_Pkg(pkg), _Assignment())
        wp = load_work_product(
            find_work_products(package_id=pkg, store=store)[0]["artifact_path"])
        return wp, store

    def test_worker_success_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._run(tmp, success=True)
            validate_work_product(wp, store=store)
            self.assertEqual(wp["status"], STATUS_COMPLETED)
            self.assertTrue(wp["declaration"]["expected"])
            self.assertIsNone(wp.get("no_execution"))

    def test_worker_failure_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._run(tmp, success=False)
            validate_work_product(wp, store=store)
            self.assertEqual(wp["status"], STATUS_FAILED)
            bundle = build_review_bundle(wp, store=store)
            self.assertEqual(synthesize(bundle)["sections"]["review_outcome"]["disposition"],
                             REVIEW_EXECUTION_FAILED)

    def test_mixed_graph_all_three_states_visible(self):
        """A completed, a failed and a refused package all reach synthesis."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, store = _repo(tmp), Path(tmp) / "store"

            def _make(success):
                def _fn(p, a):
                    return ExecutionResult(
                        success=success, actual_runtime="claude-cli",
                        agent_id="lisa-haiku", run_id=f"run-{p.id}",
                        error=None if success else "worker failed")
                return mark_executor(_fn, WORKER_SIMULATED)

            # mix-ok is a fully-evidenced success: a worker ran AND declared.
            decl = store / "declared" / "mix-ok.json"
            decl.parent.mkdir(parents=True, exist_ok=True)
            decl.write_text(json.dumps({"summary": "completed the bounded change"}))
            work_product_recording_executor(
                _make(True), repo=repo, store=store)(_Pkg("mix-ok"), _Assignment())
            work_product_recording_executor(
                _make(False), repo=repo, store=store)(_Pkg("mix-fail"), _Assignment())
            write_work_product(
                build_no_execution_work_product(
                    package_id="mix-refused", assignment=_assignment(), repo=repo),
                store=store)

            expected = {
                "mix-ok": REVIEW_EVIDENCE_COMPLETE,
                "mix-fail": REVIEW_EXECUTION_FAILED,
                "mix-refused": REVIEW_NO_EXECUTION,
            }
            for pkg, want in expected.items():
                found = find_work_products(package_id=pkg, store=store)
                self.assertEqual(len(found), 1, f"{pkg} disappeared from reporting")
                wp = load_work_product(found[0]["artifact_path"])
                validate_work_product(wp, store=store)
                bundle = build_review_bundle(wp, store=store)
                got = synthesize(bundle)["sections"]["review_outcome"]["disposition"]
                self.assertEqual(got, want, f"{pkg}: expected {want}, got {got}")

    def test_every_package_is_discoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, store = _repo(tmp), Path(tmp) / "store"
            write_work_product(
                build_no_execution_work_product(
                    package_id="disc-refused", assignment=_assignment(), repo=repo,
                    context={"job_id": "job-9", "sprint": "LISA-I012"}),
                store=store)
            self.assertEqual(len(find_work_products(job_id="job-9", store=store)), 1)
            self.assertEqual(len(find_work_products(sprint="LISA-I012", store=store)), 1)


if __name__ == "__main__":
    unittest.main()

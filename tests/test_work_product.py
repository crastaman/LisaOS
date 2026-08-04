"""Proof-of-work tests for the LisaOS Work Product evidence layer (Phase 3).

Run:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_work_product -v

Fully hermetic: every test builds a REAL throwaway git repository in a
tempdir (so patch capture is genuinely exercised, not mocked) and writes all
evidence into a tempdir store. No network, no OpenClaw, no spend.

Covers: work product generation, the observed/declared trust boundary,
patch capture + hash integrity, test-evidence validation, review handoff,
invalid artifacts, missing fields, corrupt evidence, and the guarantee that
capture can never alter or break execution.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.dispatcher import (
    ExecutionResult, WORKER_REAL, WORKER_SIMULATED, mark_executor,
)
from core.work_product import (
    DECLARATION_SCHEMA_VERSION, DECLARED_KEYS, DEFAULT_STORE,
    FORBIDDEN_DECLARED_KEYS, SCHEMA_VERSION, STATUS_COMPLETED, STATUS_FAILED,
    augment_brief, declaration_contract_text, validate_declaration,
    WorkProductValidationError, build_review_bundle, build_work_product,
    capture_repo_state, declared_path, find_work_products, load_declared,
    load_work_product, observe_changes, reconcile, validate_test_evidence,
    validate_work_product, work_product_recording_executor, write_work_product,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )


def _make_repo(tmp: str) -> str:
    """A real git repo with one commit."""
    repo = Path(tmp) / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@lisaos.local")
    _git(repo, "config", "user.name", "LisaOS Test")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")
    return str(repo)


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


def _valid_observed(repo="/tmp/repo", **overrides):
    observed = {
        "repo": repo, "branch": "main", "base_commit": "a" * 40,
        "head_commit": "a" * 40, "files_changed": [], "untracked_files": [],
        "changed": False, "patch_covers_untracked": False, "available": True,
        "capture_error": None, "patch_path": None, "patch_sha256": None,
        "patch_bytes": 0,
    }
    observed.update(overrides)
    return observed


def _valid_wp(**overrides):
    wp = build_work_product(
        package_id="pkg-1",
        status=STATUS_COMPLETED,
        worker={"employee": "implementation-engineer", "agent_id": "lisa-claude-sonnet",
                "provenance": WORKER_REAL, "run_id": "run-123"},
        observed=_valid_observed(),
        declared=None,
        discrepancies=[],
        context={"job_id": "job-1", "sprint": "LISA-I005"},
    )
    wp.update(overrides)
    return wp


# --------------------------------------------------------------------------- #
# Observation (the authoritative half)
# --------------------------------------------------------------------------- #

class TestObservation(unittest.TestCase):

    def test_capture_repo_state_reads_branch_and_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            state = capture_repo_state(repo)
            self.assertTrue(state.available)
            self.assertEqual(state.branch, "main")
            self.assertEqual(len(state.commit), 40)
            self.assertIsNone(state.capture_error)

    def test_non_git_directory_fails_soft(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = capture_repo_state(tmp)
            self.assertFalse(state.available)
            self.assertIn("not a git work tree", state.capture_error)

    def test_missing_directory_fails_soft(self):
        state = capture_repo_state("/nonexistent/path/xyz")
        self.assertFalse(state.available)
        self.assertIn("not a directory", state.capture_error)

    def test_observe_uncommitted_edit(self):
        """A worker that edits without committing still produces evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            base = capture_repo_state(repo).commit
            (Path(repo) / "seed.txt").write_text("seed\nmodified by worker\n")
            changes = observe_changes(repo, base)
            self.assertTrue(changes["changed"])
            self.assertEqual([c["path"] for c in changes["files_changed"]], ["seed.txt"])
            self.assertIn("modified by worker", changes["patch_text"])

    def test_observe_committed_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            base = capture_repo_state(repo).commit
            (Path(repo) / "new.py").write_text("print('hi')\n")
            _git(repo, "add", "new.py")
            _git(repo, "commit", "-q", "-m", "add new")
            changes = observe_changes(repo, base)
            self.assertTrue(changes["changed"])
            paths = [c["path"] for c in changes["files_changed"]]
            self.assertIn("new.py", paths)
            self.assertEqual(changes["files_changed"][0]["status"], "A")

    def test_untracked_files_listed_but_not_in_patch(self):
        """Honest limitation: git diff cannot include untracked files."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            base = capture_repo_state(repo).commit
            (Path(repo) / "brand_new.txt").write_text("untracked\n")
            changes = observe_changes(repo, base)
            self.assertEqual(changes["untracked_files"], ["brand_new.txt"])
            self.assertTrue(changes["changed"])
            self.assertNotIn("brand_new", changes["patch_text"])

    def test_no_change_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            base = capture_repo_state(repo).commit
            changes = observe_changes(repo, base)
            self.assertFalse(changes["changed"])
            self.assertEqual(changes["files_changed"], [])
            self.assertEqual(changes["patch_text"], "")

    def test_pre_existing_dirt_is_not_attributed_to_the_worker(self):
        """Regression (found in LISA-I005 review): a repository that was already
        dirty must not have that work credited to the executing worker."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            base = capture_repo_state(repo).commit
            # Dirt that exists BEFORE the worker runs.
            (Path(repo) / "seed.txt").write_text("seed\nsomeone else edited this\n")
            (Path(repo) / "stray.txt").write_text("pre-existing untracked\n")
            before_dirty = {"seed.txt", "stray.txt"}

            changes = observe_changes(repo, base, pre_existing_dirty=before_dirty)

            self.assertEqual(changes["attributed_files_changed"], [])
            self.assertEqual(changes["untracked_files"], [])
            self.assertFalse(
                changes["changed"],
                "pre-existing dirt must not be reported as this worker's change")
            # Nothing is hidden: the raw diff still shows it.
            self.assertEqual([c["path"] for c in changes["files_changed"]], ["seed.txt"])
            self.assertEqual(changes["pre_existing_dirty"], ["seed.txt", "stray.txt"])

    def test_worker_change_still_attributed_alongside_pre_existing_dirt(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            base = capture_repo_state(repo).commit
            (Path(repo) / "seed.txt").write_text("seed\npre-existing\n")
            (Path(repo) / "worker.py").write_text("# written by the worker\n")

            changes = observe_changes(repo, base, pre_existing_dirty={"seed.txt"})

            self.assertTrue(changes["changed"])
            self.assertEqual(changes["untracked_files"], ["worker.py"])
            self.assertEqual(changes["pre_existing_dirty"], ["seed.txt"])

    def test_capture_records_pre_existing_dirt_as_discrepancy(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            (Path(repo) / "seed.txt").write_text("seed\ndirty before dispatch\n")
            store = Path(tmp) / "store"

            def _inner(pkg, assignment):
                return ExecutionResult(success=True, actual_runtime="claude-cli",
                                       agent_id="lisa-haiku", run_id="run-x")
            wrapped = work_product_recording_executor(
                mark_executor(_inner, WORKER_SIMULATED), repo=repo, store=store)
            wrapped(_Pkg("pkg-dirty"), _Assignment())

            wp = load_work_product(
                find_work_products(package_id="pkg-dirty", store=store)[0]["artifact_path"])
            self.assertIsNotNone(validate_work_product(wp, store=store))
            self.assertFalse(wp["observed"]["changed"])
            self.assertEqual(wp["observed"]["attributed_files_changed"], [])
            self.assertIn("seed.txt", wp["observed"]["pre_existing_dirty"])
            self.assertTrue(
                any(d["code"] == "PRE_EXISTING_DIRT" for d in wp["discrepancies"]),
                wp["discrepancies"])

    def test_missing_base_commit_recorded_as_capture_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            changes = observe_changes(repo, None)
            self.assertIn("no base commit", changes["capture_error"])


# --------------------------------------------------------------------------- #
# Declared evidence (the untrusted half)
# --------------------------------------------------------------------------- #

class TestDeclaredEvidence(unittest.TestCase):

    def test_absent_declaration_is_a_recorded_fact_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            declared, problems = load_declared("pkg-1", store=tmp)
            self.assertIsNone(declared)
            self.assertIn("no worker declaration", problems[0])

    def test_valid_declaration_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = declared_path("pkg-1", store=tmp)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"summary": "did the thing", "risks": ["none"]}))
            declared, problems = load_declared("pkg-1", store=tmp)
            self.assertEqual(problems, [])
            self.assertEqual(declared["summary"], "did the thing")

    def test_worker_cannot_smuggle_unpermitted_keys(self):
        """A worker must not be able to inject fields LisaOS observes itself."""
        with tempfile.TemporaryDirectory() as tmp:
            path = declared_path("pkg-1", store=tmp)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"summary": "ok", "status": "completed",
                                        "files_changed": ["lie.py"]}))
            declared, problems = load_declared("pkg-1", store=tmp)
            self.assertIsNone(declared)
            self.assertTrue(any("must not be declared" in p for p in problems), problems)

    def test_corrupt_declaration_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = declared_path("pkg-1", store=tmp)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not json")
            declared, problems = load_declared("pkg-1", store=tmp)
            self.assertIsNone(declared)
            self.assertIn("unreadable", problems[0])

    def test_declaration_path_traversal_is_neutralised(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = declared_path("../../etc/passwd", store=tmp)
            self.assertNotIn("..", str(path.relative_to(Path(tmp))))


# --------------------------------------------------------------------------- #
# Reconciliation -- observation wins, conflict is surfaced
# --------------------------------------------------------------------------- #

class TestReconciliation(unittest.TestCase):

    def test_summary_without_observed_change_is_a_discrepancy(self):
        notes = reconcile(_valid_observed(changed=False), {"summary": "I refactored everything"})
        self.assertTrue(any(n["code"] == "SUMMARY_WITHOUT_CHANGE" for n in notes))

    def test_change_without_declared_tests_is_a_discrepancy(self):
        notes = reconcile(_valid_observed(changed=True), {"summary": "edited"})
        self.assertTrue(any(n["code"] == "CHANGE_WITHOUT_TESTS" for n in notes))

    def test_declared_failing_tests_surfaced(self):
        notes = reconcile(
            _valid_observed(changed=True),
            {"tests": [{"command": "pytest", "result": "fail"}]},
        )
        self.assertTrue(any(n["code"] == "DECLARED_TEST_FAILURES" for n in notes))

    def test_absent_declaration_is_itself_recorded(self):
        notes = reconcile(_valid_observed(), None)
        self.assertEqual([n["code"] for n in notes], ["DECLARATION_MISSING"])


# --------------------------------------------------------------------------- #
# Validation -- fail closed
# --------------------------------------------------------------------------- #

class TestValidation(unittest.TestCase):

    def _reject(self, wp, fragment, **kwargs):
        with self.assertRaises(WorkProductValidationError) as ctx:
            validate_work_product(wp, **kwargs)
        joined = " | ".join(ctx.exception.errors)
        self.assertIn(fragment, joined)
        return ctx.exception.errors

    def test_valid_work_product_accepted(self):
        self.assertIsNotNone(validate_work_product(_valid_wp()))

    def test_not_a_dict_rejected(self):
        with self.assertRaises(WorkProductValidationError):
            validate_work_product(["not", "a", "dict"])

    def test_missing_package_id(self):
        self._reject(_valid_wp(package_id=""), "V2")

    def test_missing_status(self):
        self._reject(_valid_wp(status=None), "V3")

    def test_invalid_status_value(self):
        self._reject(_valid_wp(status="mostly-done"), "V3")

    def test_unknown_schema_version(self):
        self._reject(_valid_wp(schema_version="something-else/9"), "V1")

    def test_unknown_top_level_key(self):
        self._reject(_valid_wp(sneaky="value"), "V10")

    def test_missing_worker_employee(self):
        self._reject(_valid_wp(worker={"agent_id": "x", "provenance": WORKER_REAL}), "V4")

    def test_real_execution_requires_agent_id(self):
        self._reject(
            _valid_wp(worker={"employee": "e", "provenance": WORKER_REAL}), "V4",
        )

    def test_simulated_execution_may_omit_agent_id(self):
        wp = _valid_wp(worker={"employee": "e", "provenance": WORKER_SIMULATED})
        self.assertIsNotNone(validate_work_product(wp))

    def test_observed_must_be_object(self):
        self._reject(_valid_wp(observed="nope"), "V5")

    def test_unavailable_repo_needs_capture_error(self):
        self._reject(
            _valid_wp(observed=_valid_observed(available=False, capture_error=None)), "V5",
        )

    def test_files_changed_must_be_list(self):
        self._reject(_valid_wp(observed=_valid_observed(files_changed="a.py")), "V6")

    def test_changed_true_with_no_files_is_incoherent(self):
        """The 'missing files changed' rejection."""
        self._reject(_valid_wp(observed=_valid_observed(changed=True)), "V6")

    def test_changed_false_with_files_is_incoherent(self):
        self._reject(
            _valid_wp(observed=_valid_observed(
                changed=False, files_changed=[{"status": "M", "path": "a.py"}])),
            "V6",
        )

    def test_files_changed_entry_needs_path(self):
        self._reject(
            _valid_wp(observed=_valid_observed(
                changed=True, files_changed=[{"status": "M"}])),
            "V6",
        )

    def test_changed_files_require_patch_reference(self):
        self._reject(
            _valid_wp(observed=_valid_observed(
                changed=True, files_changed=[{"status": "M", "path": "a.py"}],
                patch_path=None)),
            "V7",
        )

    def test_invalid_patch_reference_rejected(self):
        self._reject(
            _valid_wp(observed=_valid_observed(
                changed=True, files_changed=[{"status": "M", "path": "a.py"}],
                patch_path="/nonexistent/x.patch", patch_sha256="d" * 64,
                patch_bytes=10)),
            "does not resolve",
        )

    def test_patch_hash_mismatch_rejected(self):
        """Corrupt/tampered evidence must not validate."""
        with tempfile.TemporaryDirectory() as tmp:
            patch = Path(tmp) / "x.patch"
            patch.write_text("diff --git a/a.py b/a.py\n")
            self._reject(
                _valid_wp(observed=_valid_observed(
                    changed=True, files_changed=[{"status": "M", "path": "a.py"}],
                    patch_path=str(patch), patch_sha256="0" * 64,
                    patch_bytes=patch.stat().st_size)),
                "sha256 mismatch", store=tmp,
            )

    def test_patch_without_changes_rejected(self):
        self._reject(_valid_wp(observed=_valid_observed(patch_path="/x.patch")), "V7")

    def test_declared_unpermitted_key_rejected(self):
        self._reject(_valid_wp(declared={"summary": "s", "status": "completed"}), "V11")

    def test_declared_risks_must_be_strings(self):
        self._reject(_valid_wp(declared={"summary": "s", "risks": [{"oops": 1}]}), "V11")

    def test_discrepancies_must_be_string_list(self):
        self._reject(_valid_wp(discrepancies=[{"bad": 1}]), "V12")

    def test_all_violations_are_accumulated(self):
        errors = self._reject(
            _valid_wp(package_id="", status="bogus", schema_version="x/1"), "V3",
        )
        self.assertGreaterEqual(len(errors), 3)


class TestTestEvidenceValidation(unittest.TestCase):

    def _entry(self, **overrides):
        entry = {"command": "python3 -m unittest discover tests", "result": "pass",
                 "duration_seconds": 11.7, "passed": 618, "failed": 0,
                 "skipped": 39, "environment": "python3.14 darwin"}
        entry.update(overrides)
        return entry

    def test_valid_entry(self):
        self.assertEqual(validate_test_evidence(self._entry(), 0), [])

    def test_missing_command(self):
        self.assertTrue(validate_test_evidence(self._entry(command=""), 0))

    def test_invalid_result_value(self):
        self.assertTrue(validate_test_evidence(self._entry(result="mostly"), 0))

    def test_negative_duration(self):
        self.assertTrue(validate_test_evidence(self._entry(duration_seconds=-1), 0))

    def test_non_integer_counts(self):
        self.assertTrue(validate_test_evidence(self._entry(passed="lots"), 0))

    def test_missing_environment(self):
        self.assertTrue(validate_test_evidence(self._entry(environment=""), 0))

    def test_pass_contradicting_failures(self):
        errors = validate_test_evidence(self._entry(result="pass", failed=3), 0)
        self.assertTrue(any("contradicts" in e for e in errors))

    def test_malformed_entry_type(self):
        self.assertTrue(validate_test_evidence("not-an-object", 0))

    def test_entries_validated_through_work_product(self):
        wp = _valid_wp(declared={"summary": "s", "tests": [self._entry(result="pass", failed=2)]})
        with self.assertRaises(WorkProductValidationError):
            validate_work_product(wp)


# --------------------------------------------------------------------------- #
# Storage + discovery
# --------------------------------------------------------------------------- #

class TestStorage(unittest.TestCase):

    def test_write_creates_artifact_patch_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = _valid_wp(observed=_valid_observed(
                changed=True, files_changed=[{"status": "M", "path": "a.py"}]))
            paths = write_work_product(wp, patch_text="diff --git a/a.py b/a.py\n+x\n", store=tmp)
            self.assertTrue(Path(paths["artifact_path"]).is_file())
            self.assertTrue(Path(paths["patch_path"]).is_file())
            self.assertTrue((Path(tmp) / "index.jsonl").is_file())

    def test_written_artifact_is_self_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = _valid_wp(observed=_valid_observed(
                changed=True, files_changed=[{"status": "M", "path": "a.py"}]))
            paths = write_work_product(wp, patch_text="diff --git a/a.py\n", store=tmp)
            reloaded = load_work_product(paths["artifact_path"])
            self.assertIsNotNone(validate_work_product(reloaded, store=tmp))
            self.assertEqual(reloaded["observed"]["patch_bytes"],
                             Path(paths["patch_path"]).stat().st_size)

    def test_invalid_product_is_never_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WorkProductValidationError):
                write_work_product(_valid_wp(status="bogus"), store=tmp)
            self.assertEqual(list(Path(tmp).glob("*.json")), [])

    def test_discovery_by_every_axis(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_work_product(_valid_wp(), store=tmp)
            wp2 = _valid_wp(package_id="pkg-2")
            wp2["context"] = {"job_id": "job-2", "sprint": "OTHER"}
            wp2["worker"]["employee"] = "qa-engineer"
            write_work_product(wp2, store=tmp)

            self.assertEqual(len(find_work_products(package_id="pkg-1", store=tmp)), 1)
            self.assertEqual(len(find_work_products(job_id="job-2", store=tmp)), 1)
            self.assertEqual(len(find_work_products(sprint="LISA-I005", store=tmp)), 1)
            self.assertEqual(len(find_work_products(employee="qa-engineer", store=tmp)), 1)
            self.assertEqual(len(find_work_products(store=tmp)), 2)
            self.assertEqual(len(find_work_products(package_id="nope", store=tmp)), 0)

    def test_corrupt_index_line_does_not_hide_other_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_work_product(_valid_wp(), store=tmp)
            with open(Path(tmp) / "index.jsonl", "a") as fh:
                fh.write("{corrupt not json\n")
            write_work_product(_valid_wp(package_id="pkg-3"), store=tmp)
            self.assertEqual(len(find_work_products(store=tmp)), 2)

    def test_find_on_empty_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_work_products(store=tmp), [])


# --------------------------------------------------------------------------- #
# Review handoff -- assembly, not synthesis
# --------------------------------------------------------------------------- #

class TestReviewHandoff(unittest.TestCase):

    def test_bundle_carries_everything_a_reviewer_needs(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = _valid_wp(
                observed=_valid_observed(
                    changed=True, files_changed=[{"status": "M", "path": "a.py"}]),
                declared={"summary": "changed a.py", "risks": ["may break x"],
                          "tests": [{"command": "unittest", "result": "pass",
                                     "duration_seconds": 1.0, "passed": 3,
                                     "failed": 0, "skipped": 0,
                                     "environment": "py3.14"}],
                          "deferred": ["docs"]},
            )
            write_work_product(wp, patch_text="diff --git a/a.py b/a.py\n+x\n", store=tmp)
            bundle = build_review_bundle(wp, store=tmp)

            self.assertEqual(bundle["package_id"], "pkg-1")
            self.assertIn("+x", bundle["change"]["patch_text"])
            self.assertEqual(bundle["declared"]["risks"], ["may break x"])
            self.assertEqual(bundle["declared"]["tests"][0]["result"], "pass")
            self.assertEqual(bundle["declared"]["deferred"], ["docs"])
            self.assertTrue(bundle["declaration_present"])
            self.assertEqual(bundle["change"]["files_changed"][0]["path"], "a.py")
            self.assertEqual(bundle["worker"]["agent_id"], "lisa-claude-sonnet")

    def test_bundle_marks_absent_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = build_review_bundle(_valid_wp(), store=tmp)
            self.assertFalse(bundle["declaration_present"])
            self.assertEqual(bundle["declared"]["tests"], [])

    def test_invalid_product_cannot_reach_review(self):
        with self.assertRaises(WorkProductValidationError):
            build_review_bundle(_valid_wp(status="bogus"))

    def test_large_patch_truncated_and_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp = _valid_wp(observed=_valid_observed(
                changed=True, files_changed=[{"status": "M", "path": "a.py"}]))
            write_work_product(wp, patch_text="x" * 5000, store=tmp)
            bundle = build_review_bundle(wp, store=tmp, max_patch_bytes=100)
            self.assertTrue(bundle["change"]["patch_truncated"])
            self.assertEqual(len(bundle["change"]["patch_text"]), 100)

    def test_bundle_performs_no_interpretation(self):
        """Handoff must assemble evidence, never summarise it."""
        with tempfile.TemporaryDirectory() as tmp:
            wp = _valid_wp(declared={"summary": "verbatim summary text"})
            write_work_product(wp, store=tmp)
            bundle = build_review_bundle(wp, store=tmp)
            self.assertEqual(bundle["declared"]["summary"], "verbatim summary text")


# --------------------------------------------------------------------------- #
# The capture point (executor wrapper)
# --------------------------------------------------------------------------- #

class TestCaptureExecutor(unittest.TestCase):

    def _inner(self, success=True, provenance=WORKER_SIMULATED, edits=None, repo=None):
        def _fn(pkg, assignment):
            if edits:
                for name, content in edits.items():
                    (Path(repo) / name).write_text(content)
            return ExecutionResult(
                success=success, actual_runtime="claude-cli",
                agent_id="lisa-claude-sonnet", run_id="run-abc",
                observed_model="anthropic/claude-sonnet-4-6",
                observed_provider="anthropic",
                error=None if success else "worker failed",
            )
        return mark_executor(_fn, provenance)

    def test_requires_inner_executor(self):
        with self.assertRaises(ValueError):
            work_product_recording_executor(None)

    def test_refuses_undeclared_provenance(self):
        with self.assertRaises(ValueError):
            work_product_recording_executor(lambda p, a: None, repo="/tmp")

    def test_provenance_is_inherited_never_invented(self):
        from core.dispatcher import executor_provenance
        inner = self._inner(provenance=WORKER_SIMULATED)
        wrapped = work_product_recording_executor(inner, repo="/tmp")
        self.assertEqual(executor_provenance(wrapped), WORKER_SIMULATED)

    def test_capture_records_worker_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            store = Path(tmp) / "store"
            inner = self._inner(edits={"seed.txt": "seed\nedited\n"}, repo=repo)
            wrapped = work_product_recording_executor(
                inner, repo=repo, store=store,
                context={"job_id": "job-9", "sprint": "LISA-I005"})

            result = wrapped(_Pkg("pkg-capture"), _Assignment())
            self.assertTrue(result.success)

            found = find_work_products(package_id="pkg-capture", store=store)
            self.assertEqual(len(found), 1)
            wp = load_work_product(found[0]["artifact_path"])
            self.assertIsNotNone(validate_work_product(wp, store=store))
            self.assertEqual(wp["status"], STATUS_COMPLETED)
            self.assertTrue(wp["observed"]["changed"])
            self.assertEqual(
                [c["path"] for c in wp["observed"]["files_changed"]], ["seed.txt"])
            self.assertIn("edited", Path(wp["observed"]["patch_path"]).read_text())
            self.assertEqual(wp["worker"]["agent_id"], "lisa-claude-sonnet")
            self.assertEqual(wp["worker"]["run_id"], "run-abc")
            self.assertEqual(wp["context"]["sprint"], "LISA-I005")

    def test_failed_execution_recorded_as_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            store = Path(tmp) / "store"
            wrapped = work_product_recording_executor(
                self._inner(success=False), repo=repo, store=store)
            wrapped(_Pkg("pkg-fail"), _Assignment())
            wp = load_work_product(
                find_work_products(package_id="pkg-fail", store=store)[0]["artifact_path"])
            self.assertEqual(wp["status"], STATUS_FAILED)
            self.assertEqual(wp["worker"]["execution_error"], "worker failed")

    def test_result_is_returned_unmodified(self):
        """Capture is a passive observer: it can neither pass nor fail a package."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            inner = self._inner()
            wrapped = work_product_recording_executor(
                inner, repo=repo, store=Path(tmp) / "store")
            result = wrapped(_Pkg(), _Assignment())
            self.assertIsInstance(result, ExecutionResult)
            self.assertTrue(result.success)
            self.assertEqual(result.run_id, "run-abc")

    def test_capture_failure_never_breaks_execution(self):
        """An unusable store must not convert a success into a failure."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            blocker = Path(tmp) / "blocked"
            blocker.write_text("I am a file, not a directory")
            wrapped = work_product_recording_executor(
                self._inner(), repo=repo, store=blocker)
            result = wrapped(_Pkg(), _Assignment())
            self.assertTrue(result.success)

    def test_capture_on_non_git_repo_still_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "store"
            wrapped = work_product_recording_executor(
                self._inner(), repo=tmp, store=store)
            wrapped(_Pkg("pkg-nogit"), _Assignment())
            found = find_work_products(package_id="pkg-nogit", store=store)
            self.assertEqual(len(found), 1)
            wp = load_work_product(found[0]["artifact_path"])
            self.assertFalse(wp["observed"]["available"])
            self.assertIsNotNone(wp["capture_error"])

    def test_declared_evidence_is_merged_and_reconciled(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            store = Path(tmp) / "store"
            path = declared_path("pkg-declared", store=store)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "summary": "I changed everything",
                "tests": [{"command": "unittest", "result": "pass",
                           "duration_seconds": 2.0, "passed": 5, "failed": 0,
                           "skipped": 0, "environment": "py3.14"}],
            }))
            wrapped = work_product_recording_executor(
                self._inner(), repo=repo, store=store)
            wrapped(_Pkg("pkg-declared"), _Assignment())

            wp = load_work_product(
                find_work_products(package_id="pkg-declared", store=store)[0]["artifact_path"])
            self.assertEqual(wp["declared"]["summary"], "I changed everything")
            # Observation wins: a summary with no observed change is flagged.
            self.assertTrue(
                any(d["code"] == "SUMMARY_WITHOUT_CHANGE" for d in wp["discrepancies"]),
                wp["discrepancies"],
            )

    def test_composes_with_ledger_recording_executor(self):
        """Must stack with the existing wrapper without laundering provenance."""
        from core.capacity_ledger import CapacityLedger, ledger_recording_executor
        from core.dispatcher import executor_provenance
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            ledger = CapacityLedger.at_path(Path(tmp) / "ledger.json")
            stacked = work_product_recording_executor(
                ledger_recording_executor(ledger, inner=self._inner()),
                repo=repo, store=Path(tmp) / "store")
            self.assertEqual(executor_provenance(stacked), WORKER_SIMULATED)
            self.assertTrue(stacked(_Pkg("pkg-stack"), _Assignment()).success)


# --------------------------------------------------------------------------- #
# Phase 4 (LISA-I006): the worker declaration contract
# --------------------------------------------------------------------------- #

def _valid_declaration(**overrides):
    declaration = {
        "schema_version": DECLARATION_SCHEMA_VERSION,
        "summary": "Implemented the bounded change described in the brief.",
        "tests": [{"command": "python3 -m unittest discover tests",
                   "result": "pass", "duration_seconds": 12.0, "passed": 10,
                   "failed": 0, "skipped": 1, "environment": "python3.14 darwin"}],
        "risks": ["may interact with the cache layer"],
        "warnings": [],
        "deferred": ["docs not updated"],
        "assumptions": ["the fixture data is representative"],
        "notes": "reviewer should check the boundary case",
    }
    declaration.update(overrides)
    return declaration


def _write_declaration(store, package_id, content):
    path = declared_path(package_id, store=store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


class TestDeclarationValidation(unittest.TestCase):

    def test_valid_declaration_accepted(self):
        self.assertEqual(validate_declaration(_valid_declaration()), [])

    def test_minimal_declaration_accepted(self):
        self.assertEqual(validate_declaration({"summary": "did the thing"}), [])

    def test_non_object_rejected(self):
        self.assertTrue(validate_declaration(["not", "an", "object"]))

    def test_missing_required_summary(self):
        errors = validate_declaration({"risks": ["x"]})
        self.assertTrue(any(e.startswith("D3") for e in errors), errors)

    def test_blank_summary_rejected(self):
        errors = validate_declaration({"summary": "   "})
        self.assertTrue(any(e.startswith("D3") for e in errors), errors)

    def test_every_forbidden_field_is_rejected(self):
        """A worker must not be able to assert any LisaOS-observed fact."""
        for key in sorted(FORBIDDEN_DECLARED_KEYS):
            errors = validate_declaration({"summary": "s", key: "anything"})
            self.assertTrue(
                any(e.startswith("D1") and f"'{key}'" in e for e in errors),
                f"forbidden key {key!r} was not rejected: {errors}")

    def test_forbidden_field_names_the_reason(self):
        errors = validate_declaration({"summary": "s", "files_changed": ["a.py"]})
        self.assertTrue(any("observed by LisaOS" in e for e in errors), errors)

    def test_unknown_key_rejected(self):
        errors = validate_declaration({"summary": "s", "vibes": "good"})
        self.assertTrue(any(e.startswith("D2") for e in errors), errors)

    def test_wrong_schema_version_rejected(self):
        errors = validate_declaration(_valid_declaration(schema_version="other/9"))
        self.assertTrue(any(e.startswith("D4") for e in errors), errors)

    def test_malformed_test_evidence_rejected(self):
        errors = validate_declaration(_valid_declaration(
            tests=[{"command": "x", "result": "maybe"}]))
        self.assertTrue(errors)

    def test_tests_must_be_a_list(self):
        errors = validate_declaration(_valid_declaration(tests="all of them"))
        self.assertTrue(any(e.startswith("D5") for e in errors), errors)

    def test_string_lists_enforced(self):
        for key in ("risks", "warnings", "deferred", "assumptions"):
            errors = validate_declaration(_valid_declaration(**{key: [{"o": 1}]}))
            self.assertTrue(any(e.startswith("D6") for e in errors), (key, errors))

    def test_notes_must_be_string(self):
        errors = validate_declaration(_valid_declaration(notes=["a", "b"]))
        self.assertTrue(any(e.startswith("D6") for e in errors), errors)

    def test_all_violations_accumulated(self):
        errors = validate_declaration({"patch": "x", "vibes": "y"})
        self.assertGreaterEqual(len(errors), 3)  # D1 + D2 + D3

    def test_invalid_declaration_is_never_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_declaration(tmp, "pkg-1", {"summary": "s", "patch": "sneaky"})
            declared, problems = load_declared("pkg-1", store=tmp)
            self.assertIsNone(declared, "invalid declaration must not be accepted")
            self.assertTrue(problems)


class TestDeclarationContractText(unittest.TestCase):

    def test_contract_names_the_exact_write_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = declaration_contract_text("pkg-7", store=tmp)
            self.assertIn(str(declared_path("pkg-7", store=tmp)), text)

    def test_contract_lists_permitted_and_required_fields(self):
        text = declaration_contract_text("pkg-1", store="/tmp/s")
        for key in DECLARED_KEYS - {"schema_version"}:
            self.assertIn(key, text)
        self.assertIn("REQUIRED", text)
        self.assertIn(DECLARATION_SCHEMA_VERSION, text)

    def test_contract_forbids_observed_fields(self):
        text = declaration_contract_text("pkg-1", store="/tmp/s")
        self.assertIn("MUST NOT appear", text)
        self.assertIn("files changed", text)

    def test_augment_brief_appends_contract_without_mutating_original(self):
        pkg = _Pkg("pkg-aug")
        original = pkg.description
        augmented = augment_brief(pkg, store="/tmp/s")
        self.assertIn("LISAOS WORKER DECLARATION CONTRACT", augmented.description)
        self.assertIn(original, augmented.description)
        self.assertEqual(pkg.description, original, "original must not be mutated")
        self.assertIsNot(augmented, pkg)

    def test_augment_brief_is_idempotent(self):
        pkg = _Pkg("pkg-idem")
        once = augment_brief(pkg, store="/tmp/s")
        twice = augment_brief(once, store="/tmp/s")
        self.assertEqual(once.description.count("END CONTRACT"), 1)
        self.assertEqual(twice.description.count("END CONTRACT"), 1)

    def test_augment_brief_works_on_real_work_package(self):
        from core.workforce_resolver import WorkPackage
        pkg = WorkPackage(id="pkg-real", description="do the thing",
                          required_capabilities=["documentation"])
        augmented = augment_brief(pkg, store="/tmp/s")
        self.assertIn("END CONTRACT", augmented.description)
        self.assertEqual(pkg.description, "do the thing")
        self.assertEqual(augmented.id, "pkg-real")
        self.assertEqual(augmented.required_capabilities, ["documentation"])

    def test_augment_brief_tolerates_unusable_package(self):
        class Weird:
            id = "x"
            description = None
        weird = Weird()
        self.assertIs(augment_brief(weird, store="/tmp/s"), weird)


class TestDeclarationReconciliation(unittest.TestCase):

    def test_invalid_declaration_is_a_conflict_discrepancy(self):
        notes = reconcile(_valid_observed(), None,
                          declaration_errors=["D1: 'patch' is observed by LisaOS"])
        self.assertEqual(notes[0]["code"], "DECLARATION_INVALID")
        self.assertEqual(notes[0]["severity"], "conflict")
        self.assertTrue(notes[0]["errors"])

    def test_missing_declaration_is_a_warning_not_a_conflict(self):
        notes = reconcile(_valid_observed(), None,
                          declaration_errors=["no worker declaration was written"])
        self.assertEqual(notes[0]["code"], "DECLARATION_MISSING")
        self.assertEqual(notes[0]["severity"], "warning")

    def test_deferred_work_recorded_as_info(self):
        notes = reconcile(_valid_observed(changed=False),
                          {"summary": "", "deferred": ["docs", "tests"]})
        deferred = [n for n in notes if n["code"] == "WORK_DEFERRED"]
        self.assertEqual(deferred[0]["severity"], "info")
        self.assertEqual(deferred[0]["deferred"], ["docs", "tests"])

    def test_discrepancies_are_deterministic(self):
        observed = _valid_observed(changed=True,
                                   files_changed=[{"status": "M", "path": "a.py"}],
                                   attributed_files_changed=[{"status": "M", "path": "a.py"}])
        declared = {"summary": "edited a.py"}
        self.assertEqual(reconcile(observed, declared), reconcile(observed, declared))


class TestDeclarationEndToEnd(unittest.TestCase):

    def _inner(self, success=True):
        def _fn(pkg, assignment):
            return ExecutionResult(success=success, actual_runtime="claude-cli",
                                   agent_id="lisa-claude-sonnet", run_id="run-decl")
        return mark_executor(_fn, WORKER_SIMULATED)

    def _capture(self, tmp, package_id, declaration=None, declare=True):
        repo = _make_repo(tmp)
        store = Path(tmp) / "store"
        if declaration is not None:
            _write_declaration(store, package_id, declaration)
        wrapped = work_product_recording_executor(
            self._inner(), repo=repo, store=store, declare=declare)
        wrapped(_Pkg(package_id), _Assignment())
        found = find_work_products(package_id=package_id, store=store)
        self.assertEqual(len(found), 1)
        return load_work_product(found[0]["artifact_path"]), store

    def test_valid_declaration_is_preserved_and_marked_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._capture(tmp, "pkg-ok", _valid_declaration())
            self.assertIsNotNone(validate_work_product(wp, store=store))
            self.assertTrue(wp["declaration"]["present"])
            self.assertTrue(wp["declaration"]["valid"])
            self.assertEqual(wp["declaration"]["errors"], [])
            self.assertEqual(wp["declared"]["risks"], ["may interact with the cache layer"])
            self.assertEqual(wp["declared"]["deferred"], ["docs not updated"])

    def test_forbidden_declaration_rejected_but_recorded(self):
        """The rejection itself is evidence a reviewer must see."""
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._capture(
                tmp, "pkg-forbidden",
                _valid_declaration(files_changed=["totally_real.py"]))
            self.assertIsNotNone(validate_work_product(wp, store=store))
            self.assertTrue(wp["declaration"]["present"])
            self.assertFalse(wp["declaration"]["valid"])
            self.assertTrue(wp["declaration"]["errors"])
            self.assertIsNone(wp["declared"], "rejected content must not be stored")
            codes = [d["code"] for d in wp["discrepancies"]]
            self.assertIn("DECLARATION_INVALID", codes)

    def test_worker_cannot_overwrite_observed_status(self):
        """Observation stays authoritative even when the worker contradicts it."""
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._capture(
                tmp, "pkg-liar", _valid_declaration(status="failed", changed=True))
            self.assertEqual(wp["status"], STATUS_COMPLETED)  # observed wins
            self.assertFalse(wp["declaration"]["valid"])
            self.assertFalse(wp["observed"]["changed"])

    def test_missing_declaration_recorded_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._capture(tmp, "pkg-none", None)
            self.assertIsNotNone(validate_work_product(wp, store=store))
            self.assertFalse(wp["declaration"]["present"])
            self.assertFalse(wp["declaration"]["valid"])
            self.assertIn("DECLARATION_MISSING",
                          [d["code"] for d in wp["discrepancies"]])

    def test_corrupt_declaration_recorded_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            wp, store = self._capture(tmp, "pkg-corrupt", "{not json at all")
            self.assertIsNotNone(validate_work_product(wp, store=store))
            self.assertTrue(wp["declaration"]["present"])
            self.assertFalse(wp["declaration"]["valid"])
            self.assertTrue(any("unreadable" in e for e in wp["declaration"]["errors"]))

    def test_contract_is_delivered_to_the_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            seen = {}

            def _fn(pkg, assignment):
                seen["description"] = pkg.description
                return ExecutionResult(success=True, agent_id="lisa-x", run_id="r")
            wrapped = work_product_recording_executor(
                mark_executor(_fn, WORKER_SIMULATED), repo=repo,
                store=Path(tmp) / "store")
            original = _Pkg("pkg-contract")
            wrapped(original, _Assignment())

            self.assertIn("LISAOS WORKER DECLARATION CONTRACT", seen["description"])
            self.assertIn("do a bounded thing", seen["description"])
            self.assertEqual(original.description, "do a bounded thing")

    def test_contract_injection_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            seen = {}

            def _fn(pkg, assignment):
                seen["description"] = pkg.description
                return ExecutionResult(success=True, agent_id="lisa-x", run_id="r")
            wrapped = work_product_recording_executor(
                mark_executor(_fn, WORKER_SIMULATED), repo=repo,
                store=Path(tmp) / "store", declare=False)
            wrapped(_Pkg("pkg-nodecl"), _Assignment())
            self.assertNotIn("DECLARATION CONTRACT", seen["description"])


class TestReviewBundlePhase4(unittest.TestCase):

    def test_bundle_carries_declaration_validation_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            store = Path(tmp) / "store"
            _write_declaration(store, "pkg-bundle",
                               _valid_declaration(patch="forbidden"))

            def _fn(pkg, assignment):
                return ExecutionResult(success=True, agent_id="lisa-x", run_id="r")
            wrapped = work_product_recording_executor(
                mark_executor(_fn, WORKER_SIMULATED), repo=repo, store=store)
            wrapped(_Pkg("pkg-bundle"), _Assignment())

            wp = load_work_product(
                find_work_products(package_id="pkg-bundle", store=store)[0]["artifact_path"])
            bundle = build_review_bundle(wp, store=store)

            self.assertTrue(bundle["declaration"]["present"])
            self.assertFalse(bundle["declaration"]["valid"])
            self.assertTrue(bundle["declaration"]["errors"])
            self.assertTrue(
                any(d["code"] == "DECLARATION_INVALID" for d in bundle["discrepancies"]))
            # Observed evidence is still fully present alongside the rejection.
            self.assertIn("repo", bundle["change"])
            self.assertIn("base_commit", bundle["change"])

    def test_bundle_never_drops_declared_fields(self):
        """Regression (found in LISA-I007 review): the bundle cherry-picked a
        fixed key list and silently dropped `assumptions` and `notes`, losing
        evidence a worker had legitimately declared."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            store = Path(tmp) / "store"
            _write_declaration(store, "pkg-keys", _valid_declaration())

            def _fn(pkg, assignment):
                return ExecutionResult(success=True, agent_id="lisa-x", run_id="r")
            wrapped = work_product_recording_executor(
                mark_executor(_fn, WORKER_SIMULATED), repo=repo, store=store)
            wrapped(_Pkg("pkg-keys"), _Assignment())

            wp = load_work_product(
                find_work_products(package_id="pkg-keys", store=store)[0]["artifact_path"])
            bundle = build_review_bundle(wp, store=store)

            for key in DECLARED_KEYS - {"schema_version"}:
                self.assertIn(key, bundle["declared"],
                              f"declared field {key!r} was dropped by the bundle")
            self.assertEqual(bundle["declared"]["assumptions"],
                             ["the fixture data is representative"])
            self.assertEqual(bundle["declared"]["notes"],
                             "reviewer should check the boundary case")

    def test_bundle_gives_reviewer_both_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            store = Path(tmp) / "store"
            _write_declaration(store, "pkg-both", _valid_declaration())

            def _fn(pkg, assignment):
                (Path(repo) / "impl.py").write_text("# worker wrote this\n")
                return ExecutionResult(success=True, agent_id="lisa-x", run_id="r")
            wrapped = work_product_recording_executor(
                mark_executor(_fn, WORKER_SIMULATED), repo=repo, store=store)
            wrapped(_Pkg("pkg-both"), _Assignment())

            wp = load_work_product(
                find_work_products(package_id="pkg-both", store=store)[0]["artifact_path"])
            bundle = build_review_bundle(wp, store=store)

            # Observed (authoritative)
            self.assertIn("impl.py", bundle["change"]["untracked_files"])
            # Declared (worker-supplied), preserved verbatim
            self.assertEqual(bundle["declared"]["deferred"], ["docs not updated"])
            self.assertEqual(bundle["declared"]["tests"][0]["result"], "pass")
            self.assertTrue(bundle["declaration"]["valid"])


if __name__ == "__main__":
    unittest.main()

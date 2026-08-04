"""Integration tests for bin/lisa — runs the real script via subprocess.

All tests are hermetic:
  - --intake-path redirected to a tempdir file.
  - LISA_DISPATCH_CMD redirected to a tiny stub script in the tempdir
    (requires LISA_TEST_MODE=1 to take effect).
  - No network, no real dispatch, no spend.
"""

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

LISA_BIN = str(Path(__file__).resolve().parent.parent / "bin" / "lisa")
LISA_HOME = str(Path(__file__).resolve().parent.parent)


def _run(args, *, env=None, **kwargs):
    base_env = {**os.environ, "PYTHONPATH": LISA_HOME}
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, LISA_BIN] + args,
        capture_output=True,
        text=True,
        env=base_env,
        **kwargs,
    )


def _run_with_stub(args, stub_path, *, extra_env=None, **kwargs):
    """Run bin/lisa with a test stub, activating both LISA_TEST_MODE and LISA_DISPATCH_CMD."""
    env = {"LISA_TEST_MODE": "1", "LISA_DISPATCH_CMD": stub_path}
    if extra_env:
        env.update(extra_env)
    return _run(args, env=env, **kwargs)


def _read_intake(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _make_stub(tmpdir: str, exit_code: int = 0) -> str:
    """Write a stub lisa-dispatch that records its argv and exits."""
    stub = Path(tmpdir) / "stub-dispatch"
    argv_file = Path(tmpdir) / "stub-argv.json"
    stub.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" > {argv_file}\n"
        f"exit {exit_code}\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(stub)


def _make_valid_goal(tmpdir: str) -> str:
    goal = [
        {
            "id": "pkg-a",
            "description": "Read the codebase",
            "required_capabilities": ["repository_read"],
            "risk": "low",
            "mode": "balanced",
            "depends_on": [],
        },
        {
            "id": "pkg-b",
            "description": "Write the report",
            "required_capabilities": ["documentation"],
            "risk": "low",
            "mode": "balanced",
            "depends_on": ["pkg-a"],
        },
    ]
    p = Path(tmpdir) / "goal.json"
    p.write_text(json.dumps(goal))
    return str(p)


def _make_cyclic_goal(tmpdir: str) -> str:
    goal = [
        {"id": "a", "description": "A", "required_capabilities": ["repository_read"],
         "risk": "low", "mode": "balanced", "depends_on": ["b"]},
        {"id": "b", "description": "B", "required_capabilities": ["repository_read"],
         "risk": "low", "mode": "balanced", "depends_on": ["a"]},
    ]
    p = Path(tmpdir) / "bad-goal.json"
    p.write_text(json.dumps(goal))
    return str(p)


class TestGoverned_NoGoal(unittest.TestCase):
    def test_exit_4_planning_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            r = _run_with_stub(
                ["S046 review the codebase", "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 4, msg=r.stdout + r.stderr)
            out = r.stdout
            self.assertIn("PLANNING_REQUIRED", out)
            records = _read_intake(str(intake))
            self.assertTrue(records)
            self.assertEqual(records[-1]["status"], "PLANNING_REQUIRED")
            # stub must NOT have been invoked
            self.assertFalse((Path(tmp) / "stub-argv.json").exists())

    def test_json_flag_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            r = _run_with_stub(
                ["implement something", "--json", "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 4)
            data = json.loads(r.stdout)
            self.assertIn("status", data)
            self.assertEqual(data["status"], "PLANNING_REQUIRED")


class TestGoverned_WithValidGoal(unittest.TestCase):
    def test_stub_invoked_dispatched_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp, exit_code=0)
            goal = _make_valid_goal(tmp)
            r = _run_with_stub(
                ["S046 audit the module", "--goal", goal,
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            # stub argv file should exist
            argv_file = Path(tmp) / "stub-argv.json"
            self.assertTrue(argv_file.exists(), "Stub was not invoked")
            argv_str = argv_file.read_text().strip()
            self.assertIn("run", argv_str)
            self.assertIn(goal, argv_str)
            # intake records: DISPATCHED + DISPATCH_COMPLETED
            records = _read_intake(str(intake))
            statuses = [rec["status"] for rec in records]
            self.assertIn("DISPATCHED", statuses)
            self.assertIn("DISPATCH_COMPLETED", statuses)
            # same request_id
            dispatched = next(r for r in records if r["status"] == "DISPATCHED")
            completed = next(r for r in records if r["status"] == "DISPATCH_COMPLETED")
            self.assertEqual(dispatched["request_id"], completed["request_id"])
            self.assertEqual(completed["dispatch_exit_code"], 0)


class TestGoverned_InvalidGoal(unittest.TestCase):
    def test_cyclic_dep_exit_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            goal = _make_cyclic_goal(tmp)
            r = _run_with_stub(
                ["S046 audit the module", "--goal", goal,
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 6, msg=r.stdout + r.stderr)
            out = r.stdout
            self.assertTrue(
                "cycle" in out.lower() or "error" in out.lower() or "Dependency" in out,
                msg=f"Expected cycle/error in output: {out}",
            )
            records = _read_intake(str(intake))
            self.assertTrue(records)
            self.assertEqual(records[-1]["status"], "VALIDATION_FAILED")
            self.assertIsNotNone(records[-1]["validation_errors"])
            # stub must NOT have been invoked
            self.assertFalse((Path(tmp) / "stub-argv.json").exists())

    def test_bad_risk_exit_6(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            goal_data = [
                {"id": "x", "description": "x", "required_capabilities": [],
                 "risk": "INVALID_RISK", "mode": "balanced", "depends_on": []},
            ]
            goal = Path(tmp) / "bad-risk.json"
            goal.write_text(json.dumps(goal_data))
            r = _run_with_stub(
                ["S046 do something", "--goal", str(goal),
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 6, msg=r.stdout + r.stderr)
            records = _read_intake(str(intake))
            self.assertEqual(records[-1]["status"], "VALIDATION_FAILED")

    def test_json_flag_on_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            goal = _make_cyclic_goal(tmp)
            r = _run_with_stub(
                ["S046 audit", "--goal", goal, "--json",
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 6)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "VALIDATION_FAILED")
            self.assertIsInstance(data["validation_errors"], list)


class TestDirect(unittest.TestCase):
    def test_explain_mission_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            r = _run_with_stub(
                ["Explain what the Lisa dispatcher does.",
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            out = r.stdout
            self.assertIn("Phase 1 scope", out)
            records = _read_intake(str(intake))
            self.assertTrue(records)
            self.assertEqual(records[-1]["status"], "DIRECT_INFO")
            # stub must NOT have been invoked
            self.assertFalse((Path(tmp) / "stub-argv.json").exists())

    def test_json_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            r = _run_with_stub(
                ["Explain what the Lisa dispatcher does.", "--json",
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 0)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "DIRECT_INFO")


class TestBlocked(unittest.TestCase):
    def test_empty_mission_exit_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            r = _run_with_stub(
                ["", "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 5, msg=r.stdout + r.stderr)
            records = _read_intake(str(intake))
            self.assertTrue(records)
            self.assertEqual(records[-1]["status"], "BLOCKED")

    def test_json_parseable_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            r = _run_with_stub(
                ["", "--json", "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 5)
            data = json.loads(r.stdout)
            self.assertEqual(data["status"], "BLOCKED")


class TestDispatchCmdGuard(unittest.TestCase):
    """LISA_DISPATCH_CMD without LISA_TEST_MODE=1 must be ignored (warning emitted)."""

    def test_dispatch_cmd_without_test_mode_ignored(self):
        """Stub is NOT called; warning appears on stderr; --simulate keeps it hermetic."""
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp, exit_code=0)
            goal = _make_valid_goal(tmp)
            # Deliberately NOT setting LISA_TEST_MODE=1
            r = _run(
                ["S046 audit the module", "--goal", goal,
                 "--intake-path", str(intake), "--simulate"],
                env={"LISA_DISPATCH_CMD": stub},
                # --simulate prevents real spend even if production dispatch runs
            )
            # Warning must appear on stderr
            self.assertIn("LISA_DISPATCH_CMD", r.stderr,
                          msg=f"Expected warning in stderr; got: {r.stderr!r}")
            self.assertIn("LISA_TEST_MODE", r.stderr,
                          msg=f"Expected LISA_TEST_MODE mention in warning; got: {r.stderr!r}")
            # Stub must NOT have been invoked (no stub-argv.json written)
            self.assertFalse((Path(tmp) / "stub-argv.json").exists(),
                             "Stub was invoked despite missing LISA_TEST_MODE=1")


class TestDispatchCompletedTimestamp(unittest.TestCase):
    """DISPATCH_COMPLETED must carry a timestamp >= the DISPATCHED timestamp."""

    def test_completed_timestamp_gte_dispatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp, exit_code=0)
            goal = _make_valid_goal(tmp)
            r = _run_with_stub(
                ["S046 implement the module", "--goal", goal,
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            records = _read_intake(str(intake))
            dispatched = next(rec for rec in records if rec["status"] == "DISPATCHED")
            completed = next(rec for rec in records if rec["status"] == "DISPATCH_COMPLETED")
            # Same request_id
            self.assertEqual(dispatched["request_id"], completed["request_id"],
                             "request_id must be identical across DISPATCHED and DISPATCH_COMPLETED")
            # Completed timestamp must be >= dispatched timestamp
            ts_dispatched = datetime.fromisoformat(dispatched["timestamp"])
            ts_completed = datetime.fromisoformat(completed["timestamp"])
            self.assertGreaterEqual(
                ts_completed, ts_dispatched,
                msg=(f"DISPATCH_COMPLETED timestamp ({ts_completed}) must be >= "
                     f"DISPATCHED timestamp ({ts_dispatched})"),
            )


class TestInvokedAs(unittest.TestCase):
    """_invoked_as() returns a path (not bare 'lisa') when lisa is not on PATH."""

    def test_invoked_as_returns_path_when_not_on_path(self):
        """When called via explicit path and 'lisa' is not on PATH, _invoked_as() != 'lisa'."""
        # Run bin/lisa with a GOVERNED mission (no --goal) and inspect next_command.
        # We strip PATH so that 'lisa' is definitely not resolvable.
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp)
            # Use a minimal PATH that excludes any lisa symlink.
            restricted_path = "/usr/bin:/bin"
            r = _run_with_stub(
                ["S046 review the codebase", "--intake-path", str(intake), "--json"],
                stub,
                extra_env={"PATH": restricted_path},
            )
            self.assertEqual(r.returncode, 4, msg=r.stdout + r.stderr)
            data = json.loads(r.stdout)
            next_cmd = data.get("next_command", "")
            # next_command should NOT start with bare 'lisa "' (that would be wrong)
            # It should contain some path component (relative or absolute).
            self.assertNotEqual(next_cmd, "", "next_command must not be empty")
            # The invoked path is the full abs path to bin/lisa; it should appear in next_cmd.
            invoked_name = next_cmd.split(" ")[0]
            self.assertNotEqual(invoked_name, "lisa",
                                msg=f"Expected path-based name, got bare 'lisa': {next_cmd!r}")


class TestExampleGoalValidation(unittest.TestCase):
    """goal-phase1-validation.json must pass _validate_goal() cleanly."""

    GOAL_FILE = str(
        Path(__file__).resolve().parent.parent / "jobs" / "examples" / "goal-phase1-validation.json"
    )

    def test_example_goal_file_is_graph_valid(self):
        """Load bin/lisa via importlib and call _validate_goal() directly."""
        import importlib.machinery
        lisa_path = str(Path(__file__).resolve().parent.parent / "bin" / "lisa")
        loader = importlib.machinery.SourceFileLoader("lisa_entrypoint", lisa_path)
        spec = importlib.util.spec_from_loader("lisa_entrypoint", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        packages, errors = module._validate_goal(self.GOAL_FILE)
        self.assertEqual(errors, [],
                         msg=f"goal-phase1-validation.json failed validation: {errors}")
        self.assertEqual(len(packages), 1,
                         msg=f"Expected 1 package, got {len(packages)}")
        self.assertEqual(packages[0].id, "p1-validate-inspect")

    def test_example_goal_via_subprocess_validates(self):
        """Run bin/lisa with the example goal file through the test stub — exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            stub = _make_stub(tmp, exit_code=0)
            r = _run_with_stub(
                ["S046 sprint validation",
                 "--goal", self.GOAL_FILE,
                 "--intake-path", str(intake)],
                stub,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            records = _read_intake(str(intake))
            statuses = [rec["status"] for rec in records]
            self.assertIn("DISPATCHED", statuses)
            self.assertIn("DISPATCH_COMPLETED", statuses)


class TestNoOpenclaw(unittest.TestCase):
    """bin/lisa must not directly import from core.openclaw_bridge.

    Phase 2 update: bin/lisa now imports build_openclaw_proposer (and related
    names) from core.planner, which internally uses the openclaw bridge.  The
    constraint is that bin/lisa must not bypass the planner/bridge abstraction
    by importing core.openclaw_bridge directly.
    """

    def test_no_direct_openclaw_bridge_import(self):
        src = Path(LISA_BIN).read_text()
        import re as _re
        stripped = _re.sub(r'""".*?"""', '""', src, flags=_re.DOTALL)
        stripped = _re.sub(r"'''.*?'''", "''", stripped, flags=_re.DOTALL)
        code_parts = []
        for line in stripped.splitlines():
            if line.strip().startswith("#"):
                continue
            code_parts.append(line.split("#")[0])
        code_text = "\n".join(code_parts)
        self.assertNotIn(
            "core.openclaw_bridge",
            code_text,
            "bin/lisa must not directly import from core.openclaw_bridge; "
            "route through core.planner instead",
        )
        self.assertNotIn(
            "openclaw_bridge",
            code_text,
            "bin/lisa must not directly reference openclaw_bridge; "
            "route through core.planner instead",
        )


# ── Phase 2: --plan route helpers ─────────────────────────────────────────────

def _make_proposer_stub(tmpdir: str, plan_json: str, exit_code: int = 0) -> str:
    """Write a proposer stub that echoes `plan_json` to stdout and exits."""
    stub = Path(tmpdir) / "stub-proposer"
    # Use single quotes for the JSON to avoid shell-quoting issues with double quotes.
    # Write a Python script instead to handle arbitrary JSON safely.
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({plan_json!r})\n"
        f"sys.exit({exit_code})\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(stub)


def _valid_canned_plan() -> str:
    """Return a valid single-package plan JSON string for stub proposers."""
    return json.dumps([
        {
            "id": "stub-task-one",
            "description": "Read the repository structure and identify the key source files to analyze.",
            "required_capabilities": ["code-implementation"],
            "risk": "low",
            "mode": "balanced",
            "depends_on": [],
        }
    ])


def _invalid_canned_plan() -> str:
    """Return an invalid plan JSON string (hallucinated cap + bad id)."""
    return json.dumps([
        {
            "id": "BAD ID!",
            "description": "x",
            "required_capabilities": ["wizardry"],
            "risk": "normal",
            "mode": "balanced",
            "depends_on": [],
        }
    ])


def _run_plan(args, proposer_stub_path, dispatch_stub_path=None, *,
              extra_env=None, **kwargs):
    """Run bin/lisa with both LISA_TEST_MODE=1 and the given proposer stub."""
    env = {
        "LISA_TEST_MODE": "1",
        "LISA_PROPOSER_CMD": proposer_stub_path,
    }
    if dispatch_stub_path:
        env["LISA_DISPATCH_CMD"] = dispatch_stub_path
    if extra_env:
        env.update(extra_env)
    return _run(args, env=env, **kwargs)


# ── Phase 2 tests ─────────────────────────────────────────────────────────────

class TestPlanRoute_Success(unittest.TestCase):
    """--plan on a governed mission → exit 0, artifact + sidecar, PLAN_READY."""

    def test_plan_only_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            r = _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)

    def test_plan_artifact_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertTrue(plan_out.exists(), "plan artifact not created")
            # Artifact must be a bare JSON array
            data = json.loads(plan_out.read_text())
            self.assertIsInstance(data, list)

    def test_plan_sidecar_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            sidecar = plan_out.parent / (plan_out.stem + ".meta.json")
            self.assertTrue(sidecar.exists(), "sidecar meta file not created")
            meta = json.loads(sidecar.read_text())
            self.assertIn("request_id", meta)
            self.assertIn("mission", meta)
            self.assertIn("package_ids", meta)

    def test_plan_ready_intake_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            records = _read_intake(str(intake))
            statuses = [r["status"] for r in records]
            self.assertIn("PLAN_READY", statuses)

    def test_no_dispatch_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            dispatch_stub = _make_stub(tmp)
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
                dispatch_stub_path=dispatch_stub,
            )
            # Dispatch stub must NOT have been invoked
            self.assertFalse(
                (Path(tmp) / "stub-argv.json").exists(),
                "dispatch stub was invoked without --dispatch flag",
            )


class TestPlanRoute_Rejection(unittest.TestCase):
    """--plan with an invalid plan → exit 7, PLAN_REJECTED, no artifact."""

    def test_exit_7_on_invalid_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _invalid_canned_plan())
            r = _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertEqual(r.returncode, 7, msg=r.stdout + r.stderr)

    def test_plan_rejected_intake_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _invalid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            records = _read_intake(str(intake))
            statuses = [r["status"] for r in records]
            self.assertIn("PLAN_REJECTED", statuses)

    def test_no_artifact_on_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _invalid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertFalse(
                plan_out.exists(),
                "artifact must NOT be created when the plan is rejected",
            )


class TestPlanRoute_ProposerFailed(unittest.TestCase):
    """--plan with a failing stub → exit 8, PLAN_PROPOSER_FAILED."""

    def test_exit_8_on_proposer_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, "", exit_code=1)
            r = _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertEqual(r.returncode, 8, msg=r.stdout + r.stderr)

    def test_plan_proposer_failed_intake_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, "", exit_code=1)
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            records = _read_intake(str(intake))
            statuses = [r["status"] for r in records]
            self.assertIn("PLAN_PROPOSER_FAILED", statuses)

    def test_no_artifact_on_proposer_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, "", exit_code=1)
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertFalse(
                plan_out.exists(),
                "artifact must NOT be created when the proposer fails",
            )


class TestPlanDispatch(unittest.TestCase):
    """--plan --dispatch → artifact created AND dispatch stub invoked."""

    def test_plan_and_dispatch_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            dispatch_stub = _make_stub(tmp, exit_code=0)
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            r = _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan", "--dispatch",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
                dispatch_stub_path=dispatch_stub,
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            # Artifact must exist
            self.assertTrue(plan_out.exists(), "plan artifact not created")
            # Dispatch stub must have been invoked with `run <plan_out>`
            argv_file = Path(tmp) / "stub-argv.json"
            self.assertTrue(argv_file.exists(), "dispatch stub was not invoked")
            argv_str = argv_file.read_text().strip()
            self.assertIn("run", argv_str)
            self.assertIn(str(plan_out), argv_str)

    def test_plan_dispatch_intake_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            dispatch_stub = _make_stub(tmp, exit_code=0)
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan", "--dispatch",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                proposer,
                dispatch_stub_path=dispatch_stub,
            )
            records = _read_intake(str(intake))
            statuses = [r["status"] for r in records]
            self.assertIn("PLAN_READY", statuses)
            self.assertIn("DISPATCHED", statuses)
            self.assertIn("DISPATCH_COMPLETED", statuses)


class TestPlanGoalMutualExclusion(unittest.TestCase):
    """--plan and --goal together → exit 2."""

    def test_exit_2_on_conflicting_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            goal = _make_valid_goal(tmp)
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            r = _run_plan(
                [
                    "S046 implement the payment module",
                    "--plan", "--goal", goal,
                    "--intake-path", str(intake),
                ],
                proposer,
            )
            self.assertEqual(r.returncode, 2, msg=r.stdout + r.stderr)


class TestPlanOnDirectMission(unittest.TestCase):
    """--plan on a DIRECT mission → DIRECT behaviour wins, no proposer call."""

    def test_direct_wins_over_plan_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            # Use a file-based sentinel to detect if the proposer was called
            proposer_invoked_file = Path(tmp) / "proposer-invoked"
            # Write a proposer stub that creates a sentinel then outputs a valid plan
            stub = Path(tmp) / "stub-proposer"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                f"open({str(proposer_invoked_file)!r}, 'w').close()\n"
                f"sys.stdout.write({_valid_canned_plan()!r})\n"
                "sys.exit(0)\n"
            )
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            r = _run(
                [
                    "Explain what the Lisa dispatcher does.",
                    "--plan",
                    "--intake-path", str(intake),
                ],
                env={"LISA_TEST_MODE": "1", "LISA_PROPOSER_CMD": str(stub)},
            )
            self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
            records = _read_intake(str(intake))
            statuses = [rec["status"] for rec in records]
            self.assertIn("DIRECT_INFO", statuses)
            self.assertFalse(
                proposer_invoked_file.exists(),
                "proposer was invoked on a DIRECT mission — classification must win",
            )


class TestProposerCmdGuard(unittest.TestCase):
    """LISA_PROPOSER_CMD without LISA_TEST_MODE=1 → warning on stderr, override ignored."""

    def test_warning_on_missing_test_mode(self):
        """Proposer override set but test mode absent → warning on stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            intake = Path(tmp) / "intake.jsonl"
            plan_out = Path(tmp) / "test-plan.json"
            proposer = _make_proposer_stub(tmp, _valid_canned_plan())
            # Deliberately NOT setting LISA_TEST_MODE=1, so bin/lisa must ignore
            # the stub and fall back to the real OpenClaw proposer. OPENCLAW_BIN
            # is pointed at a nonexistent binary so that fallback fails closed
            # locally: this test must never make a live, paid LLM call, and must
            # not depend on what a live model would return.
            r = _run(
                [
                    "S046 implement the payment module",
                    "--plan",
                    "--plan-out", str(plan_out),
                    "--intake-path", str(intake),
                ],
                env={
                    "LISA_PROPOSER_CMD": proposer,
                    "OPENCLAW_BIN": str(Path(tmp) / "no-such-openclaw-binary"),
                },
            )
            # Exit 8 == PLAN_PROPOSER_FAILED: proves the real proposer was the
            # one selected (and failed closed), not the ignored stub.
            self.assertEqual(
                r.returncode, 8,
                f"expected PLAN_PROPOSER_FAILED (8); got {r.returncode}. "
                f"stdout={r.stdout!r} stderr={r.stderr!r}",
            )
            self.assertIn(
                "LISA_PROPOSER_CMD",
                r.stderr,
                f"expected LISA_PROPOSER_CMD warning in stderr; got: {r.stderr!r}",
            )
            self.assertIn(
                "LISA_TEST_MODE",
                r.stderr,
                f"expected LISA_TEST_MODE mention in warning; got: {r.stderr!r}",
            )
            # Stub must NOT have been invoked (no sentinel from the stub)
            self.assertFalse(
                plan_out.exists(),
                "Plan artifact should not exist: proposer stub must not have been used",
            )


if __name__ == "__main__":
    unittest.main()

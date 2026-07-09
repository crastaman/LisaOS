"""Proof-of-work tests for the LisaOS <-> OpenClaw real execution bridge
(Phase 4 remediation; see core/openclaw_bridge.py).

Fully hermetic: every subprocess call into the real `openclaw` binary is
mocked. No network, no real spend, no dependency on a running Gateway --
mirrors the hermetic-by-injection style of tests/test_provider_resolution.py
and tests/test_dispatcher.py.

Covers:
  * Live agent-map derivation + WBS-agent exclusion.
  * Fail-closed paths: no physical model, gateway unreachable, no eligible
    non-WBS agent bound to the resolved model (the "no --model override"
    finding from PHASE4_IMPLEMENTATION_REPORT.md).
  * Real-execution success path against the actual `openclaw agent --json`
    response shape captured from a live probe call.
  * Mismatch detection when the observed model disagrees with the resolved
    one.
  * The dispatcher never falls back to simulation when real execution fails.
"""

import json
import unittest
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

from core.dispatcher import ExecutionResult
from core.openclaw_bridge import (
    agent_for_physical_model,
    non_wbs_agents,
    gateway_reachable,
    build_real_executor,
    labelled_simulated_executor,
    BridgeError,
    SIMULATED_LABEL,
)
from core.provider_resolver import ProviderResolver, CredentialSource


_AGENTS_JSON = json.dumps([
    {"id": "main", "model": "custom-api-deepseek-com/deepseek-reasoner"},
    {"id": "documentation", "model": "custom-api-deepseek-com/deepseek-reasoner"},
    {"id": "architecture", "model": "openai/gpt-5.5"},
    {"id": "engineering", "model": "openai/gpt-5.5"},
    {"id": "qa", "model": "openai/gpt-5.5"},
    {"id": "wbs-architect-opus", "model": "anthropic/claude-opus-4-8"},
    {"id": "wbs-worker-qwen", "model": "deepinfra/Qwen/Qwen3.6-35B-A3B"},
])


def _resolver():
    config = {
        "providers": {
            "deepseek": {
                "physical_model": "custom-api-deepseek-com/deepseek-reasoner",
                "runtime": "openclaw",
                "credential": {"type": "inline_api_key", "openclaw_provider": "custom-api-deepseek-com"},
                "aliases": [],
            },
            # ORDER IS LOAD-BEARING: codex is declared BEFORE gpt, matching
            # registry/provider_resolution.yml (codex ~line 83, gpt ~line 93).
            # Both share physical_model openai/gpt-5.5, so the physical-model-
            # keyed reverse index (_physical_model_index) resolves that key to
            # whichever is inserted LAST -> ('gpt','openclaw'). A pre-hotfix
            # reverse-index lookup therefore MISLABELS a correct codex dispatch
            # as gpt/openclaw. If this ordering were flipped (codex last), the
            # buggy path would accidentally return codex and the regression
            # test would pass on pre-hotfix code -- do not reorder.
            "codex": {
                "physical_model": "openai/gpt-5.5",
                "runtime": "codex",
                "credential": {"type": "oauth", "provider": "openai"},
                "aliases": [],
            },
            "gpt": {
                "physical_model": "openai/gpt-5.5",
                "runtime": "openclaw",
                "credential": {"type": "oauth", "provider": "openai"},
                "aliases": [],
            },
            "claude-opus": {
                "physical_model": "anthropic/claude-opus-4-8",
                "runtime": "claude-cli",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": [],
            },
        },
        "fallback_policy": {"enabled": False, "chains": {}},
    }
    creds = CredentialSource(env={}, openclaw_config={})
    return ProviderResolver(config=config, credentials=creds)


@dataclass
class _FakePkg:
    id: str
    description: str = "Reply with exactly one word: ack"


@dataclass
class _FakeAssignment:
    physical_model: str | None
    available: bool = True
    resolved_logical: str | None = None
    resolved_runtime: str | None = "openclaw"


class TestAgentInventory(unittest.TestCase):
    @patch("core.openclaw_bridge.subprocess.run")
    def test_non_wbs_agents_excludes_wbs_prefixed_ids(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr="")
        agents = non_wbs_agents()
        ids = {a["id"] for a in agents}
        self.assertNotIn("wbs-architect-opus", ids)
        self.assertNotIn("wbs-worker-qwen", ids)
        self.assertIn("main", ids)
        self.assertIn("architecture", ids)

    @patch("core.openclaw_bridge.subprocess.run")
    def test_agent_for_physical_model_finds_non_wbs_match(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr="")
        self.assertEqual(agent_for_physical_model("openai/gpt-5.5"), "architecture")
        self.assertEqual(agent_for_physical_model("custom-api-deepseek-com/deepseek-reasoner"), "main")

    @patch("core.openclaw_bridge.subprocess.run")
    def test_agent_for_physical_model_returns_none_when_only_wbs_agent_bound(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr="")
        # Only wbs-architect-opus is bound to claude-opus -- must not match.
        self.assertIsNone(agent_for_physical_model("anthropic/claude-opus-4-8"))
        self.assertIsNone(agent_for_physical_model("deepinfra/Qwen/Qwen3.6-35B-A3B"))

    @patch("core.openclaw_bridge.subprocess.run")
    def test_agents_list_failure_raises_bridge_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        with self.assertRaises(BridgeError):
            non_wbs_agents()


class TestGatewayReachable(unittest.TestCase):
    @patch("core.openclaw_bridge.subprocess.run")
    def test_reachable_when_health_exits_zero(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        ok, reason = gateway_reachable()
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    @patch("core.openclaw_bridge.subprocess.run")
    def test_unreachable_when_health_exits_nonzero(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="gateway down")
        ok, reason = gateway_reachable()
        self.assertFalse(ok)
        self.assertIn("gateway down", reason)


class TestRealExecutorFailClosed(unittest.TestCase):
    def test_no_physical_model_fails_closed_without_any_subprocess_call(self):
        executor = build_real_executor(resolver=_resolver())
        with patch("core.openclaw_bridge.subprocess.run") as mock_run:
            result = executor(_FakePkg("p1"), _FakeAssignment(physical_model=None, available=False))
        mock_run.assert_not_called()
        self.assertFalse(result.success)
        self.assertIn("no resolved physical model", result.error)
        self.assertEqual(result.execution_evidence_source, "fail-closed-no-resolution")

    @patch("core.openclaw_bridge.gateway_reachable")
    def test_gateway_unreachable_fails_closed_never_falls_back_to_simulation(self, mock_reachable):
        mock_reachable.return_value = (False, "connection refused")
        executor = build_real_executor(resolver=_resolver())
        with patch("core.openclaw_bridge.subprocess.run") as mock_run:
            result = executor(_FakePkg("p1"),
                              _FakeAssignment(physical_model="openai/gpt-5.5", available=True))
        # No 'openclaw agent' spawn attempted once gateway check failed.
        mock_run.assert_not_called()
        self.assertFalse(result.success)
        self.assertIn("gateway unreachable", result.error)
        self.assertIsNone(result.actual_runtime)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge.subprocess.run")
    def test_no_eligible_non_wbs_agent_fails_closed_with_specific_reason(self, mock_run, _reachable):
        mock_run.return_value = MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr="")
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("claude-probe"),
            _FakeAssignment(physical_model="anthropic/claude-opus-4-8", available=True),
        )
        self.assertFalse(result.success)
        self.assertIn("no non-WBS OpenClaw agent is bound", result.error)
        self.assertEqual(result.execution_evidence_source, "fail-closed-no-eligible-agent")
        # Only the (mocked) 'agents list' call happened -- never a real spawn.
        self.assertEqual(mock_run.call_count, 1)
        self.assertIn("agents", mock_run.call_args[0][0])


_REAL_RESPONSE_SHAPE = json.dumps({
    "runId": "d6f23e4f-6e9e-48e0-8659-d6335bbd7411",
    "status": "ok",
    "summary": "completed",
    "result": {
        "payloads": [{"text": "ack", "mediaUrl": None}],
        "meta": {
            "durationMs": 2950,
            "agentMeta": {
                "provider": "openai", "model": "gpt-5.5",
                "usage": {"input": 6902, "output": 5, "total": 13051},
            },
        },
        "executionTrace": {
            "winnerProvider": "openai", "winnerModel": "gpt-5.5",
            "attempts": [{"provider": "openai", "model": "gpt-5.5", "result": "success"}],
            "fallbackUsed": False, "runner": "embedded",
        },
    },
})


class TestRealExecutorSuccess(unittest.TestCase):
    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run")
    @patch("core.openclaw_bridge.subprocess.run")
    def test_success_path_parses_real_response_shape(self, mock_run, mock_fetch, _reachable):
        # Exactly two calls: agents list (agent selection), then the spawn.
        # Phase 5 hardening (R2): there must be NO second 'agents list' call
        # in the success path -- the old tautological observed-model lookup
        # (which re-queried agents) is gone, replaced by the registry-driven
        # short-id index in _resolve_observed_physical_model.
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_REAL_RESPONSE_SHAPE, stderr=""),
        ]
        mock_fetch.return_value = {
            "task_id": "t1", "runtime": "cli", "agent_id": "architecture",
            "run_id": "d6f23e4f-6e9e-48e0-8659-d6335bbd7411", "status": "succeeded",
        }
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("codex-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.actual_runtime, "openclaw")  # gpt's runtime in the fixture resolver
        self.assertEqual(result.observed_model, "openai/gpt-5.5")
        self.assertEqual(result.observed_provider, "openai")
        self.assertEqual(result.agent_id, "architecture")
        self.assertEqual(result.run_id, "d6f23e4f-6e9e-48e0-8659-d6335bbd7411")
        self.assertEqual(result.tokens, {"input": 6902, "output": 5, "total": 13051})
        self.assertFalse(result.mismatch)
        self.assertEqual(result.execution_evidence_source,
                         "openclaw_json_response+task_runs_confirmed")
        self.assertEqual(mock_run.call_count, 2,
                         "success path must not re-query 'openclaw agents list'")

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_mismatch_detected_when_task_runs_disagrees(self, mock_run, mock_fetch, _reachable):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_REAL_RESPONSE_SHAPE, stderr=""),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("codex-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        # No DB row found -> evidence source reflects unconfirmed, not silently "matched".
        self.assertEqual(result.execution_evidence_source, "openclaw_json_response")

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge.subprocess.run")
    def test_nonzero_exit_fails_closed_with_stderr_reason(self, mock_run, _reachable):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=1, stdout="", stderr="GatewayClientRequestError: boom"),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("codex-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertFalse(result.success)
        self.assertIn("boom", result.error)
        self.assertEqual(result.execution_evidence_source, "real-execution-failed")


_FALLBACK_RESPONSE_SHAPE = json.dumps({
    "runId": "fb00fb00-0000-0000-0000-000000000000",
    "status": "ok",
    "summary": "completed",
    "result": {
        "payloads": [{"text": "ack", "mediaUrl": None}],
        "meta": {
            "durationMs": 4000,
            "agentMeta": {
                "provider": "custom-api-deepseek-com", "model": "deepseek-reasoner",
                "usage": {"input": 100, "output": 10, "total": 110},
            },
        },
        "executionTrace": {
            # The agent is bound to gpt-5.5, but OpenClaw's own runtime
            # signal says it actually fell back to DeepSeek -- exactly the
            # class of drift the old (tautological, agent-binding-based)
            # comparison could never detect.
            "winnerProvider": "custom-api-deepseek-com", "winnerModel": "deepseek-reasoner",
            "attempts": [
                {"provider": "openai", "model": "gpt-5.5", "result": "failure"},
                {"provider": "custom-api-deepseek-com", "model": "deepseek-reasoner", "result": "success"},
            ],
            "fallbackUsed": True, "runner": "embedded",
        },
    },
})

_UNRECOGNIZED_MODEL_RESPONSE_SHAPE = json.dumps({
    "runId": "unk00unk-0000-0000-0000-000000000000",
    "status": "ok",
    "summary": "completed",
    "result": {
        "payloads": [{"text": "ack", "mediaUrl": None}],
        "meta": {"durationMs": 1000, "agentMeta": {"provider": "openai", "model": "totally-unknown-model-9000"}},
        "executionTrace": {
            "winnerProvider": "openai", "winnerModel": "totally-unknown-model-9000",
            "attempts": [], "fallbackUsed": False, "runner": "embedded",
        },
    },
})


class TestExecutionAttributionMismatch(unittest.TestCase):
    """R1: mismatch detection must use OpenClaw's own runtime signal
    (executionTrace.winnerModel/fallbackUsed), not the agent's configured
    binding (which is tautologically always equal to the resolved model,
    since that's how the agent was selected)."""

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_fallback_used_flags_mismatch_and_observed_model_is_the_real_winner(
        self, mock_run, _fetch, _reachable,
    ):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_FALLBACK_RESPONSE_SHAPE, stderr=""),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("drift-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertTrue(result.mismatch)
        self.assertIn("fallbackUsed=True", result.mismatch_detail)
        # observed_model reflects what ACTUALLY ran (deepseek), not what was
        # configured/requested (gpt-5.5) -- the old code would have reported
        # the gpt-5.5 agent binding here and shown mismatch=False.
        self.assertEqual(result.observed_model, "custom-api-deepseek-com/deepseek-reasoner")
        self.assertEqual(result.observed_provider, "custom-api-deepseek-com")
        # success is a SEPARATE signal from mismatch -- real work did
        # complete (just not on the intended model), so success stays True;
        # it is check_no_execution_mismatch (anti_regression) that turns
        # this into a hard gate failure, not the execution result itself.
        self.assertTrue(result.success)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_unrecognized_winner_model_is_flagged_not_assumed_clean(
        self, mock_run, _fetch, _reachable,
    ):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_UNRECOGNIZED_MODEL_RESPONSE_SHAPE, stderr=""),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("unknown-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertTrue(result.mismatch)
        self.assertIn("does not match any known registry physical model", result.mismatch_detail)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_clean_run_no_fallback_recognized_winner_is_not_a_mismatch(
        self, mock_run, _fetch, _reachable,
    ):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_REAL_RESPONSE_SHAPE, stderr=""),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("clean-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertFalse(result.mismatch)
        self.assertIsNone(result.mismatch_detail)


class TestExecutorExceptionSafety(unittest.TestCase):
    """R2: no unexpected exception inside the bridge may escape build_real_executor's
    returned callable -- it must always come back as a fail-closed
    ExecutionResult, even after the real spawn already returned successfully."""

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run")
    @patch("core.openclaw_bridge.subprocess.run")
    def test_post_success_exception_is_converted_to_fail_closed_result(
        self, mock_run, mock_fetch, _reachable,
    ):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_REAL_RESPONSE_SHAPE, stderr=""),
        ]
        # Simulate a fault AFTER the real (paid) spawn already returned --
        # e.g. a gateway blip on the post-run DB confirmation step.
        mock_fetch.side_effect = RuntimeError("simulated gateway blip after spend")
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("codex-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.execution_evidence_source, "fail-closed-executor-exception")
        self.assertIn("simulated gateway blip", result.error)

    @patch("core.openclaw_bridge.subprocess.run")
    def test_agents_list_enumeration_error_is_fail_closed_not_a_crash(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        with patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok")):
            executor = build_real_executor(resolver=_resolver())
            result = executor(
                _FakePkg("p1"),
                _FakeAssignment(physical_model="openai/gpt-5.5", available=True),
            )
        self.assertFalse(result.success)
        self.assertIn("fail-closed", result.execution_evidence_source)


class TestWorkforceTruthHotfix(unittest.TestCase):
    """Workforce Truth Hotfix (see reports/lisa/CTO_WORKFORCE_GOVERNANCE_REVIEW.md):
    codex and gpt share ONE physical_model (openai/gpt-5.5) but declare
    DIFFERENT runtime labels in the registry. The reverse index used to
    silently collapse them -- a correct codex dispatch got labelled
    actual_runtime="gpt"/"openclaw". Fixed by using the assignment's own
    resolved_runtime when there is no genuine physical-model drift."""

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_codex_no_drift_labels_actual_runtime_as_codex_not_gpt(
        self, mock_run, _fetch, _reachable,
    ):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_REAL_RESPONSE_SHAPE, stderr=""),  # winnerModel="gpt-5.5", no drift
        ]
        executor = build_real_executor(resolver=_resolver())
        # This assignment is exactly what WorkforceResolver produces for a
        # codex-staffed employee: resolved_logical/resolved_runtime="codex",
        # set unambiguously at staffing time from the registry's own
        # 'codex' entry -- never derived from the collided reverse index.
        result = executor(
            _FakePkg("codex-hotfix-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True,
                            resolved_logical="codex", resolved_runtime="codex"),
        )
        # Criterion 1: actual_runtime == resolved_runtime, gate would pass.
        self.assertEqual(result.actual_runtime, "codex")
        self.assertNotEqual(result.actual_runtime, "openclaw")
        # Criterion 2: observed_model / mismatch / success all unchanged.
        self.assertEqual(result.observed_model, "openai/gpt-5.5")
        self.assertFalse(result.mismatch)
        self.assertTrue(result.success)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_gpt_no_drift_still_labels_actual_runtime_as_gpt(
        self, mock_run, _fetch, _reachable,
    ):
        # Sibling case: a gpt-staffed (not codex-staffed) assignment on the
        # same physical model must keep its own correct label too -- the
        # fix must not just special-case codex.
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_REAL_RESPONSE_SHAPE, stderr=""),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("gpt-hotfix-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True,
                            resolved_logical="gpt", resolved_runtime="openclaw"),
        )
        self.assertEqual(result.actual_runtime, "openclaw")
        self.assertFalse(result.mismatch)

    @patch("core.openclaw_bridge.gateway_reachable", return_value=(True, "ok"))
    @patch("core.openclaw_bridge._fetch_task_run", return_value=None)
    @patch("core.openclaw_bridge.subprocess.run")
    def test_genuine_drift_still_uses_reverse_index_unaffected_by_hotfix(
        self, mock_run, _fetch, _reachable,
    ):
        # Criterion 3: a REAL drift (codex requested, deepseek actually ran)
        # must still be caught -- the hotfix only changes the NO-drift label
        # path, never the drift-detection path.
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=_AGENTS_JSON, stderr=""),
            MagicMock(returncode=0, stdout=_FALLBACK_RESPONSE_SHAPE, stderr=""),
        ]
        executor = build_real_executor(resolver=_resolver())
        result = executor(
            _FakePkg("codex-drift-probe"),
            _FakeAssignment(physical_model="openai/gpt-5.5", available=True,
                            resolved_logical="codex", resolved_runtime="codex"),
        )
        self.assertTrue(result.mismatch)
        self.assertEqual(result.observed_model, "custom-api-deepseek-com/deepseek-reasoner")
        self.assertEqual(result.actual_runtime, "openclaw")  # deepseek's own runtime, from the reverse index


class TestSimulatedLabelling(unittest.TestCase):
    def test_labelled_simulated_executor_stamps_the_label(self):
        result = labelled_simulated_executor(
            _FakePkg("p1"), _FakeAssignment(physical_model="x", resolved_logical="deepseek"),
        )
        self.assertEqual(result.execution_evidence_source, SIMULATED_LABEL)
        self.assertTrue(result.success)  # underlying simulated_executor still "succeeds"


if __name__ == "__main__":
    unittest.main()

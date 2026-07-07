"""Proof-of-work tests for the LisaOS Workforce Resolver (Phase 1).

Validates docs/LISAOS/V3/21_WORKFORCE_RESOLVER_REPORT.md against the REAL,
shipped `registry/employees.yml` (loaded via EmployeeRegistry(), no injection),
combined with a fully hermetic 9-provider ProviderResolver fixture (injected
config + credentials -- no real network/provider calls, no spend).

Covers:
  * Employee registry validity (structural + referenced-model checks).
  * Capability matching + seniority-ordered candidate selection.
  * Employee -> model -> physical runtime resolution.
  * Explicit, recorded fallback selection (multi-hop, skipping probation).
  * Fail-closed: no capable employee; no available model; DeepSeek never
    injected implicitly (only used when an employee's own chain lists it).
  * GLM / GLM-turbo PROBATION restriction (low-risk only; skipped/fail-closed
    otherwise).
  * The six required assignment scenarios: Haiku microtask, Sonnet
    implementation, Opus architecture, Qwen-DeepInfra documentation, Codex
    implementation, DeepSeek orchestration.

Run with:
    PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_workforce_resolver -v
"""

import unittest

from core.provider_resolver import ProviderResolver, CredentialSource
from core.workforce_resolver import (
    EmployeeRegistry,
    WorkforceResolver,
    WorkforceResolutionError,
    WorkPackage,
    DETERMINISTIC_MODEL,
)

DEEPSEEK_PHYSICAL = "custom-api-deepseek-com/deepseek-reasoner"


# --------------------------------------------------------------------------- #
# Hermetic provider fixture: the 9 logical providers every employee in
# registry/employees.yml references, mirroring registry/provider_resolution.yml.
# --------------------------------------------------------------------------- #

def make_provider_config() -> dict:
    return {
        "version": 2,
        "providers": {
            "deepseek": {
                "physical_model": DEEPSEEK_PHYSICAL,
                "runtime": "openclaw",
                "provider_id": "custom-api-deepseek-com",
                "credential": {"type": "inline_api_key",
                               "openclaw_provider": "custom-api-deepseek-com"},
                "aliases": ["ds"],
            },
            "claude-opus": {
                "physical_model": "anthropic/claude-opus-4-8",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["opus"],
            },
            "claude-sonnet": {
                "physical_model": "anthropic/claude-sonnet-4-6",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["sonnet"],
            },
            "claude-haiku": {
                "physical_model": "anthropic/claude-haiku-4-5",
                "runtime": "claude-cli",
                "provider_id": "anthropic",
                "credential": {"type": "oauth", "provider": "claude-cli"},
                "aliases": ["haiku"],
            },
            "codex": {
                "physical_model": "openai/gpt-5.5",
                "runtime": "codex",
                "provider_id": "openai",
                "credential": {"type": "oauth", "provider": "openai"},
                "aliases": [],
            },
            "gpt": {
                "physical_model": "openai/gpt-5.5",
                "runtime": "openclaw",
                "provider_id": "openai",
                "credential": {"type": "oauth", "provider": "openai"},
                "aliases": [],
            },
            "qwen-deepinfra": {
                "physical_model": "deepinfra/Qwen/Qwen3.6-35B-A3B",
                "runtime": "openclaw",
                "provider_id": "deepinfra",
                "credential": {"type": "api_key", "env": "DEEPINFRA_API_KEY",
                               "openclaw_provider": "deepinfra"},
                "aliases": [],
            },
            # PROBATIONARY: authenticated but not trusted; low-risk work only.
            "glm": {
                "physical_model": "zai/glm-5.2",
                "runtime": "openclaw",
                "provider_id": "zai",
                "credential": {"type": "api_key", "env": "ZAI_API_KEY",
                               "openclaw_provider": "zai"},
                "probation": True,
                "critical_routing": False,
                "aliases": [],
            },
            "glm-turbo": {
                "physical_model": "zai/glm-5-turbo",
                "runtime": "openclaw",
                "provider_id": "zai",
                "credential": {"type": "api_key", "env": "ZAI_API_KEY",
                               "openclaw_provider": "zai"},
                "probation": True,
                "critical_routing": False,
                "aliases": [],
            },
        },
        "fallback_policy": {"enabled": False, "chains": {}},
    }


def _openclaw_config(*, claude_cli_oauth: bool = True) -> dict:
    profiles = {"openai:user": {"provider": "openai", "mode": "oauth"}}
    if claude_cli_oauth:
        profiles["anthropic:claude-cli"] = {"provider": "claude-cli", "mode": "oauth"}
    return {
        "models": {"providers": {
            "custom-api-deepseek-com": {"apiKey": "sk-deepseek-inline"},
            "deepinfra": {"apiKey": "${DEEPINFRA_API_KEY}"},
            "zai": {"apiKey": "${ZAI_API_KEY}"},
        }},
        "auth": {"profiles": profiles},
    }


def resolver_all_available() -> ProviderResolver:
    creds = CredentialSource(
        env={"DEEPINFRA_API_KEY": "di-key", "ZAI_API_KEY": "zai-key"},
        openclaw_config=_openclaw_config(claude_cli_oauth=True),
    )
    return ProviderResolver(config=make_provider_config(), credentials=creds)


def resolver_no_deepinfra() -> ProviderResolver:
    creds = CredentialSource(
        env={"ZAI_API_KEY": "zai-key"},   # DEEPINFRA_API_KEY absent
        openclaw_config=_openclaw_config(claude_cli_oauth=True),
    )
    return ProviderResolver(config=make_provider_config(), credentials=creds)


def resolver_no_claude_cli() -> ProviderResolver:
    """Anthropic subscription down: claude-opus/sonnet/haiku all unavailable."""
    creds = CredentialSource(
        env={"DEEPINFRA_API_KEY": "di-key", "ZAI_API_KEY": "zai-key"},
        openclaw_config=_openclaw_config(claude_cli_oauth=False),
    )
    return ProviderResolver(config=make_provider_config(), credentials=creds)


def resolver_none_available() -> ProviderResolver:
    creds = CredentialSource(env={}, openclaw_config={"models": {"providers": {}},
                                                       "auth": {"profiles": {}}})
    return ProviderResolver(config=make_provider_config(), credentials=creds)


def real_employees() -> EmployeeRegistry:
    """The REAL, shipped registry/employees.yml -- not a fixture."""
    return EmployeeRegistry()


# --------------------------------------------------------------------------- #
# 1. Employee registry validity
# --------------------------------------------------------------------------- #

class TestEmployeeRegistryValidity(unittest.TestCase):
    def test_registry_loads_and_has_fifteen_employees(self):
        reg = real_employees()
        self.assertEqual(len(reg.employees), 15)

    def test_registry_validates_structurally(self):
        reg = real_employees()
        problems = reg.validate()
        self.assertEqual(problems, [], f"structural problems: {problems}")

    def test_registry_all_model_references_are_known_providers(self):
        # Every preferred_model / fallback_model in the shipped registry must
        # resolve against the (hermetic) 9-provider schema.
        reg = real_employees()
        problems = reg.validate(resolver_all_available())
        self.assertEqual(problems, [], f"unknown model references: {problems}")

    def test_registry_detects_unknown_model_reference(self):
        # Sanity check that validate() actually catches a bad reference --
        # inject a fake employee pointing at a retired alias.
        cfg = {
            "seniority_ranks": {"standard": 3},
            "employees": {
                "broken-employee": {
                    "department": "engineering", "seniority": "standard",
                    "capabilities": ["code-implementation"],
                    "preferred_family": "x", "preferred_model": "qwen",  # retired!
                    "fallback_models": [], "cost_class": "elastic-api",
                    "reliability_class": "medium", "failure_policy": "halt",
                },
            },
        }
        reg = EmployeeRegistry(config=cfg)
        problems = reg.validate(resolver_all_available())
        self.assertTrue(any("qwen" in p for p in problems))

    def test_registry_detects_duplicate_and_missing_fields(self):
        cfg = {
            "seniority_ranks": {"standard": 3},
            "employees": {
                "incomplete": {"department": "engineering"},  # missing most fields
            },
        }
        reg = EmployeeRegistry(config=cfg)
        problems = reg.validate()
        self.assertTrue(any("missing required field" in p for p in problems))


# --------------------------------------------------------------------------- #
# 2. Capability matching + seniority ordering
# --------------------------------------------------------------------------- #

class TestCapabilityMatching(unittest.TestCase):
    def test_only_chief_architect_provides_architecture(self):
        candidates = real_employees().candidates_for(["architecture"])
        self.assertEqual([c.id for c in candidates], ["chief-architect"])

    def test_deterministic_employees_never_candidates(self):
        reg = real_employees()
        for caps in (["routing", "scheduling"], ["provider-resolution"]):
            candidates = reg.candidates_for(caps)
            self.assertEqual(candidates, [],
                             f"deterministic employee wrongly matched for {caps}")
        # Even a capability no one has -> empty, not an error.
        self.assertEqual(reg.candidates_for(["nonexistent-capability"]), [])

    def test_seniority_ordering_lowest_first(self):
        reg = real_employees()
        candidates = reg.candidates_for(["documentation"])
        ids = [c.id for c in candidates]
        # operations-microtask-agent (microtask=1) must be first.
        self.assertEqual(ids[0], "operations-microtask-agent")
        # release-manager (standard=3) must be last.
        self.assertEqual(ids[-1], "release-manager")
        ranks = [reg.seniority_rank(c) for c in candidates]
        self.assertEqual(ranks, sorted(ranks), "candidates must be seniority-sorted")

    def test_capability_superset_required(self):
        # implementation-engineer lacks 'refactor'/'review'/'long-context', so a
        # senior-engineer-shaped requirement must exclude it.
        reg = real_employees()
        candidates = reg.candidates_for(
            ["code-implementation", "refactor", "review", "long-context"])
        self.assertEqual([c.id for c in candidates], ["senior-software-engineer"])


# --------------------------------------------------------------------------- #
# 3. Fail-closed behaviour
# --------------------------------------------------------------------------- #

class TestFailClosed(unittest.TestCase):
    def test_no_capable_employee_raises(self):
        wf = WorkforceResolver(real_employees(), resolver_all_available())
        wp = WorkPackage(id="wp1", description="x",
                         required_capabilities=["nonexistent-capability"])
        with self.assertRaises(WorkforceResolutionError) as ctx:
            wf.resolve(wp)
        self.assertEqual(ctx.exception.evidence.auth_result, "no_capable_employee")
        self.assertIsNone(ctx.exception.evidence.employee)

    def test_no_available_model_raises_and_never_injects_deepseek(self):
        # chief-architect has NO fallback models. With Anthropic subscription
        # down, architecture work must fail closed -- never silently land on
        # DeepSeek (which chief-architect's chain does not even list).
        wf = WorkforceResolver(real_employees(), resolver_no_claude_cli())
        wp = WorkPackage(id="wp2", description="x",
                         required_capabilities=["architecture"])
        with self.assertRaises(WorkforceResolutionError) as ctx:
            wf.resolve(wp)
        ev = ctx.exception.evidence
        self.assertEqual(ev.employee, "chief-architect")
        self.assertEqual(ev.auth_result, "no_available_model")
        # No physical model/runtime was ever assigned -- in particular, never
        # DeepSeek, which does not even appear in chief-architect's chain.
        self.assertIsNone(ev.physical_model)
        self.assertIsNone(ev.resolved_logical)
        self.assertNotEqual(ev.physical_model, DEEPSEEK_PHYSICAL)
        self.assertNotIn("deepseek", ",".join(
            real_employees().employees["chief-architect"].model_chain()).lower())

    def test_fully_unavailable_registry_fails_closed(self):
        wf = WorkforceResolver(real_employees(), resolver_none_available())
        wp = WorkPackage(id="wp3", description="x", required_capabilities=["microtask"])
        with self.assertRaises(WorkforceResolutionError) as ctx:
            wf.resolve(wp)
        self.assertEqual(ctx.exception.evidence.auth_result, "no_available_model")


# --------------------------------------------------------------------------- #
# 4. Explicit, recorded fallback selection
# --------------------------------------------------------------------------- #

class TestFallbackSelection(unittest.TestCase):
    def test_multihop_fallback_skips_probation_and_records_reason(self):
        # documentation-engineer chain: [qwen-deepinfra, glm, claude-haiku].
        # DeepInfra down -> glm is a probation candidate but risk=normal ->
        # skipped -> lands on claude-haiku, with the fallback explicitly
        # recorded against the employee's PREFERRED model.
        wf = WorkforceResolver(real_employees(), resolver_no_deepinfra())
        wp = WorkPackage(id="wp4", description="x",
                         required_capabilities=["documentation", "long-context",
                                                "bulk-mechanical"],
                         risk="normal")
        assignment = wf.resolve(wp)
        self.assertEqual(assignment.employee, "documentation-engineer")
        self.assertEqual(assignment.intended_model, "qwen-deepinfra")
        self.assertEqual(assignment.resolved_logical, "claude-haiku")
        self.assertEqual(assignment.fallback_from, "qwen-deepinfra")
        self.assertIsNotNone(assignment.fallback_reason)
        self.assertIn("qwen-deepinfra", assignment.fallback_reason)
        self.assertIn("claude-haiku", assignment.fallback_reason)

    def test_no_fallback_when_preferred_available(self):
        wf = WorkforceResolver(real_employees(), resolver_all_available())
        wp = WorkPackage(id="wp5", description="x",
                         required_capabilities=["documentation", "long-context",
                                                "bulk-mechanical"])
        assignment = wf.resolve(wp)
        self.assertEqual(assignment.resolved_logical, assignment.intended_model)
        self.assertIsNone(assignment.fallback_from)
        self.assertIsNone(assignment.fallback_reason)


# --------------------------------------------------------------------------- #
# 5. GLM / GLM-turbo probation restriction
# --------------------------------------------------------------------------- #

class TestGLMProbationRestriction(unittest.TestCase):
    def test_glm_turbo_used_on_low_risk_when_haiku_unavailable(self):
        wf = WorkforceResolver(real_employees(), resolver_no_claude_cli())
        wp = WorkPackage(id="wp6", description="x",
                         required_capabilities=["microtask"], risk="low")
        assignment = wf.resolve(wp)
        self.assertEqual(assignment.employee, "operations-microtask-agent")
        self.assertEqual(assignment.resolved_logical, "glm-turbo")
        self.assertEqual(assignment.fallback_from, "claude-haiku")
        self.assertIsNotNone(assignment.fallback_reason)

    def test_glm_turbo_skipped_and_fails_closed_on_normal_risk(self):
        wf = WorkforceResolver(real_employees(), resolver_no_claude_cli())
        wp = WorkPackage(id="wp7", description="x",
                         required_capabilities=["microtask"], risk="normal")
        with self.assertRaises(WorkforceResolutionError) as ctx:
            wf.resolve(wp)
        ev = ctx.exception.evidence
        self.assertEqual(ev.employee, "operations-microtask-agent")
        self.assertEqual(ev.auth_result, "no_available_model")
        self.assertIn("probation", ev.fallback_reason)

    def test_glm_never_used_for_critical_risk(self):
        wf = WorkforceResolver(real_employees(), resolver_no_claude_cli())
        wp = WorkPackage(id="wp8", description="x",
                         required_capabilities=["microtask"], risk="critical")
        with self.assertRaises(WorkforceResolutionError):
            wf.resolve(wp)


# --------------------------------------------------------------------------- #
# 6. Required assignment scenarios
# --------------------------------------------------------------------------- #

class TestRequiredAssignmentScenarios(unittest.TestCase):
    """The six staffing scenarios explicitly required for Phase 1."""

    def setUp(self):
        self.wf = WorkforceResolver(real_employees(), resolver_all_available())

    def _resolve(self, caps, **kwargs):
        wp = WorkPackage(id="scn", description="x", required_capabilities=caps, **kwargs)
        return self.wf.resolve(wp)

    def test_haiku_microtask_assignment(self):
        a = self._resolve(["microtask"])
        self.assertEqual(a.employee, "operations-microtask-agent")
        self.assertEqual(a.resolved_logical, "claude-haiku")
        self.assertEqual(a.physical_model, "anthropic/claude-haiku-4-5")
        self.assertEqual(a.routed_by, "workforce_resolver")

    def test_sonnet_implementation_assignment(self):
        a = self._resolve(["code-implementation", "refactor", "review", "long-context"])
        self.assertEqual(a.employee, "senior-software-engineer")
        self.assertEqual(a.resolved_logical, "claude-sonnet")
        self.assertEqual(a.physical_model, "anthropic/claude-sonnet-4-6")

    def test_opus_architecture_assignment(self):
        a = self._resolve(["architecture"])
        self.assertEqual(a.employee, "chief-architect")
        self.assertEqual(a.resolved_logical, "claude-opus")
        self.assertEqual(a.physical_model, "anthropic/claude-opus-4-8")

    def test_qwen_deepinfra_documentation_assignment(self):
        a = self._resolve(["documentation", "long-context", "bulk-mechanical"])
        self.assertEqual(a.employee, "documentation-engineer")
        self.assertEqual(a.resolved_logical, "qwen-deepinfra")
        self.assertEqual(a.physical_model, "deepinfra/Qwen/Qwen3.6-35B-A3B")

    def test_codex_implementation_assignment(self):
        a = self._resolve(["code-execution", "code-implementation", "test-authoring"])
        self.assertEqual(a.employee, "software-engineer")
        self.assertEqual(a.resolved_logical, "codex")
        self.assertEqual(a.physical_model, "openai/gpt-5.5")
        self.assertEqual(a.resolved_runtime, "codex")

    def test_deepseek_orchestration_assignment(self):
        a = self._resolve(["code-implementation", "bulk-mechanical"])
        self.assertEqual(a.employee, "implementation-engineer")
        self.assertEqual(a.resolved_logical, "deepseek")
        self.assertEqual(a.physical_model, DEEPSEEK_PHYSICAL)


# --------------------------------------------------------------------------- #
# 7. Stale alias rejection (workforce layer never accepts a retired alias)
# --------------------------------------------------------------------------- #

class TestStaleAliasRejection(unittest.TestCase):
    def test_retired_aliases_are_unknown_to_the_hermetic_fixture(self):
        resolver = resolver_all_available()
        for alias in ("qwen", "qwen-alibaba", "ali-qwen", "qwen-modelstudio", "alibaba-qwen"):
            self.assertIsNone(resolver.normalise(alias),
                              f"retired alias {alias!r} must not resolve")

    def test_employee_referencing_stale_alias_fails_validation(self):
        cfg = {
            "seniority_ranks": {"bulk": 2},
            "employees": {
                "stale-hire": {
                    "department": "engineering", "seniority": "bulk",
                    "capabilities": ["bulk-mechanical"],
                    "preferred_family": "x", "preferred_model": "qwen-alibaba",
                    "fallback_models": [], "cost_class": "elastic-api",
                    "reliability_class": "medium", "failure_policy": "halt",
                },
            },
        }
        reg = EmployeeRegistry(config=cfg)
        problems = reg.validate(resolver_all_available())
        self.assertTrue(any("qwen-alibaba" in p for p in problems))


# --------------------------------------------------------------------------- #
# 8. Deterministic employees are never used as work executors
# --------------------------------------------------------------------------- #

class TestDeterministicEmployees(unittest.TestCase):
    def test_dispatcher_and_provider_manager_are_deterministic(self):
        reg = real_employees()
        self.assertTrue(reg.employees["dispatcher-manager"].is_deterministic)
        self.assertTrue(reg.employees["provider-manager"].is_deterministic)

    def test_deterministic_model_chain_excludes_the_sentinel(self):
        # model_chain() may list DETERMINISTIC_MODEL as the first entry, but the
        # resolver explicitly skips it (never resolves "deterministic" as a
        # logical provider).
        reg = real_employees()
        chain = reg.employees["dispatcher-manager"].model_chain()
        self.assertIn(DETERMINISTIC_MODEL, chain)


if __name__ == "__main__":
    unittest.main(verbosity=2)

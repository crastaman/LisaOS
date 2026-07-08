"""Tests for advisors.gpt_advisor (Lisa Console v1, Phase C2).

Hermetic: builds its own tmp context pack + bundle directories per test.
The OpenAI call is always injected via call_fn -- no test in this file
makes or attempts a real network call. Credentials tests rely on
LISA_CONSOLE_OPENAI_API_KEY being unset in the test environment (asserted
in setUp) so the real fail-closed path is exercised, not simulated.

Run: PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_gpt_advisor -v
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from advisors.context_pack import ContextPack, ContextPackFile
from advisors.gpt_advisor import (
    AdvisorConfigError,
    EXPECTED_BUNDLE_SCHEMA,
    SCHEMA,
    generate_and_write_brief,
    generate_brief,
    generate_brief_for_bundle_id,
    write_brief,
)
from advisors.openai_client import AdvisorAPIError, AdvisorCredentialsError


def _fake_pack(text: str = "FAKE SYSTEM ROLE CONTENT") -> ContextPack:
    return ContextPack(text=text, files=(ContextPackFile(path=Path("01_x.md"), order=1, mtime=0.0, size=0),))


def _minimal_bundle(**overrides) -> dict:
    bundle = {
        "bundle_id": "db-2026-07-08-test0001",
        "schema": EXPECTED_BUNDLE_SCHEMA,
        "job_id": "impl-example",
        "evidence": {"workforce_evidence": []},
        "decision": None,
    }
    bundle.update(overrides)
    return bundle


def _ok_response(**overrides) -> dict:
    resp = {
        "headline": "Fix looks safe to merge",
        "summary": "One low-risk change with passing evidence.",
        "recommendation": "approve",
        "confidence": "high",
        "key_risks": [],
        "suggested_actions": ["Merge after CI passes"],
        "missing_information": [],
        "escalation_recommendation": {"level": "none", "reason": None},
    }
    resp.update(overrides)
    return resp


class GPTAdvisorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-gpt-advisor-test-"))
        self.bundles_dir = self.tmp / "bundles"
        self.briefs_dir = self.tmp / "briefs"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestGenerateBriefSuccess(GPTAdvisorTestCase):
    def test_ok_response_produces_ok_brief(self) -> None:
        bundle = _minimal_bundle()
        call_fn = lambda **kwargs: _ok_response()
        brief = generate_brief(bundle, context_pack=_fake_pack(), call_fn=call_fn)
        self.assertEqual(brief["status"], "ok")
        self.assertEqual(brief["schema"], SCHEMA)
        self.assertEqual(brief["bundle_id"], bundle["bundle_id"])
        self.assertEqual(brief["recommendation"], "approve")
        self.assertEqual(brief["confidence"], "high")
        self.assertIsNone(brief["degraded_category"])

    def test_bundle_json_is_included_in_user_prompt(self) -> None:
        bundle = _minimal_bundle(job_id="my-unique-job-marker")
        seen = {}

        def call_fn(*, system_prompt, user_prompt, model=None):
            seen["system_prompt"] = system_prompt
            seen["user_prompt"] = user_prompt
            return _ok_response()

        generate_brief(bundle, context_pack=_fake_pack("SYSTEM ROLE MARKER"), call_fn=call_fn)
        self.assertIn("my-unique-job-marker", seen["user_prompt"])
        self.assertEqual(seen["system_prompt"], "SYSTEM ROLE MARKER")


class TestGenerateBriefDegradedMode(GPTAdvisorTestCase):
    def test_credentials_missing_produces_degraded_brief_not_a_crash(self) -> None:
        self.assertNotIn("LISA_CONSOLE_OPENAI_API_KEY", os.environ, "test env must not have a real key")

        def call_fn(**kwargs):
            raise AdvisorCredentialsError("LISA_CONSOLE_OPENAI_API_KEY is not set")

        bundle = _minimal_bundle()
        brief = generate_brief(bundle, context_pack=_fake_pack(), call_fn=call_fn)
        self.assertEqual(brief["status"], "degraded")
        self.assertEqual(brief["degraded_category"], "credentials")
        self.assertIsNone(brief["recommendation"])
        self.assertIsNone(brief["confidence"])
        # Bundle itself is untouched -- brief construction never mutates its input.
        self.assertIsNone(bundle["decision"])

    def test_each_api_failure_category_produces_matching_degraded_category(self) -> None:
        for category in ("unavailable", "timeout", "rate_limited", "invalid_response", "context_overflow"):
            with self.subTest(category=category):
                def call_fn(**kwargs):
                    raise AdvisorAPIError(f"simulated {category}", category=category)

                brief = generate_brief(_minimal_bundle(), context_pack=_fake_pack(), call_fn=call_fn)
                self.assertEqual(brief["status"], "degraded")
                self.assertEqual(brief["degraded_category"], category)

    def test_missing_critical_field_treated_as_partial_summary(self) -> None:
        def call_fn(**kwargs):
            return _ok_response(recommendation="not-a-real-value")

        brief = generate_brief(_minimal_bundle(), context_pack=_fake_pack(), call_fn=call_fn)
        self.assertEqual(brief["status"], "degraded")
        self.assertEqual(brief["degraded_category"], "partial_summary")
        self.assertIsNone(brief["recommendation"])

    def test_missing_noncritical_field_defaults_without_full_degradation(self) -> None:
        def call_fn(**kwargs):
            resp = _ok_response()
            del resp["key_risks"]
            return resp

        brief = generate_brief(_minimal_bundle(), context_pack=_fake_pack(), call_fn=call_fn)
        self.assertEqual(brief["key_risks"], [])
        self.assertEqual(brief["recommendation"], "approve")

    def test_degraded_brief_is_still_schema_conformant(self) -> None:
        def call_fn(**kwargs):
            raise AdvisorAPIError("down", category="unavailable")

        brief = generate_brief(_minimal_bundle(), context_pack=_fake_pack(), call_fn=call_fn)
        required_keys = {
            "brief_id", "schema", "bundle_id", "bundle_schema", "created_at", "status",
            "model", "headline", "summary", "recommendation", "confidence", "key_risks",
            "suggested_actions", "missing_information", "escalation_recommendation",
            "degraded_category", "degraded_reason",
        }
        self.assertTrue(required_keys.issubset(brief.keys()))


class TestGenerateBriefValidation(GPTAdvisorTestCase):
    def test_bundle_without_bundle_id_rejected(self) -> None:
        with self.assertRaises(AdvisorConfigError):
            generate_brief({"schema": EXPECTED_BUNDLE_SCHEMA}, context_pack=_fake_pack(), call_fn=lambda **k: _ok_response())

    def test_unsupported_bundle_schema_rejected(self) -> None:
        bundle = _minimal_bundle(schema="lisaos.console.decision_bundle.v99")
        with self.assertRaises(AdvisorConfigError):
            generate_brief(bundle, context_pack=_fake_pack(), call_fn=lambda **k: _ok_response())


class TestWriteBrief(GPTAdvisorTestCase):
    def test_writes_and_round_trips(self) -> None:
        brief = generate_brief(_minimal_bundle(), context_pack=_fake_pack(), call_fn=lambda **k: _ok_response())
        path = write_brief(brief, briefs_dir=self.briefs_dir)
        self.assertTrue(path.is_file())
        reloaded = json.loads(path.read_text())
        self.assertEqual(reloaded["brief_id"], brief["brief_id"])
        self.assertFalse((path.parent / f"{brief['brief_id']}.json.tmp").exists())

    def test_generate_and_write_brief_end_to_end(self) -> None:
        path = generate_and_write_brief(
            _minimal_bundle(), context_pack=_fake_pack(), call_fn=lambda **k: _ok_response(),
            briefs_dir=self.briefs_dir,
        )
        self.assertTrue(path.is_file())


class TestGenerateBriefForBundleId(GPTAdvisorTestCase):
    def test_reads_bundle_read_only_never_writes_to_it(self) -> None:
        bundle_dir = self.bundles_dir / "db-fixed"
        bundle_dir.mkdir(parents=True)
        bundle_path = bundle_dir / "bundle.json"
        bundle_path.write_text(json.dumps(_minimal_bundle(bundle_id="db-fixed")))

        # Make the bundle file (and its directory) read-only. If gpt_advisor
        # ever attempted to open this file for writing -- even to "fix" or
        # touch it -- this call would fail with a PermissionError.
        bundle_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        bundle_dir.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        try:
            path = generate_brief_for_bundle_id(
                "db-fixed",
                bundles_dir=self.bundles_dir,
                briefs_dir=self.briefs_dir,
                context_pack=_fake_pack(),
                call_fn=lambda **k: _ok_response(),
            )
            self.assertTrue(path.is_file())
            reloaded_bundle = json.loads(bundle_path.read_text())
            self.assertIsNone(reloaded_bundle["decision"])
        finally:
            bundle_dir.chmod(stat.S_IRWXU)
            bundle_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def test_missing_bundle_raises_config_error(self) -> None:
        with self.assertRaises(AdvisorConfigError):
            generate_brief_for_bundle_id(
                "no-such-bundle", bundles_dir=self.bundles_dir, briefs_dir=self.briefs_dir,
                context_pack=_fake_pack(), call_fn=lambda **k: _ok_response(),
            )


if __name__ == "__main__":
    unittest.main()

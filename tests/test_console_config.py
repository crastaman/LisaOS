"""Tests for console.config_check (Lisa Console v1, Phase C5).

No Flask dependency -- runs on the bare system Python, same as
tests.test_console_data / tests.test_console_actions.

Run: PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_console_config -v
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from console.config_check import check_config

_ENV_VARS = (
    "LISA_CONSOLE_OWNER_IDENTITY",
    "LISA_CONSOLE_OPENAI_API_KEY",
    "LISA_CONSOLE_NTFY_TOPIC",
    "LISA_CONSOLE_BASE_URL",
)


class ConfigCheckTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="lisaos-console-config-test-"))
        self.registry_path = self.tmp / "employees.yml"
        self.reports_console_dir = self.tmp / "reports-console"
        self._saved_env = {k: os.environ.get(k) for k in _ENV_VARS}
        for k in _ENV_VARS:
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _valid_registry(self) -> None:
        self.registry_path.write_text(yaml.dump({"employees": {"a": {"department": "eng"}}}))


class TestOwnerIdentity(ConfigCheckTestCase):
    def test_unset_is_an_error(self) -> None:
        self._valid_registry()
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertFalse(report.ok)
        self.assertTrue(any("LISA_CONSOLE_OWNER_IDENTITY" in e for e in report.errors))

    def test_commas_only_is_an_error(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = " , , "
        self._valid_registry()
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertFalse(report.ok)

    def test_set_clears_the_error(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        self._valid_registry()
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertTrue(not any("LISA_CONSOLE_OWNER_IDENTITY" in e for e in report.errors))


class TestDegradedModeWarnings(ConfigCheckTestCase):
    def test_missing_optional_config_produces_warnings_not_errors(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        self._valid_registry()
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertTrue(report.ok)  # no errors -- Console is still usable
        self.assertTrue(any("OPENAI_API_KEY" in w for w in report.warnings))
        self.assertTrue(any("NTFY_TOPIC" in w for w in report.warnings))
        self.assertTrue(any("BASE_URL" in w for w in report.warnings))

    def test_fully_configured_yields_no_warnings(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        os.environ["LISA_CONSOLE_OPENAI_API_KEY"] = "sk-x"
        os.environ["LISA_CONSOLE_NTFY_TOPIC"] = "topic"
        os.environ["LISA_CONSOLE_BASE_URL"] = "https://lisa.example.ts.net"
        self._valid_registry()
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertTrue(report.ok)
        self.assertEqual(report.warnings, [])


class TestRegistry(ConfigCheckTestCase):
    def test_missing_registry_is_an_error(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        report = check_config(
            registry_path=self.tmp / "does-not-exist.yml", reports_console_dir=self.reports_console_dir
        )
        self.assertFalse(report.ok)

    def test_malformed_yaml_is_an_error(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        self.registry_path.write_text(": : : not valid yaml : : :\n\t- broken")
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertFalse(report.ok)

    def test_empty_employees_is_a_warning_not_error(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        self.registry_path.write_text(yaml.dump({"employees": {}}))
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertTrue(report.ok)
        self.assertTrue(any("Workers screen" in w for w in report.warnings))


class TestStorage(ConfigCheckTestCase):
    def test_creates_reports_console_dir_if_missing(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        self._valid_registry()
        self.assertFalse(self.reports_console_dir.exists())
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertTrue(report.ok)
        self.assertTrue(self.reports_console_dir.is_dir())

    def test_unwritable_dir_is_an_error(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        self._valid_registry()
        self.reports_console_dir.mkdir(parents=True)
        self.reports_console_dir.chmod(0o500)  # read + execute, no write
        try:
            report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
            self.assertFalse(report.ok)
        finally:
            self.reports_console_dir.chmod(0o700)


class TestReportText(ConfigCheckTestCase):
    def test_to_text_reports_clean_state(self) -> None:
        os.environ["LISA_CONSOLE_OWNER_IDENTITY"] = "roshan@example.ts.net"
        os.environ["LISA_CONSOLE_OPENAI_API_KEY"] = "sk-x"
        os.environ["LISA_CONSOLE_NTFY_TOPIC"] = "topic"
        os.environ["LISA_CONSOLE_BASE_URL"] = "https://lisa.example.ts.net"
        self._valid_registry()
        report = check_config(registry_path=self.registry_path, reports_console_dir=self.reports_console_dir)
        self.assertIn("OK", report.to_text())


if __name__ == "__main__":
    unittest.main()

"""Configuration validation / preflight for Lisa Console (Phase C5).

A misconfigured Console should fail loudly and specifically before
deployment, not fail mysteriously on the first real request. This module
inspects the environment and local files (never modifies anything) and
returns a structured report: errors (Console cannot function safely)
versus warnings (a feature degrades gracefully -- see the C2/C3 degraded-
mode contracts -- but isn't fully configured).

No LisaOS runtime imports (core/, engines/); no Flask import either --
this module has no route/UI dependency and can be run from a bare
`python3` CLI (`bin/console-preflight`) without the console/ virtualenv,
except for the one registry check, which needs PyYAML (already a de
facto LisaOS dependency -- see core/registry.py et al).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
REGISTRY_PATH = LISA_BASE / "registry" / "employees.yml"
REPORTS_CONSOLE_DIR = LISA_BASE / "reports" / "console"


@dataclass
class ConfigReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_text(self) -> str:
        lines = []
        if not self.errors and not self.warnings:
            lines.append("Configuration OK -- no errors or warnings.")
        for e in self.errors:
            lines.append(f"ERROR: {e}")
        for w in self.warnings:
            lines.append(f"WARNING: {w}")
        return "\n".join(lines)


def check_config(*, registry_path: Path | None = None, reports_console_dir: Path | None = None) -> ConfigReport:
    report = ConfigReport()

    # -- Auth: the one setting that is a hard error, not a degrade. An
    # unset/empty allowlist doesn't crash the app -- it fails closed and
    # denies everyone, silently, forever, which looks like "the Console
    # is broken" rather than "the Console is unconfigured." Surface it
    # loudly here instead.
    owner_identity = os.environ.get("LISA_CONSOLE_OWNER_IDENTITY", "").strip()
    if not owner_identity:
        report.errors.append(
            "LISA_CONSOLE_OWNER_IDENTITY is not set -- every request will be "
            "denied (fail closed). Set it to your Tailscale-User-Login value "
            "(comma-separated if more than one identity should be allowed)."
        )
    else:
        identities = [p.strip() for p in owner_identity.split(",") if p.strip()]
        if not identities:
            report.errors.append(
                "LISA_CONSOLE_OWNER_IDENTITY is set but contains no usable "
                "identity after parsing (e.g. it's just commas/whitespace)."
            )

    # -- GPT Advisor: degrades gracefully (Phase C2), so this is a warning.
    if not os.environ.get("LISA_CONSOLE_OPENAI_API_KEY", "").strip():
        report.warnings.append(
            "LISA_CONSOLE_OPENAI_API_KEY is not set -- every Executive Brief "
            "will be degraded (status: 'degraded', category: 'credentials'). "
            "Bundles remain fully usable without it; this is a capability "
            "gap, not a broken deployment."
        )

    # -- ntfy: degrades gracefully (Phase C3), so this is a warning.
    if not os.environ.get("LISA_CONSOLE_NTFY_TOPIC", "").strip():
        report.warnings.append(
            "LISA_CONSOLE_NTFY_TOPIC is not set -- notifications will fail "
            "closed with category 'not_configured' and no network attempt. "
            "The Console remains fully usable; you just won't get pushed."
        )

    # -- Deep link base URL: cosmetic only.
    if not os.environ.get("LISA_CONSOLE_BASE_URL", "").strip():
        report.warnings.append(
            "LISA_CONSOLE_BASE_URL is not set -- ntfy notifications will "
            "omit the console_deep_link field rather than pointing back at "
            "the Console."
        )

    # -- Registry: Workers screen needs this to be non-empty and parseable.
    registry_path = registry_path or REGISTRY_PATH
    if not registry_path.is_file():
        report.errors.append(f"registry/employees.yml not found at {registry_path}")
    else:
        try:
            parsed = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            report.errors.append(f"registry/employees.yml is not valid YAML: {exc}")
        else:
            if not parsed.get("employees"):
                report.warnings.append(
                    "registry/employees.yml has no 'employees' entries -- the "
                    "Workers screen will be empty."
                )

    # -- Storage: reports/console/ must be writable (bundles/briefs/audit
    # all live there). Create-if-missing is safe -- this directory is
    # Console's own private storage, not existing LisaOS state.
    reports_console_dir = reports_console_dir or REPORTS_CONSOLE_DIR
    try:
        reports_console_dir.mkdir(parents=True, exist_ok=True)
        probe = reports_console_dir / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        report.errors.append(f"reports/console/ is not writable ({reports_console_dir}): {exc}")

    return report

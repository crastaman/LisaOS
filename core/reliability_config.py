"""Reliability boundary configuration loader (RC003 Wave 1, package A2).

Loads configs/reliability.yml, applies safe defaults for any missing key, and
layers environment overrides on top. The loader NEVER raises on a missing or
malformed file: it falls back to the built-in defaults, which are themselves
invariant-safe (reconciliation enabled, evidence.require_artifact true).

Design contract (fail-safe):
  * The defaults below are the source of truth for behaviour when the file is
    absent. They must, on their own, satisfy invariants I1/I2 (UNKNOWN
    representable; UNKNOWN never auto-retried without reconciliation).
  * Disabling reconciliation.enabled makes the gate ESCALATE, never RETRY.
  * This module performs no dispatch, no I/O beyond reading the config file,
    and holds no mutable global state a caller could corrupt.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # PyYAML is already a project dependency (registry loaders use it)
    import yaml
except Exception:  # pragma: no cover - defensive; defaults still work
    yaml = None  # type: ignore

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
DEFAULT_CONFIG_PATH = LISA_BASE / "configs" / "reliability.yml"

ENV_PREFIX = "LISA_RELIABILITY__"

# --- built-in, invariant-safe defaults ------------------------------------- #
_DEFAULTS: dict[str, Any] = {
    "reconciliation": {"enabled": True, "auto_retry_max": 1},
    "evidence": {"require_artifact": True, "liveness_grace_seconds": 30},
    "fencing": {"enabled": True, "mode": "enforce"},
    "telemetry": {"require": True},
    "session": {"warning_threshold_pct": 0.80, "reset_threshold_pct": 1.0},
    "capacity": {"provider_window_minutes": 60},
    "provider": {"queue_until_reset": False},
    "staleness_window_minutes": 120,
}


def _coerce(value: str) -> Any:
    """Coerce an env-string override into bool/int/str."""
    low = value.strip().lower()
    if low in ("true", "1", "yes", "on"):
        return True
    if low in ("false", "0", "no", "off"):
        return False
    try:
        return int(value)
    except ValueError:
        return value


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass(frozen=True)
class ReliabilityConfig:
    """Immutable view over the reliability flags. Access via helper properties."""

    data: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULTS))

    # -- reconciliation ------------------------------------------------------
    @property
    def reconciliation_enabled(self) -> bool:
        return bool(self.data.get("reconciliation", {}).get("enabled", True))

    @property
    def auto_retry_max(self) -> int:
        try:
            return int(self.data.get("reconciliation", {}).get("auto_retry_max", 1))
        except (TypeError, ValueError):
            return 1

    # -- evidence ------------------------------------------------------------
    @property
    def require_artifact(self) -> bool:
        return bool(self.data.get("evidence", {}).get("require_artifact", True))

    @property
    def liveness_grace_seconds(self) -> int:
        try:
            return int(self.data.get("evidence", {}).get("liveness_grace_seconds", 30))
        except (TypeError, ValueError):
            return 30

    # -- forward-wave flags (declared, conservative) ------------------------
    @property
    def fencing_enabled(self) -> bool:
        return bool(self.data.get("fencing", {}).get("enabled", True))

    @property
    def fencing_mode(self) -> str:
        mode = str(self.data.get("fencing", {}).get("mode", "enforce")).lower()
        return mode if mode in {"log_only", "enforce"} else "enforce"

    def session_threshold(self, name: str, default: float) -> float:
        try:
            raw = float(self.data.get("session", {}).get(name, default))
            return raw / 100.0 if raw > 1 else raw
        except (TypeError, ValueError):
            return default

    @property
    def telemetry_require(self) -> bool:
        return bool(self.data.get("telemetry", {}).get("require", True))

    @property
    def provider_window_minutes(self) -> int:
        try:
            return int(self.data.get("capacity", {}).get("provider_window_minutes", 60))
        except (TypeError, ValueError):
            return 60

    @property
    def queue_until_reset(self) -> bool:
        return bool(self.data.get("provider", {}).get("queue_until_reset", False))

    @property
    def staleness_window_minutes(self) -> int:
        try:
            return int(self.data.get("staleness_window_minutes", 120))
        except (TypeError, ValueError):
            return 120

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """LISA_RELIABILITY__SECTION__KEY=value overrides (highest precedence)."""
    for env_key, raw in os.environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue
        path = env_key[len(ENV_PREFIX):].lower().split("__")
        if not path:
            continue
        node = data
        for part in path[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                node[part] = nxt
            node = nxt
        node[path[-1]] = _coerce(raw)
    return data


def load_reliability_config(path: Path | str | None = None) -> ReliabilityConfig:
    """Load config with defaults + file + env, never raising.

    Precedence (low -> high): built-in defaults < YAML file < environment.
    A missing/malformed file yields the invariant-safe defaults.
    """
    data = dict(_DEFAULTS)
    p = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if yaml is not None and p.is_file():
        try:
            loaded = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data = _deep_merge(_DEFAULTS, loaded)
        except Exception:
            data = dict(_DEFAULTS)  # fail safe to defaults
    data = _apply_env_overrides(data)
    return ReliabilityConfig(data=data)

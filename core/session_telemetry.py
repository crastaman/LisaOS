"""Authoritative OpenClaw JSONL session-context telemetry (RC005/D1)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPENCLAW_AGENTS = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw")) / "agents"
PROVIDER_WINDOWS = {"anthropic": 200_000, "openai": 200_000,
                    "deepseek": 128_000, "glm": 128_000, "qwen": 200_000}


def provider_window(provider: str | None) -> int:
    key = str(provider or "").lower()
    return next((window for name, window in PROVIDER_WINDOWS.items() if name in key), 200_000)


def _usage(block: dict[str, Any]) -> dict[str, Any] | None:
    usage = block.get("usage")
    if not isinstance(usage, dict):
        data = block.get("data")
        usage = data.get("usage") if isinstance(data, dict) else None
    return usage if isinstance(usage, dict) else None


def session_context_usage(session_key: str, *, sessions_root: Path | None = None,
                          provider: str | None = None) -> dict[str, Any]:
    """Read the latest matching session usage; never infer liveness from it."""
    root = sessions_root or OPENCLAW_AGENTS
    latest: tuple[float, dict[str, Any]] | None = None
    for path in root.glob("*/sessions/*.jsonl") if root.is_dir() else ():
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                item = json.loads(line)
                encoded = json.dumps(item, separators=(",", ":"))
                if session_key not in encoded:
                    continue
                usage = _usage(item)
                if not usage:
                    continue
                stamp = item.get("timestamp") or item.get("ts") or path.stat().st_mtime
                try:
                    order = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
                except (TypeError, ValueError):
                    order = float(stamp) if isinstance(stamp, (int, float)) else path.stat().st_mtime
                if latest is None or order >= latest[0]:
                    latest = (order, usage)
        except (OSError, json.JSONDecodeError):
            continue
    if latest is None:
        return {"active_context": None, "cache_read": None, "total_tokens": None,
                "pct": None, "last_seen_at": None}
    usage = latest[1]
    cache = int(usage.get("cacheRead") or usage.get("cache_read") or 0)
    total_raw = usage.get("totalTokens")
    if total_raw is None:
        total_raw = usage.get("total")
    total = int(total_raw or 0)
    # OpenClaw cacheRead is cumulative cache accounting, not the current
    # context size. Prefer the real per-turn total; variants without it use
    # the actual turn components and never cacheRead.
    active = total or sum(int(usage.get(name) or 0)
                          for name in ("input", "output", "reasoningTokens"))
    window = provider_window(provider or usage.get("provider"))
    return {"active_context": active, "cache_read": cache,
            "total_tokens": total,
            "pct": min(1.0, max(0.0, active / window)),
            "context_window": window,
            "last_seen_at": datetime.fromtimestamp(latest[0], timezone.utc).isoformat()}

#!/usr/bin/env python3
"""lisa-auto-resume-check — headless state check for the cron trigger gate.

Pure deterministic check: prints {"fire": true|false, "goal": <path|none>}.
NEVER invokes MAIN/LLM. NEVER narrates polling. Fail-closed: any error
prints {"fire": false} so a broken check can never cause spurious dispatch.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.auto_resume import load_graph_state, needs_dispatch  # noqa: E402


def main() -> int:
    try:
        state = load_graph_state()
        fire = bool(state is not None and needs_dispatch(state))
        goal = (state or {}).get("goal_path", "none")
        print(json.dumps({"fire": fire, "goal": goal}))
        return 0
    except Exception as exc:  # fail-closed
        print(json.dumps({"fire": False, "goal": "none",
                          "error": str(exc)}))
        return 0


if __name__ == "__main__":
    sys.exit(main())

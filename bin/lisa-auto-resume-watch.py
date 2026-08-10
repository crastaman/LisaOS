#!/usr/bin/env python3
"""lisa-auto-resume-watch — deterministic auto-resume watcher (command payload).

Designed as the --command for an OpenClaw cron job. Runs headless: loads
persisted graph state, decides whether to re-dispatch, and re-dispatches
only when worker state has changed (HWM advanced or non-terminal packages
remain).

NEVER invokes MAIN/LLM. NEVER narrates polling output. Preserves exactly-once
semantics: a DONE mission is never re-dispatched.

Exit codes:
    0   DONE (no work needed, or dispatch completed successfully)
    3   WAKE_MAIN (escalation — cron failure alert will notify MAIN)
    2   dispatch error (cron records as error run)
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.auto_resume import (
    resume_if_needed,
    load_graph_state,
    DECISION_CONTINUE,
    DECISION_WAKE_MAIN,
    DECISION_DONE,
)

# Default goal path — overridable via LISA_MISSION_GOAL env var.
DEFAULT_GOAL_PATH = os.environ.get(
    "LISA_MISSION_GOAL",
    str(Path.home() / "Lisa" / "reports" / "lisa" / "orchestration" / "active_goal.json"),
)


def _dispatch_bin() -> str:
    return str(Path(__file__).resolve().parent / "lisa-dispatch")


def _run_dispatch(goal_path: str) -> int:
    """Run lisa-dispatch as a subprocess with --auto-resume. Returns exit code."""
    cmd = [sys.executable, _dispatch_bin(), "run", goal_path, "--auto-resume"]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=600,  # 10-minute hard cap
    )
    # Only print on non-zero exit (error path) so cron surface is silent on success.
    if result.returncode != 0:
        print(result.stderr[:2000], file=sys.stderr)
    return result.returncode


def _find_active_goal() -> str | None:
    """Discover the active mission goal path from graph state."""
    state = load_graph_state()
    if state is None:
        return None
    goal = state.get("goal_path", "")
    if goal and Path(goal).is_file():
        return goal
    return None


def main() -> int:
    goal_path = _find_active_goal()
    if goal_path is None:
        # No active mission — nothing to do.
        return 0

    decision = resume_if_needed(goal_path)

    if decision == DECISION_DONE:
        # Mission complete. Silent success.
        return 0

    if decision == DECISION_WAKE_MAIN:
        # Escalation needed — non-zero exit so cron records it as an error
        # and MAIN can pick it up via failure notification.
        state = load_graph_state()
        failed = [pid for pid, s in (state or {}).get("packages", {}).items()
                  if s in ("failed", "timed_out")]
        print(f"WAKE_MAIN: {len(failed)} failed package(s) need MAIN attention.",
              file=sys.stderr)
        return 3

    # DECISION_CONTINUE — re-dispatch
    rc = _run_dispatch(goal_path)
    return rc


if __name__ == "__main__":
    sys.exit(main())

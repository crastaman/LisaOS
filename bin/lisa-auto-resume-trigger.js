// lisa-auto-resume-trigger — headless gate for OpenClaw cron event trigger.
//
// Evaluated by the OpenClaw cron runtime BEFORE the command payload runs.
// Returns {fire: bool} — fire:true only when the mission needs another
// dispatch cycle (HWM advanced or non-terminal packages exist).
//
// NEVER invokes MAIN/LLM.  NEVER narrates polling.  Pure state check.
// Uses exactly-once semantics: a DONE mission never fires.
// Fail-closed: any check error returns fire:false.

(async () => {
  try {
    const res = await tools.call("exec", {
      command:
        "/Users/lisa/Lisa/.venv/bin/python /Users/lisa/Lisa/bin/lisa-auto-resume-check.py",
      timeout: 15,
    });

    const output = String(res?.result?.details?.aggregated ?? "").trim();
    // Take the LAST non-empty line (defensive against stray stdout noise).
    const lines = output.split("\n").map((l) => l.trim()).filter(Boolean);
    const parsed = JSON.parse(lines[lines.length - 1]);
    const fire = parsed.fire === true;

    // Persist last evaluation state for change detection across ticks.
    trigger.state = { fired: fire, goal: parsed.goal };

    json({ fire });
  } catch (e) {
    // Defensive: if the check fails, do NOT fire.
    // A broken trigger must never cause spurious dispatch.
    json({ fire: false, message: `trigger check failed: ${e}` });
  }
})();

"""GPT Advisor: Decision Bundle + GPT Context Pack -> Executive Brief.

Lisa Console v1, Phase C2. See docs/LISAOS/CONSOLE/02_GPT_ADVISOR_SPEC.md.

Advisory only, by construction, not just by instruction:
  * This module has zero imports from core/ or engines/ -- grep it
    yourself, there is nothing to invoke a dispatcher, workforce resolver,
    or any engine with. See docs/GPT_CONTEXT/09_ARCHITECTURAL_CONSTRAINTS.md.
  * It reads a Decision Bundle file with plain json.load() and never opens
    it for writing. It cannot mutate bundle state, and it never writes a
    `decision` -- that remains exclusively the Console's Safe Action Model
    (Phase C4), and even there, only Roshan's Approve/Reject click can
    populate it.
  * Its only write is a new file under reports/console/briefs/ -- a
    recommendation, never an action.

Degraded mode: if the OpenAI API is unavailable, times out, rate-limits,
returns an invalid or overflowing response, or returns an incomplete
result, generate_brief() still returns (and persists) a valid, schema-
conformant brief with status="degraded" and a null recommendation/
confidence rather than raising. The bundle it read is untouched either
way. There is no failure mode in this module that blocks the ability to
view a bundle or (once Phase C4 exists) still make an Approve/Reject
decision on it.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from advisors.context_pack import ContextPack, ContextPackError, load_context_pack
from advisors.openai_client import (
    AdvisorAPIError,
    AdvisorCredentialsError,
    call_chat_completion,
)

LISA_BASE = Path(os.environ.get("LISA_HOME", Path.home() / "Lisa"))
BUNDLES_DIR = LISA_BASE / "reports" / "console" / "bundles"
BRIEFS_DIR = LISA_BASE / "reports" / "console" / "briefs"

SCHEMA = "lisaos.console.executive_brief.v1"
EXPECTED_BUNDLE_SCHEMA = "lisaos.console.decision_bundle.v1"

_RECOMMENDATION_VALUES = {"approve", "reject", "approve_with_changes", "needs_more_info"}
_CONFIDENCE_VALUES = {"low", "medium", "high"}
_ESCALATION_LEVELS = {"none", "recommended", "urgent"}

CallFn = Callable[..., dict]


class AdvisorConfigError(Exception):
    """Raised for programming/configuration errors -- not a degraded-mode case.

    Distinct from API failures: a malformed bundle or missing context pack
    is not something a retry or a later API call fixes, so this is not
    absorbed into the degraded-brief contract the way AdvisorCredentialsError
    / AdvisorAPIError are.
    """


# --------------------------------------------------------------------------- #
# Prompt assembly
# --------------------------------------------------------------------------- #

_OUTPUT_INSTRUCTIONS = """\
You are producing one Executive Brief for the Decision Bundle given below,
as a single JSON object with exactly these keys:

  "headline": string, <=140 characters, one line.
  "summary": string, up to 6 sentences, grounded strictly in the bundle's
      evidence and proposed_actions -- do not speculate about facts the
      bundle does not contain.
  "recommendation": one of "approve", "reject", "approve_with_changes",
      "needs_more_info". This is advisory only -- you cannot approve or
      reject anything; only Roshan can, in the Console.
  "confidence": one of "low", "medium", "high".
  "key_risks": array of short strings. Empty array if none.
  "suggested_actions": array of short strings -- your own suggestions,
      distinct from the bundle's proposed_actions. Empty array if none.
  "missing_information": array of short strings describing what the bundle
      does not contain that would change your recommendation. Empty array
      if nothing is missing.
  "escalation_recommendation": an object {"level": one of "none",
      "recommended", "urgent", "reason": string or null}.

If the bundle's evidence is too thin to make a confident call, set
recommendation to "needs_more_info" and confidence to "low" rather than
guessing. Return ONLY the JSON object, no other text.
"""


def _build_user_prompt(bundle: dict[str, Any]) -> str:
    return (
        "Decision Bundle (full, self-contained -- do not request "
        "additional context):\n\n"
        + json.dumps(bundle, indent=2)
        + "\n\n"
        + _OUTPUT_INSTRUCTIONS
    )


# --------------------------------------------------------------------------- #
# Response validation (catches "partial summaries" -- a successful API call
# that returns an incomplete or malformed JSON object)
# --------------------------------------------------------------------------- #

def _validate_and_normalize(parsed: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Field-by-field validation. Returns (normalized_fields, problems).

    Problems prefixed "critical:" mean recommendation or confidence could
    not be trusted -- the caller treats that as a degraded/partial_summary
    brief. Non-critical problems (e.g. a malformed list) just fall back to
    an empty default for that one field, so a single bad field doesn't
    discard an otherwise-usable brief.
    """
    problems: list[str] = []
    out: dict[str, Any] = {}

    headline = parsed.get("headline")
    out["headline"] = headline if isinstance(headline, str) and headline.strip() else None
    if out["headline"] is None:
        problems.append("headline missing or empty")

    summary = parsed.get("summary")
    out["summary"] = summary if isinstance(summary, str) and summary.strip() else None
    if out["summary"] is None:
        problems.append("summary missing or empty")

    recommendation = parsed.get("recommendation")
    if recommendation in _RECOMMENDATION_VALUES:
        out["recommendation"] = recommendation
    else:
        out["recommendation"] = None
        problems.append(f"critical: recommendation missing or invalid ({recommendation!r})")

    confidence = parsed.get("confidence")
    if confidence in _CONFIDENCE_VALUES:
        out["confidence"] = confidence
    else:
        out["confidence"] = None
        problems.append(f"critical: confidence missing or invalid ({confidence!r})")

    for field_name in ("key_risks", "suggested_actions", "missing_information"):
        value = parsed.get(field_name)
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            out[field_name] = value
        else:
            out[field_name] = []
            problems.append(f"{field_name} missing or malformed -- defaulted to empty list")

    escalation = parsed.get("escalation_recommendation")
    if isinstance(escalation, dict) and escalation.get("level") in _ESCALATION_LEVELS:
        out["escalation_recommendation"] = {
            "level": escalation["level"],
            "reason": escalation.get("reason") if isinstance(escalation.get("reason"), str) else None,
        }
    else:
        out["escalation_recommendation"] = {"level": "none", "reason": None}
        problems.append("escalation_recommendation missing or malformed -- defaulted to 'none'")

    return out, problems


# --------------------------------------------------------------------------- #
# Brief construction
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_brief_id() -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"eb-{date}-{uuid.uuid4().hex[:8]}"


def _degraded_brief(
    bundle: dict[str, Any], *, category: str, reason: str, model: str | None, brief_id: str | None,
) -> dict[str, Any]:
    return {
        "brief_id": brief_id or _generate_brief_id(),
        "schema": SCHEMA,
        "bundle_id": bundle.get("bundle_id"),
        "bundle_schema": bundle.get("schema"),
        "created_at": _now_iso(),
        "status": "degraded",
        "model": model,
        "headline": None,
        "summary": None,
        "recommendation": None,
        "confidence": None,
        "key_risks": [],
        "suggested_actions": [],
        "missing_information": [],
        "escalation_recommendation": {"level": "none", "reason": None},
        "degraded_category": category,
        "degraded_reason": reason,
    }


def generate_brief(
    bundle: dict[str, Any],
    *,
    context_pack: ContextPack | None = None,
    model: str | None = None,
    call_fn: CallFn | None = None,
    brief_id: str | None = None,
) -> dict[str, Any]:
    """Build one Executive Brief for an already-loaded Decision Bundle dict.

    Never raises for OpenAI-side failures (credentials, unavailable,
    timeout, rate limiting, invalid/overflowing/partial responses) --
    those all produce a valid degraded brief instead. Raises
    AdvisorConfigError for a malformed bundle or missing context pack,
    since neither is fixed by degraded mode.
    """
    if not isinstance(bundle, dict) or not bundle.get("bundle_id"):
        raise AdvisorConfigError("bundle is missing or has no bundle_id")
    if bundle.get("schema") != EXPECTED_BUNDLE_SCHEMA:
        raise AdvisorConfigError(
            f"unsupported bundle schema {bundle.get('schema')!r}, expected "
            f"{EXPECTED_BUNDLE_SCHEMA!r} -- refusing rather than assuming compatibility"
        )

    call_fn = call_fn or call_chat_completion

    try:
        pack = context_pack or load_context_pack()
    except ContextPackError as exc:
        raise AdvisorConfigError(f"GPT Context Pack unavailable: {exc}") from exc

    user_prompt = _build_user_prompt(bundle)

    try:
        parsed = call_fn(system_prompt=pack.text, user_prompt=user_prompt, model=model)
    except AdvisorCredentialsError as exc:
        return _degraded_brief(bundle, category="credentials", reason=str(exc), model=model, brief_id=brief_id)
    except AdvisorAPIError as exc:
        return _degraded_brief(bundle, category=exc.category, reason=str(exc), model=model, brief_id=brief_id)

    normalized, problems = _validate_and_normalize(parsed)
    critical = [p for p in problems if p.startswith("critical:")]
    if critical:
        reason = "; ".join(problems)
        return _degraded_brief(
            bundle, category="partial_summary", reason=reason, model=model, brief_id=brief_id
        )

    brief: dict[str, Any] = {
        "brief_id": brief_id or _generate_brief_id(),
        "schema": SCHEMA,
        "bundle_id": bundle.get("bundle_id"),
        "bundle_schema": bundle.get("schema"),
        "created_at": _now_iso(),
        "status": "ok" if not problems else "degraded",
        "model": model or os.environ.get("LISA_CONSOLE_OPENAI_MODEL"),
        **normalized,
        "degraded_category": "partial_summary" if problems else None,
        "degraded_reason": "; ".join(problems) if problems else None,
    }
    return brief


# --------------------------------------------------------------------------- #
# Persistence (the only place this module writes to disk)
# --------------------------------------------------------------------------- #

def write_brief(brief: dict[str, Any], *, briefs_dir: Path | None = None) -> Path:
    """Atomically write a brief. Briefs are not immutability-enforced like
    bundles -- a retry after a degraded brief produces a new brief_id, so
    there is never a need to overwrite one.
    """
    brief_id = brief.get("brief_id")
    if not brief_id:
        raise AdvisorConfigError("brief has no brief_id -- generate_brief() first")

    target_dir = briefs_dir or BRIEFS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = target_dir / f"{brief_id}.json.tmp"
    final_path = target_dir / f"{brief_id}.json"
    tmp_path.write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, final_path)
    return final_path


def generate_and_write_brief(
    bundle: dict[str, Any],
    *,
    briefs_dir: Path | None = None,
    **generate_kwargs: Any,
) -> Path:
    brief = generate_brief(bundle, **generate_kwargs)
    return write_brief(brief, briefs_dir=briefs_dir)


def generate_brief_for_bundle_id(
    bundle_id: str,
    *,
    bundles_dir: Path | None = None,
    briefs_dir: Path | None = None,
    **generate_kwargs: Any,
) -> Path:
    """Read-only bundle load by bundle_id, then generate + write a brief.

    Reads reports/console/bundles/<bundle_id>/bundle.json with plain
    json.load() -- never opened for writing, never touched by this module
    beyond reading.
    """
    bundle_path = (bundles_dir or BUNDLES_DIR) / bundle_id / "bundle.json"
    if not bundle_path.is_file():
        raise AdvisorConfigError(f"no such bundle: {bundle_path}")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    return generate_and_write_brief(bundle, briefs_dir=briefs_dir, **generate_kwargs)

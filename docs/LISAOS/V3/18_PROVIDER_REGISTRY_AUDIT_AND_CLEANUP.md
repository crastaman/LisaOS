# Provider Registry Audit, Cleanup & Integrity Validation

**Status:** VALIDATION ARTIFACT + executed cleanup. 2026-07-07.
**Scope:** `registry/provider_resolution.yml` + `tests/test_provider_resolution.py`. **The live `~/.openclaw/openclaw.json` was NOT mutated** (deferred to Phase 0 — see §6).

Covers deliverables **Provider Registry Audit**, **Registry Cleanup Report**, and **Workforce Integrity Validation**.

---

## 1. What was audited

The LisaOS provider registry (`registry/provider_resolution.yml`) — the machine-readable source of truth that turns a logical provider name into a physical OpenClaw model + runtime for the spawn payload. Audited against the live inventory (`16`) and the integrity criteria in the brief.

## 2. Cleanup executed (this validation)

### 2.1 Removed the Alibaba / Qwen provider
`qwen-alibaba` (`codex-model-studio/qwen3.7-plus`) and **all** its aliases (`alibaba-qwen`, `qwen-modelstudio`, `ali-qwen`) were **deleted** from the registry. It is not part of the approved workforce (403-prone CN endpoint; provider mis-named "codex-model-studio").

### 2.2 Eliminated the Codex/Qwen naming ambiguity
With `qwen-alibaba` gone, **no registry entry references `codex-model-studio`**. Therefore `codex` now unambiguously resolves to OpenAI:
```
codex  ->  openai/gpt-5.5   (runtime: codex, provider_id: openai)   [verified live]
```
The only path that ever attached "codex" to a Qwen backend is removed.

### 2.3 Updated the disambiguation rule
The header comment now states there is exactly **one approved Qwen** (`qwen-deepinfra`) and records the removal + rationale, pointing to `15` and this document.

### 2.4 Diff summary
```
registry/provider_resolution.yml
  - qwen-alibaba: (block removed, incl. codex-model-studio/qwen3.7-plus + 3 aliases)
  ~ DISAMBIGUATION RULE comment: two-Qwen -> single-approved-Qwen + cleanup note

tests/test_provider_resolution.py
  - make_config(): qwen-alibaba fixture removed; codex fixture added
  ~ test_qwen_alibaba_is_distinct_backend  -> test_qwen_alibaba_is_removed
  ~ test_two_qwens_never_conflate          -> test_single_qwen_backend_only
  + test_no_registry_entry_references_codex_model_studio
  + test_codex_is_openai_not_qwen
  + test_shipped_registry_has_no_alibaba_and_no_codex_model_studio
  ~ fallback mechanism test retargeted qwen-alibaba -> claude-sonnet
```

## 3. Post-cleanup registry (approved workforce providers only)

`python3 bin/lisa-resolve providers` against the **real** `~/.openclaw` config:

| logical | physical model | runtime | availability |
|---|---|---|---|
| `deepseek` | custom-api-deepseek-com/deepseek-reasoner | openclaw | AVAILABLE |
| `claude-opus` | anthropic/claude-opus-4-8 | claude-cli | AVAILABLE |
| `claude-sonnet` | anthropic/claude-sonnet-4-6 | claude-cli | AVAILABLE |
| `codex` | openai/gpt-5.5 | codex | AVAILABLE |
| `gpt` | openai/gpt-5.5 | openclaw | AVAILABLE |
| `qwen-deepinfra` | deepinfra/Qwen/Qwen3.6-35B-A3B | openclaw | AVAILABLE |

Six providers, all approved, all AVAILABLE. No Alibaba. No legacy entries.

## 4. Workforce Integrity Validation

Each integrity criterion from the brief, checked with evidence:

| Criterion | Method | Result |
|---|---|---|
| **No duplicate providers** | Each logical name unique; each `physical_model`/`provider_id` inspected | ✅ `gpt` and `codex` share model `openai/gpt-5.5` but differ by **runtime** (openclaw vs codex) — intentional, not a duplicate. All others distinct. |
| **No conflicting aliases** | Every alias maps to exactly one canonical provider; `normalise()` deterministic | ✅ No alias resolves to >1 backend; bare `qwen` → None; stale Alibaba aliases → None (verified via CLI). |
| **No incorrect model identities** | `codex` provider_id, live resolve | ✅ `codex` → provider `openai`, model `openai/gpt-5.5` (not Qwen). `test_codex_is_openai_not_qwen` passes. |
| **No silent fallbacks** | `fallback_policy.enabled: false`; unknown/unavailable → error, exit 2 | ✅ `qwen-alibaba`, `ali-qwen`, unknown names all raise `unknown_provider` (exit 2), never substitute DeepSeek. |
| **No orphaned employee mappings** | Cross-check `02` employees vs registry providers | ✅ No employee referenced `qwen-alibaba`; all employee `preferred`/`fallback` models exist in the inventory. |
| **No inactive providers referenced by Dispatcher policies** | Dispatcher is not yet implemented; modes (`08`) reference only approved providers + probation-flagged GLM | ✅ No mode/policy references the removed Alibaba provider. |
| **No stale aliases in registry** | grep + CLI resolve of every removed alias | ✅ `alibaba-qwen`/`qwen-modelstudio`/`ali-qwen`/`qwen-alibaba` all unknown. |

## 5. Test evidence

```
PYTHONPATH="$HOME/Lisa" python3 -m unittest tests.test_provider_resolution -v
...
Ran 23 tests in 0.009s

OK
```

**23/23 pass** (was 20; +3 net for the cleanup assertions). Key new/updated cases:
- `test_qwen_alibaba_is_removed` — qwen-alibaba + all 3 aliases → `unknown_provider`.
- `test_single_qwen_backend_only` — the only qwen-* provider is `qwen-deepinfra`.
- `test_no_registry_entry_references_codex_model_studio` — nothing references the mis-named provider.
- `test_codex_is_openai_not_qwen` — Codex identity is OpenAI.
- `test_shipped_registry_has_no_alibaba_and_no_codex_model_studio` — asserts the above on the **real shipped YAML**.

Live CLI confirmation:
```
$ bin/lisa-resolve resolve codex          -> openai/gpt-5.5, provider_id: openai   (exit 0)
$ bin/lisa-resolve resolve qwen-alibaba   -> unknown_provider                       (exit 2)
$ bin/lisa-resolve resolve ali-qwen       -> unknown_provider                       (exit 2)
```

## 6. Deferred to Phase 0 (live-system changes, NOT done here)

The **repo** registry is clean. Two changes to the **live OpenClaw install** remain, because they mutate the running system and require approval (consistent with "do not proceed to implementation"):

| Action | Where | Phase 0 task |
|---|---|---|
| Remove/disable the `codex-model-studio` provider block; rename to `alibaba-model-studio` if retained for reference | `~/.openclaw/openclaw.json` | 0.3 |
| Repoint or delete the OpenClaw `qwen` alias (currently → `codex-model-studio/qwen3.7-plus`) so bare `qwen` never means Alibaba | OpenClaw aliases | 0.2 |
| Fix/remove the corrupt native `deepseek:default` auth key | `~/.openclaw` auth store | 0.7 |

Until these land, LisaOS is already protected: its registry never emits the Alibaba backend and fails closed on its aliases. The live changes remove the ambiguity at the OpenClaw layer too.

## 7. Conclusion

The provider registry is **clean, unambiguous, and integrity-validated**: six approved providers, one approved Qwen, Codex unambiguously OpenAI, no stale aliases, no silent fallbacks, no orphaned mappings, 23/23 tests green. The workforce can begin from a verified foundation. The remaining Alibaba/DeepSeek-credential cleanup at the live OpenClaw layer is captured as explicit Phase 0 tasks.

# LisaOS Token Efficiency Guide

**Job ID:** L005-L007-LISAOS-ORCHESTRATION-DESIGN-STUDY  
**Repository:** `~/Lisa`  
**Scope:** Token efficiency best practices derived from WBS development lessons.  
**Runtime behaviour:** Unchanged. Documentation only.

---

## 1. Purpose

This guide captures practical token-efficiency patterns learned during WBS development and formalises them for LisaOS operations. Following these practices reduces costs, improves latency, and increases output quality.

---

## 2. Token Economics

### 2.1 What Tokes Cost

| Runtime | Approximate Cost per 1M Input Tokens | Cost per 1M Output Tokens |
|---------|--------------------------------------|---------------------------|
| GPT-5 | ~$10-15 | ~$40-60 |
| Claude Sonnet 4 | ~$3-5 | ~$15-25 |
| Claude Opus 4 | ~$15-25 | ~$75-125 |
| DeepSeek R1 | ~$0.25-1 | ~$1-4 |
| Codex | ~$10-15 | ~$40-60 |
| Ollama (local) | ~$0 | ~$0 |

**Lesson:** A single inefficient session with a premium model can cost as much as 50+ efficient sessions with a budget model. Token efficiency is a cost multiplier.

### 2.2 Where Tokes Go

Analysis of typical engineering sessions:

| Activity | Share of Tokens | Can Be Reduced? |
|----------|----------------|-----------------|
| Reading files into context | 40-60% | Yes — selective reading, reference-only |
| Conversation history (turns) | 20-30% | Yes — fresh sessions, shorter threads |
| System prompts and agent identity | 5-10% | Yes — compact identity files |
| Tool outputs | 10-20% | Yes — suppress verbose output |
| Generated code output | 5-15% | Yes — targeted changes only |
| Error output | 1-5% | Yes — capture to files |

**The 80/20 rule:** Reading files and maintaining conversation history account for ~70% of all token consumption.

---

## 3. Core Practices

### 3.1 Practice 1: Read Once, Reference by Path

**Problem:** Every time context is loaded, the same files are re-read, costing tokens for repeated content.

**Solution:**
- First read: include the file's content in context.
- Subsequent references: use the file path, not the contents.
- The agent's prompt should teach: "If you already read a file, reference it by path. Do not re-read its contents."

**Example:**
```yaml
# Bad — costs 12K tokens for the same file again
context: "The current KERNEL.md says: <full 12K content>"

# Good — costs ~50 tokens
context: "See docs/LISAOS/KERNEL.md (already loaded in previous session. Re-read only if changed.)"
```

**Savings:** ~12K tokens per repeated reference.

### 3.2 Practice 2: Keep Agent Identity Compact

**Problem:** Agent identity files (IDENTITY.md, SOUL.md) are loaded into every session, consuming budget.

**Solution:**
- Keep identity files under 2K tokens total.
- Distill core instructions; remove explanations and examples.
- Move verbose instructions to job-packet context, not agent identity.

**Compact identity example (IDENTITY.md — ~300 tokens):**
```markdown
# Identity: Planner Agent
- Role: Decompose jobs, define scope, preserve boundaries.
- Constraint: No runtime decisions. No capacity changes.
- Output: Job packet with required_capabilities and context_file list.
- Rule: Always verify repository boundary before defining scope.
```

**Verbose identity (~1500 tokens) replaced:**
```markdown
# Identity: Planner Agent
(15 paragraphs of exposition, examples, historical context removed.)
```

**Savings:** ~1200 tokens per session.

### 3.3 Practice 3: Use Fresh Sessions Per Job

**Problem:** Long-running sessions accumulate conversational history, passive-aggressive back-and-forth, and tool output noise — each turn adds 500-2000 tokens.

**Solution:**
- Start a fresh session for every job.
- End the session when the job completes.
- Do not let agents "stick around" for follow-ups.

**Evidence from WBS:**
```
Sessions with 30+ turns: average 45K tokens, $0.45-2.25/session
Fresh sessions per job: average 8K-15K tokens, $0.08-0.75/session
```

**Savings:** 3-5x token reduction per job.

### 3.4 Practice 4: Selective Inclusion Over Full Files

**Problem:** Loading a 15K-token document when only one section (500 tokens) is relevant.

**Solution:**
- Include only relevant sections in context.
- Reference the full document by path for supplementary reading.
- The Context Loader should implement selective inclusion.

**Example:**
```yaml
# Bad — dump full 15K document
context_includes: [docs/LISAOS/KERNEL.md]

# Good — include only the relevant 500 tokens
context_includes:
  - docs/LISAOS/KERNEL.md#3.5-runtime-resolver  # 500 tokens
  - docs/LISAOS/KERNEL.md#3.6-agent-dispatcher  # 400 tokens
  - # rest available on request: "Full doc at docs/LISAOS/KERNEL.md"
```

**Savings:** ~14K tokens per large document reference.

### 3.5 Practice 5: Suppress Verbose Tool Output

**Problem:** Tool outputs (test results, file listings, error stacks) consume significant tokens.

**Solution:**
- Capture tool output to files, not to the conversation.
- Only include the summary or relevant lines in context.
- Configure agents to suppress verbose output by default.

```yaml
# Bad — 15K tokens of test output in conversation
---
Ran 127 tests: 124 passed, 3 failed.
  test_create_appointment: FAIL
  ... 200 lines of stack trace ...
  test_cancel_appointment: FAIL
  ... 150 lines of stack trace ...
  test_reschedule: FAIL
  ... 180 lines of stack trace ...

# Good — 600 tokens of summary in conversation, full output in file
---
Test results: 124/127 passed. 3 failures captured to output/test-failures.log
Failures: test_create_appointment, test_cancel_appointment, test_reschedule
Investigation: check output/test-failures.log for full trace
```

**Savings:** ~14K tokens per test run.

### 3.6 Practice 6: Use Structured Data Over Prose

**Problem:** Paragraphs describing decisions are 3-5x more token-heavy than structured data.

**Solution:**
- Use YAML for decisions, reports, and summaries.
- Use tables for comparisons and trade-offs.
- Use bullet points for lists.
- Avoid explaining things that can be expressed as facts.

**Example:**
```markdown
# Bad — 280 tokens of prose
"After careful consideration of the runtime options, we decided to use Codex for the implementation phase. Codex was chosen because it provides the best balance of cost and capability for this specific engineering task. The runner-up was Claude, which has similar capabilities but at a higher cost. DeepSeek was also considered but lacks the repository_write capability needed for this job."

# Good — 70 tokens, more precise
runtime_selection:
  chosen: codex
  rationale: "Best capability/cost balance for implementation"
  runner_up: claude
  excluded: deepseek  # missing repository_write
```

**Savings:** ~75% token reduction for common decision recording.

### 3.7 Practice 7: Compress Conversation History

**Problem:** Full conversation history can exceed 20K tokens for a moderate session.

**Solution:**
- Summarise conversation history at session boundaries.
- The summary should capture: decisions made, questions answered, dead ends explored.
- The raw conversation is discarded; the summary carries forward.

**Summary format (max 1K tokens):**
```yaml
conversation_summary:
  session_type: job_execution
  duration_minutes: 12
  total_turns: 8
  
  decisions:
    - "Split Practitioner model into Practitioner + PractitionerProfile"
    - "Defer address migration to follow-up job"
  
  resolved_questions:
    - "PractitionerProfile nullable? → Yes, for backward compatibility"
  
  unresolved:
    - "Should we rename Practitioner → Provider for domain consistency?"
  
  dead_ends:
    - "Approach: Single-table inheritance → Rejected: query complexity too high"
  
  key_files_changed:
    - src/Models/Practitioner.php
    - src/Models/PractitionerProfile.php
  
  state: "Implementation 80% complete. Migration class written but untested."
  next_steps: ["Write test for PractitionerProfile model", "Run migration dry-run"]
```

**Savings:** 80-95% reduction in conversation context size.

### 3.8 Practice 8: Batch Small Changes

**Problem:** Multiple small jobs each trigger full context loading, wasting tokens on repeated overhead.

**Solution:**
- Batch small, related changes into a single job packet.
- Splitting criteria: unrelated changes → separate jobs. Related changes → batch.
- Batch size limit: 5 files or 3 functional changes per batch.

**Example:**
```yaml
# Bad — 4 jobs, each loading full context (12K × 4 = 48K tokens)
jobs:
  - "Fix typo in Practitioner model"
  - "Update Practitioner model PHPDoc"
  - "Add validation rule to Practitioner model"
  - "Update Practitioner model test"

# Good — 1 job, loading context once (12K tokens)
job: "Batch improvements to Practitioner model"
changes:
  - "Fix typo in Practitioner model (line 42: 'adress' → 'address')"
  - "Update PHPDoc for getFullName() to document return type"
  - "Add validation rule: practitioner email must be unique"
  - "Update test assertions to match new validation rule"
```

**Savings:** 4x reduction in context loading overhead.

---

## 4. Job Type Token Profiling

| Job Type | Median Tokens | Token Distribution | Cost Impact |
|----------|--------------|-------------------|-------------|
| Typo fix (single file) | 4K-8K | 2K context, 2K-6K session | Negligible |
| Simple doc update | 6K-12K | 4K context, 2K-8K session | Negligible |
| Single feature (1-2 files) | 20K-40K | 12K context, 8K-28K execution | Low |
| Multi-file change (3-5 files) | 40K-80K | 20K context, 20K-60K execution | Medium |
| Architecture analysis | 80K-150K | 64K context, 16K-86K reasoning | High |
| Large refactoring | 100K-200K | 48K context, 52K-152K execution | High |

**Takeaway:** Context is the fixed cost. Execution is the variable cost. Optimising context saves across all job types.

---

## 5. Token Budget Calculation

### 5.1 Estimating Tokens

Use these heuristics for quick estimation:

| Content Type | Tokens Per Unit |
|-------------|----------------|
| English prose | ~1.3 tokens per word |
| Code (PHP) | ~2.5 tokens per LOC |
| Code (JS) | ~2.0 tokens per LOC |
| YAML/structured | ~1.0 tokens per line |
| Markdown (with formatting) | ~1.5 tokens per word |
| Long base64 output | ~0.75 tokens per character |

### 5.2 Budget Template

```
Job: <job-type>
Context budget: <budget> tokens

Context allocation:
  Agent identity:      ~2K  (compact IDENTITY.md + SOUL.md)
  Job packet:          X tokens (full packet)
  Target files:        X tokens (selective, relevant sections only)
  Architecture docs:   X tokens (selective sections)
  Policy injection:    X tokens (for templates)
  Conversation sum.:   X tokens (summary, 0 for fresh jobs)
  Reserved for agent:  X tokens (20% of total)
  ─────────────────────
  Total:              ≤ budget

Overhead:  tool outputs, agent scratch, response generation
Estimated total consumption: budget + overhead (typically +10-20%)
```

---

## 6. Measurement and Tracking

### 6.1 What to Track

| Metric | How | Frequency |
|--------|-----|-----------|
| Tokens per job | From audit log | Per-job |
| Tokens per job type | Aggregate from audit log | Weekly |
| Cost per job | Token count × runtime cost | Per-job |
| Cost per job type | Aggregate | Weekly |
| Context efficiency | Context tokens / total tokens | Per-job |
| Peak session tokens | Maximum session length | Per-session |

### 6.2 Budget Alerts

| Condition | Alert Level | Action |
|-----------|-------------|--------|
| Job exceeds budget by >20% | Warning | Log in governance audit |
| Job exceeds budget by >50% | Flag | Review context assembly for efficiency |
| Weekly cost exceeds threshold | Alert | Review runtime selection and job batching |
| Repeated context waste pattern | Investigation | Update Context Loader rules |

---

## 7. Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Better Approach |
|-------------|-------------|-----------------|
| Loading entire project tree into context | Token explosion for marginal gain | Selective loading of relevant files only |
| Re-reading files on every turn | Repeat token consumption on same content | Reference by path after first read |
| Long debugging sessions in main context | Massive token waste from back-and-forth | Isolate debugging to a separate spike job |
| Including full test output in approval packet | Tokens wasted on human-stressful detail | Summary only; full output in artifact file |
| Loading conversation history for new jobs | Carries irrelevant noise into fresh context | Use artifact summaries, not raw transcripts |
| Chat-based specification before job creation | Creates long context that the job must include | Put specification in the job packet directly |
| Agent re-reads its own identity in every turn | Agent identity is already in context; re-reading wastes tokens | Identity is loaded once at session start |

---

## Related Documents

- `docs/LISAOS/LISAOS_CONTEXT_MANAGEMENT.md` — Context budgets, assembly, compaction
- `docs/LISAOS/LISAOS_ARTIFACT_LIFECYCLE.md` — Artifact-driven workflows
- `docs/LISAOS/L007_OPENCLAW_ORCHESTRATION_ARCHITECTURE.md` — Session rotation, fresh sessions
- `docs/LISAOS/KERNEL.md` — Context Loader architecture

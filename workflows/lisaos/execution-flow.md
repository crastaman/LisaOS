# LisaOS Execution Flow

**Sprint:** L003-LISAOS-RUNTIME-EXECUTION-FRAMEWORK  
**Status:** Documentation-only foundation

This document defines the minimal future execution path for LisaOS jobs.

## Flow

```text
Job
↓
Job Type
↓
Default Agent
↓
Required Capabilities
↓
Runtime Profile
↓
Fallback Runtime
↓
Validation
↓
Approval
```

## Step definitions

### 1. Job

A job begins as a job packet matching `jobs/schema.yml`.

### 2. Job Type

`job_type` maps to `registry/jobs.yml`.

The job type provides default agent, required capabilities, validation requirement, approval requirement, and expected output artifacts.

### 3. Default Agent

The default agent comes from the job type unless `preferred_agent` is present and allowed by policy.

Agent definitions come from `registry/agents.yml` and the L002 agent framework under `agents/`.

### 4. Required Capabilities

Required capabilities come from both the job packet and registry defaults.

Capability metadata comes from `registry/capabilities.yml`.

### 5. Runtime Profile

The selected agent provides a `runtime_profile`.

Runtime profile is an abstract role such as `planning-runtime`, `review-runtime`, `implementation-runtime`, or `governance-runtime`.

### 6. Fallback Runtime

Fallback runtimes are read from `registry/agents.yml` and candidate runtime metadata comes from `registry/runtimes.yml`.

### 7. Validation

Validation is required when requested by the job packet or job type.

Validation should produce evidence before completion.

### 8. Approval

Approval is required when requested by the job packet, job type, policy, or restricted capability.

Approval gates must not be bypassed by future automation.

## L003 limitations

This flow is descriptive only. It does not implement queue processing, dispatch, model calls, provider calls, scheduling, memory writes, Telegram integration, cloud execution, or OpenClaw runtime changes.

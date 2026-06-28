# Lisa and OpenClaw Integration

## Purpose

LisaOS separates planning and governance from operational execution.

Lisa is the planner and governance layer.

OpenClaw is the operations runtime.

This boundary keeps Lisa responsible for intent, routing, policy, and architectural integrity while allowing OpenClaw to execute jobs through operational primitives such as Cron, Tasks, Skills, Nodes, and Playwright QA.

## Lisa Responsibilities

Lisa owns:

- User intent interpretation
- Capability matching
- Planning
- Governance and approval policy
- Engine routing
- Architecture decisions
- Reporting requirements
- Result interpretation
- Knowledge preservation

Lisa decides what should happen, why it should happen, which constraints apply, and which runtime or engine should receive the work.

## OpenClaw Responsibilities

OpenClaw owns operational execution assigned by Lisa.

OpenClaw may run:

- Cron-based recurring jobs
- Task workflows
- Skill-driven operational procedures
- Node-based workflow steps
- Playwright browser QA
- Local site checks
- Screenshot capture
- Workflow execution
- Runtime evidence collection

OpenClaw executes the assigned job and returns structured evidence to Lisa.

## Integration Boundary

Lisa sends OpenClaw an operational job when the required capability involves runtime execution rather than planning.

Examples:

- Run a Playwright QA suite against a LocalWP site
- Capture screenshots for a test failure
- Execute a scheduled health check
- Run an approved operational task workflow
- Coordinate node-based runtime steps

OpenClaw returns:

- PASS / FAIL status
- Commands or workflow steps run
- Logs and console errors
- Screenshot, video, or trace paths when available
- Operational findings
- Recommended next action

Lisa remains responsible for deciding whether the evidence satisfies the original goal.

## Non-Goals

OpenClaw does not:

- Decide product direction
- Override Lisa governance
- Change architecture policy
- Publicly expose local services without approval
- Perform destructive actions unless the Lisa-assigned job explicitly allows them

Lisa does not:

- Replace OpenClaw operational primitives
- Directly own browser runtime execution
- Treat OpenClaw as an architecture authority

## Routing Principle

Lisa routes by capability.

When the capability is planning, governance, architecture, or strategy, Lisa keeps the work in the planning layer or routes it to an appropriate reasoning engine.

When the capability is operational execution, Lisa may assign the job to OpenClaw.

OpenClaw is therefore not a peer planner to Lisa. It is the runtime Lisa uses for repeatable operational work.

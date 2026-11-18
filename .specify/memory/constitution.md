<!--
SYNC IMPACT REPORT
==================
Version change: template scaffold (unratified) -> 1.0.0
Ratification: initial adoption on 2026-11-18; replaces the unmodified Spec Kit template,
which contained no project-specific governance.

Modified principles:
  - Template placeholders PRINCIPLE_1 through PRINCIPLE_5 -> I. Build From Primitives,
    II. Provider-Agnostic Model Boundary, III. Small Modules With Narrow Contracts,
    IV. Observable by Default, V. Eval-Driven Behavior Change (NON-NEGOTIABLE)

Added sections:
  - Core Principles (five principles, all newly defined)
  - Additional Constraints
  - Development Workflow

Removed sections: none (no prior project-specific content existed)

Deferred TODOs: none. Language and runtime are intentionally undecided; /speckit-plan must
record the chosen stack in plan.md.

Follow-up: this report is scratch material for human review and SHOULD be deleted before the
amendment is committed.
-->

# BYO Agent Constitution

## Core Principles

### I. Build From Primitives

The agent is built, not configured. The control loop, tool dispatch, context assembly, and
memory MUST be implemented as source in this repository.

- The control loop (model call, tool execution, context update, repeat) MUST be written
  here. Agent frameworks and orchestration libraries (LangGraph, LlamaIndex agents, the
  OpenAI Agents SDK, CrewAI, or equivalent) MUST NOT own control flow.
- Every behavior MUST be reachable by reading repository source: a maintainer can trace one
  user message from input to final answer without entering an opaque dependency.
- Third-party libraries MAY serve leaf utilities (HTTP, JSON/schema validation, token
  counting, CLI parsing) but MUST NOT perform model calls or tool execution on the agent's
  behalf.
- Each subsystem MUST carry a short design note stating what mechanism it implements and
  which alternatives were rejected.

Rationale: the project's purpose is to make each agent mechanism visible and teachable; a
framework dependency converts the exercise into configuration.

Verification: the dependency list contains no agent-orchestration framework, and a reviewer
can walk one message end-to-end using source alone.

### II. Provider-Agnostic Model Boundary

- All model access MUST go through a single in-repo adapter interface. Provider SDKs and
  HTTP details MUST NOT appear outside adapters.
- The core MUST run and pass its test suite against a fake model adapter with no network
  access and no credentials.
- The adapter contract MUST express every capability the core relies on (tool-call output,
  structured output, streaming, token usage, stop reasons) as capability flags or typed
  errors. Core code MUST branch on capabilities, never on vendor identity.
- Adding a provider MUST require only a new adapter plus its conformance tests: no changes
  to loop, tools, or context logic.

Rationale: a stable seam keeps the core testable offline and prevents vendor lock-in.

Verification: swapping the real adapter for a fake changes no file outside the adapter
package.

### III. Small Modules With Narrow Contracts

- Each concern (loop, model adapter, tool registry, context builder, memory, trace sink,
  configuration) MUST be its own module with an explicit, documented, typed interface.
- Modules MUST be independently testable without network access, credentials, or child
  processes. A module that cannot be tested alone has the wrong boundary.
- Dependencies MUST point inward: pure domain logic depends on nothing infrastructural, and
  infrastructure depends on domain interfaces.
- Behavior MUST live in the module that owns the concern. A module accumulating
  cross-cutting responsibilities MUST be split rather than extended.
- Public contracts MUST be documented at the seam, and changing one is a deliberate,
  reviewed decision rather than an incidental edit.

Rationale: narrow seams are what make an agent debuggable, replaceable, and reviewable one
piece at a time.

Verification: each module has a test file that imports it in isolation, and review can name
the owner of any new behavior.

### IV. Observable by Default

- Every run MUST emit a structured event trace covering run start and end, each model
  request and response with token usage and latency, each tool call with arguments, outcome,
  and duration, and every context or memory mutation.
- Trace records MUST be machine-readable (JSON Lines) and MUST support replay: a captured
  trace alone is enough to reconstruct and inspect what the agent did.
- Tracing MUST be enabled by default in development and configurable, not compiled out, in
  production.
- Secret redaction MUST be enforced at the trace sink boundary so no caller can leak
  credentials into a trace.
- A behavior bug report MUST include the trace that reproduces it.

Rationale: agent defects are trajectory defects; without a trace, debugging is guessing.

Verification: one command renders a human-readable timeline for a recorded run, and
redaction tests prove no secret reaches the sink.

### V. Eval-Driven Behavior Change (NON-NEGOTIABLE)

- No change to prompts, tool descriptions, loop logic, context strategy, or memory policy
  may merge without an eval that measures it.
- Every such change MUST report the baseline score, the post-change score, and the specific
  cases that moved, alongside the diff.
- A golden set of recorded trajectories MUST exist and MUST grow with every fixed behavior
  bug; each fixed bug adds a regression case.
- Evals MUST run offline against fake or recorded models in the default test path. Live-model
  evals are opt-in, cost-bounded, and MUST NOT be required for the main suite to pass.
- A change that lowers eval scores MUST be justified in writing or reverted.

Rationale: prompts and loop logic are code; without measurement, quality regressions ship
silently.

Verification: the review checklist requires an eval delta for behavior-touching diffs.

## Additional Constraints

- **Stack neutrality.** This constitution deliberately names no language or runtime. The
  stack is selected during /speckit-plan and recorded in plan.md; changing it later is a
  documented plan-level decision, not a constitutional amendment.
- **Dependency budget.** Runtime dependencies MUST stay minimal. Each new dependency MUST be
  justified in plan.md by what it replaces and why in-repo code is not preferred. No
  dependency may own control flow, tool execution, or the model boundary.
- **Offline-first testing.** The default test command MUST pass with no network access and
  no credentials.
- **Configuration over hardcoding.** Model choice, temperature, step limits, tool
  enablement, and trace destination MUST be configuration, not literals embedded in code
  paths.
- **Secrets.** Credentials MUST come from the environment or a secret store and MUST NOT
  appear in source, fixtures, committed traces, or logs.
- **Documentation duty.** Each subsystem's design note MUST state what the subsystem does,
  its contract, and at least one rejected alternative, keeping the "why" next to the "how".

## Development Workflow

- **Spec before code.** Non-trivial features follow /speckit-specify, then /speckit-clarify
  when underspecified, then /speckit-plan, /speckit-tasks, and /speckit-implement. No
  implementation starts before spec.md and tasks.md exist.
- **Test-first for logic.** Loop, tool dispatch, context assembly, and policy logic MUST be
  written test-first: red, then green, then refactor.
- **Vertical slices.** Each feature lands as a runnable end-to-end increment: the new
  behavior can be exercised with a real or fake model at the end of the slice.
- **Review gates.** A change is reviewable only when it includes tests, an eval delta for
  behavior-touching diffs, and, where relevant, a sample trace.
- **Constitution check.** Every plan.md MUST include a Constitution Check gate against
  Principles I through V. Any violation is recorded in the plan's Complexity Tracking table
  with the simpler alternative rejected and its cost.
- **Justify complexity.** Additional abstraction MUST pay for itself now; speculative
  generality is a defect, not foresight.

## Governance

- This constitution supersedes ad-hoc practice and MUST be honored by plans, tasks, and
  reviews. Where guidance conflicts, this document wins.
- **Amendments** require a pull request that edits this file, states the motivation and the
  affected principles, and carries a Sync Impact Report. The report is reviewed and removed
  before merge.
- **Versioning** is semantic: MAJOR for removing or redefining a principle or governance
  rule; MINOR for a new principle or materially expanded guidance; PATCH for clarification
  and wording only.
- **Compliance review.** Every plan and every review verifies the change against the
  principles; unjustified violations block merge. Repeated violations signal that an
  amendment, not an exception, is needed.
- **Runtime guidance.** plan.md, tasks.md, and the per-subsystem design notes carry
  implementation detail; this document stays principle-level.

**Version**: 1.0.0 | **Ratified**: 2026-11-18 | **Last Amended**: 2026-11-18

# Feature Specification: Waku-Parity Minimal Agent Core

**Feature Branch**: `n/a — repository has no version control yet`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "保留waku-agent最少可用的模块 ~/Projects/Private/waku-agent，技术栈一致，执行过程可视化一致"

**Reference**: The parity source is the read-only checkout at `~/Projects/Private/waku-agent`
(referred to below as "the reference"). It is input to this feature, never a target of change.

**Terminology**: this project calls the per-turn event log a *trajectory*. The reference calls the
same artifact a *trace*; the schema is shared, the name is ours.

## Clarifications

### Session 2026-11-18

- Q: Should SKILL.md packs and the skill marketplace be retired, leaving procedural memory as the persona/preferences file? → A: Yes — retire both; procedural memory is the persona file only.
- Q: Should judge-scored evals and the model/memory/judgment arenas be retired, leaving deterministic offline evals plus the release gate as the bar? → A: Yes — retire them; deterministic suite plus release gate only.
- Q: Should the tool set be fixed at the six tools in FR-017, with web search, MCP servers and the external calendar/ecosystem integrations retired? → A: Yes — exactly those six ship enabled.
- Q: Should the rebuild keep the reference's on-disk and configuration names (its variable prefix, home directory and persona file name), or use its own names and keep only structure and contracts in common? → A: Its own names; no migration entry point from an existing reference installation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A working agent in the terminal (Priority: P1)

A person installs the package, puts one model-provider key in the environment, and starts
the chat command. They ask for something that cannot be answered without acting — "book a
catch-up with Alex on Friday" — and the assistant resolves the date, creates the event, and
answers with the time it booked and where it recorded it. While the turn runs, every step
the assistant takes is printed as it happens rather than held back until the end.

**Why this priority**: The loop, the tool dispatch and the terminal chat *are* the product.
Everything else in this specification exists to make that turn visible, remembered or
provable; none of it is worth building if the turn itself does not work.

**Independent Test**: With a scripted model (offline, no credentials), a turn that requests
one tool, receives its result and answers produces the expected reply, the expected stored
artifact, and one printed line per step.

**Acceptance Scenarios**:

1. **Given** a clean home directory and one provider key, **When** the person starts the agent and asks to book a meeting, **Then** the event is stored and the reply names the meeting time and the place it was recorded.
2. **Given** the model asks for a tool, **When** that tool runs, **Then** the response prints the tool name, its arguments and a preview of the result before the final reply.
3. **Given** the model keeps asking for tools, **When** it reaches the step limit, **Then** the turn ends with a single answer that says what is missing and that the limit was reached.
4. **Given** a tool raises an error, **When** the model reads the result, **Then** the turn continues and the error text reaches the model, not the person's screen as a crash.

---

### User Story 2 - The same turn, watchable in the browser (Priority: P2)

The person starts the dashboard command, sends the same request in the browser, and watches
the turn assemble live: the memory-gate decision, each loop iteration, each tool call with
its duration, the reply streaming in word by word, and finally a receipt with what the turn
cost. Afterwards, the observability view shows the same turn as a waterfall on one time axis.

**Why this priority**: Visible execution is the reason this project exists rather than being
another chat box. The anatomy must match the reference so that what a person learned there
transfers without relearning.

**Independent Test**: A scripted two-tool turn driven through the dashboard produces a turn
card with two loop rows, two tool rows, a receipt, and the same turn in the waterfall.

**Acceptance Scenarios**:

1. **Given** the dashboard command is running, **When** a turn runs, **Then** the card shows the gate decision, one row per loop iteration, one row per tool call with duration and outcome, then the reply and a receipt whose token counts and cost match the trajectory.
2. **Given** a tool takes several seconds, **When** it finishes, **Then** its row appears before the reply is produced, not after the turn ends.
3. **Given** the turn has ended, **When** the person opens the observability view, **Then** the same turn appears as a waterfall on one time axis with one closed row per loop.
4. **Given** the process is restarted, **When** the dashboard opens again, **Then** past turns are still there because they are read from the recorded trajectory rather than from process memory.

---

### User Story 3 - Memory that earns its place (Priority: P3)

The person tells the agent something durable, quits, and later asks a question that depends
on it; the agent recalls it. A question that needs no memory does not trigger retrieval. After
enough exchanges, consolidation distils the conversation into facts and an episode, all
visible in the memory view and readable as plain files on disk.

**Why this priority**: Memory is what makes a local assistant worth keeping, but it is only
meaningful once a turn and its visualization exist. A gate that decides *whether* to remember
is the distinctive part, not a vector database.

**Independent Test**: With a scripted model and a temporary home, a fact saved in one process
is retrieved by a fresh process; six exchanges produce new facts and an episode; a no-memory
turn records a skip decision with a reason.

**Acceptance Scenarios**:

1. **Given** a durable fact stated in one process, **When** it is asked about in a new process, **Then** the reply uses the fact and the turn shows it was retrieved.
2. **Given** a turn that does not need memory, **When** the gate runs, **Then** no retrieval happens and both the card and the trajectory record the skip with a reason.
3. **Given** six unconsolidated exchanges, **When** consolidation runs, **Then** new facts and an episode exist, the chat rows are marked consolidated, and the readable memory mirror matches the store.
4. **Given** a fact is wrong, **When** the person asks the agent to forget it, **Then** it no longer appears in retrieval or in the mirror.

---

### User Story 4 - Prove it, offline (Priority: P4)

A maintainer changes a prompt, a tool description or the loop. Before shipping they run the
default test command with no network and no credentials, then the release gate, which names
each suite and refuses to call the build ready when one fails. A support report arrives with
a trajectory attached; the timeline command replays it into a readable story.

**Why this priority**: Prompts and loop logic are code. Without an offline check and a
replayable trajectory, every change is a guess — but this story only pays off once there is
behavior worth measuring, hence P4.

**Independent Test**: On a machine with networking disabled, the default test command passes;
a deliberately lowered step limit makes one check fail and the gate reports not-ready.

**Acceptance Scenarios**:

1. **Given** no network access, **When** the default test command runs, **Then** the suite passes using a scripted model only.
2. **Given** a recorded trajectory, **When** the timeline command runs, **Then** it prints the turn's events in order with durations, token usage and cost.
3. **Given** a trajectory file with one corrupted line, **When** it is rendered, **Then** the bad line is reported and every other line still renders.
4. **Given** one suite fails, **When** the release gate runs, **Then** it exits non-zero and names the failing suite instead of reporting readiness.
5. **Given** a trajectory from a reported defect, **When** the replay procedure is followed, **Then** the defect is reproduced as a test that fails before the fix and passes after it.

---

### Edge Cases

- **No provider key on first run**: the agent names the exact variable to set and exits without a stack trajectory; it does not half-start.
- **Provider refuses a request mid-turn (4xx)**: the turn ends with the provider's own sentence, the failure is recorded in the trajectory, and the card marks the step as failed rather than looping without progress.
- **Provider transport failure**: a retry is attempted once; if it fails again the turn ends with a readable message and a recorded error.
- **Model returns neither text nor a tool call**: the turn ends with an explicit "no answer" message, and the trajectory records the stop reason.
- **Empty or whitespace-only input**: ignored, no turn started, no trajectory written.
- **A turn crashes before its end record**: the turn is shown as unfinished, later turns keep their normal position in the timeline, and nothing is silently dropped.
- **Corrupted trajectory line**: reported and skipped; rendering continues.
- **Dashboard port already in use**: a clear message names the port and how to change it; the terminal chat remains usable.
- **Terminal chat and dashboard used at the same time**: no "database is locked" failures; each message records which surface it came from.
- **Unknown model in the pricing table**: the receipt is marked as an estimate rather than showing a false zero.
- **Very large tool output**: previews are bounded in the UI and in the trajectory, while the model still receives what it needs.
- **Relative dates across a timezone/DST boundary**: the assistant is told the current local time with its zone on every turn, and "in 30 minutes" resolves correctly.
- **A step-limit turn**: the person sees one answer plus the limit notice, never a silent truncation.

## Requirements *(mandatory)*

### Module Cut — what "minimum usable" means here

The retained set is the four pillars reduced to one local user, two surfaces and one process.

**Retained**:

- Harness assembly, settings, home-directory resolution, and one embedded database.
- The turn loop: model call, tool dispatch, observation, stop conditions.
- One model-adapter seam covering the reference's default wire formats.
- Tools: create calendar event, list calendar events, save a note/fact, draft a message to a local outbox, correct or forget a fact, and update the persona file.
- Working memory per turn: persona file + current time and timezone + active model/provider + retrieved memory + bounded history.
- Memory: retrieval gate, semantic facts, episodic episodes, consolidation, readable on-disk mirror.
- Operations: JSON Lines trajectory, turn/waterfall projection, terminal trajectory timeline, per-turn receipt and cost, local dashboard (chat, memory, observability, settings), dependency-free front end.
- Surfaces: terminal chat and local dashboard only.

**Retired for this version** (must not exist, and must not appear as stubs or "coming soon"):

- Voice, Telegram, Discord and WhatsApp surfaces.
- Graph workflow engine, morning brief, gather, triage routing.
- Plugin system, hooks, MCP client and servers, hosted-memory integration.
- Community skill marketplace, SKILL.md loader and its trigger machinery.
- Judge evals, model/memory/judgment arenas, comparison history, turn-eval UI.
- Multi-tenant hosted deployment, lab experiments, example applications.
- Opt-in ecosystems: Apple Calendar, Google Calendar, GitHub, external data relays, experimental sub-agents.

### Parity Seams *(the "技术栈一致 / 可视化一致" requirement)*

Parity is required at seams a person or a script can observe; internals may differ.

| Seam | Parity requirement |
|---|---|
| Commands | The bare command starts chat; `dashboard` keeps the reference's verb; the timeline command is `trajectory` where the reference says `trace`; the offline suite and release gate keep the reference's make targets; the executable carries this project's own name |
| Address | Dashboard serves the same local address and the same route shape for live events, turn data and observability data |
| Files | One home directory: one database, a persona file, a trajectories directory of daily JSON Lines files, a memory mirror |
| Trajectory | Same event names, field names and units, so either side's timeline renderer reads either side's trajectory |
| Turn card | Same anatomy: message, stage row, per-step rows with duration and outcome, reply, receipt |
| Waterfall | Same time-axis chart, one closed row per loop, failures called out, raw event reachable |
| Configuration | Same knobs, meanings and default values for retained behavior, under this project's own variable prefix so both agents can be installed side by side |
| Install | One install command and one console command; no build step, no framework, no daemon |

### Functional Requirements

**Parity and scope**

- **FR-001**: Retained behavior MUST match the reference at every seam in the table above: the same verbs do the same things (except the timeline verb, which is this project's word for the same artifact), the dashboard has the same shape at the same address, and state is laid out the same way on disk. Only the product's own name, executable, variable prefix and the word *trajectory* are new, and those are the only new instructions a person who knows the reference needs.
- **FR-002**: The system MUST ship exactly the retained modules. Retired capabilities MUST be absent from code, commands, help text and UI, not stubbed.
- **FR-003**: The system MUST use the same runtime baseline and dependency budget as the reference: one installable command, no agent-orchestration framework, no browser build step, and no default runtime dependency beyond the reference's default set.
- **FR-004**: All runtime state MUST live in one project-owned home directory, defaulting to a user-wide location and overridable for tests and portable installs; it MUST be readable with ordinary tools, and the product MUST NOT read, write or claim compatibility with the reference's home directory.
- **FR-005**: Retained tables MUST keep the reference's names and the columns the retained behaviors use (columns that exist only for retired integrations are omitted), so a later migration from an existing install would be mechanical and trajectories stay comparable. No migration tooling ships in this version.
- **FR-006**: Every retained configuration knob MUST keep the reference's meaning and default value, exposed under this project's own variable prefix so both agents can be installed side by side; credentials MUST come only from the environment or a dotenv file and MUST never appear in source, fixtures, trajectories or logs.
- **FR-007**: The reference's brand assets (mark, fonts, design tokens, illustrations) MUST NOT be copied. The interface MUST reproduce the same information architecture and layout with its own neutral identity.
- **FR-008**: The reference checkout MUST remain unmodified; it is read-only input for comparison.

**Turn loop and model access**

- **FR-009**: A turn MUST be a loop: assemble working memory, call the model with tools, run any requested tools, return their results to the model, repeat until the model stops asking for tools or the step limit is reached.
- **FR-010**: The step limit MUST default to the reference's value, be configurable, and on exhaustion make one final tools-off call so the person gets an answer from what was gathered; the reply MUST state that the limit was reached.
- **FR-011**: A failing tool MUST NOT crash the turn: the model observes the error as text and may retry or explain.
- **FR-012**: All model access MUST pass through one adapter seam that expresses the capabilities the loop relies on (tool calls, streaming text, usage, stop reason) and returns typed errors; no vendor SDK may be imported by loop, tools or context code.
- **FR-013**: The core MUST run and pass its tests against a scripted model with no network and no credentials.
- **FR-014**: Working memory MUST include the persona file, the current local date-time with timezone, the active model and provider, the retrieved memory block when present, and a bounded conversation history.
- **FR-015**: Conversation history MUST be bounded by a configurable turn count, and long tool results already read by the model MUST be shortened before later iterations rather than re-sent verbatim.

**Tools**

- **FR-016**: A tool MUST be one declaration — name, model-facing description, JSON-schema arguments, and a callable returning text — registered once and dispatched by name; an unknown name returns an error text, not an exception.
- **FR-017**: The retained tool set is: create calendar event, list calendar events, save note/fact, draft message to the local outbox, correct or forget a fact, update the persona file. No other tool ships enabled.
- **FR-018**: Every tool's output MUST state exactly where its artifact landed (the database path, the outbox file, the memory file), so the assistant never claims a sync that did not happen.

**Memory**

- **FR-019**: Every turn MUST consult a retrieval gate that decides whether memory is needed, defaulting to "retrieve" when the decision cannot be made, and MUST record the decision and reason in the trajectory and on the card.
- **FR-020**: Facts and episodes MUST be stored locally with keyword search, and retrieval MUST return a bounded top-k (reference default) for the current message.
- **FR-021**: Consolidation MUST run after a configurable number of unconsolidated exchanges, distil them into proposed facts and one episode, mark the consumed rows, and never fail the turn; a failure MUST leave the rows unconsolidated for the next attempt.
- **FR-022**: Consolidation MUST write a human-readable mirror on disk (one file per fact plus one combined readable memory file) that matches the store.
- **FR-023**: The persona file (the project's own file name for it) MUST be created on first run, included in every turn's system prompt, and editable by the person and by the agent.
- **FR-024**: The person MUST be able to inspect memory in the terminal and in the dashboard, correct a fact, and delete a fact; deletions MUST take effect in retrieval and in the mirror immediately.

**Execution visibility**

- **FR-025**: The terminal MUST print each step as it completes — tool name with arguments and a result preview, gate decision with reason, consolidation outcome — before the reply is printed.
- **FR-026**: The dashboard MUST show a turn as it happens: the user's message, a stage row summarising gate, loops, tools and reply, one row per loop iteration, one row per tool call with arguments, result preview, duration and outcome, the reply streamed token by token, and a receipt with token usage and cost.
- **FR-027**: Steps MUST reach the surface as they complete. The reply MUST stream; a step MUST NOT be withheld until the turn ends, and the turn MUST NOT be delayed by the visualization being closed or unavailable.
- **FR-028**: Every turn MUST append a JSON Lines trajectory containing: turn start with the user message and turn id; the gate decision with reason; one record per model call with iteration, stop reason and token usage; one record per tool call with arguments, output preview and duration in milliseconds; consolidation with the kept facts; the receipt with cost; and the turn end with reply and iteration count.
- **FR-029**: A turn that dies mid-way MUST be recorded as unfinished, MUST NOT corrupt later records, and MUST be rendered as unfinished rather than dropped.
- **FR-030**: The observability view MUST render a per-turn waterfall on one time axis, one closed row per loop, with failures highlighted, argument and output previews, durations, and a way to reach the raw event.
- **FR-031**: A terminal command MUST render any recorded trajectory as a readable timeline (indented inside its turn), default to the most recent trajectory when none is named, and skip malformed lines while reporting them.
- **FR-032**: The trajectory schema MUST be versioned — readable from the trajectory itself — and documented; a trajectory produced by the reference MUST render here and a trajectory produced here MUST render in the reference's timeline, with no unparsed events. Because this build emits a subset of the reference's event types, unknown event types MUST render as a generic row rather than an error.
- **FR-033**: Secret redaction MUST be enforced at the trajectory sink, so no caller can write a credential into a trajectory, a log line or the UI.

**Proof and cost**

- **FR-034**: A deterministic offline suite MUST cover each retained behavior above, including the parity seams, and MUST be the default test command.
- **FR-035**: A release-gate command MUST run the suite, report each result, and exit non-zero naming the failing check rather than reporting readiness.
- **FR-036**: The receipt MUST compute per-call cost from a model pricing table and mark any unknown model as an estimate; the same numbers MUST appear on the card and in the trajectory.
- **FR-037**: A defect MUST be reproducible from its trajectory alone: a documented procedure turns a trajectory into a failing test, and at least one such replay test MUST exist.

### Key Entities *(include if feature involves data)*

- **Turn**: one user message and everything the agent did in response. Has an id, a start and end time, the reply, the iteration count, and a sequence of steps.
- **Step / Trajectory event**: one recorded action inside a turn (gate decision, model call, tool call, consolidation, receipt, turn boundary) with a timestamp, a duration where applicable, and type-specific fields.
- **Tool call**: the tool name, its arguments, a bounded output preview, the full output the model saw, an outcome (ok or failed) and a duration.
- **Fact**: a durable statement, with a subject, the text, where it came from, and when it was learned.
- **Episode**: a dated summary of something that happened, with the date it happened and when it was distilled.
- **Chat message**: one turn of the conversation, with role, text, surface (terminal or dashboard), session, and the turn metadata needed to redraw its card later.
- **Session**: a named conversation thread; messages and turns belong to one.
- **Receipt**: the per-turn accounting — iterations, tool calls, tokens in and out, and cost in the configured currency.
- **Home**: the one directory holding the database, persona file, trajectories, memory mirror, outbox and dotenv file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with one provider key goes from a clean machine to a first answered turn in at most five commands and under five minutes, with no file editing beyond pasting the key.
- **SC-002**: In at least 95% of turns the first step appears within two seconds of sending, and in 100% of turns every step is visible before the final reply is rendered.
- **SC-003**: Every turn produces exactly one trajectory that renders in both the terminal timeline and the dashboard waterfall; zero unparsed events across a 50-turn sample.
- **SC-004**: A fact stated in one process is recalled in a fresh process in at least 95% of scripted checks, and a turn that needs no memory performs no retrieval in at least 95% of scripted no-memory checks.
- **SC-005**: The default test command passes with networking disabled in under three minutes and asserts at least one check per retained behavior in the module cut.
- **SC-006**: The parity checklist passes 100%: for one scripted turn run through both systems, commands (the timeline verb being the one named difference), local address, file layout, trajectory vocabulary and turn-card anatomy are equivalent, judged side by side.
- **SC-007**: The dependency budget holds: zero orchestration frameworks, zero front-end build step, and no default runtime dependency beyond the reference's default set.
- **SC-008**: Zero credentials appear in any produced trajectory, log or UI across the test corpus.
- **SC-009**: No turn exceeds the configured step limit, and closing the dashboard does not fail or slow a terminal turn.
- **SC-010**: A trajectory captured from the reference renders here and a trajectory captured here renders in the reference's timeline, with zero unparsed events in both directions.

## Assumptions

- **Reference availability**: `~/Projects/Private/waku-agent` stays on disk, unmodified, for side-by-side comparison; the parity claims in SC-006 and SC-010 are checked against that checkout.
- **Meaning of "minimum usable"**: one local user, one process, two surfaces (terminal and browser), the four pillars (harness, loop, memory, operations), no multi-user, no hosting, no network services beyond the model provider.
- **Rebuild vs. port**: parity is defined on observable behavior and contracts, not on file-for-file likeness. Every retained behavior must be readable as source in this repository (the project's constitution forbids frameworks owning control flow); whether a module is adapted from the reference's permissively licensed code or rewritten is a planning decision, and either way no brand asset is copied.
- **Procedural memory is reduced to a persona file** (confirmed 2026-11-18). Loading SKILL.md packs and the skill marketplace is deferred: it adds a directory layout, a trigger mechanism and a validation surface that the minimum usable product does not need.
- **Proof is deterministic in this version** (confirmed 2026-11-18). Judge-scored evals, arenas and release dashboards are deferred; a deterministic offline suite plus the release gate is the bar.
- **The tool set is closed** (confirmed 2026-11-18). The six tools in FR-017 are the whole set; web search, MCP servers and the external calendar/ecosystem integrations stay retired, not merely switched off.
- **Provider set**: the reference's default wire formats and provider list are retained; adding a provider later is additive and must not touch the loop.
- **Own identity, same shape**: the executable, the environment-variable prefix, the home directory and the persona file use this project's own names; parity covers layout, contracts and visualization, not identifiers. No migration entry point from an existing reference installation ships in v1, and the schema stays compatible only so migrating later would be mechanical.
- **Retention**: nothing is deleted automatically. Trajectories, chat rows, facts and episodes stay until the person deletes them — the data is theirs — and this version ships no pruning or compaction.
- **Platforms**: macOS and Linux terminals, one user account per machine, localhost-only dashboard with no authentication (matching the reference).
- **Cost currency**: the receipt shows cost in US dollars derived from a versioned pricing table; unknown models are marked as estimates.
- **Definition of done for this feature**: the retained surface works end to end, the retired surface is absent, and the parity seams are demonstrated side by side on one scripted turn.

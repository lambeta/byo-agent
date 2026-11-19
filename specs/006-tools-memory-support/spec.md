# Feature Specification: Working Tools & Memory in the Dashboard

**Feature Branch**: `006-tools-memory-support`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "增加 tools 和 memory 的支持"

**Observed defects (clarified 2026-11-19)**: (1) clicking the **Tools** node on the
Overview map produces no visible response; (2) the **Memory** view renders the text
"Undefined" instead of the memory content. Fixing both — and pinning them with offline
tests — is the heart of this feature.

**Scope (clarified 2026-11-19)**: No new tools. This feature makes the **existing** six tools
(`create_event`, `list_events`, `save_note`, `send_message`, `manage_memory`,
`update_persona`) and the **existing** memory subsystem (gate, retrieval, consolidation,
readable mirror, Memory view) work properly when the agent is driven from the **dashboard**.
Anything beyond that — new tools, open tool registration, shell/web capability, new memory
types, semantic retrieval — is out of scope.

## Clarifications

### Session 2026-11-19

- Q: 这次"增加 tools 的支持"，Agent 应该获得哪些超出当前六个工具的新能力？ → A: 不需要新工具。"我需要的是 dashboard 中现有的 tool，以及 memory 能正常工作，其余无需添加新 tool" — the feature is making the existing tools and memory work properly in the dashboard.
- Q: 你在 dashboard 里实际观察到的"不能正常工作"是什么现象？ → A: 两个症状：① Overview 地图上点击 Tools 节点没有任何反应；② 进入 Memory 视图，页面显示 "Undefined"。Both symptoms are reproducible defects of the dashboard surface, not of the agent core (the offline suite — 223 tests — passes, and the dashboard tests run with memory disabled, so neither symptom is currently pinned by a test).
- Q: 点击 Overview 地图上的 Tools 节点，应该发生什么？ → A: 遵循现有的 waku agent 设计交互方式 — adopt the waku-agent interaction model: every Overview map node is clickable and navigates (hash route) to its own view. The Tools node opens a dedicated Tools view (waku's #tools: an "Available" catalog of what the agent can call — one card per tool with name, description and schema — plus "Results": what tool calls actually produced). Memory nodes open the Memory view organized in waku-style sections (gate overview, facts, episodes, consolidation). Waku tabs for retired capabilities (MCP, hooks, Apple, skills) are NOT ported.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tools work in the dashboard chat (Priority: P1)

A person opens the dashboard, and in the chat dock asks for something that needs a tool —
"book a catch-up with Alex on Friday". The agent resolves the date, calls the tool, and
answers with what it did and where the artifact landed. While the turn runs, the tool call
is visible as its own lane in the dock (name, arguments, result) before the reply finishes,
and the turn lands in the trajectory exactly like a terminal turn does.

**Why this priority**: The chat dock is the dashboard's only way to talk to the agent. If
tools do not actually run (or run invisibly) there, the dashboard is a viewer, not an agent
surface — and every other view exists to explain turns like this one.

**Independent Test**: Against a scripted model (offline, no credentials), drive one turn
through the dashboard's chat endpoint that calls one tool; verify the tool executed, the
result reached the model, the reply reflects it, and the live stream carried the tool start
and tool result frames before the reply.

**Acceptance Scenarios**:

1. **Given** the dashboard is running, **When** the person sends a chat message that the model answers with a tool call, **Then** the tool executes and the reply truthfully states what it did and where the result landed.
2. **Given** a turn with a tool call is running, **When** the tool starts and finishes, **Then** the dock shows the tool lane (name, arguments, result preview) before the final reply, not after.
3. **Given** a tool raises an error, **When** the model reads the result, **Then** the turn continues, the error text reaches the model, and the person sees a reply rather than a crash or a silently empty answer.
4. **Given** a dashboard turn used tools, **When** the turn ends, **Then** the trajectory records the same tool events (name, arguments, outcome, duration) as an equivalent terminal turn.
5. **Given** the Overview map, **When** the person clicks the Tools node, **Then** the dashboard navigates to the Tools view, which lists the six available tools (name, description, input schema) and the recent results tool calls produced; with no recorded calls yet, the results area shows an explicit empty state. A click is never a silent no-op.

---

### User Story 2 - Memory works end to end in the dashboard (Priority: P2)

From the dashboard, the person teaches the agent something ("remember that I take my coffee
black"), and later asks a question that needs it. The gate runs on the dashboard turn, the
relevant fact is retrieved into context, and the reply uses it. Opening the **Memory** view
shows the stored facts and episodes; adding, editing or forgetting a fact there persists to
the store and the readable mirror reflects the change. When enough turns have passed,
consolidation runs and its result is visible in the Memory view and the mirror.

**Why this priority**: Memory is one of the product's four pillars, and the dashboard has a
dedicated Memory view. If the view or the recall path is broken from this surface, the
person cannot see or correct what the agent believes — the agent becomes a black box, which
is the opposite of the project's purpose.

**Independent Test**: Offline, drive a dashboard turn with a memory-bearing message and a
scripted model whose gate decision is "retrieve"; verify the recalled block reaches the
system prompt, then add/edit/forget a fact through the Memory API and verify the store and
the mirror file agree.

**Acceptance Scenarios**:

1. **Given** a fact stored from an earlier day, **When** a dashboard chat turn touches the same subject and the gate decides to retrieve, **Then** the fact appears in the context the model sees and the reply uses it.
2. **Given** the Memory view, **When** the person adds, edits or forgets a fact, **Then** the change persists, the view reflects it, and the readable mirror matches the database.
3. **Given** the dashboard is open, **When** the person navigates to the Memory view, **Then** the view renders its sections — gate overview, facts, episodes, consolidation status — with the stored content (or explicit empty states), and it never renders blank, an error, or the text "Undefined".
4. **Given** the consolidation threshold is reached, **When** a dashboard turn ends, **Then** consolidation runs, its event is recorded in the trajectory, and new facts appear in the Memory view and the mirror.
5. **Given** the memory store is missing or a memory step fails, **When** a dashboard turn runs, **Then** the turn still completes, the failure is recorded, and the person is not left with a silent hang.

---

### User Story 3 - CLI and dashboard tell the same story (Priority: P3)

A maintainer sends the same request through the terminal and through the dashboard and gets
equivalent behavior: same tools offered, same memory path, equivalent trajectory records —
differing only in surface (terminal print vs. browser rendering). A regression in the
dashboard path is caught by the offline suite, not by a person clicking around.

**Why this priority**: The project promises one agent reachable from every surface. Parity
is what makes the dashboard a trustworthy window instead of a second, divergent agent. It
ranks P3 because it is a property of the first two stories rather than a new user journey.

**Independent Test**: Run the same scripted tool-and-memory turn through both the CLI path
and the dashboard path; compare the recorded trajectory events for equivalence (same kinds,
same order, same payloads modulo timestamps and ids).

**Acceptance Scenarios**:

1. **Given** one scripted scenario, **When** it runs once through the terminal path and once through the dashboard chat path, **Then** both trajectories record the same sequence of event kinds (gate, loop iterations, tool calls, reply, receipt, consolidation when due).
2. **Given** a behavior-touching change to the dashboard chat or Memory view path, **When** the offline suite runs, **Then** it fails if the dashboard path diverges from the terminal path, with no network and no credentials.

---

### Edge Cases

- A second chat message arrives while a turn is running: the dashboard refuses it with a clear "a turn is already running" response rather than queueing or corrupting state.
- A tool errors or returns oversized output: the error (or a bounded result) reaches the model and the turn continues; the dock shows the failure honestly.
- The person closes the browser tab mid-turn: the turn completes server-side, the trajectory is whole, and reopening the dashboard shows the finished turn.
- The memory store is missing, locked or corrupted at startup: the dashboard still serves, turns still run, and the degradation is visible rather than silent.
- A fact added via the Memory view contains a secret: redaction at the trace boundary still applies to anything the turn records.
- Retrieval finds nothing relevant: no memory block is injected, rather than padding context with noise.

## Requirements *(mandatory)*

### Functional Requirements

#### Tools in the dashboard

- **FR-001**: Every tool the agent offers — the existing six, and no others — MUST be callable from a dashboard chat turn exactly as from the terminal: same schemas offered to the model, same execution path, same error-to-text conversion.
- **FR-002**: A tool call made during a dashboard turn MUST be visible live in the chat dock as its own lane (tool name, arguments, result or error) before the final reply, and MUST be recorded in the trajectory with name, arguments, outcome, ok flag and duration.
- **FR-003**: No new tool MAY be added by this feature; the tool set stays the existing six. Tool enablement remains configuration, consistent with the constitution.
- **FR-003a**: Following the waku interaction model, every node on the Overview map MUST be clickable and MUST navigate (hash route) to its own view; the Tools node MUST open a dedicated **Tools view**.
- **FR-003b**: The Tools view MUST show (a) the **Available** catalog — one card per existing tool with its name, description and input schema, exactly as offered to the model — and (b) **Results** — what recent tool calls actually produced, read from the recorded trajectory, with an explicit empty state when no calls are recorded.

#### Memory in the dashboard

- **FR-004**: The retrieval gate MUST run for dashboard chat turns exactly as for terminal turns, with its decision recorded and visible on the dashboard's live surfaces.
- **FR-005**: When the gate decides to retrieve, the recalled memory block MUST reach the system prompt of a dashboard turn, bounded by configuration, and MUST be omitted entirely when nothing relevant is found.
- **FR-006**: The Memory view MUST be organized in waku-style sections — **gate overview** (retrieve/skip decisions), **facts** (the semantic store), **episodes**, and **consolidation** status — listing content from the database; it MUST support adding, editing and forgetting a fact; every such change MUST persist and leave the readable mirror consistent with the database.
- **FR-007**: Consolidation MUST run on the same threshold regardless of surface, and its outcome MUST be recorded in the trajectory and reflected in the Memory view and the mirror.
- **FR-008**: Any failure in the gate, retrieval or consolidation MUST degrade to safe behavior (retrieve anyway, or no memory), be recorded, and never fail or hang the person's turn.

#### Cross-cutting (constitution-derived)

- **FR-009**: Dashboard and terminal paths MUST share one agent implementation — no parallel tool dispatch, memory logic or trajectory writing in the dashboard server.
- **FR-010**: The default offline test suite MUST cover the dashboard chat path (a tool-calling turn through the chat endpoint and stream) and the Memory view API (add/edit/forget plus mirror consistency), passing with no network and no credentials.
- **FR-011**: Every behavior-touching change (tool descriptions, loop logic, memory policy, chat dock behavior) MUST ship with an offline eval delta per the constitution.
- **FR-012**: Secrets MUST NOT appear in any dashboard response, stream frame, trajectory line or mirror file; redaction stays enforced at the trace sink boundary.

### Key Entities

- **Tool**: one of the existing six declared capabilities — name, description, input schema and handler — callable by the model from any surface.
- **Fact**: a durable piece of remembered knowledge (subject, content, source); listed and editable in the Memory view, mirrored to a readable file.
- **Episode**: a dated summary of something that happened; listed in the Memory view and surfaceable by retrieval.
- **Gate decision**: the per-turn record of whether memory was consulted, taken identically on terminal and dashboard turns.
- **Chat dock lane**: the dashboard's live rendering of one step of a running turn (thinking, tool call, output); a projection of recorded events, never a re-enactment.
- **Trajectory event**: the append-only record of one observable step; the single source every surface reads from.

## Success Criteria *(mandatory)*

- **SC-001**: From the dashboard chat, a request needing each of the six tools completes with the tool executed and the outcome visible; in the offline suite this holds for 100% of the pinned scenarios (one per tool that can be exercised offline).
- **SC-002**: In a live dashboard turn that calls a tool, the tool lane appears before the final reply in 100% of observed turns (stream frame ordering verified in tests).
- **SC-003**: A fact stored on a previous day is used in the reply of a later dashboard turn that needs it, in all offline retrieval scenarios; a dashboard turn with the gate deciding "no retrieval" injects no memory block.
- **SC-004**: Every Memory view mutation (add/edit/forget) leaves the database and the readable mirror identical, verified by offline tests; the view never shows a fact the store does not have.
- **SC-005**: The same scripted scenario driven through terminal and dashboard produces trajectories with the same event-kind sequence in 100% of compared runs.
- **SC-006**: The default offline test command passes with no network and no credentials, including the new dashboard-path coverage, and the change lowers no existing eval score.
- **SC-007**: Every Overview map node click navigates to its view; the Tools view renders all six tool cards and the Memory view renders all its sections, in 100% of offline render tests — no blank view, no "Undefined", no silent no-op.

## Out of Scope

- Adding any new tool (filesystem, shell, web search, delegation, MCP, external ecosystems).
- Opening the tool set to user-declared or plugin tools.
- New memory types or structures, semantic/embedding retrieval, forgetting/decay policies.
- Changes to the visual design of the dashboard (covered by specs 003–004).
- Waku Tools/Memory tabs for capabilities byo retired in spec 001: MCP servers, hooks, Apple ecosystem, skills. The Tools view shows the six existing tools only.

## Assumptions

- The six existing tools and the memory pipeline already work on the terminal path; this feature closes whatever gap keeps them from working properly on the dashboard path.
- "正常工作" is defined by the acceptance scenarios above: tools execute and are visible live; memory is gated, recalled, editable and consolidated; both are provable offline.
- The fix is expected to live in wiring, surfaces and tests — not in replacing the loop, registry or memory pipeline, which the offline suite already covers (223 tests passing as of 2026-11-19).
- The specific symptoms observed in the browser will be confirmed in clarification; the acceptance scenarios are written so they fail on any surface where tools or memory do not actually work.

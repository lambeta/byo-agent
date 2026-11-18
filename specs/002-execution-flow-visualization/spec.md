# Feature Specification: Agent Execution Visualization

**Feature Branch**: `n/a — repository has no version control yet`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "添加agent执行可视化的流程，仿照 waku"

**Reference**: The visualization anatomy is modelled on the local, read-only `waku-agent` checkout at
`~/Projects/Private/waku-agent` — specifically its Overview architecture map, which lights up as a
turn flows through the harness, and the per-turn detail behind it. Only the information architecture
and behavior are borrowed; the visual identity stays this project's own, and the reference is never
modified.

**Depends on**: `specs/001-waku-minimal-core` — the dashboard, turn card, recorded trajectory and
observability window this feature extends already exist there.

## Clarifications

### Session 2026-11-18

- Q: Should the primary visualization be a per-turn execution path, the whole-agent architecture map that lights up (the reference's Overview), or both? → A: The runtime architecture map with live lighting is the primary landing view; single-turn detail is a secondary drill-down.
- Q: Should the map include the reference's LLM Ops area (Trajectory → Observability → Evals → Release), or only the runtime execution path? → A: Only the runtime execution path; evals and release stay command-line and are not drawn on the map.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The runtime agent at a glance, live (Priority: P1)

A person opens the dashboard and lands on a map of their agent: the surfaces it is reached through,
the memory decision, the working context, the loop that reasons and calls tools, the reply, the
record it writes, and the memory and operations around it. The map is not a poster — when a turn
runs, the parts involved light up in the order they happen, a status line names the step currently
under way, and each node carries a small live summary. A person can see *where* a turn is by looking
at one picture, whether the turn was typed into the browser or started in the terminal.

**Why this priority**: The reference's Overview is the front door to its whole system, and the user
chose that shape for this feature. It explains both the architecture and the live turn in one view,
which no single turn card can do. The per-turn detail in the next story is only reachable once this
map exists.

**Independent Test**: With a scripted model and a temporary home, one turn that requests a tool lights
the input, memory decision, working context, loop, tool, reply and recording nodes in the recorded
order on an otherwise idle map, and each node's link opens its detail.

**Acceptance Scenarios**:

1. **Given** the dashboard starts with no turn running, **When** it finishes loading, **Then** the map is the landing view, every runtime part in scope is present once, each node is clickable, and a status line says the agent is idle.
2. **Given** a turn starts from any surface, **When** its steps are recorded, **Then** the corresponding nodes and connections light in the order the steps happened, the status line names the current step, and no unrelated node lights.
3. **Given** the memory decision is "skip", **When** the gate lights, **Then** the gate shows "skipped" with its recorded reason and the memory nodes stay neutral; **Given** the decision is "retrieve", **Then** the gate and the memory path light together.
4. **Given** a tool call fails but the model recovers, **When** the tool step is recorded, **Then** the tool node is marked failed and the status line names it, while the reply and recording still light as the turn completes.
5. **Given** the turn has ended, **When** the highlight settles, **Then** the map returns to its idle state, the last turn's summary remains readable on the relevant nodes, and clicking the loop or recording node opens that turn's detail.

---

### User Story 2 - Drill from the map into one turn (Priority: P2)

The map answers *where* something happened; the person then clicks the loop, the recording node or a
recent turn and reads *what* happened. A detail view opens without losing the map: the selected
turn's memory decision, one row per loop with its tool calls underneath, the reply and any memory
write, all on one shared time axis. Steps open to show their recorded input, output, duration,
tokens and cost. A failed step announces itself without being opened, and an unfinished turn says so
instead of pretending it completed. Closing the detail returns to the same map.

**Why this priority**: A map that cannot explain a single run is only decoration. The detail is
deliberately secondary — the map stays the entry point — but without it the feature cannot support
debugging, cost review or failure analysis.

**Independent Test**: A recorded fixture with two model calls, two tool calls and one failure opens
from the map with the same count, order, durations, outcomes and costs as the record; the summary
numbers agree with the receipt; closing the detail leaves the map unchanged.

**Acceptance Scenarios**:

1. **Given** the map is showing, **When** the person opens the loop, recording or recent-turn entry, or picks a turn from the turn list, **Then** a detail for the selected turn opens with one row per loop on one shared time axis and tool calls nested under the loop that requested them.
2. **Given** a step in the detail, **When** it is opened, **Then** its recorded arguments or input, output preview, duration, outcome, model, token counts, stop reason and cost are shown, with any truncation marked.
3. **Given** a failed or unfinished turn, **When** its detail opens, **Then** the failure or unfinished state is visible without expanding a row, steps that never ran read not reached, and no reply or cost is invented.
4. **Given** the person is reading an older turn's detail, **When** a new turn starts, **Then** the detail stays put and a visible indicator offers to return to the live map view.
5. **Given** the process has restarted, **When** the person opens an older turn, **Then** it still renders because it is read from the recorded trajectory, not from process memory.

---

### User Story 3 - Watch turns from anywhere, without disturbing them (Priority: P3)

The person runs the terminal chat in one window and leaves the map open in the browser. They ask a
question in the terminal, and the map lights up for that turn, labelled as coming from the terminal.
A second browser tab can watch the same turn without either viewer blocking the other. If a burst of
steps arrives, the map keeps up and never silently drops one. If the browser loses the connection
mid-turn, it says so, catches up when the connection returns, and never shows a stale step as live.
Closing the tab does not cancel or slow the turn.

**Why this priority**: The agent is used from two surfaces, and the map's value is that it observes
the whole agent, not only the turns typed into it. This story makes the map the shared window on
execution; it depends on the first two stories.

**Independent Test**: With the map open, a scripted turn started in the terminal appears without a
page refresh, is labelled by source, and can be watched from two tabs while a third viewer reads an
old turn's detail without being moved.

**Acceptance Scenarios**:

1. **Given** the map is open and following the newest turn, **When** a turn starts in the terminal, **Then** the map lights for it, labels the source, and needs no manual refresh.
2. **Given** the person is reading an older turn's detail, **When** a new turn starts, **Then** the view stays on the detail and a visible indicator offers to return to the live map.
3. **Given** two browser tabs are watching the same live turn, **When** steps are recorded, **Then** both receive the same lighting sequence, watching is read-only, and neither viewer blocks the turn or the other viewer.
4. **Given** a viewer disconnects during a turn, **When** it reconnects, **Then** it shows every recorded step exactly once and in order, and its status distinguishes "live" from "caught up".
5. **Given** the browser tab is closed mid-turn, **When** the turn ends in the terminal, **Then** the turn is not cancelled or slowed, and reopening the dashboard shows the completed turn through the map and its detail.

---

### Edge Cases

- **No turn has ever run**: the map is idle, every node is present, and a short hint says how to start a turn; nothing animates and no fake data is shown.
- **Memory not configured**: the gate and memory nodes read "not configured" and the turn still runs; they are not shown as a successful retrieval.
- **Memory decision skipped**: the gate reads "skipped" with its reason and the memory path stays dark.
- **Memory decision unavailable**: a gate that failed shows "retrieve" with the failure reason and is marked degraded, not silently healthy.
- **Failure at a stage**: a failure in the memory decision, model call or memory write marks that node and the turn, leaves later nodes neutral, and shows the recorded message; a recovered tool error marks only the tool node, and the turn still finishes.
- **Unfinished turn**: a record that stops before its end leaves the last node marked partial, the map does not complete the path, and no reply or cost is invented.
- **Unknown or future event type**: the status line names it as unmapped, no node is lit for it, and the rest of the turn continues to light; nothing crashes.
- **Burst of steps**: events are queued or coalesced so none is silently dropped, and the map catches up to the latest state within one second; if it cannot, it says it is catching up.
- **A new turn starts while the previous highlight is still settling**: the new turn takes over the map cleanly; the previous turn remains readable in the turn list and detail.
- **A turn starts while an old detail is open**: the detail stays; the live indicator is the only change.
- **Corrupted or partial line**: the bad line is reported and skipped, the rest of the turn lights and renders, and one bad line does not blank the map.
- **Very long node summary or step value**: the recorded bounded preview is shown and truncation is marked; the view never implies the full value is present.
- **Instant or unrecorded duration**: the detail shows a minimum marker labelled "not timed" and keeps record order; it does not invent a duration.
- **Zero or missing cost**: an unknown model's cost is marked as an estimate; missing cost reads "not recorded", never "$0".
- **Many steps or many turns**: a turn with 20 or more steps and a window with 200 or more turns still opens, lights, scrolls and expands without freezing.
- **Narrow window or zoom**: at 1024 px and 200% zoom the map pans or stacks and the detail scrolls, without clipping essential labels.
- **Reduced motion**: lighting becomes an immediate state change; the sequence and the status line still convey what happened.
- **Keyboard or screen reader**: every node is reachable, its state is announced, and the same information is available as a text list.
- **Live updates unavailable**: the map marks itself stale, keeps the last complete state, and catches up on recovery; it does not present old steps as new.
- **Two viewers**: both can watch; neither can start, stop or alter the turn by watching.
- **A node's detail destination is unavailable**: the map still lights and explains, and the click reports the missing destination instead of failing silently.
- **Someone looks for evals or release on the map**: they are absent by design, with no placeholder node; the terminal commands remain the way to run them.

## Requirements *(mandatory)*

### Functional Requirements

**The agent map (primary view)**

- **FR-001**: The dashboard MUST provide an architecture map as its primary landing view, reachable from the main navigation, showing the agent from the surfaces it is used through to the record it writes.
- **FR-002**: The map MUST show the runtime parts this product actually has, grouped into surfaces, harness (memory decision, working context, loop, model reasoning, tools, reply), memory (facts, episodes, persona, consolidation) and operations (trajectory, observability, cost). Retired capabilities and command-line-only tooling — voice, Telegram, Discord, graph workflows, MCP, skills marketplace, hosted and multi-tenant features, evals and release — MUST NOT appear as nodes, edges or "coming soon" hints.
- **FR-003**: Every node MUST correspond to a real runtime part of the product and MUST lead to that part's detail; no node is decorative or implies behavior the product does not have. Each node MUST carry a compact one-line live summary (for example a memory count, the gate's skip/retrieve split, the last model or tool, the number of recorded turns, today's cost) and MUST NOT show a number that was not measured.
- **FR-004**: Connections MUST show the direction of flow and carry a short label where the flow is not obvious (message in, only if needed, act, reply, save, distill). A connection MUST NOT be drawn where no such flow exists.
- **FR-005**: The map layout MUST reflect the actual order and loops of this product: a message reaches the gate and working context before the loop, the loop alternates model reasoning and tool calls, the reply returns to the surface it came from, every turn is recorded, and consolidation writes back to memory.
- **FR-006**: Every node MUST be a navigation control that opens its detail without losing the map: a surface opens the chat, the working context opens the current session, the gate and memory nodes open memory, the loop, tool and reply nodes open the selected turn's detail, consolidation opens memory, the record opens observability, and the operations nodes open their existing views.
- **FR-007**: The map MUST have an idle state, a live state and a caught-up state, with a status line that names the step currently under way. When no turn is running the map MUST stay idle, with no looping animation and no invented activity.
- **FR-008**: The map MUST provide a text alternative that lists every node, its current state and its link, so the same information is available to a screen reader and to a person who prefers text over the diagram.

**Live lighting**

- **FR-009**: As each step is recorded, it MUST light its mapped node and connection in the order it was recorded, without waiting for the turn to end; the final end step lights when it is recorded. The mapping MUST cover every event type the product emits, including the memory decision, each model call, each tool call, the reply and the end, consolidation, the receipt and errors.
- **FR-010**: Lighting MUST reflect what actually happened: a skipped memory decision leaves the memory path dark, a retrieval lights it with the recorded count, a failed tool lights that tool as failed, an unreached stage stays neutral, and a final tools-off model call is labelled as a final answer rather than another tool-requesting loop.
- **FR-011**: A live turn MUST be observable when it starts from any surface sharing the same home — terminal, dashboard or another browser tab — and the status line MUST label the surface of origin.
- **FR-012**: Watching MUST be read-only: it MUST NOT start, delay, cancel or block a turn, and any number of viewers MUST be able to watch the same turn.
- **FR-013**: When steps arrive faster than they can be shown, the map MUST queue or coalesce them so none is silently dropped and the displayed state never lags the record by more than one second. If it cannot keep up, it MUST say it is catching up and jump to the latest complete state rather than inventing intermediate ones.
- **FR-014**: The highlight MUST settle to the idle state after a consistent pause of between 0.5 and 2 seconds once the turn ends, leaving the last turn's summary readable; the map MUST NOT stay lit indefinitely or reset before the person can see the end.

**Turn detail (secondary drill-down)**

- **FR-015**: The map MUST open a per-turn detail for the selected or most recent turn without leaving the map context, through the loop, tool or recording node, a recent-turn entry, or a turn list. The turn list MUST cover the selected window, be ordered newest first, and show each turn's time, source, state and receipt summary, so any turn can be chosen without leaving the map.
- **FR-016**: The detail MUST show the selected turn's timeline on one shared time axis, with one row per loop and the tool calls nested under the loop that requested them; the reply and any memory write MUST have their own rows; a failure MUST be visible without expanding a row.
- **FR-017**: Every step in the detail MUST offer its recorded data on demand: input or arguments, output preview, duration, outcome, model, token counts, stop reason, cost and error where present. A truncated recorded value MUST be marked as truncated and MUST NOT be presented as complete.
- **FR-018**: Each turn MUST show a one-line plain-language summary built only from its recorded steps (for example: question → memory skipped → 2 model calls · 1 tool · 3.2 s · $0.004). An unknown cost MUST be marked as an estimate; a missing value MUST read "not recorded".
- **FR-019**: The detail MUST make the slowest step and the most expensive step of the turn identifiable from recorded durations and costs. When either value is missing, it MUST say so rather than guess.
- **FR-020**: Every recorded step MUST be reachable as a read-only raw record for the selected turn, so any visual claim can be traced to the record that produced it.
- **FR-021**: The same stage vocabulary and state labels MUST be used on the compact turn card, on the map and in the detail, so the three cannot describe the same turn differently.

**History, honesty and data**

- **FR-022**: Any turn within the selected retention window MUST be openable from the turn list, with the newest selected by default. Turns MUST remain available after the process restarts because they are read from the recorded trajectory, not from process memory.
- **FR-023**: The retention window MUST offer today, 7 days and all, defaulting to 7 days to match the existing observability view.
- **FR-024**: Corrupted or partially written records MUST be skipped and reported with a count while the rest of the turn renders. An unknown event type MUST be named in the status line and rendered as a generic row in the detail rather than causing an error or a crash.
- **FR-025**: All displayed values MUST come from the recorded trajectory and the existing local stores. This feature MUST NOT add event types, a second turn store or a parallel status model. A turn recorded before this feature MUST open with the same steps, order, timings and costs as its record.
- **FR-026**: Redaction and truncation applied when the turn was recorded MUST be preserved. The visualization MUST NOT expose a secret or reconstruct a value that was removed.

**Scope and quality**

- **FR-027**: The feature MUST stay local. It runs inside the existing local dashboard, is reachable only on the loopback address, needs no account or cloud service, and adds no runtime service, external chart or graphics service, or build step.
- **FR-028**: The map and detail MUST remain usable at 1024-pixel width and at 200% zoom without losing essential information. Every node and control MUST be keyboard reachable, states MUST be conveyed as text or shape as well as colour, and animation MUST respect a reduced-motion preference.
- **FR-029**: With at least 200 turns in the window and a turn of at least 20 steps, the map MUST show a newly recorded step within one second, opening a turn's detail MUST complete within one second, and expanding a step MUST complete within 100 milliseconds, on a current laptop.
- **FR-030**: When live updates cannot be maintained, the map MUST say so, keep the last complete state clearly marked, and catch up when the connection returns; it MUST NOT show stale steps as live.
- **FR-031**: An empty state MUST explain that no turn has been recorded and how to start one. A loading or empty selection MUST never leave a blank view.
- **FR-032**: The visual identity MUST be this project's own. No brand assets, fonts or illustrations from the reference are copied, while the information architecture and node vocabulary may match.
- **FR-033**: The map MUST remain truthful as the product changes: a node or connection that no longer corresponds to a shipped part MUST be removed or corrected in the same change, and the map MUST NOT advertise a capability the product does not have.

### Key Entities *(include if feature involves data)*

- **Agent map**: the fixed set of nodes and connections that represent the product's parts. Each node has an id, a label, a group, a live summary and a detail destination; each connection has a source, a target, a direction and an optional label.
- **Turn**: one person message and everything the agent did in response. Carries an id, the surface it came from, the session, start and end, a state of complete, failed or unfinished, the reply, the number of model calls, its steps and its receipt.
- **Execution step**: one recorded action inside a turn — memory decision, model call, tool call, memory write, receipt or error — with a timestamp, a duration where recorded, an input, an output preview and an outcome. Each step maps to one node or connection on the map.
- **Loop iteration**: one model call together with the tool calls it requested. Has a number, model, token counts, stop reason, duration, cost and outcome.
- **Receipt**: the turn's accounting — model calls, tool calls, tokens in and out, cost, and whether the cost is an estimate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After watching a scripted turn with two tool calls, at least 4 of 5 first-time viewers correctly identify where the turn entered, which node was active at a given moment, and whether memory was consulted, within 60 seconds and without opening a log.
- **SC-002**: Across 20 scripted turns, at least 95% of recorded steps light the correct node within one second of being recorded, 100% do so by the time the turn ends, and zero steps light the wrong node.
- **SC-003**: For a fixture of 50 recorded turns, every turn opens in the detail with exactly the recorded number, order, durations, outcomes and costs; there are zero discrepancies among the turn card, the map summary and the detail.
- **SC-004**: A turn started in the terminal appears on an already-open map without manual refresh within two seconds in at least 19 of 20 trials, and watching changes that turn's duration by less than 5%.
- **SC-005**: Every failure fixture — memory decision, model call, recovered tool call, memory write and unfinished turn — shows the failure or unfinished state and its recorded message; zero failures are hidden and zero failed turns appear as successes.
- **SC-006**: In a 7-day window with 200 turns and a 20-step turn, a newly recorded step appears within one second, opening the detail takes under one second, and expanding a step under 100 milliseconds on a current laptop.
- **SC-007**: Zero credentials or unredacted secret-shaped values appear in the map, status line, detail, summary or raw view across the redaction corpus.
- **SC-008**: In a five-person check, 4 of 5 can answer "where did memory run?", "what did it cost?" and "what failed?" for a given turn within 15 seconds each, using the map and its detail.
- **SC-009**: A turn recorded before this feature renders with identical steps, order, timings and costs after it ships, and no change to how turns are recorded is required.
- **SC-010**: Closing the browser tab or losing the connection mid-turn neither cancels nor fails the turn in 20 trials, and a reconnecting viewer shows each recorded step exactly once and in order.
- **SC-011**: The map contains zero nodes or connections for capabilities outside its scope — retired features and the command-line eval/release tooling — and 100% of node links resolve to a shipped view; a test fails when either claim is false.
- **SC-012**: A keyboard-only user can reach every node, hear or read its state, and open its destination in 100% of cases; the text alternative exposes the same node states as the visual map.

## Assumptions

- **Reference and chosen shape**: `~/Projects/Private/waku-agent` stays on disk, unmodified, as the side-by-side comparison for the Overview anatomy: an architecture map that lights up as a turn flows, node summaries, a status line, and per-turn detail behind it. The user chose that shape over a per-turn-path-only view on 2026-11-18. Its brand assets, fonts and illustrations are not copied; the project keeps its own identity.
- **Built on the existing core**: this feature deepens the dashboard, turn card and observability work specified in `001-waku-minimal-core`; it does not replace the terminal timeline, the raw trajectory or the existing receipts. The 7-day window and the one-turn-at-a-time server policy stay.
- **Map coverage is this product's runtime four pillars**: surfaces, harness, memory and the runtime part of operations (trajectory, observability, cost), using this project's own names and actual parts. Retired capabilities stay retired and off the map; waku's graph workflows, model and memory arenas, comparison lab, tools marketplace, and hosted, voice or multi-channel surfaces are not added by this feature. Evals and release remain command-line-only on 2026-11-18 (confirmed choice B): they are not drawn, no placeholder is shown, and the map does not gain an eval runner or a release history store.
- **The map is the landing view**: opening the dashboard shows the map; the chat dock and the existing views remain reachable. A person who prefers the old landing view can still reach chat in one action.
- **The existing record is sufficient**: stage start times and durations are derived from what is recorded today. A detail that was not recorded is displayed as "not recorded", never estimated or reconstructed. If planning proves a required value is missing, the remedy is an additive, versioned field that older readers can ignore — not a second store and not a fabricated value.
- **Live observation is read-only and multi-viewer**: all surfaces on the same home record into the same trajectory, so a browser can follow a terminal turn. Watching never consumes the turn lock or changes the turn's timing.
- **Defaults**: map landing view, newest turn selected, live-follow on, 7-day window, and the compact stage strip remains on every turn card.
- **Data bounds**: previews stay bounded as they are today; the map and detail show what the record holds and do not promise the full model context.
- **Delivery constraints**: local-only, loopback address, no authentication, single user, no new runtime dependency, no browser build step — inherited from `001-waku-minimal-core`.
- **Accessibility target**: WCAG 2.1 AA behaviours for keyboard access, contrast, motion preference and text alternatives on the map and detail; a formal external audit is not part of this version.
- **Benchmark machine**: "current laptop" in the success criteria means the development machine used for this project's performance check, recorded with the measured fixture when the feature is planned.
- **Retention**: nothing is deleted automatically. The "all" window reads every trajectory present on disk; pruning is not part of this feature.
- **Failure semantics**: a tool error that the model recovers from does not fail the turn, but it remains visible as a failed tool node and step; a failure in the memory decision, model call or memory write marks the turn failed.
- **Map truthfulness**: the map is maintained with the product, not as a marketing illustration. A node that stops corresponding to a shipped part is removed or corrected in the same change, and no node advertises a capability that is not built.

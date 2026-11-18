# Feature Specification: Runtime-Accurate Live Highlighting

**Feature Branch**: `004-runtime-highlight-fidelity (spec directory; no branch was created)`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "修复 overview 各可视化组件高亮未和AI调用运行时一一匹配"

**Scope reference**: the **Overview** map served by the local dashboard — its nodes, its connections, the
state word on each, the status line, the text alternative and the recent-turn list. Nothing else.

**Depends on**: `specs/002-execution-flow-visualization` (the map, its graph, its event vocabulary and the
live feed) and `specs/003-neobrutalist-dashboard` (how each state is drawn). This feature changes **which
component lights, when it lights, how long it stays lit and what state it reports**. It changes no colour,
shape, position, label, route or data field.

## Why this feature exists

The map makes one promise: *the lit part is the part working now*. Today it cannot keep that promise. The
lighting is a delayed replay of completion stamps on a fixed beat, not a picture of the run:

- **A light means "finished", not "happening".** A model call that takes 2.5 s lights its component only when
  the answer arrives; for those 2.5 s the map still shows the previous step. Measured on a scripted turn: the
  memory decision took 1.2 s and lit at 1.21 s; the first model call took 2.5 s and lit at 3.71 s; the second
  took 2.5 s and lit at 6.22 s. The map showed the step before the one being worked on, for exactly as long as
  the current one took. Only the very first step — the message reaching a surface — happens to line up.
- **"Running" is a fixed pulse.** Every highlight shows running for roughly 650 ms and then done, whatever the
  step's real length. A component reading "running" therefore never means it is running.
- **The sequence runs on an invented clock.** Highlights advance on a fixed ~550 ms beat, so two steps recorded
  1 ms apart are shown half a second apart, and a turn loaded mid-flight replays in roughly 3.9 s no matter how
  long it really took. The rhythm on screen is unrelated to the rhythm of the run.
- **Counts do not match.** Two model calls and two tool calls collapse into four pulses of two reused
  components. Nothing on screen says which round of the loop is in flight or how many tool calls this turn has
  made.
- **The last model call is mislabelled.** The call that actually produces the answer is presented exactly like a
  call that is about to request a tool.
- **Some lights have no runtime counterpart, and some work has no light.** The working-context component
  relights on every model call although the context is assembled once, at the start of the turn, and nothing
  about it changes between calls. The trajectory component lights only at the spend summary and again at the
  very end, although the record is being written from the first step onward — and reads "not reached" for the
  whole turn in between.
- **Some runtime activity never lights at all.** The memory decision is itself a model call — often seconds long
  — and it shows only when it has already returned. Memory retrieval, context trimming and the memory write's
  progress are invisible.
- **States are missing or wrong.** `degraded` and `partial` exist in the vocabulary and are never shown. Memory
  components read "not reached" when memory was deliberately skipped. Operations components read "not reached"
  after every turn although they are not stages of a turn. With memory turned off the gate reads "not reached"
  instead of "not configured".
- **A dead turn poses as live.** A turn whose process died before its end is still reported as the running turn
  forever: every visit replays it and leaves the status line on its last step. Confirmed against a record two
  days old.
- **Joiners see a different runway.** Opening Overview mid-turn replays every recorded step on the made-up beat;
  when the backlog is long the queue is collapsed into instant changes. A person who opens the page during a
  turn never sees the same sequence as a person who was already watching.

The result is the one failure this surface cannot afford: a person looks at the map to find out what the agent
is doing, and the map answers with something that did not happen that way.

## What "one-to-one" means in this feature

One-to-one is a claim about **correspondence**, and it is the whole specification:

1. **One step, one light.** Every runtime step that has a component on the map produces exactly one highlight on
   exactly that component (or that explicit pair of components, where one step genuinely touches two). No step
   lights two components that were not both used; no component lights twice for one step.
2. **Start-aligned.** The highlight begins when the step begins, not when it ends. A step still in flight is
   shown as running.
3. **Duration-faithful.** The running state lasts as long as the step lasts. Very short steps get a short
   minimum dwell so they are visible, but that dwell never reorders or merges steps.
4. **Countable.** Repeated steps stay countable while the turn runs: which round the loop is in, how many tool
   calls this turn has made.
5. **Outcome-faithful.** When a step ends, the component reports the outcome that was recorded — done, failed,
   skipped, degraded, or partial — and never a state the record does not support.
6. **Nothing phantom, nothing silent.** A component may not light without a runtime step behind it, and a
   runtime step with a component may not stay dark. Anything not drawn on the map is still named in the status
   line rather than dropped.
7. **Truthful after the fact.** After the turn ends, and for a turn that never ended, every component's state
   says what the record says — including "this never ran", "this was skipped", "this is not configured" and
   "this never finished", which are four different statements.
8. **Same story for every viewer.** Someone who opens the page mid-turn, someone with reduced motion and a
   screen reader reading the text alternative all get the same steps in the same order and the same final
   state; catching up is announced, never disguised as a live replay.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Watch a turn and believe the map (Priority: P1)

A person asks a question from the composer and switches to Overview. For the whole turn, the component marked
running is the one whose step is actually in flight — the memory decision while the gate's model call runs, the
model while it reasons, the tool while it executes, the memory write while it writes. Each step produces one
highlight, in the order it happened, lasting about as long as it took. When a step ends the map settles it to
its recorded outcome and lights the next one. When the turn ends the map holds the finished picture briefly and
returns to idle.

**Why this priority**: this is the map's only reason to exist, and the defect the request names. A map that
lags, pulses and invents a rhythm is worse than no map, because it is read as truth.

**Independent Test**: run a scripted turn with a 1.2 s memory decision, a 2.5 s model call, one tool call and a
2.5 s final model call, sampling the map every 100 ms. The component in the running state matches the step in
flight in at least 95% of samples and no sample shows a component running while nothing is in flight. The total
number of highlight transitions equals the number of recorded steps, in the recorded order.

**Acceptance Scenarios**:

1. **Given** an idle Overview, **When** a message is recorded as the start of a turn, **Then** the surface component lights at that moment — not after the memory decision returns — and the status line names the step that is starting.
2. **Given** a model call in flight for 2.5 s, **When** the person watches, **Then** the model component reads running for the whole call (within 150 ms at each end), no other component reads running, and the status line names the model step; **When** the call returns with a tool request, **Then** the model component settles to done and the tool component lights for its own execution.
3. **Given** one turn with three model calls and two tool calls, **When** it runs, **Then** the map shows five distinct step transitions in recorded order, the round number and this turn's tool-call count are readable while it runs, and no two steps are merged into one visual event.
4. **Given** the final model call that returns the answer rather than a tool request, **When** it lands, **Then** it is labelled as the final answer and is distinguishable from the iterations that requested tools.
5. **Given** a step that completes in under 100 ms, **When** it lights, **Then** it is visible for a short minimum dwell, the steps around it keep their order, and the map is never more than one second behind the record.
6. **Given** the turn ends, **When** the last step is recorded, **Then** the finished picture holds for 0.5–2 s, every component that ran keeps its recorded outcome, no component that never ran has ever been shown running, and the map returns to idle.
7. **Given** a step that fails, **When** it lands, **Then** its component turns failed at that instant, the status line names the failure, and the components of steps that never ran are not marked failed.

---

### User Story 2 - Read a finished turn's map and get the truth (Priority: P2)

After the turn, and when opening any recorded turn, the person reads each component's state as the record has
it: the gate says skipped when memory was skipped and the memory components say they were not used (not "not
reached"); a failed tool is failed; a gate that failed open is degraded; with memory turned off the gate says
not configured; a record that never finished leaves its last in-flight step partial and never claims the turn
is still running; operations components that merely summarise a turn are not labelled "not reached".

**Why this priority**: the map is consulted after the fact more often than during a run, and a wrong word is
harder to disprove than a wrong moment. It is second because it can be tested against recorded fixtures without
a live turn, and because a viewer who does not trust the words will not use the live view either.

**Independent Test**: replay twenty recorded turns covering skip, retrieve, failed tool, gate failure, memory
disabled and an unfinished record; compare each component's final state word with the record. All 20 agree.

**Acceptance Scenarios**:

1. **Given** a skipped memory decision, **When** the turn's map is read, **Then** the gate reads skipped with its recorded reason and the memory components read skipped (not used this turn), never not reached.
2. **Given** a retrieved memory, **When** the gate lands, **Then** the gate and the memory path light together with the recorded decision, and the memory components settle to done.
3. **Given** a gate that failed open, **When** it lands, **Then** the gate reads degraded with the failure reason, is not presented as a healthy retrieval, and the turn continues.
4. **Given** memory is not configured, **When** any turn runs, **Then** the gate reads not configured, is not skipped, failed or not reached, and the turn is unaffected.
5. **Given** an unfinished record, **When** the map settles, **Then** the last in-flight step reads partial, the status line says the turn is not running, and no other component is marked as if the turn completed.
6. **Given** any completed turn, **When** the map settles, **Then** the operations components read their idle summaries rather than not reached, and components the turn did not need read not used rather than not reached.
7. **Given** an unknown or future record type, **When** it arrives, **Then** the status line names it as unmapped, no component lights for it, the rest of the turn still lights, and the raw record is kept.

---

### User Story 3 - Join mid-turn, come back later, and never be told a stale story (Priority: P3)

A person opens Overview while a turn started in the terminal is already running, or returns hours later after a
turn was interrupted. Opening mid-turn lands them on the component that is in flight *now*, announcing that
they have caught up rather than replaying old steps as if they were live. An interrupted turn is reported as
not running and its last step as partial. Someone who joins late and someone who watched from the start end up
looking at exactly the same picture.

**Why this priority**: it protects the credibility of the other two stories in the situations where the map is
least able to defend itself — a viewer with no prior context, and a record that ends without an ending.

**Independent Test**: begin a scripted turn, open Overview 2 s into a 6 s turn, and let both the original and
the joining viewer settle. Both show the same steps in the same order after the join and the same final state;
the joiner is never shown an old step as running. Separately, kill the process mid-turn and reload after ten
seconds: the map reports the turn as not running.

**Acceptance Scenarios**:

1. **Given** a turn in flight, **When** the person opens Overview, **Then** the map shows the step in flight now, the status line says it caught up, and no replayed step is presented as running.
2. **Given** a viewer that fell behind by more than one second of steps, **When** it catches up, **Then** it jumps to the true current state and says so, instead of replaying the backlog at a fabricated pace.
3. **Given** two viewers, one present from the start and one joining mid-turn, **When** the turn ends, **Then** both show the same final state and the same step order from the join point.
4. **Given** a record whose process died before the end, **When** the page is opened later, **Then** the map reports it as not running with its last step partial within five seconds, and nothing is replayed as live.
5. **Given** a viewer with reduced motion enabled, **When** the same turn runs, **Then** the correspondence, order and final state are unchanged and no animation plays.
6. **Given** a screen reader or the text alternative, **When** the same turn runs, **Then** it names the same running component, in the same order, with the same state words.

---

### Edge Cases

- **No turn has ever run**: idle, no highlight, nothing claimed as running.
- **A step completes before the viewer's first paint**: it must appear, in order, without being skipped.
- **A burst of steps** (20 or more in a turn): every step is shown; the map never lags the record by more than one second; if it must collapse, it collapses to the true current state and says so — it never invents intermediate steps.
- **Two steps recorded with the same timestamp**: both are shown, in record order; neither is dropped as a duplicate.
- **Instant steps** (a tool returning in 0 ms): visible for a short minimum dwell, order preserved.
- **Model streams its answer**: the model component stays running through the stream and settles when the call completes; streamed text is not a step of its own.
- **Failure at the memory decision**: gate degraded, memory path untouched, turn continues.
- **Failure at the model call**: model failed, later components not reached, status names the failure, and no reply is claimed.
- **Recovered tool failure**: only the tool component is failed and the turn still completes.
- **Memory disabled entirely**: gate not configured, memory components idle, no false skip or failure.
- **Consolidation not triggered**: the consolidation component stays idle with its summary, not not-reached.
- **A new turn starts while the previous is settling**: the new turn takes over the map immediately, no stale highlight remains, the previous turn stays in the list.
- **Two overlapping turns** (a terminal turn and a dashboard turn at the same time): the map follows the most recently started turn and the status line names its source; the overlap is reported, not silently merged.
- **Corrupted line**: reported as a count without replacing the name of the current step; the rest of the turn still lights.
- **Feed drops**: the map marks itself stale, keeps the last complete state, and resumes without replaying old steps as live.
- **A record written by an earlier version** (no start information): it still opens, still lights in recorded order, and never claims a running interval the record cannot support.
- **Very long status or summary**: wrapped or truncated in place, never widening the page.
- **Narrow window, 200 % zoom, forced colours**: highlighting remains perceivable; no state relies on hue alone.

## Requirements *(mandatory)*

### Functional Requirements

The requirements are grouped by the claim each group protects: correspondence, truthfulness, completeness,
viewer fairness, record sufficiency, and the quality floor this surface already holds.

#### Correspondence

- **FR-001**: Every highlight, state word and stated duration on Overview MUST be derived from the turn's record. No component may change state without a recorded step, and the viewer MUST NOT infer or simulate activity that the record does not show.
- **FR-002**: A component MUST enter its running state when its step starts, not when it ends, including while the step is still in flight — with a start accuracy of 150 ms or better.
- **FR-003**: A component MUST remain running for as long as its step is in flight, and MUST settle to the recorded outcome when the step ends. Sub-100 ms steps MAY receive a short minimum dwell, provided the dwell neither reorders nor merges steps.
- **FR-004**: Each recorded step MUST produce exactly one highlight, on exactly the component or components that step used. Repeated steps (each model call, each tool call) MUST remain individually and countably visible, and the status line MUST state the current loop round and this turn's tool-call count while it runs.
- **FR-005**: Connections MUST show the direction of the step in flight: the edge into a component when the step starts acting, the edge back out when its result flows on; no edge may light for a flow that did not occur.
- **FR-006**: A component MUST light only for the activity it depicts, and MUST NOT relight for a step that did not change it. The working-context component lights when the context is assembled for the turn, not on every model call; the trajectory component shows the record being written, not the turn's ending; the spend component shows cost the turn has actually accrued and recorded. No component may stand in for another.

#### State truthfulness

- **FR-007**: The eight visual states (idle, running, done, skipped, degraded, failed, not reached, partial) MUST each mean exactly what the record says: skipped = deliberately not used; not reached = a stage the turn would have reached but did not; partial = a step that started and never ended; failed = the recorded failure of that step. The vocabulary does not grow: "not used this turn" is the skipped state read with its reason, and "not configured" is an idle component whose text says the capability is absent.
- **FR-008**: A skipped memory decision MUST leave the memory components skipped, never not reached; a gate that failed open MUST be degraded; when memory is not configured the gate MUST stay idle and say so in its text; an unfinished turn MUST mark its last in-flight step partial and never present itself as running.
- **FR-009**: Components that are not stages of a turn (the operations group) MUST NOT be marked not reached when a turn ends; they keep their idle summaries.
- **FR-010**: When a turn ends, every component that ran MUST hold its recorded outcome for 0.5–2 s before the map returns to idle; a new turn MUST take over immediately; no highlight may persist indefinitely.

#### Completeness and honesty

- **FR-011**: Every runtime step that has a component MUST light it. A step that has no component MUST still be named in the status line rather than dropped silently, and an unknown or future record type MUST be named as unmapped without lighting anything.
- **FR-012**: The status line MUST name the step that is actually in flight and MUST update when that step starts. Notices that are not steps (skipped lines, reconnect, catch-up) MUST NOT replace the name of the current step.
- **FR-013**: A turn that never recorded an end MUST stop being presented as running within 5 s of the page loading or of the last step, MUST mark its last in-flight step partial, and MUST NOT be replayed as live on later visits.
- **FR-014**: A new turn MUST clear the previous turn's highlight; the previous turn MUST remain readable in the recent-turn list and its detail.

#### Joining, catching up and multiple viewers

- **FR-015**: Opening Overview during a turn MUST land on the true current state — the step in flight now — and MUST announce that the viewer caught up. It MUST NOT replay already-recorded steps as if they were happening.
- **FR-016**: When a viewer falls behind the record by more than one second, it MUST jump to the true current state and say so, rather than replaying the backlog at a fabricated pace. The displayed state MUST never lag the record by more than one second.
- **FR-017**: A viewer that joined mid-turn and a viewer present from the start MUST show the same steps in the same order from the join point and the same final state.
- **FR-018**: Watching MUST remain read-only and independent: any number of viewers, no viewer blocks or alters a turn, and one viewer's catch-up never affects another.

#### Record and compatibility

- **FR-019**: The turn record MUST be sufficient to place every highlight on the real timeline. For every step that can last longer than 200 ms, the record MUST carry when it started and when it ended (or an equivalent from which both are recoverable); a turn recorded by the new version MUST support exact start alignment.
- **FR-020**: Adding that information MUST be backward compatible: existing consumers keep working, redaction and truncation are unchanged, and no second turn store, parallel status model or invented value is introduced.
- **FR-021**: Turns recorded before this feature MUST still open, light in recorded order with their recorded durations where present, and MUST NOT be shown with a running interval the record cannot support.
- **FR-022**: The map's graph, layout, node labels, destinations and summaries MUST NOT change; this feature changes states and their timing only.

#### Accessibility and quality

- **FR-023**: The text alternative and every component's accessible name MUST carry the same running component, the same order and the same state words as the map, updated as the turn runs.
- **FR-024**: Highlighting MUST remain perceivable with reduced motion (instant state changes, same correspondence), in forced-colours mode, and for the eight states without hue; no state may rely on hue alone.
- **FR-025**: Highlight updates MUST NOT move the layout, scroll a region, steal focus or delay the composer; keystroke echo stays under 100 ms while a turn streams and the map stays interactive.
- **FR-026**: The feature MUST remain local and dependency-free: no new runtime service, external asset, build step or network request.

### Key Entities

- **Turn record**: the append-only account of one run — its steps, their order, their start and end, their outcome, and the surface that started it. The only source for everything above.
- **Runtime step**: one unit of work the agent performs that the map can show — a memory decision, a model call, a tool call, a memory write, the reply, the end. Each carries a start, an end, an outcome and the component it belongs to.
- **Component highlight**: one appearance of a state on one component — which component, which state word, which interval, which position in the turn's order.
- **Correspondence**: the one-to-one link from a runtime step to its highlight; the audit of this link is the acceptance test for the feature.
- **State vocabulary**: the eight words and the rule that says which record fact justifies which word.

## Relationship to prior specifications

- `002-execution-flow-visualization` FR-009 (light every event in recorded order) stays; this feature adds *when* — start alignment — and *for how long*.
- FR-010 (lighting reflects what happened) is tightened: the four distinctions skipped / not reached / not configured / partial become mandatory, and components that are not stages are excluded.
- FR-013 (no silent drops, max one second of lag) stays; its catch-up behaviour is corrected so catching up never fabricates a running sequence.
- FR-014 (settle) stays, with the added rule that an unfinished turn never settles into a running state.
- FR-025's "no new event types" was written to forbid a second turn store and a parallel status model. That intent stands. If truthful start alignment requires adding start information to the record, the plan must record the amendment explicitly and keep the record backward compatible; adding a second source of truth remains forbidden.

## Out of Scope

- The Chat view's turn card, the terminal chat, the `byo trajectory` renderer and any command-line output.
- The map's geometry, groups, nodes, connections, labels, destinations, palette, typography and layout.
- New components, pages, views, routes, settings or data stores.
- Rewriting or back-filling already-recorded turns.
- Simultaneous multi-turn visualisation beyond the defined overlap behaviour; parallel sub-agents do not exist in this product.
- Evals, release, voice, MCP and other retired or command-line-only surfaces remain absent from the map.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a scripted turn of seven steps (memory decision 1.2 s, model 2.5 s, one tool, model 2.5 s, memory write, spend, end), a captured timeline shows exactly seven step transitions in recorded order, and the step in flight is the running component in at least 95% of 100 ms samples, with zero samples showing a step component running while no step is in flight; the trajectory component is running exactly while the turn is.
- **SC-002**: Every step lasting 200 ms or longer starts its highlight within 150 ms of the step's recorded start, in 100% of steps, over ten recorded turns.
- **SC-003**: An audit of twenty recorded turns finds zero highlights without a corresponding step and zero steps with a component that stayed dark.
- **SC-004**: An audit of twenty recorded turns covering skip, retrieve, failed tool, gate failure, memory disabled and unfinished records finds the component's final state word correct in 100% of cases.
- **SC-005**: A turn whose process is killed mid-flight is reported as not running with its last step partial within 5 s of loading, in 10 of 10 trials, and is never replayed as live on a later visit in 10 of 10 trials.
- **SC-006**: A viewer joining 2 s into a 6 s turn and a viewer present from the start report the same final state and the same step order from the join point, in 5 of 5 trials, with zero replayed steps shown as running.
- **SC-007**: A turn with 20 or more steps lights every step, drops none, and stays within one second of the record; the page remains scrollable and responsive throughout.
- **SC-008**: The text alternative names the same running component as the map in at least 95% of 100 ms samples during the scripted turn, and lists the same order and the same state words.
- **SC-009**: A hundred turns recorded before this feature open with the same steps, order, durations and costs, and none is shown with a running interval the record cannot support.
- **SC-010**: The layout does not move when highlights change: every component's position is identical before and after a turn, and the page acquires no horizontal scrollbar beyond the map's own region.
- **SC-011**: With reduced motion enabled, the same turn produces the same order, correspondence and final state with zero animation, verified on the scripted turn.
- **SC-012**: Under a live turn, keystroke echo in the composer stays under 100 ms and the map remains interactive, measured on the scripted turn.

### Qualitative Outcomes

- **SC-013**: Five people watching the same recorded turn, asked "which part of the agent is working right now", answer correctly in 5 of 5 attempts at three different moments of the turn.
- **SC-014**: Five people asked "did this turn use memory?" after watching a skipped-memory turn answer correctly in 5 of 5 attempts without opening the detail.

## Assumptions

- **The complaint is about correspondence, not decoration.** "高亮未和AI调用运行时一一匹配" is read as: the wrong component lights, at the wrong time, for the wrong length, in the wrong state, with steps merged or missing. Visual identity from `003` is preserved; nothing about it is revisited.
- **"AI call runtime" means the run itself**, including the memory decision, whose implementation is itself a model call and therefore one of the slowest steps of a turn.
- **One-to-one is at step granularity, not token granularity.** A streaming model call is one step; its deltas are not highlights.
- **Truthful start alignment may require the record to say when a step began.** That is treated as an acceptable, additive, backward-compatible change; a synthetic client-side timer that guesses when a step started is not acceptable, because it would reintroduce a parallel status model.
- **Tolerances**: 150 ms at a step boundary, 1 s maximum lag, 0.5–2 s settle, and a minimum dwell in the 100–200 ms range for instant steps. These are engineering values chosen to make the claim testable, not user settings.
- **The canonical evidence is the record.** Every acceptance test above can be run offline against recorded turns with a scripted model; no live API call is required.
- **Desktop remains primary** (1440×900 canonical, usable at 900 and 375); no new responsive behaviour is introduced.
- **Existing tests and the offline eval suite must keep passing**, and this behaviour change requires an eval that measures correspondence before and after, per the project constitution.
- **One user, one local machine**; the dashboard remains loopback-only and unauthenticated.
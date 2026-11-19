# Feature Specification: Chat Stream Persistence Across Navigation

**Feature Branch**: `009-chat-stream-persistence`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "Fix chat 流式输出时，切换菜单栏，chat输出会丢失"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A streaming answer survives sidebar navigation (Priority: P1)

A person sends a message in the chat dock. The agent is still answering when the person clicks
another sidebar destination — Tools, Memory, Observability or Settings — to look at something
while waiting. Today that click clears the live card, and every fragment that arrives afterwards
is silently discarded; the chat sits empty until the turn happens to finish, and the answer
never streams. The person should be able to browse the dashboard and come back to find the
answer where it would have been: everything received while away is still there, in order, and
the stream keeps flowing.

**Why this priority**: This is the reported defect and the smallest journey that fixes it — one
message, one navigation, no lost output. Without it, every multi-second answer punishes the
person for looking at anything else.

**Independent Test**: With a scripted model that emits a numbered fragment every 200 ms (20
fragments), send a message; after fragment 5 switch to Tools; after 10 more fragments switch
back to Overview; let the turn finish. Verify the live card showed fragments 1–20 exactly once,
in order, with no restart and no gap, and that the transcript then contains the complete reply.

**Acceptance Scenarios**:

1. **Given** a turn streaming in the chat dock, **When** the person selects any other sidebar destination, **Then** the live reply keeps accumulating and the chat dock continues to show the turn — thinking, tool and output entries included — unless the person has collapsed the dock.
2. **Given** several fragments arrived while another destination was displayed, **When** the person returns to the chat, **Then** the live card shows every fragment received so far, in the original order, each exactly once.
3. **Given** the person changes destination before the first fragment, or while the memory gate or a tool call is pending, **When** the turn continues, **Then** the turn is not cancelled and its pending indicator, and then its content, appears normally.
4. **Given** the person switches destinations repeatedly (at least ten times) during one stream, **When** the turn finishes, **Then** the accumulated output and every thinking and tool entry are identical to a run with no navigation, with no duplicated or reordered text.

---

### User Story 2 - Completion while away leaves one clean transcript (Priority: P2)

The answer finishes while the person is reading another view or another chat. The live card must
give way to exactly one transcript entry for the turn: the user's message, the assistant's reply,
and the folded thinking and tool trace — with no duplicate reply and no missing last lines. The
chat dock updates in place without a reload, and the person is not yanked back to Overview.

**Why this priority**: It closes the handoff that begins in P1. Preserving the stream is not
enough if completion then duplicates the reply, drops its tail, or leaves a stranded live card.

**Independent Test**: With a scripted model that emits fragments and then completes after a
pause, switch to Memory before completion; wait for the turn to complete; inspect the dock while
still on Memory, then return to Overview. Verify one user message and one assistant reply for
the turn in both places, the live card gone, no duplicated reply and no truncated tail.

**Acceptance Scenarios**:

1. **Given** a turn completes while another destination is displayed, **When** the person looks at the still-open chat dock, **Then** it shows the completed turn once, without a page reload and without changing the selected destination.
2. **Given** the person returns to Overview after completion, **Then** the transcript contains exactly one user message and one assistant reply for that turn, matching the text that streamed.
3. **Given** the turn ends in failure or at the step limit while the person is away, **Then** the completed transcript preserves the partial output and states the failure or limit plainly, and no blank live card remains.
4. **Given** completion coincides with a destination change, **Then** the person sees either the live card or the transcript, never both and never neither, and the reply appears exactly once.

---

### User Story 3 - Other shell actions do not disturb the live turn (Priority: P3)

The person collapses and reopens the chat dock, resizes it, flips the theme, expands a trace in
the history, opens a turn's detail, or selects a past chat while the answer is still streaming.
None of these actions may cancel, blank, restart or duplicate the in-flight turn. A live turn
belongs to the chat it was sent from: selecting a past chat must not show the live turn inside
that chat, and returning to the sending chat must show it intact. Starting a new chat must not
paint the previous turn's live card over the new chat.

**Why this priority**: These are the same root cause at lower frequency. They matter because a
person waiting for a slow answer naturally pokes at the surrounding controls.

**Independent Test**: With a slow scripted stream, collapse the dock, reopen it, resize it, toggle
the theme, select a past chat, then return to the sending chat; verify the accumulated output is
complete and in order after every step, the stream finishes normally, and the live card was never
shown inside the past chat.

**Acceptance Scenarios**:

1. **Given** a live turn, **When** the chat dock is collapsed and reopened, **Then** the accumulated output and the running indicator are intact and the stream continues.
2. **Given** a live turn, **When** the person resizes the dock, changes the theme, expands a history trace or opens a turn detail, **Then** the live turn keeps its content and continues.
3. **Given** a live turn in the current chat, **When** the person selects a past chat, **Then** the past chat shows only its own history, the live turn is neither shown there nor cancelled, and selecting the sending chat again restores the full accumulated live turn.
4. **Given** a live turn, **When** the person starts a new chat, **Then** the new chat does not display the previous turn's live card, and that previous turn is still available, completed, in its own chat.

---

### Edge Cases

- The person navigates away and back before any fragment arrives: the live turn is present with its pending gate or thinking indicator, not blank.
- A burst of fragments arrives at the exact moment of a destination change: every fragment is applied once, in emission order.
- The person stays on another destination for the whole turn: the turn completes and is recorded, and the next time the chat is shown it contains exactly one entry for that turn.
- The turn completes while the dock is collapsed: nothing is stranded; reopening the dock shows the completed transcript, not a stale live card.
- The person selects chat sessions twice while streaming and ends on the sending chat: the live turn is intact on return.
- Failure, step limit, or an empty reply while away: partial output is preserved, the ending is stated, and no completion is fabricated.
- The dashboard is reloaded or closed mid-turn: live streaming cannot be resumed inside the page (out of scope), but the turn must still finish and be recorded, and the next load shows the completed turn once.
- Two dashboard tabs are open on the same deployment: each tab keeps its own live view; cross-tab synchronisation is out of scope.
- The person sends a second message while the first turn is live: it is still refused, and no second live card is created.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: In-app navigation MUST NOT clear or discard the live turn. This covers selecting any sidebar destination (Overview, Tools, Memory, Observability, Settings), following a map-node link to another destination, and using back or forward within the dashboard.
- **FR-002**: While another destination is displayed and the chat dock is open, the live turn MUST continue to render and update there, so the person can watch the answer arrive without returning to Overview.
- **FR-003**: Every fragment received during navigation MUST be applied exactly once, in emission order; navigation MUST NOT produce a gap, a duplicate, a reordering, or a restart of the accumulated text.
- **FR-004**: On return to the chat, the accumulated content MUST be shown immediately from the live turn's preserved state — no page reload, no waiting for the turn to finish, and no blank intermediate render.
- **FR-005**: Navigation before the first fragment, or while the memory gate or a tool call is pending, MUST preserve the turn and its pending indicators; the pending step MUST resolve into its content in the normal position.
- **FR-006**: A live turn MUST remain attached to the chat that sent it. Selecting another chat MUST NOT display the live turn inside it and MUST NOT cancel the turn; returning to the sending chat MUST restore the full accumulated turn; starting a new chat MUST NOT display the prior turn's live card over the new chat.
- **FR-007**: Collapsing and reopening the chat dock, resizing it, changing the theme, expanding a history trace, and opening a turn detail MUST NOT alter the live turn's content or interrupt its stream.
- **FR-008**: On completion, the live card MUST be replaced by exactly one transcript entry for the turn: one user message and one assistant reply, with the reply text complete, the thinking and tool trace available, and the live card removed. The final reply MUST NOT be duplicated or truncated.
- **FR-009**: Completion while another destination is displayed MUST update the chat dock in place; it MUST NOT change the selected destination, force a return to Overview, or require a reload.
- **FR-010**: A turn that ends in failure or at the step limit MUST preserve its partial output and state the ending plainly across navigation; navigation MUST NOT erase that content or present a fabricated completion.
- **FR-011**: In-app navigation MUST NOT cancel the turn; the agent MUST finish it and record it in history regardless of which destination or chat is displayed.
- **FR-012**: A full page reload, tab close, or leaving the dashboard MUST NOT cancel the turn; it MUST finish and be recorded, and a later load MUST show the completed turn exactly once. Resuming the live stream in the page is not required.
- **FR-013**: The handoff from live card to transcript MUST be atomic at every destination: the reply is visible exactly once, never simultaneously as a live card and a transcript entry, and never momentarily absent.
- **FR-014**: The change MUST add offline deterministic regression coverage for at least: one mid-stream destination switch, repeated rapid switches, a switch before the first fragment, a switch while a tool call is pending, completion while away, failure while away, past-chat selection, and dock collapse and reopen.
- **FR-015**: Behaviour with no live turn MUST be unchanged: switching destinations still renders the same view content and history as before, and no new network service, credential or configuration setting is introduced.
- **FR-016**: Single-turn behaviour MUST be preserved: a second message while a turn is running is still refused and MUST NOT create a second live card.

### Key Entities *(include if feature involves data)*

- **Live turn**: the in-flight turn as the dashboard holds it — the user's message, the accumulating gate, thinking, tool and output entries, the receipt, the ending state, and the chat it belongs to. It exists only while the page keeps it; it is the thing navigation must not lose.
- **Transcript entry**: the completed record of one turn — the user's message, the assistant's reply, and the folded thinking and tool trace, loadable after the fact. Exactly one exists per completed turn.
- **Chat session**: the identity of a conversation. A live turn belongs to exactly one chat session; a transcript entry belongs to the session it was sent from.
- **Dashboard destination**: the section currently displayed (Overview, Tools, Memory, Observability, Settings). Choosing one is navigation, not a change to the chat itself.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of runs that switch destinations mid-stream — including 50 randomised switch timings and ten rapid switches in one turn — the accumulated reply after each return matches the fragments received exactly, with zero lost, duplicated or reordered characters.
- **SC-002**: A person who returns to the chat during a stream sees the content accumulated so far within 1 second of the chat being shown, with no additional wait for the turn to finish.
- **SC-003**: In 100% of turns completed while another destination is displayed, the transcript contains exactly one user message and one assistant reply for that turn; zero duplicate replies and zero missing final lines.
- **SC-004**: In 100% of turns that fail or hit the step limit while the person is away, the partial output and the failure or limit state are visible on return; zero blank or stranded live cards.
- **SC-005**: Zero turns are cancelled by navigation: 100% of streams navigated away from finish and are recorded as completed or failed in the run record.
- **SC-006**: The default offline test command passes with no network and no credentials, including the new navigation-during-stream regression scenarios.
- **SC-007**: There is no regression in the existing dashboard: 100% of the existing dashboard checks pass, and switching destinations with no live turn renders the same view content and history as before.
- **SC-008**: In 100% of simulated completion timings — including a completion that lands during a destination change — the reply appears exactly once and the selected destination does not change.

## Out of Scope

- Resuming a live stream after a full page reload, a tab close, or in a second browser tab; buffering or replaying a live turn for late joiners.
- Multiple concurrent turns, queued messages, and stopping or cancelling a turn from the interface.
- Writing partial replies into the transcript as if they were complete turns.
- Any visual redesign, new chat lane, or change to the runtime map's lighting.
- The terminal chat, which has no view navigation.
- Cross-device or cross-tab synchronisation of an in-flight turn.

## Assumptions

- The chat dock is part of the dashboard shell and is visible on every destination unless the person collapses it; FR-002 rests on that existing layout.
- One turn runs at a time: the deployment already refuses a second turn while one is in flight.
- Switching destinations stays within the same page, so the live turn survives; a full reload is a different case, covered by FR-012.
- Chat history is the record of completed turns; an in-flight turn has no transcript entry yet, so preserving it across navigation depends on the page keeping it.
- Fragments arrive in order and are text; out-of-order transport is not a design case.
- The dashboard is used on desktop and responsive layouts; both are in scope for the behaviour above.
- The turn still completes and is recorded even when the page navigates away or disconnects; this is existing behaviour to preserve, not new behaviour to build.
- The five existing destinations (Overview, Tools, Memory, Observability, Settings) are the whole navigation surface; no new destination is added by this feature.

# Feature Specification: Clearer Fact Capture and Correction in Memory

**Feature Branch**: `007-memory-facts-editing`

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "Memory 下的 Facts 增加和编辑功能增强"

**Scope note**: This feature improves the **Facts** section of the dashboard's **Memory** view —
how a fact is added and how a stored fact is edited — together with the validation and
integrity rules those two actions must obey. It does not change what the agent retrieves,
add new memory types, add tools, or alter the agent-facing fact tools (`save_note`,
`manage_memory`).

## Clarifications

### Session 2026-11-19

- Q: Should the agent's fact-writing tools (`save_note`, `manage_memory`) adopt the same add/edit rules in this iteration, or is this work limited to the dashboard's Memory view? → A: Dashboard only — the Memory view's add/edit is enhanced; `save_note` and `manage_memory` keep their current schemas, action set, validation and result text.
- Q: When a person saves an edit to a fact that has changed since they opened it, what should the system compare to decide there is a conflict? → A: Compare with the edit baseline — the subject and content shown when edit mode opened; if the stored fact differs or is gone, refuse the save and refresh. No revision or last-changed marker is stored.
- Q: How should the size limits treat a fact that is already longer than the limit when the person edits it? → A: Enforce the limits on every save — an over-limit fact must be shortened to the limit before it can be saved again; nothing is auto-truncated.
- Q: How many stored facts should the Facts section stay comfortable with in this iteration? → A: A few hundred — every fact is shown in one list; no paging, search or filtering in this iteration.
- Q: Should adding or editing a fact from the Memory view also leave a record in the activity trace, or stay outside it like a direct store change? → A: Record each change — every accepted or refused add/edit appends a structured event (fact identity, action, outcome, time) that the activity surfaces can read.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct a wrong or incomplete fact in place (Priority: P1)

A person opens **Memory → Facts** and finds a fact that is partly wrong or stale: the subject
says "alex" but it is Alex Chen, or the content says "takes coffee black" but it is now with
milk. They choose edit on that row; the row itself becomes editable with the current subject
and content already filled in. They change only what is wrong, save, and the row shows the
corrected values with a brief confirmation. If they change their mind, cancel leaves the fact
exactly as it was.

**Why this priority**: A memory the person cannot correct is worse than no memory, because the
agent keeps acting on it. Today correction can only rewrite the fact body through a separate
single-field prompt: the subject cannot be corrected, the current value is not visible while
editing, and a failed or ignored save is silent. Making correction safe and complete is the
core of this feature.

**Independent Test**: With at least one stored fact, open Facts, edit only the subject and
save; verify the row, the stored values, the fact count and the readable mirror agree, and the
fact keeps its identity, origin and creation time. Repeat for content-only, both-fields, and
cancel.

**Acceptance Scenarios**:

1. **Given** a stored fact, **When** the person chooses edit, **Then** the row offers editable subject and content fields prefilled with the stored values plus save and cancel controls, with no separate dialog that forces retyping.
2. **Given** edit mode with only the subject changed, **When** save succeeds, **Then** the subject updates, the content, origin, creation time and fact identity stay unchanged, a confirmation is shown, and both the list and the readable mirror reflect the new subject.
3. **Given** edit mode with only the content changed, **When** save succeeds, **Then** the content updates while the subject, origin, creation time and identity stay unchanged.
4. **Given** edit mode, **When** the person cancels, **Then** nothing is written, the row returns to its original values, and no confirmation implying a save is shown.
5. **Given** edit mode, **When** the person empties the subject or the content and saves, **Then** the save is refused with a message naming the field and rule, the row stays editable with the typed values, and nothing is written.
6. **Given** a save that cannot be completed because the fact was deleted or changed elsewhere, **When** the person saves, **Then** an explicit conflict message is shown, the previous values are not overwritten, the list refreshes to the current truth, and no fact is recreated.
7. **Given** a fact whose text looks like markup or a script, **When** it is displayed or edited, **Then** it appears literally as text and is never executed.

---

### User Story 2 - Capture a new fact with little friction and proof it was kept (Priority: P2)

The person adds a fact about a person, project or preference. The subject is a short label and
the content may be a sentence or a short paragraph. They type both, see guidance in place if
something is wrong, press remember once, and get an unmistakable confirmation; the new fact
appears at the top of the list, the count increases, and the form is cleared and ready for the
next fact.

**Why this priority**: Adding facts is the most frequent write to memory and the entry point
for everything else. Today an empty submit does nothing at all, content is confined to a
single line, and success has no confirmation beyond the page redrawing — so a person cannot
tell whether the agent will remember it.

**Independent Test**: Add a fact with multi-line content; verify the confirmation, the
top-of-list placement, the count, the recorded origin and creation time, and the readable
mirror. Add an empty value, a whitespace-only value, an over-limit value and an exact duplicate;
verify each is refused with a specific message and nothing is written.

**Acceptance Scenarios**:

1. **Given** the Facts section, **When** the person writes content that spans multiple lines, **Then** it is accepted and later displayed with its line breaks preserved.
2. **Given** an empty or whitespace-only subject or content, **When** the person presses remember, **Then** nothing is stored and a message identifies the field and the rule that was broken.
3. **Given** valid values, **When** the person presses remember, **Then** the fact is stored with the person as its origin and the current creation time, a confirmation appears, the fact is first in the list, the count increases, and the form is cleared for the next entry.
4. **Given** an identical fact — same subject and content after trimming, case-folding and collapsing repeated whitespace — already exists, **When** the person presses remember, **Then** no second copy is stored and a message identifies the existing fact and points at its edit control.
5. **Given** a subject longer than 120 characters or content longer than 2000 characters, **When** the person presses remember, **Then** the add is refused with a message stating the applicable limit and nothing is stored; the value is never silently truncated.
6. **Given** the store or the readable mirror fails during an add, **When** the person presses remember, **Then** an explicit error is shown and the typed values remain in the form so they can retry without retyping.

---

### User Story 3 - Every change is reflected everywhere and none is silently lost (Priority: P3)

After any add or edit, the Facts list, the fact count, what the agent can later recall, and
the readable mirror all show the same values. Every operation ends with an explicit outcome,
so the person is never left guessing. The offline acceptance suite pins these behaviors, so a
regression is caught without a person clicking around.

**Why this priority**: Trust in memory depends on the surfaces not diverging — a fact that
looks edited in the view but not in the store, or vice versa, is the same black box the
project exists to avoid. It ranks P3 because it hardens the outcomes of the first two stories
rather than introducing a new journey.

**Independent Test**: Drive a sequence of invalid and valid add/edit values through the
Memory view; after each attempt verify the change outcome, the stored values, the fact count,
the recalled values, the readable mirror and the recorded activity event agree, and that the
existing agent-facing tools still behave exactly as before.

**Acceptance Scenarios**:

1. **Given** the Memory view is open in two places, **When** a fact is added or edited in one, **Then** reopening or refreshing the other shows the stored truth — never a value that differs from the store.
2. **Given** a successful add or edit from the view, **When** the Memory view is reopened and the readable mirror inspected, **Then** both show the new values and the fact count agrees.
3. **Given** a change aimed at a fact that no longer exists, **When** it is submitted, **Then** it is reported as a failure — never as a success — and no fact is created or resurrected.
4. **Given** the readable mirror cannot be rewritten, **When** an add or edit succeeds, **Then** the stored change is kept, a warning is shown, and a later successful change or view refresh brings the mirror back in line.
5. **Given** the offline acceptance suite, **When** it runs with no network and no credentials, **Then** every scenario in this specification has an automated check and the suite passes.
6. **Given** an accepted or refused add or edit, **When** the activity trace is inspected, **Then** exactly one event records the action, the fact's identity where it applies, the outcome and the time, and the event contains no secret.

---

### Edge Cases

- Two views of the Memory page are open. A fact is edited in one; the stale edit is then saved in the other. The stale save is refused as a conflict, the list refreshes, and the newer values are not overwritten.
- The person saves twice in quick succession. Only one write happens; the save control is unavailable while a save is in progress and the second attempt does not duplicate the change.
- A fact inserted before this feature is longer than the new limits. It stays visible; it can be saved again only after the person shortens the offending field to the limit, and nothing is auto-truncated for them.
- Subject text containing line breaks is normalized to a single line; content line breaks are preserved.
- Content made only of emoji or other non-Latin characters is preserved exactly, and length is measured in display characters, not bytes.
- The readable mirror is missing or unwritable when the view loads. Facts still list and mutate, and the mirror problem is visible as a warning rather than a blank view or a failed save.
- The fact list is empty. The Facts section shows its existing empty state and no edit controls; adding the first fact works exactly as described.
- A save fails because storage is temporarily unavailable. The previous stored values remain, the typed values remain in the form, and a retry can succeed.
- A fact containing a secret is added or edited. The existing redaction boundary still applies to anything this feature records in the activity trace; the fact itself is not silently rewritten.

## Requirements *(mandatory)*

### Adding a fact

- **FR-001**: The Facts section MUST offer an add form with separate **subject** and **content** fields; content MUST accept multiple lines and MUST preserve the person's line breaks when displayed.
- **FR-002**: Both fields MUST be trimmed before saving, and a save MUST be refused when either field is empty or whitespace-only, with a message that names the field and the rule; nothing may be stored in that case.
- **FR-003**: A save MUST be refused when the subject exceeds 120 display characters or the content exceeds 2000 display characters — on adds and on edits alike, including a stored value that is already over the limit — with a message stating the applicable limit; values MUST NOT be silently truncated.
- **FR-004**: A successful add MUST store the subject and content as entered (after trimming), record the person as origin and the current time as creation time, show an explicit confirmation, place the fact first in the list, and increment the fact count — all without navigating away from the view.
- **FR-005**: A successful add MUST clear the form and return it to a ready state for the next fact.
- **FR-006**: Before storing, the system MUST compare the draft against stored facts using a normalized form (trimmed, case-folded, repeated whitespace collapsed). If an identical fact exists, the add MUST be refused, no second copy stored, and the message MUST identify the existing fact and its edit control.
- **FR-007**: If the add cannot be completed — validation, storage or readable-mirror failure — the form MUST show an explicit error, MUST retain the typed values, and MUST NOT leave a partially stored fact.
- **FR-008**: A line break inside the subject MUST be normalized to a single space; content line breaks MUST be preserved.

### Editing a fact

- **FR-009**: Every fact row MUST offer an edit control that turns that row into an edit mode with the current subject and content prefilled, plus save and cancel controls; editing MUST NOT require a separate single-field dialog or retyping unchanged values.
- **FR-010**: Edit mode MUST allow changing the subject only, the content only, or both, and saving MUST persist the submitted values together.
- **FR-011**: Edit validation MUST apply the same rules as adding (FR-002, FR-003, FR-006 — treating the fact itself as excluded from the duplicate check), with messages shown without leaving edit mode and without writing anything.
- **FR-012**: Cancel MUST discard all changes, restore the row's displayed values exactly, write nothing, and show no confirmation that implies a save.
- **FR-013**: A successful edit MUST preserve the fact's identity, origin and creation time; it MUST update the changed values, show an explicit confirmation, and reflect the new values in the list and the readable mirror immediately.
- **FR-014**: A failed edit MUST leave the previously stored values untouched, keep the row in edit mode with the typed values, and show an explicit error so a retry does not lose what was typed.
- **FR-015**: If the fact was changed or deleted since edit mode opened — determined by comparing the stored subject and content with the edit baseline captured when edit mode opened — the save MUST be refused as a conflict; the list MUST refresh to the current truth, no older value may overwrite a newer one, and a deleted fact MUST NOT be recreated.
- **FR-016**: Only one fact may be in edit mode at a time, and a save in progress MUST prevent a second submission for that fact; repeated activation MUST NOT produce duplicate writes.

### Integrity, observability and safety

- **FR-017**: Every add and edit from the view MUST return an explicit outcome — success, validation refusal, conflict, or failure — with a message a person can act on; a change aimed at a fact that no longer exists MUST be reported as a failure and never as success.
- **FR-018**: After every successful change, the Facts list, the fact count, the values the agent can later recall, and the readable mirror MUST agree; the view MUST never present a value that differs from what is stored.
- **FR-019**: If the readable mirror cannot be rewritten, the stored change MUST be kept, a warning MUST be shown, and the mirror MUST converge to the store on the next successful change or view refresh.
- **FR-020**: Fact content MUST be rendered literally in both read and edit modes: markup or script in a fact is displayed as text and never executed.
- **FR-021**: The rules in this specification MUST be enforced wherever the Memory view itself writes a fact, so the view cannot accept through one path a value it refuses through another. The agent-facing tools (`save_note`, `manage_memory`) are explicitly out of scope: their schemas, action set, validation rules and result text MUST remain unchanged.
- **FR-022**: This feature MUST NOT add tools or actions, alter memory retrieval policy or the gate's decisions, or introduce new memory types or storage locations for facts.
- **FR-023**: Every add and edit control MUST be operable with a keyboard alone; when a save is refused, focus MUST move to the first offending field and each message MUST be associated with the field it describes.
- **FR-024**: The trace events this feature records MUST pass through the existing redaction boundary; a fact's stored text MUST NOT be altered by redaction.
- **FR-025**: Every acceptance scenario in this specification MUST have an automated acceptance check that runs with no network and no credentials.
- **FR-026**: Every accepted or refused add or edit from the view MUST append exactly one structured event to the activity trace, recording the action, the fact's identity where it applies, the outcome and the time; the event MUST be readable by the existing activity surfaces and MUST contain no secret.

### Key Entities *(include if feature involves data)*

- **Fact**: A durable remembered statement. Key attributes: identity, subject (short label), content (what is remembered), origin (person or agent), creation time. Editing changes subject and/or content only; identity, origin and creation time survive.
- **Fact draft**: What the person has typed in the add form or edit mode, together with its validation state. It is not a fact until saved, and it must be preserved across failed saves.
- **Duplicate**: A stored fact whose normalized subject and content match a draft's. Detected for adds, excluded for the fact being edited.
- **Edit baseline**: The values shown when edit mode opened, used to detect that the stored fact changed or disappeared before saving.
- **Change outcome**: The explicit result of an add or edit — confirmation, field-level refusal, conflict, or failure with warning — shown to the person and used by the acceptance suite.
- **Readable mirror**: The human-readable projection of memory that must stay consistent with the stored facts.
- **Activity record**: The structured event appended for each accepted or refused fact change — action, fact identity where it applies, outcome and time — readable by the dashboard's activity surfaces and replayable without the screen.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of refused adds and edits show a message naming the field and rule; zero silent no-ops occur across the automated acceptance scenarios.
- **SC-002**: 100% of successful adds and edits leave the Facts list, fact count, recalled values and readable mirror in agreement, verified automatically.
- **SC-003**: A correction that changes the subject only, the content only, or both is completed in a single edit session without retyping the unchanged field; verified for 5 representative facts in a walkthrough.
- **SC-004**: Adding the same fact twice yields exactly one stored fact in 100% of repeated runs.
- **SC-005**: No failed add or edit loses either the previously stored values or the values typed in the current attempt; verified for 100% of failure scenarios in the suite.
- **SC-006**: Capturing a new fact takes at most 3 interactions after typing (remember, see confirmation, start the next entry), and the new fact appears first in the list within the same view.
- **SC-007**: Boundary values exactly at the limits are accepted and one character over is refused, in 100% of boundary cases.
- **SC-008**: A keyboard-only person can add a fact and correct a fact end to end in a walkthrough, with focus landing on the first invalid field after a refused save.
- **SC-009**: Every acceptance scenario in this specification is covered by the offline suite, which passes with no network access and no credentials.
- **SC-010**: With 500 stored facts, opening the Facts section and completing an add or edit shows the result within 2 seconds of the person's action, with every fact still listed.
- **SC-011**: 100% of add and edit attempts produce exactly one activity record with the correct action, identity and outcome, verified in the offline suite.

## Out of Scope

- Redesigning the Forget action beyond keeping it consistent with the outcomes and messages defined here.
- Bulk import or export of facts, tagging, categories, merging duplicate facts, or version history and undo.
- Search, filtering, sorting changes, pagination or virtualization of the facts list.
- Editing or managing episodes, or any other Memory section.
- New tools or actions; any change to the agent-facing `save_note` or `manage_memory` behavior, validation or result text; changes to the retrieval gate, retrieval policy, consolidation, or memory storage layout.
- Multi-user support, permissions, synchronization across devices, or a visual redesign beyond the existing design system.

## Assumptions

- "Memory 下的 Facts" means the **Facts** section of the dashboard's **Memory** view; the feature is a behavior and usability enhancement, not a visual redesign.
- The product is used by one person locally, with no accounts or permission model.
- The facts list keeps its existing newest-first ordering and stays comfortable at up to roughly 500 facts; larger collections, paging and search are deferred.
- The agent keeps adding facts through `save_note` and correcting them through `manage_memory` exactly as today; parity between the view and those tools is a future concern, not this iteration's acceptance bar.
- The limits (120-character subject, 2000-character content) are agreed defaults for this iteration and may be tuned later without changing the behavior contract.
- Exact duplicates are blocked in this iteration, with no "add anyway" override; near-duplicates (same subject, different content) are allowed.
- One fact is edited at a time; undo and version history are deferred.
- Facts created earlier or by the agent are editable under the same rules; legacy content above the limits stays visible but must be shortened to the limit before it can be saved again.
- Conflict detection compares against the edit baseline; no change marker, revision number or last-edited time is stored, so the facts list does not show when a fact was last edited.
- Creation time continues to use the existing timestamp presentation, and origin is shown as the fact's source.
- The existing responsive layout and accessibility baseline remain; this feature adds keyboard operation and field-level messaging on top of them.
- This feature depends on the existing memory store, readable mirror, Memory view and offline test suite introduced before it.

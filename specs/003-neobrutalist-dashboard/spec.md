# Feature Specification: Neobrutalist Dashboard Refresh

**Feature Branch**: `003-neobrutalist-dashboard (spec directory; no branch was created)`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "使用 Neobrutalism 风格美化当前的页面"

**Scope reference**: The "current page" is the local dashboard served by `byo dashboard` — its
**Overview**, **Chat**, **Observability**, **Memory** and **Settings** views, the persistent sidebar and
composer, and the turn-detail and raw-record overlays. The terminal chat and the trajectory renderer
are not pages and are out of scope.

**Depends on**: `specs/002-execution-flow-visualization` — the runtime map, live lighting, turn detail
and recent-turn list this refresh restyles already exist there. This feature changes appearance only;
their information and behavior are preserved.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Land on a dashboard that looks built, not skinned (Priority: P1)

A person starts the local dashboard and lands on Overview. The product now has a deliberate visual
identity: heavy dark contours around every surface, flat saturated colour blocks, hard offset shadows,
bold display type and tracked uppercase labels. The runtime map — groups, nodes, connections, state
words, the status pill and the window controls — is redrawn in that language while every label, count
and state remains exactly as readable as before. A first-time viewer can still tell within a glance
which part of the agent is working, what each node is, and what to click.

**Why this priority**: Overview is the front door and the most visually complex surface. If the style
works here without losing the map's meaning, the rest of the product can inherit it. A restyle that
breaks the map is a net loss regardless of how the other views look.

**Independent Test**: Open the dashboard against a recorded sample with turns present. The shell and
Overview show the new vocabulary on every element; a side-by-side inventory of labels, counts, states
and actions matches the previous page one-for-one; the live lighting sequence still plays and remains
perceivable against the new fills.

**Acceptance Scenarios**:

1. **Given** the dashboard loads, **When** Overview appears, **Then** the brand, navigation, active view, home path, status pill, window controls, map, text view and recent-turn list all use the new visual language, and no region still shows the previous appearance.
2. **Given** an idle Overview, **When** a person scans the map, **Then** every group, node, connection, edge label and state word is legible, and the eight state words remain distinguishable from one another.
3. **Given** a turn starts, **When** nodes and edges light in order, **Then** the highlight is clearly perceivable on the new fills, the status line names the current step, and the lighting does not cause the surrounding page to reflow.
4. **Given** the person switches the operating system between light and dark appearance, **When** the page repaints, **Then** both schemes present the same identity and neither loses contrast or hierarchy.
5. **Given** the person uses only the keyboard, **When** they tab through Overview, **Then** every focusable map node and control shows an unclipped, high-contrast focus indicator.

---

### User Story 2 - Send a message and watch a turn without the style getting in the way (Priority: P2)

The person types into the composer and sends. The dock, the live turn card, its stage chips, step rows,
reply and receipt all speak the same visual language, and streaming steps remain easy to follow. Typing
stays responsive, the send action is unmistakable, failures look like failures, and long messages, tool
output and model names wrap instead of breaking the layout.

**Why this priority**: Chat is where the person actually works. A bold style that makes the input hard
to find, the live card jumpy, or failures ambiguous would undermine daily use.

**Independent Test**: Send a scripted turn that calls a tool and returns a reply. The composer, live
card and receipt render in the new style; the card grows without shifting the sidebar or dock; a failed
tool step is recognisable without reading a legend; long content does not overflow.

**Acceptance Scenarios**:

1. **Given** the Chat view, **When** the composer receives focus, **Then** its focus treatment is obvious against the page, the send control is clearly actionable, and submitting with the button and with the keyboard both work.
2. **Given** a turn is streaming, **When** steps arrive, **Then** the card updates in place, the stage chips, step rows and reply remain legible, and the dock does not move.
3. **Given** a tool call fails, **When** its step appears, **Then** the failure is signalled by label as well as colour, and the reply that follows is still clearly distinguished from the error.
4. **Given** a very long user message, tool argument, model name or error text, **When** it renders, **Then** it wraps within its card and no horizontal scrolling appears outside the map.
5. **Given** a person prefers reduced motion, **When** they use the dashboard, **Then** no decorative or state animation plays beyond an instant state change.

---

### User Story 3 - Read the record: turn detail, memory, spend and settings (Priority: P3)

The person drills into a turn, reviews stored facts and episodes, checks spend by model, and edits
provider, model and key. Dense surfaces — the timeline, raw record, tables and form — are restyled but
stay scannable: rows still align, numbers still line up, the selected turn still opens in place, and
the form still says which fields are set.

**Why this priority**: These views are consulted rather than admired. They carry the highest
information density, so they are where heavy outlines and bold fills are most likely to hurt reading.

**Independent Test**: Open a recorded turn, expand its raw record, then visit Memory, Observability and
Settings. Every table row, timeline row, form field, empty state and error message is styled
consistently, aligned, and fully readable at default zoom and at 200% zoom.

**Acceptance Scenarios**:

1. **Given** a recent turn, **When** its detail opens, **Then** the timeline rows, axes, hot badges, reply and raw record use the new language, and the detail panel is visually distinct from the map behind it.
2. **Given** Memory, **When** facts and episodes exist, **Then** rows remain aligned, the forget action is unambiguous, and empty tables explain themselves instead of rendering as bare outlines.
3. **Given** Observability, **When** spend and turn tracks are shown, **Then** figures remain legible and aligned, and a bar that encodes duration is still distinguishable from its track.
4. **Given** Settings, **When** the form renders, **Then** fields, labels and the key-set indicator are clear, the save action is prominent, and focus moves through the form in a sensible order.
5. **Given** any view at a 375-wide viewport, **When** it is displayed, **Then** content reflows to a single column, controls remain operable, and no text is clipped.

---

### Edge Cases

- **No data anywhere**: no turns, no facts, no episodes, no spend, and an empty chat. Each empty state is styled in the new language and still says what is missing and what to do next.
- **Long identifiers**: a deep home path, long model names, long fact text, large tool arguments and raw JSON lines. They wrap or scroll inside their own container without widening the page.
- **Hundreds of rows**: many facts, episodes or turns. The page stays usable; outlines do not merge into a wall of lines and rows remain separable.
- **Live turn while reading history**: a new turn starts while an older turn detail is open. The detail stays put, the live indicator stays visible, and the new style does not obscure the offer to return to the live map.
- **Degraded or failed streams**: the event feed drops, a turn fails, or the map endpoint errors. The error/status surfaces use the new language and still announce what happened; the page does not look broken or empty.
- **Forced-colours / high-contrast mode**: the system overrides colours. Outlines, focus and text remain perceivable and no information disappears.
- **200% zoom and 375-wide viewport**: navigation, map controls, timeline and tables reflow without overlap; the map remains the only intentional horizontal scroll region.
- **Light/dark switch mid-turn**: the appearance changes while a turn is streaming; the live highlight remains visible in both schemes.
- **Map legend checked in grayscale**: state distinctions must survive when colour is removed.

## Requirements *(mandatory)*

### Visual Direction

The following is the design contract for "Neobrutalism" in this product. It is descriptive, not an
implementation instruction; how it is produced belongs to planning.

- **VD-001 Contour first.** Every card, panel, map node, control and table container is bounded by a continuous, consistent dark outline. Outlines, not faint borders or soft shadow, are the primary device that separates layers.
- **VD-002 Hard depth.** Elevated surfaces cast a single solid offset shadow with no blur or soft falloff. Resting, hover and pressed treatments move the offset so controls feel physically depressible.
- **VD-003 Flat, saturated colour.** Accent areas use flat, fully saturated blocks against a light or dark field. No gradients, glass, translucency or texture; colour blocks mark sections and states, not decoration.
- **VD-004 Display type.** A bold geometric or grotesque display face carries the brand, page titles and large figures; body copy stays highly readable; recorded values, identifiers and timings remain monospaced; micro-labels are uppercase with visible tracking.
- **VD-005 Near-sharp corners.** Corners are sharp or minimally rounded so that outlines read as deliberately drawn rather than as generic rounded cards.
- **VD-006 Deliberate imbalance.** Offset blocks, stacked labels and at most one small rotated sticker accent per region add character. They never cover data, shift layout, or cause horizontal overflow.
- **VD-007 Snappy motion.** Motion is limited to short state transitions tied to interaction or live execution. No ambient or looping decoration, and reduced-motion preferences are honoured.
- **VD-008 Data stays the hero.** The style strengthens hierarchy and state; it never competes with numbers, labels or the runtime map's meaning.

### Functional Requirements

- **FR-001**: The dashboard MUST apply the Visual Direction to every surface in scope: the sidebar and brand, the composer, all five views, the turn-detail panel, the map text view, the raw-record panel, the live indicator and the status pill.
- **FR-002**: The product MUST use one consistent visual grammar across all surfaces — the same contour weight, shadow offset, corner treatment, spacing rhythm and accent palette — so no view looks like a different product.
- **FR-003**: The shell MUST make brand, navigation, the active view, the home path and the composer identifiable at a glance, and the active view MUST be marked by at least two cues, not hue alone.
- **FR-004**: The page MUST expose at least four clearly distinct typographic levels (brand/page title, section heading, label, body), with tracked uppercase micro-labels and monospaced recorded values. Body text MUST be no smaller than the pre-change page.
- **FR-005**: The eight runtime states (idle, running, done, skipped, degraded, failed, not reached, partial) MUST each be recognisable from a written state word plus at least two non-hue cues (for example border weight, fill, dash pattern or shadow).
- **FR-006**: The runtime map MUST retain every group, node, connection, arrowhead, label, state word and the text alternative. Selection, hover, keyboard focus and live highlighting MUST remain perceptible against the new fills, and connections MUST remain traceable from source to target.
- **FR-007**: Dense surfaces — tables, the turn timeline, the raw record, receipts and stat blocks — MUST remain aligned and scannable; numeric values MUST use consistent figures; long content MUST wrap within its container.
- **FR-008**: Every interactive element MUST have distinct resting, hover, pressed and keyboard-focus states, and focus indicators MUST be visible, unclipped and high-contrast against their surroundings.
- **FR-009**: The composer MUST remain usable while a turn streams: typing stays responsive, the send action stays available where it can be used, and incoming steps MUST NOT move the sidebar, navigation or composer.
- **FR-010**: The layout MUST adapt for desktop, tablet and phone widths (reference widths 1280, 900 and 375) without unintended page-level horizontal scrolling, clipped text or overlapping controls. The runtime map's own scroll region is the only intentional horizontal scroll.
- **FR-011**: Light and dark appearance MUST both follow the operating system preference, express the same identity, and satisfy the contrast requirements. No new manual theme switch is required.
- **FR-012**: The refresh MUST meet WCAG 2.1 AA: body text contrast at least 4.5:1, large text at least 3:1, interactive boundaries and focus indicators at least 3:1; full keyboard operability; the map's text alternative and the status live announcement preserved; reduced motion honoured; forced-colours mode usable.
- **FR-013**: Empty, loading and error states MUST use the same visual language and MUST still state what is happening and what the person can do. Decoration MUST NOT hide or soften an error.
- **FR-014**: The visual identity MUST be self-contained: rendering the dashboard MUST require no network request for fonts, images or styles beyond the local server, and MUST NOT add a build step to view the page.
- **FR-015**: Content parity MUST hold: no label, count, figure, action, route or data field may be removed, hidden behind hover, or reordered in a way that changes meaning.
- **FR-016**: Decoration MUST be bounded: at most one signature accent per region, no ornament over data, and no treatment that reduces text contrast or target size.
- **FR-017**: Interactive targets on narrow widths MUST be at least 40 by 40 units for primary controls (send, navigation, window, close, forget, save), excluding links embedded in prose.

### Out of Scope

- The terminal chat, the `byo trajectory` renderer and any command-line output styling.
- New pages, new data, new API behavior, new settings or a manual theme switcher.
- Branding assets, logos or typography licensed from another product; the identity is original.
- Print layouts, email templates and native desktop or mobile shells.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A coverage audit finds 100% of in-scope surfaces — five views, the sidebar, the composer, the turn detail, map text view, raw record and live indicator, plus the empty, loading and error states — carrying the new visual language, with zero regions left in the previous appearance.
- **SC-002**: A content parity audit finds 100% of the pre-change labels, counts, figures and actions still present and reachable in the refreshed page.
- **SC-003**: Automated and manual contrast checks pass at 100% in both light and dark schemes: all text at least 4.5:1 (large text at least 3:1), all interactive boundaries and focus indicators at least 3:1.
- **SC-004**: At 1280, 900 and 375 width, every view and the turn detail render with zero unintended page-level horizontal scrolling, zero clipped text and zero overlapping controls; at 200% zoom the same holds for text and controls.
- **SC-005**: A keyboard-only reviewer can reach and operate every action in every view, sees a visible focus indicator at every stop, and is returned to a sensible location when the turn detail closes.
- **SC-006**: In a grayscale capture of the map, a first-time reviewer names all eight runtime states correctly from the state word plus non-hue cues, in 8 of 8 cases.
- **SC-007**: During a live turn, a first-time viewer identifies which part of the agent is currently working within 5 seconds, in 5 of 5 attempts.
- **SC-008**: Four of five first-time viewers complete each of "find the last turn's cost", "open the slowest step" and "change the model" without assistance, in under 60 seconds each.
- **SC-009**: The dashboard's first view renders in under 1 second on the local machine and remains interactive while a turn streams; keystroke-to-echo latency in the composer stays under 100 milliseconds while steps arrive.
- **SC-010**: With network access disabled, the dashboard renders fully styled with zero external asset requests and no build step required.
- **SC-011**: A reviewer checking the edge-case list finds every case handled without layout breakage, lost information or hidden errors.

## Assumptions

- **Scope is the whole dashboard, with Overview as the signature surface.** The request names "the current page"; the product's only page is the dashboard, so all five views, the persistent chrome and the overlays are included rather than Overview alone.
- **Presentation only.** Data, routes, labels, copy (English), keyboard shortcuts and API contracts are unchanged; this is a restyle, not a redesign of information architecture. If a pure visual change would force a copy or structure change, the simpler visual alternative is preferred.
- **Neobrutalism is interpreted as:** thick dark contours, hard offset shadows, flat saturated colour, bold display type, near-sharp corners and deliberate but restrained imbalance — playful, utilitarian, and never at the expense of dense data.
- **Both appearance schemes remain in scope**, with the light scheme as the canonical expression and dark as its equivalent. The system preference decides; no in-page theme control is added.
- **Desktop is primary.** The canonical viewport is 1440 by 900; the page must remain usable at 900 and 375 width, but a dedicated mobile navigation pattern is not required beyond reflow.
- **No new runtime dependency, framework, build step or webfont download.** The existing no-build, offline-first delivery approach is preserved; any display face must come from locally available or bundled resources.
- **Accessibility target is WCAG 2.1 AA**, verified by automated checks plus a manual keyboard and contrast review.
- **Supported browsers are current Chrome, Safari, Firefox and Edge**; legacy browsers are not targeted.
- **The current information density is a floor, not a ceiling.** The refresh may not reduce the amount of visible data or shrink body text; added ornament is capped by the Visual Direction.
- **Existing automated tests and the offline eval suite must keep passing**; the page's behavior is unchanged, so no eval delta is expected beyond visual regression evidence.

# Receipt Intelligence OS — Product Constitution

**Status:** Final design direction  
**Authority:** Single source of truth for product, interaction, content, and interface decisions  
**Scope:** All current and future Receipt Intelligence OS experiences  

## Constitutional Frame

Receipt Intelligence OS continuously transforms purchase history into explainable, useful intelligence. Receipts are evidence, not the product. The product is understanding: what changed, what may explain it, why it matters, how the system knows, and what the user should decide next.

This constitution governs every feature and screen. When principles compete, apply this order: truth and evidence; user agency and privacy; clarity and continuity; usefulness; visual distinction. A feature that cannot satisfy the higher principle must change or not ship.

The official product name is **Receipt Intelligence OS**. **Briefing** is its finite opening experience, not the product itself. **Claim** is its core intelligence object. **Trace the Claim** is its universal explanatory interaction. **Decision** is the valid outcome of reasoning; it may be to act, investigate, monitor, accept, correct, dismiss, or do nothing.

The interface may use warmer everyday labels, but internal concepts must remain stable. New terminology must not create a second name for an existing primitive.

## 1. Product Manifesto

Purchase history should do more than accumulate. It should help a person understand how their shopping is changing and make better decisions with less effort.

Receipt Intelligence OS turns fragmented receipts into a continuous account of shopping behavior. It notices meaningful movement, explains likely causes, shows the underlying proof, remembers what happened before, and follows decisions through to their outcomes.

The product does not manufacture urgency. It does not judge spending. It does not hide uncertainty behind artificial confidence. It earns trust by being specific, traceable, proportionate, and willing to say that nothing meaningful changed.

The interface is not a control room full of numbers. It is a calm, living explanation of the user's purchasing world.

## 2. Product Vision

Receipt Intelligence OS becomes the trusted reasoning layer between raw purchase records and everyday shopping decisions.

At launch, it must excel at three promises:

1. Explain why shopping spend changed.
2. Detect when products become materially worse value through price, quantity, promotion, or substitution changes.
3. Show whether a shopping decision produced the expected result.

The same architecture must later support price forecasting, basket planning, shopping strategy, seasonality, household patterns, store comparison, and AI-assisted exploration without changing the product's mental model.

Success is not measured by how many metrics are displayed. Success is measured by whether users understand a meaningful change, trust the proof, make an appropriate decision, and learn from the outcome.

## 3. Design Philosophy

The product is editorial in reading rhythm, investigative in depth, and operational only when action becomes necessary.

It explains before it visualizes. It places one high-level conclusion before individual findings. It reveals depth progressively while preserving the question that led there. It prefers a finite, prepared briefing to an infinite feed and a focused claim to a grid of unrelated cards.

The product should feel calm, personal, capable, and exact. It borrows the continuity of Apple Health, the focus of Linear, the spatial confidence of Arc, and the analytical seriousness of Bloomberg without imitating any of their appearances.

Visual novelty is never the goal by itself. The product's distinctiveness comes from its reasoning structure, evidence behavior, memory, and outcome loop.

## 4. Product Principles

1. **Lead with a conclusion.** Orient the user before presenting detail.
2. **Make intelligence traceable.** Every consequential intelligence claim links to its basis and source evidence.
3. **Make evidence contextual.** Evidence identifies scope, time, baseline, comparison, and relevant transformations.
4. **Express significance.** A change is not useful until the user understands why it matters to them.
5. **End in a decision.** Every recommendation leads to a safe next step; doing nothing is a legitimate decision.
6. **Remember over time.** Findings, decisions, corrections, and outcomes form a continuous history.
7. **Calibrate confidence.** Known, likely, and unknown causes are visibly different.
8. **Preserve agency.** Users can inspect, challenge, correct, dismiss, or defer system reasoning.
9. **Respect quiet.** Stability is a useful result, not an empty state.
10. **Use operations in service of understanding.** Import, cleanup, and reconciliation are capabilities, not the product's identity.
11. **Protect privacy by default.** Household data, member attribution, and sensitive purchasing patterns are scoped and disclosed deliberately.
12. **Prefer less, better intelligence.** Ranking and omission are product responsibilities.

## 5. Operating System Philosophy

The product earns the term operating system through shared, durable primitives rather than visual complexity. Claims, evidence bundles, context, memory, decisions, and outcomes behave consistently across every domain.

The complete system loop is:

**Import → Normalize → Understand → Explain → Show Evidence → Decide → Observe Outcome**

The first four stages are largely system work. The latter stages become user-visible when they create understanding or require judgment. No intelligence feature may bypass provenance, significance, or uncertainty. No action may bypass the claim and evidence that justify it.

Receipt operations remain directly accessible when a user needs to import, repair, merge, or correct data. They are subordinate system capabilities, usually surfaced because an investigation reveals a need.

Historical records are append-only in meaning. Corrections may recalculate current understanding, but the system must not silently rewrite what it previously claimed, what evidence was available, or what the user decided at that time.

## 6. User Mental Model

The user should understand the product as a careful reviewer that:

1. Reads and organizes purchase evidence.
2. Compares the present with a personal, relevant past.
3. Surfaces only meaningful conclusions.
4. Shows why each conclusion was reached.
5. Helps the user decide what to do.
6. Remembers the decision and later reports what happened.

The user does not need to understand data pipelines, models, or normalization rules to use the product. They must always understand the current scope: whose purchases, which period, which stores or categories, and how complete the evidence is.

The product is not an oracle. It is a transparent reasoning partner. Its confidence may be challenged, and its evidence may be corrected.

## 7. Briefing Philosophy

**Briefing** is the opening ritual of Receipt Intelligence OS. It answers, in order:

1. What is the most important conclusion since the last meaningful review?
2. What findings support that conclusion?
3. What may explain them?
4. Why do they matter?
5. What evidence supports them?
6. What decision is recommended?

The briefing has a beginning, progress, and end. It is ranked, concise, and intentionally finite. It normally contains no more than five to seven findings, followed by a stability summary for areas that did not require attention.

The opening statement is one executive conclusion written in plain language. It is not a greeting, metric, score, or collection of tiles. Findings are grouped by **New**, **Still happening**, and **Back to usual** in user-facing language while retaining the canonical states NEW, ONGOING, and RESOLVED internally.

A briefing is complete when the user has reviewed, deferred, or dismissed the surfaced claims. Completion language is calm: **You're up to date.** The system then becomes ready for investigation rather than pretending that the product is finished.

Quiet briefings are deliberate. The system may say: "Nothing important has changed since your last visit. Prices and shopping totals remain within their usual range. There are no unresolved receipt issues. You're up to date." It may claim stability only when evidence is sufficiently fresh and complete.

## 8. Intelligence Memory

Memory creates continuity between sessions. A finding has a persistent identity and one or more dated episodes. Its visible states are:

- **NEW:** first surfaced in the current episode.
- **ONGOING:** previously surfaced and still materially valid.
- **RESOLVED:** previously valid and no longer materially valid, with a recorded resolution basis.

Recurrence after resolution starts a new episode linked to the prior history. Lifecycle state is separate from whether the user has read a finding and separate from whether an action is pending.

Internally, the lifecycle may include detected, surfaced, acknowledged, acting, monitoring, resolved, dismissed, expired, superseded, and reopened. The interface exposes only the complexity needed for the current decision.

Resolved findings appear once in the briefing when useful, then move into memory. Their original claim, evidence snapshot, decision, and resolution remain inspectable. The system also stores the result of decisions so later briefings can say whether the expected outcome occurred.

Memory belongs to an explicit personal or household scope. Member attribution, shared purchases, and private records must never be inferred or exposed beyond that scope without clear consent.

## 9. Universal Interaction Model

The universal model has a headline claim followed by five trace layers:

1. **What changed** — the observed state or difference.
2. **What may explain it** — known causes, likely contributors, alternatives, and unknowns.
3. **Why it matters** — significance relative to the user's baseline, goals, or risk.
4. **How we know** — the evidence summary and source records.
5. **What next** — the available decision and expected outcome.

This is the constitutional form of **Change → Cause → Significance → Evidence → Action**. “Cause” never implies certainty the evidence does not support. “Action” is broadened to “Decision” because monitoring, accepting, correcting, and doing nothing may be the right outcomes.

The chain applies to intelligence claims, not to ordinary labels, navigation, or raw records. Evidence can also be searched directly, but it must retain source context.

The user preserves reasoning context while tracing: the active claim, period, filters, expanded layer, selected evidence, and return position remain recoverable. Layout may change by device; continuity may not.

## 10. Information Architecture

Receipt Intelligence OS has seven stable layers:

1. **Context** — household, member, time, store, category, and shopping purpose.
2. **Briefing** — the finite opening review of ranked change and stability.
3. **Investigate** — questions across prices, products, categories, stores, behavior, forecasts, and seasonality.
4. **Decisions** — plans, watchlists, corrections, monitored choices, and follow-through.
5. **Evidence** — receipts, line items, source images, normalized products, and comparisons.
6. **Memory** — claim episodes, prior briefings, decisions, outcomes, and recurring patterns.
7. **Control** — imports, normalization review, household settings, preferences, and data quality.

These layers are durable; future capabilities live within them rather than expanding the primary navigation indefinitely. Price forecasting is an investigation capability. Basket optimization produces a decision. AI exploration helps formulate and trace questions. None becomes a disconnected mini-product.

At scale, receipts aggregate by time, store, shopping purpose, or member; products aggregate by category, canonical product, brand, and package variant. Branch-level detail appears only when material. Long-tail records remain searchable outside primary navigation.

## 11. Reading Hierarchy

The default reading order is:

**Conclusion → Reason → Evidence → Decision**

Time and scope remain visible throughout. A screen begins with the strongest supported statement, not with a chart, table, filter bar, or KPI row. Supporting findings follow in ranked order. Each finding reveals the smallest sufficient proof before offering deeper source records.

Charts are allowed when they help prove or investigate a claim. In Briefing, a chart is subordinate to a conclusion. In Investigate, charts may support exploration, but they must answer a visible question and expose interpretation rather than leaving the user with unlabeled movement.

Metrics are reference values, not headlines by default. Their significance, baseline, period, and units must be legible near them.

## 12. Visual Language

The visual language is calm, precise, warm, and evidence-led. It uses hierarchy, spacing, alignment, and temporal relationships before decoration.

The recognizable claim anatomy is consistent across surfaces: one dominant plain-language conclusion; past and present shown together; a visible reasoning spine; a compact evidence strip containing real products, stores, quantities, and unit-price movement; a decision; and a memory trail.

The interface avoids generic dashboard grammar: equal-weight statistic cards, decorative gradients, oversized empty hero areas, ornamental AI effects, dense chart walls, and color as the only carrier of meaning.

Color communicates state and emphasis with restraint. Neutral surfaces carry most content. New, ongoing, resolved, uncertain, and attention states use distinct but accessible treatments, always paired with text or form. Warmth comes from language, proportion, and detail, not beige styling or playful decoration.

## 13. Motion Philosophy

Motion explains continuity. It may reveal a trace layer, connect a claim to evidence, preserve a selected object across a transition, or confirm that a decision entered monitoring.

Motion must not dramatize ordinary spending, simulate intelligence, delay reading, or compete with evidence. State changes use short, restrained transitions. Large movement is reserved for a meaningful change in context, such as moving from the finite briefing into investigation.

Reduced-motion preferences are fully respected. Every interaction remains understandable without animation. Motion never becomes the signature; explanatory continuity does.

## 14. Timeline Philosophy

Time is an organizing dimension, not merely a filter. Every important claim communicates:

**Past baseline → Observed change → Present state → Ongoing continuity**

The comparison period must be appropriate to the behavior: previous basket, typical month, seasonal baseline, promotion cycle, or a user-selected range. The system avoids false comparisons and names the baseline it chose.

Claims are timestamped. Evidence is snapshot-addressable: users can inspect what supported the original claim and, separately, how the conclusion looks after newer or corrected data. Forecasts expose horizon, confidence, and materiality; weak evidence is labeled insufficient rather than converted into false precision.

Time may appear as a line, paired values, episodes, or prose. A universal timeline widget is not required. Temporal clarity is.

## 15. Component Philosophy

Components encode reasoning roles, not arbitrary containers. The core component families are:

- conclusion header
- finding row or passage
- reasoning layer
- evidence summary
- source record
- decision control
- confidence and coverage indicator
- memory episode
- context control

A component must communicate its place in the reasoning chain. Repeated findings may be framed individually, but page sections are not stacks of floating cards and cards are not nested.

Evidence uses a progressive ladder: claim, explanation, evidence summary, source records. An evidence bundle records scope, baseline, calculation, included and excluded data, normalization decisions, generation time, freshness, and coverage. AI-generated prose is presentation, never evidence.

Controls use familiar forms: icons for common tools, tabs for views, toggles for binary settings, menus for option sets, and explicit text actions for decisions. Novel controls require a real explanatory advantage.

## 16. Typography Philosophy

Typography serves reading order. The conclusion is the largest text on an intelligence surface, but it remains a readable statement rather than a marketing headline. Finding titles, reasons, evidence, metadata, and decisions descend through a disciplined scale.

Body text is comfortable for report-like reading. Numeric evidence uses tabular figures where comparison benefits. Labels are concise and never rely on letter spacing for importance. Type does not scale with viewport width; responsive hierarchy comes from layout and bounded type steps.

Uppercase is reserved for compact system state labels such as NEW, ONGOING, and RESOLVED when those canonical terms are shown. Long passages, buttons, and navigation use normal case.

## 17. Content Writing Principles

The voice is perceptive, calm, specific, and human. It sounds like someone carefully reviewed the user's purchases. It is personal without becoming familiar, confident when evidence is strong, and candid when it is not.

Writing follows these rules:

1. State what changed, over what period, and by how much when material.
2. Distinguish what is known, likely, and unknown.
3. Explain significance against the user's own baseline before generic benchmarks.
4. Show the smallest useful proof: period, comparison, amount, contributors, and missing information.
5. Offer the next step as an invitation, not a command.
6. Never moralize spending or imply surveillance.
7. Never use urgency without evidence of consequence and time sensitivity.
8. Prefer everyday language: **In short**, **A closer look**, **See why**, **Worth a look**, **Still happening**, **Back to usual**, **Suggested next step**, and **Nothing needs attention**.

Avoid user-facing language borrowed from military, security, or enterprise command systems, including command, mission, incident, surveillance, and anomaly. Avoid empty claims such as AI-powered, smart insight, actionable intelligence, optimize, and AI magic.

Example uncertainty: "Coffee may have become more expensive, but the evidence is incomplete. Two recent receipts are missing package size, so the unit-price comparison may change."

## 18. Desktop Information Architecture

Desktop uses three coordinated zones:

1. A restrained navigation and context rail.
2. A primary reading surface for Briefing or Investigate.
3. An anchored, resizable evidence inspector.

The reading surface remains dominant. The evidence inspector opens from the active claim without replacing it, and preserves the reasoning layer and selected source. Navigation does not compete with the briefing conclusion.

Briefing begins with the dominant conclusion and finite progress, followed by ranked findings and a quiet/stability close. Investigation may become denser, but it retains the active question and claim anatomy. Operations live in Control and may open contextually when a correction is needed.

## 19. Tablet Information Architecture

Tablet uses two primary zones. Navigation condenses while the reading surface remains central. In landscape, evidence may appear in a side sheet. In portrait, it becomes a full-height layer with a persistent claim header and a clear return path.

The design avoids nested scrolling and miniature desktop layouts. Touch targets, comparison layouts, and decision controls are sized for direct interaction. Context remains visible in a compact header or sheet rather than disappearing behind a generic menu.

Briefing still feels finite and editorial. Investigation gains depth through progressive layers, not by squeezing every desktop panel onto the screen.

## 20. Mobile Information Architecture

Mobile is a single focused reading column. The opening viewport presents the conclusion, its time scope, and the next meaningful reading step. Findings read as a sequence, not a carousel of cards.

Tracing a claim may move to a full-screen drill-down, but a persistent claim header, context summary, and predictable back behavior preserve continuity. The user returns to the exact finding, expansion state, and scroll position.

Evidence prioritizes a concise comparison before source records. Decisions are reachable after proof and remain thumb-accessible without covering content. Briefing progress is subtle and persistent. Mobile never reduces the product to headline metrics or hides evidence behind an unrelated route.

Recent investigations and unresolved decisions recover across devices so mobile can continue, rather than restart, a line of reasoning.

## 21. Signature Interaction

**Trace the Claim** is the signature interaction.

A user selects **See why** on any consequential conclusion. The claim remains anchored while its reasoning unfolds in a consistent order: what changed, what may explain it, why it matters, how the system knows, and what next. Evidence first appears as a compact proof, then opens to exact receipt lines, source images, normalization decisions, and comparison math.

The interaction supports challenge as well as acceptance. The user can correct a product match, change scope, question a cause, dismiss a finding, or choose a different decision. The claim then records the intervention and recalculates transparently.

When the user makes a decision, the system records the expected effect and monitoring period. A later briefing closes the loop by reporting the outcome. This turns explanation into learning rather than a one-time recommendation.

## 22. Signature Screen

The signature screen is the opening Briefing with one dominant conclusion in plain language.

Within one viewport, it shows:

- the relevant past and present state
- the most likely explanation with calibrated confidence
- why the conclusion matters personally
- a compact strip of exact supporting products, stores, quantities, and unit prices
- the finding's memory state and prior episode when relevant
- one suggested decision with its expected effect
- finite briefing progress

The screen is recognizable without a logo because its geometry follows the reasoning chain rather than dashboard conventions. During quiet periods, the same structure communicates stable evidence coverage, what was reviewed, and why nothing needs attention. Quiet mode is not a different empty-state template.

## 23. Why the Product Is Memorable

The product makes a strong promise that ordinary receipt apps do not: every important conclusion can be unfolded into proof, acted upon, and checked later.

Users remember receiving a concise interpretation rather than opening a dashboard. They remember seeing exact products and receipt lines behind a conclusion. They remember that the system knew what was new, what continued, what returned to normal, and whether their previous decision worked.

Its identity comes from a repeated intellectual experience: **understand → verify → decide → learn**. The interface makes that experience visible without turning it into spectacle.

## 24. Why It Cannot Be Confused With a Generic Dashboard

A generic dashboard begins with persistent metrics, equal-weight cards, filters, and charts. Receipt Intelligence OS begins with one time-bound conclusion. It ranks change, carries memory, explains causes, shows receipt-level proof, and ends in a decision whose outcome will be revisited.

The briefing is finite. The evidence is adjacent. The claim has a lifecycle. Quiet periods are written as trusted conclusions. Investigation begins from a question and preserves its reasoning context. Operations emerge when evidence reveals a need.

Removing colors and branding would not remove this structure. A screenshot would still show a conclusion, temporal comparison, causal explanation, evidence strip, decision, and memory trail rather than a collection of KPIs.

## 25. Why Competitors Would Struggle to Copy It

The visible pattern can be imitated. The product behavior cannot be copied quickly because it depends on accumulated system capability:

- canonical product and package normalization across inconsistent receipts
- personal and household baselines with seasonal awareness
- receipt-line provenance and snapshot-addressable evidence
- persistent claim identity across recurring episodes
- confidence, freshness, coverage, and materiality calibration
- ranking that knows what to omit
- decision and outcome tracking over time
- corrections that preserve historical truth while updating current understanding

Bank feeds can show merchant totals but rarely know unit price, package shrinkage, product substitution, promotion dependence, basket composition, store switching, quantity, or repeated waste. Receipt Intelligence OS builds its moat from this item-level evidence and the memory needed to turn it into longitudinal understanding.

The durable advantage is not AI prose. It is a trustworthy data and reasoning model that can explain itself.

## 26. Principles That Must Never Be Violated

Future development must never:

1. Present a consequential intelligence claim without traceable evidence.
2. Present evidence without source, scope, time, baseline, and transformation context.
3. Express certainty beyond the available evidence.
4. Hide missing, stale, incomplete, or corrected data.
5. Recommend a decision without explaining significance and expected effect.
6. Treat action as mandatory when monitoring, accepting, correcting, or doing nothing is valid.
7. Silently rewrite a historical claim, decision, or evidence snapshot.
8. Break continuity when moving from conclusion to reason, evidence, decision, or outcome.
9. Turn Briefing into an infinite feed, metric wall, or generic home dashboard.
10. Invent urgency, shame spending, or use fear to create engagement.
11. Use AI-generated text as evidence or conceal its uncertainty.
12. Let operations become the primary product identity.
13. Add top-level navigation for every new intelligence domain.
14. Use visual novelty to compensate for weak product reasoning.
15. Expose household or member intelligence outside its consented scope.
16. Ship a feature that cannot state which claim it supports, which evidence it uses, which decision it enables, and how its outcome will be remembered.

## Constitutional Product Test

Before design or implementation begins, every feature must answer:

1. What user question or claim does this serve?
2. What evidence supports it, and how fresh and complete is that evidence?
3. How is significance explained against the user's context?
4. What decisions are enabled, including no action?
5. What is remembered, and how will an outcome be observed?
6. How does the user challenge or correct it?
7. Does it fit the seven-layer architecture without creating a parallel product model?
8. Would it still be recognizably Receipt Intelligence OS without branding or decorative styling?

If these questions do not have strong answers, the feature is not ready to enter design.

## Final Recognition Standard

Without its logo, an experienced product designer should recognize Receipt Intelligence OS from the dominant conclusion, temporal comparison, reasoning spine, exact evidence, decision, and memory trail.

Discussion of the product should center on what it helps people understand, verify, decide, and learn, not on the attractiveness of its interface. The product must remain more interesting than its styling.

# Receipt Intelligence OS Design Discoveries

This ledger preserves discoveries from product exploration, the five browser concepts, implementation audits, the Product Constitution, and the Interaction Specification.

Status values: **Frozen** is binding for MVP implementation; **Preserved** remains useful context; **Deferred** belongs outside MVP.

## Product Discoveries

| Discovery | Description | Why it matters | Implementation impact | Status | Future relevance |
|---|---|---|---|---|---|
| Briefing instead of Dashboard | Opening the app means receiving a finite, prepared Briefing, not scanning persistent KPIs. | Users first need orientation and meaning, not measurement inventory. | Replace the overview's KPI-first reading order with one conclusion, ranked findings, evidence, and completion. | Frozen | Briefing remains the opening ritual as capabilities grow. |
| Receipt Intelligence OS | Product transforms purchase history into explainable intelligence. Receipts are raw evidence. | Prevents the product from collapsing into receipt storage or bookkeeping. | Features must serve understanding, evidence, Decision, Memory, or Control. | Frozen | Forecasting and planning remain capabilities inside the OS. |
| Intelligence before charts | Explain what changed and why before showing a chart. | Charts without interpretation transfer analytical work to the user. | Charts support a visible Claim or investigation question; they do not lead the Briefing. | Frozen | Advanced analytics may be exploratory but still preserves context. |
| One executive conclusion | Briefing begins with one supported high-level conclusion. | A strong first statement communicates product value within seconds. | First viewport prioritizes plain-language conclusion, scope, period, and smallest proof. | Frozen | Conclusion generation can improve without changing hierarchy. |
| Finite reading experience | Briefing has a beginning, progress, and end, with at most five MVP findings. | Protects attention and differentiates the product from feeds and dashboards. | Rank deterministically; omit low-value findings; preserve omitted Claims in Investigation and Memory. | Frozen | Capacity can change only with implementation evidence. |
| Claims as product primitive | A Claim is a persistent evidence-backed interpretation, not a chart, receipt, or category. | Creates one architecture for spending, price, category, and future intelligence. | Views, Decisions, evidence, and Memory bind to Claim Episodes and Revisions. | Frozen | New intelligence domains reuse Claim contracts. |
| Candidate is not Claim | Candidate evaluation is pre-Claim, deterministic, and may be eligible, pending, or rejected. | Prevents speculative or incomplete interpretations from polluting Memory. | Automatic create-or-return follows eligibility; no user confirmation creates Claims. | Frozen | Future generators must use the same gate. |
| Evidence-backed conclusions | Every consequential Claim traces to source records, scope, baseline, transformations, freshness, and coverage. | Explainability is the trust mechanism. | Evidence summaries lead to exact receipt lines, images, and calculation context. | Frozen | Provenance becomes more important as intelligence grows. |
| Trace the Claim | Signature interaction unfolds Change, Cause, Significance, Evidence, and Decision without losing context. | Makes explainability memorable and reusable across the product. | Preserve Claim, Revision, evidence snapshot, filters, and return position at every layer. | Frozen | Same model supports forecasts and planning. |
| Universal reasoning model | The reasoning chain applies across Briefing, Investigation, receipt detail, category review, and operations. | One learned interaction lowers cognitive load. | Components and content map to reasoning roles rather than arbitrary cards. | Frozen | Future capabilities must not invent parallel explanation models. |
| Living Memory | The product remembers NEW, ONGOING, and RESOLVED intelligence across visits. | Continuity is more valuable than refreshed statistics. | Persist Episode history, prior Claims, Decisions, Outcomes, and resolution reasons. | Frozen | Memory becomes the longitudinal advantage. |
| Quiet Mode | “Nothing meaningful changed” is a valuable conclusion when evidence is fresh and complete. | The product must not manufacture urgency for engagement. | Quiet Briefing shows reviewed scope, coverage, stable areas, unresolved limitations, and completion. | Frozen | Stronger baselines make reassurance more credible. |
| Decision instead of Action | Valid outcomes include Accept, Correct, Monitor, Defer, Dismiss, Merge, Reclassify, Investigate, and No action. | Action is not always appropriate; user agency matters. | Never infer a Decision from inactivity. Commit only explicit, revision-pinned choices. | Frozen | More Decision types require evidence, reversibility, and outcome contracts. |
| Outcome closes learning loop | A Decision is not the end. Execution and later evidence report whether it worked. | Converts recommendations into learning and accountability. | Separate execution result, observed effect, and prediction assessment; feed material outcomes into future Briefings. | Frozen | Outcome history supports future personalization. |
| Operations follow investigation | Import, merge, correction, and classification are subordinate capabilities, often reached because evidence exposes a need. | Keeps the product about understanding rather than administration. | Preserve direct access for necessary repair, but do not make operations the opening experience. | Frozen | Control remains one stable OS layer. |

## Information and Visual Discoveries

| Discovery | Description | Why it matters | Implementation impact | Status | Future relevance |
|---|---|---|---|---|---|
| Editorial, not administrative | Reading rhythm resembles a concise personal report rather than an admin console. | Supports comprehension, calm, and product identity. | Use conclusion-led hierarchy, restrained navigation, readable passages, and progressive proof. | Frozen | Dense Investigation can grow without changing Briefing tone. |
| Calm, warm, exact voice | Product sounds like a careful reviewer, not a security center, command system, or moralizing budget coach. | Language shapes trust as much as visual styling. | Prefer “In short,” “See why,” “Worth a look,” “Back to usual,” and “You're up to date.” | Frozen | Voice remains stable across new intelligence types. |
| Timeline is structural | Every Claim communicates baseline, observed change, present state, and continuity. | Purchase intelligence is meaningless without temporal comparison. | Keep period, baseline, evidence-as-known time, and observation horizon explicit. | Frozen | Forecasts extend this model into future time. |
| Progressive evidence ladder | Show Claim, explanation, compact proof, then exact sources and transformations. | Balances clarity with auditability. | Do not load or display all receipt evidence immediately. | Frozen | Scale-safe pagination extends the same ladder. |
| Responsive continuity | Device layout may change, but semantic state and return context do not. | Mobile must remain the same product, not a metric summary. | Desktop inspector maps to tablet sheet and mobile drill-down; Back restores exact context. | Frozen | Cross-device sync is deferred, semantic parity is not. |
| Visual identity comes from reasoning geometry | Recognizable screen contains conclusion, past/present comparison, reasoning spine, evidence strip, Decision, and Memory trail. | Brandless recognition should come from product behavior, not decoration. | Avoid equal-weight card grids; repeat Claim anatomy across surfaces. | Frozen | Surface styling can evolve without losing identity. |
| Generic KPI dashboard rejected | Equal-weight metrics, chart walls, decorative gradients, oversized heroes, and ornamental AI effects were rejected. | They make the product interchangeable with generic finance software. | Metrics and charts become evidence, not the opening content. | Frozen | Dashboard patterns may appear only where operationally justified. |

## Exploration Discoveries

| Discovery | Description | Why it matters | Implementation impact | Status | Future relevance |
|---|---|---|---|---|---|
| Dispatch Dossier strength | Finite editorial dossier produced strongest comprehension and quiet-period behavior. | It best expressed the opening ritual. | Briefing adopts its finite reading model without keeping “Dispatch” as product identity. | Preserved | Useful reference for future Briefing refinements. |
| Reasoning Spine strength | Persistent Change/Cause/Significance/Evidence/Decision structure produced strongest explainability. | It became the universal interaction architecture. | Trace the Claim uses this structure across surfaces. | Frozen | Remains reusable for every Claim type. |
| Conclusion Stage trade-off | One dominant Claim reduced cognitive load but hid breadth and slowed scanning. | Demonstrated why one conclusion needs ranked supporting findings. | Use dominant conclusion plus finite findings, not conclusion-only navigation. | Preserved | May suit focused single-Claim moments. |
| Evidence Field trade-off | Claim-to-proof map made evidence visible but risked a busy node-board and weak mobile parity. | Evidence should be strong without becoming spatial complexity. | Use progressive evidence inspection rather than a graph-first home. | Preserved | Could inform specialized investigation tools later. |
| Living Brief trade-off | Persistent Memory created continuity but risked conventional sidebar/dashboard composition. | Memory is essential, while common dashboard geometry is not. | Keep Memory in architecture and Claim trail, not as a generic sidebar feed. | Preserved | Useful for history and recurring-pattern views. |

## Data and Implementation Discoveries

| Discovery | Description | Why it matters | Implementation impact | Status | Future relevance |
|---|---|---|---|---|---|
| Uncertainty must remain visible | Ambiguous OCR, package size, units, categories, and price evidence cannot be guessed away. | False precision destroys trust and contaminates future Claims. | Retain last valid interpretation, block unsupported Decisions, and route correction explicitly. | Frozen | All future generators inherit this rule. |
| Evidence-first price model | Package, weighted, and piece inference have explicit precedence and confidence. | Price intelligence depends on valid units and package semantics. | Reuse current price model and safety audits; avoid unsafe full backfill. | Frozen | Enables later price Claims and shrinkflation analysis. |
| Manual authority in categorization | Manual category and product decisions outrank automated suggestions. | User correction is durable evidence. | Preserve category source, product keys, aliases, and no silent fuzzy categorization. | Frozen | Future recommendations remain subordinate to explicit correction. |
| Existing app should evolve vertically | Current Flask/Jinja application already has valuable parser, price, category, analytics, and UI work. | A rewrite would discard tested behavior and delay visible progress. | Build small slices through current routes, services, templates, CSS, and tests. | Frozen | Reconsider only if implementation evidence proves a limitation. |
| Current docs are historical, not uniformly current | Some legacy docs describe `/` as receipt list and stale module/test baselines. | Freeze must preserve history without treating every old statement as current truth. | Code and tests govern implemented behavior; frozen docs govern new product behavior. | Frozen | Update operational docs during implementation, not through another discovery cycle. |

## Source Trail

- Product Constitution and Interaction Specification in this directory
- original dated specs under `docs/superpowers/specs/`
- Phase 1, Phase 2A, and parser-quality plans under `docs/superpowers/plans/`
- visual concepts under `.superpowers/brainstorm/*/content/receipt-intelligence-directions.html`
- implementation documentation under `docs/`
- root state and price/package audit notes

# Receipt Intelligence OS Architecture Freeze

**Architecture Version:** 1.0  
**Status:** Frozen  
**Freeze Date:** 2026-07-15  
**Product:** Receipt Intelligence OS  

## Declaration

Product discovery is complete. Product philosophy, interaction model, visual direction, behavioral architecture, MVP boundary, and deferred capabilities are stable.

No further manifestos, constitutions, interaction specifications, or architecture explorations should be created. Architecture may change only when implementation evidence demonstrates a real limitation, contradiction, safety problem, or unusable workflow. Preference, novelty, and theoretical elegance are insufficient reasons.

## Frozen Product Identity

Receipt Intelligence OS transforms receipt evidence into explainable shopping intelligence. Receipts are evidence, not the product. Briefing is the opening ritual. Claim is the product primitive. Trace the Claim explains every consequential Claim. Decision records the user's choice. Outcome closes the learning loop. Memory preserves continuity. Quiet Mode communicates trustworthy stability.

The product is not a KPI dashboard, budgeting tool, accounting system, receipt archive, notification center, generic reporting application, or AI chatbot.

## Frozen MVP Boundary

The first implementation is:

- local and single-user
- Flask and Jinja
- one active SQLite database
- synchronous workflows
- deterministic rules-based Claims
- normal browser-tab concurrency only
- incremental evolution of the existing application

The MVP excludes AI-generated Claims, household collaboration, distributed services, cross-device synchronization, asynchronous workflow infrastructure, enterprise privacy administration, and large-corpus optimization.

## Current Implementation Versus Target Contract

The current application already provides receipt upload, Gmail and batch import, parsing, categorization, product normalization, receipt detail, analytics, product review, price-quality review, and an initial command-center shell. Existing code, current schema, and tests are authoritative for implemented behavior.

The frozen OS documents describe the target behavior to be reached through vertical slices. They do not claim that Claims, Episodes, Revisions, Briefings, Decisions, Outcomes, tombstones, or all idempotency contracts already exist in the database.

No broad rewrite is authorized. Each slice should reuse existing services and templates, adding only the minimum contract needed for visible behavior.

## Preserved Implementation Constraints

- Dashboard totals currently use `receipts.total`; legacy analytics may use `items.price`. Do not merge these financial meanings silently.
- Product grouping retains `COALESCE(NULLIF(canonical_name, ''), name)` semantics.
- Existing databases may lack `UNIQUE(receipt_number)` and `ON DELETE CASCADE`; documentation cannot assume schema rebuilding.
- Parser repairs remain deterministic. Ambiguous package evidence stays unresolved rather than invented.
- Price inference remains evidence-first. Unsafe full backfill and `inferred_piece` write-back remain prohibited.
- Category assignment preserves canonical categories, aliases, sources, exact product keys, and manual authority. Fuzzy similarity does not silently categorize or merge products.

## Change Control

An architecture change is allowed only when all are true:

1. A working implementation or test exposes the limitation.
2. The limitation cannot be solved within the current contract without material harm.
3. The smallest compatible correction is documented.
4. Product identity and historical evidence remain preserved.
5. A regression test or reproducible demonstration accompanies the change.

Architecture changes update this version explicitly. Ordinary implementation decisions do not.

## Build Mode Rules

1. Working software over additional theory.
2. Small vertical slices over broad rewrites.
3. Reuse current Flask/Jinja services, routes, templates, CSS, and tests.
4. One visible user improvement per completed task.
5. Implement a prototype when it can resolve a question in less than one day.
6. Add documentation only when it supports operation, verification, or a proven architecture correction.

Every completed implementation task reports:

- files changed
- tests passed
- screenshots captured
- behavior improved

## Freeze Confirmation

Architecture version 1.0 is frozen. The next product task must modify the application itself.

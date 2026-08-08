# Product Merge Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy `/products/merge` admin table with a clear Review / Bulk Selection Workspace while preserving the existing GET search and POST merge semantics.

**Architecture:** Keep the Flask routes and database query/update behavior unchanged. Recompose the page with Jinja selection macros, page-scoped CSS in the existing stylesheet, and a small dedicated client module that derives selected names and impact totals from server-rendered row attributes. Native form submission remains the fallback when JavaScript is unavailable.

**Tech Stack:** Flask, Jinja2, semantic HTML, existing CSS tokens, vanilla JavaScript, Python `unittest`, project browser QA.

## Global Constraints

- Do not change merge semantics, database, parser, normalized-product logic, routes, existing POST actions, Suggestions, Category Review, or other tabs.
- Do not add algorithms, APIs, bulk operations, modals, dependencies, or database writes during verification.
- Preserve dark/light theme, native checkbox and form behavior, keyboard access, visible focus, 44px touch targets, and reduced-motion behavior.
- Do not commit changes unless the user explicitly requests a commit.

---

### Task 1: Structural contracts

**Files:**
- Modify: `tests/test_category_engine.py`

**Interfaces:**
- Consumes: existing `GET /products/merge` response and `POST /products/merge` behavior.
- Produces: stable semantic contracts for one H1, search, selection rows, command band, canonical field, empty state, and unchanged merge persistence.

- [ ] Add a populated-page test with long product names and repeated receipt rows.
- [ ] Assert semantic workspace hooks rather than CSS coordinates.
- [ ] Add no-results and client-script contract assertions.
- [ ] Run the focused tests and confirm the new assertions fail before implementation.

### Task 2: Selection components and page composition

**Files:**
- Create: `app/web/templates/_selection_components.html`
- Modify: `app/web/templates/products_merge.html`

**Interfaces:**
- Consumes: existing `products`, `query`, and `merged_count` template values.
- Produces: `selection_row(product)`, `selected_set_summary()`, and `merge_command_band(query)` macros with stable `data-*` hooks.

- [ ] Build a compact header and search toolbar using existing Review primitives.
- [ ] Render each product as one desktop table row and one responsive hierarchical record through a single semantic row structure.
- [ ] Keep the checkbox value and form action exactly aligned with the existing POST handler.
- [ ] Place the selected-set summary, canonical target, neutral consequence copy, reset, and merge action in the same workspace.
- [ ] Render distinct empty and filtered no-results states.

### Task 3: Selection state behavior

**Files:**
- Create: `app/web/static/product-merge.js`
- Modify: `app/web/templates/products_merge.html`

**Interfaces:**
- Consumes: `[data-merge-form]`, `[data-selection-row]`, checkbox `data-item-count` / `data-receipt-count`, canonical input, reset button.
- Produces: selected-row state, selected count, selected-name list, summed row/receipt impact, whitespace-safe canonical validation, and reset behavior.

- [ ] Recompute all visible state from checked native controls after every selection change.
- [ ] Mark rows with both `data-selected` and text available to assistive technology.
- [ ] Trim canonical input and block empty/whitespace-only submission with an associated error.
- [ ] Reset only the current selected set and canonical field without changing search.
- [ ] Keep the form functional without JavaScript through native `required` and direct POST submission.

### Task 4: Responsive visual system

**Files:**
- Modify: `app/web/static/style.css`

**Interfaces:**
- Consumes: existing semantic tokens and shared Review header/toolbar/focus patterns.
- Produces: dense selection table on desktop, sticky in-workspace command band, mobile records at 360/390px, visible selected state independent of color, and no horizontal overflow.

- [ ] Add Merge-scoped layout, typography, surfaces, row hierarchy, selected indicator, and stable numeric columns.
- [ ] Convert rows to vertical records below the mobile breakpoint while retaining header associations for screen readers.
- [ ] Keep the command band in normal document flow on mobile and sticky only where it cannot cover content.
- [ ] Limit transitions to selection, focus, command-state color/opacity, and respect reduced motion.

### Task 5: Verification and project memory

**Files:**
- Modify: `CURRENT_CONTEXT.md`

**Interfaces:**
- Consumes: completed implementation and fresh test/browser evidence.
- Produces: current verified project state and final screenshots.

- [ ] Run focused merge/UI tests and the full relevant suite.
- [ ] Browser-check default, one selected, multiple selected, no-results, long names, validation, dark/light, desktop/tablet/390/360, keyboard focus order, console, and horizontal overflow without submitting the merge.
- [ ] Save desktop/mobile dark/light screenshots under `tmp/screenshots/merge/`.
- [ ] Review `git diff` and update `CURRENT_CONTEXT.md` with only verified current state.

# Design System Preview Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone dark design-system preview for Receipt Intelligence OS without touching production UI.

**Architecture:** Create one static HTML file at project root with inline CSS tokens copied from `DESIGN.md`. Use semantic sample content to show component language, states, drawer, and responsive mobile layout. Capture desktop and mobile screenshots as verification artifacts.

**Tech Stack:** HTML, CSS, small vanilla JavaScript for drawer toggle only.

## Global Constraints

- Do not change Flask routes, Jinja templates, production CSS, or business logic.
- Use existing design tokens from `DESIGN.md`.
- Do not copy Linear or VoltAgent visual identity.
- Show Spending Pulse, one Intelligence Finding, Action Queue, Receipt Table, Evidence Trace drawer, Data Health, badge/status variants, loading, empty, error, and mobile layout.
- Keep surfaces restrained, compact, progressive, one-accent, evidence-first.

---

### Task 1: Standalone Preview File

**Files:**
- Create: `preview-dark.html`

**Interfaces:**
- Consumes: `DESIGN.md` token names and product rules.
- Produces: Browser-openable static preview at `preview-dark.html`.

- [ ] **Step 1: Create preview structure**

Create semantic sections for Spending Pulse, Finding, Action Queue, Receipt Table, Evidence Trace, Data Health, badges, loading, empty, and error.

- [ ] **Step 2: Add inline CSS tokens**

Copy current project tokens from `DESIGN.md` into `:root`, then build only preview-scoped classes.

- [ ] **Step 3: Add drawer interaction**

Use one small script to open and close Evidence Trace. No framework.

- [ ] **Step 4: Verify**

Open as a local file and capture desktop plus mobile screenshots.

Expected: no production files modified.

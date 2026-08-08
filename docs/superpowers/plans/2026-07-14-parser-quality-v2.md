# Parser Quality v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or execute each task with the same TDD gates.

**Goal:** Reject proven receipt/OCR contamination before item persistence while preserving ambiguous text unchanged.

**Architecture:** Keep `parse_receipt()` as the shared boundary. Add conservative line preprocessing and candidate-name sanitation in `app/receipt_parser.py`; add a separate SQLite read-only audit command that reuses parser classifiers. No parser rewrite, schema change, import, backfill, Price Model change, or Category Engine change.

**Tech Stack:** Python standard library, `unittest`, SQLite URI `mode=ro`.

## Global Constraints

- Main `data/receipts.db` must remain byte-for-byte unchanged.
- Only deterministic whitespace repair is allowed; `21`, `lkg`, `m1`, glued tokens, multipacks, and ambiguous package sizes must not be guessed.
- Prefer rejection over persisting a proven non-product line.
- Preserve all pre-existing dirty-worktree changes.

---

### Task 1: Regression Tests and Baseline

**Files:**
- Create: `tests/test_receipt_parser.py`

- [ ] Add direct tests for decimal whitespace, Rimi, Maxima, discounts, weighted/package products, receipt/cashier/service rejection, and preservation of ambiguous OCR/multipack text.
- [ ] Run `python -m unittest tests.test_receipt_parser -v`; verify new preprocessing/sanitation tests fail for missing behavior.
- [ ] Record baseline counts from `data/receipts.db` through a SQLite read-only connection.

### Task 2: Conservative Parser Boundary

**Files:**
- Modify: `app/receipt_parser.py`
- Test: `tests/test_receipt_parser.py`

- [ ] Add `preprocess_receipt_text(text: str) -> str` that joins whitespace only in an unambiguous decimal immediately followed by a known unit.
- [ ] Add narrow metadata/service classifiers and apply them before candidate items are appended.
- [ ] Keep ambiguous strings unchanged and run focused tests until green.

### Task 3: Read-only Audit

**Files:**
- Create: `app/audit_parser_quality.py`
- Test: `tests/test_receipt_parser.py`

- [ ] Classify persisted item names into requested non-overlapping groups with reason and likely origin layer.
- [ ] Open the database with SQLite URI `mode=ro`; report counts, examples, projected rejections, and unresolved cases.
- [ ] Verify audit execution leaves database SHA256 unchanged.

### Task 4: Documentation and Verification

**Files:**
- Modify: `docs/Parser.md`
- Modify: `docs/DeveloperNotes.md`
- Modify: `CURRENT_CONTEXT.md`

- [ ] Document only implemented preprocessing, sanitation, audit limits, and unresolved risks.
- [ ] Run full unittest, compileall, and `git diff --check`.
- [ ] Request focused code review; fix Critical/Important findings and rerun verification.

No commit: project guide requires explicit user permission.

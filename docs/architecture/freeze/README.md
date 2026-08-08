# Receipt Intelligence OS Architecture Freeze

This directory is the permanent architecture package for Receipt Intelligence OS.

## Authority Order

1. [ARCHITECTURE_FREEZE.md](ARCHITECTURE_FREEZE.md) defines the frozen boundary and change policy.
2. [PRODUCT_CONSTITUTION.md](PRODUCT_CONSTITUTION.md) defines product identity and non-negotiable principles.
3. [INTERACTION_SPECIFICATION.md](INTERACTION_SPECIFICATION.md) defines deterministic MVP behavior.
4. [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) records major choices and rejected alternatives.
5. [DESIGN_DISCOVERIES.md](DESIGN_DISCOVERIES.md) preserves insights from exploration.
6. [FUTURE_IDEAS.md](FUTURE_IDEAS.md) holds intentionally deferred capabilities.
7. [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) transitions the product into Build Mode.

If documents conflict, use this order. Current code and tests remain the authority for behavior already implemented. The Constitution and Interaction Specification govern new Receipt Intelligence OS behavior.

## Preserved History

Nothing was moved or deleted. Original sources remain available:

- `docs/superpowers/specs/` - dated canonical source documents
- `docs/superpowers/plans/` - Phase 1, Phase 2A, and parser-quality plans
- `.superpowers/brainstorm/*/content/receipt-intelligence-directions.html` - five competing visual concepts
- `docs/Architecture.md`, `docs/Analytics.md`, `docs/Database.md`, `docs/Parser.md`, `docs/CategoryEngine.md`, and other implementation documentation
- root context and audit notes, including `CURRENT_CONTEXT.md`, `CURRENT_STATE_REPORT.md`, `PACKAGE_PIECE_AUDIT.md`, and `PRICE_MODEL_DRY_RUN_AUDIT.md`

Runtime PID and server-state files under `.superpowers` are not product documentation.

## Build Mode

Architecture is frozen at version 1.0. Future work should modify working software. Architecture changes require implementation evidence demonstrating that a frozen contract cannot be implemented safely or usefully.

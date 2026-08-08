# Receipt Intelligence Command Center Phase 2A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the receipt-list home page with a data-backed operational Overview while preserving the full receipt list as an alternate view on the existing `/` route.

**Architecture:** Add one read-only `dashboard_service.py` beside `analytics_service.py`. It owns named period windows, receipt-total summaries, category movement, recent receipt enrichment, action queue ranking, and data health. The index route remains a thin query-parameter adapter; Jinja renders either Overview or the preserved receipt list, and Chart.js renders one compact trend using the already-used CDN dependency.

**Tech Stack:** Python standard library, SQLite, Flask, Jinja2, Bootstrap 5.3.2, Bootstrap Icons 1.11.1, Chart.js CDN, plain CSS, Python `unittest`.

## Global Constraints

- Use `receipts.total` for spend, comparison, and forecast totals.
- Change no parser, import, schema, category-write, merge, price-threshold, route URL, or receipt-total behavior.
- Add no package, cache, migration, API route, or frontend framework.
- Default `/` renders Overview. `/?view=receipts` preserves the complete receipt workflow on the same endpoint.
- Queue has at most five rows and contains only warnings with working filtered destinations.
- Omit separate generic parsing confidence: only `price_parse_confidence` and its price-quality destination exist.
- Treat category `прочее` as “requires categorization”; do not claim it is exclusively blank or uncategorized.
- Preserve existing dirty work. Do not commit overlapping files.

---

## File Map

- Create `app/dashboard_service.py`: all read-only dashboard dates, SQL, aggregation, interpretation, and queue logic.
- Modify `app/web/routes.py`: import dashboard functions and adapt only `index()`.
- Replace `app/web/templates/index.html`: Overview and alternate receipt-list mode.
- Modify `app/web/static/style.css`: scoped `.command-*`, `.pulse-*`, `.action-*`, `.change-*`, `.recent-*`, and `.health-*` rules.
- Create `tests/test_dashboard.py`: service and route contracts.

## Exact Service API

```python
@dataclass(frozen=True)
class PeriodWindow:
    key: str
    label: str
    start: date | None
    end: date
    previous_start: date | None
    previous_end: date | None

def resolve_period(period_key: str, as_of: date | None = None) -> PeriodWindow: ...
def get_dashboard_data(period_key: str = "current_month", *, as_of: date | None = None) -> dict: ...
def get_period_receipts(window: PeriodWindow, store_search: str = "") -> list[dict]: ...
def rank_action_queue(candidates: list[dict], limit: int = 5) -> list[dict]: ...
```

`get_dashboard_data()` returns `period`, `summary`, `comparison`, `forecast`, `trend`, `category_changes`, `insight`, `recent_receipts`, `action_queue`, and `data_health`.

## Period Rules

- `current_month`: first day through `as_of`, compared with the same elapsed calendar-day count in the prior month, capped at that month’s end.
- `previous_month`: complete prior calendar month compared with the complete month before it.
- `last_30_days`: `as_of - 29 days` through `as_of`, compared with the immediately preceding 30 days.
- `all_time`: every valid dated receipt through `as_of`; no comparison or forecast.
- SQL uses half-open ISO ranges: `date >= start AND date < end`.
- Forecast appears only for `current_month`, elapsed day at least 7, and at least 3 period receipts. Formula: `spend / elapsed_days * days_in_month`.

## Action Destinations

- Category conflicts: `/products/review?filter=conflict&sort=conflicts`.
- Low-confidence prices: `/data-quality/prices?filter=low_confidence`.
- Suspicious normalized prices: `/data-quality/prices?filter=suspicious`.
- High-confidence merge suggestions: `/products/suggestions?confidence=high`.
- Requires categorization: `/products/review?filter=other`.
- No-manual-rule and generic parser-confidence candidates are never created.

### Task 1: Dashboard Contract Tests

**Files:** Create `tests/test_dashboard.py`.

- [ ] Write temporary-database tests for all four period windows and exact boundary inclusion.
- [ ] Verify current-month comparison uses equal elapsed days and zero prior spend yields `percentage=None`.
- [ ] Verify empty database produces zeros, empty collections, and no forecast.
- [ ] Verify forecast requires current month, day 7+, and three receipts; verify exact daily-pace value.
- [ ] Verify `rank_action_queue()` follows requested priority, excludes `no_manual_rule`, and caps at five.
- [ ] Verify recent receipts are newest-first and capped at five.
- [ ] Verify `/` renders Overview while `/?view=receipts` preserves `#searchInput`, `name="store_search"`, `#receiptTable`, upload link, and receipt links.
- [ ] Run `python -m unittest tests.test_dashboard -v`; expected RED because `app.dashboard_service` does not exist.

### Task 2: Read-Only Aggregation

**Files:** Create `app/dashboard_service.py`; test `tests/test_dashboard.py`.

- [ ] Implement date helpers using `datetime.date`, `calendar.monthrange`, and half-open windows.
- [ ] Query summary spend/count from `receipts`, never item totals.
- [ ] Query daily trend for bounded windows and monthly trend for all time; zero-fill bounded calendar dates.
- [ ] Aggregate category movement from `COALESCE(items.line_total, items.price, 0)`, normalize stored aliases in Python, and phrase insight as two evidence-separated sentences so category changes are not claimed to reconcile receipt-header totals.
- [ ] Query latest five receipts with item count and price-warning count.
- [ ] Build product groups with existing `get_product_key()` and `normalize_category_name()` to count conflicts and `прочее` groups consistently with review semantics.
- [ ] Reuse `find_similar_products(conn, limit=200)` and count only `confidence == "high"`.
- [ ] Compute normalization coverage, unresolved category groups, low-confidence price rows, and merge count.
- [ ] Run `python -m unittest tests.test_dashboard -v`; expected GREEN.

### Task 3: Route and Product Hierarchy

**Files:** Modify `app/web/routes.py`; replace `app/web/templates/index.html`; test `tests/test_dashboard.py`.

- [ ] Change only `index()` to read `period`, `view`, and `store_search`, call the dashboard service, and fetch full period receipts only for `view=receipts`.
- [ ] Build command header with title/subtitle, native GET period selector, store search, and primary upload action.
- [ ] Build asymmetric Overview: dominant spending pulse plus ranked action queue; compact trend plus ranked category movement; five recent receipts plus compact data health.
- [ ] Link spend/count/recent actions to `/?view=receipts&period=<key>` and category/chart drilldowns to existing Analytics date/category filters.
- [ ] Preserve the old searchable/sortable full table only inside the alternate receipt-list branch.
- [ ] Add Chart.js dark defaults and one accessible compact line chart; keep narrative and values visible without canvas.
- [ ] Run `python -m unittest tests.test_dashboard tests.test_ui_shell -v`; expected GREEN.

### Task 4: Overview Styling

**Files:** Modify `app/web/static/style.css`.

- [ ] Add a 12-column desktop command grid with 7/5, 8/4, and 8/4 asymmetric bands.
- [ ] Make spend value the visual anchor; keep queue rows list-like rather than card-like.
- [ ] Add severity text/icons, compact delta bars, receipt rows, and health rails using existing semantic tokens.
- [ ] Stack bands below 960px and preserve 44px touch targets and zero page overflow at 375px.
- [ ] Respect existing reduced-motion block; add no decorative animation or new `!important`.

### Task 5: Verification

**Files:** No source changes unless a regression is found.

- [ ] Run `python -m unittest discover -s tests -v` and confirm every test passes.
- [ ] Run `git -c safe.directory='D:/Python projects/reciept_tracker_v2' diff --check`.
- [ ] Start `python run.py`; verify `/`, `/?period=previous_month`, `/?period=last_30_days`, `/?period=all_time`, and `/?view=receipts`.
- [ ] Browser-check 1440x900, 1024x768, 768x1024, and 375x812: hierarchy, no overflow, working selectors/search, chart pixels, active navigation, console errors, and mobile stacking.
- [ ] Confirm no changes to Analytics, Upload, Receipt Detail, Operations templates, parser/import/category/price logic, schema, or route URLs.

# Receipt Intelligence Command Center Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared dark visual foundation and responsive application shell without changing routes, business logic, data, or page information architecture.

**Architecture:** Keep Flask, Jinja, Bootstrap 5.3.2, Bootstrap Icons 1.11.1, Chart.js, and current inline page scripts. Use `base.html` for grouped navigation and active state, `style.css` for the complete shared visual layer, and two existing chart templates for presentation-only Chart.js defaults. Add one narrow UI shell test module; create no component abstraction or JavaScript bundle.

**Tech Stack:** Flask 3, Jinja2, Bootstrap 5.3.2 CDN, Bootstrap Icons 1.11.1 CDN, Chart.js CDN, plain CSS, Python `unittest`.

## Global Constraints

- Phase 1 is visual-only. Preserve all route URLs, forms, query parameters, database behavior, import behavior, parser logic, categorization logic, price thresholds, and analytics data.
- Install no package and add no frontend framework.
- Do not redesign dashboard information architecture, add dashboard widgets, or extract page-specific markup.
- Use local font stack: `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Do not download Inter.
- Treat `receipts.total` as canonical; do not change totals.
- Preserve existing uncommitted changes in `base.html` and `style.css`. Do not commit because these files already contain user-owned edits.
- Avoid `!important`; only existing reduced-motion declarations may retain it because they must override all component transitions.
- Avoid selectors targeting Chart.js canvases or third-party widgets globally.

---

## A. Current UI Architecture

### Entry points

- `run.py` creates `app = create_app()` and runs Flask on `PORT`, default `5000`.
- `app/web/app.py:create_app()` creates tables, creates the Flask app, registers routes, and installs Jinja helpers.
- `app/main.py` is a separate CLI and does not render the web UI.

### Template inheritance and shared layout

- `app/web/templates/base.html` is the sole shared layout.
- All nine page templates extend `base.html`: `index.html`, `upload.html`, `analytics.html`, `receipt.html`, `item.html`, `products_merge.html`, `product_suggestions.html`, `product_review.html`, and `price_data_quality.html`.
- `base.html` owns document metadata, Bootstrap CSS/JS, Bootstrap Icons, `style.css`, skip link, navigation, flash messages, and the main content block.
- `app/web/templates/static/style.css` is a stale template-side file and is not served by Flask. Leave it untouched in Phase 1.

### Navigation

- Current navigation is a Bootstrap `navbar navbar-expand-lg` horizontal bar.
- Mobile behavior already uses Bootstrap Collapse through `data-bs-toggle="collapse"`, `data-bs-target="#navbarNav"`, and `bootstrap.bundle.min.js`.
- Seven links are flat and no link has an active state or `aria-current`.

### CSS and JavaScript

- `app/web/static/style.css` is the only served local asset. It contains tokens, page layout, controls, tables, upload, analytics, review, receipt, responsive rules, and reduced-motion handling in one 1,088-line file.
- There are no local JavaScript files. Inline scripts own receipt filtering/sorting, upload/Gmail requests, product-suggestion dismissal, and Chart.js rendering.
- Bootstrap 5.3.2, Bootstrap Icons 1.11.1, Chart.js, and chartjs-plugin-datalabels load from jsDelivr CDN.
- Only inline style: upload progress width in `upload.html`; upload JavaScript updates this value. Preserve it.

### Current inconsistencies

- Light tokens conflict with approved dark direction.
- Repeated buttons, controls, tables, badges, empty messages, status lines, and flash messages share classes but lack one semantic dark-state system.
- Navigation has no grouping or active state.
- Chart.js uses hard-coded light-theme colors in `analytics.html` and `item.html`.
- Some badges use raw light colors; flash messages assume success styling even when message category is unknown.
- Existing breakpoint is custom `960px`, while Bootstrap `navbar-expand-lg` changes at `992px`; shell behavior must align to `992px` while legacy page grids may retain `960px`.
- No UI screenshots or snapshots exist. Six PNG files under `tmp/pdfs/parser-evidence/` are parser evidence, not interface references.

## B. Proposed File Changes

### `app/web/templates/base.html`

- **Purpose:** Shared shell and navigation.
- **Change:** Add Bootstrap dark theme hint, endpoint-derived active states, three visual navigation groups, desktop sidebar-compatible structure, mobile collapse semantics, and neutral accessible flash wrapper.
- **Why:** Every page inherits this file; one edit supplies shell, navigation grouping, active state, and accessibility consistently.
- **Risk:** Medium. Bad collapse markup could hide navigation; bad endpoint mapping could highlight the wrong destination. Preserve hrefs, IDs, Bootstrap data attributes, and content block.

### `app/web/static/style.css`

- **Purpose:** Shared design tokens and visual components.
- **Change:** Replace light tokens with approved dark semantic tokens; restyle shell, typography, controls, buttons, status primitives, badges, tables, surfaces, progress, empty states, focus, desktop/mobile navigation, and reduced motion.
- **Why:** Existing classes already cover all repeated Phase 1 patterns. New dependency or stylesheet split adds no value.
- **Risk:** Medium. Global Bootstrap overrides can affect every page. Scope rules to existing classes and verify all routes at four viewport widths.

### `app/web/templates/analytics.html`

- **Purpose:** Keep Chart.js legible on dark surfaces.
- **Change:** Replace presentation-only chart colors and set Chart.js text/grid defaults before chart construction. Do not alter queries, labels, datasets, filters, chart types, or data calculations.
- **Why:** Canvas content cannot inherit CSS text color.
- **Risk:** Low. Typo in inline JavaScript could stop charts; verify console and canvas rendering.

### `app/web/templates/item.html`

- **Purpose:** Keep item trend chart legible on dark surfaces.
- **Change:** Apply the same presentation-only Chart.js defaults and dark-safe line/fill colors.
- **Why:** Same canvas limitation as Analytics.
- **Risk:** Low. Verify item route and chart request remain unchanged.

### `tests/test_ui_shell.py` (new)

- **Purpose:** Protect shared shell rendering, active navigation, dark tokens, and reduced-motion contract.
- **Change:** Add isolated temporary-database route tests using existing `unittest` pattern.
- **Why:** Current suite tests business behavior but has no shared UI regression coverage.
- **Risk:** Low. Patch only `app.db.DB_PATH`, matching `test_category_engine.py`.

No Jinja macros or partials created. Existing shared classes already remove duplication; an abstraction would hide simple markup without reducing Phase 1 edits.

## C. Design-Token Mapping

```css
:root {
    color-scheme: dark;
    --bg: #090d12;
    --surface: #111820;
    --surface-raised: #17212b;
    --surface-soft: #17212b;
    --text: #f2f5f7;
    --text-secondary: #a6b1bd;
    --muted: #7f8b98;
    --line: #283541;
    --line-strong: #586b7c;
    --primary: #4da8e8;
    --primary-hover: #70baf0;
    --on-primary: #06131d;
    --positive: #35b987;
    --warning: #e8b04c;
    --critical: #e6636b;
    --focus-ring: rgba(77, 168, 232, .42);
    --sidebar-width: 248px;
    --radius-sm: 6px;
    --radius: 8px;
    --motion-fast: 160ms;
    --motion-base: 200ms;
    --shadow-overlay: 0 18px 44px rgba(0, 0, 0, .28);
}
```

Contrast checks:

- `#F2F5F7` on `#111820`: 16.32:1.
- `#A6B1BD` on `#111820`: 8.21:1.
- `#7F8B98` on `#111820`: 5.15:1.
- `#4DA8E8` on `#090D12`: 7.50:1.
- `#06131D` on `#4DA8E8`: 7.22:1.
- White on accent is only 2.60:1, so primary buttons use `--on-primary`, not white.
- Approved `#283541` remains the subtle panel border. Add `#586B7C` only for form boundaries where 3:1 graphical contrast is needed.

Typography stays local. Apply tabular numerals to `.amount-cell`, metric values, totals, price/status values, and table numeric cells without converting body copy to monospace.

## D. Component Strategy

- Do not create macros or partials in Phase 1.
- Keep repeated patterns on existing shared classes: `.btn`, `.form-control`, `.form-select`, `.app-table`, `.metric-card`, `.surface`, `.inline-status`, `.empty-message`, `.source-badge`, `.confidence-badge`, `.price-status`, `.progress`, `.status-line`, and `.result-list`.
- Add semantic presentation classes only where required: `.state-message`, `.state-neutral`, `.state-success`, `.state-warning`, `.state-error`, and `.loading-state`.
- Keep page-specific review cards, charts, upload markup, and category forms in their current templates.

## E. Responsive Behavior

- At `min-width: 992px`, use a fixed 248px expanded sidebar. No icon-only collapse control; it adds state and JavaScript without Phase 1 value.
- Below `992px`, remove body/sidebar offset, turn shell into a sticky top bar, and use existing Bootstrap Collapse trigger. Preserve `#navbarNav` and Bootstrap bundle.
- Mobile nav rows remain icon plus text with 44px minimum targets.
- Existing page-grid breakpoint at `960px` remains; only shell breakpoint aligns with Bootstrap `lg` at `992px`.
- `.table-responsive` keeps horizontal scrolling with visible scroll affordance. Do not hide columns globally because table structures differ and no priority metadata exists.
- Treat first descriptive column and amount/action columns as future high-priority fields; Phase 1 preserves every column through scrolling.
- Table headers use sticky positioning within their existing responsive container; no fixed-height nested table scroll region is introduced.
- Inputs and standard buttons are at least 44px high. Compact buttons become 44px on touch-width viewports.
- App gutters: 16px mobile, 24px tablet, 32px desktop within existing max-width container.

## F. Compatibility Strategy

- Preserve every `url_for()` call, route endpoint, form `method`, form `action`, input `name`, query parameter, and element ID.
- Active navigation reads `request.endpoint` only; no route or view function changes.
- Preserve flash retrieval. No Flask-WTF or CSRF extension exists, so Phase 1 neither adds nor removes CSRF behavior.
- Preserve `#navbarNav`, `data-bs-toggle`, and `data-bs-target`; there are no current Bootstrap modals or dropdowns.
- Preserve inline JavaScript selectors: `#searchInput`, `#receiptTable`, upload/Gmail IDs, analytics filter/chart IDs, and suggestion dismissal attributes.
- Chart changes affect color defaults only. API URLs, datasets, chart types, and Chart.js/plugin loading stay unchanged.
- Gmail and upload buttons keep IDs and handlers. Category forms keep actions, names, selects, and submit buttons. Merge forms keep checkbox names and canonical-name input.
- Do not change `receipts.total` or any rendered financial source.

## G. Verification Plan

Automated baseline and regression:

```powershell
python -m unittest discover -s tests -v
```

Expected: 82 existing tests plus new UI tests pass.

Focused UI tests:

```powershell
python -m unittest tests.test_ui_shell -v
```

Route smoke checks use Flask `test_client()` with a temporary database for `/`, `/upload`, `/analytics`, `/products/merge`, `/products/suggestions`, `/products/review`, `/data-quality/prices`, `/receipt/1`, and `/item/test`.

Runtime/browser checks:

```powershell
python run.py
```

- Open `/`, `/upload`, `/analytics`, `/products/review`, `/products/merge`, `/data-quality/prices`, one receipt, and one item.
- Check browser console for JavaScript errors and failed CDN assets.
- Verify Chart.js canvases contain non-background pixels and readable labels.
- Test 375x812, 768x1024, 1024x768, and 1440x900.
- Verify mobile nav opens, closes, retains keyboard access, and does not cover content.
- Tab from skip link through navigation and page controls; confirm 3px visible focus ring and logical order.
- Verify active link has visible state and `aria-current="page"`.
- Verify all control labels remain visible, no text clips, and tables scroll horizontally without page overflow.
- Emulate `prefers-reduced-motion: reduce`; transitions become effectively instant and no loading feedback disappears.
- Exercise upload file selection without submitting a real receipt. Confirm progress/status presentation and unchanged selectors.
- Do not trigger live Gmail import during visual verification; verify button state and handler presence only.
- Submit temporary-database category and merge actions through automated tests; do not mutate production data.

---

### Task 1: Add UI Shell Regression Tests

**Files:**
- Create: `tests/test_ui_shell.py`

**Interfaces:**
- Consumes: `app.web.app.create_app()` and mutable `app.db.DB_PATH` test pattern.
- Produces: Regression contract for route rendering, active navigation, semantic tokens, and reduced motion.

- [ ] **Step 1: Write failing tests**

```python
import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.web.app import create_app


class UIShellTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def test_shared_routes_render(self):
        for path in (
            "/", "/upload", "/analytics", "/products/merge",
            "/products/suggestions", "/products/review",
            "/data-quality/prices", "/receipt/1", "/item/test",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_navigation_marks_current_page(self):
        for path, href in (("/", "/"), ("/analytics", "/analytics"), ("/upload", "/upload")):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn(f'href="{href}"', html)
                self.assertIn('aria-current="page"', html)

    def test_dark_tokens_and_reduced_motion_exist(self):
        css = (Path(__file__).parents[1] / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")
        for declaration in (
            "--bg: #090d12", "--surface: #111820", "--primary: #4da8e8",
            "--positive: #35b987", "--warning: #e8b04c", "--critical: #e6636b",
        ):
            self.assertIn(declaration, css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python -m unittest tests.test_ui_shell -v`

Expected: route smoke test passes; active navigation and dark token assertions fail before implementation.

### Task 2: Build Shared Shell and Active Navigation

**Files:**
- Modify: `app/web/templates/base.html:1-64`

**Interfaces:**
- Consumes: Flask `request.endpoint`, existing route endpoint names, Bootstrap Collapse.
- Produces: `.app-shell`, `.app-nav-frame`, `.nav-groups`, `.nav-group`, and active `.nav-link` markup consumed by Task 3 CSS.

- [ ] **Step 1: Add `data-bs-theme="dark"` and endpoint sets**

Define exact endpoint groups in Jinja:

```jinja2
{% set current_endpoint = request.endpoint or '' %}
{% set overview_endpoints = ['index', 'view_receipt'] %}
{% set intelligence_endpoints = ['analytics', 'item_profile'] %}
{% set operations_endpoints = ['upload', 'products_merge', 'product_suggestions', 'product_review', 'price_data_quality'] %}
```

- [ ] **Step 2: Replace flat navigation with three visual groups**

Keep current hrefs and icons. Add `active` and `aria-current="page"` only when exact destination endpoint matches. Keep `#navbarNav` and Bootstrap collapse attributes unchanged.

- [ ] **Step 3: Keep flash and content contracts**

Wrap flash text with `class="state-message state-neutral inline-status" role="status"`; keep `get_flashed_messages()` and `{% block content %}` unchanged.

- [ ] **Step 4: Run focused tests**

Run: `python -m unittest tests.test_ui_shell -v`

Expected: active navigation tests pass; token tests still fail.

### Task 3: Apply Dark Tokens and Shared Component Styling

**Files:**
- Modify: `app/web/static/style.css:1-1088`

**Interfaces:**
- Consumes: existing page class names plus shell classes from Task 2.
- Produces: visual tokens and responsive behavior used by every template.

- [ ] **Step 1: Replace root variables with Section C tokens**

Keep compatibility aliases (`--surface-soft`, `--primary-dark`, `--teal`, `--shadow`) mapped to semantic dark values so existing page rules continue working.

- [ ] **Step 2: Implement desktop sidebar and mobile top bar**

Use `@media (min-width: 992px)` for fixed 248px sidebar and `@media (max-width: 991.98px)` for sticky top shell with Bootstrap Collapse. Do not add desktop collapse JavaScript.

- [ ] **Step 3: Restyle existing shared components**

Cover body/surfaces, typography, buttons, forms, focus rings, tables, scroll wrappers, progress, empty states, state messages, source/confidence/price badges, disabled states, and numeric values. Use no global canvas selector.

- [ ] **Step 4: Preserve page layouts and update dark raw colors**

Replace light-only backgrounds and text colors inside existing selectors with semantic tokens or `color-mix()`. Keep grid structure, dimensions, and page-specific behavior unchanged.

- [ ] **Step 5: Align responsive and reduced-motion behavior**

Preserve legacy `960px` and `560px` page-grid rules. Add shell-specific `992px` rules and retain the existing reduced-motion override.

- [ ] **Step 6: Run focused tests**

Run: `python -m unittest tests.test_ui_shell -v`

Expected: all UI shell tests pass.

### Task 4: Make Existing Charts Dark-Safe

**Files:**
- Modify: `app/web/templates/analytics.html:111-233`
- Modify: `app/web/templates/item.html:247-281`

**Interfaces:**
- Consumes: existing Chart.js CDN global and current data responses.
- Produces: readable chart text, gridlines, lines, and fills on dark surfaces.

- [ ] **Step 1: Add presentation constants before chart construction**

```javascript
const chartTextColor = '#a6b1bd';
const chartGridColor = 'rgba(166, 177, 189, .14)';
const chartPrimary = '#4da8e8';
const chartPositive = '#35b987';
Chart.defaults.color = chartTextColor;
Chart.defaults.borderColor = chartGridColor;
```

- [ ] **Step 2: Replace light-theme chart colors only**

Use approved semantic colors for datasets and translucent fills. Keep chart types, values, labels, API requests, filters, and plugin setup unchanged.

- [ ] **Step 3: Run full automated suite**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

### Task 5: Runtime and Visual Verification

**Files:**
- No source changes unless verification exposes a Phase 1 regression.

**Interfaces:**
- Consumes: completed Phase 1 UI.
- Produces: verified desktop/mobile shell and compatibility evidence.

- [ ] **Step 1: Start app on an available local port**

Run: `python run.py` with `PORT=5000`, or next free port.

- [ ] **Step 2: Execute browser checks from Section G**

Capture desktop and mobile screenshots of Overview, Analytics, Upload, and one operations screen. Check console, layout overflow, chart pixels, active navigation, controls, and keyboard focus.

- [ ] **Step 3: Test reduced motion and responsive breakpoints**

Verify 375x812, 768x1024, 1024x768, and 1440x900 with reduced motion both off and on.

- [ ] **Step 4: Review final diff**

Run: `git -c safe.directory='D:/Python projects/reciept_tracker_v2' diff -- app/web/templates/base.html app/web/static/style.css app/web/templates/analytics.html app/web/templates/item.html tests/test_ui_shell.py docs/superpowers/plans/2026-07-14-command-center-phase-1.md`

Confirm no route, database, parser, category, price, import, or analytics-data code changed.


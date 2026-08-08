# Receipt Tracker Visual Constitution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every current Receipt Tracker screen into one quiet, evidence-led visual system while preserving its four distinct composition modes: reading, register, investigation, and review.

**Architecture:** Keep the existing Flask/Jinja, Bootstrap, Chart.js, and vanilla JavaScript stack. Reuse the current shell, semantic CSS variables, shared surfaces, controls, tables, state messages, receipt partial, and route contracts; change only presentation markup, presentation scripts, CSS, and UI contract tests. Work screen-by-screen so every commit remains usable and reviewable.

**Tech Stack:** Flask/Jinja templates, CSS, Bootstrap 5.3, Bootstrap Icons, Chart.js, vanilla JavaScript, Python `unittest`.

## Global Constraints

- Visual north star: `Quiet Evidence Instrument`.
- Preserve four composition modes: Briefing = reading, Archive = register, Analytics = investigation, operational queues = review.
- One screen has one dominant user question, one page-level focus, no more than three primary blocks, and no more than one page-level primary action.
- Keep current data, routes, forms, mutations, filtering, sorting, chart queries, parser results, and receipt evidence intact.
- Do not add features, business rules, backend queries, routes, dependencies, component frameworks, icon libraries, fonts, or build tooling.
- Do not turn screens into a generic SaaS dashboard, KPI-card grid, corporate BI console, admin panel, marketing hero, AI interface, cyberpunk UI, neon/glow UI, glassmorphism, or Apple-style translucent glass UI.
- Keep Radar absent. Do not replace it unless a separate product decision proves user value.
- Use one system language: Russian. Do not translate original merchant names, product names, receipt strings, or source evidence.
- Use blue/cyan only for action and selection, amber for attention/review, green for verified/positive, red for error/critical, neutral for metadata, and a visibly distinct disabled state.
- Never encode status by color alone.
- Prefer one canvas, borders, spacing, and tonal contrast over shadows and nested cards.
- Keep small stable radii. Use pills only for statuses and active filters.
- Keep primary meaning visible without hover, tooltip, drawer, animation, or navigation.
- Keep native control behavior, visible labels, keyboard navigation, focus states, touch targets, reduced motion, and usable layouts at 320 CSS pixels and 200% text scaling.
- Do not alter `app/dashboard_service.py`, analytics services, database code, parser code, or route response schemas.

## File Map

- `app/web/templates/base.html`: shared desktop/mobile navigation, page canvas, flash states.
- `app/web/templates/index.html`: Intelligence Briefing presentation and archive interaction script.
- `app/web/templates/_receipt_workspace.html`: archive header, month context, filters, rows, expanded receipt, evidence drawer.
- `app/web/templates/receipt.html`: standalone expanded receipt.
- `app/web/templates/analytics.html`: investigation filters, written result summary, charts, item trend.
- `app/web/templates/upload.html`: import dropzone, selected-file queue, progress, result states.
- `app/web/templates/product_review.html`: category review queue.
- `app/web/templates/product_suggestions.html`: similar-product comparison queue.
- `app/web/templates/products_merge.html`: merge selection and command area.
- `app/web/templates/price_data_quality.html`: price-quality diagnostic register.
- `app/web/static/style.css`: shared shell, primitives, register/investigation/review layouts, responsive behavior.
- `app/web/static/home-story.css`: reading-mode layout only.
- `app/web/static/home-story.js`: visit-state disclosure only.
- `app/web/static/home-story-motion.js`: remove after static briefing replaces decorative presentation motion.
- `tests/test_ui_shell.py`: existing route, shell, story, and theme contracts.
- `tests/test_visual_contract.py`: new focused visual-structure contract tests.
- `DESIGN.md`: update component and screen-role documentation after production markup stabilizes.

---

### Task 1: Lock the Visual Contract in Tests

**Files:**
- Create: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: `create_app()`, current Flask endpoints, `app/web/static/style.css`.
- Produces: route-level structural checks that later tasks update one screen at a time.

- [ ] **Step 1: Create the first failing contract test**

```python
import re
import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.web.app import create_app


ROOT = Path(__file__).parents[1]
TEMPLATES = ROOT / "app" / "web" / "templates"
STYLE = ROOT / "app" / "web" / "static" / "style.css"


class VisualContractTests(unittest.TestCase):
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

    def html(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_shared_shell_names_composition_mode(self):
        cases = {
            "/": "mode-reading",
            "/?view=receipts": "mode-register",
            "/analytics": "mode-investigation",
            "/products/review": "mode-review",
            "/products/suggestions": "mode-review",
            "/products/merge": "mode-review",
            "/data-quality/prices": "mode-review",
            "/upload": "mode-review",
        }
        for path, mode in cases.items():
            with self.subTest(path=path):
                self.assertIn(mode, self.html(path))

    def test_system_copy_is_russian_and_radar_stays_absent(self):
        archive = self.html("/?view=receipts")
        quality = self.html("/data-quality/prices")
        for copy in (
            "Receipts",
            "Filters",
            "Clear filters",
            "Receipt Workspace",
            "Extraction summary",
            "Receipt Radar",
        ):
            self.assertNotIn(copy, archive)
        for copy in ("Line total", "Unit price", "Normalized", "Unknown", "Low confidence", "Suspicious"):
            self.assertNotIn(copy, quality)

    def test_global_visual_primitives_exist(self):
        css = STYLE.read_text(encoding="utf-8")
        for selector in (
            ".mode-reading",
            ".mode-register",
            ".mode-investigation",
            ".mode-review",
            ".page-header",
            ".filters-grid",
            ".app-table",
            ".state-message",
            ".evidence-block",
        ):
            self.assertIn(selector, css)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test and verify the expected failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_shared_shell_names_composition_mode -v
```

Expected: `FAIL` because `mode-reading` is not rendered yet.

- [ ] **Step 3: Do not add production code in this task**

This task only installs the contract harness. Later tasks make individual assertions pass.

- [ ] **Step 4: Commit the test harness**

```powershell
git add tests/test_visual_contract.py
git commit -m "test: define visual constitution contract"
```

---

### Task 2: Unify Shared Shell, Page Headers, Actions, and Mobile Navigation

**Files:**
- Modify: `app/web/templates/base.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: existing `.app-shell`, `.app-nav-frame`, `.nav-group`, `.nav-link`, `.page-content`, `.app-container`, `.page-header`, button, form, and state classes.
- Produces: one shared shell and composition-mode hook used by every later screen.

- [ ] **Step 1: Add failing shell assertions**

Add to `VisualContractTests`:

```python
    def test_navigation_has_clear_mobile_and_desktop_states(self):
        html = self.html("/analytics")
        self.assertIn('class="app-shell', html)
        self.assertIn('aria-current="page"', html)
        self.assertIn('aria-label="Открыть навигацию"', html)
        self.assertIn('id="navbarNav"', html)
        self.assertNotIn("Receipt Intelligence", html)

    def test_shared_page_header_has_one_title(self):
        for path in ("/analytics", "/upload", "/products/review", "/products/suggestions",
                     "/products/merge", "/data-quality/prices"):
            with self.subTest(path=path):
                html = self.html(path)
                self.assertEqual(html.count("<h1"), 1)
```

- [ ] **Step 2: Run the shell tests and verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_navigation_has_clear_mobile_and_desktop_states tests.test_visual_contract.VisualContractTests.test_shared_page_header_has_one_title -v
```

Expected: first test fails on current menu label and English product copy.

- [ ] **Step 3: Give the shell a Russian product name and stable mobile label**

In `base.html`, use:

```html
<a class="navbar-brand" href="{{ url_for('index') }}">
    <span class="brand-mark"><i class="bi bi-receipt" aria-hidden="true"></i></span>
    <span class="brand-copy">
        <strong>Receipt Tracker</strong>
        <small>Личный архив покупок</small>
    </span>
</a>
<button
    class="navbar-toggler"
    type="button"
    data-bs-toggle="collapse"
    data-bs-target="#navbarNav"
    aria-controls="navbarNav"
    aria-expanded="false"
    aria-label="Открыть навигацию"
>
    <span class="navbar-toggler-icon"></span>
</button>
```

Keep current navigation groups, URLs, icons, active endpoint checks, `aria-current`, theme control, skip link, and main landmark unchanged.

- [ ] **Step 4: Add composition-mode hooks without route changes**

Change the body opening tag in `base.html` to:

```html
<body class="{% block body_class %}{% endblock %}">
```

Use existing per-template `body_class` blocks. Later tasks set exactly one of `mode-reading`, `mode-register`, `mode-investigation`, or `mode-review`; no JavaScript mode detection.

- [ ] **Step 5: Replace shell and header overrides with one restrained rule set**

At the final override layer of `style.css`, add:

```css
.mode-reading,
.mode-register,
.mode-investigation,
.mode-review {
    background: var(--bg);
    color: var(--text);
}

.page-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    margin-block: 0 24px;
    padding: 0;
}

.page-header h1 {
    margin: 0;
    max-width: 24ch;
    font-size: clamp(1.75rem, 3vw, 2.25rem);
    line-height: 1.12;
}

.page-header .eyebrow {
    margin-bottom: 6px;
}

.page-header > :last-child:not(:first-child) {
    flex: 0 0 auto;
}

.nav-link {
    min-height: 44px;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
}

.nav-link.active {
    border-color: color-mix(in srgb, var(--primary) 32%, var(--line));
    background: color-mix(in srgb, var(--primary) 12%, var(--surface));
}

.nav-link.active::before {
    content: "";
    width: 3px;
    height: 20px;
    border-radius: 2px;
    background: var(--primary);
}

@media (max-width: 991.98px) {
    .app-shell {
        position: sticky;
        top: 0;
        z-index: 1030;
    }

    .app-nav-collapse {
        position: absolute;
        inset: 100% 12px auto;
        max-height: min(72dvh, 620px);
        overflow-y: auto;
        border: 1px solid var(--line-strong);
        border-radius: var(--radius);
        background: var(--surface);
        box-shadow: var(--shadow-overlay);
    }

    .app-nav-collapse .nav-groups {
        padding: 12px;
    }
}

@media (max-width: 559.98px) {
    .page-header {
        align-items: stretch;
        flex-direction: column;
        gap: 14px;
        margin-bottom: 18px;
    }

    .page-header > :last-child:not(:first-child) {
        align-self: flex-start;
    }
}
```

Do not add a mobile bottom bar, floating action, translucent backdrop, custom menu JavaScript, or new navigation destinations.

- [ ] **Step 6: Make the mode assertion pass on shell-owned review pages**

Add these blocks:

```jinja2
{% block body_class %}mode-investigation{% endblock %}
```

to `analytics.html`, and:

```jinja2
{% block body_class %}mode-review{% endblock %}
```

to `upload.html`, `product_review.html`, `product_suggestions.html`, `products_merge.html`, and `price_data_quality.html`.

- [ ] **Step 7: Run focused and existing shell tests**

Run:

```powershell
python -m unittest tests.test_visual_contract tests.test_ui_shell.UIShellTests.test_navigation_marks_current_page tests.test_ui_shell.UIShellTests.test_shared_routes_render -v
```

Expected: shell tests pass; language assertions remain allowed to fail until archive and quality tasks.

- [ ] **Step 8: Commit**

```powershell
git add app/web/templates/base.html app/web/templates/analytics.html app/web/templates/upload.html app/web/templates/product_review.html app/web/templates/product_suggestions.html app/web/templates/products_merge.html app/web/templates/price_data_quality.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: unify visual shell and navigation"
```

---

### Task 3: Reduce Briefing to a Static Reading Surface

**Files:**
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/home-story.css`
- Delete: `app/web/static/home-story-motion.js`
- Modify: `tests/test_ui_shell.py`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: existing `dashboard.month_story`, evidence links, archive partial, visit-state script.
- Produces: reading-mode Briefing with one conclusion, supporting evidence, and archive continuation; no decorative cinematic presentation.

- [ ] **Step 1: Replace motion-specific tests with static-reading assertions**

In `tests/test_ui_shell.py`, remove tests whose only contract is `story_mode=cinematic`, A/B comparison, debug overlays, animated cloning, animation phases, and skip controls. Add:

```python
    def test_briefing_is_static_reading_surface_with_progressive_disclosure(self):
        db.add_receipt_with_items("2026-07-05", "RIMI", 12.5, "reading-1", [])
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("mode-reading", html)
        self.assertIn('data-story-act="month"', html)
        self.assertIn('data-story-act="insight"', html)
        self.assertIn('data-story-act="workspace"', html)
        self.assertIn('class="story-evidence"', html)
        self.assertIn('id="receipt-workspace-start"', html)
        self.assertNotIn("home-story-motion.js", html)
        self.assertNotIn("data-story-skip", html)
        self.assertNotIn("data-story-compare", html)
        self.assertNotIn("data-story-debug", html)
        self.assertNotIn("Cinematic", html)
```

Add to `VisualContractTests`:

```python
    def test_briefing_keeps_evidence_and_avoids_decorative_motion(self):
        html = self.html("/")
        self.assertIn("mode-reading", html)
        self.assertIn("На чём основан вывод", html)
        self.assertNotIn("home-story-motion.js", html)
        self.assertNotIn("Пропустить историю", html)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```powershell
python -m unittest tests.test_ui_shell.UIShellTests.test_briefing_is_static_reading_surface_with_progressive_disclosure -v
```

Expected: `FAIL` because the motion asset and presentation controls still render.

- [ ] **Step 3: Remove presentation-only branches from the template**

In `index.html`:

- set the body class to `mode-register` for direct archive and `home-story-page mode-reading` for briefing;
- keep `story-metadata`, `home-story.css`, and `home-story.js`;
- remove the `home-story-motion.js` script;
- remove story toolbar, skip button, A/B compare, debug overlay, and `data-story-presentation`;
- render the existing timeline for all non-empty stories;
- keep month total, period, highlighted receipts, insight title, metric confirmation, destination link, evidence list, empty state, archive link, replay disclosure, and receipt workspace.

Use:

```jinja2
{% block body_class %}{{ "mode-register" if view == "receipts" else "home-story-page mode-reading" }}{% endblock %}
```

and:

```html
<article class="home-document{% if not dashboard.month_story.receipt_count %} is-empty{% endif %}" aria-labelledby="story-month-title" data-story-mode="new">
```

- [ ] **Step 4: Remove cinematic-only CSS**

Delete selectors in `home-story.css` containing:

```css
[data-story-presentation="cinematic"]
[data-cinematic-phase]
[data-story-cinematic-active]
.story-skip
.story-compare
.story-debug
```

Keep normal reading layout, timeline, evidence, visit-state disclosure, focus styles, responsive rules, and `prefers-reduced-motion`.

- [ ] **Step 5: Delete the decorative motion script**

Delete `app/web/static/home-story-motion.js`. Do not replace it with another animation library or script.

- [ ] **Step 6: Run briefing and dashboard contracts**

Run:

```powershell
python -m unittest tests.test_ui_shell tests.test_dashboard tests.test_visual_contract.VisualContractTests.test_briefing_keeps_evidence_and_avoids_decorative_motion -v
```

Expected: all tests pass after obsolete presentation-mode assertions are removed; dashboard data tests remain unchanged.

- [ ] **Step 7: Commit**

```powershell
git add app/web/templates/index.html app/web/static/home-story.css tests/test_ui_shell.py tests/test_visual_contract.py
git rm app/web/static/home-story-motion.js
git commit -m "style: make briefing a quiet reading surface"
```

---

### Task 4: Recompose Archive as a Register

**Files:**
- Modify: `app/web/templates/_receipt_workspace.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_ui_shell.py`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current receipt list, month summary, period filter, store search, sorting, inline expansion, upload link.
- Produces: one register header, one filter band, and one primary document list.

- [ ] **Step 1: Add archive hierarchy assertions**

Add:

```python
    def test_archive_is_one_register_not_repeated_panels(self):
        html = self.html("/?view=receipts")
        self.assertIn("mode-register", html)
        self.assertEqual(html.count('id="receipt-list-title"'), 1)
        self.assertIn("<h1", html)
        self.assertIn("Архив чеков", html)
        self.assertIn("Фильтры", html)
        self.assertIn("Сбросить", html)
        self.assertIn("Все чеки", html)
        self.assertNotIn("Receipts", html)
        self.assertNotIn("Receipt Workspace", html)
        self.assertNotIn("Receipt Radar", html)
```

- [ ] **Step 2: Verify current failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_archive_is_one_register_not_repeated_panels -v
```

Expected: `FAIL` on duplicate `receipt-list-title` and English copy.

- [ ] **Step 3: Replace the archive opening with one header**

At the start of `_receipt_workspace.html`, render:

```jinja2
<section class="receipts-workspace{% if view != 'receipts' %} is-story-workspace{% endif %}" id="receipt-workspace-start" aria-labelledby="receipt-list-title">
    <header class="receipts-compact-header{% if view != 'receipts' %} is-story-continuation{% endif %}">
        <div>
            <p class="eyebrow">{{ "Источники вывода" if view != "receipts" else "Личный реестр" }}</p>
            {% if view == "receipts" %}
            <h1 id="receipt-list-title">Архив чеков</h1>
            {% else %}
            <h2 id="receipt-list-title">Архив чеков</h2>
            {% endif %}
            <p class="muted">{{ receipts|length }} чек. в выбранном контексте</p>
        </div>
        <a href="{{ url_for('upload') }}" class="btn btn-primary receipts-import">
            <i class="bi bi-cloud-arrow-up" aria-hidden="true"></i>
            Импортировать
        </a>
    </header>
```

Remove the old `receipt-context` count block because it repeats the same total. Keep month facts and top products as one secondary context band, not separate equal cards.

- [ ] **Step 4: Translate and simplify filters**

Use:

```html
<section class="receipt-filter-panel" aria-labelledby="receipt-filters-title">
    <div class="receipt-filter-heading">
        <h2 id="receipt-filters-title">Фильтры</h2>
        <a href="{{ url_for('index', view='receipts') }}" class="receipt-clear-link">Сбросить</a>
    </div>
```

Keep visible labels for period and merchant search. Remove the active period chip because the select already exposes the selected period; render a chip only for a non-empty store search:

```jinja2
{% if store_search %}
<div class="receipt-filter-chips" aria-label="Активные фильтры">
    <span class="filter-chip is-active">Магазин: {{ store_search }}</span>
</div>
{% endif %}
```

- [ ] **Step 5: Make the list the dominant surface**

Use:

```html
<section class="receipt-archive" aria-labelledby="receipt-register-title">
    <div class="receipt-workspace-head">
        <div>
            <p class="eyebrow">Реестр</p>
            <h2 id="receipt-register-title">Все чеки</h2>
        </div>
```

Keep sorting, rows, inline detail, empty state, no-JavaScript receipt link, and drawer triggers unchanged.

- [ ] **Step 6: Flatten archive surfaces in CSS**

Add final overrides:

```css
.mode-register .receipt-overview {
    display: grid;
    gap: 18px;
}

.mode-register .receipts-compact-header,
.mode-register .receipt-filter-panel,
.mode-register .receipt-archive {
    border-radius: 0;
    background: transparent;
    box-shadow: none;
}

.mode-register .receipts-compact-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    padding: 0 0 20px;
    border-bottom: 1px solid var(--line-strong);
}

.mode-register .receipt-month-panel {
    padding: 18px 20px;
    border-color: var(--line);
    background: var(--surface);
}

.mode-register .receipt-filter-panel {
    padding: 0 0 18px;
    border-bottom: 1px solid var(--line);
}

.mode-register .receipt-archive {
    padding: 0;
    border: 1px solid var(--line);
    overflow: hidden;
}
```

- [ ] **Step 7: Run archive contracts**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_archive_is_one_register_not_repeated_panels tests.test_ui_shell.UIShellTests.test_receipt_workspace_is_a_single_partial_and_empty_state_renders tests.test_dashboard.DashboardTests.test_dashboard_and_preserved_receipt_list_render -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
git add app/web/templates/_receipt_workspace.html app/web/static/style.css tests/test_ui_shell.py tests/test_visual_contract.py
git commit -m "style: recompose receipt archive as register"
```

---

### Task 5: Unify Expanded Receipt and Evidence Drawer

**Files:**
- Modify: `app/web/templates/_receipt_workspace.html`
- Modify: `app/web/templates/index.html`
- Modify: `app/web/templates/receipt.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current item rows, category forms, price statuses, evidence summary, standalone receipt route.
- Produces: one selected/expanded state and one consistent evidence block, with accessible drawer focus behavior.

- [ ] **Step 1: Add failing evidence assertions**

Add:

```python
    def test_expanded_receipt_and_drawer_share_evidence_language(self):
        archive = self.html("/?view=receipts")
        receipt = self.html("/receipt/1")
        self.assertIn('class="evidence-block', archive)
        self.assertIn("Доказательства", archive)
        self.assertIn('role="dialog"', archive)
        self.assertIn('aria-modal="true"', archive)
        self.assertIn('tabindex="-1"', archive)
        self.assertIn("Доказательства", receipt)
        self.assertNotIn(">Evidence<", archive)
        self.assertNotIn(">Review<", archive)
        self.assertNotIn(">OK<", archive)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_expanded_receipt_and_drawer_share_evidence_language -v
```

Expected: `FAIL` because evidence classes and Russian copy are absent.

- [ ] **Step 3: Normalize inline receipt copy and hierarchy**

In `_receipt_workspace.html`:

- change `Review` to `Проверить`;
- change `OK` to `Проверено`;
- change `Evidence` to `Доказательства`;
- change `Extraction summary` to `Результат распознавания`;
- replace `.receipt-evidence-summary` with `.receipt-evidence-summary.evidence-block`;
- keep item names, quantities, prices, parser values, and source data unchanged.

Use this evidence heading:

```html
<aside class="receipt-evidence-summary evidence-block" aria-labelledby="receipt-evidence-{{ receipt.id }}">
    <p class="eyebrow">Доказательства</p>
    <h3 id="receipt-evidence-{{ receipt.id }}">Результат распознавания</h3>
```

- [ ] **Step 4: Make the drawer a real modal interaction**

Use:

```html
<aside
    class="receipt-drawer"
    role="dialog"
    aria-modal="true"
    aria-labelledby="receipt-drawer-title"
    aria-hidden="true"
    tabindex="-1"
>
```

Use Russian title and sections:

```html
<p class="eyebrow">Доказательства</p>
<h2 id="receipt-drawer-title">Состояние чека</h2>
```

Do not add numbered sections. Order drawer content as source, confirmed values, limitations, then link to full receipt.

- [ ] **Step 5: Replace drawer script with focus-safe behavior**

In the existing inline script in `index.html`, use:

```javascript
const receiptDrawer = document.querySelector('.receipt-drawer');
const receiptDrawerScrim = document.querySelector('.receipt-drawer-scrim');
const receiptDrawerButtons = document.querySelectorAll('[data-open-receipt-drawer]');
const receiptDrawerClose = document.querySelectorAll('[data-close-receipt-drawer]');
let receiptDrawerTrigger = null;

function setReceiptDrawer(open, trigger = null) {
    if (!receiptDrawer || !receiptDrawerScrim) return;
    if (open) receiptDrawerTrigger = trigger;
    receiptDrawer.classList.toggle('is-open', open);
    receiptDrawerScrim.classList.toggle('is-open', open);
    receiptDrawer.setAttribute('aria-hidden', String(!open));
    document.body.classList.toggle('has-open-drawer', open);
    if (open) {
        receiptDrawer.focus();
    } else {
        receiptDrawerTrigger?.focus();
        receiptDrawerTrigger = null;
    }
}

receiptDrawerButtons.forEach(button => {
    button.addEventListener('click', () => setReceiptDrawer(true, button));
});
receiptDrawerClose.forEach(button => {
    button.addEventListener('click', () => setReceiptDrawer(false));
});
document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && receiptDrawer?.classList.contains('is-open')) {
        setReceiptDrawer(false);
    }
});
```

- [ ] **Step 6: Align standalone receipt with the same evidence grammar**

In `receipt.html`, add:

```jinja2
{% block body_class %}mode-register{% endblock %}
```

Keep one H1 and receipt table. Rename `Итоги по чеку` to `Доказательства и итоги`, add `evidence-block` to the section, and keep all calculated values and category controls.

- [ ] **Step 7: Add shared evidence and selected-state CSS**

```css
.evidence-block {
    border-left: 3px solid var(--line-strong);
    background: color-mix(in srgb, var(--surface-raised) 72%, transparent);
}

.receipt-document.is-expanded {
    background: color-mix(in srgb, var(--primary) 7%, var(--surface));
    box-shadow: inset 3px 0 0 var(--primary);
}

.receipt-inline-detail {
    border-top: 1px solid var(--line-strong);
}

.receipt-drawer {
    width: min(440px, 100vw);
}

.has-open-drawer {
    overflow: hidden;
}
```

- [ ] **Step 8: Run receipt contracts**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_expanded_receipt_and_drawer_share_evidence_language tests.test_ui_shell.UIShellTests.test_shared_routes_render -v
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add app/web/templates/_receipt_workspace.html app/web/templates/index.html app/web/templates/receipt.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: unify receipt evidence states"
```

---

### Task 6: Recompose Analytics as an Investigation Canvas

**Files:**
- Modify: `app/web/templates/analytics.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: existing analytics API, filters, totals, category/month/top-item/trend datasets, Chart.js.
- Produces: filters, one written result band, one primary chart, secondary supporting charts; no KPI wall.

- [ ] **Step 1: Add investigation assertions**

```python
    def test_analytics_is_investigation_not_kpi_dashboard(self):
        html = self.html("/analytics")
        self.assertIn("mode-investigation", html)
        self.assertIn("Что показывают выбранные данные", html)
        self.assertIn('class="analytics-result"', html)
        self.assertNotIn('class="analytics-metrics"', html)
        self.assertNotIn('class="total-chip"', html)
        self.assertIn('aria-live="polite"', html)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_analytics_is_investigation_not_kpi_dashboard -v
```

Expected: `FAIL` because current totals are equal chips.

- [ ] **Step 3: Replace KPI chips with one result band**

Use:

```html
<section class="page-header">
    <div>
        <p class="eyebrow">Исследование</p>
        <h1>Аналитика покупок</h1>
        <p class="muted">Что показывают выбранные данные</p>
    </div>
</section>

<section class="analytics-result" aria-live="polite" aria-label="Итог выбранного среза">
    <div>
        <span>Расходы</span>
        <strong id="totalSpent">—</strong>
    </div>
    <div>
        <span>Среднее за месяц</span>
        <strong id="monthlyAverage">—</strong>
    </div>
</section>
```

Keep filters immediately after the header. Keep the current API calls and value updates.

- [ ] **Step 4: Establish chart hierarchy**

Wrap the month chart as primary:

```html
<section class="surface chart-card analytics-primary-chart">
    <div class="section-title">
        <div>
            <p class="eyebrow">Основной срез</p>
            <h2>Расходы по месяцам</h2>
        </div>
    </div>
    <div class="chart-frame chart-frame-wide">
        <canvas id="monthChart"></canvas>
    </div>
</section>
```

Place category and top-items charts in `.analytics-supporting-grid`. Keep price trend as a separate question with its own input and secondary action. Do not add new metrics or datasets.

- [ ] **Step 5: Change the category chart from doughnut to horizontal bar**

In existing Chart.js setup, use:

```javascript
categoryChart = new Chart(document.getElementById('categoryChart'), {
    type: 'bar',
    data: {
        labels: data.categories.labels,
        datasets: [{
            label: 'Расходы',
            data: data.categories.values,
            backgroundColor: chartPrimary,
            borderWidth: 0,
        }],
    },
    options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { beginAtZero: true, grid: { color: chartGridColor } },
            y: { grid: { display: false } },
        },
    },
});
```

Use current `data.categories` keys exactly as already returned. Do not change analytics endpoints.

- [ ] **Step 6: Add investigation layout CSS**

```css
.analytics-result {
    display: flex;
    gap: 28px;
    margin-bottom: 18px;
    padding: 14px 0;
    border-block: 1px solid var(--line);
}

.analytics-result div {
    display: grid;
    gap: 4px;
}

.analytics-result span {
    color: var(--muted);
    font-size: .8125rem;
}

.analytics-result strong {
    font-size: 1.35rem;
    font-variant-numeric: tabular-nums;
}

.analytics-primary-chart {
    margin-top: 18px;
}

.analytics-supporting-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
}

@media (max-width: 767.98px) {
    .analytics-result,
    .analytics-supporting-grid {
        grid-template-columns: 1fr;
    }

    .analytics-result {
        display: grid;
        gap: 12px;
    }
}
```

- [ ] **Step 7: Run analytics contracts**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_analytics_is_investigation_not_kpi_dashboard tests.test_ui_shell.UIShellTests.test_chart_templates_define_dark_theme_defaults -v
```

Expected: pass.

- [ ] **Step 8: Commit**

```powershell
git add app/web/templates/analytics.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: recompose analytics for investigation"
```

---

### Task 7: Clarify the Upload Workflow

**Files:**
- Modify: `app/web/templates/upload.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current file picker, drag/drop, upload endpoint, Gmail endpoint, progress and result rendering.
- Produces: one import work area with primary local upload and secondary mail import.

- [ ] **Step 1: Add upload hierarchy assertions**

```python
    def test_upload_has_one_primary_import_path(self):
        html = self.html("/upload")
        self.assertIn("mode-review", html)
        self.assertEqual(html.count("btn btn-primary"), 1)
        self.assertIn("Выбранные файлы", html)
        self.assertIn("Импорт из почты", html)
        self.assertIn('aria-live="polite"', html)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_upload_has_one_primary_import_path -v
```

Expected: failure until labels and hierarchy are updated.

- [ ] **Step 3: Reorder the existing upload regions**

Use this structure inside `.upload-layout`:

```html
<div class="dropzone" id="dropzone" tabindex="0">
    <label class="visually-hidden" for="fileInput">PDF-файлы чеков</label>
    <input type="file" id="fileInput" name="pdfs" multiple accept="application/pdf" class="d-none" autocomplete="off">
    <div class="dropzone-icon"><i class="bi bi-file-earmark-arrow-up" aria-hidden="true"></i></div>
    <div>
        <h2>Добавьте PDF-чеки</h2>
        <p>Перетащите файлы сюда или выберите их на устройстве.</p>
    </div>
</div>
<div class="upload-panel">
    <div class="panel-title">
        <h2>Выбранные файлы</h2>
        <span id="fileCounter" class="muted">0</span>
    </div>
    <div id="fileList" class="file-list muted">Файлы не выбраны</div>
    <button id="uploadBtn" class="btn btn-primary w-100">
        <i class="bi bi-cloud-arrow-up" aria-hidden="true"></i>
        Импортировать выбранные
    </button>
    <div class="upload-secondary-path">
        <span>Или</span>
        <button id="gmailBtn" class="btn btn-outline-secondary w-100">
            <i class="bi bi-envelope-arrow-down" aria-hidden="true"></i>
            Импорт из почты
        </button>
    </div>
```

Keep current IDs and JavaScript behavior.

- [ ] **Step 4: Add keyboard activation for the dropzone**

Add beside current dropzone click handler:

```javascript
dropzone.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        fileInput.click();
    }
});
```

- [ ] **Step 5: Reduce nested surface weight**

```css
.upload-layout {
    align-items: stretch;
}

.upload-panel {
    border-left: 1px solid var(--line);
    background: transparent;
}

.upload-secondary-path {
    display: grid;
    gap: 8px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid var(--line);
}

.upload-secondary-path > span {
    color: var(--muted);
    font-size: .75rem;
}

@media (max-width: 767.98px) {
    .upload-panel {
        padding-top: 18px;
        border-top: 1px solid var(--line);
        border-left: 0;
    }
}
```

- [ ] **Step 6: Run upload tests**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_upload_has_one_primary_import_path tests.test_ui_shell.UIShellTests.test_shared_routes_render -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add app/web/templates/upload.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: clarify receipt import workflow"
```

---

### Task 8: Turn Category Review into a Decision Queue

**Files:**
- Modify: `app/web/templates/product_review.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current filters, review groups, category form, source metadata, pagination.
- Produces: compact decision rows with one clear product/category decision.

- [ ] **Step 1: Add review-queue assertions**

```python
    def test_category_review_prioritizes_decision_not_page_metrics(self):
        html = self.html("/products/review")
        self.assertIn("Какое решение нужно принять", html)
        self.assertIn('class="review-list"', html)
        self.assertNotIn('class="summary-grid"', html)
        self.assertNotIn('class="metric-card"', html)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_category_review_prioritizes_decision_not_page_metrics -v
```

Expected: `FAIL` because current page contains summary metric cards.

- [ ] **Step 3: Remove the equal-weight summary grid**

Delete the `summary-grid` block. Put one compact count in the page header:

```html
<section class="page-header">
    <div>
        <p class="eyebrow">Проверка данных</p>
        <h1>Категории товаров</h1>
        <p class="muted">Какое решение нужно принять · {{ total_count }} результатов</p>
    </div>
</section>
```

Keep filters, results, forms, details, and pager.

- [ ] **Step 4: Reorder each row around the decision**

Inside each `.review-card`, keep this order:

```jinja2
<div class="review-card-main">
    <div class="review-subject">
        <p class="eyebrow">Товар</p>
        <h2>{{ group.display_name }}</h2>
        <div class="suggestion-reasons">
            {% for problem in group.problems %}
                <span>{{ problem }}</span>
            {% endfor %}
        </div>
    </div>
    <form method="post" action="{{ url_for('product_review_update_category') }}" class="review-category-form">
        <input type="hidden" name="product_key" value="{{ group.product_key }}">
        <input type="hidden" name="q" value="{{ query }}">
        <input type="hidden" name="filter" value="{{ problem_filter }}">
        <input type="hidden" name="sort" value="{{ sort }}">
        <input type="hidden" name="limit" value="{{ limit }}">
        <input type="hidden" name="page" value="{{ page }}">
        <label>
            <span>Категория</span>
            <select class="form-select form-select-sm" name="category">
                {% for category in category_options %}
                    <option value="{{ category }}" {% if category == group.category %}selected{% endif %}>{{ category }}</option>
                {% endfor %}
            </select>
        </label>
        <button class="btn btn-primary btn-sm" type="submit">
            <i class="bi bi-check2" aria-hidden="true"></i>
            Сохранить
        </button>
    </form>
</div>
```

Keep technical details collapsed and tertiary.

- [ ] **Step 5: Make review cards behave as rows**

```css
.mode-review .review-list {
    gap: 0;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    overflow: hidden;
}

.mode-review .review-card {
    margin: 0;
    border: 0;
    border-radius: 0;
    box-shadow: none;
}

.mode-review .review-card + .review-card {
    border-top: 1px solid var(--line);
}

.mode-review .review-meta,
.mode-review .technical-details {
    color: var(--muted);
}
```

- [ ] **Step 6: Run category-review contract**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_category_review_prioritizes_decision_not_page_metrics -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add app/web/templates/product_review.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: make category review a decision queue"
```

---

### Task 9: Make Similar Products a Difference-First Comparison

**Files:**
- Modify: `app/web/templates/product_suggestions.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current suggestion pairs, reasons, confidence, defer action, merge link.
- Produces: pair rows where names and differences dominate; confidence appears once.

- [ ] **Step 1: Add comparison assertions**

```python
    def test_similar_products_emphasizes_pair_differences(self):
        html = self.html("/products/suggestions")
        self.assertIn("Чем товары отличаются", html)
        self.assertNotIn('class="summary-grid"', html)
        self.assertNotIn('class="metric-card"', html)
        self.assertIn('class="suggestion-products"', html)
        self.assertIn('class="suggestion-reasons"', html)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_similar_products_emphasizes_pair_differences -v
```

Expected: `FAIL` because summary cards remain and question copy is absent.

- [ ] **Step 3: Remove summary cards and state the page question**

Use:

```html
<section class="page-header">
    <div>
        <p class="eyebrow">Сравнение</p>
        <h1>Похожие товары</h1>
        <p class="muted">Чем товары отличаются и нужно ли их объединить</p>
    </div>
    <a href="{{ url_for('products_merge') }}" class="btn btn-outline-secondary">
        Открыть объединение
    </a>
</section>
```

Delete the existing `summary-grid`; keep the filter result count as muted text near filters.

- [ ] **Step 4: Keep confidence once and differences next**

Within `.suggestion-card`, order:

```jinja2
<div class="suggestion-card-header">
    <span class="confidence-badge confidence-{{ item.confidence }}">
        {{ "Высокая вероятность" if item.confidence == "high" else "Возможное совпадение" }}
    </span>
    <button class="btn btn-outline-secondary btn-sm" type="button" data-dismiss>
        Отложить
    </button>
</div>
<div class="suggestion-products">
    <div>
        <span>Первый товар</span>
        <h2>{{ item.left_name }}</h2>
        <p>{{ item.left_count }} строк · {{ item.left_receipt_count }} чеков · {{ item.left_category or "без категории" }}</p>
    </div>
    <div>
        <span>Второй товар</span>
        <h2>{{ item.right_name }}</h2>
        <p>{{ item.right_count }} строк · {{ item.right_receipt_count }} чеков · {{ item.right_category or "без категории" }}</p>
    </div>
</div>
<div class="suggestion-differences">
    <h3>Основание сравнения</h3>
    <ul class="suggestion-reasons">
        {% for reason in item.reasons %}
            <li>{{ reason }}</li>
        {% endfor %}
    </ul>
</div>
```

Do not repeat confidence in reasons or technical details.

- [ ] **Step 5: Strengthen pair geometry**

```css
.suggestion-card {
    display: grid;
    gap: 16px;
}

.suggestion-products {
    border-block: 1px solid var(--line);
    background: transparent;
}

.suggestion-products > div {
    padding: 18px;
}

.suggestion-products > div + div {
    border-left: 1px solid var(--line);
}

.suggestion-differences h3 {
    margin: 0 0 8px;
    font-size: .875rem;
}

@media (max-width: 559.98px) {
    .suggestion-products {
        grid-template-columns: 1fr;
    }

    .suggestion-products > div + div {
        border-top: 1px solid var(--line);
        border-left: 0;
    }
}
```

- [ ] **Step 6: Run contract**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_similar_products_emphasizes_pair_differences -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add app/web/templates/product_suggestions.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: prioritize differences in product suggestions"
```

---

### Task 10: Make Product Merge a Selection Workspace

**Files:**
- Modify: `app/web/templates/products_merge.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current search, selected checkboxes, canonical name, merge submission.
- Produces: one selection table plus one visually connected command area.

- [ ] **Step 1: Add merge hierarchy assertions**

```python
    def test_merge_connects_selection_to_canonical_result(self):
        html = self.html("/products/merge")
        self.assertIn("Выберите товары и задайте итоговое название", html)
        self.assertIn('class="merge-panel"', html)
        self.assertIn('class="merge-actions"', html)
        self.assertNotIn("Вернуться в аналитику", html)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_merge_connects_selection_to_canonical_result -v
```

Expected: `FAIL` on missing question copy or unrelated back action.

- [ ] **Step 3: Remove unrelated page-level navigation and state the task**

Use:

```html
<section class="page-header">
    <div>
        <p class="eyebrow">Нормализация</p>
        <h1>Объединение товаров</h1>
        <p class="muted">Выберите товары и задайте итоговое название</p>
    </div>
</section>
```

Remove the analytics back button. Navigation remains available in the sidebar.

- [ ] **Step 4: Put command area directly above selected rows**

Keep one form:

```html
<form method="post" action="{{ url_for('products_merge_submit') }}">
    <section class="surface merge-panel">
        <div class="merge-actions">
            <label>
                <span>Итоговое название</span>
                <input class="form-control" type="text" name="canonical_name" placeholder="Например: Молоко 2,5%" autocomplete="off" required>
            </label>
            <button class="btn btn-primary" type="submit">
                <i class="bi bi-intersect" aria-hidden="true"></i>
                Объединить выбранные
            </button>
        </div>
        <div class="table-responsive">
            <table class="table app-table align-middle merge-table">
                <thead>
                    <tr>
                        <th class="merge-check"><span class="visually-hidden">Выбор</span></th>
                        <th>Название</th>
                        <th class="text-end">Строк</th>
                        <th class="text-end">Чеков</th>
                        <th>Итоговое название</th>
                    </tr>
                </thead>
                <tbody>
                {% for product in products %}
                    <tr>
                        <td class="merge-check">
                            <input class="form-check-input" type="checkbox" name="selected_names" value="{{ product[0] }}" aria-label="Выбрать {{ product[0] }}">
                        </td>
                        <td><a href="{{ url_for('item_profile', name=product[0]) }}">{{ product[0] }}</a></td>
                        <td class="text-end">{{ product[1] }}</td>
                        <td class="text-end">{{ product[2] }}</td>
                        <td class="muted-cell">{{ product[3] or "—" }}</td>
                    </tr>
                {% else %}
                    <tr><td colspan="5"><p class="empty-message">Ничего не найдено.</p></td></tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </section>
</form>
```

Keep search secondary and above this form.

- [ ] **Step 5: Connect command and table visually**

```css
.merge-panel {
    padding: 0;
    overflow: hidden;
}

.merge-actions {
    margin: 0;
    padding: 16px 18px;
    border-bottom: 1px solid var(--line-strong);
    background: var(--surface-raised);
}

.merge-table {
    margin: 0;
}

.merge-table tbody tr:has(input:checked) {
    background: color-mix(in srgb, var(--primary) 9%, var(--surface));
    box-shadow: inset 3px 0 0 var(--primary);
}
```

Do not add a live selected counter or new JavaScript.

- [ ] **Step 6: Run contract**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_merge_connects_selection_to_canonical_result -v
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add app/web/templates/products_merge.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: connect product merge selection and action"
```

---

### Task 11: Replace Price-Quality KPI Wall with a Diagnostic Band

**Files:**
- Modify: `app/web/templates/price_data_quality.html`
- Modify: `app/web/static/style.css`
- Modify: `tests/test_visual_contract.py`

**Interfaces:**
- Consumes: current `summary` tuple, filters, diagnostic rows, statuses.
- Produces: compact coverage summary plus dominant issue register.

- [ ] **Step 1: Add data-quality assertions**

```python
    def test_price_quality_is_diagnostic_register_not_metric_wall(self):
        html = self.html("/data-quality/prices")
        self.assertIn("Где проблема в данных", html)
        self.assertIn('class="quality-summary"', html)
        self.assertNotIn('class="metric-grid"', html)
        self.assertNotIn('class="metric-card"', html)
        for copy in ("Строки", "Цена строки", "Цена единицы", "Нормализовано",
                     "Не определено", "Низкая уверенность", "Подозрительная цена"):
            self.assertIn(copy, html)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_price_quality_is_diagnostic_register_not_metric_wall -v
```

Expected: `FAIL` because current summary is ten equal cards with mixed language.

- [ ] **Step 3: State the diagnostic question**

Use:

```html
<section class="page-header">
    <div>
        <p class="eyebrow">Качество данных</p>
        <h1>Качество цен</h1>
        <p class="muted">Где проблема в данных и насколько она распространена</p>
    </div>
</section>
```

- [ ] **Step 4: Replace ten cards with one semantic definition list**

Use:

```jinja2
<dl class="quality-summary" aria-label="Покрытие ценовых данных">
    <div><dt>Строки</dt><dd>{{ summary[0] or 0 }}</dd></div>
    <div><dt>Цена строки</dt><dd>{{ summary[1] or 0 }}</dd></div>
    <div><dt>Цена единицы</dt><dd>{{ summary[2] or 0 }}</dd></div>
    <div><dt>Нормализовано</dt><dd>{{ summary[3] or 0 }}</dd></div>
    <div><dt>EUR/L</dt><dd>{{ summary[4] or 0 }}</dd></div>
    <div><dt>EUR/kg</dt><dd>{{ summary[5] or 0 }}</dd></div>
    <div><dt>EUR/шт.</dt><dd>{{ summary[6] or 0 }}</dd></div>
    <div><dt>Не определено</dt><dd>{{ summary[7] or 0 }}</dd></div>
    <div><dt>Низкая уверенность</dt><dd>{{ summary[8] or 0 }}</dd></div>
    <div><dt>Подозрительная цена</dt><dd>{{ summary[9] or 0 }}</dd></div>
</dl>
```

Keep EUR units because they are technical data, not system navigation copy.

- [ ] **Step 5: Translate filter and table UI without translating source data**

Use these filter labels:

```jinja2
<option value="all" {% if issue_filter == "all" %}selected{% endif %}>Все проблемы</option>
<option value="unknown" {% if issue_filter == "unknown" %}selected{% endif %}>Единица не определена</option>
<option value="low_confidence" {% if issue_filter == "low_confidence" %}selected{% endif %}>Низкая уверенность</option>
<option value="missing_package" {% if issue_filter == "missing_package" %}selected{% endif %}>Нет размера упаковки</option>
<option value="suspicious" {% if issue_filter == "suspicious" %}selected{% endif %}>Подозрительная цена</option>
```

Use these table headings:

```html
<th>Товар</th>
<th>Чек</th>
<th>Магазин</th>
<th>Дата</th>
<th>Количество</th>
<th>Сумма строки</th>
<th>Цена единицы</th>
<th>Упаковка</th>
<th>Нормализованная цена</th>
<th>Уверенность</th>
```

For missing display values, render `не определено`; keep non-empty units, merchant names, product names, and receipt evidence verbatim.

- [ ] **Step 6: Make problem rows primary**

Add a section heading before the existing table:

```html
<div class="section-title">
    <div>
        <p class="eyebrow">Диагностика</p>
        <h2>Строки, требующие внимания</h2>
    </div>
</div>
```

Keep all existing columns, row values, filters, and empty state.

- [ ] **Step 7: Add compact high-density CSS**

```css
.quality-summary {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    margin: 0 0 18px;
    border-block: 1px solid var(--line);
}

.quality-summary div {
    display: grid;
    gap: 4px;
    padding: 12px 10px;
}

.quality-summary dt {
    color: var(--muted);
    font-size: .75rem;
    font-weight: 600;
}

.quality-summary dd {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}

@media (max-width: 767.98px) {
    .quality-summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
```

- [ ] **Step 8: Run quality and language contracts**

Run:

```powershell
python -m unittest tests.test_visual_contract.VisualContractTests.test_price_quality_is_diagnostic_register_not_metric_wall tests.test_visual_contract.VisualContractTests.test_system_copy_is_russian_and_radar_stays_absent -v
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add app/web/templates/price_data_quality.html app/web/static/style.css tests/test_visual_contract.py
git commit -m "style: make price quality a diagnostic register"
```

---

### Task 12: Complete Responsive, Visual Accessibility, and Documentation Verification

**Files:**
- Modify: `app/web/static/style.css`
- Modify: `app/web/static/home-story.css`
- Modify: `tests/test_visual_contract.py`
- Modify: `DESIGN.md`

**Interfaces:**
- Consumes: all completed screen structures.
- Produces: final 320px/200% behavior, consistent states, and updated design-system documentation.

- [ ] **Step 1: Add final static accessibility assertions**

Add:

```python
    def test_visual_states_and_responsive_contract_exist(self):
        css = STYLE.read_text(encoding="utf-8")
        for rule in (
            ":focus-visible",
            "@media (max-width: 559.98px)",
            "@media (prefers-reduced-motion: reduce)",
            "font-variant-numeric: tabular-nums",
            ".receipt-document.is-expanded",
            ".nav-link.active",
            ".btn:disabled",
            ".state-error",
        ):
            self.assertIn(rule, css)

    def test_controls_keep_visible_or_programmatic_labels(self):
        analytics = self.html("/analytics")
        for control_id in ("startDate", "endDate", "storeFilter", "categoryFilter", "itemFilter"):
            self.assertRegex(analytics, rf'<label[^>]+for="{control_id}"')

        upload = self.html("/upload")
        self.assertRegex(upload, r'<label[^>]+for="fileInput"')

        for path, field_names in (
            ("/products/review", ("q", "filter", "sort", "limit", "category")),
            ("/products/merge", ("q", "canonical_name")),
            ("/data-quality/prices", ("filter", "limit")),
        ):
            html = self.html(path)
            self.assertIn("<label", html)
            for field_name in field_names:
                self.assertRegex(html, rf'name="{field_name}"')
```

If a visible wrapping label is converted to `for`/`id`, update this test with the exact new pair in the same commit.

- [ ] **Step 2: Run final contract and record any real failures**

Run:

```powershell
python -m unittest tests.test_visual_contract -v
```

Expected: all visual contract tests pass.

- [ ] **Step 3: Consolidate responsive rules at the final override layer**

Ensure the final CSS contains:

```css
@media (max-width: 559.98px) {
    .app-container {
        width: 100%;
        padding-inline: 14px;
    }

    .filters-grid,
    .review-card-main,
    .review-category-form,
    .merge-actions,
    .receipt-inline-detail {
        grid-template-columns: 1fr;
    }

    .filters-grid .btn,
    .review-category-form .btn,
    .merge-actions .btn {
        width: 100%;
    }

    .app-table {
        min-width: max-content;
    }

    .table-responsive {
        overflow-x: auto;
        overscroll-behavior-inline: contain;
    }

    .receipt-document-toggle {
        grid-template-columns: minmax(0, 1fr) auto;
    }

    .receipt-items,
    .receipt-statuses,
    .receipt-signal {
        grid-column: 1;
    }

    .receipt-total,
    .receipt-expand-mark {
        grid-column: 2;
    }
}

@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        scroll-behavior: auto !important;
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: .01ms !important;
    }
}
```

Do not hide primary evidence or actions on mobile. Do not convert every table into unrelated cards.

- [ ] **Step 4: Verify keyboard-visible states**

Ensure shared controls use:

```css
:where(a, button, input, select, summary, [tabindex]):focus-visible {
    outline: 3px solid var(--focus-ring);
    outline-offset: 2px;
}

.btn:disabled,
.btn.disabled,
[aria-disabled="true"] {
    color: var(--muted);
    border-color: var(--line);
    background: var(--surface-soft);
    opacity: .62;
}
```

Selected, expanded, warning, verified, disabled, and error states must each retain a text label or structural cue in markup.

- [ ] **Step 5: Update `DESIGN.md` after the code is stable**

Replace its screen-role summary with:

```markdown
## Composition Modes

- Reading: Intelligence Briefing. Low density; conclusion, reason, evidence, next destination.
- Register: receipt archive and receipt detail. Medium density; search, sort, scan, expand.
- Investigation: analytics. Medium density; filters, one result band, primary chart, supporting views.
- Review: upload, category review, similar products, merge, and price quality. Medium-high density; subject, evidence, decision.

All modes share shell, typography roles, action hierarchy, filters, tables, states, evidence treatment, spacing rhythm, borders, radius, semantic color, focus, and responsive rules. They do not share one page composition.

## Visual Constitution Checks

Before accepting UI work, verify one dominant question, one main focus, no repeated values, no decorative container, no metadata badge without status meaning, no color-only state, no hidden primary meaning, no generic KPI wall, preserved evidence, adapted mobile composition, and unchanged native control behavior.
```

Keep existing token values and component inventory accurate; remove references to components deleted during Tasks 3, 6, 8, and 11.

- [ ] **Step 6: Run full automated suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 7: Perform exact visual verification**

Start the app:

```powershell
python run.py
```

Inspect these routes at 1440×900, 768×1024, and 320×640:

```text
/
/?view=receipts
/receipt/1
/analytics
/upload
/products/review
/products/suggestions
/products/merge
/data-quality/prices
```

For each route, verify:

- one obvious page focus within the first viewport;
- no mixed system-language copy;
- no Radar;
- no equal KPI-card wall;
- no card-inside-card-inside-card;
- one page-level primary action maximum;
- primary meaning visible without hover, tooltip, drawer, or animation;
- keyboard focus visible;
- active navigation distinct from muted and disabled states;
- status includes text or structure, not color alone;
- no horizontal page scroll at 320px; only deliberate table-local scrolling;
- open mobile navigation overlays below the app bar and does not push page content down;
- evidence stays reachable and readable;
- reduced-motion mode preserves meaning.

- [ ] **Step 8: Commit**

```powershell
git add app/web/static/style.css app/web/static/home-story.css tests/test_visual_contract.py DESIGN.md
git commit -m "docs: certify visual constitution implementation"
```

---

## Self-Review Record

### Spec Coverage

- Quiet Evidence Instrument: Tasks 2–12.
- Four distinct composition modes: Tasks 3, 4, 6, 7–11.
- One dominant question and hierarchy budget: each screen task.
- Evidence and uncertainty: Tasks 3, 5, 8, 9, 11.
- Layered density: reading Task 3, register Tasks 4–5, investigation Task 6, review Tasks 7–11.
- One system language: Tasks 2, 4, 5, 11.
- Native behavior, focus, touch, responsive, reduced motion: Tasks 2, 5, 7, 12.
- Semantic color and non-color state cues: Tasks 2, 5, 12.
- Radar remains absent: Tasks 1, 4, 12.
- Prohibited generic dashboard/card wall: Tasks 6, 8, 9, 11.
- No new product or backend behavior: Global Constraints and every task interface.

### Deliberate Non-Goals

- No new analytics, evidence model, receipt fields, review logic, bulk action, mobile feature, route, or API.
- No component framework, token migration, CSS preprocessor, TypeScript, screenshot-testing dependency, font, or icon package.
- No Radar replacement.
- No literal propagation of Briefing composition to register, investigation, or review screens.
- No redesign of original receipt/product/source data.

### Type and Interface Consistency

- Existing Flask endpoint names and form field names remain unchanged.
- Existing DOM IDs used by JavaScript remain unchanged.
- New shared hooks are CSS classes only: `mode-reading`, `mode-register`, `mode-investigation`, `mode-review`, `evidence-block`, `analytics-result`, and `quality-summary`.
- Existing data contracts remain unchanged; Chart.js changes only chart type and presentation options.

import json
import re
import tempfile
import unittest
from datetime import date
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
        self.app.config["TODAY_PROVIDER"] = lambda: date(2026, 7, 14)
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def test_shared_routes_render(self):
        paths = (
            "/",
            "/upload",
            "/analytics",
            "/products/merge",
            "/products/suggestions",
            "/products/review",
            "/data-quality/prices",
            "/item/test",
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_navigation_marks_current_page(self):
        for path, href in (("/", "/"), ("/analytics", "/analytics"), ("/upload", "/upload")):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                active_link = rf'<a[^>]+href="{re.escape(href)}"[^>]+aria-current="page"'
                self.assertRegex(html, active_link)

    def test_global_theme_tokens_and_reduced_motion_exist(self):
        css_path = Path(__file__).parents[1] / "app" / "web" / "static" / "style.css"
        css = css_path.read_text(encoding="utf-8")

        for declaration in (
            '--color-bg: var(--palette-ink-950)',
            '--color-surface: #202020',
            '--color-accent: var(--palette-mint-500)',
            '--color-success: #35b987',
            '--color-warning: #e8b04c',
            '--color-danger: #e6636b',
            'html[data-theme="light"]',
            '--color-bg: #f7f8f6',
            '--color-accent: #08785b',
            '--story-ambient-layer:',
        ):
            self.assertIn(declaration, css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

    def test_motion_cleanup_uses_scoped_native_transitions(self):
        project_root = Path(__file__).parents[1]
        static_dir = project_root / "app" / "web" / "static"
        template_dir = project_root / "app" / "web" / "templates"
        css = (static_dir / "style.css").read_text(encoding="utf-8")
        drawer_script = (static_dir / "receipt-evidence-drawer.js").read_text(encoding="utf-8")
        upload = (template_dir / "upload.html").read_text(encoding="utf-8")

        for token in (
            "--ease-out: cubic-bezier(.23, 1, .32, 1)",
            "--ease-in-out: cubic-bezier(.77, 0, .175, 1)",
            "--ease-drawer: cubic-bezier(.32, .72, 0, 1)",
        ):
            self.assertIn(token, css)

        self.assertNotIn("scroll-behavior: smooth", css)
        self.assertIn("scroll-behavior: auto", css)
        self.assertNotIn("transition-duration: .01ms", css)
        self.assertNotIn("transition: width", css)
        self.assertNotIn("transition: height", css)

        skip_link = re.search(r"\.skip-link\s*\{(?P<body>.*?)\}", css, flags=re.S)
        self.assertIsNotNone(skip_link)
        for property_name in ("opacity", "transform", "transition"):
            self.assertNotIn(property_name, skip_link.group("body"))

        self.assertRegex(
            css,
            r"\.receipt-expand-mark \.app-icon\s*\{[^}]*transition:\s*transform var\(--motion-fast\) var\(--ease-out\)",
        )
        self.assertRegex(css, r"\.progress-bar\s*\{[^}]*transform-origin:\s*left center")
        self.assertIn("transform: scaleX(var(--progress-scale, 0))", css)
        self.assertNotIn("progressBar.style.width", upload)
        self.assertIn('style="--progress-scale:0"', upload)

        self.assertRegex(
            css,
            r"\.receipt-drawer-scrim\s*\{[^}]*opacity:\s*0;[^}]*transition:\s*opacity",
        )
        self.assertIn("transition: transform 220ms var(--ease-drawer)", css)
        self.assertIn("requestAnimationFrame", drawer_script)
        self.assertIn("transitionend", drawer_script)
        self.assertIn("function finishClose", drawer_script)
        self.assertIn("activeTrigger?.focus()", drawer_script)

    def test_semantic_theme_tokens_alias_existing_component_tokens(self):
        css_path = Path(__file__).parents[1] / "app" / "web" / "static" / "style.css"
        css = css_path.read_text(encoding="utf-8")

        for declaration in (
            "--palette-ink-950: #161616",
            "--palette-ink-900: #1e1e1e",
            "--palette-ink-800: #2b2b2b",
            "--palette-mint-500: #17d1ac",
            "--color-bg: var(--palette-ink-950)",
            "--color-bg-elevated: var(--palette-ink-900)",
            "--color-surface: #202020",
            "--color-surface-muted: var(--palette-ink-800)",
            "--color-text: #f2f5f7",
            "--color-text-muted: #a6b1bd",
            "--color-accent-soft: rgb(23 209 172 / .14)",
            "--color-positive: var(--color-success)",
            "--color-negative: var(--color-danger)",
            "--color-shadow: rgb(0 0 0 / .28)",
            "--bg: var(--color-bg)",
            "--surface: var(--color-surface)",
            "--primary: var(--color-accent)",
        ):
            self.assertIn(declaration, css)
        self.assertNotIn("--archive-", css)
        self.assertNotIn("--story-palette-", css)

        home_css = css_path.with_name("home-story.css").read_text(encoding="utf-8")
        self.assertIn("--primary-dark: var(--color-accent-hover)", home_css)

    def test_receipt_workspace_is_a_single_partial_and_empty_state_renders(self):
        template_dir = Path(__file__).parents[1] / "app" / "web" / "templates"
        index = (template_dir / "index.html").read_text(encoding="utf-8")
        workspace = (template_dir / "_receipt_workspace.html").read_text(encoding="utf-8")

        self.assertEqual(index.count('{% include "_receipt_workspace.html" %}'), 2)
        self.assertNotIn('<section class="receipts-workspace"', index)
        self.assertEqual(workspace.count('<section class="receipts-workspace'), 1)
        self.assertIn('name="store_search"', workspace)
        self.assertIn('href="{{ url_for(\'upload\') }}"', workspace)
        self.assertEqual(index.count("const receiptList = document.getElementById('receiptTable')"), 1)

        overview = self.client.get("/")
        archive = self.client.get("/?view=receipts")
        filtered = self.client.get("/?view=receipts&period=all_time&store_search=MAXIMA")
        self.assertEqual(overview.status_code, 200)
        overview_html = overview.get_data(as_text=True)
        self.assertIn('class="home-document is-empty"', overview_html)
        self.assertIn('data-story-act="month"', overview_html)
        self.assertNotIn('data-story-act="insight"', overview_html)
        self.assertNotIn('class="story-timeline"', overview_html)
        self.assertIn("После первого импорта", overview_html)
        self.assertIn('id="receipt-workspace-start"', overview_html)
        self.assertIn('href="/upload"', overview_html)
        self.assertNotIn("js-loading", overview_html)
        self.assertEqual(archive.status_code, 200)
        self.assertIn("В выбранном периоде чеков нет", archive.get_data(as_text=True))
        self.assertEqual(filtered.status_code, 200)
        filtered_html = filtered.get_data(as_text=True)
        self.assertIn('value="MAXIMA"', filtered_html)
        self.assertIn("Чеки не найдены", filtered_html)
        self.assertIn("Сбросить фильтры", filtered_html)
        self.assertIn('href="/upload"', filtered_html)

    def test_archive_register_and_expanded_receipt_follow_visual_contract(self):
        db.add_receipt_with_items(
            "2026-07-05",
            "RIMI",
            12.5,
            "register-contract",
            [{"name": "Длинное название товара", "quantity": 1.5, "price": 12.5, "category": "прочее"}],
        )
        html = self.client.get("/?view=receipts&period=current_month").get_data(as_text=True)
        workspace = (
            Path(__file__).parents[1] / "app" / "web" / "templates" / "_receipt_workspace.html"
        ).read_text(encoding="utf-8")

        self.assertEqual(html.count('<h1 id="receipt-list-title">Архив чеков</h1>'), 1)
        self.assertLess(html.index("receipts-compact-header"), html.index("receipt-summary-band"))
        self.assertLess(html.index("receipt-summary-band"), html.index("receipt-filter-panel"))
        self.assertLess(html.index("receipt-filter-panel"), html.index("receipt-register"))
        self.assertIn('aria-label="Реестр чеков"', html)
        self.assertIn('<label for="receiptPeriodSelect">Период</label>', html)
        self.assertIn('<label for="searchInput">Магазин</label>', html)
        self.assertNotIn("receipt-filter-chips", html)
        self.assertNotIn("receipt-signal", html)
        self.assertNotIn("Receipt Workspace", html)
        self.assertNotIn(">Filters<", html)
        self.assertNotIn(">Clear filters<", html)
        self.assertNotIn(">Review<", html)
        self.assertNotIn(">OK<", html)

        self.assertIn('id="receipt-toggle-1"', html)
        self.assertIn('aria-controls="receipt-detail-1"', html)
        self.assertIn('id="receipt-detail-1"', html)
        self.assertIn('role="region"', html)
        self.assertIn('aria-labelledby="receipt-toggle-1"', html)
        self.assertIn('class="receipt-item-head"', html)
        self.assertIn('data-label="Количество">1.5</span>', html)
        self.assertIn("Состав чека", html)
        self.assertIn("Проверка данных", html)

        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertRegex(html, r'class="receipt-drawer"[\s\S]*?hidden')
        self.assertLess(html.index("<h3>Источник</h3>"), html.index("<h3>Подтверждено</h3>"))
        self.assertLess(html.index("<h3>Подтверждено</h3>"), html.index("<h3>Ограничения</h3>"))
        self.assertLess(html.index("<h3>Ограничения</h3>"), html.index("<h3>Трассировка</h3>"))
        self.assertNotIn("01 /", html)

        ids = re.findall(r'\sid="([^"]+)"', html)
        self.assertEqual(len(ids), len(set(ids)))
        index_script = (
            Path(__file__).parents[1] / "app" / "web" / "templates" / "index.html"
        ).read_text(encoding="utf-8")
        drawer_script = (
            Path(__file__).parents[1] / "app" / "web" / "static" / "receipt-evidence-drawer.js"
        ).read_text(encoding="utf-8")
        self.assertIn("receipt-evidence-drawer.js", index_script)
        self.assertIn("closeButton?.focus()", drawer_script)
        self.assertIn("activeTrigger?.focus()", drawer_script)

    def test_standalone_receipt_is_an_expanded_archive_document(self):
        db.add_receipt_with_items(
            "2026-07-05",
            "RIMI Hyper",
            18.75,
            "standalone-contract",
            [
                {
                    "name": "Очень длинное название товара для проверки устойчивого переноса в документальном режиме",
                    "quantity": 1.5,
                    "price": 12.5,
                    "category": "продукты",
                },
                {
                    "name": "Молоко",
                    "quantity": 1,
                    "price": 6.25,
                    "category": "продукты",
                },
            ],
        )
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE items SET price_parse_confidence = 0.5 WHERE receipt_id = 1 AND id = 1"
            )
            conn.execute(
                "UPDATE items SET price_parse_confidence = 0.95 WHERE receipt_id = 1 AND id = 2"
            )
            conn.commit()

        response = self.client.get(
            "/receipt/1",
            query_string={
                "return_to": "/?view=receipts&period=all_time&store_search=RIMI",
            },
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertEqual(len(re.findall(r"<h1\b", html)), 1)
        self.assertIn('<h1 id="receipt-detail-title">RIMI Hyper</h1>', html)
        self.assertIn('<time datetime="2026-07-05">2026-07-05</time>', html)
        self.assertIn("18.75 €", html)
        self.assertIn("standalone-contract", html)
        self.assertIn(
            'href="/?view=receipts&amp;period=all_time&amp;store_search=RIMI"',
            html,
        )
        self.assertEqual(html.count("data-receipt-item-row"), 2)
        self.assertIn('data-label="Количество">1.5</span>', html)
        self.assertIn("Очень длинное название товара", html)
        self.assertIn("К проверке", html)
        self.assertIn("Проверено", html)
        self.assertIn("Цена пока несопоставима", html)
        self.assertIn("Не удалось надёжно определить цену за кг, литр или штуку.", html)
        self.assertIn("Источники и ограничения", html)
        self.assertIn("data-open-receipt-drawer", html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertLess(html.index("<h3>Источник</h3>"), html.index("<h3>Подтверждено</h3>"))
        self.assertLess(html.index("<h3>Подтверждено</h3>"), html.index("<h3>Ограничения</h3>"))
        self.assertLess(html.index("<h3>Ограничения</h3>"), html.index("<h3>Трассировка</h3>"))
        self.assertNotIn('class="surface"', html)
        self.assertNotIn('class="table app-table', html)
        self.assertNotIn("receipt-insights-grid", html)

    def test_standalone_receipt_empty_and_not_found_states_are_distinct(self):
        db.add_receipt_with_items(
            "2026-07-06",
            "",
            0,
            "empty-document",
            [],
        )

        empty = self.client.get("/receipt/1")
        missing = self.client.get("/receipt/999")
        malformed = self.client.get("/receipt/not-a-number")

        self.assertEqual(empty.status_code, 200)
        empty_html = empty.get_data(as_text=True)
        self.assertIn("Магазин не указан", empty_html)
        self.assertIn("В чеке нет товарных позиций", empty_html)
        self.assertIn("Метаданные документа сохранены", empty_html)
        self.assertEqual(len(re.findall(r"<h1\b", empty_html)), 1)

        self.assertEqual(missing.status_code, 404)
        missing_html = missing.get_data(as_text=True)
        self.assertIn("Чек не найден", missing_html)
        self.assertIn("Чек #999 отсутствует", missing_html)
        self.assertEqual(len(re.findall(r"<h1\b", missing_html)), 1)
        self.assertEqual(malformed.status_code, 404)

    def test_standalone_receipt_return_path_is_strictly_local_archive(self):
        db.add_receipt_with_items(
            "2026-07-07",
            "MAXIMA",
            4.5,
            "safe-return",
            [],
        )
        valid = self.client.get(
            "/receipt/1",
            query_string={
                "return_to": "/?view=receipts&period=month:2026-07&store_search=MAXIMA",
            },
        ).get_data(as_text=True)
        self.assertIn(
            'href="/?view=receipts&amp;period=month:2026-07&amp;store_search=MAXIMA"',
            valid,
        )

        for unsafe in (
            "https://evil.test/",
            "//evil.test/",
            "javascript:alert(1)",
            "/analytics",
            "/?view=receipts&period=invalid",
            "/?view=receipts&period=all_time&unexpected=1",
        ):
            with self.subTest(unsafe=unsafe):
                html = self.client.get(
                    "/receipt/1",
                    query_string={"return_to": unsafe},
                ).get_data(as_text=True)
                self.assertIn('href="/?view=receipts"', html)
                self.assertNotIn("evil.test", html)
                self.assertNotIn("javascript:", html)

    def test_archive_and_standalone_share_one_evidence_drawer_implementation(self):
        template_dir = Path(__file__).parents[1] / "app" / "web" / "templates"
        workspace = (template_dir / "_receipt_workspace.html").read_text(encoding="utf-8")
        receipt = (template_dir / "receipt.html").read_text(encoding="utf-8")
        drawer = (template_dir / "_receipt_evidence_drawer.html").read_text(encoding="utf-8")
        index = (template_dir / "index.html").read_text(encoding="utf-8")

        self.assertEqual(workspace.count('{% include "_receipt_evidence_drawer.html" %}'), 1)
        self.assertEqual(receipt.count('{% include "_receipt_evidence_drawer.html" %}'), 1)
        self.assertEqual(drawer.count('class="receipt-drawer"'), 1)
        self.assertIn("receipt-evidence-drawer.js", index)
        self.assertIn("receipt-evidence-drawer.js", receipt)

    def test_story_html_is_semantic_and_core_paths_do_not_require_javascript(self):
        html = self.client.get("/").get_data(as_text=True)
        without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)

        self.assertRegex(without_scripts, r'<article class="home-document[^>]*aria-labelledby="story-month-title"')
        self.assertRegex(without_scripts, r'<section class="story-act story-act-month"[^>]*aria-labelledby="story-month-title"')
        self.assertIn('href="/?view=receipts&amp;period=current_month"', without_scripts)
        self.assertIn('method="get" action="/" class="period-control receipt-period-control"', without_scripts)
        self.assertIn('class="btn btn-outline-secondary receipt-period-submit"', without_scripts)
        self.assertIn('name="store_search"', without_scripts)

        direct = self.client.get("/?view=receipts").get_data(as_text=True)
        self.assertNotIn("home-story.css", direct)
        self.assertNotIn('data-story-act="month"', direct)

    def test_story_visit_metadata_replay_and_direct_archive_isolation(self):
        db.add_receipt_with_items("2026-07-05", "RIMI", 12.5, "visit-mode-1", [])
        html = self.client.get("/").get_data(as_text=True)
        metadata_match = re.search(
            r'<script id="story-metadata" type="application/json">(.*?)</script>',
            html,
            flags=re.S,
        )

        self.assertIsNotNone(metadata_match)
        metadata = json.loads(metadata_match.group(1))
        self.assertEqual(set(metadata), {"month_key", "signature", "last_receipt_id", "has_story"})
        self.assertEqual(metadata["month_key"], "2026-07")
        self.assertTrue(metadata["signature"])
        self.assertEqual(metadata["last_receipt_id"], 1)
        self.assertTrue(metadata["has_story"])
        self.assertIn('src="/static/home-story.js"', html)
        self.assertIn('class="story-replay"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('aria-controls="story-month-details story-insight-copy-details story-evidence-details"', html)

        without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)
        self.assertNotIn(metadata["signature"], without_scripts)
        self.assertIn('id="story-month-details"', without_scripts)
        self.assertIn('data-story-act="insight"', without_scripts)
        self.assertIn('id="receipt-workspace-start"', without_scripts)

        direct = self.client.get("/?view=receipts").get_data(as_text=True)
        self.assertNotIn('id="story-metadata"', direct)
        self.assertNotIn("home-story.js", direct)
        self.assertNotIn('class="story-replay"', direct)

    def test_story_visit_script_keeps_storage_minimal_and_dependency_free(self):
        script_path = Path(__file__).parents[1] / "app" / "web" / "static" / "home-story.js"
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("receipt-intelligence:story:v1:", script)
        self.assertIn("function determineStoryMode", script)
        self.assertIn("version: VERSION", script)
        self.assertIn("signature: metadata.signature", script)
        self.assertIn("viewed_at: new Date().toISOString()", script)
        self.assertIn("last_receipt_id: metadata.last_receipt_id", script)
        self.assertNotIn("import ", script)
        self.assertNotIn("store_search", script)

    def test_story_motion_is_progressive_isolated_and_accessible(self):
        db.add_receipt_with_items("2026-07-05", "RIMI", 12.5, "motion-1", [])
        html = self.client.get("/").get_data(as_text=True)
        direct = self.client.get("/?view=receipts").get_data(as_text=True)
        without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)
        static_dir = Path(__file__).parents[1] / "app" / "web" / "static"
        motion = (static_dir / "home-story-motion.js").read_text(encoding="utf-8")
        visit = (static_dir / "home-story.js").read_text(encoding="utf-8")

        self.assertIn('src="/static/home-story-motion.js"', html)
        self.assertNotIn("home-story-motion.js", direct)
        self.assertIn("data-story-total-source", without_scripts)
        self.assertIn("data-story-total-destination", without_scripts)
        self.assertIn('data-story-act="insight"', without_scripts)
        self.assertIn('id="receipt-workspace-start"', without_scripts)

        self.assertIn("IntersectionObserver", motion)
        self.assertIn("prefers-reduced-motion: reduce", motion)
        self.assertIn("story:modechange", motion)
        self.assertIn("'replay'", motion)
        self.assertIn("clone.setAttribute('aria-hidden', 'true')", motion)
        self.assertIn("visibilitychange", motion)
        self.assertNotIn("localStorage", motion)
        self.assertNotIn("receipt-intelligence:story:v1:", motion)

        self.assertIn("receipt-intelligence:story:v1:", visit)
        self.assertIn("viewed_at: new Date().toISOString()", visit)

    def test_cinematic_is_canonical_and_legacy_story_modes_redirect(self):
        db.add_receipt_with_items("2026-07-05", "RIMI", 12.5, "ab-mode-1", [])
        default_html = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-story-presentation="cinematic"', default_html)
        self.assertNotIn('data-story-presentation="product"', default_html)
        self.assertNotIn("story_mode=", default_html)

        for legacy_url in (
            "/?story_mode=product",
            "/?story_mode=cinematic",
            "/?story_mode=unknown",
            "/?story_mode=",
        ):
            response = self.client.get(legacy_url, follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/")

        legacy_month = self.client.get(
            "/?story_mode=product&month=2026-07",
            follow_redirects=False,
        )
        self.assertEqual(legacy_month.status_code, 302)
        self.assertEqual(legacy_month.headers["Location"], "/?month=2026-07")

        self.assertEqual(default_html.count('data-story-act="month"'), 1)
        self.assertEqual(default_html.count('data-story-act="insight"'), 1)
        self.assertEqual(default_html.count('data-story-act="workspace"'), 1)
        self.assertEqual(default_html.count('id="receipt-workspace-start"'), 1)

    def test_story_debug_remains_explicit_without_product_compare_ui(self):
        plain = self.client.get("/").get_data(as_text=True)
        debugged = self.client.get(
            "/?story_compare=1&story_debug=1&period=all_time&store_search=RIMI"
        ).get_data(as_text=True)

        self.assertNotIn("data-story-compare", plain)
        self.assertNotIn("data-story-debug", plain)
        self.assertNotIn("data-story-compare", debugged)
        self.assertEqual(debugged.count("data-story-debug"), 1)
        self.assertIn('data-debug-presentation>cinematic</output>', debugged)
        self.assertNotIn(">Product</a>", debugged)
        self.assertNotIn(">Cinematic</a>", debugged)

    def test_story_ab_assets_and_direct_archive_remain_isolated(self):
        direct = self.client.get(
            "/?view=receipts&story_mode=cinematic&story_compare=1&story_debug=1",
            follow_redirects=True,
        ).get_data(as_text=True)
        motion_path = Path(__file__).parents[1] / "app" / "web" / "static" / "home-story-motion.js"
        visit_path = Path(__file__).parents[1] / "app" / "web" / "static" / "home-story.js"
        css_path = Path(__file__).parents[1] / "app" / "web" / "static" / "home-story.css"
        motion = motion_path.read_text(encoding="utf-8")
        visit = visit_path.read_text(encoding="utf-8")
        css = css_path.read_text(encoding="utf-8")

        self.assertNotIn("home-story-motion.js", direct)
        self.assertNotIn("data-story-presentation", direct)
        self.assertNotIn("data-story-compare", direct)
        self.assertNotIn("data-story-debug", direct)
        self.assertNotIn("story_mode", visit)
        self.assertNotIn("story_mode", motion)
        self.assertNotIn("localStorage", motion)
        self.assertIn("document.addEventListener('story:sequencecomplete'", visit)
        self.assertIn("mode = 'repeat';", visit)
        self.assertIn("replayButton.setAttribute('aria-disabled', 'false')", visit)
        self.assertIn("class ProductMotionController", motion)
        self.assertIn("class CinematicStoryController", motion)
        self.assertIn("element.animate", motion)
        self.assertIn("animation.finished", motion)
        self.assertIn("data-story-skip", motion)
        self.assertIn("data-story-total-destination", motion)
        self.assertIn("this.settleSummary('complete')", motion)
        self.assertIn("this.settleSummary('static')", motion)
        self.assertNotIn("async handoff(generation)", motion)
        self.assertNotIn("await this.handoff(generation)", motion)
        self.assertIn("{ opacity: 0, transform:", motion)
        self.assertNotIn("this.onScroll", motion)
        self.assertNotIn("scheduleRender", motion)
        self.assertNotIn("ResizeObserver", motion)
        self.assertNotIn("--cinematic-progress", motion)
        self.assertIn("mode === 'repeat'", motion)
        self.assertIn("mode === 'update'", motion)
        self.assertIn("mode === 'replay'", motion)
        self.assertNotIn('story-scene-range', css)
        self.assertNotIn('story-scene-sticky', css)
        self.assertNotIn('position: sticky', css)
        self.assertNotIn('dvh', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('data-story-presentation="product"', css)
        self.assertIn('data-story-presentation="cinematic"', css)
        self.assertIn('[data-cinematic-phase="complete"]', css)
        self.assertIn('.story-evidence {', css)
        self.assertIn('[data-story-receipt] {', css)
        self.assertNotIn('data-cinematic-handoff-complete', css)

    def test_story_no_js_markup_keeps_both_acts_and_archive_visible(self):
        db.add_receipt_with_items("2026-07-05", "RIMI", 12.5, "no-js-ab-1", [])
        html = self.client.get("/").get_data(as_text=True)
        without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)

        self.assertIn('data-story-act="month"', without_scripts)
        self.assertIn('data-story-act="insight"', without_scripts)
        self.assertIn('data-story-act="workspace"', without_scripts)
        self.assertIn('data-story-narrative', without_scripts)
        self.assertNotIn('class="story-timeline"', without_scripts)
        self.assertNotIn('data-story-cinematic-active', without_scripts)
        self.assertIn('href="/?view=receipts&amp;period=current_month"', without_scripts)

    def test_legacy_product_url_cannot_restore_product_markup(self):
        db.add_receipt_with_items("2026-07-05", "RIMI", 12.5, "timeline-scope-1", [])
        cinematic = self.client.get("/").get_data(as_text=True)
        legacy_product = self.client.get(
            "/?story_mode=product",
            follow_redirects=True,
        ).get_data(as_text=True)

        self.assertNotIn('class="story-timeline"', cinematic)
        self.assertNotIn('data-story-timeline-event', cinematic)
        self.assertNotIn('story-timeline-help', cinematic)
        self.assertIn('data-story-skip', cinematic)
        self.assertIn('data-story-presentation="cinematic"', legacy_product)
        self.assertNotIn('data-story-presentation="product"', legacy_product)
        self.assertNotIn('class="story-timeline"', legacy_product)
        self.assertIn('data-story-skip', legacy_product)

    def test_cinematic_month_selector_rebuilds_story_and_archive_context(self):
        db.add_receipt_with_items("2026-01-05", "LIDL", 11, "month-jan", [])
        db.add_receipt_with_items("2026-05-08", "MAXIMA", 42, "month-may", [])
        db.add_receipt_with_items("2026-07-09", "RIMI", 99, "month-july", [])

        may = self.client.get("/?month=2026-05").get_data(as_text=True)
        fallback = self.client.get("/?month=2035-12").get_data(as_text=True)
        legacy_product = self.client.get(
            "/?story_mode=product&month=2026-05",
            follow_redirects=True,
        ).get_data(as_text=True)
        archive = self.client.get(
            "/?view=receipts&period=month:2026-05"
        ).get_data(as_text=True)

        self.assertIn('id="storyMonthSelect"', may)
        self.assertLess(may.index('value="2026-07"'), may.index('value="2026-05"'))
        self.assertLess(may.index('value="2026-05"'), may.index('value="2026-01"'))
        self.assertRegex(may, r'value="2026-05"\s+selected')
        self.assertIn('<h1 id="story-month-title">Май 2026</h1>', may)
        self.assertIn('Итого за месяц 42.00 евро', may)
        self.assertIn('month-may', may)
        self.assertNotIn('month-july', may)
        self.assertIn('period=month:2026-05', may)
        self.assertIn('class="receipt-summary-period"', may)
        self.assertIn('<strong>Май 2026</strong>', may)
        self.assertIn('class="receipt-summary-total" data-story-total-destination', may)

        metadata_match = re.search(
            r'<script id="story-metadata" type="application/json">(.*?)</script>',
            may,
            flags=re.S,
        )
        self.assertEqual(json.loads(metadata_match.group(1))["month_key"], "2026-05")
        self.assertIn('value="2026-05"', may)
        self.assertNotIn('name="story_mode"', may)

        self.assertIn('<h1 id="story-month-title">Июль 2026</h1>', fallback)
        self.assertIn('id="storyMonthSelect"', legacy_product)
        self.assertIn('<h1 id="story-month-title">Май 2026</h1>', legacy_product)

        self.assertNotIn('id="story-metadata"', archive)
        self.assertIn('value="month:2026-05" selected', archive)
        self.assertIn('month-may', archive)
        self.assertNotIn('month-july', archive)
        self.assertIn('Май 2026', archive)

    def test_theme_bootstrap_is_global_prepaint_and_whitelisted(self):
        base_path = Path(__file__).parents[1] / "app" / "web" / "templates" / "base.html"
        theme_path = Path(__file__).parents[1] / "app" / "web" / "static" / "theme.js"
        base = base_path.read_text(encoding="utf-8")
        theme = theme_path.read_text(encoding="utf-8")

        bootstrap = base.index("receipt-intelligence:theme:v1")
        first_stylesheet = base.index('rel="stylesheet"')
        self.assertLess(bootstrap, first_stylesheet)
        self.assertIn("new Set(['system', 'light', 'dark'])", base)
        self.assertIn('data-theme="dark"', base)
        self.assertIn('data-theme-choice="system"', base)
        self.assertIn('data-theme-control', base)
        self.assertIn('src="{{ url_for(\'static\', filename=\'theme.js\') }}"', base)
        self.assertIn("const ALLOWED = new Set(['system', 'light', 'dark'])", theme)
        self.assertIn("localStorage.setItem(STORAGE_KEY, safeChoice)", theme)
        self.assertIn("root.dataset.bsTheme = resolved", theme)
        self.assertNotIn("transition: all", theme)

        for path in ("/", "/?view=receipts", "/analytics"):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn('data-theme-control', html)
                self.assertIn('src="/static/theme.js"', html)

    def test_chart_templates_define_dark_theme_defaults(self):
        template_dir = Path(__file__).parents[1] / "app" / "web" / "templates"
        static_dir = Path(__file__).parents[1] / "app" / "web" / "static"

        item_template = (template_dir / "item.html").read_text(encoding="utf-8")
        item_script = (static_dir / "item-profile.js").read_text(encoding="utf-8")
        analytics_script = (static_dir / "analytics.js").read_text(encoding="utf-8")
        self.assertIn("item-profile.js", item_template)
        self.assertIn("Chart.defaults.color = colors.text", item_script)
        self.assertIn("Chart.defaults.borderColor = colors.line", item_script)
        self.assertIn("receipt-intelligence:themechange", item_script)
        self.assertIn("prefers-reduced-motion: reduce", item_script)
        self.assertIn("Chart.getChart(canvas)", item_script)
        self.assertEqual(item_script.count("new Chart("), 1)
        self.assertIn("Chart.defaults.color = colors.text", analytics_script)
        self.assertIn("Chart.defaults.borderColor = colors.line", analytics_script)
        self.assertIn("receipt-intelligence:themechange", analytics_script)
        self.assertIn("prefers-reduced-motion: reduce", analytics_script)
        self.assertIn("Chart.getChart(canvas)", analytics_script)
        self.assertEqual(analytics_script.count("new Chart("), 1)
        for chart_key in ("months", "categories", "top", "trend"):
            with self.subTest(chart_lifecycle=chart_key):
                self.assertIn(f"createChart('{chart_key}',", analytics_script)

    def test_analytics_is_an_investigation_workspace_not_a_dashboard_wall(self):
        response = self.client.get(
            "/analytics?start=2026-07-01&end=2026-07-14&category=мясо"
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        template_dir = Path(__file__).parents[1] / "app" / "web" / "templates"
        static_dir = Path(__file__).parents[1] / "app" / "web" / "static"
        template = (template_dir / "analytics.html").read_text(encoding="utf-8")
        script = (static_dir / "analytics.js").read_text(encoding="utf-8")
        css = (static_dir / "style.css").read_text(encoding="utf-8")

        self.assertEqual(len(re.findall(r"<h1\b", html)), 1)
        self.assertIn('<h1 id="analytics-title">Аналитика</h1>', html)
        self.assertLess(html.index("analytics-page-header"), html.index("analytics-filter-toolbar"))
        self.assertLess(html.index("analytics-filter-toolbar"), html.index("analytics-summary-band"))
        self.assertLess(html.index("analytics-summary-band"), html.index("analytics-insight-note"))
        self.assertLess(html.index("analytics-insight-note"), html.index("analytics-primary-panel"))
        self.assertLess(html.index("analytics-primary-panel"), html.index("analytics-secondary-grid"))
        self.assertLess(html.index("analytics-secondary-grid"), html.index("analytics-trend-panel"))

        for control_id, label in (
            ("startDate", "Начало"),
            ("endDate", "Конец"),
            ("storeFilter", "Магазин"),
            ("categoryFilter", "Категория"),
            ("itemFilter", "Товар"),
            ("itemTrendInput", "Товар"),
        ):
            with self.subTest(control=control_id):
                self.assertRegex(
                    html,
                    rf"<label[^>]*>[\s\S]*?{label}[\s\S]*?id=\"{control_id}\"",
                )

        self.assertIn('role="img" aria-label="Динамика расходов по месяцам"', html)
        self.assertIn('id="monthValueList"', html)
        self.assertIn('id="monthValueToggle"', html)
        self.assertIn('id="analyticsInsightList"', html)
        self.assertIn('id="analyticsInsightEmpty"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('src="/static/analytics.js"', html)
        self.assertIn('type: \'line\'', script)
        self.assertIn("indexAxis: 'y'", script)
        self.assertIn("formatter: value => currencyTick(value)", script)
        self.assertIn("document.createElement('dt')", script)
        self.assertIn("document.createElement('dd')", script)
        self.assertIn("function renderInsightSummary(data)", script)
        self.assertIn("monthName.format", script)
        self.assertIn("money.format(line.amount)", script)
        self.assertIn("summary.lines.slice(0, 3)", script)
        self.assertIn("function createChart(key, config)", script)
        self.assertIn("function destroyChart(key)", script)
        self.assertIn("const registered = canvas && window.Chart ? Chart.getChart(canvas) : null", script)
        self.assertIn("Chart.getChart(canvas)?.destroy()", script)
        self.assertIn("group.classList.add('is-earlier-period')", script)
        self.assertIn("aria-expanded", template)
        self.assertNotIn("type: 'doughnut'", script)
        self.assertNotIn("backgroundColor: colors,", script)
        self.assertIn("--analytics-chart-primary", script)
        self.assertIn("--analytics-chart-category", script)
        self.assertIn("--analytics-chart-product", script)
        self.assertIn("--analytics-chart-trend", script)

        self.assertNotIn('class="surface', template)
        self.assertNotIn("total-chip", template)
        self.assertNotIn("charts-grid", template)
        self.assertNotIn("metric-grid", template)
        self.assertIn(".analytics-primary-panel", css)
        self.assertIn(".analytics-secondary-grid", css)
        self.assertIn("grid-template-columns: minmax(0, 1.62fr) minmax(0, 1fr)", css)
        self.assertIn('.analytics-chart-frame-trend[data-state="empty"]', css)
        self.assertIn("@media (max-width: 560px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)


    def test_receipt_detail_renders_paid_total_piece_and_weighted_semantics(self):
        db.add_receipt_with_items(
            "2026-08-08",
            "MAXIMA",
            3.63,
            "receipt-price-semantics",
            [
                {
                    "name": "NONGSHIM 120g",
                    "quantity": 2,
                    "quantity_unit": "piece",
                    "price": 3.10,
                    "line_total": 3.10,
                    "unit_price": 1.55,
                    "source": "parser",
                },
                {
                    "name": "Sīpoli 45+ kg",
                    "quantity": .58,
                    "quantity_unit": "kg",
                    "price": .53,
                    "line_total": .53,
                    "unit_price": .91,
                    "source": "parser",
                },
            ],
        )

        html = self.client.get("/receipt/1").get_data(as_text=True)

        self.assertIn("Итого за позицию", html)
        self.assertIn("2 шт. · 1,55 €/шт. · итого 3,10 €", html)
        self.assertIn("0,580 кг · 0,91 €/кг · итого 0,53 €", html)
        self.assertNotIn('data-label="Цена"', html)

    def test_receipt_detail_uses_legacy_price_when_line_total_is_null(self):
        db.add_receipt_with_items(
            "2026-08-08",
            "MAXIMA",
            2.40,
            "legacy-total-fallback",
            [{"name": "Legacy item", "quantity": 1, "price": 2.40}],
        )
        with db.get_connection() as conn:
            conn.execute("UPDATE items SET line_total = NULL WHERE receipt_id = 1")
            conn.commit()

        html = self.client.get("/receipt/1").get_data(as_text=True)
        self.assertIn("итого 2,40 €", html)

    def test_receipt_detail_status_uses_prior_normalized_history(self):
        prices = (1.0, 1.0, 2.0, 1.15)
        for index, price in enumerate(prices, start=1):
            db.add_receipt_with_items(
                f"2026-07-{index:02d}",
                "RIMI",
                price,
                f"shared-price-{index}",
                [{
                    "name": "Shared Milk 1L",
                    "quantity": 1,
                    "quantity_unit": "piece",
                    "line_total": price,
                    "unit_price": price,
                    "source": "package_name",
                }],
            )

        html = self.client.get("/receipt/4").get_data(as_text=True)

        self.assertIn("Выше медианы", html)
        self.assertIn("+15.0%", html)

    def test_receipt_detail_shows_eligible_history_progress(self):
        for index in range(1, 4):
            db.add_receipt_with_items(
                f"2026-07-{index:02d}",
                "RIMI",
                2.0,
                f"receipt-progress-{index}",
                [{
                    "name": "Progress milk 1L",
                    "quantity": 1,
                    "quantity_unit": "piece",
                    "line_total": 2.0,
                    "unit_price": 2.0,
                    "source": "package_name",
                }],
            )

        html = self.client.get("/receipt/3").get_data(as_text=True)

        self.assertIn("Недостаточно истории цен", html)
        self.assertIn("Сопоставимых наблюдений: 2 из 3.", html)


if __name__ == "__main__":
    unittest.main()

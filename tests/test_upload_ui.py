import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.web.app import create_app


class UploadWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.create_tables()
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def test_upload_is_a_focused_workspace_with_one_heading(self):
        response = self.client.get("/upload")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="upload-workspace"', html)
        self.assertIn('class="upload-workflow"', html)
        self.assertIn('class="upload-dropzone"', html)
        self.assertIn('class="upload-queue"', html)
        self.assertIn('class="upload-command-bar"', html)
        self.assertIn('class="upload-mail-source"', html)
        self.assertNotIn('class="metric-card"', html)
        self.assertNotIn('class="eyebrow"', html)

    def test_selection_queue_action_and_mail_follow_expected_order(self):
        html = self.client.get("/upload").get_data(as_text=True)

        selection = html.index('class="upload-selection"')
        queue = html.index('class="upload-queue"')
        command = html.index('class="upload-command-bar"')
        mail = html.index('class="upload-mail-source"')
        self.assertLess(selection, queue)
        self.assertLess(queue, command)
        self.assertLess(command, mail)
        self.assertIn("Основной способ", html)
        self.assertIn("Другой источник", html)

    def test_upload_controls_preserve_existing_contracts(self):
        html = self.client.get("/upload").get_data(as_text=True)

        self.assertIn('id="fileInput"', html)
        self.assertIn('name="pdfs"', html)
        self.assertIn('multiple', html)
        self.assertIn('accept="application/pdf,.pdf"', html)
        self.assertIn('id="uploadBtn"', html)
        self.assertIn('id="gmailBtn"', html)
        self.assertIn('id="uploadBtn" class="btn btn-primary" type="button" disabled', html)
        self.assertIn('aria-label="Прогресс импорта"', html)
        self.assertIn('style="--progress-scale:0"', html)

        missing_files = self.client.post("/upload")
        self.assertEqual(missing_files.status_code, 400)
        self.assertEqual(missing_files.get_json()["message"], "Нет файлов")

    def test_empty_queue_and_feedback_states_are_explicit(self):
        html = self.client.get("/upload").get_data(as_text=True)

        self.assertIn("Очередь пока пуста", html)
        self.assertIn("Выбранные PDF появятся здесь", html)
        self.assertIn('class="upload-feedback" aria-labelledby="upload-feedback-title" hidden', html)
        self.assertIn('role="status" aria-live="polite"', html)

    def test_upload_script_preserves_endpoints_and_uses_safe_dom_rendering(self):
        script = (
            Path(__file__).parents[1] / "app" / "web" / "static" / "upload-workspace.js"
        ).read_text(encoding="utf-8")

        for contract in (
            "fetch('/upload'",
            "fetch('/gmail/fetch'",
            "new FormData()",
            "formData.append('pdfs', file)",
            "files_saved.length",
            "files_existing?.length",
            "result.skipped_files",
            "progressBar.style.setProperty('--progress-scale'",
            "replaceChildren()",
            "textContent",
        ):
            self.assertIn(contract, script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("style.width", script)

    def test_upload_styles_are_scoped_responsive_and_touch_friendly(self):
        css = (
            Path(__file__).parents[1] / "app" / "web" / "static" / "style.css"
        ).read_text(encoding="utf-8")

        for contract in (
            ".upload-page .app-container",
            ".upload-workspace",
            ".upload-workflow-body",
            ".upload-dropzone",
            ".upload-queue",
            ".upload-command-bar",
            ".upload-mail-source",
            "min-height: 44px",
            "@media (max-width: 820px)",
            "@media (max-width: 560px)",
            "@media (prefers-reduced-motion: reduce)",
        ):
            self.assertIn(contract, css)


if __name__ == "__main__":
    unittest.main()

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TEMPLATES = ROOT / "app" / "web" / "templates"
STATIC = ROOT / "app" / "web" / "static"


class IconSystemTests(unittest.TestCase):
    def test_templates_use_only_the_local_lucide_primitive(self):
        templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in TEMPLATES.glob("*.html")
        )
        base = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        self.assertNotIn("bi bi-", templates)
        self.assertNotIn("bootstrap-icons", base)
        self.assertIn('from "_icons.html" import icon', templates)

    def test_icon_macro_is_decorative_and_has_stable_dimensions(self):
        macro = (TEMPLATES / "_icons.html").read_text(encoding="utf-8")

        self.assertIn('class="app-icon', macro)
        self.assertIn('width="20"', macro)
        self.assertIn('height="20"', macro)
        self.assertIn('viewBox="0 0 24 24"', macro)
        self.assertIn('aria-hidden="true"', macro)
        self.assertIn('focusable="false"', macro)

    def test_curated_sprite_contains_every_referenced_icon(self):
        templates = "\n".join(
            path.read_text(encoding="utf-8")
            for path in TEMPLATES.glob("*.html")
        )
        referenced = set(re.findall(r"icon\(\s*['\"]([a-z0-9-]+)['\"]", templates))
        sprite = (STATIC / "icons" / "lucide.svg").read_text(encoding="utf-8")
        available = set(re.findall(r'<symbol id="([a-z0-9-]+)"', sprite))

        self.assertTrue(referenced)
        self.assertEqual(referenced - available, set())
        self.assertIn('stroke="currentColor"', sprite)
        self.assertIn('stroke-width="2"', sprite)

    def test_shared_icon_css_preserves_alignment_and_disclosure_rotation(self):
        css = (STATIC / "style.css").read_text(encoding="utf-8")

        self.assertIn(".app-icon", css)
        self.assertIn("vertical-align: -0.125em", css)
        self.assertIn(".receipt-expand-mark .app-icon", css)
        self.assertNotIn(".receipt-expand-mark i", css)


if __name__ == "__main__":
    unittest.main()

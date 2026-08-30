import unittest
from pathlib import Path

from app.apply_category_taxonomy_v2 import load_manifest
from app.category_keywords import (
    CANONICAL_CATEGORIES,
    UNRESOLVED_CATEGORY,
    category_for_reporting,
    categorize_with_source,
    normalize_category_name,
)


EXPECTED_CATEGORIES = [
    "овощи и фрукты",
    "мясо и птица",
    "рыба и морепродукты",
    "молочные продукты и альтернативы",
    "яйца",
    "хлеб и выпечка",
    "бакалея и основные продукты",
    "готовая еда и быстрое приготовление",
    "замороженные продукты",
    "соусы, приправы и консервы",
    "снеки и сладости",
    "безалкогольные напитки",
    "алкоголь",
    "детское",
    "товары для животных",
    "бытовое и личный уход",
    "служебные строки",
    "прочее / требует решения",
]


class CategoryTaxonomyV2ContractTests(unittest.TestCase):
    def test_exact_flat_vocabulary_and_legacy_compatibility(self):
        self.assertEqual(CANONICAL_CATEGORIES, EXPECTED_CATEGORIES)
        self.assertEqual(UNRESOLVED_CATEGORY, "прочее / требует решения")
        self.assertEqual(normalize_category_name("молочка"), "молочные продукты и альтернативы")
        self.assertEqual(normalize_category_name("напитки"), "безалкогольные напитки")
        self.assertEqual(category_for_reporting("мясо"), UNRESOLVED_CATEGORY)
        self.assertEqual(category_for_reporting("яйца"), "яйца")
        self.assertEqual(category_for_reporting("custom-test-category"), "custom-test-category")

    def test_existing_classifier_scoring_emits_only_v2_vocabulary(self):
        for name in ("piens 1L", "olas 10gab", "pasta 500g", "unknown xyz"):
            category, source = categorize_with_source(name)
            self.assertIn(category, CANONICAL_CATEGORIES)
            self.assertIn(source, {"rule", "fallback"})

    def test_safe_manifest_covers_required_semantic_regressions(self):
        manifest_path = Path(
            "docs/audits/2026-08-14-category-taxonomy-v2-safe-migration-candidates.csv"
        )
        targets = {
            candidate.effective_product: candidate.target_category
            for candidate in load_manifest(manifest_path)
        }
        expected = {
            "Kūtī dētas olas 10gab.": "яйца",
            "Pasta DE CECCO Spaghetti Nr. 12 500g": "бакалея и основные продукты",
            "Griki Valdo 4x125g": "бакалея и основные продукты",
            "Rīsi VALDO kārba 8x125g": "бакалея и основные продукты",
            "NONGSHIM Kimchi": "готовая еда и быстрое приготовление",
            "Tomātu pasta SPILVA 520g": "соусы, приправы и консервы",
            "Atlantijas laSa fileja kg": "рыба и морепродукты",
            "Sald. frī kartupeļi Original AVIKO 1,5kg": "замороженные продукты",
            "Zaļā tēja LIPTON ar citrusu arom. 25x1, 3g": "безалкогольные напитки",
            "Čipsi ĀDAŽU ar siera garšu 130g": "снеки и сладости",
            "Gard. kaķiem PERFECTO putnu-aknu 10gab.": "товары для животных",
            "Alus MADONAS nefiltrēts 5,6% 0,5L D": "алкоголь",
        }
        for effective_product, target in expected.items():
            self.assertEqual(targets[effective_product], target)


if __name__ == "__main__":
    unittest.main()

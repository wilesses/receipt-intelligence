import sqlite3
import unittest

from app.db import create_tables
from app import product_matcher
from app.product_matcher import find_similar_products
from app.product_normalizer import normalize_product_name


def build_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            store TEXT,
            total REAL,
            receipt_number TEXT
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER,
            name TEXT,
            canonical_name TEXT,
            normalized_name TEXT,
            quantity REAL,
            price REAL,
            category TEXT,
            FOREIGN KEY(receipt_id) REFERENCES receipts(id)
        );
    """)
    conn.execute("INSERT INTO receipts (date, store, total, receipt_number) VALUES ('2026-01-01', 'TEST', 0, 't')")
    return conn


def add_item(conn, name, category="прочее"):
    conn.execute(
        """
        INSERT INTO items (receipt_id, name, normalized_name, quantity, price, category)
        VALUES (1, ?, ?, 1, 1, ?)
        """,
        (name, normalize_product_name(name), category),
    )


class ProductMatcherTests(unittest.TestCase):
    def setUp(self):
        product_matcher._cache.clear()

    def test_similar_same_sku(self):
        conn = build_conn()
        add_item(conn, "GRIMBERGEN Blonde 6,7% 0,5L", "напитки")
        add_item(conn, "GRIMBERGEN Blonde 6.7% 500 ml", "напитки")

        suggestions = find_similar_products(conn, query="grimbergen", limit=10)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["confidence"], "high")

    def test_different_volume_blocked(self):
        conn = build_conn()
        add_item(conn, "Blue Moon 0.33L")
        add_item(conn, "Blue Moon 0.5L")

        self.assertEqual(find_similar_products(conn, query="blue moon", limit=10), [])

    def test_different_variants_blocked(self):
        conn = build_conn()
        add_item(conn, "Coca Cola Zero 1L")
        add_item(conn, "Coca Cola Original 1L")
        add_item(conn, "Lay's Cheese 150g")
        add_item(conn, "Lay's Bacon 150g")

        suggestions = find_similar_products(conn, limit=10)

        names = {(item["left_name"], item["right_name"]) for item in suggestions}
        self.assertNotIn(("Coca Cola Zero 1L", "Coca Cola Original 1L"), names)
        self.assertNotIn(("Lay's Cheese 150g", "Lay's Bacon 150g"), names)

    def test_merchant_packaging_abbreviation_remains_a_suggestion(self):
        conn = build_conn()
        add_item(conn, "Rīsi VALDO kārba 8x125g")
        add_item(conn, "Rīsi Valdo 8x125g")

        suggestions = find_similar_products(conn, query="Valdo", limit=10)

        self.assertEqual(len(suggestions), 1)
        self.assertIn(suggestions[0]["confidence"], {"high", "possible"})
        self.assertTrue(any(
            "симметричное совпадение полного названия" in reason
            for reason in suggestions[0]["reasons"]
        ))
        self.assertIn("совпадает упаковка 8 × 125 g", suggestions[0]["reasons"])

    def test_subset_name_is_not_high_confidence_by_token_set_alone(self):
        conn = build_conn()
        add_item(conn, "Kūtī dētas olas 10gab")
        add_item(conn, "Kūtī dētas olas WELL DONE 10gab")

        suggestions = find_similar_products(conn, query="olas", limit=10)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["confidence"], "possible")

    def test_unmatched_significant_token_prevents_high_confidence(self):
        conn = build_conn()
        add_item(conn, "Produkts Alfa Beta 500g")
        add_item(conn, "Produkts Alfa Beta Plus 500g")

        suggestions = find_similar_products(conn, query="Alfa", limit=10)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["confidence"], "possible")
        self.assertIn(
            "есть несовпадающие значимые слова",
            suggestions[0]["reasons"],
        )

    def test_one_sided_and_latvian_variant_conflicts_are_blocked(self):
        conn = build_conn()
        add_item(conn, "Gāzēts dzēriens PEPSI 1L")
        add_item(conn, "Gāzēts dzēriens PEPSI MAX 1L")
        add_item(conn, "Čipsi ĀDAŽU ar siera garšu 130g")
        add_item(conn, "Čipsi ĀDAŽU ar bekona garšu 130g")

        suggestions = find_similar_products(conn, limit=20)
        pairs = {
            frozenset((item["left_name"], item["right_name"]))
            for item in suggestions
        }

        self.assertNotIn(
            frozenset(("Gāzēts dzēriens PEPSI 1L", "Gāzēts dzēriens PEPSI MAX 1L")),
            pairs,
        )
        self.assertNotIn(
            frozenset(("Čipsi ĀDAŽU ar siera garšu 130g", "Čipsi ĀDAŽU ar bekona garšu 130g")),
            pairs,
        )

    def test_single_pack_and_multipack_are_blocked_for_supported_separators(self):
        for multipack in ("6x110g", "6 x 110 g", "6×110g", "6х110g"):
            with self.subTest(multipack=multipack):
                product_matcher._cache.clear()
                conn = build_conn()
                add_item(conn, "Biezenis RŪDOLFS 110g")
                add_item(conn, f"Biezenis RŪDOLFS {multipack}")

                suggestions = find_similar_products(conn, query="RŪDOLFS", limit=10)

                self.assertEqual(suggestions, [])

    def test_different_multipack_signatures_are_blocked(self):
        conn = build_conn()
        add_item(conn, "Biezenis RŪDOLFS 6x110g")
        add_item(conn, "Biezenis RŪDOLFS 4x110g")

        suggestions = find_similar_products(conn, query="RŪDOLFS", limit=10)

        self.assertEqual(suggestions, [])

    def test_incompatible_explicit_package_units_are_blocked(self):
        conn = build_conn()
        add_item(conn, "Saldais krējums EXPORTA 35% 200ml")
        add_item(conn, "Saldais krējums Exporta 35% 200g")

        suggestions = find_similar_products(conn, query="EXPORTA", limit=10)

        self.assertEqual(suggestions, [])

    def test_quality_grade_and_egg_size_conflicts_are_blocked(self):
        conn = build_conn()
        add_item(conn, "Gurķi īsie kg")
        add_item(conn, "Gurķi īsie kg 2. šķ.")
        add_item(conn, "Kūtī dētas olas WELL DONE L izm. 10gab")
        add_item(conn, "Kūtī dētas olas WELL DONE M izm. 10gab")

        suggestions = find_similar_products(conn, limit=20)
        pairs = {
            frozenset((item["left_name"], item["right_name"]))
            for item in suggestions
        }

        self.assertNotIn(
            frozenset(("Gurķi īsie kg", "Gurķi īsie kg 2. šķ.")),
            pairs,
        )
        self.assertNotIn(
            frozenset((
                "Kūtī dētas olas WELL DONE L izm. 10gab",
                "Kūtī dētas olas WELL DONE M izm. 10gab",
            )),
            pairs,
        )

    def test_audited_spicy_young_and_caliber_variants_are_blocked(self):
        conn = build_conn()
        add_item(conn, "Nūdeles REEVA ar aso vistas garšu 60g")
        add_item(conn, "Nūdeles REEVA ar vistas garšu 60g")
        add_item(conn, "Burkāni 1kg")
        add_item(conn, "Burkāni jaunie 1kg")
        add_item(conn, "Ķiploki kg")
        add_item(conn, "Ķiploki 50+ mm kg")

        suggestions = find_similar_products(conn, limit=30)
        pairs = {
            frozenset((item["left_name"], item["right_name"]))
            for item in suggestions
        }

        for pair in (
            ("Nūdeles REEVA ar aso vistas garšu 60g", "Nūdeles REEVA ar vistas garšu 60g"),
            ("Burkāni 1kg", "Burkāni jaunie 1kg"),
            ("Ķiploki kg", "Ķiploki 50+ mm kg"),
        ):
            with self.subTest(pair=pair):
                self.assertNotIn(frozenset(pair), pairs)

    def test_diacritic_loss_from_audit_is_discoverable(self):
        conn = build_conn()
        add_item(conn, "Cipsi Adazu ar siera garsu 130g")
        add_item(conn, "Čipsi ĀDAŽU ar siera garšu 130g")

        suggestions = find_similar_products(conn, query="siera", limit=10)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["confidence"], "high")

    def test_safe_ocr_diacritic_variation_from_audit_is_discoverable(self):
        conn = build_conn()
        add_item(conn, "Biezpiena sierins Karums karamelu 45g")
        add_item(conn, "Biezpiena sieriņš KĀRUMS karameļu 45g")

        suggestions = find_similar_products(conn, query="Biezpiena", limit=10)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["confidence"], "high")


if __name__ == "__main__":
    unittest.main()

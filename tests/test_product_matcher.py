import sqlite3
import unittest

from app.db import create_tables
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


if __name__ == "__main__":
    unittest.main()

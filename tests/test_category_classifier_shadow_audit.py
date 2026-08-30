import hashlib
import importlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.product_normalizer import normalize_product_name


class CategoryClassifierShadowAuditTests(unittest.TestCase):
    def test_read_only_evaluation_splits_rule_covered_and_rule_free_rows(self):
        try:
            audit = importlib.import_module("app.audit_category_classifier_v2")
        except ModuleNotFoundError:
            self.fail("Shadow evaluator module is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "shadow.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.executescript(
                    """
                    CREATE TABLE items (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        normalized_name TEXT,
                        canonical_name TEXT,
                        category TEXT NOT NULL
                    );
                    CREATE TABLE product_category_rules (
                        product_key TEXT PRIMARY KEY,
                        category TEXT NOT NULL
                    );
                    """
                )
                rows = [
                    (1, "Kūtī dētas olas 10gab.", "яйца"),
                    (2, "Alus TEST 5,0% 0,5L", "безалкогольные напитки"),
                    (3, "Unknown TEST 500g", "прочее / требует решения"),
                    (4, "Tomātu pasta 500g", "соусы, приправы и консервы"),
                ]
                conn.executemany(
                    "INSERT INTO items (id, name, normalized_name, category) VALUES (?, ?, ?, ?)",
                    [(item_id, name, normalize_product_name(name), category) for item_id, name, category in rows],
                )
                conn.execute(
                    "INSERT INTO product_category_rules VALUES (?, ?)",
                    (normalize_product_name("Alus TEST 5,0% 0,5L"), "безалкогольные напитки"),
                )
                conn.commit()

            before_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
            before_stat = db_path.stat()

            result = audit.evaluate_database(db_path)

            self.assertEqual(result["overall"]["rows"], 4)
            self.assertEqual(result["overall"]["exact_matches"], 3)
            self.assertEqual(result["overall"]["fallback_count"], 1)
            self.assertEqual(result["rule_covered"]["rows"], 1)
            self.assertEqual(result["rule_covered"]["exact_matches"], 0)
            self.assertEqual(result["rule_free"]["rows"], 3)
            self.assertEqual(result["rule_free"]["exact_matches"], 3)
            self.assertEqual(result["rule_override_rows"], 1)
            self.assertEqual(
                result["overall"]["confusion"]["безалкогольные напитки -> алкоголь"],
                1,
            )
            self.assertEqual(result["overall"]["effective_identities"], 4)
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), before_hash)
            self.assertEqual(db_path.stat().st_size, before_stat.st_size)
            self.assertEqual(db_path.stat().st_mtime_ns, before_stat.st_mtime_ns)
            for suffix in ("-wal", "-shm", "-journal"):
                self.assertFalse(Path(str(db_path) + suffix).exists())


if __name__ == "__main__":
    unittest.main()

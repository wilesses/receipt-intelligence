import sqlite3
from collections.abc import Iterable

from app.config import DB_PATH, ensure_data_dirs


def get_connection() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                store TEXT,
                total REAL NOT NULL DEFAULT 0,
                receipt_number TEXT NOT NULL UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                canonical_name TEXT,
                quantity REAL NOT NULL DEFAULT 1,
                price REAL NOT NULL DEFAULT 0,
                category TEXT NOT NULL DEFAULT 'прочее',
                FOREIGN KEY(receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("PRAGMA table_info(items)")
        item_columns = {row[1] for row in cursor.fetchall()}
        if "category" not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN category TEXT DEFAULT 'прочее'")
        if "canonical_name" not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN canonical_name TEXT")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_number ON receipts(receipt_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_store ON receipts(store)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_receipt_id ON items(receipt_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_canonical_name ON items(canonical_name)")
        conn.commit()


def add_receipt_with_items(date, store, total, receipt_number, items: Iterable[dict]) -> bool:
    create_tables()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM receipts WHERE receipt_number = ?", (receipt_number,))
            if cursor.fetchone():
                return False

            cursor.execute("""
                INSERT INTO receipts (date, store, total, receipt_number)
                VALUES (?, ?, ?, ?)
            """, (date, store, total or 0, receipt_number))
            receipt_id = cursor.lastrowid

            cursor.executemany("""
                INSERT INTO items (receipt_id, name, quantity, price, category)
                VALUES (?, ?, ?, ?, ?)
            """, [
                (
                    receipt_id,
                    item.get("name") or "Unknown",
                    item.get("quantity") or 1,
                    item.get("price") or 0,
                    item.get("category") or "прочее",
                )
                for item in items
            ])
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_all_receipts():
    create_tables()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, receipt_number, date, store, total
            FROM receipts
            ORDER BY date DESC, id DESC
        """)
        return cursor.fetchall()


def get_items_by_receipt(receipt_id: int):
    create_tables()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, quantity, price, category
            FROM items
            WHERE receipt_id = ?
            ORDER BY id
        """, (receipt_id,))
        return cursor.fetchall()


def get_total_spent() -> float:
    create_tables()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total) FROM receipts")
        total = cursor.fetchone()[0]
    return round(total or 0, 2)

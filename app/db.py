import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.category_keywords import categorize_with_source, normalize_category_name
from app.category_rules import get_category_rule, get_product_key
from app.config import DB_PATH, ensure_data_dirs
from app.price_model import derive_price_data
from app.product_normalizer import normalize_product_name


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def get_connection() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def backup_database(label: str, backup_dir: Path | None = None) -> Path:
    source = Path(DB_PATH).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Database not found: {source}")

    target_dir = backup_dir or source.parent / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = target_dir / f"{source.stem}_before_{label}_{timestamp}{source.suffix}"

    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as source_conn:
            with closing(sqlite3.connect(target)) as backup_conn:
                source_conn.backup(backup_conn)
                if backup_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError(f"Backup integrity check failed: {target}")
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target


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
                normalized_name TEXT,
                quantity REAL NOT NULL DEFAULT 1,
                price REAL NOT NULL DEFAULT 0,
                line_total REAL,
                unit_price REAL,
                quantity_unit TEXT,
                package_size REAL,
                package_unit TEXT,
                normalized_unit_price REAL,
                normalized_price_unit TEXT,
                price_parse_source TEXT,
                price_parse_confidence REAL,
                category TEXT NOT NULL DEFAULT 'прочее / требует решения',
                category_source TEXT NOT NULL DEFAULT 'rule',
                FOREIGN KEY(receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_category_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_key TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("PRAGMA table_info(items)")
        item_columns = {row[1] for row in cursor.fetchall()}
        if "category" not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN category TEXT DEFAULT 'прочее / требует решения'")
        if "canonical_name" not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN canonical_name TEXT")
        if "normalized_name" not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN normalized_name TEXT")
        if "category_source" not in item_columns:
            cursor.execute("ALTER TABLE items ADD COLUMN category_source TEXT NOT NULL DEFAULT 'rule'")
        price_columns = {
            "line_total": "REAL",
            "unit_price": "REAL",
            "quantity_unit": "TEXT",
            "package_size": "REAL",
            "package_unit": "TEXT",
            "normalized_unit_price": "REAL",
            "normalized_price_unit": "TEXT",
            "price_parse_source": "TEXT",
            "price_parse_confidence": "REAL",
        }
        for column, column_type in price_columns.items():
            if column not in item_columns:
                cursor.execute(f"ALTER TABLE items ADD COLUMN {column} {column_type}")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_number ON receipts(receipt_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_store ON receipts(store)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_receipt_id ON items(receipt_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_canonical_name ON items(canonical_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_normalized_name ON items(normalized_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_category_source ON items(category_source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_normalized_price_unit ON items(normalized_price_unit)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_category_rules_key ON product_category_rules(product_key)")
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

            prepared_items = []
            for item in items:
                name = item.get("name") or "Unknown"
                normalized_name = normalize_product_name(name)
                line_total = item.get("line_total")
                if line_total is None:
                    line_total = 0 if item.get("price") is None else item.get("price")
                price_data = derive_price_data(
                    name=name,
                    normalized_name=normalized_name,
                    quantity=1 if item.get("quantity") is None else item.get("quantity"),
                    line_total=line_total,
                    unit_price=item.get("unit_price"),
                    quantity_unit=item.get("quantity_unit"),
                    package_size=item.get("package_size"),
                    package_unit=item.get("package_unit"),
                    source=item.get("source") or item.get("price_parse_source") or "derived",
                )
                product_key = get_product_key(name, normalized_name, None)
                rule = get_category_rule(conn, product_key)
                if rule:
                    category = rule["category"]
                    category_source = "inherited"
                else:
                    category = normalize_category_name(item.get("category"))
                    category_source = item.get("category_source")
                    if category_source not in {"rule", "fallback"}:
                        category, category_source = categorize_with_source(name)

                prepared_items.append((
                    receipt_id,
                    name,
                    normalized_name,
                    price_data.quantity,
                    price_data.line_total,
                    price_data.line_total,
                    price_data.unit_price,
                    price_data.quantity_unit,
                    price_data.package_size,
                    price_data.package_unit,
                    price_data.normalized_unit_price,
                    price_data.normalized_price_unit,
                    price_data.source,
                    price_data.confidence,
                    category,
                    category_source,
                ))

            cursor.executemany("""
                INSERT INTO items (
                    receipt_id, name, normalized_name, quantity, price, line_total, unit_price,
                    quantity_unit, package_size, package_unit, normalized_unit_price,
                    normalized_price_unit, price_parse_source, price_parse_confidence,
                    category, category_source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, prepared_items)
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

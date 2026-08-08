from datetime import datetime, timezone

from app.category_keywords import normalize_category_name
from app.product_normalizer import normalize_product_name


def now_utc_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_product_key(name: str, normalized_name: str | None = None, canonical_name: str | None = None) -> str:
    if canonical_name and canonical_name.strip():
        return normalize_product_name(canonical_name)
    return (normalized_name or "").strip() or normalize_product_name(name)


def get_category_rule(conn, product_key: str) -> dict | None:
    row = conn.execute(
        """
        SELECT product_key, category, source
        FROM product_category_rules
        WHERE product_key = ?
        """,
        (product_key,),
    ).fetchone()
    if not row:
        return None
    return {
        "product_key": row[0],
        "category": normalize_category_name(row[1]),
        "source": row[2],
    }


def upsert_category_rule(conn, product_key: str, category: str) -> None:
    normalized_category = normalize_category_name(category)
    timestamp = now_utc_text()
    conn.execute(
        """
        INSERT INTO product_category_rules (product_key, category, source, created_at, updated_at)
        VALUES (?, ?, 'manual', ?, ?)
        ON CONFLICT(product_key) DO UPDATE SET
            category = excluded.category,
            source = 'manual',
            updated_at = excluded.updated_at
        """,
        (product_key, normalized_category, timestamp, timestamp),
    )


def matching_item_ids_for_product_key(conn, product_key: str) -> list[int]:
    rows = conn.execute("""
        SELECT id, name, normalized_name, canonical_name
        FROM items
    """).fetchall()
    return [
        item_id
        for item_id, name, normalized_name, canonical_name in rows
        if get_product_key(name or "", normalized_name, canonical_name) == product_key
    ]


def apply_category_to_product_key(conn, product_key: str, category: str) -> int:
    item_ids = matching_item_ids_for_product_key(conn, product_key)
    if not item_ids:
        return 0

    placeholders = ",".join("?" for _ in item_ids)
    conn.execute(
        f"""
        UPDATE items
        SET category = ?, category_source = 'manual'
        WHERE id IN ({placeholders})
        """,
        (normalize_category_name(category), *item_ids),
    )
    return len(item_ids)

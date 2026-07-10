from app.db import get_connection


PRODUCT_NAME_EXPR = "COALESCE(NULLIF(items.canonical_name, ''), items.name)"


def _build_filters(start=None, end=None, store=None, category=None, item=None):
    conditions = []
    params = []

    if start:
        conditions.append("receipts.date >= ?")
        params.append(start)
    if end:
        conditions.append("receipts.date <= ?")
        params.append(end)
    if store:
        conditions.append("LOWER(receipts.store) = LOWER(?)")
        params.append(store)
    if category:
        conditions.append("items.category = ?")
        params.append(category)
    if item:
        conditions.append(f"({PRODUCT_NAME_EXPR} LIKE ? OR items.name LIKE ?)")
        params.append(f"%{item}%")
        params.append(f"%{item}%")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, params


def get_analytics_data(start=None, end=None, store=None, category=None, item=None):
    where_clause, params = _build_filters(start, end, store, category, item)

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT COALESCE(items.category, 'прочее'), SUM(items.price)
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            {where_clause}
            GROUP BY COALESCE(items.category, 'прочее')
            ORDER BY SUM(items.price) DESC
        """, params)
        category_rows = cursor.fetchall()

        cursor.execute(f"""
            SELECT strftime('%Y-%m', receipts.date), SUM(items.price)
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            {where_clause}
            GROUP BY strftime('%Y-%m', receipts.date)
            ORDER BY strftime('%Y-%m', receipts.date)
        """, params)
        month_rows = cursor.fetchall()

        cursor.execute(f"""
            SELECT {PRODUCT_NAME_EXPR} AS product_name, SUM(items.price)
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            {where_clause}
            GROUP BY product_name
            ORDER BY SUM(items.price) DESC
            LIMIT 10
        """, params)
        top_rows = cursor.fetchall()

        cursor.execute(f"""
            SELECT SUM(items.price)
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            {where_clause}
        """, params)
        total_spent = cursor.fetchone()[0] or 0

    month_values = [row[1] or 0 for row in month_rows]
    monthly_average = sum(month_values) / len(month_values) if month_values else 0

    return {
        "categories": {
            "labels": [row[0] for row in category_rows],
            "values": [round(row[1] or 0, 2) for row in category_rows],
        },
        "months": {
            "labels": [row[0] for row in month_rows],
            "values": [round(value, 2) for value in month_values],
        },
        "top": {
            "labels": [row[0] for row in top_rows],
            "values": [round(row[1] or 0, 2) for row in top_rows],
        },
        "total_spent": round(total_spent, 2),
        "monthly_average": round(monthly_average, 2),
    }


def get_item_trend(item_name: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT strftime('%Y-%m', receipts.date) AS ym,
                   SUM(items.price) AS total,
                   SUM(items.quantity) AS qty
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            WHERE (COALESCE(NULLIF(items.canonical_name, ''), items.name) LIKE ?
                   OR items.name LIKE ?)
            GROUP BY ym
            ORDER BY ym
        """, (f"%{item_name}%", f"%{item_name}%"))
        rows = cursor.fetchall()

    labels = []
    values = []
    for ym, total, qty in rows:
        if not qty or not total:
            continue
        unit_price = float(total) / float(qty)
        if 0 < unit_price <= 1000:
            labels.append(ym)
            values.append(round(unit_price, 2))

    return {"labels": labels, "values": values}

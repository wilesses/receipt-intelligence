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


def _build_insight_summary(category_rows, month_rows, top_rows, receipt_count, total_spent):
    """Build a deterministic, presentation-neutral summary from analytics aggregates."""
    if not month_rows:
        return {
            "state": "empty",
            "receipt_count": receipt_count,
            "period_count": 0,
            "lines": [],
        }

    lines = [{
        "type": "coverage",
        "period_count": len(month_rows),
        "receipt_count": receipt_count,
    }]

    if len(month_rows) >= 2:
        previous_month, previous_value = month_rows[-2]
        current_month, current_value = month_rows[-1]
        previous_value = float(previous_value or 0)
        current_value = float(current_value or 0)
        if previous_value > 0:
            change_percent = round(((current_value - previous_value) / previous_value) * 100, 1)
            if abs(change_percent) < 0.05:
                direction = "unchanged"
                change_percent = 0.0
            else:
                direction = "increased" if change_percent > 0 else "decreased"
            lines.append({
                "type": "month_change",
                "previous_month": previous_month,
                "current_month": current_month,
                "direction": direction,
                "change_percent": abs(change_percent),
            })
        else:
            lines.append({
                "type": "comparison_unavailable",
                "reason": "zero_baseline",
                "previous_month": previous_month,
                "current_month": current_month,
            })
    else:
        peak_month, peak_value = max(month_rows, key=lambda row: float(row[1] or 0))
        lines.append({
            "type": "peak_month",
            "month": peak_month,
            "amount": round(float(peak_value or 0), 2),
        })

    if category_rows and total_spent > 0:
        category, amount = category_rows[0]
        amount = float(amount or 0)
        lines.append({
            "type": "largest_category",
            "category": category,
            "amount": round(amount, 2),
            "share_percent": round((amount / float(total_spent)) * 100, 1),
        })
    elif top_rows:
        product, amount = top_rows[0]
        lines.append({
            "type": "top_product",
            "product": product,
            "amount": round(float(amount or 0), 2),
        })

    return {
        "state": "ready",
        "receipt_count": receipt_count,
        "period_count": len(month_rows),
        "lines": lines[:3],
    }


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

        cursor.execute(f"""
            SELECT COUNT(DISTINCT receipts.id)
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            {where_clause}
        """, params)
        receipt_count = cursor.fetchone()[0] or 0

    month_values = [row[1] or 0 for row in month_rows]
    monthly_average = sum(month_values) / len(month_values) if month_values else 0
    insight_summary = _build_insight_summary(
        category_rows,
        month_rows,
        top_rows,
        receipt_count,
        total_spent,
    )

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
        "insight_summary": insight_summary,
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

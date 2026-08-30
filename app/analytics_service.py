from collections import defaultdict
from datetime import date
from statistics import median

from app.category_keywords import (
    CANONICAL_CATEGORIES,
    UNRESOLVED_CATEGORY,
    category_for_reporting,
    normalize_category_name,
)
from app.db import get_connection
from app.price_deviation import (
    PRICE_UNIT_LABELS,
    has_resolved_price_identity,
    is_eligible_price_observation,
)
from app.product_identity import (
    effective_product_identity_sql,
    resolve_effective_product_identity,
)


PRODUCT_NAME_EXPR = effective_product_identity_sql("items")


def _empty_normalized_price_trend(reason):
    return {
        "status": "insufficient",
        "reason": reason,
        "labels": [],
        "values": [],
        "observation_counts": [],
        "normalized_price_unit": None,
        "unit_label": None,
    }


def build_normalized_price_trend(observations):
    rows = list(observations)
    if not rows or not has_resolved_price_identity(rows):
        return _empty_normalized_price_trend("unresolved_product_identity")

    eligible = [row for row in rows if is_eligible_price_observation(row)]
    units = {row["normalized_price_unit"] for row in eligible}
    if len(units) > 1:
        return _empty_normalized_price_trend("incompatible_price_units")
    if not eligible:
        return _empty_normalized_price_trend("no_comparable_history")

    prices_by_month = defaultdict(list)
    for row in eligible:
        try:
            month = date.fromisoformat(str(row["date"])).strftime("%Y-%m")
        except (KeyError, TypeError, ValueError):
            continue
        prices_by_month[month].append(float(row["normalized_unit_price"]))
    if not prices_by_month:
        return _empty_normalized_price_trend("no_comparable_history")

    labels = sorted(prices_by_month)
    unit = next(iter(units))
    return {
        "status": "ready",
        "reason": None,
        "labels": labels,
        "values": [round(float(median(prices_by_month[month])), 4) for month in labels],
        "observation_counts": [len(prices_by_month[month]) for month in labels],
        "normalized_price_unit": unit,
        "unit_label": PRICE_UNIT_LABELS[unit],
    }


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
        normalized_category = normalize_category_name(category)
        if normalized_category == UNRESOLVED_CATEGORY:
            placeholders = ", ".join("?" for _ in CANONICAL_CATEGORIES)
            conditions.append(
                f"(items.category IS NULL OR TRIM(items.category) = '' "
                f"OR LOWER(TRIM(items.category)) NOT IN ({placeholders}))"
            )
            params.extend(CANONICAL_CATEGORIES)
        else:
            conditions.append("LOWER(TRIM(items.category)) = ?")
            params.append(normalized_category)
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
        raw_category_rows = cursor.fetchall()

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

    category_totals = {}
    for category_name, amount in raw_category_rows:
        category = category_for_reporting(category_name)
        category_totals[category] = category_totals.get(category, 0) + float(amount or 0)
    category_rows = sorted(
        category_totals.items(),
        key=lambda row: (-row[1], row[0]),
    )
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
        effective_name = resolve_effective_product_identity(conn, item_name)
        if effective_name is None:
            return _empty_normalized_price_trend("unknown_product")
        rows = conn.execute(f"""
            SELECT items.id, items.receipt_id, {PRODUCT_NAME_EXPR} AS effective_name,
                   items.name, items.canonical_name, items.normalized_name,
                   receipts.store, receipts.date, items.quantity, items.price,
                   items.line_total, items.unit_price, items.quantity_unit,
                   items.package_size, items.package_unit,
                   items.normalized_unit_price, items.normalized_price_unit,
                   items.price_parse_source, items.price_parse_confidence
            FROM items
            JOIN receipts ON items.receipt_id = receipts.id
            WHERE {PRODUCT_NAME_EXPR} = ?
            ORDER BY receipts.date, items.receipt_id, items.id
        """, (effective_name,)).fetchall()

    columns = (
        "id", "receipt_id", "effective_name", "name", "canonical_name",
        "normalized_name", "store", "date", "quantity", "price",
        "line_total", "unit_price", "quantity_unit", "package_size",
        "package_unit", "normalized_unit_price", "normalized_price_unit",
        "price_parse_source", "price_parse_confidence",
    )
    return build_normalized_price_trend(dict(zip(columns, row)) for row in rows)

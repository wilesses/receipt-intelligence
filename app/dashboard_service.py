"""Read-only aggregations and presentation data for the Intelligence Briefing."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import re
from statistics import median
from urllib.parse import quote, urlencode

from app.category_keywords import UNRESOLVED_CATEGORY, category_for_reporting
from app.category_rules import get_product_key
from app.db import get_connection
from app.price_deviation import evaluate_price_deviation
from app.product_identity import effective_product_identity_sql
from app.product_matcher import find_similar_products


@dataclass(frozen=True)
class PeriodWindow:
    key: str
    label: str
    start: date | None
    end: date
    previous_start: date | None
    previous_end: date | None


PERIOD_LABELS = {
    "current_month": "Текущий месяц",
    "previous_month": "Прошлый месяц",
    "last_30_days": "Последние 30 дней",
    "all_time": "За всё время",
}

PRICE_UNIT_LABELS = {
    "eur_per_kg": "EUR/kg",
    "eur_per_l": "EUR/l",
    "eur_per_piece": "EUR/gab",
}

MONTH_NAMES_RU = (
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

SUPPORTED_PRICE_UNITS = set(PRICE_UNIT_LABELS)
PRODUCT_NAME_EXPR = effective_product_identity_sql("items")

STORY_MAX_EVIDENCE = 3
STORY_MAX_TIMELINE_EVENTS = 60
MONTH_KEY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_month(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def resolve_period(period_key: str, as_of: date | None = None) -> PeriodWindow:
    as_of = as_of or date.today()
    if period_key.startswith("month:"):
        month_key = period_key.removeprefix("month:")
        if MONTH_KEY_RE.fullmatch(month_key):
            year, month = (int(part) for part in month_key.split("-"))
            start = date(year, month, 1)
            end = _shift_month(start, 1)
            return PeriodWindow(
                period_key,
                f"{MONTH_NAMES_RU[month]} {year}",
                start,
                end,
                _shift_month(start, -1),
                start,
            )
    key = period_key if period_key in PERIOD_LABELS else "current_month"
    tomorrow = as_of + timedelta(days=1)
    current_start = _month_start(as_of)

    if key == "current_month":
        previous_start = _shift_month(current_start, -1)
        elapsed_days = (tomorrow - current_start).days
        previous_end = min(previous_start + timedelta(days=elapsed_days), current_start)
        return PeriodWindow(
            key, PERIOD_LABELS[key], current_start, tomorrow, previous_start, previous_end
        )

    if key == "previous_month":
        start = _shift_month(current_start, -1)
        return PeriodWindow(
            key,
            PERIOD_LABELS[key],
            start,
            current_start,
            _shift_month(start, -1),
            start,
        )

    if key == "last_30_days":
        start = as_of - timedelta(days=29)
        previous_start = start - timedelta(days=30)
        return PeriodWindow(
            key, PERIOD_LABELS[key], start, tomorrow, previous_start, start
        )

    return PeriodWindow(key, PERIOD_LABELS[key], None, tomorrow, None, None)


def get_available_receipt_months() -> list[dict]:
    """Return real receipt months, newest first, for the server-rendered story selector."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', date) AS month_key, COUNT(*)
            FROM receipts
            WHERE date(date) IS NOT NULL
            GROUP BY month_key
            HAVING COUNT(*) > 0
            ORDER BY month_key DESC
            """
        ).fetchall()
    months = []
    for month_key, receipt_count in rows:
        if not month_key or not MONTH_KEY_RE.fullmatch(month_key):
            continue
        year, month = (int(part) for part in month_key.split("-"))
        months.append({
            "key": month_key,
            "label": f"{MONTH_NAMES_RU[month]} {year}",
            "receipt_count": int(receipt_count),
        })
    return months


def resolve_story_month(
    requested_month: str | None,
    available_months: list[dict],
    *,
    as_of: date | None = None,
) -> str:
    """Validate a requested story month and choose a safe data-backed fallback."""
    as_of = as_of or date.today()
    available_keys = {month["key"] for month in available_months}
    current_key = as_of.strftime("%Y-%m")
    fallback = current_key if current_key in available_keys else (
        available_months[0]["key"] if available_months else current_key
    )
    if requested_month and MONTH_KEY_RE.fullmatch(requested_month) and requested_month in available_keys:
        return requested_month
    return fallback


def _range_sql(start: date | None, end: date, column: str = "receipts.date"):
    conditions = [f"date({column}) IS NOT NULL", f"{column} < ?"]
    params = [end.isoformat()]
    if start is not None:
        conditions.insert(0, f"{column} >= ?")
        params.insert(0, start.isoformat())
    return " AND ".join(conditions), params


def _summary(conn, start: date | None, end: date) -> dict:
    where, params = _range_sql(start, end)
    row = conn.execute(
        f"SELECT COALESCE(SUM(total), 0), COUNT(*) FROM receipts WHERE {where}", params
    ).fetchone()
    return {"spend": round(float(row[0] or 0), 2), "receipt_count": int(row[1] or 0)}


def _trend(conn, window: PeriodWindow) -> dict:
    where, params = _range_sql(window.start, window.end)
    if window.start is None:
        rows = conn.execute(
            f"""
            SELECT strftime('%Y-%m', date), COALESCE(SUM(total), 0)
            FROM receipts
            WHERE {where}
            GROUP BY strftime('%Y-%m', date)
            ORDER BY strftime('%Y-%m', date)
            """,
            params,
        ).fetchall()
        return {
            "labels": [row[0] for row in rows if row[0]],
            "values": [round(float(row[1] or 0), 2) for row in rows if row[0]],
            "granularity": "month",
        }

    rows = conn.execute(
        f"""
        SELECT date, COALESCE(SUM(total), 0)
        FROM receipts
        WHERE {where}
        GROUP BY date
        ORDER BY date
        """,
        params,
    ).fetchall()
    values_by_day = {row[0]: round(float(row[1] or 0), 2) for row in rows}
    labels = []
    values = []
    cursor = window.start
    while cursor < window.end:
        key = cursor.isoformat()
        labels.append(key)
        values.append(values_by_day.get(key, 0.0))
        cursor += timedelta(days=1)
    return {"labels": labels, "values": values, "granularity": "day"}


def _category_totals(conn, start: date | None, end: date) -> dict[str, float]:
    where, params = _range_sql(start, end)
    rows = conn.execute(
        f"""
        SELECT items.category, COALESCE(SUM(COALESCE(items.line_total, items.price, 0)), 0)
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        WHERE {where}
        GROUP BY items.category
        """,
        params,
    ).fetchall()
    totals = {}
    for category, amount in rows:
        normalized = category_for_reporting(category)
        totals[normalized] = totals.get(normalized, 0.0) + float(amount or 0)
    return totals


def _category_changes(conn, window: PeriodWindow) -> list[dict]:
    current = _category_totals(conn, window.start, window.end)
    previous = (
        _category_totals(conn, window.previous_start, window.previous_end)
        if window.previous_end is not None
        else {}
    )
    changes = [
        {
            "category": category,
            "current": round(current.get(category, 0.0), 2),
            "previous": round(previous.get(category, 0.0), 2),
            "delta": round(current.get(category, 0.0) - previous.get(category, 0.0), 2),
        }
        for category in current.keys() | previous.keys()
    ]
    changes.sort(key=lambda item: (-abs(item["delta"]), -item["current"], item["category"]))
    visible = changes[:5]
    largest = abs(visible[0]["delta"]) if visible else 0
    for item in visible:
        item["magnitude_percent"] = round(abs(item["delta"]) / largest * 100, 1) if largest else 0
    return visible


def _insight(summary: dict, comparison: dict | None, changes: list[dict]) -> str:
    if not summary["receipt_count"]:
        return "За выбранный период чеков нет."
    if comparison is None:
        if changes:
            return f"Крупнейшая категория периода — {changes[0]['category']}: {changes[0]['current']:.2f} €."
        return "Недостаточно категорий для интерпретации."

    delta = comparison["absolute_delta"]
    if delta > 0:
        first = f"Расходы выросли на {abs(delta):.2f} €."
    elif delta < 0:
        first = f"Расходы снизились на {abs(delta):.2f} €."
    else:
        first = "Расходы не изменились."
    if not changes:
        return first
    leader = changes[0]
    direction = "рост" if leader["delta"] >= 0 else "снижение"
    return f"{first} Крупнейшее изменение категорий — {leader['category']}: {direction} на {abs(leader['delta']):.2f} €."


def _meaningful_spend_change(comparison: dict | None) -> bool:
    if not comparison or not comparison.get("previous_receipt_count"):
        return False
    delta = abs(comparison["absolute_delta"])
    percentage = abs(comparison.get("percentage_delta") or 0)
    return delta >= 5 and percentage >= 5


def _analytics_href(window: PeriodWindow, **filters) -> str:
    params = {
        "start": window.start.isoformat() if window.start else None,
        "end": (window.end - timedelta(days=1)).isoformat(),
        **filters,
    }
    return f"/analytics?{urlencode({key: value for key, value in params.items() if value is not None})}"


def build_briefing(
    window: PeriodWindow,
    summary: dict,
    comparison: dict | None,
    category_changes: list[dict],
    action_queue: list[dict],
) -> dict:
    """Build deterministic, read-only copy and Trace data for the opening briefing."""
    receipt_count = summary["receipt_count"]
    spend = summary["spend"]
    has_baseline = bool(comparison and comparison.get("previous_receipt_count"))
    spend_changed = _meaningful_spend_change(comparison)
    urgent_operations = [
        item for item in action_queue if item["severity"] in {"critical", "high"}
    ]

    if not receipt_count:
        conclusion = (
            "За выбранный период чеков нет. Новых изменений для разбора не обнаружено."
        )
        significance = "Спокойный период: система не будет делать выводы без новых данных."
    elif not has_baseline:
        conclusion = (
            f"Расходы за период составили {spend:.2f} €. "
            "Для надежного сравнения пока не хватает данных прошлого периода."
        )
        significance = "Текущий период станет базой для следующего сопоставимого обзора."
    elif not spend_changed:
        conclusion = "Расходы остаются стабильными относительно прошлого периода."
        significance = (
            f"Изменение {comparison['absolute_delta']:+.2f} € не прошло порог значимости; "
            "срочной реакции не требуется."
        )
    else:
        delta = comparison["absolute_delta"]
        direction = "выросли" if delta > 0 else "снизились"
        conclusion = f"Расходы {direction} на {abs(delta):.2f} € относительно прошлого периода."
        visit_delta = receipt_count - comparison["previous_receipt_count"]
        leader = category_changes[0] if category_changes else None
        if visit_delta and (visit_delta > 0) == (delta > 0):
            visits = abs(visit_delta)
            conclusion += (
                f" Изменение совпало с {'дополнительными' if visit_delta > 0 else 'меньшим числом'} "
                f"походов за покупками: {visits}."
            )
        elif leader and leader["delta"] and (leader["delta"] > 0) == (delta > 0):
            conclusion += (
                f" Наиболее заметный сдвиг сосредоточен в категории «{leader['category']}»."
            )
        significance = (
            "Изменение достаточно велико, чтобы проверить его источник до следующей покупки."
            if delta > 0
            else "Снижение заметно и может указывать на устойчивое изменение покупательского ритма."
        )

    findings = []
    if has_baseline and category_changes:
        leader = category_changes[0]
        category_threshold = max(5.0, comparison["previous_spend"] * 0.05)
        if abs(leader["delta"]) >= category_threshold:
            direction = "выросли" if leader["delta"] > 0 else "снизились"
            findings.append({
                "key": "category_movement",
                "title": f"Расходы в категории «{leader['category']}» {direction} на {abs(leader['delta']):.2f} €.",
                "significance": "Это крупнейшее категорийное изменение выбранного периода.",
                "evidence_label": f"Сравнение двух периодов · {leader['current']:.2f} € сейчас",
                "comparison": f"{leader['previous']:.2f} € → {leader['current']:.2f} €",
                "reason": "Сдвиг рассчитан по сумме позиций, отнесенных к этой категории.",
                "evidence_summary": f"Разница составляет {leader['delta']:+.2f} € между сопоставимыми периодами.",
                "links": [{"href": _analytics_href(window, category=leader["category"]), "label": "Исследовать категорию"}],
                "decision": "Проверить товары, сформировавшие изменение.",
            })

    if has_baseline:
        visit_delta = receipt_count - comparison["previous_receipt_count"]
        if visit_delta:
            findings.append({
                "key": "visit_frequency",
                "title": f"Число походов за покупками {'выросло' if visit_delta > 0 else 'снизилось'} на {abs(visit_delta)}.",
                "significance": "Частота визитов помогает отличить изменение ритма от одного крупного чека.",
                "evidence_label": f"{receipt_count} чеков сейчас · {comparison['previous_receipt_count']} ранее",
                "comparison": f"{comparison['previous_receipt_count']} → {receipt_count} чеков",
                "reason": "Система сравнила количество чеков в равных временных окнах.",
                "evidence_summary": "Каждый учтенный чек доступен в архиве за выбранный период.",
                "links": [{"href": f"/?{urlencode({'view': 'receipts', 'period': window.key})}", "label": "Открыть чеки периода"}],
                "decision": "Проверить, были ли дополнительные визиты запланированными.",
            })

    for operation in urgent_operations:
        findings.append({
            "key": operation["key"],
            "title": f"{operation['title']}: {operation['count']}.",
            "significance": "Проблема может снизить точность интерпретации расходов.",
            "evidence_label": f"{operation['count']} записей требуют проверки",
            "comparison": "Проверка качества текущего набора данных",
            "reason": operation["explanation"],
            "evidence_summary": "Список уже отфильтрован в существующем рабочем процессе.",
            "links": [{"href": operation["href"], "label": operation["action"]}],
            "decision": f"{operation['action']} записи с наивысшим приоритетом.",
        })

    findings = findings[:3]
    quiet = not receipt_count or (has_baseline and not spend_changed and not findings)
    if quiet and receipt_count:
        conclusion = "Все выглядит стабильно за выбранный период."
        significance = "Значимых изменений расходов и срочных проблем качества не обнаружено."

    return {
        "quiet": quiet,
        "conclusion": conclusion,
        "significance": significance,
        "findings": findings,
        "has_baseline": has_baseline,
        "selected_range": (
            f"{window.start.isoformat()} — {(window.end - timedelta(days=1)).isoformat()}"
            if window.start else f"До {(window.end - timedelta(days=1)).isoformat()}"
        ),
        "comparison_range": (
            f"{window.previous_start.isoformat()} — {(window.previous_end - timedelta(days=1)).isoformat()}"
            if window.previous_start and window.previous_end else None
        ),
    }


def _receipt_rows(conn, window: PeriodWindow, *, limit=None, store_search="") -> list[dict]:
    where, params = _range_sql(window.start, window.end)
    if store_search:
        where += " AND LOWER(receipts.store) LIKE LOWER(?)"
        params.append(f"%{store_search}%")
    limit_sql = " LIMIT ?" if limit is not None else ""
    if limit is not None:
        params.append(limit)
    rows = conn.execute(
        f"""
        SELECT receipts.id, receipts.receipt_number, receipts.date, receipts.store, receipts.total,
               COUNT(items.id),
               SUM(CASE WHEN items.id IS NOT NULL AND (
                    items.price_parse_confidence IS NULL OR items.price_parse_confidence < 0.75
                    OR items.normalized_unit_price > 10000 OR items.normalized_unit_price <= 0
               ) THEN 1 ELSE 0 END)
        FROM receipts
        LEFT JOIN items ON items.receipt_id = receipts.id
        WHERE {where}
        GROUP BY receipts.id
        ORDER BY receipts.date DESC, receipts.id DESC
        {limit_sql}
        """,
        params,
    ).fetchall()
    receipts = [
        {
            "id": row[0],
            "receipt_number": row[1],
            "date": row[2],
            "store": row[3],
            "total": round(float(row[4] or 0), 2),
            "item_count": int(row[5] or 0),
            "price_warning_count": int(row[6] or 0),
            "preview_items": [],
        }
        for row in rows
    ]
    receipt_ids = [receipt["id"] for receipt in receipts]
    if receipt_ids:
        placeholders = ", ".join("?" for _ in receipt_ids)
        preview_rows = conn.execute(
            f"""
            SELECT receipt_id, name, quantity, price, category, category_source,
                   price_parse_confidence, normalized_unit_price
            FROM (
                SELECT receipt_id, name, quantity, price, category, category_source,
                       price_parse_confidence, normalized_unit_price,
                       ROW_NUMBER() OVER (PARTITION BY receipt_id ORDER BY id) AS row_number
                FROM items
                WHERE receipt_id IN ({placeholders})
            )
            WHERE row_number <= 8
            ORDER BY receipt_id, row_number
            """,
            receipt_ids,
        ).fetchall()
        by_receipt = {receipt["id"]: receipt for receipt in receipts}
        for row in preview_rows:
            by_receipt[row[0]]["preview_items"].append(
                {
                    "name": row[1],
                    "quantity": float(row[2] or 0),
                    "price": round(float(row[3] or 0), 2),
                    "category": category_for_reporting(row[4]),
                    "category_source": row[5] or "rule",
                    "price_parse_confidence": row[6],
                    "has_price_warning": (
                        row[6] is None
                        or float(row[6]) < 0.75
                        or (row[7] is not None and (float(row[7]) > 10000 or float(row[7]) <= 0))
                    ),
                }
            )
    return receipts


def _month_forecast(
    *,
    spend: float,
    receipt_count: int,
    item_line_count: int,
    latest_receipt_date: str | None,
    as_of: date,
) -> dict:
    days_in_month = monthrange(as_of.year, as_of.month)[1]
    reasons = []
    if as_of.day < 7:
        reasons.append("less_than_7_elapsed_days")
    if receipt_count < 3:
        reasons.append("less_than_3_receipts")
    if item_line_count < 10:
        reasons.append("less_than_10_item_lines")
    if latest_receipt_date:
        try:
            latest = date.fromisoformat(latest_receipt_date)
        except ValueError:
            latest = None
        if latest is None or (as_of - latest).days > 3:
            reasons.append("latest_receipt_older_than_3_days")
    else:
        reasons.append("no_current_month_receipts")

    if reasons:
        return {
            "eligible": False,
            "amount": None,
            "reason": "Insufficient data for forecast",
            "reasons": reasons,
            "elapsed_days": as_of.day,
            "days_in_month": days_in_month,
        }

    return {
        "eligible": True,
        "amount": round(spend / as_of.day * days_in_month, 2),
        "reason": None,
        "reasons": [],
        "elapsed_days": as_of.day,
        "days_in_month": days_in_month,
    }


def _product_price_context(conn, product_key: str, month_start: date, month_end: date) -> dict:
    placeholders = ", ".join("?" for _ in SUPPORTED_PRICE_UNITS)
    rows = conn.execute(
        f"""
        SELECT items.id, receipts.date, items.normalized_unit_price, items.normalized_price_unit
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        WHERE {PRODUCT_NAME_EXPR} = ?
          AND items.normalized_unit_price IS NOT NULL
          AND items.normalized_unit_price > 0
          AND items.normalized_price_unit IN ({placeholders})
          AND date(receipts.date) IS NOT NULL
          AND receipts.date < ?
        ORDER BY receipts.date DESC, receipts.id DESC, items.id DESC
        """,
        [product_key, *sorted(SUPPORTED_PRICE_UNITS), month_end.isoformat()],
    ).fetchall()

    latest = None
    for row in rows:
        try:
            row_date = date.fromisoformat(row[1])
        except (TypeError, ValueError):
            continue
        if month_start <= row_date < month_end:
            latest = row
            break

    if latest is None:
        return {
            "latest_price": None,
            "unit": None,
            "unit_label": None,
            "change_percent": None,
            "history_label": "No comparable history",
        }

    latest_price = round(float(latest[2]), 2)
    unit = latest[3]
    previous = next((row for row in rows if row[0] != latest[0] and row[3] == unit), None)
    if previous is None or not float(previous[2] or 0):
        change_percent = None
        history_label = "No comparable history"
    else:
        previous_price = float(previous[2])
        change_percent = round((float(latest[2]) - previous_price) / previous_price * 100, 1)
        history_label = f"{change_percent:+.1f}%"

    return {
        "latest_price": latest_price,
        "unit": unit,
        "unit_label": PRICE_UNIT_LABELS.get(unit, unit),
        "change_percent": change_percent,
        "history_label": history_label,
    }


def _top_month_products(conn, month_start: date, month_end: date) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT
            {PRODUCT_NAME_EXPR} AS product_key,
            {PRODUCT_NAME_EXPR} AS display_name,
            ROUND(COALESCE(SUM(COALESCE(items.line_total, items.price, 0)), 0), 2) AS spend,
            COUNT(*) AS purchase_count
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        WHERE receipts.date >= ?
          AND receipts.date < ?
          AND date(receipts.date) IS NOT NULL
        GROUP BY product_key
        ORDER BY spend DESC, purchase_count DESC, LOWER(display_name)
        LIMIT 3
        """,
        (month_start.isoformat(), month_end.isoformat()),
    ).fetchall()

    products = []
    for row in rows:
        price_context = _product_price_context(conn, row[0], month_start, month_end)
        products.append({
            "key": row[0],
            "name": row[1],
            "spend": round(float(row[2] or 0), 2),
            "purchase_count": int(row[3] or 0),
            **price_context,
        })
    return products


def _receipt_month_summary(
    conn, as_of: date, window: PeriodWindow | None = None
) -> dict:
    is_selected_month = bool(
        window
        and window.key.startswith("month:")
        and window.start
    )
    month_start = window.start if is_selected_month else as_of.replace(day=1)
    month_end = window.end if is_selected_month else as_of + timedelta(days=1)
    receipt_row = conn.execute(
        """
        SELECT ROUND(COALESCE(SUM(total), 0), 2), COUNT(*), MAX(date)
        FROM receipts
        WHERE date(date) IS NOT NULL
          AND date >= ?
          AND date < ?
        """,
        (month_start.isoformat(), month_end.isoformat()),
    ).fetchone()
    item_row = conn.execute(
        """
        SELECT COUNT(items.id)
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        WHERE date(receipts.date) IS NOT NULL
          AND receipts.date >= ?
          AND receipts.date < ?
        """,
        (month_start.isoformat(), month_end.isoformat()),
    ).fetchone()
    spend = round(float(receipt_row[0] or 0), 2)
    receipt_count = int(receipt_row[1] or 0)
    item_line_count = int(item_row[0] or 0)
    latest_receipt_date = receipt_row[2]
    top_products = _top_month_products(conn, month_start, month_end)
    forecast = (
        {
            "eligible": False,
            "amount": None,
            "elapsed_days": monthrange(month_start.year, month_start.month)[1],
            "days_in_month": monthrange(month_start.year, month_start.month)[1],
            "reasons": ["completed_month"],
        }
        if is_selected_month
        else _month_forecast(
            spend=spend,
            receipt_count=receipt_count,
            item_line_count=item_line_count,
            latest_receipt_date=latest_receipt_date,
            as_of=as_of,
        )
    )
    return {
        "month_label": month_start.strftime("%Y-%m"),
        "display_label": f"{MONTH_NAMES_RU[month_start.month]} {month_start.year}",
        "is_selected_month": is_selected_month,
        "spend": spend,
        "receipt_count": receipt_count,
        "item_line_count": item_line_count,
        "latest_receipt_date": latest_receipt_date,
        "forecast": forecast,
        "top_products": top_products,
    }


def get_period_receipts(window: PeriodWindow, store_search: str = "") -> list[dict]:
    with get_connection() as conn:
        return _receipt_rows(conn, window, store_search=store_search)


def _story_receipts(conn, start: date | None, end: date) -> list[dict]:
    where, params = _range_sql(start, end)
    rows = conn.execute(
        f"""
        SELECT id, receipt_number, date, store, ROUND(COALESCE(total, 0), 2)
        FROM receipts
        WHERE {where}
        ORDER BY date, id
        """,
        params,
    ).fetchall()
    return [
        {
            "id": int(row[0]),
            "receipt_number": row[1],
            "date": row[2],
            "store": row[3],
            "total": round(float(row[4] or 0), 2),
            "href": f"/receipt/{int(row[0])}",
        }
        for row in rows
    ]


def _story_category_data(conn, window: PeriodWindow) -> dict:
    def period_data(start, end):
        where, params = _range_sql(start, end)
        rows = conn.execute(
            f"""
            SELECT items.category, receipts.id,
                   COALESCE(items.line_total, items.price, 0)
            FROM items
            JOIN receipts ON receipts.id = items.receipt_id
            WHERE {where}
            """,
            params,
        ).fetchall()
        totals = {}
        receipt_amounts = {}
        covered = 0.0
        other = 0.0
        for category, receipt_id, amount in rows:
            value = max(0.0, float(amount or 0))
            normalized = category_for_reporting(category)
            totals[normalized] = totals.get(normalized, 0.0) + value
            receipt_amounts.setdefault(normalized, {})[int(receipt_id)] = (
                receipt_amounts.setdefault(normalized, {}).get(int(receipt_id), 0.0) + value
            )
            covered += value
            if normalized == UNRESOLVED_CATEGORY:
                other += value
        return {
            "totals": totals,
            "receipt_amounts": receipt_amounts,
            "covered": covered,
            "other": other,
        }

    current = period_data(window.start, window.end)
    previous = (
        period_data(window.previous_start, window.previous_end)
        if window.previous_end is not None
        else {"totals": {}, "receipt_amounts": {}, "covered": 0.0, "other": 0.0}
    )
    return {"current": current, "previous": previous}


def _story_item_candidates(conn, window: PeriodWindow, summary: dict, comparison: dict | None) -> list[dict]:
    if window.start is None:
        return []
    where, params = _range_sql(window.start, window.end)
    current_rows = conn.execute(
        f"""
        SELECT items.id, items.receipt_id, receipts.date, receipts.store, items.name,
               {PRODUCT_NAME_EXPR},
               {PRODUCT_NAME_EXPR},
               items.canonical_name, items.normalized_name,
               COALESCE(items.line_total, items.price, 0),
               items.quantity, items.price, items.line_total, items.unit_price,
               items.quantity_unit, items.package_size, items.package_unit,
               items.normalized_unit_price, items.normalized_price_unit,
               items.price_parse_source, items.price_parse_confidence, items.category
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        WHERE {where}
        ORDER BY receipts.date, items.receipt_id, items.id
        """,
        params,
    ).fetchall()
    history_start = window.start - timedelta(days=180)
    history_rows = conn.execute(
        f"""
        SELECT items.id, items.receipt_id, receipts.date, receipts.store, items.name,
               {PRODUCT_NAME_EXPR},
               {PRODUCT_NAME_EXPR},
               items.canonical_name, items.normalized_name,
               COALESCE(items.line_total, items.price, 0),
               items.quantity, items.price, items.line_total, items.unit_price,
               items.quantity_unit, items.package_size, items.package_unit,
               items.normalized_unit_price, items.normalized_price_unit,
               items.price_parse_source, items.price_parse_confidence, items.category
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        WHERE receipts.date >= ? AND receipts.date < ? AND date(receipts.date) IS NOT NULL
        ORDER BY receipts.date, items.receipt_id, items.id
        """,
        (history_start.isoformat(), window.start.isoformat()),
    ).fetchall()
    columns = (
        "id", "receipt_id", "date", "store", "name", "story_key",
        "effective_name", "canonical_name", "normalized_name", "amount",
        "quantity", "price", "line_total", "unit_price", "quantity_unit",
        "package_size", "package_unit", "normalized_unit_price",
        "normalized_price_unit", "price_parse_source", "price_parse_confidence",
        "category",
    )
    current_rows = [dict(zip(columns, row)) for row in current_rows]
    history_rows = [dict(zip(columns, row)) for row in history_rows]
    history_amounts = {}
    categories_by_price_key = {}
    price_rows_by_key = {}
    unusual_history_start = window.start - timedelta(days=90)
    for row in [*history_rows, *current_rows]:
        price_key = row["effective_name"]
        if price_key:
            price_rows_by_key.setdefault(price_key, []).append(row)
            categories_by_price_key.setdefault(price_key, set()).add(
                category_for_reporting(row["category"])
            )
    for row in history_rows:
        key = row["story_key"]
        if (
            key
            and row["date"] >= unusual_history_start.isoformat()
            and float(row["amount"] or 0) > 0
        ):
            history_amounts.setdefault(key, []).append(float(row["amount"]))

    absolute_delta = abs((comparison or {}).get("absolute_delta") or 0)
    candidates = []
    for row in current_rows:
        key = row["story_key"]
        price_key = row["effective_name"]
        value = max(0.0, float(row["amount"] or 0))
        prior_amounts = history_amounts.get(key, [])
        unusual = (
            len(prior_amounts) >= 5
            and value >= max(40.0, 3 * median(prior_amounts))
            and (
                (summary["spend"] > 0 and value >= summary["spend"] * 0.25)
                or (absolute_delta > 0 and value >= absolute_delta * 0.5)
            )
        )
        price_result = evaluate_price_deviation(
            row,
            price_rows_by_key.get(price_key, []),
        )
        price_change = price_result["deviation_percent"]
        price_effect = (
            abs(price_result["current_normalized_price"] - price_result["historical_median"])
            if price_result["historical_median"] is not None
            else 0.0
        )
        candidates.append({
            "item_id": int(row["id"]), "receipt_id": int(row["receipt_id"]), "date": row["date"],
            "store": row["store"], "name": row["name"] or price_key,
            "key": key, "price_key": price_key, "amount": round(value, 2),
            "unusual": unusual, "history_count": len(prior_amounts),
            "unit_price": price_result["current_normalized_price"],
            "unit": price_result["normalized_price_unit"],
            "price_status": price_result["status"],
            "price_history_count": price_result["eligible_prior_observation_count"],
            "price_change_percent": price_change,
            "price_effect": round(price_effect, 2),
            "category_conflict": len(categories_by_price_key.get(price_key, set())) > 1,
        })
    return candidates


def _story_insight(
    conn, window: PeriodWindow, summary: dict, comparison: dict | None,
    receipts: list[dict], category_data: dict, item_candidates: list[dict],
) -> dict:
    receipt_by_id = {receipt["id"]: receipt for receipt in receipts}
    absolute_delta = abs((comparison or {}).get("absolute_delta") or 0)

    unusual_items = sorted(
        (item for item in item_candidates if item["unusual"]),
        key=lambda item: (-item["amount"], item["key"], item["receipt_id"]),
    )
    prior_receipts = []
    if window.start is not None:
        prior_start = window.start - timedelta(days=90)
        prior_receipts = _story_receipts(conn, prior_start, window.start)
    prior_totals = [receipt["total"] for receipt in prior_receipts if receipt["total"] > 0]
    unusual_receipts = []
    if len(prior_totals) >= 5:
        threshold = max(100.0, 3 * median(prior_totals))
        unusual_receipts = [
            receipt for receipt in receipts
            if receipt["total"] >= threshold and (
                (summary["spend"] > 0 and receipt["total"] >= summary["spend"] * 0.25)
                or (absolute_delta > 0 and receipt["total"] >= absolute_delta * 0.5)
            )
        ]
        unusual_receipts.sort(key=lambda receipt: (-receipt["total"], receipt["id"]))
    if unusual_items or unusual_receipts:
        if unusual_items and (not unusual_receipts or unusual_items[0]["amount"] >= unusual_receipts[0]["total"]):
            winner = unusual_items[0]
            receipt = receipt_by_id[winner["receipt_id"]]
            return {
                "type": "unusual_purchase", "priority": 1, "subject_key": winner["key"],
                "title": f"Одна из заметных покупок месяца — «{winner['name']}».",
                "metric_confirmation": f"{winner['amount']:.2f} € в чеке от {winner['date']}.",
                "metric_value": winner["amount"], "metric_unit": "EUR",
                "evidence_events": [receipt], "destination_link": receipt["href"],
                "destination_label": "Открыть чек",
            }
        receipt = unusual_receipts[0]
        return {
            "type": "unusual_purchase", "priority": 1, "subject_key": f"receipt:{receipt['id']}",
            "title": "Один чек заметно выделяется относительно недавних покупок.",
            "metric_confirmation": f"{receipt['total']:.2f} € — {receipt['store'] or 'магазин не указан'}, {receipt['date']}.",
            "metric_value": receipt["total"], "metric_unit": "EUR",
            "evidence_events": [receipt], "destination_link": receipt["href"],
            "destination_label": "Открыть чек",
        }

    has_baseline = bool(comparison and comparison.get("previous_receipt_count"))
    current = category_data["current"]
    previous = category_data["previous"]
    total_delta = (comparison or {}).get("absolute_delta") or 0
    current_coverage = current["covered"] / summary["spend"] if summary["spend"] > 0 else 0
    previous_spend = (comparison or {}).get("previous_spend") or 0
    previous_coverage = previous["covered"] / previous_spend if previous_spend > 0 else 0
    other_share = current["other"] / current["covered"] if current["covered"] > 0 else 1
    previous_other_share = previous["other"] / previous["covered"] if previous["covered"] > 0 else 1
    meaningful_delta = abs(total_delta) >= max(10.0, previous_spend * 0.10)
    category_candidates = []
    if (
        has_baseline and summary["receipt_count"] >= 3
        and comparison["previous_receipt_count"] >= 3 and meaningful_delta
        and current_coverage >= 0.80 and previous_coverage >= 0.80
        and other_share <= 0.30 and previous_other_share <= 0.30
    ):
        for category in current["totals"].keys() | previous["totals"].keys():
            category_delta = current["totals"].get(category, 0) - previous["totals"].get(category, 0)
            if (
                category != UNRESOLVED_CATEGORY and category_delta and total_delta
                and (category_delta > 0) == (total_delta > 0)
                and abs(category_delta) >= max(10.0, abs(total_delta) * 0.40)
            ):
                category_candidates.append((abs(category_delta) / abs(total_delta), abs(category_delta), category, category_delta))
    if category_candidates:
        ratio, _, category, category_delta = sorted(
            category_candidates, key=lambda item: (-item[0], -item[1], item[2])
        )[0]
        evidence_ids = sorted(
            current["receipt_amounts"].get(category, {}).items(),
            key=lambda item: (-item[1], item[0]),
        )[:STORY_MAX_EVIDENCE]
        evidence = [receipt_by_id[receipt_id] for receipt_id, _ in evidence_ids if receipt_id in receipt_by_id]
        direction = "выше" if category_delta > 0 else "ниже"
        return {
            "type": "category_impact", "priority": 2, "subject_key": category,
            "title": f"Самый заметный сдвиг месяца сосредоточен в категории «{category}».",
            "metric_confirmation": f"Расходы в категории на {abs(category_delta):.2f} € {direction}; это соответствует {min(ratio, 1) * 100:.0f}% общего изменения.",
            "metric_value": round(category_delta, 2), "metric_unit": "EUR",
            "impact_ratio": round(min(ratio, 1), 4), "raw_impact_ratio": round(ratio, 4),
            "evidence_events": evidence,
            "destination_link": _analytics_href(window, category=category),
            "destination_label": "Открыть категорию",
        }

    if has_baseline and window.start and window.previous_start and window.previous_end:
        current_days = (window.end - window.start).days
        previous_days = (window.previous_end - window.previous_start).days
        previous_count = comparison["previous_receipt_count"]
        count_delta = summary["receipt_count"] - previous_count
        count_ratio = abs(count_delta) / previous_count if previous_count else 0
        estimated = abs(count_delta) * (previous_spend / previous_count if previous_count else 0)
        frequency_delta_is_meaningful = abs(total_delta) >= max(10.0, previous_spend * 0.10)
        if (
            current_days >= 7 and previous_days >= 7
            and summary["receipt_count"] + previous_count >= 5
            and abs(count_delta) >= 3 and count_ratio >= 0.40 and total_delta
            and frequency_delta_is_meaningful
            and (count_delta > 0) == (total_delta > 0)
            and estimated >= abs(total_delta) * 0.40
        ):
            evidence = sorted(receipts, key=lambda receipt: (receipt["date"], receipt["id"]), reverse=True)[:STORY_MAX_EVIDENCE]
            return {
                "type": "visit_frequency", "priority": 3, "subject_key": "receipt_frequency",
                "title": "В сопоставимом окне изменилось число походов за покупками.",
                "metric_confirmation": f"{previous_count} → {summary['receipt_count']} чеков ({count_delta:+d}).",
                "metric_value": count_delta, "metric_unit": "receipts",
                "evidence_events": evidence,
                "destination_link": f"/?{urlencode({'view': 'receipts', 'period': window.key})}",
                "destination_label": "Открыть чеки периода",
            }

    price_candidates = []
    for item in item_candidates:
        change = item["price_change_percent"]
        if (
            change is not None and abs(change) >= 15
            and item["price_status"] in {"CHEAPER_THAN_USUAL", "MORE_EXPENSIVE_THAN_USUAL"}
            and not item["category_conflict"]
            and (
                (summary["spend"] > 0 and item["amount"] >= summary["spend"] * 0.10)
                or item["price_effect"] >= 3
            )
        ):
            price_candidates.append(item)
    if price_candidates:
        winner = sorted(
            price_candidates,
            key=lambda item: (-abs(item["price_change_percent"]), -item["amount"], item["price_key"]),
        )[0]
        receipt = receipt_by_id[winner["receipt_id"]]
        direction = "выше" if winner["price_change_percent"] > 0 else "ниже"
        unit_label = PRICE_UNIT_LABELS.get(winner["unit"], winner["unit"])
        return {
            "type": "normalized_price", "priority": 4, "subject_key": f"{winner['price_key']}:{winner['unit']}",
            "title": f"Нормализованная цена «{winner['name']}» заметно отличается от недавней истории.",
            "metric_confirmation": f"На {abs(winner['price_change_percent']):.1f}% {direction} медианы сопоставимых наблюдений · {unit_label}.",
            "metric_value": winner["price_change_percent"], "metric_unit": "percent",
            "evidence_events": [receipt],
            "destination_link": f"/item/{quote(winner['price_key'], safe='')}",
            "destination_label": "Открыть историю товара",
        }

    if not receipts:
        title = "За выбранный период чеков пока нет."
        confirmation = "После импорта появятся временная линия и сопоставимый вывод."
        destination = "/upload"
        destination_label = "Импортировать чек"
        subject = "empty"
    elif not has_baseline:
        title = "Этот период формирует базу для будущего сравнения."
        confirmation = f"{summary['receipt_count']} чек. · {summary['spend']:.2f} € без достаточной истории прошлого периода."
        destination = f"/?{urlencode({'view': 'receipts', 'period': window.key})}"
        destination_label = "Открыть чеки периода"
        subject = "no_baseline"
    else:
        delta = comparison["absolute_delta"]
        title = "Месяц прошёл без значимых отклонений по доступным данным."
        confirmation = f"Изменение к сопоставимому периоду: {delta:+.2f} €."
        destination = f"/?{urlencode({'view': 'receipts', 'period': window.key})}"
        destination_label = "Открыть чеки периода"
        subject = "stable"
    return {
        "type": "calm_month", "priority": 5, "subject_key": subject,
        "title": title, "metric_confirmation": confirmation,
        "metric_value": round((comparison or {}).get("absolute_delta") or summary["spend"], 2),
        "metric_unit": "EUR", "evidence_events": [],
        "destination_link": destination, "destination_label": destination_label,
    }


def _story_highlights(receipts: list[dict], evidence_ids: list[int]) -> list[dict]:
    if len(receipts) <= 3:
        return list(receipts)
    target = min(6, max(4, len(receipts)))
    candidates = list(evidence_ids)
    candidates.extend(receipt["id"] for receipt in sorted(receipts, key=lambda item: (-item["total"], item["id"]))[:2])
    candidates.extend((receipts[-1]["id"], receipts[0]["id"]))
    if len(receipts) > 4:
        candidates.extend(receipts[round((len(receipts) - 1) * fraction)]["id"] for fraction in (0.25, 0.5, 0.75))
    selected = []
    by_id = {receipt["id"]: receipt for receipt in receipts}
    for receipt_id in candidates:
        if receipt_id in by_id and receipt_id not in selected:
            selected.append(receipt_id)
        if len(selected) == target:
            break
    if len(selected) < target:
        for receipt in receipts:
            if receipt["id"] not in selected:
                selected.append(receipt["id"])
            if len(selected) == target:
                break
    return sorted((by_id[receipt_id] for receipt_id in selected), key=lambda item: (item["date"], item["id"]))


def _story_timeline(receipts: list[dict]) -> list[dict]:
    if len(receipts) <= STORY_MAX_TIMELINE_EVENTS:
        return [{"type": "receipt", **receipt} for receipt in receipts]
    grouped = {}
    for receipt in receipts:
        day = grouped.setdefault(receipt["date"], {"type": "day_group", "date": receipt["date"], "count": 0, "total": 0.0, "receipt_ids": []})
        day["count"] += 1
        day["total"] += receipt["total"]
        day["receipt_ids"].append(receipt["id"])
    events = list(grouped.values())
    for event in events:
        event["total"] = round(event["total"], 2)
    return events


def build_month_story(conn, window: PeriodWindow, summary: dict, comparison: dict | None) -> dict:
    """Build the deterministic, presentation-neutral contract for the future home story."""
    receipts = _story_receipts(conn, window.start, window.end)
    category_data = _story_category_data(conn, window)
    items = _story_item_candidates(conn, window, summary, comparison)
    insight = _story_insight(conn, window, summary, comparison, receipts, category_data, items)
    evidence_ids = [event["id"] for event in insight["evidence_events"]]
    highlights = _story_highlights(receipts, evidence_ids)
    highlighted_ids = {receipt["id"] for receipt in highlights}
    remainder = [receipt for receipt in receipts if receipt["id"] not in highlighted_ids]
    actual_dates = [receipt["date"] for receipt in receipts if receipt["date"]]
    metric_bucket = (
        round(float(insight["metric_value"]) / 5) * 5
        if insight["metric_unit"] == "EUR"
        else round(float(insight["metric_value"]) / 5) * 5
    )
    signature_source = "|".join([
        insight["type"], str(insight["subject_key"]), str(metric_bucket),
        ",".join(str(receipt_id) for receipt_id in sorted(evidence_ids)),
        str(receipts[-1]["id"] if receipts else 0),
    ])
    return {
        "month": {
            "key": window.key, "label": window.label,
            "display_label": (
                f"{MONTH_NAMES_RU[window.start.month]} {window.start.year}"
                if window.start else window.label
            ),
            "start": window.start.isoformat() if window.start else None,
            "end": (window.end - timedelta(days=1)).isoformat(),
        },
        "total": summary["spend"],
        "receipt_count": summary["receipt_count"],
        "actual_period": {
            "start": min(actual_dates) if actual_dates else None,
            "end": max(actual_dates) if actual_dates else None,
        },
        "timeline_events": _story_timeline(receipts),
        "highlighted_receipts": highlights,
        "grouped_remainder": {
            "count": len(remainder),
            "total": round(sum(receipt["total"] for receipt in remainder), 2),
            "receipt_ids": [receipt["id"] for receipt in remainder],
        },
        "insight": insight,
        "story_signature": sha256(signature_source.encode("utf-8")).hexdigest(),
    }


def _product_group_health(conn) -> tuple[int, int]:
    rows = conn.execute(
        "SELECT name, normalized_name, canonical_name, category FROM items"
    ).fetchall()
    groups = {}
    for name, normalized_name, canonical_name, category in rows:
        key = get_product_key(name or "", normalized_name, canonical_name)
        groups.setdefault(key, set()).add(category_for_reporting(category))
    conflicts = sum(len(categories) > 1 for categories in groups.values())
    unresolved = sum(UNRESOLVED_CATEGORY in categories for categories in groups.values())
    return conflicts, unresolved


def rank_action_queue(candidates: list[dict], limit: int = 5) -> list[dict]:
    visible = [
        item for item in candidates
        if item.get("key") != "no_manual_rule" and int(item.get("count") or 0) > 0
    ]
    visible.sort(key=lambda item: (item.get("priority", 99), -int(item.get("count") or 0)))
    return visible[:limit]


def _operations(conn) -> tuple[list[dict], dict]:
    conflicts, unresolved = _product_group_health(conn)
    price_row = conn.execute(
        """
        SELECT COUNT(*),
               SUM(normalized_unit_price IS NOT NULL
                   AND normalized_price_unit IS NOT NULL
                   AND normalized_price_unit != 'unknown'),
               SUM(price_parse_confidence IS NULL OR price_parse_confidence < 0.75),
               SUM(normalized_unit_price > 10000 OR normalized_unit_price <= 0)
        FROM items
        """
    ).fetchone()
    item_count = int(price_row[0] or 0)
    normalized_count = int(price_row[1] or 0)
    low_confidence = int(price_row[2] or 0)
    suspicious = int(price_row[3] or 0)
    suggestions = find_similar_products(conn, limit=200)
    merge_count = sum(item["confidence"] == "high" for item in suggestions)
    queue = rank_action_queue([
        {
            "key": "category_conflicts", "priority": 1, "count": conflicts,
            "severity": "critical", "severity_label": "Критично", "title": "Конфликты категорий",
            "explanation": "Один товар попал в несколько категорий.",
            "href": "/products/review?filter=conflict&sort=conflicts",
            "action": "Разобрать",
        },
        {
            "key": "low_confidence_prices", "priority": 2, "count": low_confidence,
            "severity": "high", "severity_label": "Высокий", "title": "Низкая уверенность цены",
            "explanation": "Парсер не подтвердил цену с достаточной уверенностью.",
            "href": "/data-quality/prices?filter=low_confidence", "action": "Проверить",
        },
        {
            "key": "suspicious_prices", "priority": 2.1, "count": suspicious,
            "severity": "high", "severity_label": "Высокий", "title": "Подозрительные цены",
            "explanation": "Нормализованная цена вышла за допустимый диапазон.",
            "href": "/data-quality/prices?filter=suspicious", "action": "Проверить",
        },
        {
            "key": "merge_suggestions", "priority": 4, "count": merge_count,
            "severity": "medium", "severity_label": "Средний", "title": "Надёжные совпадения товаров",
            "explanation": "Похожие позиции можно объединить без ручного поиска.",
            "href": "/products/suggestions?confidence=high", "action": "Сравнить",
        },
        {
            "key": "uncategorized", "priority": 5, "count": unresolved,
            "severity": "low", "severity_label": "Низкий", "title": "Требуют категоризации",
            "explanation": "Группы товаров остаются в категории «прочее / требует решения».",
            "href": "/products/review?filter=other", "action": "Назначить",
        },
    ])
    coverage = round(normalized_count / item_count * 100, 1) if item_count else 0.0
    health = {
        "normalized": {
            "value": coverage, "count": normalized_count, "total": item_count,
            "href": "/data-quality/prices", "label": "Нормализация цен",
        },
        "unresolved_categories": {
            "value": unresolved, "href": "/products/review?filter=other",
            "label": "Требуют категории",
        },
        "low_confidence_prices": {
            "value": low_confidence, "href": "/data-quality/prices?filter=low_confidence",
            "label": "Низкая уверенность цены",
        },
        "merge_suggestions": {
            "value": merge_count, "href": "/products/suggestions?confidence=high",
            "label": "Надёжные совпадения",
        },
    }
    return queue, health


def get_dashboard_data(
    period_key: str = "current_month", *, as_of: date | None = None
) -> dict:
    as_of = as_of or date.today()
    window = resolve_period(period_key, as_of)
    with get_connection() as conn:
        summary = _summary(conn, window.start, window.end)
        comparison = None
        if window.previous_end is not None:
            previous = _summary(conn, window.previous_start, window.previous_end)
            absolute_delta = round(summary["spend"] - previous["spend"], 2)
            percentage_delta = (
                round(absolute_delta / previous["spend"] * 100, 1)
                if previous["spend"]
                else None
            )
            comparison = {
                "previous_spend": previous["spend"],
                "previous_receipt_count": previous["receipt_count"],
                "absolute_delta": absolute_delta,
                "percentage_delta": percentage_delta,
            }

        forecast = None
        if window.key == "current_month" and as_of.day >= 7 and summary["receipt_count"] >= 3:
            days_in_month = monthrange(as_of.year, as_of.month)[1]
            forecast = {
                "amount": round(summary["spend"] / as_of.day * days_in_month, 2),
                "elapsed_days": as_of.day,
                "days_in_month": days_in_month,
            }

        category_changes = _category_changes(conn, window)
        action_queue, data_health = _operations(conn)
        recent_receipts = _receipt_rows(conn, window, limit=5)
        receipt_month = _receipt_month_summary(conn, as_of, window)
        trend = _trend(conn, window)
        briefing = build_briefing(
            window, summary, comparison, category_changes, action_queue
        )
        month_story = build_month_story(conn, window, summary, comparison)

    return {
        "period": window,
        "analytics_start": window.start.isoformat() if window.start else None,
        "analytics_end": (window.end - timedelta(days=1)).isoformat(),
        "summary": summary,
        "comparison": comparison,
        "forecast": forecast,
        "trend": trend,
        "category_changes": category_changes,
        "insight": _insight(summary, comparison, category_changes),
        "recent_receipts": recent_receipts,
        "receipt_month": receipt_month,
        "action_queue": action_queue,
        "data_health": data_health,
        "briefing": briefing,
        "month_story": month_story,
    }

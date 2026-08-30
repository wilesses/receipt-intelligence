from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import sqlite3

from app.price_deviation import BLOCKING_PRICE_WARNINGS, is_eligible_price_observation
from app.price_model import (
    MANUAL_CORRECTION_CONFIDENCE,
    MAX_REASONABLE_NORMALIZED_PRICE,
    derive_price_data,
)


EDITABLE_QUANTITY_UNITS = frozenset({"piece", "kg", "g", "l", "ml"})
EDITABLE_PACKAGE_UNITS = frozenset({"g", "ml", "piece", "unknown"})


class CorrectionError(ValueError):
    pass


def _number(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _current_model(row):
    return derive_price_data(
        name=row.get("name") or "",
        normalized_name=row.get("normalized_name"),
        quantity=row.get("quantity"),
        line_total=row.get("line_total"),
        unit_price=row.get("unit_price"),
        quantity_unit=row.get("quantity_unit"),
        package_size=row.get("package_size"),
        package_unit=row.get("package_unit"),
        source=row.get("price_parse_source") or "derived",
    )


def classify_price_correction(row):
    if is_eligible_price_observation(row):
        return {"classification": "ALREADY_SAFE", "reason": "Уже пригодно для сравнения цен"}

    quantity = _number(row.get("quantity"))
    line_total = _number(row.get("line_total"))
    unit_price = _number(row.get("unit_price"))
    if quantity is None or quantity <= 0:
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Количество требует parser-level correction"}
    if line_total is None or line_total <= 0:
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Итог строки требует проверки исходного чека"}
    if unit_price is not None and abs(quantity * unit_price - line_total) > Decimal("0.02"):
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Арифметика цены требует parser-level correction"}

    warnings = set(_current_model(row).warnings)
    if "parser_contamination" in warnings:
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Parser contamination требует проверки исходного чека"}
    if "multipack_unresolved" in warnings:
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Неоднозначный multipack"}
    if "service_line" in warnings:
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Служебная строка не корректируется как товар"}
    confidence = _number(row.get("price_parse_confidence"))
    if confidence is not None and confidence > Decimal(str(MANUAL_CORRECTION_CONFIDENCE)):
        return {"classification": "NOT_CORRECTABLE_V1", "reason": "Существующее evidence сильнее ручной коррекции"}
    return {"classification": "CORRECTABLE_V1", "reason": None}


def _validated_proposal(proposed):
    quantity_unit = str(proposed.get("quantity_unit") or "").strip()
    package_unit = str(proposed.get("package_unit") or "unknown").strip()
    if quantity_unit not in EDITABLE_QUANTITY_UNITS:
        raise CorrectionError("Выберите поддерживаемую единицу количества")
    if package_unit not in EDITABLE_PACKAGE_UNITS:
        raise CorrectionError("Выберите поддерживаемую единицу упаковки")

    raw_size = proposed.get("package_size")
    package_size = None if raw_size is None or str(raw_size).strip() == "" else _number(raw_size)
    if package_size is not None and package_size <= 0:
        raise CorrectionError("Укажите положительный размер упаковки")
    if raw_size not in (None, "") and package_size is None:
        raise CorrectionError("Укажите числовой размер упаковки")
    if (package_size is None) != (package_unit == "unknown"):
        raise CorrectionError("Размер и единица упаковки должны быть указаны вместе")
    if quantity_unit != "piece" and package_size is not None:
        raise CorrectionError("Для весовой или объёмной единицы упаковка не задаётся")
    if package_size is not None:
        maximum = Decimal("1000") if package_unit == "piece" else Decimal("20000")
        if package_size > maximum:
            raise CorrectionError("Размер упаковки выходит за допустимый диапазон")
        if package_unit == "piece" and package_size != package_size.to_integral_value():
            raise CorrectionError("Количество штук в упаковке должно быть целым")

    return {
        "quantity_unit": quantity_unit,
        "package_size": float(package_size) if package_size is not None else None,
        "package_unit": package_unit,
    }


def build_correction_preview(row, proposed):
    policy = classify_price_correction(row)
    if policy["classification"] != "CORRECTABLE_V1":
        raise CorrectionError(policy["reason"])
    fields = _validated_proposal(proposed)
    projected = derive_price_data(
        name=row.get("name") or "",
        normalized_name=row.get("normalized_name"),
        quantity=row.get("quantity"),
        line_total=row.get("line_total"),
        unit_price=row.get("unit_price"),
        source="manual_correction",
        **fields,
    )
    warnings = BLOCKING_PRICE_WARNINGS.intersection(projected.warnings)
    if "multipack_unresolved" in warnings:
        raise CorrectionError("Неоднозначный multipack нельзя исправить в v1")
    if "parser_contamination" in warnings:
        raise CorrectionError("Parser contamination нельзя исправить в v1")
    if warnings.intersection({
        "age_package_ambiguous",
        "ambiguous_package_size",
        "invalid_package_size",
        "weighted_measurement_ambiguous",
    }):
        raise CorrectionError("Неоднозначное измерение не устранено structured evidence")
    if warnings:
        raise CorrectionError("После коррекции остаётся блокирующая диагностика")
    normalized = projected.normalized_unit_price
    if normalized is None or not math.isfinite(normalized) or not 0 < normalized <= MAX_REASONABLE_NORMALIZED_PRICE:
        raise CorrectionError("Нормализованная цена не прошла проверку диапазона")

    after = {
        "unit_price": projected.unit_price,
        "quantity_unit": projected.quantity_unit,
        "package_size": projected.package_size,
        "package_unit": projected.package_unit,
        "normalized_unit_price": projected.normalized_unit_price,
        "normalized_price_unit": projected.normalized_price_unit,
        "price_parse_source": projected.source,
        "price_parse_confidence": projected.confidence,
        "warnings": projected.warnings,
    }
    projected_row = dict(row)
    projected_row.update(after)
    return {
        "before": dict(row),
        "proposed": fields,
        "after": after,
        "eligible_before": is_eligible_price_observation(row),
        "eligible_after": is_eligible_price_observation(projected_row),
    }


ITEM_STATE_FIELDS = (
    "id", "receipt_id", "name", "canonical_name", "normalized_name",
    "quantity", "price", "line_total", "unit_price", "quantity_unit",
    "package_size", "package_unit", "normalized_unit_price",
    "normalized_price_unit", "price_parse_source", "price_parse_confidence",
    "category", "category_source",
)
DERIVED_FIELDS = (
    "unit_price", "quantity_unit", "package_size", "package_unit",
    "normalized_unit_price", "normalized_price_unit", "price_parse_source",
    "price_parse_confidence",
)


class StaleCorrectionError(CorrectionError):
    pass


def before_state_hash(row):
    values = [row.get(field) for field in ITEM_STATE_FIELDS]
    serialized = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def correction_token_payload(preview):
    return {
        "item_id": preview["before"]["id"],
        "before_state_hash": before_state_hash(preview["before"]),
        "proposed": preview["proposed"],
        "projected": {field: preview["after"][field] for field in DERIVED_FIELDS},
    }


def apply_price_correction(conn, item_id, token_payload, posted_proposed):
    try:
        token_item_id = int(token_payload["item_id"])
        token_hash = token_payload["before_state_hash"]
        token_proposed = token_payload["proposed"]
        token_projected = token_payload["projected"]
    except (KeyError, TypeError, ValueError) as exc:
        raise StaleCorrectionError("Предпросмотр недействителен; создайте новый") from exc
    if token_item_id != item_id:
        raise StaleCorrectionError("Предпросмотр относится к другой строке")

    conn.execute("BEGIN IMMEDIATE")
    conn.row_factory = sqlite3.Row
    stored = conn.execute(
        """
        SELECT items.*, receipts.store, receipts.date
        FROM items JOIN receipts ON receipts.id = items.receipt_id
        WHERE items.id = ?
        """,
        (item_id,),
    ).fetchone()
    if stored is None:
        raise StaleCorrectionError("Строка больше не существует")
    current = dict(stored)
    if before_state_hash(current) != token_hash:
        raise StaleCorrectionError("Данные изменились после предпросмотра; создайте новый")

    recalculated = build_correction_preview(current, posted_proposed)
    if recalculated["proposed"] != token_proposed:
        raise StaleCorrectionError("Поля исправления отличаются от предпросмотра")
    projected = {field: recalculated["after"][field] for field in DERIVED_FIELDS}
    if projected != token_projected:
        raise StaleCorrectionError("Результат модели изменился; создайте новый предпросмотр")

    set_clause = ", ".join(f"{field} = ?" for field in DERIVED_FIELDS)
    stale_clause = " AND ".join(f"{field} IS ?" for field in ITEM_STATE_FIELDS)
    cursor = conn.execute(
        f"UPDATE items SET {set_clause} WHERE id = ? AND {stale_clause}",
        (
            *(projected[field] for field in DERIVED_FIELDS),
            item_id,
            *(current.get(field) for field in ITEM_STATE_FIELDS),
        ),
    )
    if cursor.rowcount != 1:
        raise StaleCorrectionError("Данные изменились во время применения; создайте новый предпросмотр")
    return recalculated

from datetime import date
import re
from statistics import median
from urllib.parse import parse_qsl, unquote, urlsplit

from flask import flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from app.analytics_service import get_analytics_data, get_item_trend
from app.category_keywords import CANONICAL_CATEGORIES, SOURCE_LABELS, normalize_category_name
from app.category_rules import (
    apply_category_to_product_key,
    get_product_key,
    upsert_category_rule,
)
from app.config import UPLOAD_DIR, ensure_data_dirs
from app.dashboard_service import (
    get_available_receipt_months,
    get_dashboard_data,
    get_period_receipts,
    resolve_story_month,
)
from app.db import get_connection, get_items_by_receipt
from app.gmail_fetcher import fetch_pdf_attachments, gmail_settings
from app.importer import process_pdf_api
from app.product_matcher import find_similar_products


ALLOWED_EXTENSIONS = {"pdf"}
DEFAULT_CATEGORY = "прочее"
PRODUCT_NAME_EXPR = "COALESCE(NULLIF(items.canonical_name, ''), items.name)"
PRICE_UNIT_LABELS = {"eur_per_l": "€/L", "eur_per_kg": "€/kg", "eur_per_piece": "€/шт."}
RECEIPT_RETURN_PERIODS = {
    "current_month",
    "previous_month",
    "last_30_days",
    "all_time",
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_category_options(conn=None):
    return list(CANONICAL_CATEGORIES)


def source_label(source):
    return SOURCE_LABELS.get(source or "rule", source or "rule")


def _safe_receipt_return_path(raw_path):
    fallback = url_for("index", view="receipts")
    if not raw_path:
        return fallback

    parsed = urlsplit(raw_path)
    if parsed.scheme or parsed.netloc or parsed.path != "/" or parsed.fragment:
        return fallback

    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key not in {"view", "period", "store_search"} for key, _ in pairs):
        return fallback
    params = dict(pairs)
    if params.get("view") != "receipts":
        return fallback

    period = params.get("period", "current_month")
    if (
        period not in RECEIPT_RETURN_PERIODS
        and not re.fullmatch(r"month:\d{4}-(0[1-9]|1[0-2])", period)
    ):
        return fallback

    target = {"view": "receipts", "period": period}
    store_search = params.get("store_search", "").strip()
    if store_search:
        target["store_search"] = store_search[:120]
    return url_for("index", **target)


def _item_requires_review(price_parse_confidence, normalized_unit_price):
    return (
        price_parse_confidence is None
        or float(price_parse_confidence) < 0.75
        or (
            normalized_unit_price is not None
            and (
                float(normalized_unit_price) > 10000
                or float(normalized_unit_price) <= 0
            )
        )
    )


def _review_groups(conn, query=""):
    params = []
    where = ""
    if query:
        where = f"""
            WHERE ({PRODUCT_NAME_EXPR} LIKE ?
               OR items.name LIKE ?
               OR items.normalized_name LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]

    rows = conn.execute(f"""
        SELECT items.id, items.name, items.normalized_name, items.canonical_name,
               {PRODUCT_NAME_EXPR} AS display_name,
               items.category, items.category_source,
               receipts.id AS receipt_id, receipts.date, receipts.store
        FROM items
        JOIN receipts ON receipts.id = items.receipt_id
        {where}
    """, params).fetchall()

    rule_keys = {
        row[0]
        for row in conn.execute("SELECT product_key FROM product_category_rules").fetchall()
    }

    groups = {}
    for row in rows:
        item_id, name, normalized_name, canonical_name, display_name, category, category_source, receipt_id, date, store = row
        product_key = get_product_key(name or "", normalized_name, canonical_name)
        group = groups.setdefault(product_key, {
            "product_key": product_key,
            "display_name": display_name or name,
            "aliases": set(),
            "item_count": 0,
            "receipt_ids": set(),
            "categories": set(),
            "sources": set(),
            "last_date": "",
            "stores": set(),
            "normalized_name": normalized_name or "",
            "has_canonical_name": False,
            "has_rule": product_key in rule_keys,
            "has_empty_category": False,
            "has_empty_normalized_name": False,
        })

        group["aliases"].add(name or "")
        group["item_count"] += 1
        group["receipt_ids"].add(receipt_id)
        normalized_category = normalize_category_name(category)
        group["categories"].add(normalized_category)
        group["sources"].add(category_source or "rule")
        group["last_date"] = max(group["last_date"], date or "")
        if store:
            group["stores"].add(store)
        if canonical_name:
            group["has_canonical_name"] = True
        if not normalized_name:
            group["has_empty_normalized_name"] = True
        if not category or not str(category).strip():
            group["has_empty_category"] = True

    result = []
    for group in groups.values():
        categories = sorted(group["categories"])
        sources = sorted(group["sources"])
        problems = []
        if "прочее" in categories:
            problems.append("Прочее")
        if "fallback" in sources:
            problems.append("Fallback")
        if len(categories) > 1:
            problems.append("Конфликт категорий")
        if "manual" in sources and "rule" in sources:
            problems.append("Manual + rule")
        if group["has_empty_normalized_name"]:
            problems.append("Нет normalized_name")
        if not group["has_rule"]:
            problems.append("Нет ручного правила")
        if group["has_empty_category"]:
            problems.append("Пустая категория")

        if not problems:
            continue

        result.append({
            **group,
            "aliases": sorted(alias for alias in group["aliases"] if alias),
            "receipt_count": len(group["receipt_ids"]),
            "categories": categories,
            "sources": sources,
            "source_labels": [source_label(source) for source in sources],
            "stores": sorted(group["stores"]),
            "problems": problems,
            "conflict_count": max(0, len(categories) - 1),
            "category": categories[0] if len(categories) == 1 else DEFAULT_CATEGORY,
        })

    return result


def build_price_evaluation(rows):
    normalized_by_unit = {}
    legacy_prices = []
    for row in rows:
        quantity = float(row[2] or 0)
        price = float(row[3] or 0)
        normalized_price = row[10] if len(row) > 10 else None
        normalized_unit = row[11] if len(row) > 11 else None
        if normalized_price and normalized_unit and normalized_unit != "unknown":
            normalized_by_unit.setdefault(normalized_unit, []).append(float(normalized_price))
        if quantity > 0 and price > 0:
            legacy_prices.append(price / quantity)

    comparison_source = "legacy comparison"
    comparison_label = "legacy comparison"
    unit_prices = legacy_prices
    for normalized_unit, values in normalized_by_unit.items():
        if len(values) >= 3:
            unit_prices = values
            comparison_source = normalized_unit
            comparison_label = f"по {PRICE_UNIT_LABELS.get(normalized_unit, normalized_unit)}"
            break

    if len(unit_prices) < 3:
        return {"has_enough_data": False}

    average_price = sum(unit_prices) / len(unit_prices)
    median_price = median(unit_prices)
    min_price = min(unit_prices)
    max_price = max(unit_prices)
    last_price = unit_prices[-1]

    if median_price and last_price <= median_price * 0.9:
        status = "🔥 Выгодная цена"
    elif median_price and last_price >= median_price * 1.15:
        status = "⚠️ Дороже обычного"
    else:
        status = "Обычная цена"

    return {
        "has_enough_data": True,
        "average_price": round(average_price, 2),
        "median_price": round(median_price, 2),
        "min_price": round(min_price, 2),
        "max_price": round(max_price, 2),
        "last_price": round(last_price, 2),
        "status": status,
        "comparison_source": comparison_source,
        "comparison_label": comparison_label,
        "average_deviation": round(((last_price - average_price) / average_price) * 100, 1) if average_price else 0,
        "median_deviation": round(((last_price - median_price) / median_price) * 100, 1) if median_price else 0,
    }


def build_receipt_price_analysis(conn, receipt_items):
    histories = {}
    for item in receipt_items:
        name = item.get("display_name") or item["name"]
        if name in histories:
            continue

        rows = conn.execute(f"""
            SELECT quantity, price, normalized_unit_price, normalized_price_unit
            FROM items
            WHERE {PRODUCT_NAME_EXPR} = ?
              AND quantity > 0
              AND price > 0
            ORDER BY id
        """, (name,)).fetchall()

        by_unit = {}
        legacy = []
        for quantity, price, normalized_price, normalized_unit in rows:
            if normalized_price and normalized_unit and normalized_unit != "unknown":
                by_unit.setdefault(normalized_unit, []).append(float(normalized_price))
            if quantity and price:
                legacy.append(float(price) / float(quantity))
        histories[name] = {"by_unit": by_unit, "legacy": legacy}

    summary = {
        "total_items": len(receipt_items),
        "cheap": 0,
        "expensive": 0,
        "insufficient": 0,
    }

    for item in receipt_items:
        quantity = float(item["quantity"] or 0)
        price = float(item["price"] or 0)
        history = histories.get(item.get("display_name") or item["name"], {"by_unit": {}, "legacy": []})
        normalized_unit = item.get("normalized_price_unit")
        normalized_price = item.get("normalized_unit_price")
        if normalized_price and normalized_unit and normalized_unit != "unknown":
            unit_prices = history["by_unit"].get(normalized_unit, [])
            current_price = float(normalized_price)
            basis = normalized_unit
        else:
            unit_prices = history["legacy"]
            current_price = price / quantity if quantity else 0
            basis = "legacy"

        if quantity <= 0 or price <= 0 or len(unit_prices) < 3:
            item["price_status"] = None
            summary["insufficient"] += 1
            continue

        median_price = median(unit_prices)
        deviation = ((current_price - median_price) / median_price) * 100 if median_price else 0

        if current_price <= median_price * 0.9:
            label = "🟢 Выгодно"
            kind = "cheap"
            summary["cheap"] += 1
        elif current_price >= median_price * 1.15:
            label = "🔴 Дорого"
            kind = "expensive"
            summary["expensive"] += 1
        else:
            label = "🟡 Обычная цена"
            kind = "normal"

        item["price_status"] = {
            "label": label,
            "kind": kind,
            "current_price": round(current_price, 2),
            "median_price": round(median_price, 2),
            "basis": basis,
            "deviation": round(deviation, 1),
            "tooltip": (
                f"Текущая цена: {current_price:.2f} €\n"
                f"Медианная цена: {median_price:.2f} €\n"
                f"Сравнение: {basis}\n"
                f"Отклонение: {deviation:+.1f}%"
            ),
        }

    return summary


def init_routes(app):
    @app.route("/")
    def index():
        if "story_mode" in request.args:
            canonical_args = request.args.to_dict(flat=True)
            canonical_args.pop("story_mode", None)
            return redirect(url_for("index", **canonical_args))

        period = request.args.get("period", "current_month").strip() or "current_month"
        view = request.args.get("view", "overview").strip() or "overview"
        store_search = request.args.get("store_search", "").strip()
        story_debug = request.args.get("story_debug") == "1"
        available_story_months = get_available_receipt_months()
        selected_story_month = resolve_story_month(
            request.args.get("month", "").strip() or None,
            available_story_months,
        )
        story_period = (
            "current_month"
            if selected_story_month == date.today().strftime("%Y-%m")
            else f"month:{selected_story_month}"
        )
        dashboard_period = (
            story_period
            if view != "receipts"
            else period
        )
        dashboard = get_dashboard_data(dashboard_period)
        receipts = get_period_receipts(dashboard["period"], store_search)
        return render_template(
            "index.html",
            dashboard=dashboard,
            period=dashboard["period"].key,
            view=view,
            store_search=store_search,
            receipts=receipts,
            story_presentation="cinematic",
            story_debug=story_debug,
            available_story_months=available_story_months,
            selected_story_month=selected_story_month,
            story_period=story_period,
        )

    @app.route("/receipt/<int:receipt_id>")
    def view_receipt(receipt_id):
        items = []
        item_total_sum = 0.0

        with get_connection() as conn:
            receipt_row = conn.execute(
                """
                SELECT id, date, store, total, receipt_number
                FROM receipts
                WHERE id = ?
                """,
                (receipt_id,),
            ).fetchone()
            if receipt_row is None:
                return render_template(
                    "receipt.html",
                    receipt=None,
                    receipt_id=receipt_id,
                    return_path=_safe_receipt_return_path(request.args.get("return_to")),
                ), 404

            rows = conn.execute(f"""
                SELECT id, name, quantity, price, category, category_source,
                       normalized_unit_price, normalized_price_unit, line_total, unit_price,
                       package_size, package_unit, {PRODUCT_NAME_EXPR} AS display_name,
                       price_parse_confidence
                FROM items
                WHERE receipt_id = ?
                ORDER BY id
            """, (receipt_id,)).fetchall()

            for item_id, name, quantity, price, category, category_source, normalized_unit_price, normalized_price_unit, line_total, unit_price, package_size, package_unit, display_name, price_parse_confidence in rows:
                quantity = float(quantity or 0)
                price = float(price or 0)
                item_total_sum += price
                items.append({
                    "id": item_id,
                    "name": name,
                    "quantity": quantity,
                    "quantity_display": f"{quantity:g}",
                    "price": price,
                    "category": normalize_category_name(category),
                    "category_source": category_source or "rule",
                    "category_source_label": source_label(category_source),
                    "normalized_unit_price": normalized_unit_price,
                    "normalized_price_unit": normalized_price_unit,
                    "line_total": line_total,
                    "unit_price": unit_price,
                    "package_size": package_size,
                    "package_unit": package_unit,
                    "display_name": display_name or name,
                    "price_parse_confidence": price_parse_confidence,
                    "needs_review": _item_requires_review(
                        price_parse_confidence,
                        normalized_unit_price,
                    ),
                })

            receipt_summary = build_receipt_price_analysis(conn, items)
            category_options = get_category_options(conn)
            receipt = {
                "id": int(receipt_row[0]),
                "date": receipt_row[1],
                "store": receipt_row[2],
                "total": round(float(receipt_row[3] or 0), 2),
                "receipt_number": receipt_row[4],
            }

        return render_template(
            "receipt.html",
            receipt=receipt,
            items=items,
            receipt_id=receipt_id,
            total_sum=receipt["total"],
            item_total_sum=round(item_total_sum, 2),
            receipt_summary=receipt_summary,
            review_count=sum(1 for item in items if item["needs_review"]),
            category_options=category_options,
            category_updated=request.args.get("category_updated") == "1",
            return_path=_safe_receipt_return_path(request.args.get("return_to")),
        )

    @app.route("/item/<int:item_id>/category", methods=["POST"])
    def update_item_category(item_id):
        new_category = request.form.get("new_category", "").strip()
        category = normalize_category_name(new_category or request.form.get("category"))
        scope = request.form.get("category_scope", "product")

        with get_connection() as conn:
            row = conn.execute("""
                SELECT id, name, normalized_name, canonical_name
                FROM items
                WHERE id = ?
            """, (item_id,)).fetchone()
            if not row:
                flash("Позиция не найдена")
                return redirect(request.referrer or url_for("index"))

            if scope == "item":
                conn.execute(
                    "UPDATE items SET category = ?, category_source = 'manual' WHERE id = ?",
                    (category, item_id),
                )
                flash("Категория обновлена только для этой позиции")
            else:
                product_key = get_product_key(row[1] or "", row[2], row[3])
                upsert_category_rule(conn, product_key, category)
                updated_count = apply_category_to_product_key(conn, product_key, category)
                flash(f"Категория обновлена для {updated_count} позиций товара")
            conn.commit()

        target = request.referrer or url_for("index")
        separator = "&" if "?" in target else "?"
        return redirect(f"{target}{separator}category_updated=1")

    @app.route("/upload", methods=["GET", "POST"])
    def upload():
        if request.method == "GET":
            return render_template("upload.html")

        if "pdfs" not in request.files:
            return jsonify({"status": "error", "message": "Нет файлов"}), 400

        ensure_data_dirs()
        uploaded = []
        errors = []

        for file in request.files.getlist("pdfs"):
            if not file or not allowed_file(file.filename):
                errors.append({
                    "file": getattr(file, "filename", ""),
                    "error": "Недопустимый формат. Можно загружать только PDF.",
                })
                continue

            filename = secure_filename(file.filename)
            file_path = UPLOAD_DIR / filename

            try:
                file.save(file_path)
                result = process_pdf_api(file_path)
                if result["status"] == "ok":
                    uploaded.append({"file": filename, "message": result.get("message", "")})
                else:
                    errors.append({"file": filename, "error": result.get("error", "Ошибка при обработке")})
            except Exception as exc:
                errors.append({"file": filename, "error": str(exc)})

        return jsonify({"status": "ok", "uploaded": uploaded, "errors": errors})

    @app.route("/gmail/fetch", methods=["POST"])
    def gmail_fetch():
        try:
            result = fetch_pdf_attachments()
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

        imported = []
        errors = []
        skipped = list(result.skipped_files)
        settings = gmail_settings()
        import_paths = list(result.files_saved)
        if settings["import_existing"]:
            import_paths.extend(result.files_existing)
        else:
            skipped.extend(f"{path.name} уже скачан" for path in result.files_existing)

        print(f"Gmail: PDF к импорту: {len(import_paths)}", flush=True)

        for index, file_path in enumerate(import_paths, 1):
            print(f"Gmail: импорт PDF {index}/{len(import_paths)}: {file_path.name}", flush=True)
            receipt_number = file_path.stem
            with get_connection() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM receipts WHERE receipt_number = ?",
                    (receipt_number,),
                ).fetchone()
            if exists:
                skipped.append(f"{file_path.name} уже есть в базе")
                print(f"Gmail: пропуск дубликата {file_path.name}", flush=True)
                continue

            import_result = process_pdf_api(file_path)
            if import_result["status"] == "ok":
                imported.append({
                    "file": file_path.name,
                    "message": import_result.get("message", ""),
                })
            else:
                errors.append({
                    "file": file_path.name,
                    "error": import_result.get("error", "Ошибка при обработке"),
                })

        return jsonify({
            "status": "ok",
            "emails_checked": result.emails_checked,
            "emails_matched": result.emails_matched,
            "files_saved": [path.name for path in result.files_saved],
            "files_existing": [path.name for path in result.files_existing],
            "skipped_files": skipped,
            "imported": imported,
            "errors": errors,
        })

    @app.route("/analytics")
    def analytics():
        return render_template("analytics.html", category_options=get_category_options())

    @app.route("/analytics/data")
    def analytics_data():
        return jsonify(get_analytics_data(
            start=request.args.get("start"),
            end=request.args.get("end"),
            store=request.args.get("store"),
            category=request.args.get("category"),
            item=request.args.get("item"),
        ))

    @app.route("/analytics/item_trend")
    def item_trend():
        item = request.args.get("item", "").strip()
        if not item:
            return jsonify({"labels": [], "values": []})
        return jsonify(get_item_trend(item))

    @app.route("/autocomplete/item_names")
    def autocomplete_item_names():
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify([])

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT DISTINCT {PRODUCT_NAME_EXPR} AS product_name
                FROM items
                WHERE ({PRODUCT_NAME_EXPR} LIKE ? OR items.name LIKE ?)
                ORDER BY LOWER({PRODUCT_NAME_EXPR})
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            names = [row[0] for row in cursor.fetchall()]

        return jsonify(names)

    @app.route("/products/merge", methods=["GET"])
    def products_merge():
        query = request.args.get("q", "").strip()
        merged_count = request.args.get("merged")
        params = []
        where_clause = ""
        if query:
            where_clause = f"""
                WHERE ({PRODUCT_NAME_EXPR} LIKE ?
                   OR items.name LIKE ?
                   OR items.canonical_name LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%", f"%{query}%"]

        with get_connection() as conn:
            products = conn.execute(f"""
                SELECT {PRODUCT_NAME_EXPR} AS product_name,
                       COUNT(*) AS item_count,
                       COUNT(DISTINCT receipt_id) AS receipt_count,
                       GROUP_CONCAT(DISTINCT NULLIF(canonical_name, '')) AS canonical_names
                FROM items
                {where_clause}
                GROUP BY product_name
                ORDER BY LOWER({PRODUCT_NAME_EXPR})
                LIMIT 200
            """, params).fetchall()

        return render_template(
            "products_merge.html",
            products=products,
            query=query,
            merged_count=merged_count,
        )

    @app.route("/products/merge", methods=["POST"])
    def products_merge_submit():
        selected_names = [
            name.strip()
            for name in request.form.getlist("selected_names")
            if name.strip()
        ]
        canonical_name = request.form.get("canonical_name", "").strip()
        query = request.form.get("q", "").strip()
        updated_count = 0

        if selected_names and canonical_name:
            placeholders = ",".join("?" for _ in selected_names)
            params = [
                canonical_name,
                *selected_names,
                *selected_names,
                *selected_names,
            ]
            with get_connection() as conn:
                cursor = conn.execute(f"""
                    UPDATE items
                    SET canonical_name = ?
                    WHERE name IN ({placeholders})
                       OR canonical_name IN ({placeholders})
                       OR {PRODUCT_NAME_EXPR} IN ({placeholders})
                """, params)
                conn.commit()
                updated_count = cursor.rowcount

        return redirect(url_for("products_merge", q=query, merged=updated_count))

    @app.route("/products/suggestions")
    def product_suggestions():
        query = request.args.get("q", "").strip()
        confidence = request.args.get("confidence", "").strip()
        try:
            limit = min(max(int(request.args.get("limit", 50)), 10), 200)
        except ValueError:
            limit = 50

        with get_connection() as conn:
            suggestions = find_similar_products(conn, query=query or None, limit=limit)

        if confidence in {"high", "possible"}:
            suggestions = [
                item for item in suggestions
                if item["confidence"] == confidence
            ]

        return render_template(
            "product_suggestions.html",
            suggestions=suggestions,
            query=query,
            confidence=confidence,
            limit=limit,
        )

    @app.route("/products/review")
    def product_review():
        query = request.args.get("q", "").strip()
        problem_filter = request.args.get("filter", "all").strip() or "all"
        sort = request.args.get("sort", "count").strip() or "count"
        try:
            limit = min(max(int(request.args.get("limit", 50)), 10), 200)
        except ValueError:
            limit = 50
        try:
            page = max(int(request.args.get("page", 1)), 1)
        except ValueError:
            page = 1

        with get_connection() as conn:
            groups = _review_groups(conn, query)

        if problem_filter == "other":
            groups = [group for group in groups if "Прочее" in group["problems"]]
        elif problem_filter == "conflict":
            groups = [group for group in groups if "Конфликт категорий" in group["problems"]]
        elif problem_filter == "no_rule":
            groups = [group for group in groups if "Нет ручного правила" in group["problems"]]
        elif problem_filter == "new":
            groups = [
                group for group in groups
                if "Нет ручного правила" in group["problems"] or "Нет normalized_name" in group["problems"]
            ]

        if sort == "conflicts":
            groups.sort(key=lambda group: (-group["conflict_count"], -group["item_count"], group["display_name"].lower()))
        elif sort == "recent":
            groups.sort(key=lambda group: (group["last_date"] or ""), reverse=True)
        elif sort == "name":
            groups.sort(key=lambda group: group["display_name"].lower())
        else:
            groups.sort(key=lambda group: (-group["item_count"], group["display_name"].lower()))

        total_count = len(groups)
        start = (page - 1) * limit
        visible_groups = groups[start:start + limit]

        return render_template(
            "product_review.html",
            groups=visible_groups,
            total_count=total_count,
            query=query,
            problem_filter=problem_filter,
            sort=sort,
            limit=limit,
            page=page,
            has_prev=page > 1,
            has_next=start + limit < total_count,
            category_options=get_category_options(),
        )

    @app.route("/products/review/category", methods=["POST"])
    def product_review_update_category():
        product_key = request.form.get("product_key", "").strip()
        category = normalize_category_name(request.form.get("category"))
        return_args = {
            "q": request.form.get("q", "").strip(),
            "filter": request.form.get("filter", "all").strip(),
            "sort": request.form.get("sort", "count").strip(),
            "limit": request.form.get("limit", "50").strip(),
            "page": request.form.get("page", "1").strip(),
        }

        if not product_key:
            flash("Товарная группа не найдена")
            return redirect(url_for("product_review", **return_args))

        with get_connection() as conn:
            upsert_category_rule(conn, product_key, category)
            updated_count = apply_category_to_product_key(conn, product_key, category)
            conn.commit()

        flash(f"Категория товара обновлена: {updated_count} позиций")
        return redirect(url_for("product_review", **return_args))

    @app.route("/data-quality/prices")
    def price_data_quality():
        issue_filter = request.args.get("filter", "all").strip() or "all"
        try:
            limit = min(max(int(request.args.get("limit", 50)), 10), 200)
        except ValueError:
            limit = 50

        with get_connection() as conn:
            summary = conn.execute("""
                SELECT COUNT(*),
                       SUM(line_total IS NOT NULL),
                       SUM(unit_price IS NOT NULL),
                       SUM(normalized_unit_price IS NOT NULL),
                       SUM(normalized_price_unit = 'eur_per_l'),
                       SUM(normalized_price_unit = 'eur_per_kg'),
                       SUM(normalized_price_unit = 'eur_per_piece'),
                       SUM(normalized_price_unit IS NULL OR normalized_price_unit = 'unknown'),
                       SUM(price_parse_confidence IS NOT NULL AND price_parse_confidence < 0.75),
                       SUM(normalized_unit_price > 10000 OR normalized_unit_price <= 0)
                FROM items
            """).fetchone()

            conditions = []
            if issue_filter == "unknown":
                conditions.append("(items.quantity_unit IS NULL OR items.quantity_unit = 'unknown')")
            elif issue_filter == "low_confidence":
                conditions.append("(items.price_parse_confidence IS NULL OR items.price_parse_confidence < 0.75)")
            elif issue_filter == "missing_package":
                conditions.append("(items.quantity_unit = 'piece' AND items.package_size IS NULL)")
            elif issue_filter == "suspicious":
                conditions.append("(items.normalized_unit_price > 10000 OR items.normalized_unit_price <= 0)")
            else:
                conditions.append("""(
                    items.line_total IS NULL OR items.unit_price IS NULL
                    OR items.normalized_price_unit IS NULL OR items.normalized_price_unit = 'unknown'
                    OR items.price_parse_confidence IS NULL OR items.price_parse_confidence < 0.75
                    OR items.normalized_unit_price > 10000 OR items.normalized_unit_price <= 0
                )""")

            rows = conn.execute(f"""
                SELECT items.name, items.receipt_id, receipts.store, receipts.date,
                       items.quantity, items.quantity_unit, items.line_total, items.unit_price,
                       items.package_size, items.package_unit, items.normalized_unit_price,
                       items.normalized_price_unit, items.price_parse_confidence
                FROM items
                JOIN receipts ON receipts.id = items.receipt_id
                WHERE {" AND ".join(conditions)}
                ORDER BY receipts.date DESC, items.id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return render_template(
            "price_data_quality.html",
            summary=summary,
            rows=rows,
            issue_filter=issue_filter,
            limit=limit,
        )

    @app.route("/item/<name>")
    def item_profile(name):
        decoded_name = unquote(name)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT receipts.date, receipts.store, items.quantity, items.price,
                       items.receipt_id, items.id, items.category, items.category_source, items.name,
                       {PRODUCT_NAME_EXPR} AS product_name,
                       items.normalized_unit_price, items.normalized_price_unit,
                       items.line_total, items.unit_price, items.package_size, items.package_unit
                FROM items
                JOIN receipts ON items.receipt_id = receipts.id
                WHERE ({PRODUCT_NAME_EXPR} = ? OR items.name = ?)
                ORDER BY receipts.date
            """, (decoded_name, decoded_name))
            rows = cursor.fetchall()

            cursor.execute(f"""
                SELECT
                    ROUND(AVG(CASE WHEN quantity > 0 THEN price / quantity ELSE NULL END), 2),
                    ROUND(MIN(CASE WHEN quantity > 0 THEN price / quantity ELSE NULL END), 2),
                    ROUND(MAX(CASE WHEN quantity > 0 THEN price / quantity ELSE NULL END), 2),
                    SUM(quantity),
                    ROUND(SUM(price), 2)
                FROM items
                WHERE ({PRODUCT_NAME_EXPR} = ? OR items.name = ?)
            """, (decoded_name, decoded_name))
            stats = cursor.fetchone()

            cursor.execute(f"""
                SELECT receipts.store, COUNT(*), ROUND(SUM(items.price), 2)
                FROM items
                JOIN receipts ON items.receipt_id = receipts.id
                WHERE ({PRODUCT_NAME_EXPR} = ? OR items.name = ?)
                GROUP BY receipts.store
            """, (decoded_name, decoded_name))
            per_store = cursor.fetchall()

            cursor.execute(f"""
                SELECT DISTINCT items.name
                FROM items
                WHERE ({PRODUCT_NAME_EXPR} = ? OR items.name = ?)
                ORDER BY LOWER(items.name)
            """, (decoded_name, decoded_name))
            aliases = [row[0] for row in cursor.fetchall()]
            category_options = get_category_options(conn)

        latest_price_model = None
        if rows:
            latest = rows[-1]
            latest_price_model = {
                "line_total": latest[12],
                "unit_price": latest[13],
                "package_size": latest[14],
                "package_unit": latest[15],
                "normalized_unit_price": latest[10],
                "normalized_price_unit": latest[11],
                "normalized_price_label": PRICE_UNIT_LABELS.get(latest[11] or "unknown", latest[11] or "unknown"),
            }

        return render_template(
            "item.html",
            name=decoded_name,
            rows=rows,
            stats=stats,
            per_store=per_store,
            price_evaluation=build_price_evaluation(rows),
            latest_price_model=latest_price_model,
            category_options=category_options,
            aliases=aliases,
        )

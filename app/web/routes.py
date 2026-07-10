from statistics import median
from urllib.parse import unquote

from flask import jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from app.analytics_service import get_analytics_data, get_item_trend
from app.config import UPLOAD_DIR, ensure_data_dirs
from app.db import get_all_receipts, get_connection, get_items_by_receipt
from app.gmail_fetcher import fetch_pdf_attachments, gmail_settings
from app.importer import process_pdf_api


ALLOWED_EXTENSIONS = {"pdf"}
DEFAULT_CATEGORY = "прочее"
PRODUCT_NAME_EXPR = "COALESCE(NULLIF(items.canonical_name, ''), items.name)"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_category_options(conn=None):
    owns_connection = conn is None
    if conn is None:
        conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT DISTINCT category
            FROM items
            WHERE category IS NOT NULL AND TRIM(category) != ''
            ORDER BY LOWER(category)
        """).fetchall()
    finally:
        if owns_connection:
            conn.close()

    categories = [row[0] for row in rows]
    if DEFAULT_CATEGORY not in categories:
        categories.append(DEFAULT_CATEGORY)
    return categories


def build_price_evaluation(rows):
    unit_prices = []
    for row in rows:
        quantity = float(row[2] or 0)
        price = float(row[3] or 0)
        if quantity > 0 and price > 0:
            unit_prices.append(price / quantity)

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
            SELECT quantity, price
            FROM items
            WHERE {PRODUCT_NAME_EXPR} = ?
              AND quantity > 0
              AND price > 0
            ORDER BY id
        """, (name,)).fetchall()

        unit_prices = [
            float(price) / float(quantity)
            for quantity, price in rows
            if quantity and price
        ]
        histories[name] = unit_prices

    summary = {
        "total_items": len(receipt_items),
        "cheap": 0,
        "expensive": 0,
        "insufficient": 0,
    }

    for item in receipt_items:
        quantity = float(item["quantity"] or 0)
        price = float(item["price"] or 0)
        unit_prices = histories.get(item.get("display_name") or item["name"], [])

        if quantity <= 0 or price <= 0 or len(unit_prices) < 3:
            item["price_status"] = None
            summary["insufficient"] += 1
            continue

        current_price = price / quantity
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
            "deviation": round(deviation, 1),
            "tooltip": (
                f"Текущая цена: {current_price:.2f} €\n"
                f"Медианная цена: {median_price:.2f} €\n"
                f"Отклонение: {deviation:+.1f}%"
            ),
        }

    return summary


def init_routes(app):
    @app.route("/")
    def index():
        receipts = get_all_receipts()
        return render_template("index.html", receipts=receipts)

    @app.route("/receipt/<int:receipt_id>")
    def view_receipt(receipt_id):
        items = []
        total_sum = 0.0

        with get_connection() as conn:
            rows = conn.execute(f"""
                SELECT id, name, quantity, price, category, {PRODUCT_NAME_EXPR} AS display_name
                FROM items
                WHERE receipt_id = ?
                ORDER BY id
            """, (receipt_id,)).fetchall()

            for item_id, name, quantity, price, category, display_name in rows:
                quantity = float(quantity or 0)
                price = float(price or 0)
                total_sum += price
                items.append({
                    "id": item_id,
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "category": category or DEFAULT_CATEGORY,
                    "display_name": display_name or name,
                })

            receipt_summary = build_receipt_price_analysis(conn, items)
            category_options = get_category_options(conn)

        return render_template(
            "receipt.html",
            items=items,
            receipt_id=receipt_id,
            total_sum=round(total_sum, 2),
            receipt_summary=receipt_summary,
            category_options=category_options,
            category_updated=request.args.get("category_updated") == "1",
        )

    @app.route("/item/<int:item_id>/category", methods=["POST"])
    def update_item_category(item_id):
        new_category = request.form.get("new_category", "").strip()
        category = new_category or request.form.get("category", "").strip() or DEFAULT_CATEGORY

        with get_connection() as conn:
            conn.execute(
                "UPDATE items SET category = ? WHERE id = ?",
                (category, item_id),
            )
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

    @app.route("/item/<name>")
    def item_profile(name):
        decoded_name = unquote(name)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT receipts.date, receipts.store, items.quantity, items.price,
                       items.receipt_id, items.id, items.category, items.name,
                       {PRODUCT_NAME_EXPR} AS product_name
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

        return render_template(
            "item.html",
            name=decoded_name,
            rows=rows,
            stats=stats,
            per_store=per_store,
            price_evaluation=build_price_evaluation(rows),
            category_options=category_options,
            aliases=aliases,
        )

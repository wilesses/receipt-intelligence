# Developer Notes

## С чего начинать чтение проекта

1. `PROJECT_GUIDE.md` - короткая пользовательская памятка.
2. `run.py` - точка запуска.
3. `app/web/app.py` - создание Flask-приложения.
4. `app/web/routes.py` - маршруты, SQL для страниц, часть расчетов.
5. `app/db.py` - схема и базовые операции с SQLite.
6. `app/importer.py` - импорт PDF, OCR, подготовка данных.
7. `app/receipt_parser.py` - парсинг текста чека.
8. `app/product_normalizer.py` - нормализация названий товаров.
9. `app/product_matcher.py` - предложения похожих товаров.
10. `app/price_model.py` - Price & Quantity Model v2.
11. `app/category_keywords.py` - canonical categories и правила категоризации.
12. `app/category_rules.py` - ручные category rules и product_key.
13. `app/analytics_service.py` - данные для графиков.
14. `app/web/templates/` - UI.

## Самые важные файлы

- `run.py` - запуск приложения.
- `app/config.py` - пути к данным, загрузкам и базе.
- `app/web/app.py` - `create_app()`, регистрация маршрутов, цвета категорий.
- `app/web/routes.py` - центральный файл веб-логики.
- `app/db.py` - схема, подключение, вставка чеков.
- `app/importer.py` - PDF/OCR/import pipeline.
- `app/receipt_parser.py` - Maxima/Rimi parsing.
- `app/product_normalizer.py` - `normalized_name` и признаки упаковки.
- `app/product_matcher.py` - RapidFuzz suggestions без автоматического merge.
- `app/price_model.py` - расчет `line_total`, `unit_price`, упаковки и normalized price.
- `app/backfill_price_data.py` - dry-run/backfill новых ценовых полей.
- `app/backfill_normalized_names.py` - безопасное заполнение `normalized_name`.
- `app/category_keywords.py` - CategoryEngine.
- `app/category_rules.py` - `product_key`, `product_category_rules`, update группы.
- `app/audit_categories.py` - read-only аудит категорий.
- `app/backfill_category_sources.py` - dry-run заметка по невозможности восстановления старых manual changes.
- `app/analytics_service.py` - агрегаты для `/analytics`.
- `app/gmail_fetcher.py` - Gmail IMAP.
- `app/web/templates/base.html` - общий layout и навигация.
- `app/web/templates/analytics.html` - клиентские графики.
- `app/web/templates/receipt.html` - детали чека.
- `app/web/templates/item.html` - профиль товара.

## Как добавить новый route

Маршруты регистрируются внутри `init_routes(app)` в `app/web/routes.py`.

Текущий паттерн:

```python
@app.route("/path")
def route_name():
    return render_template("template.html")
```

Если route должен работать с БД, существующий стиль:

```python
with get_connection() as conn:
    rows = conn.execute("SELECT ...", params).fetchall()
```

Если route возвращает данные для JavaScript, используется:

```python
return jsonify(data)
```

После добавления route ссылка обычно добавляется в `app/web/templates/base.html`, если страница должна быть доступна из меню.

## Как добавить новую страницу

1. Добавить route в `app/web/routes.py`.
2. Добавить шаблон в `app/web/templates/`.
3. Если нужен общий layout, наследоваться от `base.html`:

```jinja2
{% extends "base.html" %}
{% block title %}Название{% endblock %}
{% block content %}
...
{% endblock %}
```

4. Если нужна навигация, добавить ссылку в `base.html`.
5. Если нужен CSS, использовать существующий `app/web/static/style.css`.

В проекте уже есть паттерны:

- таблицы: `index.html`, `receipt.html`, `item.html`, `products_merge.html`;
- графики: `analytics.html`, `item.html`;
- AJAX/JSON: `upload.html`, `analytics.html`.

## Как добавить новую аналитику

Основное место для данных `/analytics` - `app/analytics_service.py`.

Текущий паттерн:

1. Добавить SQL в `get_analytics_data()` или отдельную функцию.
2. Использовать `_build_filters()`, если аналитика должна поддерживать фильтры `start`, `end`, `store`, `category`, `item`.
3. Вернуть структуру JSON с `labels` и `values`, если это график.
4. Добавить canvas или UI-блок в `app/web/templates/analytics.html`.
5. В JavaScript загрузить данные через `fetch()` и построить Chart.js-график.

Если аналитика относится к одному товару, смотреть `get_item_trend()` и `item.html`.

Если аналитика относится к чеку, смотреть `build_receipt_price_analysis()` и `receipt.html`.

## Как работает Price & Quantity Model

Основной файл: `app/price_model.py`.

Минимальный поток:

1. Парсер возвращает `name`, `quantity`, `price`, а для Rimi также `quantity_unit` и `unit_price`, если они найдены.
2. `app/importer.py:prepare_receipt_data()` вызывает `derive_price_data()`.
3. `app/db.py:add_receipt_with_items()` повторно вызывает `derive_price_data()` перед вставкой, чтобы Gmail, upload и batch import шли через одну точку.
4. В `items` сохраняются новые поля Price Model, но `price` остается legacy итогом строки.

`derive_price_data()` использует evidence-first порядок: parser data, однозначная упаковка из названия, математически согласованный weighted inference, затем неподтвержденные варианты. `extract_package_size()` читает размер из названия (`500ml`, `0.5l`, `500g`, `0.5kg`, надежные `gab`/`pcs`). Multipack, сочетания нескольких размеров, malformed data и parser contamination отклоняются или остаются unresolved.

`normalized_unit_price` считается только когда хватает базы:

- весовой товар в `kg`/`g` -> `eur_per_kg`;
- литры/миллилитры -> `eur_per_l`;
- штуки с упаковкой `ml`/`g` -> `eur_per_l` или `eur_per_kg`;
- штуки без упаковки могут стать `inferred_piece`, но этот источник не применен к основной базе;
- неизвестная единица без упаковки -> `unknown`.

Confidence: parser `0.95`, `package_name` `0.85`, `weighted_inference` `0.75`, `inferred_piece` `0.70`, unresolved `NULL`. `weighted_inference` допустим только при `quantity * unit_price ~= line_total` с допуском округления. Служебные строки распознаются узкими правилами, получают `service_line` и остаются без normalized price; категория не меняется.

Selective backfill:

```text
python -m app.backfill_price_data --sources package_name,weighted_inference
python -m app.backfill_price_data --apply --sources package_name,weighted_inference
```

Dry-run является default. `--apply` без `--sources` отклоняется; неизвестные sources отклоняются. Field-level merge не заменяет сильное существующее значение слабым. High-confidence conflicts и IDs 3544, 3578, 3579, 3581 исключаются. Перед write `app.db:backup_database()` создает копию через SQLite Backup API и проверяет `PRAGMA integrity_check`.

Фактический selective backfill: 2184 строки (`package_name` 2179, `weighted_inference` 5), normalized units: 1664 `eur_per_kg`, 452 `eur_per_l`, 68 `eur_per_piece`. Повторный dry-run: 0 изменений. `inferred_piece`, `service_line`, rejected и unresolved не применялись; normalized price остается unresolved у 1094 строк. Полный apply не выполнялся.

Экран `/data-quality/prices` только читает данные. Он не исправляет БД.

## Как работает Product Normalizer

`app/product_normalizer.py:normalize_product_name()`:

- обрабатывает `None` и пустые строки;
- приводит название к lowercase;
- заменяет десятичную запятую между цифрами на точку;
- унифицирует пробелы;
- удаляет лишнюю пунктуацию;
- сохраняет латинские и латышские буквы, цифры и `%`;
- приводит `l` к `ml`, `kg` к `g`, `gr` к `g`, `gab.` к `gab`;
- удаляет только allowlist технических токенов: `d`, `pet`, `sk`.

Функция не удаляет бренд, вкус, вариант, жирность, крепость, размер упаковки, объем или массу.

`extract_product_features()` извлекает только:

- `volume_ml`;
- `weight_g`;
- `percentage`.

Бренд, вкус, тип товара и категория намеренно не определяются.

## Как работает Product Suggestions

Route `/products/suggestions` находится в `app/web/routes.py:product_suggestions()`.

Данные строит `app/product_matcher.py:find_similar_products()`:

- агрегирует уникальные варианты товаров из `items`;
- использует `normalized_name`, если поле заполнено;
- если `normalized_name` пустой, вычисляет его из `items.name` на лету;
- делает token buckets для shortlist;
- считает RapidFuzz score через `fuzz.token_set_ratio()`;
- показывает только score от `88`;
- `95+` считается `high`, `88-94.99` считается `possible`.

Hard guards блокируют пары с разным объемом, массой, процентом или явными разными вариантами вроде `zero/original`, `cheese/bacon`.

Страница не выполняет POST merge и не меняет `canonical_name`.

## Как добавить новый parser

Текущий вход: `app/receipt_parser.py:parse_receipt(text)`.

Перед store-specific parsing весь текст проходит через `preprocess_receipt_text()` и `sanitize_receipt_lines()`. Новая ветка parser должна использовать этот общий boundary, а не добавлять собственную OCR-нормализацию. Разрешены только доказуемые whitespace fixes; `lkg`, `m1`, glued tokens и unsafe decimals отклоняются функцией `parser_quality_issue()` без попытки восстановить значение. Multipack сохраняется как исходный товар и остается unresolved downstream.

Read-only аудит запускается через `python -m app.audit_parser_quality`. Он читает только `items.id/name` через SQLite `mode=ro`, показывает exclusive contamination groups, вероятный слой причины, примеры и projected action. Audit текущей базы: 8 corrected, 694 rejected, 138 unresolved, 2740 unchanged. Старый raw OCR text не хранится, поэтому это проекция, а не повторный parse исторических PDF.

Существующий паттерн:

- создать отдельную функцию, как `parse_rimi_receipt(lines)`;
- в `parse_receipt()` определить магазин по строкам;
- вернуть объект:

```python
{
    "store": "...",
    "date": "...",
    "total": 0.0,
    "items": [
        {
            "name": "...",
            "quantity": 1.0,
            "price": 0.0,
            "category": "..."
        }
    ]
}
```

Важно: итоговая категория все равно будет перезаписана в `app/importer.py:prepare_receipt_data()` через `categorize_with_source()`.

Импорт ожидает:

- `items` не пустой;
- `price` может быть пустой, тогда станет `0`;
- `quantity` может быть пустой, тогда станет `1`;
- `total` может быть пустой, тогда будет сумма товаров.

## Как добавить категорию или правило

Канонический список лежит в `app/category_keywords.py:CANONICAL_CATEGORIES`.

Alias mapping лежит в `CATEGORY_ALIASES`.

Фактические keyword-правила лежат в `CATEGORY_KEYWORDS`.

Если новая категория может конфликтовать с существующими, порядок выбора задается в `PRIORITY`.

UI-цвет категории находится в `app/web/app.py:category_color()`.

Список категорий в формах строится из canonical list. Новые ручные категории через UI не добавляются.

## Как работает ручная категория товара

`POST /item/<id>/category` поддерживает:

- `category_scope=item` - обновляется только одна строка `items`, source становится `manual`;
- `category_scope=product` - создается/обновляется `product_category_rules`, затем обновляется вся точная группа.

`product_key` считает `app/category_rules.py:get_product_key()`:

- normalized `canonical_name`, если canonical заполнен;
- иначе `normalized_name`;
- иначе `normalize_product_name(name)`.

При новом импорте `app/db.py:add_receipt_with_items()` проверяет `product_category_rules`. Если правило есть, item получает `category_source = inherited`.

## Как работает проверка категорий

Route `/products/review` агрегирует группы из `items` и `receipts`. Он не использует RapidFuzz и не объединяет товары. Форма на странице применяет выбранную canonical category ко всей точной группе.

## Места, которые лучше не трогать без проверки побочных эффектов

- `app/db.py:create_tables()` - влияет на запуск приложения и существующую БД.
- `app/db.py:add_receipt_with_items()` - единая точка вставки чеков и товаров.
- `app/importer.py:prepare_receipt_data()` - связывает PDF extraction, parser, categorization и fallback total.
- `app/receipt_parser.py:parse_receipt()` - решает, какой parser использовать.
- `app/category_keywords.py:categorize_from_name()` - влияет на все будущие импорты и ручную перекатегоризацию.
- `app/category_keywords.py:CANONICAL_CATEGORIES` - влияет на dropdown категорий.
- `app/category_rules.py:get_product_key()` - влияет на границы ручной category-группы.
- `app/product_normalizer.py:normalize_product_name()` - влияет на новые `items.normalized_name`, backfill и suggestions.
- `app/product_matcher.py:_blocked()` - отвечает за безопасность предложений похожих товаров.
- `app/price_model.py:derive_price_data()` - влияет на все новые ценовые поля при импорте и backfill.
- `app/backfill_price_data.py` - default режим read-only; write требует явные `--apply --sources package_name,weighted_inference` и отдельное разрешение пользователя.
- `PRODUCT_NAME_EXPR` в `app/web/routes.py` и `app/analytics_service.py` - влияет на аналитику, товары, профили и объединение.
- `/products/merge` - массово обновляет `canonical_name`.
- `app/gmail_fetcher.py:gmail_settings()` - влияет на то, какие письма и файлы будут импортированы.

## Где могут возникнуть побочные эффекты

- Изменение regex парсера может изменить количество найденных товаров.
- Изменение логики даты может повлиять на сортировку и месячные графики.
- Изменение `receipt_number` может повлиять на дубликаты.
- Изменение категорий может изменить историческую аналитику после перекатегоризации.
- Изменение manual product rule влияет на новые импорты этой товарной группы.
- Изменение `canonical_name` меняет группировку товаров во всей аналитике.
- Изменение `normalized_name` меняет только suggestions и будущий Product Engine, но не текущую аналитику.
- Изменение `price` или `quantity` меняет цену за единицу, топ товаров и оценку выгодности.
- Изменение `normalized_unit_price` или `normalized_price_unit` меняет сравнение цен на `/item/<name>` и `/receipt/<id>`, но не основные графики расходов.
- Изменение схемы БД может не примениться к старой базе, если используется `CREATE TABLE IF NOT EXISTS`.
- Фактическая старая БД может иметь constraints, отличные от новой схемы в коде.

## Что отсутствует в проекте

- Миграционный инструмент не найден.
- Отдельный parser registry не найден.
- Таблица аудита ручных изменений категорий не найдена.
- Таблица ошибок категоризации не найдена.
- Явный парсер Lidl не найден.
- Таблица `products` не создавалась.
- Таблица rejected matches не создавалась.
- Полноценный audit log category changes отсутствует.
- Таблица price warnings не создавалась; warnings пока живут только в расчетной модели и dry-run выводе.
- Полный Price Model backfill и применение `inferred_piece` не одобрены.

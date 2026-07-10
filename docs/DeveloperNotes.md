# Developer Notes

## С чего начинать чтение проекта

1. `PROJECT_GUIDE.md` - короткая пользовательская памятка.
2. `run.py` - точка запуска.
3. `app/web/app.py` - создание Flask-приложения.
4. `app/web/routes.py` - маршруты, SQL для страниц, часть расчетов.
5. `app/db.py` - схема и базовые операции с SQLite.
6. `app/importer.py` - импорт PDF, OCR, подготовка данных.
7. `app/receipt_parser.py` - парсинг текста чека.
8. `app/category_keywords.py` - правила категоризации.
9. `app/analytics_service.py` - данные для графиков.
10. `app/web/templates/` - UI.

## Самые важные файлы

- `run.py` - запуск приложения.
- `app/config.py` - пути к данным, загрузкам и базе.
- `app/web/app.py` - `create_app()`, регистрация маршрутов, цвета категорий.
- `app/web/routes.py` - центральный файл веб-логики.
- `app/db.py` - схема, подключение, вставка чеков.
- `app/importer.py` - PDF/OCR/import pipeline.
- `app/receipt_parser.py` - Maxima/Rimi parsing.
- `app/category_keywords.py` - CategoryEngine.
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

## Как добавить новый parser

Текущий вход: `app/receipt_parser.py:parse_receipt(text)`.

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

Важно: итоговая категория все равно будет перезаписана в `app/importer.py:prepare_receipt_data()` через `categorize_from_name()`.

Импорт ожидает:

- `items` не пустой;
- `price` может быть пустой, тогда станет `0`;
- `quantity` может быть пустой, тогда станет `1`;
- `total` может быть пустой, тогда будет сумма товаров.

## Как добавить категорию или правило

Фактические правила лежат в `app/category_keywords.py:CATEGORY_KEYWORDS`.

Если новая категория может конфликтовать с существующими, порядок выбора задается в `PRIORITY`.

UI-цвет категории находится в `app/web/app.py:category_color()`.

Список категорий в формах строится из фактических значений БД через `get_category_options()`, поэтому новые категории могут появляться после импорта или ручной смены.

## Места, которые лучше не трогать без проверки побочных эффектов

- `app/db.py:create_tables()` - влияет на запуск приложения и существующую БД.
- `app/db.py:add_receipt_with_items()` - единая точка вставки чеков и товаров.
- `app/importer.py:prepare_receipt_data()` - связывает PDF extraction, parser, categorization и fallback total.
- `app/receipt_parser.py:parse_receipt()` - решает, какой parser использовать.
- `app/category_keywords.py:categorize_from_name()` - влияет на все будущие импорты и ручную перекатегоризацию.
- `PRODUCT_NAME_EXPR` в `app/web/routes.py` и `app/analytics_service.py` - влияет на аналитику, товары, профили и объединение.
- `/products/merge` - массово обновляет `canonical_name`.
- `app/gmail_fetcher.py:gmail_settings()` - влияет на то, какие письма и файлы будут импортированы.

## Где могут возникнуть побочные эффекты

- Изменение regex парсера может изменить количество найденных товаров.
- Изменение логики даты может повлиять на сортировку и месячные графики.
- Изменение `receipt_number` может повлиять на дубликаты.
- Изменение категорий может изменить историческую аналитику после перекатегоризации.
- Изменение `canonical_name` меняет группировку товаров во всей аналитике.
- Изменение `price` или `quantity` меняет цену за единицу, топ товаров и оценку выгодности.
- Изменение схемы БД может не примениться к старой базе, если используется `CREATE TABLE IF NOT EXISTS`.
- Фактическая старая БД может иметь constraints, отличные от новой схемы в коде.

## Что отсутствует в проекте

- Автоматические тесты не найдены.
- Миграционный инструмент не найден.
- Отдельный parser registry не найден.
- Таблица аудита ручных изменений категорий не найдена.
- Таблица ошибок категоризации не найдена.
- Явный парсер Lidl не найден.
- Документированная API-схема JSON endpoint не найдена до создания этих docs.


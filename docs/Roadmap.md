# Roadmap

## DONE

- Flask-приложение запускается через `run.py`.
- При старте создаются таблицы SQLite через `create_tables()`.
- Настроены папки `data`, `data/uploads`, `data/pdf_receipts`.
- Реализована SQLite-модель чеков `receipts`.
- Реализована SQLite-модель товаров `items`.
- Добавлены индексы для дат, магазинов, номеров чеков, receipt_id, категорий, имен и canonical_name.
- Реализован ручной импорт PDF через страницу `/upload`.
- Реализовано чтение текстового слоя PDF через `pdfplumber`.
- Реализован OCR fallback для PDF-сканов через Poppler и Tesseract.
- Реализован импорт PDF-вложений из Gmail через IMAP.
- Реализован парсер Rimi.
- Реализован fallback-парсер Maxima.
- Реализована словарная категоризация товаров.
- Реализована ручная смена категории позиции.
- Реализована перекатегоризация существующих товаров через `app/categorize_existing_items.py`.
- Реализована главная страница списка чеков `/`.
- Реализована страница деталей чека `/receipt/<id>`.
- Реализована страница аналитики `/analytics`.
- Реализован JSON endpoint `/analytics/data`.
- Реализован JSON endpoint `/analytics/item_trend`.
- Реализован профиль товара `/item/<name>`.
- Реализовано автодополнение товаров `/autocomplete/item_names`.
- Реализовано объединение товаров через `canonical_name` на `/products/merge`.
- Реализованы Chart.js-графики категорий, месяцев, топ товаров и динамики цены.
- Реализована оценка цены товара относительно средней и медианной цены.
- Реализована оценка позиций чека как дешевле/дороже/обычно/без истории.
- Создана техническая документация в `docs/`.
- Реализован Product Normalizer.
- Добавлено поле `items.normalized_name`.
- Реализован RapidFuzz suggestion engine.
- Добавлена страница похожих товаров `/products/suggestions`.
- Реализован единый список категорий.
- Добавлено поле `items.category_source`.
- Добавлена таблица `product_category_rules`.
- Реализована ручная категория всей товарной группы.
- Реализовано наследование ручных категорий при импорте.
- Добавлен review screen категорий `/products/review`.
- Добавлен category audit script `app/audit_categories.py`.
- Реализована Price & Quantity Model v2.
- Добавлены поля `line_total`, `unit_price`, `quantity_unit`, `package_size`, `package_unit`, `normalized_unit_price`, `normalized_price_unit`, `price_parse_source`, `price_parse_confidence`.
- Добавлено извлечение размера упаковки из названия товара.
- Добавлен расчет нормализованной цены EUR/L, EUR/kg и EUR/piece.
- Добавлен helper совместимости ценовых единиц `are_price_units_comparable()`.
- Добавлен dry-run/backfill скрипт `app/backfill_price_data.py`.
- Добавлена read-only страница качества цен `/data-quality/prices`.
- Профиль товара и страница чека используют нормализованную цену для сравнения, если данных достаточно.
- Добавлены unit tests для Price Model.
- Завершен selective Price Model backfill: 2184 строки (`package_name` 2179, `weighted_inference` 5).
- Добавлены evidence-first confidence levels, service-line exclusions, field-level downgrade protection и SQLite Backup API с integrity check.
- `normalized_name` заполнен для всех 3580 items; повторный selective Price Model dry-run показывает 0 изменений.

## IN PROGRESS

- Нет активных изменений.

## TODO

1. Провести manual review 1094 unresolved normalized-price строк, включая service-line, suspicious/multipack группы и конфликты 3544, 3578, 3579, 3581.
2. Улучшать parser evidence точечно по подтвержденным исходным данным.
3. Отдельно решить судьбу `inferred_piece`; он не считается завершенным и не разрешен к write-backfill.
4. Не выполнять полный Price Model backfill без отдельного решения и нового safety audit.

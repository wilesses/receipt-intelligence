# Architecture

## Назначение проекта

Receipt Tracker v2 собирает PDF-чеки, извлекает из них товары, сохраняет чеки и позиции в SQLite и показывает расходы через веб-интерфейс.

Реализованные источники чеков:

- ручная загрузка PDF на странице `/upload`;
- загрузка PDF-вложений из Gmail через IMAP на endpoint `/gmail/fetch`;
- пакетный импорт файлов из папки `data/pdf_receipts` через `app/importer.py`.

## Используемый стек

- Python.
- Flask для веб-приложения: `run.py`, `app/web/app.py`, `app/web/routes.py`.
- Jinja2-шаблоны: `app/web/templates/`.
- SQLite через стандартный модуль `sqlite3`: `app/db.py`.
- pdfplumber для чтения текстового слоя PDF: `app/importer.py`.
- Poppler `pdftoppm` и Tesseract для OCR, если PDF выглядит как скан: `app/importer.py`.
- RapidFuzz для безопасных предложений похожих товаров: `app/product_matcher.py`.
- python-dotenv для загрузки `.env` в Gmail-импорте: `app/gmail_fetcher.py`.
- imaplib/email из стандартной библиотеки для Gmail IMAP.
- Bootstrap, Bootstrap Icons, Chart.js и chartjs-plugin-datalabels через CDN в шаблонах.

## Структура приложения

```text
reciept_tracker_v2/
  run.py
  requirements.txt
  PROJECT_GUIDE.md
  app/
    config.py
    db.py
    importer.py
    receipt_parser.py
    product_normalizer.py
    product_matcher.py
    backfill_normalized_names.py
    category_keywords.py
    analytics_service.py
    analytics.py
    gmail_fetcher.py
    categorize_existing_items.py
    main.py
    analy
    web/
      app.py
      routes.py
      static/
        style.css
      templates/
        base.html
        index.html
        upload.html
        analytics.html
        item.html
        receipt.html
        products_merge.html
        static/
          style.css
  data/
    receipts.db
    pdf_receipts/
    uploads/
  backups/
  refactor_preview/
  docs/
```

`app/analy` существует как пустой файл. По коду не используется.

`app/analytics.py` пустой. Реальная аналитика находится в `app/analytics_service.py` и `app/web/routes.py`.

`refactor_preview/` и `backups/` есть в проекте, но текущий запуск использует основной пакет `app/`.

## Основные слои

### Запуск

- `run.py` импортирует `create_app()` из `app/web/app.py`.
- `app/web/app.py:create_app()` вызывает `create_tables()`, создает `Flask`, регистрирует маршруты через `init_routes(app)` и добавляет Jinja helper `category_color()`.
- Порт берется из `PORT`, по умолчанию `5000`.
- Debug включается через `FLASK_DEBUG=1`.

### Конфигурация путей

`app/config.py` задает:

- `BASE_DIR`;
- `DATA_DIR = data`;
- `UPLOAD_DIR = data/uploads`;
- `PDF_IMPORT_DIR = data/pdf_receipts`;
- `DB_PATH = data/receipts.db`.

`ensure_data_dirs()` создает эти папки при работе с БД, загрузкой и импортом.

### Web UI

Маршруты лежат в `app/web/routes.py`:

- `/` - список чеков;
- `/upload` - ручная загрузка PDF;
- `/gmail/fetch` - проверка Gmail и импорт найденных PDF;
- `/analytics` - страница аналитики;
- `/analytics/data` - JSON для основных графиков;
- `/analytics/item_trend` - JSON динамики цены товара;
- `/autocomplete/item_names` - автодополнение товаров;
- `/products/merge` - объединение названий товаров через `canonical_name`;
- `/products/suggestions` - предложения похожих товаров без автоматического объединения;
- `/item/<name>` - профиль товара;
- `/receipt/<int:receipt_id>` - страница чека;
- `/item/<int:item_id>/category` - ручное обновление категории позиции.

### База данных

Основная работа с БД находится в `app/db.py`:

- `get_connection()`;
- `create_tables()`;
- `add_receipt_with_items()`;
- `get_all_receipts()`;
- `get_items_by_receipt()`;
- `get_total_spent()`.

Аналитические SQL-запросы находятся в:

- `app/analytics_service.py:get_analytics_data()`;
- `app/analytics_service.py:get_item_trend()`;
- `app/web/routes.py:item_profile()`;
- `app/web/routes.py:view_receipt()`;
- `app/web/routes.py:products_merge()`;
- `app/web/routes.py:products_merge_submit()`.
- `app/product_matcher.py:find_similar_products()`.

## Жизненный цикл данных

```text
PDF / Gmail
↓
Извлечение текста
↓
Парсер
↓
Категоризация
↓
SQLite
↓
Analytics
↓
Web UI
```

### PDF / Gmail

Ручной PDF:

- `app/web/routes.py:upload()`;
- проверка расширения в `allowed_file()`;
- сохранение в `data/uploads` через `secure_filename()`;
- запуск `process_pdf_api(file_path)`.

Gmail:

- `app/web/routes.py:gmail_fetch()`;
- `app/gmail_fetcher.py:fetch_pdf_attachments()`;
- настройки через `gmail_settings()`;
- подключение через `connect_to_gmail()`;
- поиск писем через `_search_email_ids()`;
- сохранение PDF в `SAVE_FOLDER`, по умолчанию `data/pdf_receipts`;
- импорт через `process_pdf_api(file_path)`.

Пакетный импорт:

- `app/importer.py:import_all_pdfs()`;
- берет `.pdf` из `PDF_IMPORT_DIR`;
- после успешного импорта удаляет файл через `os.remove(file_path)`.

### Извлечение текста

`app/importer.py:extract_text_from_pdf()`:

- открывает PDF через `pdfplumber.open()`;
- собирает `page.extract_text()` по страницам;
- если текст найден, возвращает объединенный текст;
- если текста нет, но есть изображения, вызывает `extract_text_with_ocr()`;
- если нет ни текста, ни OCR-сценария, бросает `PdfTextExtractionError`.

OCR:

- `extract_text_with_ocr()`;
- ищет `pdftoppm` через `PDFTOPPM_CMD`, известный путь или `PATH`;
- ищет `tesseract` через `TESSERACT_CMD`, стандартные Windows-пути или `PATH`;
- конвертирует PDF в PNG через `pdftoppm -png -r 220`;
- читает картинки через `tesseract ... stdout -l lav+eng`.

### Парсер

`app/receipt_parser.py:parse_receipt(text)`:

- делит текст на непустые строки;
- если любая строка содержит `rimi`, пробует `parse_rimi_receipt(lines)`;
- если Rimi-парсер вернул товары, результат считается Rimi;
- иначе используется Maxima-парсер.

Rimi:

- `parse_rimi_receipt(lines)`;
- дата ищется по строке с `laiks`, затем fallback по общему regex даты;
- итог ищется снизу вверх по `kopa` или `kopā`;
- товары ищутся по regex количества/цены `qty_line_pattern`;
- название собирается из предыдущих строк.

Maxima:

- магазин задается как `MAXIMA`;
- дата ищется по `YYYY-MM-DD` или `DD.MM.YYYY`;
- итог ищется снизу вверх по `kopā apmaksai`;
- товарная строка определяется по шаблону `\d+,\d{2}\s+X\s+[\d,]+`;
- название собирается из предыдущих строк.

### Категоризация

В парсере есть `categorize_item(name)`, но итоговая категория при импорте повторно назначается в `app/importer.py:prepare_receipt_data()` через `app/category_keywords.py:categorize_from_name()`.

Правила лежат в:

- `CATEGORY_KEYWORDS`;
- `PRIORITY`;
- `categorize_from_name()`.

Если совпадений нет, категория становится `прочее`.

### Нормализация товара

Product Normalizer находится в `app/product_normalizer.py`.

Функции:

- `normalize_product_name(name)` - детерминированно приводит название к форме для сравнения;
- `extract_product_features(normalized_name)` - извлекает `volume_ml`, `weight_g`, `percentage`.

Нормализация не меняет `items.name`, `items.canonical_name` и `items.category`. При новых импортах `app/db.py:add_receipt_with_items()` заполняет только новое поле `items.normalized_name`.

Для существующих данных создан отдельный dry-run/backfill скрипт:

```text
python -m app.backfill_normalized_names --dry-run
python -m app.backfill_normalized_names
```

Обычный backfill не запускается автоматически.

### SQLite

`app/importer.py:process_pdf_api()`:

- получает подготовленные данные через `prepare_receipt_data()`;
- берет `receipt_number` из имени файла: `Path(file_path).stem`;
- сохраняет через `add_receipt_with_items()`.

`app/db.py:add_receipt_with_items()`:

- вызывает `create_tables()`;
- проверяет дубликат по `receipt_number`;
- вставляет строку в `receipts`;
- вставляет позиции в `items`.

Вставка новых `items` также сохраняет `normalized_name = normalize_product_name(name)`. `canonical_name` при импорте остается `NULL`.

### Analytics

Основная аналитика:

- `app/analytics_service.py:get_analytics_data()`;
- фильтры строятся в `_build_filters()`;
- суммы по категориям, месяцам, топ товарам и общий расход считаются SQL;
- средний расход в месяц считается в Python.

Тренд товара:

- `app/analytics_service.py:get_item_trend()`;
- SQL группирует по месяцу и суммирует цену/количество;
- Python считает цену за единицу.

Страница товара:

- `app/web/routes.py:item_profile()`;
- SQL получает историю покупок, агрегаты, магазины, алиасы;
- Python вызывает `build_price_evaluation()`.

Страница чека:

- `app/web/routes.py:view_receipt()`;
- SQL получает позиции чека;
- Python считает `total_sum` и вызывает `build_receipt_price_analysis()`.

### Web UI

Шаблоны:

- `index.html` показывает список чеков, поиск по магазину и сортировку на клиенте;
- `upload.html` отправляет PDF на `/upload` и запускает `/gmail/fetch`;
- `analytics.html` получает JSON с `/analytics/data` и `/analytics/item_trend`, строит Chart.js-графики;
- `item.html` показывает профиль товара, алиасы, цену за единицу и историю покупок;
- `receipt.html` показывает позиции чека и статус цены;
- `products_merge.html` обновляет `canonical_name`.
- `product_suggestions.html` показывает пары похожих товаров и ведет в существующее объединение.

### Product Suggestions

`app/product_matcher.py:find_similar_products(conn, query=None, limit=100)` строит предложения только по уникальным агрегированным товарам, а не по всем строкам `items` попарно.

Используются:

- `normalized_name`;
- `extract_product_features()`;
- `rapidfuzz.fuzz.token_set_ratio()`;
- предварительные token buckets;
- hard guards по объему, массе, проценту и вариантам товара.

Route `/products/suggestions` только показывает кандидатов. Он не присваивает `canonical_name`, не меняет `items.name`, не создает `products` table и не делает merge.

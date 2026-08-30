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
- Собственная Price & Quantity Model v2 для расчета `line_total`, `unit_price`, размера упаковки и нормализованной цены: `app/price_model.py`.
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
    price_model.py
    backfill_normalized_names.py
    backfill_price_data.py
    category_rules.py
    audit_categories.py
    backfill_category_sources.py
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
- `/autocomplete/item_names` - автодополнение effective product identities; `details=1` добавляет серверный Product Dossier URL;
- `/products/merge` - объединение названий товаров через `canonical_name`;
- `/products/suggestions` - предложения похожих товаров без автоматического объединения;
- `/products/review` - проверка категорий товарных групп;
- `/data-quality/prices` - read-only экран качества данных Price Model;
- `/item/<path:name>` - профиль товара, включая имена с `/`;
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
- `app/category_rules.py` - ручные category rules и product_key.

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

`app/receipt_parser.py:categorize_item()` делегирует в общую `app/category_keywords.py:categorize_from_name()`. `app/importer.py:prepare_receipt_data()` повторно вызывает тот же общий classifier на финальном имени товара, поэтому parser и import boundary не содержат двух разных реализаций.

Правила лежат в:

- `CATEGORY_KEYWORDS`;
- `PRIORITY`;
- `categorize_from_name()`.

Classifier нормализует Unicode-текст один раз, сопоставляет целые токены, фразы и явные token-prefix правила. Каждый keyword учитывается один раз. Product/use type имеет приоритет над flavour/ingredient: service, pet/baby/non-food и alcohol идут раньше пищевых типов; sauces/ready/fish/frozen/eggs и явные bakery/snack/beverage/meat/dairy/pantry/produce формы разрешаются детерминированно. Небезопасные brand-only `Santa Maria`/`Spilva`, одиночное `sald.` и процент без alcohol term не являются положительным evidence. Если evidence недостаточно или политика неоднозначна, категория становится `прочее / требует решения`.

При вставке `app/db.py:add_receipt_with_items()` после автоматического результата вычисляет exact raw `product_key`. Найденное `product_category_rules` всегда сильнее classifier и сохраняется с `category_source = inherited`.

Read-only shadow evaluator `app/audit_category_classifier_v2.py` открывает SQLite через `mode=ro&immutable=1`, сравнивает автоматический прогноз с persisted taxonomy и отдельно показывает exact-rule-covered и rule-free cohorts. Он ничего не перекатегоризирует.

Category Engine v2 использует единый плоский список из 18 значений в `CANONICAL_CATEGORIES`, alias mapping старых названий, `category_source`, таблицу `product_category_rules`, ручную категорию всей точной группы товара, наследование manual rule при новом импорте и экран `/products/review`. Подкатегории не сохраняются. Старые значения на исключенных REVIEW/UNRESOLVED строках остаются в БД, но `category_for_reporting()` отображает их как `прочее / требует решения` и формы показывают исходное сохраненное значение.

Контролируемое применение исторической таксономии выполняет `app/apply_category_taxonomy_v2.py`: только точный SAFE CSV, все before-state predicates, один `BEGIN IMMEDIATE`, проверенная SQLite Backup API копия и строгий diff с backup. Скрипт не использует classifier keywords, fuzzy matching, `LIKE` или общий backfill.

### Price & Quantity Model

Price Model находится в `app/price_model.py`.

Архитектура evidence-first: parser evidence имеет приоритет над выводом из названия; `weighted_inference` принимается только при математической согласованности исходных значений. Confidence levels: parser `0.95`, `package_name` `0.85`, `weighted_inference` `0.75`, `inferred_piece` `0.70`. `manual_correction = 0.85` означает policy confidence: пользователь подтвердил structured evidence, и результат прошел те же structural guards; это не статистическая или «истинная» уверенность. Service/non-product lines, multipack, malformed и parser-contaminated строки остаются без автоматически рассчитанной normalized price, в том числе при ручной коррекции.

Функции:

- `derive_price_data()` - единая функция вывода ценовых полей;
- `extract_package_size()` - извлекает размер упаковки из названия;
- `calculate_normalized_unit_price()` - считает EUR/L, EUR/kg или EUR/piece;
- `validate_price_data()` - собирает warnings; confidence назначается по источнику evidence;
- `are_price_units_comparable()` - проверяет, можно ли сравнивать две цены.

При импорте `app/importer.py:prepare_receipt_data()` добавляет ценовые поля к item, а `app/db.py:add_receipt_with_items()` повторно считает их в общей точке вставки. Это сохраняет одну точку истины для Gmail, upload и batch import.

`items.price` остается итоговой ценой строки. Новые поля `line_total`, `unit_price`, `quantity_unit`, `package_size`, `package_unit`, `normalized_unit_price`, `normalized_price_unit`, `price_parse_source`, `price_parse_confidence` добавляются без перестройки таблицы.

`app/backfill_price_data.py` является dry-run по умолчанию. Selective write разрешает только явный source allowlist (`package_name`, `weighted_inference`), применяет field-level downgrade protection и исключает high-confidence conflicts. Перед write `app.db:backup_database()` создает backup через SQLite Backup API и требует `PRAGMA integrity_check = ok`.

Selective backfill основной базы завершен: 2184 строки, только 2179 `package_name` и 5 `weighted_inference`. `inferred_piece`, `service_line`, rejected/unresolved и manual-review IDs 3544, 3578, 3579, 3581 не применялись. Повторный selective dry-run показывает 0 изменений; 1094 normalized prices остаются unresolved. Полный backfill не выполнялся и запрещен без отдельного решения.

Узкий one-row correction workflow начинается в Price Quality и разрешает менять только `quantity_unit`, `package_size`, `package_unit`. `app/price_correction.py` классифицирует строки и исключает missing `line_total`, arithmetic mismatch, unresolved multipack, service/parser contamination и предложения с любым блокирующим warning.

Preview ничего не пишет и формирует signed token как integrity/stale-state mechanism, а не security boundary. Token содержит `item_id`, hash persisted before-state, proposed fields и projected derived fields. Apply открывает `BEGIN IMMEDIATE`, заново загружает строку, проверяет before-state и предложение, повторно вызывает `derive_price_data()` и только затем атомарно обновляет одну строку через optimistic predicates. Derived values из token никогда не являются источником истины.

Успешный apply меняет только structured/derived Price Model поля и ставит `price_parse_source = manual_correction`, `price_parse_confidence = 0.85`. После этого строка участвует в Analytics, Dossier, historical deviation и Store Comparison только если проходит существующие eligibility contracts.

### Нормализация товара

Product Normalizer находится в `app/product_normalizer.py`. Общий пользовательский identity-контракт находится в `app/product_identity.py`.

Функции:

- `normalize_product_name(name)` - детерминированно приводит название к форме для сравнения;
- `extract_product_features(normalized_name)` - извлекает `volume_ml`, `weight_g`, `percentage`.

Нормализация не меняет `items.name`, `items.canonical_name` и `items.category`. При новых импортах `app/db.py:add_receipt_with_items()` заполняет только новое поле `items.normalized_name`.

Effective product identity вычисляется только как непустой persisted `canonical_name`, иначе raw receipt `name`. SQL и row helpers принадлежат `app/product_identity.py`; Product Dossier, Analytics, autocomplete, Home, deviation, Store Comparison, discovery и Merge не должны копировать выражение локально. `normalized_name` разрешено использовать для поиска и Suggestions, но не для автоматического объединения user-facing identities.

Category `product_key` намеренно отдельный: `get_product_key()` использует normalized canonical/name fallback, чтобы сохранять правила категории. Его нельзя подменять effective product identity.

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

Вставка новых `items` также сохраняет Price Model поля через `derive_price_data()`. У Rimi parser теперь может прийти `quantity_unit` (`gab`/`kg`) и `unit_price`; у Maxima `quantity_unit` пока остается `unknown`.

При вставке новых `items` `app/db.py:add_receipt_with_items()` также вычисляет `product_key`, ищет правило в `product_category_rules`, ставит `category_source = inherited`, если правило найдено, иначе сохраняет `rule` или `fallback`.

### Analytics

Основная аналитика:

- `app/analytics_service.py:get_analytics_data()`;
- фильтры строятся в `_build_filters()`;
- суммы по категориям, месяцам, топ товарам и общий расход считаются SQL;
- средний расход в месяц считается в Python.

Тренд товара:

- `app/analytics_service.py:get_item_trend()`;
- SQL выбирает строки одной exact effective identity;
- Python применяет общий safe normalized-price eligibility и считает месячную медиану внутри одного denominator; mixed units и недостаток evidence закрываются без fallback.

Страница товара:

- `app/web/routes.py:item_profile()`;
- SQL получает историю покупок, агрегаты, магазины, алиасы;
- Python передает последнюю покупку и ее effective identity в общий `app/price_deviation.py:evaluate_price_deviation()`;
- latest-vs-usual и месячный график используют только безопасную normalized price; legacy `price / quantity` отсутствует.

Страница чека:

- `app/web/routes.py:view_receipt()`;
- SQL получает позиции чека;
- Python считает `total_sum` и вызывает `build_receipt_price_analysis()`;
- статус цены каждой позиции приходит из общего `evaluate_price_deviation()`; legacy fallback отсутствует.

### Historical price deviation

`app/price_deviation.py` владеет единым контрактом для Receipt Detail, Product Dossier Price Story и normalized-price кандидата Home Month Story:

- identity: shared persisted canonical-or-raw helper из `app/product_identity.py` без fuzzy matching;
- evidence: positive normalized EUR/kg, EUR/L или EUR/piece; source `derived`, `package_name`, `parser`, `weighted_inference` или guarded `manual_correction`; confidence `>= 0.75`; полные согласованные quantity/unit price/line total; допуск €0.02; валидная дата; без блокирующих Price Model diagnostics и известных unresolved identities;
- baseline: медиана минимум трех eligible prior observations того же identity и unit за предыдущие 180 дней;
- порядок в один день: `(date, receipt_id, item_id)`; текущая строка и более поздние строки исключены;
- статусы: `CHEAPER_THAN_USUAL` при `<= -10%`, `MORE_EXPENSIVE_THAN_USUAL` при `>= +15%`, иначе `NORMAL`; любой недостаток evidence возвращает `INSUFFICIENT_HISTORY` с reason.

`app/price_deviation_presentation.py` переводит только готовый `INSUFFICIENT_HISTORY` result в общий presentation-контракт для Receipt Detail и Product Dossier. Он не вычисляет eligibility, baseline или deviation. Четыре стабильные категории:

- `NOT_ENOUGH_HISTORY`: `insufficient_prior_history`; показывает число eligible prior observations из требуемых трех;
- `PRICE_NOT_COMPARABLE`: отсутствующая/неподдерживаемая normalized-price evidence, service line или unresolved multipack;
- `PRODUCT_IDENTITY_UNCERTAIN`: `unresolved_product_identity`;
- `EVIDENCE_NEEDS_REVIEW`: low confidence, non-positive/out-of-range evidence, отсутствующие store/date, invalid ordering, arithmetic mismatch, parser contamination, ambiguous measurement и другие blocking diagnostics.

Presentation сохраняет приоритет evaluator: unresolved identity → непригодность текущего observation → недостаток eligible prior history. Progress означает только eligible normalized observations того же effective identity и unit, строго раньше текущей строки в пределах 180 дней; это не общий счетчик покупок.

Home сохраняет дополнительный presentation gate `abs(deviation) >= 15%` и существующее ранжирование историй. Store Price Comparison остается отдельным вопросом с per-store median/evidence levels, хотя использует тот же deterministic observation eligibility helper. Analytics spend не использует historical-deviation evaluator; Analytics item trend переиспользует только его identity/observation eligibility и независимо агрегирует monthly median.

### Web UI

Шаблоны:

- `index.html` показывает список чеков, поиск по магазину и сортировку на клиенте;
- `upload.html` отправляет PDF на `/upload` и запускает `/gmail/fetch`;
- `analytics.html` получает JSON с `/analytics/data` и `/analytics/item_trend`, строит Chart.js-графики;
- Local Research использует `/autocomplete/item_names?details=1` как universal discovery entry: endpoint ищет по shared effective identity, raw aliases и `normalized_name`, но каждый результат возвращает одну точную effective identity и сгенерированный Flask URL существующего Product Dossier;
- кнопка динамики и ссылка Dossier активируются только для результата autocomplete; любое изменение текста немедленно сбрасывает выбранную identity, поэтому свободный текст не создаёт guessed URL;
- `item.html` показывает профиль товара, алиасы, цену за единицу и историю покупок;
- `receipt.html` показывает позиции чека и статус цены;
- `products_merge.html` обновляет `canonical_name`.
- `product_suggestions.html` показывает пары похожих товаров и ведет в существующее объединение.
- `product_review.html` показывает проблемные товарные группы и форму применения canonical category ко всей группе.
- `price_data_quality.html` показывает read-only диагностику Price Model.

### Product Suggestions

`app/product_matcher.py:find_similar_products(conn, query=None, limit=100)` строит предложения только по уникальным агрегированным товарам, а не по всем строкам `items` попарно.

Используются:

- `normalized_name`;
- matcher-only форма исходного `name` без диакритики; persisted `normalized_name` не переписывается;
- `extract_product_features()`;
- равная комбинация `rapidfuzz.fuzz.token_set_ratio()` и `token_sort_ratio()`;
- предварительные token buckets по matcher-only форме;
- hard guards по объему, массе, типу единицы, проценту, multipack и corpus-backed вариантам товара.

Пороги score остаются `95`/`88`, но `high` дополнительно требует одинаковое покрытие значимых matcher-токенов. Односторонний вариантный признак, разные pack signatures, single-pack/multipack, разные quality grade или L/M egg size блокируют пару до scoring. Accepted pair показывает общий score, симметричное совпадение полного названия, несовпадающие значимые слова и совпавший multipack, когда эти evidence применимы.

Route `/products/suggestions` только показывает кандидатов. Он не присваивает `canonical_name`, не меняет `items.name`, не создает `products` table и не делает merge.

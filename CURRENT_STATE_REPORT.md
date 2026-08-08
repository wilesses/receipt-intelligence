# 1. Текущее состояние проекта

- Проект `Receipt Tracker v2` решает задачу импорта PDF-чеков, сохранения строк покупок в SQLite и просмотра расходов, категорий, товаров и цен через Flask UI. Главный поток подтверждён в `run.py`, `app/web/app.py`, `app/importer.py`, `app/db.py`, `app/analytics_service.py`.
- Реально работает: Flask-запуск через `run.py` (`create_app()`, `PORT`, `FLASK_DEBUG`), создание/расширение SQLite-схемы через `create_tables()`, список чеков `/`, просмотр чека `/receipt/<id>`, ручная загрузка PDF `/upload`, Gmail fetch `/gmail/fetch`, аналитика `/analytics`, JSON endpoints, профиль товара `/item/<name>`, объединение товаров `/products/merge`, подсказки похожих товаров `/products/suggestions`, review категорий `/products/review`, страница качества цен `/data-quality/prices`.
- Частично реализовано: парсер поддерживает Rimi и fallback Maxima, но не универсальный формат; Price & Quantity Model заполнена только у малой части текущей базы; `canonical_name` есть и используется, но импорт его не заполняет; ручные категории работают по `product_key`, но не по fuzzy-группам.
- Сломано/рискованно: фактическая БД старее текущего `CREATE TABLE`: `receipts.receipt_number` в базе не `UNIQUE`, `items.receipt_id/name/quantity/price/category` nullable, FK без `ON DELETE CASCADE`; `create_tables()` вызывается даже при старте UI и read-функциях, значит приложение может мигрировать БД при просмотре; `pytest` не установлен; прямых тестов парсера нет.
- Запуск: `python run.py`, порт по умолчанию `5000`; переменные `PORT` и `FLASK_DEBUG` читаются в `run.py`. Flask app создаётся в `app/web/app.py:create_app()`, который сразу вызывает `create_tables()`.

# 2. Архитектура

- Основные файлы:
  - `run.py` - web entrypoint.
  - `app/config.py` - пути `data/`, `data/uploads`, `data/pdf_receipts`, `data/receipts.db`.
  - `app/web/app.py` - Flask factory, Jinja globals.
  - `app/web/routes.py` - все web routes и часть бизнес-логики UI.
  - `app/db.py` - SQLite connection, schema, insert/read helpers.
  - `app/importer.py` - PDF text extraction, OCR fallback, import API.
  - `app/receipt_parser.py` - Rimi/Maxima parsing.
  - `app/category_keywords.py`, `app/category_rules.py` - словари, ручные правила категорий.
  - `app/product_normalizer.py`, `app/product_matcher.py` - нормализация и fuzzy suggestions.
  - `app/price_model.py` - расчет quantity/unit/package/normalized price.
  - `app/analytics_service.py` - SQL агрегации для графиков.
  - `app/gmail_fetcher.py` - IMAP Gmail attachment fetch.
- Основные точки входа: `run.py`; CLI `app/main.py`; batch/import scripts `app/importer.py`, `app/gmail_fetcher.py`, `app/backfill_normalized_names.py`, `app/backfill_price_data.py`, `app/categorize_existing_items.py`, `app/audit_categories.py`.
- Поток данных: PDF попадает через `/upload` или Gmail в `data/uploads`/`data/pdf_receipts`; `importer.extract_text_from_pdf()` читает текст через `pdfplumber`, при скане пробует OCR через Poppler/Tesseract; `parse_receipt()` выбирает Rimi или Maxima; `prepare_receipt_data()` добавляет category/price model поля; `add_receipt_with_items()` сохраняет receipt/items, применяет ручные category rules; UI и аналитика читают `items` + `receipts`.
- Жёсткие связи:
  - `app/db.py` импортирует category, rules, price model, normalizer и тем самым смешивает storage с бизнес-логикой.
  - `app/importer.py` и `app/db.py` оба рассчитывают price/category данные; логика частично дублируется.
  - `app/web/routes.py` содержит SQL, агрегации, формирование view models и mutations в одном файле.
  - `create_app()` вызывает `create_tables()`, поэтому web startup связан с миграциями.
  - Analytics SQL жёстко завязан на `items.price`, `items.category`, `canonical_name`.

# 3. База данных

- Актуальная фактическая база: `data/receipts.db`, read-only запрос показал 3 таблицы: `receipts`, `items`, `product_category_rules`.
- Фактическая схема:
  - `receipts`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `date TEXT`, `store TEXT`, `total REAL`, `receipt_number TEXT`.
  - `items`: `id`, `receipt_id`, `name`, `quantity`, `price`, `category`, `canonical_name`, `normalized_name`, `category_source`, `line_total`, `unit_price`, `quantity_unit`, `package_size`, `package_unit`, `normalized_unit_price`, `normalized_price_unit`, `price_parse_source`, `price_parse_confidence`, FK на `receipts(id)`.
  - `product_category_rules`: `id`, `product_key UNIQUE`, `category`, `source`, `created_at`, `updated_at`.
- Текущий код новой схемы строже фактической БД: `app/db.py:create_tables()` задаёт `receipt_number TEXT NOT NULL UNIQUE`, `items.receipt_id/name/quantity/price/category NOT NULL`, FK `ON DELETE CASCADE`, но существующая БД была создана раньше и `ALTER TABLE` не добавляет эти constraints.
- Миграции внесены прямо в `create_tables()`: добавление `category`, `canonical_name`, `normalized_name`, `category_source`, Price Model полей; индексы на даты, номер, store, item fields, category source, normalized price unit, product rules.
- Данные сейчас: 358 чеков, 3555 item rows, 16 category rules. Магазины: MAXIMA 224 чека на 5915.67 EUR за 2024-03-18..2026-07-08; RIMI 134 чека на 1504.63 EUR за 2025-06-01..2026-07-09.
- Качество данных: 365 строк имеют `canonical_name`; 3519 строк без `normalized_name`; 3530 строк без нормализованной единицы цены; 3532 строк без confidence или confidence < 0.75; 279 строк в `прочее`; есть старые категории-алиасы в данных (`молочка`, `ребенок`).
- Дубликаты: точных duplicate `receipt_number` не найдено, но есть receipt numbers с суффиксами `-2`/`-3`, например `2056-0030-5150-2121-2`, `2150-0050-7800-0927-3`; это похоже на повторно сохранённые PDF-файлы, но не доказывает одинаковый чек.
- Нормализация/категории: найдены конфликты категорий по одному normalized key, например `Kartupeļi frī AVIKO Zig Zag 750g` как `овощи` и `замороженные продукты`, `Piens Alma...` как `молочка` и `молочные`.
- Безопасно удалить БД и импортировать заново нельзя без подготовки: потеряются 16 manual rules, 365 canonical names и ручные категории; также не доказано, что набор PDF в `data/pdf_receipts`/`data/uploads` полностью и однозначно воспроизводит текущую БД.

# 4. Парсер чеков

- Поддерживаемые магазины: Rimi и fallback Maxima. Магазин определяется по наличию `rimi` в строках; если Rimi parser не вернул items, используется Maxima fallback.
- Rimi: дата ищется по строке с `laiks`, затем любая дата; total ищется с конца по `kopa`/`kopā`; товары ищутся regex `qty_line_pattern` с `gab|kg`, `X`, `unit_price`, optional `line_total`; название собирается из предыдущих строк с stop words; скидки учитываются через lookahead `atl`/`gala cena`.
- Maxima: дата ищется regex `YYYY-MM-DD` или `DD.MM.YYYY`; total по `kopā apmaksai`; товары по строкам вида `price X quantity`; название берётся из предыдущих 1-2 строк; скидочная цена ищется по `cena ar atlaidi`; `quantity_unit` всегда `unknown`.
- Количество/вес/цена: Rimi передает `quantity`, `quantity_unit` (`gab` или `kg`) и `unit_price`; Maxima передает `quantity` и `unknown`; `prepare_receipt_data()` затем прогоняет всё через `derive_price_data()`.
- Ошибки/неподдержанное: сканы требуют OCR; если Poppler/Tesseract нет, возвращается понятная ошибка; multipack Price Model помечает warning и не парсит; форматы вне Rimi/Maxima не поддержаны; Maxima unit quality слабая.
- Тесты парсера отсутствуют: в `tests/` есть tests для category engine, price model, product matcher, normalizer, но нет `test_receipt_parser.py` или importer parser tests.

# 5. Нормализация товаров

- `normalize_product_name()` приводит имя к lowercase, нормализует запятую в десятичных числах, разделители, латышские буквы, единицы (`l` to `ml`, `kg` to `g`, `gab`) и убирает technical tokens `d`, `pet`, `sk`.
- `extract_product_features()` достаёт `volume_ml`, `weight_g`, `percentage`.
- `rapidfuzz` используется в `app/product_matcher.py` через `fuzz.token_set_ratio`; пороги: high 95, possible 88.
- Canonical name хранится в `items.canonical_name`; display expression в UI/analytics: `COALESCE(NULLIF(items.canonical_name, ''), items.name)`.
- Ложные совпадения блокируются по разным volume/weight, проценту и variant tokens (`zero`, `classic`, `light`, etc.).
- Уже сделано: `/products/suggestions` показывает похожие товары; `/products/merge` вручную пишет `canonical_name`; тесты matcher покрывают same SKU, different volume, variants.
- Осталось: заполнить `normalized_name` для старой базы; решить, как массово подтверждать suggestions; не смешивать разные упаковки/варианты; добавить audit trail merge-операций.

# 6. Категоризация

- Категории назначаются словарно через `CATEGORY_KEYWORDS`, `PRIORITY`, `categorize_from_name()` и `categorize_with_source()`.
- Есть canonical categories и aliases: `молочка` to `молочные`, `сладости` to `сладости/снеки`, `кот` to `корма`, `ребенок` to `детское`.
- Категория хранится в `items.category`, источник в `items.category_source`; ручные правила хранятся в `product_category_rules`.
- Ручное исправление возможно в `/receipt/<id>`, `/item/<name>`, `/products/review`; route `update_item_category()` поддерживает scope `item` или `product`.
- Исправление на весь товар создаёт/обновляет `product_category_rules` и применяет category к matching `product_key`; будущий импорт наследует rule в `add_receipt_with_items()`.
- Исправление не распространяется на fuzzy-similar товары автоматически, только на exact `product_key`.
- Основные причины ошибок: неполный keyword словарь, OCR/диакритика, старые alias values в базе, отсутствие `normalized_name` у 3519 строк, неоднозначные товары (`farm frites`, `chips with cheese`, `dušas eļļa`).

# 7. Web UI и аналитика

- Список чеков `/`: работает; показывает table, поиск по магазину на клиенте, переход к чеку. Багов по коду не найдено.
- Просмотр чека `/receipt/<id>`: работает; показывает позиции, category source, price status, ручное редактирование категории. Частично: нет редактирования количества/цены/имени.
- Аналитика `/analytics` + `/analytics/data`: работает; фильтры start/end/store/category/item; графики категорий, месяцев, top items; trend endpoint. Частично: store filter в template статически содержит RIMI/MAXIMA, не берёт stores из БД.
- Фильтры: работают на analytics, product review, suggestions, price quality; index filter только client-side по store.
- Профиль товара `/item/<name>`: работает; history, stats, per-store block, aliases, trend chart, category edit. Частично: сравнение по магазинам есть как блок, не отдельная полноценная страница.
- Сравнение магазинов: частично; есть per-store агрегаты в item profile, отдельной страницы/матрицы сравнения магазинов нет.
- Графики: работают через Chart.js CDN в templates; зависят от интернета/CDN.
- Ручное редактирование: категории и canonical merge работают; редактирования чеков, сумм, строк, дат нет.
- Upload `/upload`: работает для PDF; сохраняет файл и импортирует; не удаляет uploaded файл после успешного импорта.
- Gmail `/gmail/fetch`: реализован; требует `.env` и IMAP credentials; в рамках проверки не запускался.
- Product suggestions `/products/suggestions`: работает read-only, dismissal только client-side.
- Product merge `/products/merge`: работает, меняет `canonical_name`.
- Product review `/products/review`: работает, меняет category rules.
- Price quality `/data-quality/prices`: работает read-only.

# 8. Последние изменения

- Git history содержит только 2 коммита:
  - `4c0d51e Initial project`.
  - `b1879fb Add colonical name` - добавлены Product Normalizer, RapidFuzz matcher, `canonical_name`/`normalized_name`, `/products/suggestions`, тесты normalizer/matcher.
- Последние 10 значимых изменений по Git + незакоммиченному diff + docs:
  1. Product Normalizer и `normalized_name` (`b1879fb`).
  2. RapidFuzz suggestion engine и `/products/suggestions` (`b1879fb`).
  3. `canonical_name` и `/products/merge` (`b1879fb` + текущий UI).
  4. Единый список canonical categories и aliases (`app/category_keywords.py`).
  5. `category_source` и `product_category_rules` (`app/db.py`, `app/category_rules.py`).
  6. Ручная категория всей товарной группы и наследование при импорте (`app/web/routes.py`, `app/db.py`).
  7. Category review screen `/products/review` и audit script (`app/web/routes.py`, `app/audit_categories.py`).
  8. Price & Quantity Model v2 (`app/price_model.py`, `app/db.py`).
  9. Rimi parser начал передавать `quantity_unit` и `unit_price`; Maxima явно ставит `unknown` (`app/receipt_parser.py`).
  10. Read-only price quality page и нормализованное сравнение цен в чеке/профиле (`app/web/routes.py`, templates, docs).
- Завершённые задачи по `docs/Roadmap.md`: Flask app, SQLite, upload, OCR fallback, Gmail import, Rimi/Maxima parser, analytics, product normalizer, suggestions, category engine v2, price model v2, price data quality.
- Последняя выполнявшаяся задача по незакоммиченным файлам и roadmap: Price & Quantity Model v2 + quality page + нормализованное сравнение цен.
- Незавершённые изменения: большое незакоммиченное рабочее дерево; фактическая БД не backfilled по `normalized_name`/price model; docs говорят "IN PROGRESS: нет активных изменений", но Git status показывает много незакоммиченного.
- Изменённые, но не закоммиченные tracked files: `PROJECT_GUIDE.md`, `app/category_keywords.py`, `app/db.py`, `app/importer.py`, `app/receipt_parser.py`, `app/web/app.py`, `app/web/routes.py`, `app/web/static/style.css`, `app/web/templates/base.html`, `app/web/templates/item.html`, `app/web/templates/receipt.html`, все 8 файлов в `docs/`.
- Untracked project files: `.agents/skills/...`, `PROJECT_GUIDE_old.md`, `app/audit_categories.py`, `app/backfill_category_sources.py`, `app/backfill_price_data.py`, `app/category_rules.py`, `app/price_model.py`, `app/web/templates/price_data_quality.html`, `app/web/templates/product_review.html`, `skills-lock.json`, `tests/test_category_engine.py`, `tests/test_price_model.py`.
- Untracked non-project/vault content: `obsidian_vault/` symlink раскрывает много файлов Obsidian; по правилу пользователя vault не трогался.

# 9. Технический долг и риски

## Критические

- Фактическая SQLite-схема слабее кода: нет `UNIQUE` на `receipt_number`, nullable поля, FK без cascade. Где: `data/receipts.db` vs `app/db.py:create_tables()`. Риск: дубликаты, orphan rows, несовпадение поведения dev/prod. Сложность: medium.
- Сильная нехватка backfill: 3519/3555 items без `normalized_name`, 3530 без normalized price unit. Где: текущая БД, `app/backfill_normalized_names.py`, `app/backfill_price_data.py`. Риск: suggestions, analytics и price comparisons работают хуже, чем код обещает. Сложность: medium.
- Нет файловых миграций/версий схемы. Где: `create_tables()` с `ALTER TABLE`. Риск: невозможно воспроизводимо понять состояние БД и constraints. Сложность: medium.

## Важные

- `app/web/routes.py` перегружен: routes, SQL, view models, mutations, price evaluation. Риск: изменения UI легко ломают бизнес-логику. Сложность: medium.
- Parser не покрыт тестами. Где: `app/receipt_parser.py`, `app/importer.py`. Риск: тихие ошибки импорта чеков. Сложность: medium.
- `create_tables()` вызывается из read helpers и `create_app()`. Риск: запуск UI меняет БД и маскирует миграции. Сложность: small/medium.
- `import_all_pdfs()` удаляет PDF после успешного импорта (`os.remove`). Риск: потеря исходника при ошибке качества данных после импорта. Сложность: small.
- Analytics использует `items.price`, а не всегда `line_total`; сейчас они совпадают при новом импорте, но модель допускает расхождение. Сложность: small.
- Category aliases не нормализованы в старых rows (`молочка`, `ребенок`). Риск: фильтры и отчеты раздваивают категории. Сложность: small.

## Косметические

- Опечатка в коммите `Add colonical name`. Сложность: small, но историю менять не стоит без причины.
- `app/analy` выглядит как лишний/непонятный файл. Сложность: small.
- Дублирующий CSS `app/web/templates/static/style.css` выглядит устаревшим, основной CSS в `app/web/static/style.css`. Сложность: small.
- `readme.md` пустой. Сложность: small.

# 10. Тесты

- Существуют:
  - `tests/test_product_normalizer.py` - normalizer/features.
  - `tests/test_product_matcher.py` - RapidFuzz matcher, volume/variant blocking.
  - `tests/test_price_model.py` - package size, normalized EUR/L/EUR/kg/EUR/piece, warnings, zero quantity.
  - `tests/test_category_engine.py` - category source, manual rules, inherited import, review route filters, item/product scope.
- Покрыты: normalizer, matcher, price model, category engine, часть Flask category review behavior через test client.
- Не покрыты критически: receipt parser Rimi/Maxima, PDF extraction/OCR diagnostics, `/upload`, Gmail fetch, analytics JSON, product merge mutation, DB migration constraints, duplicate import behavior.
- Проверки:
  - `python -m pytest -p no:cacheprovider` - не прошёл, потому что `pytest` не установлен: `No module named pytest`.
  - `$env:PYTHONDONTWRITEBYTECODE='1'; python -m unittest discover -s tests -v` - 22 теста, OK.

# 11. Документация

- В `/docs` находятся: `Analytics.md`, `Architecture.md`, `CategoryEngine.md`, `Database.md`, `DeveloperNotes.md`, `Parser.md`, `ProjectSummary.md`, `Roadmap.md`.
- Документация в целом отражает текущий незакоммиченный код: описаны category engine v2, product rules, price model v2, parser limitations, analytics pages.
- Устарело/противоречит:
  - `docs/Roadmap.md` пишет `IN PROGRESS: Нет активных изменений`, но Git status показывает много незакоммиченных изменений.
  - Документация описывает Price Model как реализованную, но текущая БД почти не backfilled.
  - Нужна явная пометка, что фактическая БД имеет старые constraints, отличные от `CREATE TABLE`.
  - Docs не должны считать старые alias categories уже нормализованными: в БД есть `молочка` и `ребенок`.
- Нужно обновить после следующей задачи: `docs/Database.md`, `docs/ProjectSummary.md`, `docs/Roadmap.md`, возможно `docs/DeveloperNotes.md`. В рамках этого анализа существующая документация не изменялась.

# 12. Следующий этап

1. Зафиксировать и обезопасить схему/миграции.
   - Цель: привести фактическую БД и кодовые ожидания к ясному состоянию.
   - Файлы: `app/db.py`, новый migration/check script или docs after approval.
   - Результат: понятный schema audit, решение по `receipt_number UNIQUE`, nullable fields, FK cascade.
   - Зависимости: backup БД.
   - Риски: изменение constraints на живой БД.
   - Сложность: medium.
2. Backfill `normalized_name` и Price Model только после backup/dry-run.
   - Цель: включить фактическую пользу normalizer/suggestions/price quality для старых данных.
   - Файлы: `app/backfill_normalized_names.py`, `app/backfill_price_data.py`, `data/receipts.db`.
   - Результат: заполнены `normalized_name`, `line_total`, `unit_price`, normalized price fields.
   - Зависимости: задача 1 или хотя бы backup.
   - Риски: массовое изменение данных.
   - Сложность: medium.
3. Добавить parser regression tests.
   - Цель: защитить импорт от поломок.
   - Файлы: `app/receipt_parser.py`, новые `tests/test_receipt_parser.py`.
   - Результат: тесты Rimi item/date/total/discount/unit и Maxima fallback.
   - Зависимости: собрать anonymized text fixtures.
   - Риски: реальные чеки могут содержать личные данные.
   - Сложность: medium.
4. Разделить `app/web/routes.py` на сервисы без изменения поведения.
   - Цель: снизить риск будущих UI/analytics/category изменений.
   - Файлы: `app/web/routes.py`, возможные `app/category_service.py`, `app/price_service.py`.
   - Результат: routes тоньше, тестировать проще.
   - Зависимости: тесты из задачи 3 и текущие tests.
   - Риски: регрессии routes.
   - Сложность: large.
5. Улучшить category cleanup.
   - Цель: убрать старые alias values и конфликтные категории.
   - Файлы: `app/category_keywords.py`, `app/category_rules.py`, `app/audit_categories.py`, DB data after approval.
   - Результат: `молочка`/`ребенок` нормализованы, конфликтные groups reviewable.
   - Зависимости: backup, clear manual-review process.
   - Риски: неправильное массовое исправление категорий.
   - Сложность: small/medium.

# 13. Рекомендуемая ближайшая задача

- Выбор: задача 1, schema audit/migration safety.
- Почему: сейчас код и фактическая БД расходятся; любые backfill, импорт или массовые исправления категорий будут рискованными, пока не ясно, какие constraints реально действуют.
- Завершение: есть read-only schema check command/script или документированный результат; принято решение по `receipt_number UNIQUE`, nullable item fields, FK cascade; перед любым write есть backup plan.
- Проверки: `python -m unittest discover -s tests -v`; read-only SQLite schema/count checks; `git status`; ручная проверка, что БД не изменилась до утвержденной write-операции.
- Пока не трогать: импорт чеков, удаление/пересоздание БД, Obsidian vault, массовый backfill, переписывание routes, изменение parser regex без regression tests.

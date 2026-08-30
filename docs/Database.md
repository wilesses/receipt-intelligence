# Database

## Общая информация

Проект использует SQLite-файл `data/receipts.db`. Подключение создается в `app/db.py:get_connection()`. При каждом подключении выполняется:

```sql
PRAGMA foreign_keys = ON
```

Создание и миграция минимальной схемы находятся в `app/db.py:create_tables()`.

Фактическая база на момент документирования содержит:

- `receipts`: 360 строк;
- `items`: 3580 строк;
- `items.normalized_name`: заполнено 3580 из 3580 строк;
- `sqlite_sequence`: служебная таблица SQLite для AUTOINCREMENT.

Важно: фактическая схема текущего `data/receipts.db` не полностью совпадает с `CREATE TABLE IF NOT EXISTS` в коде для новой базы. В существующей базе `receipt_number` не имеет `UNIQUE` constraint на уровне схемы, а внешний ключ `items.receipt_id` создан без `ON DELETE CASCADE`. Код дополнительно проверяет дубликаты перед вставкой.

## Таблица `receipts`

### Назначение

Хранит один импортированный чек: дату, магазин, итоговую сумму и номер/идентификатор PDF. Строка `receipts` является родителем для строк `items`.

### Фактические поля в `data/receipts.db`

| Поле | Тип | Null | Default | Primary key | Описание |
|---|---|---:|---|---:|---|
| `id` | `INTEGER` | да | нет | да | Внутренний ID чека, `AUTOINCREMENT`. |
| `date` | `TEXT` | да | нет | нет | Дата покупки. Код нормализует `DD.MM.YYYY` в `YYYY-MM-DD`. |
| `store` | `TEXT` | да | нет | нет | Магазин. Парсер сейчас выставляет `MAXIMA` или `RIMI`. |
| `total` | `REAL` | да | нет | нет | Итог чека. Если парсер не нашел итог, импорт считает сумму товаров. |
| `receipt_number` | `TEXT` | да | нет | нет | Идентификатор чека. При импорте берется из имени PDF без расширения. |

### Поля по текущему коду создания новой таблицы

`app/db.py:create_tables()` для новой базы задает:

```sql
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    store TEXT,
    total REAL NOT NULL DEFAULT 0,
    receipt_number TEXT NOT NULL UNIQUE
)
```

### Primary key

- `id`.

### Foreign key

- Нет. Это родительская таблица.

### Индексы

Фактические индексы:

```sql
CREATE INDEX idx_receipts_date ON receipts(date);
CREATE INDEX idx_receipts_number ON receipts(receipt_number);
CREATE INDEX idx_receipts_store ON receipts(store);
```

### Частое использование

- `/` читает `id`, `receipt_number`, `date`, `store`, `total` через `get_all_receipts()`.
- `/receipt/<id>` использует `id` для поиска позиций.
- `/analytics/data` фильтрует и группирует по `date`, `store`.
- `/item/<name>` соединяет покупки с датой и магазином.
- Gmail-импорт проверяет дубликаты по `receipt_number`.

### Поля, используемые аналитикой

- `date`: группировка по месяцам через `strftime('%Y-%m', receipts.date)`.
- `store`: фильтр магазина, группировка в профиле товара.
- `id`: связь с `items.receipt_id`.
- `total`: используется на главной странице и в `get_total_spent()`. Основные графики используют `items.price`, а не `receipts.total`.

## Таблица `items`

### Назначение

Хранит товарные строки чеков. Каждая строка относится к одному чеку через `receipt_id`. Эта таблица является главным источником аналитики: категории, топ товаров, динамика цены и профиль товара считаются по ней.

### Фактические поля в `data/receipts.db`

| Поле | Тип | Null | Default | Primary key | Описание |
|---|---|---:|---|---:|---|
| `id` | `INTEGER` | да | нет | да | Внутренний ID позиции, `AUTOINCREMENT`. |
| `receipt_id` | `INTEGER` | да | нет | нет | Ссылка на `receipts.id`. |
| `name` | `TEXT` | да | нет | нет | Исходное название товара из парсера. |
| `quantity` | `REAL` | да | нет | нет | Количество из чека. |
| `price` | `REAL` | да | нет | нет | Итоговая цена товарной строки. |
| `line_total` | `REAL` | да | нет | нет | Итоговая цена товарной строки в Price Model v2. Сохраняется равной `price` для совместимости старой аналитики. |
| `unit_price` | `REAL` | да | нет | нет | Цена за единицу из парсера или расчет `line_total / quantity`. |
| `quantity_unit` | `TEXT` | да | нет | нет | Единица количества: `piece`, `kg`, `g`, `l`, `ml`, `unknown`. |
| `package_size` | `REAL` | да | нет | нет | Размер упаковки, извлеченный из названия. |
| `package_unit` | `TEXT` | да | нет | нет | Единица упаковки: `ml`, `g`, `piece`, `unknown`. |
| `normalized_unit_price` | `REAL` | да | нет | нет | Нормализованная цена для сравнения: EUR/L, EUR/kg или EUR/piece. |
| `normalized_price_unit` | `TEXT` | да | нет | нет | Тип нормализованной цены: `eur_per_l`, `eur_per_kg`, `eur_per_piece`, `unknown`. |
| `price_parse_source` | `TEXT` | да | нет | нет | Источник интерпретации цены: `parser`, `package_name`, `weighted_inference`, `manual_correction`, `inferred_piece`, `service_line`, `rejected` или `unresolved`. |
| `price_parse_confidence` | `REAL` | да | нет | нет | Уверенность Price Model. |
| `category` | `TEXT` | да | нет | нет | Категория товара. Обычно назначается `categorize_from_name()`. |
| `canonical_name` | `TEXT` | да | нет | нет | Ручное объединенное название товара. Используется аналитикой вместо `name`, если заполнено. |
| `normalized_name` | `TEXT` | да | нет | нет | Нормализованное название для Product Normalizer и RapidFuzz suggestions. Не заменяет `name` и не влияет на `canonical_name`. |
| `category_source` | `TEXT` | нет | `rule` | нет | Источник категории: `rule`, `manual`, `inherited`, `fallback`. |

### Поля по текущему коду создания новой таблицы

`app/db.py:create_tables()` для новой базы задает:

```sql
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    canonical_name TEXT,
    normalized_name TEXT,
    quantity REAL NOT NULL DEFAULT 1,
    price REAL NOT NULL DEFAULT 0,
    line_total REAL,
    unit_price REAL,
    quantity_unit TEXT,
    package_size REAL,
    package_unit TEXT,
    normalized_unit_price REAL,
    normalized_price_unit TEXT,
    price_parse_source TEXT,
    price_parse_confidence REAL,
    category TEXT NOT NULL DEFAULT 'прочее',
    category_source TEXT NOT NULL DEFAULT 'rule',
    FOREIGN KEY(receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
)
```

`create_tables()` также добавляет `category`, `canonical_name`, `normalized_name`, `category_source` и поля Price Model v2, если этих колонок нет в старой базе. Таблица `items` не пересоздается.

### Primary key

- `id`.

### Foreign key

Фактическая БД:

```text
items.receipt_id -> receipts.id
ON UPDATE NO ACTION
ON DELETE NO ACTION
```

Код для новой БД:

```text
items.receipt_id -> receipts.id
ON DELETE CASCADE
```

### Индексы

Фактические индексы:

```sql
CREATE INDEX idx_items_receipt_id ON items(receipt_id);
CREATE INDEX idx_items_category ON items(category);
CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_items_canonical_name ON items(canonical_name);
CREATE INDEX idx_items_normalized_name ON items(normalized_name);
CREATE INDEX idx_items_category_source ON items(category_source);
CREATE INDEX idx_items_normalized_price_unit ON items(normalized_price_unit);
```

### Частое использование

- `receipt_id`: загрузка позиций конкретного чека.
- `name`: поиск, отображение исходного названия, автодополнение.
- `canonical_name`: ручное объединение похожих товаров; executable canonical-or-raw contract находится в `app/product_identity.py`.
- `normalized_name`: поиск похожих товаров и Suggestions; не user-facing identity.

- `quantity`: расчет цены за единицу.
- `price`: сумма расходов, графики, топ товаров, профиль товара.
- `line_total`: явная итоговая цена строки для Price Model; сейчас равна `price`.
- `unit_price`: цена за единицу из parser output или расчетная цена.
- `quantity_unit`: источник понимания штуки/кг/литры/unknown.
- `package_size`, `package_unit`: размер упаковки из названия товара.
- `normalized_unit_price`, `normalized_price_unit`: база для сравнения EUR/L, EUR/kg или EUR/piece.
- `price_parse_source`, `price_parse_confidence`: диагностика качества ценовых данных.
- `category`: график категорий и фильтр категории.

### Поля, используемые аналитикой

- `price`: сумма по категориям, месяцам, товарам, магазинам.
- `quantity`: цена за единицу в `get_item_trend()`, `build_price_evaluation()`, `build_receipt_price_analysis()`.
- `category`: фильтр и группировка категорий.
- `name` и `canonical_name`: группировка товаров, профиль товара, автодополнение.
- `normalized_name`: не используется существующей аналитикой; используется только Product Suggestions.
- `normalized_unit_price`, `normalized_price_unit`: используются в `/item/<name>` и `/receipt/<id>` как предпочтительная база сравнения цены, если есть достаточно истории.
- `receipt_id`: join с `receipts`.

### Price & Quantity Model v2

Модель цен реализована в `app/price_model.py`. Она evidence-first: сначала использует подтвержденные parser data, затем однозначную упаковку из названия или математически согласованный weighted inference. Она не меняет `items.name`, `items.canonical_name`, `items.normalized_name`, `items.category`, `items.quantity` и `items.price`.

Семантика:

- `items.price` остается legacy-полем итоговой суммы строки и продолжает питать существующую аналитику;
- `items.line_total` явно хранит ту же итоговую сумму строки;
- `items.unit_price` хранит цену за единицу из парсера или расчет `line_total / quantity`;
- `quantity_unit` приходит из Rimi parser для `gab`/`kg`, у Maxima пока `unknown`;
- `package_size` и `package_unit` извлекаются из названия товара;
- `normalized_unit_price` считается как EUR/L, EUR/kg или EUR/piece;
- `price_parse_confidence` используется экраном качества данных `/data-quality/prices`.

Confidence отражает качество evidence:

- `0.95` — единица и цена подтверждены parser data;
- `0.85` — однозначный размер упаковки извлечен из названия (`package_name`);
- `0.75` — весовая единица выведена только при согласованности `quantity * unit_price ~= line_total` (`weighted_inference`);
- `0.70` — предположение поштучной покупки (`inferred_piece`), не примененное к основной базе;
- `0.85` при `manual_correction` — policy confidence: пользователь подтвердил structured evidence, прошедшее общие structural guards; это не вероятность истинности;
- `NULL` — нормализованная цена не рассчитана.

Служебные позиции (депозит, упаковка, бумажные и многоразовые пакеты, подтвержденные кассовые строки) получают `service_line` и остаются без нормализованной цены. Узкие правила не меняют исходную категорию. Multipack, неоднозначные упаковки, parser contamination и malformed data отклоняются или остаются unresolved.

Price Quality может исправить одну `CORRECTABLE_V1` строку без изменения schema. Редактируются только `quantity_unit`, `package_size`, `package_unit`; успешный apply пересчитывает и обновляет `unit_price`, `normalized_unit_price`, `normalized_price_unit`, `price_parse_source`, `price_parse_confidence`. `name`, `canonical_name`, `normalized_name`, `receipt_id`, `quantity`, `price`, `line_total`, `category` и `category_source` остаются неизменными.

Preview не открывает write transaction. Signed token является integrity/stale-state mechanism и содержит `item_id`, hash before-state, proposed fields и projected derived fields. Apply выполняет `BEGIN IMMEDIATE`, reload строки, повторный `derive_price_data()`, сравнение свежей projection с token и UPDATE ровно одной строки с optimistic before-state predicates. Значения derived fields из token напрямую не сохраняются.

Missing `line_total`, arithmetic mismatch, unresolved multipack, service/parser contamination и любой remaining blocking warning исключают manual apply. Stale/deleted rows, измененное proposal и SQLite errors откатываются.

Backfill существующих данных находится в `app/backfill_price_data.py`:

```text
python -m app.backfill_price_data --sources package_name,weighted_inference
python -m app.backfill_price_data --apply --sources package_name,weighted_inference
```

Dry-run является режимом по умолчанию и ничего не записывает. Write-режим требует явный `--apply` и явный allowlist источников. Сейчас разрешены только `package_name` и `weighted_inference`; полный apply без отдельного решения запрещен. Field-level merge заполняет отсутствующие значения и не заменяет существующее значение более слабым результатом. High-confidence conflicts и IDs 3544, 3578, 3579, 3581 сохраняются для manual review.

Перед write скрипт начинает транзакцию, использует SQLite Backup API через `app.db:backup_database()` и принимает backup только после `PRAGMA integrity_check = ok`; тест подтверждает включение committed WAL data. Завершенный selective backfill обновил 2184 строки: 2179 `package_name` и 5 `weighted_inference`; итоговые normalized units — 1664 `eur_per_kg`, 452 `eur_per_l`, 68 `eur_per_piece`. После него заполнено: `line_total`, `unit_price`, `quantity_unit`, `package_unit`, `normalized_price_unit`, `price_parse_source`, `price_parse_confidence` — по 2239 строк; `package_size` — 2218; `normalized_unit_price` — 2225. Повторный selective dry-run показывает 0 изменений.

Нормализованная цена остается unresolved у 1094 строк. Selective audit отдельно исключает `service_line` 656, `inferred_piece` 261, rejected 154, unresolved-source 281 и high-confidence conflicts 4; группы могут пересекаться и не должны суммироваться как общий unresolved count. Полный apply не выполнялся.

## Таблица `sqlite_sequence`

### Назначение

Служебная таблица SQLite. Создается автоматически для таблиц с `AUTOINCREMENT`.

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `name` | без явного типа | Имя таблицы. |
| `seq` | без явного типа | Последнее значение sequence. |

Проект напрямую эту таблицу не читает и не изменяет.

## Таблица `product_category_rules`

### Назначение

Хранит ручное решение категории для товарной группы. Правило применяется к будущим импортам как `category_source = inherited` и к текущей группе при ручном выборе как `category_source = manual`.

### Поля

| Поле | Тип | Null | Default | Primary key | Описание |
|---|---|---:|---|---:|---|
| `id` | `INTEGER` | нет | нет | да | Внутренний ID правила. |
| `product_key` | `TEXT` | нет | нет | нет | Устойчивый ключ группы: normalized `canonical_name`, иначе `normalized_name`, иначе normalized `items.name`. |
| `category` | `TEXT` | нет | нет | нет | Каноническая категория. |
| `source` | `TEXT` | нет | `manual` | нет | Сейчас хранится `manual`. |
| `created_at` | `TEXT` | нет | нет | нет | UTC timestamp создания. |
| `updated_at` | `TEXT` | нет | нет | нет | UTC timestamp последнего изменения. |

### Constraints и индексы

```sql
product_key TEXT NOT NULL UNIQUE
CREATE INDEX idx_product_category_rules_key ON product_category_rules(product_key);
```

Таблица не объединяет товары и не меняет `canonical_name`.

## Связи

```text
receipts
  id INTEGER PRIMARY KEY
  date TEXT
  store TEXT
  total REAL
  receipt_number TEXT

    1
    |
    | items.receipt_id -> receipts.id
    |
    N

items
  id INTEGER PRIMARY KEY
  receipt_id INTEGER
  name TEXT
  canonical_name TEXT
  normalized_name TEXT
  line_total REAL
  unit_price REAL
  quantity_unit TEXT
  package_size REAL
  package_unit TEXT
  normalized_unit_price REAL
  normalized_price_unit TEXT
  price_parse_source TEXT
  price_parse_confidence REAL
  category_source TEXT
  quantity REAL
  price REAL
  category TEXT
```

## ER Diagram

```text
+------------------+          +----------------------+
| receipts         |          | items                |
+------------------+          +----------------------+
| PK id            |<---------| FK receipt_id        |
| date             |          | PK id                |
| store            |          | name                 |
| total            |          | canonical_name       |
| receipt_number   |          | normalized_name      |
+------------------+          | price                |
                              | quantity             |
                              | category             |
                              +----------------------+
```

## SQL-запросы, влияющие на схему и данные

### Вставка чека

`app/db.py:add_receipt_with_items()`:

```sql
SELECT id FROM receipts WHERE receipt_number = ?;

INSERT INTO receipts (date, store, total, receipt_number)
VALUES (?, ?, ?, ?);

INSERT INTO items (
    receipt_id, name, normalized_name, quantity, price, line_total, unit_price,
    quantity_unit, package_size, package_unit, normalized_unit_price,
    normalized_price_unit, price_parse_source, price_parse_confidence,
    category, category_source
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
```

`normalized_name` считается из `items.name` через `normalize_product_name()`. Категория получает `category_source`: `inherited`, если найдено manual rule; иначе `rule` или `fallback`. `canonical_name` при импорте не заполняется.

Поля Price Model считаются через `app.price_model.derive_price_data()` в общей точке вставки `add_receipt_with_items()`.

### Backfill normalized_name

Скрипт `app/backfill_normalized_names.py` выбирает только строки:

```sql
SELECT id, name
FROM items
WHERE normalized_name IS NULL OR TRIM(normalized_name) = ''
ORDER BY id
```

Обычный режим обновляет только `normalized_name`:

```sql
UPDATE items SET normalized_name = ? WHERE id = ?
```

Dry-run ничего не записывает.

### Объединение товаров

`app/web/routes.py:products_merge_submit()`:

```sql
UPDATE items
SET canonical_name = ?
WHERE name IN (...)
   OR canonical_name IN (...)
   OR <shared effective identity expression> IN (...);
```

### Ручная смена категории

`app/web/routes.py:update_item_category()`:

```sql
UPDATE items SET category = ? WHERE id = ?;
```

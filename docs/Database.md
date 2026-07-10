# Database

## Общая информация

Проект использует SQLite-файл `data/receipts.db`. Подключение создается в `app/db.py:get_connection()`. При каждом подключении выполняется:

```sql
PRAGMA foreign_keys = ON
```

Создание и миграция минимальной схемы находятся в `app/db.py:create_tables()`.

Фактическая база на момент документирования содержит:

- `receipts`: 355 строк;
- `items`: 3519 строк;
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
| `category` | `TEXT` | да | нет | нет | Категория товара. Обычно назначается `categorize_from_name()`. |
| `canonical_name` | `TEXT` | да | нет | нет | Ручное объединенное название товара. Используется аналитикой вместо `name`, если заполнено. |
| `normalized_name` | `TEXT` | да | нет | нет | Нормализованное название для Product Normalizer и RapidFuzz suggestions. Не заменяет `name` и не влияет на `canonical_name`. |

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
    category TEXT NOT NULL DEFAULT 'прочее',
    FOREIGN KEY(receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
)
```

`create_tables()` также добавляет `category`, `canonical_name` и `normalized_name`, если этих колонок нет в старой базе.

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
```

### Частое использование

- `receipt_id`: загрузка позиций конкретного чека.
- `name`: поиск, отображение исходного названия, автодополнение.
- `canonical_name`: объединение похожих товаров. В аналитике используется выражение:
- `normalized_name`: поиск похожих товаров в `app/product_matcher.py`.

```sql
COALESCE(NULLIF(items.canonical_name, ''), items.name)
```

- `quantity`: расчет цены за единицу.
- `price`: сумма расходов, графики, топ товаров, профиль товара.
- `category`: график категорий и фильтр категории.

### Поля, используемые аналитикой

- `price`: сумма по категориям, месяцам, товарам, магазинам.
- `quantity`: цена за единицу в `get_item_trend()`, `build_price_evaluation()`, `build_receipt_price_analysis()`.
- `category`: фильтр и группировка категорий.
- `name` и `canonical_name`: группировка товаров, профиль товара, автодополнение.
- `normalized_name`: не используется существующей аналитикой; используется только Product Suggestions.
- `receipt_id`: join с `receipts`.

## Таблица `sqlite_sequence`

### Назначение

Служебная таблица SQLite. Создается автоматически для таблиц с `AUTOINCREMENT`.

### Поля

| Поле | Тип | Описание |
|---|---|---|
| `name` | без явного типа | Имя таблицы. |
| `seq` | без явного типа | Последнее значение sequence. |

Проект напрямую эту таблицу не читает и не изменяет.

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

INSERT INTO items (receipt_id, name, normalized_name, quantity, price, category)
VALUES (?, ?, ?, ?, ?, ?);
```

`normalized_name` считается из `items.name` через `normalize_product_name()`. `canonical_name` при импорте не заполняется.

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
   OR COALESCE(NULLIF(items.canonical_name, ''), items.name) IN (...);
```

### Ручная смена категории

`app/web/routes.py:update_item_category()`:

```sql
UPDATE items SET category = ? WHERE id = ?;
```

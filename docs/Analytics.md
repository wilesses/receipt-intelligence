# Analytics

## Где находится аналитика

Основные файлы:

- `app/analytics_service.py` - JSON-данные для страницы `/analytics`;
- `app/web/routes.py` - SQL и Python-расчеты для страниц `/`, `/analytics`, `/item/<name>`, `/receipt/<id>`;
- `app/web/templates/analytics.html` - Chart.js-графики;
- `app/web/templates/item.html` - график динамики цены товара;
- `app/web/templates/receipt.html` - оценка позиций чека;
- `app/web/templates/index.html` - сводка чеков на главной.

`app/analytics.py` пустой.

## Общие правила аналитики

Для группировки товаров используется выражение:

```sql
COALESCE(NULLIF(items.canonical_name, ''), items.name)
```

Оно задано как `PRODUCT_NAME_EXPR` в:

- `app/analytics_service.py`;
- `app/web/routes.py`.

Если `canonical_name` заполнен, аналитика считает товар по нему. Иначе используется исходный `items.name`.

## KPI

Реально считаются такие показатели:

- количество чеков на `/`;
- сумма чеков на `/`;
- дата последнего чека на `/`;
- общий расход на `/analytics`;
- средний расход в месяц на `/analytics`;
- расходы по категориям;
- расходы по месяцам;
- топ-10 товаров по сумме;
- цена за единицу товара по месяцам;
- средняя цена товара;
- минимальная и максимальная цена товара;
- всего куплено товара;
- общая сумма по товару;
- количество покупок товара по магазинам;
- сумма товара по магазинам;
- последняя цена товара;
- медианная цена товара;
- отклонение последней цены от средней и медианы;
- количество товаров в чеке;
- количество позиций дешевле обычного;
- количество позиций дороже обычного;
- количество позиций без достаточной истории.

## Страница `/`

### Откуда берутся данные

Route: `app/web/routes.py:index()`.

Данные берутся из `app/db.py:get_all_receipts()`.

SQL:

```sql
SELECT id, receipt_number, date, store, total
FROM receipts
ORDER BY date DESC, id DESC
```

Шаблон: `app/web/templates/index.html`.

### Вычисления

SQL:

- выбирает список чеков;
- сортирует по дате и ID.

Python/Jinja:

- `receipts|length` - количество чеков;
- `receipts|sum(attribute=4)` - сумма чеков;
- `receipts[0][2]` - дата последнего чека;
- форматирование суммы до 2 знаков.

JavaScript в шаблоне:

- поиск по магазину в таблице;
- сортировка строк по ID, дате и сумме;
- обновление счетчика найденных чеков.

### Графики

На `/` графиков нет.

## Страница `/analytics`

### Откуда берутся данные

Route страницы: `app/web/routes.py:analytics()`.

Шаблон получает только список категорий:

```python
render_template("analytics.html", category_options=get_category_options())
```

Сами данные грузятся браузером:

- `/analytics/data`;
- `/analytics/item_trend`.

### Категории для фильтра

`get_category_options()`:

```sql
SELECT DISTINCT category
FROM items
WHERE category IS NOT NULL AND TRIM(category) != ''
ORDER BY LOWER(category)
```

Если `прочее` нет в списке, функция добавляет ее.

### `/analytics/data`

Route: `app/web/routes.py:analytics_data()`.

Функция: `app/analytics_service.py:get_analytics_data()`.

Фильтры строит `_build_filters(start, end, store, category, item)`:

```sql
receipts.date >= ?
receipts.date <= ?
LOWER(receipts.store) = LOWER(?)
items.category = ?
(COALESCE(NULLIF(items.canonical_name, ''), items.name) LIKE ? OR items.name LIKE ?)
```

Расходы по категориям:

```sql
SELECT COALESCE(items.category, 'прочее'), SUM(items.price)
FROM items
JOIN receipts ON items.receipt_id = receipts.id
{where_clause}
GROUP BY COALESCE(items.category, 'прочее')
ORDER BY SUM(items.price) DESC
```

Расходы по месяцам:

```sql
SELECT strftime('%Y-%m', receipts.date), SUM(items.price)
FROM items
JOIN receipts ON items.receipt_id = receipts.id
{where_clause}
GROUP BY strftime('%Y-%m', receipts.date)
ORDER BY strftime('%Y-%m', receipts.date)
```

Топ товаров:

```sql
SELECT COALESCE(NULLIF(items.canonical_name, ''), items.name) AS product_name, SUM(items.price)
FROM items
JOIN receipts ON items.receipt_id = receipts.id
{where_clause}
GROUP BY product_name
ORDER BY SUM(items.price) DESC
LIMIT 10
```

Общий расход:

```sql
SELECT SUM(items.price)
FROM items
JOIN receipts ON items.receipt_id = receipts.id
{where_clause}
```

Python:

- округляет значения до 2 знаков;
- собирает `labels` и `values`;
- считает `monthly_average = sum(month_values) / len(month_values)`.

### Графики на `/analytics`

`analytics.html` строит через Chart.js:

- doughnut `categoryChart` - категории;
- line `monthChart` - расходы по месяцам;
- bar `topItemsChart` - топ товаров;
- line `trendChart` - динамика цены выбранного товара.

Ссылки под топом ведут на `/item/<name>`.

### `/analytics/item_trend`

Route: `app/web/routes.py:item_trend()`.

Функция: `app/analytics_service.py:get_item_trend(item_name)`.

SQL:

```sql
SELECT strftime('%Y-%m', receipts.date) AS ym,
       SUM(items.price) AS total,
       SUM(items.quantity) AS qty
FROM items
JOIN receipts ON items.receipt_id = receipts.id
WHERE (COALESCE(NULLIF(items.canonical_name, ''), items.name) LIKE ?
       OR items.name LIKE ?)
GROUP BY ym
ORDER BY ym
```

Python:

- пропускает строки без `qty` или `total`;
- считает `unit_price = total / qty`;
- оставляет только `0 < unit_price <= 1000`;
- округляет цену за единицу до 2 знаков.

## Страница `/item/<name>`

### Откуда берутся данные

Route: `app/web/routes.py:item_profile(name)`.

Имя декодируется через `unquote(name)`.

Шаблон: `app/web/templates/item.html`.

### История покупок

SQL:

```sql
SELECT receipts.date, receipts.store, items.quantity, items.price,
       items.receipt_id, items.id, items.category, items.name,
       COALESCE(NULLIF(items.canonical_name, ''), items.name) AS product_name
FROM items
JOIN receipts ON items.receipt_id = receipts.id
WHERE (COALESCE(NULLIF(items.canonical_name, ''), items.name) = ? OR items.name = ?)
ORDER BY receipts.date
```

Используется для таблицы покупок, формы смены категории и оценки цены.

### Агрегаты товара

SQL:

```sql
SELECT
    ROUND(AVG(CASE WHEN quantity > 0 THEN price / quantity ELSE NULL END), 2),
    ROUND(MIN(CASE WHEN quantity > 0 THEN price / quantity ELSE NULL END), 2),
    ROUND(MAX(CASE WHEN quantity > 0 THEN price / quantity ELSE NULL END), 2),
    SUM(quantity),
    ROUND(SUM(price), 2)
FROM items
WHERE (COALESCE(NULLIF(items.canonical_name, ''), items.name) = ? OR items.name = ?)
```

Считается SQL:

- средняя цена за единицу;
- минимальная цена за единицу;
- максимальная цена за единицу;
- сумма количества;
- сумма расходов.

### Разрез по магазинам

SQL:

```sql
SELECT receipts.store, COUNT(*), ROUND(SUM(items.price), 2)
FROM items
JOIN receipts ON items.receipt_id = receipts.id
WHERE (COALESCE(NULLIF(items.canonical_name, ''), items.name) = ? OR items.name = ?)
GROUP BY receipts.store
```

### Алиасы товара

SQL:

```sql
SELECT DISTINCT items.name
FROM items
WHERE (COALESCE(NULLIF(items.canonical_name, ''), items.name) = ? OR items.name = ?)
ORDER BY LOWER(items.name)
```

### Оценка текущей цены

Функция: `app/web/routes.py:build_price_evaluation(rows)`.

Python:

- из каждой покупки считает `unit_price = price / quantity`;
- если точек меньше 3, возвращает `has_enough_data = False`;
- считает среднюю, медианную, минимум, максимум, последнюю цену;
- если последняя цена `<= median * 0.9`, статус `Выгодная цена`;
- если последняя цена `>= median * 1.15`, статус `Дороже обычного`;
- иначе статус `Обычная цена`;
- считает отклонение от средней и медианы.

### Графики

`item.html` загружает `/analytics/item_trend?item=<name>` и строит line chart цены за единицу.

## Страница `/receipt/<id>`

### Откуда берутся данные

Route: `app/web/routes.py:view_receipt(receipt_id)`.

Шаблон: `app/web/templates/receipt.html`.

SQL:

```sql
SELECT id, name, quantity, price, category,
       COALESCE(NULLIF(items.canonical_name, ''), items.name) AS display_name
FROM items
WHERE receipt_id = ?
ORDER BY id
```

Python:

- приводит `quantity` и `price` к `float`;
- суммирует `total_sum += price`;
- подставляет категорию `прочее`, если категория пустая;
- вызывает `build_receipt_price_analysis(conn, items)`.

### Анализ цен внутри чека

Функция: `app/web/routes.py:build_receipt_price_analysis(conn, receipt_items)`.

Для каждого товара собирается история:

```sql
SELECT quantity, price
FROM items
WHERE COALESCE(NULLIF(items.canonical_name, ''), items.name) = ?
  AND quantity > 0
  AND price > 0
ORDER BY id
```

Python:

- считает историю `unit_prices`;
- если у товара нет цены, количества или меньше 3 исторических точек, помечает как `insufficient`;
- считает текущую цену `price / quantity`;
- считает медиану;
- если текущая цена `<= median * 0.9`, позиция `cheap`;
- если текущая цена `>= median * 1.15`, позиция `expensive`;
- иначе позиция `normal`;
- считает процент отклонения;
- собирает summary: `total_items`, `cheap`, `expensive`, `insufficient`.

### Графики

На `/receipt/<id>` графиков нет. Есть таблица позиций и блок итогов по чеку.

## Что считается SQL, что Python

SQL:

- выборка чеков;
- фильтрация по датам, магазину, категории, товару;
- суммы по категориям;
- суммы по месяцам;
- топ товаров;
- общая сумма по фильтру;
- агрегаты товара;
- разрез товара по магазинам;
- алиасы товара;
- история товара по месяцам.

Python:

- сбор JSON-структур для графиков;
- средний расход в месяц;
- цена за единицу в тренде;
- средняя/медианная/минимальная/максимальная/последняя цена в `build_price_evaluation()`;
- оценка выгодно/дорого/обычно;
- анализ цен товаров внутри чека;
- сумма позиций чека для отображения `total_sum`.


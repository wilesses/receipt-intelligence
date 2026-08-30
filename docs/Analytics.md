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

User-facing товары группируются через `app/product_identity.py`. Контракт один: непустой persisted `canonical_name`, иначе raw receipt `items.name`. `effective_product_identity_sql()` и row helper переиспользуются в Analytics, Product Dossier, autocomplete, Home, deviation, Store Comparison, discovery и Merge.

`normalized_name` помогает искать и строить Suggestions, но не является identity и не объединяет товары автоматически. Category `app/category_rules.py:get_product_key()` намеренно использует отдельную normalized-группировку для правил категорий.

Точный effective identity разрешается первым. Raw alias принимается только если однозначно соответствует одной effective identity. Тренд и Dossier после разрешения используют exact equality, не `LIKE` и не объединяющий `OR name = ?`.

Category Engine v2 не меняет формулы аналитики. Графики и KPI продолжают использовать `items.category`. После ручного изменения категории всей группы аналитика автоматически отражает новое значение, потому что обновляется та же колонка `items.category`.

Price & Quantity Model v2 не меняет основные графики расходов: они продолжают использовать `items.price`. Price intelligence и item trend используют только safe persisted `normalized_unit_price` с явным `normalized_price_unit`; legacy `price / quantity` fallback отсутствует.

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
- месячная медиана safe normalized price товара с явным €/kg, €/L или €/piece;
- число eligible observations в каждой точке тренда;
- общая оплаченная сумма по товару;
- количество покупок товара по магазинам;
- сумма товара по магазинам;
- последняя safe normalized price и её отклонение от медианы eligible prior history;
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

`get_category_options()` возвращает canonical list из `app/category_keywords.py:CANONICAL_CATEGORIES`. Старые значения в БД не удаляются автоматически, но dropdown использует единый список.

### `/analytics/data`

Route: `app/web/routes.py:analytics_data()`.

Функция: `app/analytics_service.py:get_analytics_data()`.

Фильтры строит `_build_filters(start, end, store, category, item)`:

```sql
receipts.date >= ?
receipts.date <= ?
LOWER(receipts.store) = LOWER(?)
items.category = ?
(<shared effective identity expression> LIKE ? OR items.name LIKE ?)
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
SELECT <shared effective identity expression> AS product_name, SUM(items.price)
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

`analytics.html` и `app/web/static/analytics.js` строят через Chart.js:

- horizontal bar `categoryChart` - категории;
- line `monthChart` - расходы по месяцам;
- horizontal bar `topItemsChart` - топ товаров;
- line `trendChart` - динамика цены выбранного товара.

Ссылки под топом ведут на `/item/<name>`.

Повторная отрисовка после фильтра и смены темы использует единый lifecycle. Перед созданием каждого графика код сверяет локальную ссылку на instance с владельцем canvas из `Chart.getChart(canvas)`, уничтожает оба без двойного destroy и только затем вызывает `new Chart()`. Если конструктор успел зарегистрировать canvas, но завершился ошибкой, leaked instance также уничтожается, а вместо пустой области показывается текстовое состояние ошибки. Пустой dataset остаётся отдельным нормальным empty state и не считается ошибкой рендера.

### `/analytics/item_trend`

Route: `app/web/routes.py:item_trend()`.

Функция: `app/analytics_service.py:get_item_trend(item_name)`.

Поток:

1. `resolve_effective_product_identity()` разрешает exact identity или один однозначный raw alias.
2. SQL выбирает все observations только через `WHERE <effective_identity> = ?` и сортирует `(date, receipt_id, item_id)`.
3. `build_normalized_price_trend()` применяет `app.price_deviation.is_eligible_price_observation()`:
   - положительная normalized EUR/kg, EUR/L или EUR/piece;
   - допустимый source и confidence `>= 0.75`;
   - согласованные quantity/unit price/line total в пределах €0.02;
   - валидные date/store;
   - без blocking diagnostics и unresolved identity.
4. Python группирует eligible observations по календарному месяцу и считает медиану. JSON содержит `labels`, `values`, `observation_counts`, machine unit и явный `unit_label`.

Fail-closed состояния возвращают `status = insufficient` и пустые точки:

- неизвестный или неоднозначный товар;
- нет eligible normalized history;
- несовместимые denominators внутри identity;
- нет observations с валидным месяцем.

`price / quantity`, средняя по строкам и wildcard grouping здесь не используются.

## Страница `/item/<name>`

### Откуда берутся данные

Route: `app/web/routes.py:item_profile(name)`.

Flask декодирует `<path:name>` один раз; route не вызывает повторный `unquote()`.

Шаблон: `app/web/templates/item.html`.

### История покупок

SQL:

```sql
SELECT receipts.date, receipts.store, items.quantity, items.price,
       items.receipt_id, items.id, items.category, items.category_source, items.name,
       <shared effective identity expression> AS product_name,
       items.normalized_unit_price, items.normalized_price_unit,
       items.line_total, items.unit_price, items.package_size, items.package_unit
FROM items
JOIN receipts ON items.receipt_id = receipts.id
WHERE <shared effective identity expression> = ?
ORDER BY receipts.date
```

Перед SQL route разрешает exact effective identity или один однозначный raw alias. История используется для Purchase Register, формы смены категории и shared price evaluation.

### Агрегаты товара

SQL:

```sql
SELECT ROUND(SUM(COALESCE(line_total, price)), 2)
FROM items
WHERE <shared effective identity expression> = ?
```

Summary показывает только общую оплаченную сумму. Legacy average/min/max `price / quantity` и неоднозначный total quantity удалены.

### Разрез по магазинам

SQL:

```sql
SELECT receipts.store, COUNT(*), ROUND(SUM(COALESCE(items.line_total, items.price)), 2)
FROM items
JOIN receipts ON items.receipt_id = receipts.id
WHERE <shared effective identity expression> = ?
GROUP BY receipts.store
```

### Алиасы товара

SQL:

```sql
SELECT DISTINCT items.name
FROM items
WHERE <shared effective identity expression> = ?
ORDER BY LOWER(items.name)
```

### Оценка текущей цены

`build_price_evaluation(current_observation, observations)` адаптирует результат общего `app/price_deviation.py:evaluate_price_deviation()` для Dossier. Контракт:

- exact shared effective identity и тот же normalized-price eligibility;
- медиана минимум трёх eligible prior observations того же denominator за 180 дней;
- текущая строка не входит в baseline;
- `<= -10%` cheaper, `>= +15%` more expensive, иначе normal;
- без legacy fallback;
- insufficient reason отображается через общий evidence-presentation adapter.

### Графики

`item.html` загружает `/analytics/item_trend?item=<effective identity>` и строит line chart месячной медианы safe normalized price с явным denominator.

## Страница `/receipt/<id>`

### Откуда берутся данные

Route: `app/web/routes.py:view_receipt(receipt_id)`.

Шаблон: `app/web/templates/receipt.html`.

SQL:

```sql
SELECT id, name, quantity, price, category,
       category_source, normalized_unit_price, normalized_price_unit,
       line_total, unit_price, package_size, package_unit,
       <shared effective identity expression> AS display_name
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

`build_receipt_price_analysis()` загружает observations той же shared effective identity и передает каждую текущую строку в общий `evaluate_price_deviation()`.

Python:

- использует только eligible normalized price того же denominator;
- берет минимум три prior observations за 180 дней;
- исключает текущую строку и более поздние строки по `(date, receipt_id, item_id)`;
- не использует `price / quantity` fallback;
- переводит machine statuses в receipt summary `cheap`, `expensive`, `normal`, `insufficient`.

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

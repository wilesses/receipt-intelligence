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
- `app/product_identity.py` - единственный canonical-or-raw user-facing identity contract и его SQL/row helpers.
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

Local Research не должен брать список из `get_analytics_data()["top"]`. Использовать существующий `/autocomplete/item_names`: он ищет по shared effective identity, raw `items.name` и `normalized_name`, но возвращает только distinct effective identities. Default response остаётся списком имён; `details=1` возвращает `{name, profile_url}`, где URL строится через `url_for("item_profile", name=...)`. UI обязан хранить выбранный результат отдельно от текста input и сразу инвалидировать выбор при редактировании. Route Product Dossier использует `<path:name>`; Flask уже декодирует path parameter, поэтому повторный `unquote()` применять нельзя.

Если нужен статус normalized price относительно истории, начинать с `app/price_deviation.py:evaluate_price_deviation()`. Receipt Detail адаптирует его в `build_receipt_price_analysis()`, Product Dossier — в `build_price_evaluation()`, Home Month Story — в `_story_item_candidates()`. Не добавлять новый median/threshold/legacy fallback в consumer.

Для объяснения `INSUFFICIENT_HISTORY` в пользовательском интерфейсе использовать `app/price_deviation_presentation.py:build_price_evidence_presentation()`. Этот adapter является единственным mapping machine reason → `NOT_ENOUGH_HISTORY`, `PRICE_NOT_COMPARABLE`, `PRODUCT_IDENTITY_UNCERTAIN` или `EVIDENCE_NEEDS_REVIEW`; localized copy и progress не следует дублировать в routes/templates. `eligible_prior_count` — число пригодных prior observations того же identity/unit за 180 дней, а не безусловное число прошлых покупок. Home намеренно не показывает эти объяснения.

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

Confidence: parser `0.95`, `package_name` `0.85`, `weighted_inference` `0.75`, `inferred_piece` `0.70`, unresolved `NULL`. Для `manual_correction` значение `0.85` является policy confidence: пользователь подтвердил structured evidence, прошедшее общие guards; это не вероятность истинности. `weighted_inference` допустим только при `quantity * unit_price ~= line_total` с допуском округления. Служебные строки распознаются узкими правилами, получают `service_line` и остаются без normalized price; категория не меняется.

Selective backfill:

```text
python -m app.backfill_price_data --sources package_name,weighted_inference
python -m app.backfill_price_data --apply --sources package_name,weighted_inference
```

Dry-run является default. `--apply` без `--sources` отклоняется; неизвестные sources отклоняются. Field-level merge не заменяет сильное существующее значение слабым. High-confidence conflicts и IDs 3544, 3578, 3579, 3581 исключаются. Перед write `app.db:backup_database()` создает копию через SQLite Backup API и проверяет `PRAGMA integrity_check`.

Фактический selective backfill: 2184 строки (`package_name` 2179, `weighted_inference` 5), normalized units: 1664 `eur_per_kg`, 452 `eur_per_l`, 68 `eur_per_piece`. Повторный dry-run: 0 изменений. `inferred_piece`, `service_line`, rejected и unresolved не применялись; normalized price остается unresolved у 1094 строк. Полный apply не выполнялся.

Экран `/data-quality/prices` разрешает узкую коррекцию одной строки только для `CORRECTABLE_V1`: редактируются `quantity_unit`, `package_size`, `package_unit`; raw name/identity, quantity, price, line total, category и receipt не меняются. Missing line total, arithmetic mismatch, unresolved multipack, service/parser contamination и любой оставшийся blocking warning дают `NOT_CORRECTABLE_V1`.

GET и preview не пишут в БД. Signed preview token используется только для integrity/stale-state: `item_id`, before-state hash, normalized proposed fields, projected derived fields. На apply обязательно заново загрузить row внутри `BEGIN IMMEDIATE`, проверить token/proposal, повторно вызвать `derive_price_data(source="manual_correction")` и использовать свежий результат. Derived fields из token не сохранять напрямую.

Apply должен обновлять ровно одну строку с optimistic before-state predicates; stale/deleted/different proposal и SQLite error завершаются rollback. Разрешенные write fields: `unit_price`, `quantity_unit`, `package_size`, `package_unit`, `normalized_unit_price`, `normalized_price_unit`, `price_parse_source`, `price_parse_confidence`.

Не добавлять generic item editor: расширять policy только отдельным проверенным решением для нового класса diagnostics.

## Как работает product identity

`app/product_identity.py` — единственный исполняемый контракт пользовательской идентичности товара:

- непустой `canonical_name` является ручным authoritative override;
- иначе identity равна raw receipt `name` без `normalized_name` fallback;
- сначала разрешается exact effective identity, затем только один однозначный raw alias;
- Dossier, Analytics, autocomplete, Home, deviation, Store Comparison, discovery и Merge используют общий helper.

Category `get_product_key()` остается отдельным normalized rule-grouping contract и не является user-facing identity.

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
- строит matcher-only accent-folded форму из raw `name`, не меняя persisted `normalized_name`;
- делает token buckets для shortlist по matcher-only токенам;
- считает explainable RapidFuzz score как среднее `fuzz.token_set_ratio()` и `fuzz.token_sort_ratio()`;
- показывает только score от `88`;
- `95+` считается `high` только при одинаковом наборе значимых matcher-токенов; остальные accepted pairs считаются `possible`.

Hard guards блокируют пары с разным объемом, массой, явным типом единицы, процентом, multipack signature, single-pack/multipack или разными corpus-backed вариантными признаками. Variant check симметричен: one-sided `zero`, `max`, flavor, quality grade, L/M egg size и проверенные corpus markers также блокируют unsafe merge suggestion. Multipack распознается из raw `name` для `x`/`х`/`×`; package economics не вычисляется.

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

Канонический список из 18 плоских категорий лежит в `app/category_keywords.py:CANONICAL_CATEGORIES`; sentinel — `UNRESOLVED_CATEGORY` (`прочее / требует решения`).

Alias mapping лежит в `CATEGORY_ALIASES`.

`category_for_reporting()` оставляет canonical value без изменений, а известную старую persisted category на REVIEW/UNRESOLVED строке показывает как новый unresolved sentinel. Формы при этом отдельно показывают исходное сохраненное значение. Это слой совместимости, а не разрешение неоднозначной строки.

Фактические keyword-правила лежат в `CATEGORY_KEYWORDS`. `*` в конце означает prefix одного токена или последнего токена фразы; обычная строка означает целый токен/фразу. Не добавляй unsafe substring или brand-only сигнал.

`score_keyword_matches()` считает каждый keyword максимум один раз. `PRIORITY` задает semantic tie order; узкие conjunction guards покрывают baby age+form, frozen fries, instant noodles, service bags и burger buns. Product type сильнее flavour/ingredient; неоднозначность должна уйти в `UNRESOLVED_CATEGORY`, а не в правдоподобную категорию.

`app/receipt_parser.py:categorize_item()` является wrapper общей `categorize_from_name()`. Вторую parser-классификацию не добавлять.

Read-only shadow проверяется через `python -m app.audit_category_classifier_v2 --db data/receipts.db`. Основная оценка качества — cohort без exact raw-key rule. Exact-rule-covered расхождения допустимы: `add_receipt_with_items()` применяет правило позже и сохраняет `inherited`.

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
- `app/product_identity.py` - влияет на границы user-facing товаров в Dossier, Analytics, autocomplete, Home, deviation, Store Comparison, discovery и Merge.
- `/products/merge` - массово обновляет `canonical_name`.
- `app/gmail_fetcher.py:gmail_settings()` - влияет на то, какие письма и файлы будут импортированы.

## Где могут возникнуть побочные эффекты

- Изменение regex парсера может изменить количество найденных товаров.
- Изменение логики даты может повлиять на сортировку и месячные графики.
- Изменение `receipt_number` может повлиять на дубликаты.
- Изменение категорий может изменить историческую аналитику после перекатегоризации.
- Изменение manual product rule влияет на новые импорты этой товарной группы.
- Изменение `canonical_name` меняет группировку товаров во всей аналитике.
- Изменение `normalized_name` меняет Suggestions, поисковое совпадение и category `product_key`, но само по себе не объединяет user-facing identities.
- Изменение `price`, `line_total` или `quantity` меняет spend-агрегаты и проверку арифметической согласованности, но не создаёт legacy price fallback.
- Изменение `normalized_unit_price` или `normalized_price_unit` меняет historical-deviation выводы на Home, `/item/<name>`, `/receipt/<id>` и normalized Analytics item trend, но не Analytics spend.
- Изменение схемы БД может не примениться к старой базе, если используется `CREATE TABLE IF NOT EXISTS`.
- Фактическая старая БД может иметь constraints, отличные от новой схемы в коде.

## Что отсутствует в проекте

- Общий schema migration framework отсутствует. Для единственной allowlist-миграции Category Taxonomy v2 есть узкий `app/apply_category_taxonomy_v2.py`; его нельзя использовать как keyword/backfill-инструмент.
- Отдельный parser registry не найден.
- Таблица аудита ручных изменений категорий не найдена.
- Таблица ошибок категоризации не найдена.
- Явный парсер Lidl не найден.
- Таблица `products` не создавалась.
- Таблица rejected matches не создавалась.
- Полноценный audit log category changes отсутствует.
- Таблица price warnings не создавалась; warnings пока живут только в расчетной модели и dry-run выводе.
- Полный Price Model backfill и применение `inferred_piece` не одобрены.

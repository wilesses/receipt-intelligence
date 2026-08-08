# CategoryEngine

## Где находится категоризация

Основная категоризация находится в `app/category_keywords.py`.

Ключевые элементы:

- `CATEGORY_OPTIONS`;
- `CATEGORY_KEYWORDS`;
- `PRIORITY`;
- `categorize_from_name(name)`.

Дополнительные места:

- `app/receipt_parser.py:categorize_item(name)` - простая категоризация внутри парсера;
- `app/importer.py:prepare_receipt_data()` - повторно назначает категорию через `categorize_from_name()`;
- `app/categorize_existing_items.py` - скрипт перекатегоризации существующих строк;
- `app/web/routes.py:update_item_category()` - ручное изменение категории через UI;
- `app/web/routes.py:get_category_options()` - список категорий из фактических данных;
- `app/web/app.py:category_color()` - цвета категорий для UI.

## Как сейчас работает категоризация

Фактический путь при импорте:

1. `parse_receipt(text)` находит товары.
2. Парсер может временно поставить категорию через `categorize_item(name)`.
3. `prepare_receipt_data()` проходит по всем товарам.
4. Для каждого товара выполняет:

```python
item["category"] = categorize_from_name(item.get("name", ""))
```

Итоговая категория импортируемого товара определяется `categorize_from_name()`, а не `categorize_item()`.

## Правила

Правила лежат в `CATEGORY_KEYWORDS`.

Формат:

```python
{
    "категория": [
        "keyword1",
        "keyword2",
    ]
}
```

Категоризация не использует ML, внешние справочники или БД правил. Только словарь подстрок в коде.

## Категории

`CATEGORY_KEYWORDS` содержит:

- `служебные расходы`;
- `овощи`;
- `фрукты`;
- `мясо`;
- `молочные`;
- `выпечка`;
- `сладости/снеки`;
- `чай/кофе`;
- `напитки`;
- `бытовое`;
- `корма`;
- `быстрое питание`;
- `замороженные продукты`;
- `прочее`.

`CATEGORY_OPTIONS` содержит другой UI-список:

- `мясо`;
- `молочка`;
- `овощи`;
- `фрукты`;
- `выпечка`;
- `сладости`;
- `напитки`;
- `чай/кофе`;
- `бытовое`;
- `детское`;
- `аптека`;
- `кот`;
- `прочее`.

В текущем коде `CATEGORY_OPTIONS` не используется для основной категоризации. Список категорий в формах берется из БД через `get_category_options()`.

`category_color()` в `app/web/app.py` поддерживает еще часть UI-названий:

- `молочка`;
- `сладости`;
- `кот`;
- `детское`;
- `аптека`.

В текущей базе также есть категории, которых нет в `CATEGORY_KEYWORDS`: `ребенок`, `одежда`, `молочка`.

## Порядок применения

`categorize_from_name(name)` работает так:

1. Приводит название к нижнему регистру.
2. Удаляет все символы, кроме латинских букв, латышских букв, точки и пробелов:

```regex
[^a-zāčēģīķļņōŗšūž.\s]
```

3. Делит строку на слова.
4. Оставляет слова длиной от 3 символов.
5. Создает счетчик совпадений для каждой категории.
6. Для каждого слова проходит по всем категориям и всем keywords.
7. Увеличивает счетчик категории, если:

```python
keyword in word or keyword in name_clean
```

8. Если все счетчики равны 0, возвращает `прочее`.
9. Находит максимальное число совпадений.
10. Собирает категории-кандидаты с этим максимумом.
11. Если несколько категорий совпали, выбирает первую из `PRIORITY`.
12. Если ни один кандидат не найден в `PRIORITY`, возвращает `прочее`.

`PRIORITY`:

```text
служебные расходы
мясо
молочные
овощи
фрукты
напитки
выпечка
сладости/снеки
чай/кофе
корма
быстрое питание
бытовое
замороженные продукты
```

Категория `прочее` есть в `CATEGORY_KEYWORDS`, но не входит в `PRIORITY`.

## Что происходит, если ничего не найдено

Если ни один keyword не совпал, `categorize_from_name()` возвращает:

```text
прочее
```

В `app/importer.py:prepare_receipt_data()` также есть fallback:

- `price` становится `0`, если пустой;
- `quantity` становится `1`, если пустое;
- категория всегда перезаписывается результатом `categorize_from_name()`.

В `app/db.py:add_receipt_with_items()` есть дополнительный fallback:

```python
item.get("category") or "прочее"
```

## Ручное изменение категории

Route:

- `POST /item/<int:item_id>/category`;
- функция `update_item_category(item_id)`.

Логика:

- берет `new_category`, если поле заполнено;
- иначе берет выбранную `category`;
- если обе пустые, ставит `прочее`;
- обновляет только одну строку `items.id`.

SQL:

```sql
UPDATE items SET category = ? WHERE id = ?
```

Ручное изменение категории не меняет `CATEGORY_KEYWORDS`.

## Перекатегоризация существующих товаров

Файл: `app/categorize_existing_items.py`.

Функции:

- `is_valid_item_name(name)`;
- `categorize_all_items(overwrite=False)`.

`is_valid_item_name()` отбрасывает пустые/слишком короткие названия, единицы измерения и строки вида:

```regex
\d+(g|ml|gab|kg|l)\.?
```

`categorize_all_items(overwrite=False)`:

- если `overwrite=True`, выбирает все товары;
- иначе выбирает только `category IS NULL OR category = ''`;
- обновляет `items.category`;
- возвращает `Counter` по категориям.

Скрипт не вызывается из веб-приложения автоматически.

## Слабые места

Из текущей архитектуры видны такие слабые места:

- Категории зависят от подстрок, а не от точного словаря товаров.
- Все правила зашиты в коде, не в БД.
- OCR-ошибки и отсутствие диакритики могут мешать совпадению.
- Один keyword может совпасть внутри другого слова.
- При равенстве счетчиков результат зависит от `PRIORITY`.
- Часть UI-категорий не совпадает с категориями словаря.
- Ручная категория позиции не обучает движок и не добавляет keyword.
- `categorize_item()` в `receipt_parser.py` и `categorize_from_name()` в `category_keywords.py` могут дать разные результаты, но импорт перезаписывает результат парсера.
- `canonical_name` влияет на аналитику товаров, но не влияет на категоризацию.

## Какие товары чаще всего определяются неправильно

В проекте нет таблицы ошибок, журнала ручных исправлений или признака "категория была неправильной". Поэтому достоверного списка неправильно определяемых товаров в коде нет.

В текущей базе можно увидеть частые позиции в категории `прочее`; это только кандидаты на неполное распознавание, не доказанные ошибки:

- `Sipoli 50/70 mn, kg` - 8 строк;
- `Lēcu kraukšķi ar krēj. un sīp. USTUKIU 70g` - 7 строк;
- `Burkani sverami kg` - 7 строк;
- `Kiploki 50+ mm kg` - 6 строк;
- `Piradzins Empanada ar tris sieriem 100g` - 4 строки;
- `Mērce burgeru HELLMANN'S 250ml` - 3 строки;
- `Korejiesu burkani Ca kg` - 3 строки;
- `Saulespuķu sēk. grauzd. sāl. MOGYI 200g` - 3 строки;
- `Energijas dzériens Monster 0,51` - 3 строки;
- `Sampinjoni Rimi 250g` - 3 строки.

## Существующая архитектура

```text
app/receipt_parser.py
  parse_receipt()
  parse_rimi_receipt()
  categorize_item()

        |
        | товары с предварительной категорией
        |

app/importer.py
  prepare_receipt_data()
  item["category"] = categorize_from_name(...)

        |
        | итоговая категория
        |

app/db.py
  add_receipt_with_items()
  INSERT INTO items (... category)

        |
        | сохраненные категории
        |

app/analytics_service.py
app/web/routes.py
app/web/templates/
  фильтры, графики, формы ручной правки
```

## Category Engine v2

Category Engine v2 добавляет слой ручных решений поверх существующего словарного движка. `CATEGORY_KEYWORDS` не переписан полностью, keywords сохранены.

### Канонические категории

Единый список находится в `app/category_keywords.py:CANONICAL_CATEGORIES`:

- `служебные расходы`;
- `мясо`;
- `молочные`;
- `овощи`;
- `фрукты`;
- `выпечка`;
- `сладости/снеки`;
- `чай/кофе`;
- `напитки`;
- `бытовое`;
- `корма`;
- `детское`;
- `аптека`;
- `быстрое питание`;
- `замороженные продукты`;
- `одежда`;
- `прочее`.

Legacy aliases:

- `молочка` -> `молочные`;
- `сладости` -> `сладости/снеки`;
- `кот` -> `корма`;
- `ребенок` -> `детское`.

`normalize_category_name()` возвращает `прочее` для `None` и пустой строки, применяет alias mapping и не удаляет неизвестную категорию молча.

### category_source

`items.category_source` хранит источник категории:

- `rule` - категория назначена `CATEGORY_KEYWORDS`;
- `manual` - категория выбрана пользователем;
- `inherited` - категория взята из `product_category_rules` при импорте;
- `fallback` - правила не сработали, использовано `прочее`.

Существующие строки после миграции получают default `rule`. Старые ручные изменения восстановить нельзя: audit log раньше отсутствовал.

### categorize_with_source

`categorize_with_source(name)` возвращает:

- `("категория", "rule")`, если keyword сработал;
- `("прочее", "fallback")`, если совпадений нет.

`categorize_from_name()` сохранен как совместимый wrapper для старых вызовов.

### product_category_rules

Таблица `product_category_rules` хранит ручную категорию товарной группы. `product_key` считается в `app/category_rules.py:get_product_key()`:

```text
normalize_product_name(canonical_name), если canonical_name заполнен
иначе normalized_name
иначе normalize_product_name(items.name)
```

Правило не объединяет товары, не меняет `items.name`, не меняет `canonical_name` и не использует RapidFuzz score.

### Ручная смена категории

Route `POST /item/<int:item_id>/category` поддерживает:

- `scope=item` - обновляется только одна позиция, `category_source = manual`, rule не создается;
- `scope=product` - создается/обновляется `product_category_rules`, затем обновляется вся точная группа, `category_source = manual`.

По умолчанию UI выбирает `Весь товар`.

### Review screen

`/products/review` показывает агрегированные группы, если есть хотя бы одно условие:

- категория `прочее`;
- `category_source = fallback`;
- внутри группы несколько категорий;
- внутри группы есть `manual` и `rule`;
- пустой `normalized_name`;
- нет manual rule;
- категория пустая.

Страница показывает имя, алиасы, счетчики строк и чеков, категории, источники, последнюю дату, магазины, normalized name, canonical flag и наличие manual rule. Быстрое исправление создает/обновляет rule и применяет category ко всей точной группе.

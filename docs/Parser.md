# Parser

## Где находится парсер

Основной парсер находится в `app/receipt_parser.py`.

Связанный импортный слой находится в `app/importer.py`:

- извлекает текст из PDF;
- вызывает `parse_receipt(text)`;
- повторно категоризирует товары;
- нормализует дату;
- готовит данные для сохранения.

Gmail-импорт находится в `app/gmail_fetcher.py` и `app/web/routes.py:gmail_fetch()`.

## Как определяется магазин

`parse_receipt(text)` делит текст на строки:

```python
lines = [l.strip() for l in text.splitlines() if l.strip()]
```

Затем:

- если любая строка содержит `rimi` без учета регистра, вызывается `parse_rimi_receipt(lines)`;
- если Rimi-парсер нашел товары, возвращается результат с `store = "RIMI"`;
- иначе используется Maxima-парсер с `store = "MAXIMA"`.

Отдельного универсального определения магазина нет. Lidl есть только как вариант фильтра в `analytics.html`, но парсер Lidl в коде отсутствует.

## Как определяется дата

### Rimi

`parse_rimi_receipt(lines)` сначала ищет строку, где есть `laiks`, затем дату:

```regex
(\d{4})[-.](\d{2})[-.](\d{2})
```

Если дата в строке с `laiks` не найдена, используется fallback:

```regex
(\d{4})[-.](\d{2})[-.](\d{2})|(\d{2})\.(\d{2})\.(\d{4})
```

Формат `DD.MM.YYYY` преобразуется в `YYYY-MM-DD`.

### Maxima

Maxima-парсер ищет первую строку с датой:

```regex
\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}
```

После парсинга `app/importer.py:normalize_date()` преобразует `DD.MM.YYYY` в `YYYY-MM-DD`.

## Как определяется сумма

### Rimi

Парсер идет по строкам снизу вверх. Берет первую строку, где есть `kopa` или `kopā`, и ищет сумму:

```regex
(\d+,\d{2})
```

Сумма преобразуется через `parse_money()`, то есть запятая заменяется на точку.

### Maxima

Парсер идет по строкам снизу вверх. Берет строку, где есть `kopā apmaksai`, и ищет:

```regex
\d+,\d{2}
```

Если итог не найден или равен `0`, `app/importer.py:prepare_receipt_data()` считает итог как сумму `item["price"]` по товарам.

## Как определяются товары

### Rimi

Товарная строка определяется regex `qty_line_pattern`:

```regex
(?P<qty>\d+(?:,\d+)?)\s*(?:gab|kg)\s+X\s+(?P<unit_price>\d+,\d{2})\s*EUR(?:/kg)?(?:\s+(?P<line_total>\d+,\d{2}))?
```

Логика:

- строка с количеством и ценой считается ценовой строкой товара;
- название собирается из предыдущих строк, максимум 3 строки;
- сбор названия останавливается на пустых строках, служебных словах, другой ценовой строке, скидочных строках;
- `quantity` берется из группы `qty`;
- `unit_price` берется из группы `unit_price`;
- `price` берется из `line_total`, если есть, иначе считается как `quantity * unit_price`;
- следующие 3 строки проверяются на скидку;
- если найдена строка с `gala cena`, цена заменяется на сумму в конце этой строки.

Служебные слова Rimi:

```text
sia rimi, jur. adrese, kase nr, pvn, sasijas, čeks, ceks,
elektroniska, klients, atlaides, tavs letaupijums, maksajumu,
apmaksa, bankas, terminala, tirgotaja, laiks, visa, kopa,
kopā, saglabajiet, rrn, nopelnita
```

Игнорируемые слова для имени:

```text
atl., gala cena
```

### Maxima

Товарная строка определяется так:

```regex
\d+,\d{2}\s+X\s+[\d,]+
```

Логика:

- строка с `цена X количество` считается товарной;
- название собирается из предыдущих строк;
- сбор останавливается на пустой строке, словах `atlaide`, `kopā`, `summa`, `apmaksai` или другой ценовой строке;
- максимум собираются 2 строки, либо остановка происходит, если предыдущая строка длиннее 20 символов;
- количество ищется через:

```regex
X\s+([\d,]+)
```

- явный `gab.`/`gb.` после количества задает `quantity_unit = piece`; без явного маркера единица остается `unknown`;
- первое число перед `X` сохраняется как печатное ценовое доказательство для Price Model;

- цена сначала ищется в следующих двух строках с `cena ar atlaidi`;
- если скидочной цены нет, цена берется из конца товарной строки:

```regex
(\d+,\d{2})\s+[A-Z]?$
```

## Какие regex используются

Деньги:

```regex
\d+,\d{2}
```

Rimi дата рядом с `laiks`:

```regex
(\d{4})[-.](\d{2})[-.](\d{2})
```

Rimi fallback дата:

```regex
(\d{4})[-.](\d{2})[-.](\d{2})|(\d{2})\.(\d{2})\.(\d{4})
```

Rimi товарная строка:

```regex
(?P<qty>\d+(?:,\d+)?)\s*(?:gab|kg)\s+X\s+(?P<unit_price>\d+,\d{2})\s*EUR(?:/kg)?(?:\s+(?P<line_total>\d+,\d{2}))?
```

Maxima дата:

```regex
\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}
```

Maxima товарная строка:

```regex
\d+,\d{2}\s+X\s+[\d,]+
```

Maxima количество:

```regex
X\s+([\d,]+)
```

Maxima fallback цена:

```regex
(\d+,\d{2})\s+[A-Z]?$
```

## Parser Quality v2

Общий preprocessing выполняется в `parse_receipt()` до определения магазина и обоих parser branches. `preprocess_receipt_text()` делает только доказуемые преобразования:

- нормализует длинные тире;
- удаляет пробел после десятичной запятой, только если после нее ровно одна цифра и известная единица: `1, 5L` -> `1,5L`, `0, 5L` -> `0,5L`;
- не заменяет символы и не угадывает значения: `21`, `lkg`, `m1`, `2, 86L` остаются исходным текстом.

`sanitize_receipt_lines()` узко исключает store headers, строки `Čeks`/`Ceks`, отдельные номера вида `123/456`, кассу, кассира и terminal metadata. Store detection выполняется до удаления header, поэтому Rimi dispatch сохраняется.

Перед добавлением item `parser_quality_issue()` отклоняет:

- пустое имя;
- receipt-header contamination;
- подтвержденные service/non-product lines;
- OCR-токены `lkg` и `m1`;
- split decimal с двумя и более цифрами после пробела, например `2, 86L`;
- package token, слепленный с предыдущим словом, например `sviestu250g`.

Multipack (`6x330ml`, `1+1`) не исправляется и не отклоняется как товар: исходное имя сохраняется, а package semantics остаются unresolved. Это отличается от доказанного non-product/OCR contamination.

Read-only аудит:

```text
python -m app.audit_parser_quality
python -m app.audit_parser_quality --examples 20
```

`app/audit_parser_quality.py` открывает SQLite через URI `mode=ro` и `PRAGMA query_only = ON`. На текущих 3580 items он нашел: decimal corruption 12, `lkg` 12, `m1` 11, `Čeks` 6, service lines 656, multipack 86, glued tokens 5, ambiguous package size 52. Узких cashier-name совпадений нет; 2740 строк попали в `unknown`, куда входят нормальные товары.

Проекция нового parser для сохраненных имен: 8 безопасных исправлений, 694 отклонения, 138 намеренно unresolved, 2740 без изменения. Группы exclusive по приоритету audit script. Это read-only модель будущего импорта; исходный OCR-текст старых чеков в БД не хранится, поэтому исторический parse нельзя воспроизвести полностью.

Категоризация чистит название:

```regex
[^a-zāčēģīķļņōŗšūž.\s]
```

Проверка валидности имени в `categorize_existing_items.py`:

```regex
\d+(g|ml|gab|kg|l)\.?
```

## Как работает OCR

OCR реализован в `app/importer.py:extract_text_with_ocr()`.

Перед OCR `extract_text_from_pdf()` проверяет PDF:

- если `pdfplumber` достал текст, OCR не используется;
- если текста нет, но на страницах есть изображения, запускается OCR;
- если текста нет и изображений нет, возвращается ошибка.

Поиск команд:

- `find_executable("pdftoppm", [...])`;
- `find_executable("tesseract", [...])`;
- можно задать `PDFTOPPM_CMD` и `TESSERACT_CMD`;
- иначе проверяются известные пути и `PATH`.

Процесс:

```text
PDF
↓
pdftoppm -png -r 220
↓
page-*.png
↓
tesseract <image> stdout -l lav+eng
↓
объединенный текст
```

Если `pdftoppm` или `tesseract` не найдены, возвращается пользовательская ошибка о необходимости OCR.

## Как работает импорт PDF

Основная функция: `app/importer.py:process_pdf_api(file_path)`.

Pipeline:

1. `prepare_receipt_data(file_path)`.
2. `extract_text_from_pdf(file_path)`.
3. `parse_receipt(text)`.
4. Проверка, что есть товары.
5. Повторная категоризация каждого товара через `categorize_from_name()`.
6. Расчет Price Model полей через `derive_price_data()`.
7. Заполнение пустых `price` и `quantity`.
8. Подсчет `total`, если итог не найден.
9. `receipt_number = Path(file_path).stem`.
10. `add_receipt_with_items(...)`.

Parser Hardening v2 сохраняет существующие merchant branches. Rimi передает `quantity_unit` (`gab` или `kg`) и печатную цену перед скидкой. Maxima передает `piece` только при явном `gab.`/`gb.`, иначе `unknown`, а также печатную цену перед `X`.

`derive_price_data()` приводит новые данные к общему контракту:

- `line_total` — оплаченный итог строки после скидки;
- `unit_price = line_total / quantity` с округлением до 4 знаков;
- арифметический конфликт печатной цены определяется с абсолютным допуском €0.02 и ограничивает confidence ниже 0.75;
- `normalized_unit_price` всегда считается от оплаченного `line_total`;
- при сохранении `items.price == items.line_total`.

Measurement Parsing различает узкие формы:

- age/package `1–36 + size g|ml`: `6+110g` и `6+ 110g` дают упаковку 110 g, возраст остается в имени;
- `x`, `х`, `×` multipack остается unresolved с `multipack_unresolved`;
- `45+ kg` не становится упаковкой 45000 g; fractional quantity с terminal `kg`/`l`, допустимым `2. šķ.` suffix и согласованной печатной арифметикой может получить `weighted_inference`;
- warnings остаются transient; Price Quality независимо проверяет persisted арифметику.

Ручная загрузка:

- route `/upload`;
- файлы сохраняются в `data/uploads`;
- допускается только расширение `.pdf`;
- ответ возвращается JSON с `uploaded` и `errors`.

Пакетный импорт:

- `import_all_pdfs()`;
- читает `data/pdf_receipts`;
- после успешного импорта удаляет PDF.

## Как работает Gmail импорт

Настройки читаются в `app/gmail_fetcher.py:gmail_settings()` из `.env`:

- `IMAP_SERVER`;
- `EMAIL_ACCOUNT`;
- `APP_PASSWORD`;
- `SAVE_FOLDER`;
- `DAYS_LOOKBACK`;
- `GMAIL_MAX_EMAILS`;
- `GMAIL_IMPORT_EXISTING`;
- `GMAIL_RAW_QUERY`;
- `GMAIL_SENDERS`.

Подключение:

- `connect_to_gmail()` использует `imaplib.IMAP4_SSL`;
- если настройки не заполнены, бросает `RuntimeError`;
- если Gmail отклоняет логин, возвращает сообщение про App Password.

Поиск:

- если задан `GMAIL_RAW_QUERY`, используется `X-GM-RAW`;
- иначе поиск идет по отправителям из `GMAIL_SENDERS`;
- если отправители не заданы, ищутся письма за период `DAYS_LOOKBACK`.

Вложения:

- берутся только части письма с `Content-Disposition: attachment`;
- имя декодируется через `decode_mime_value()`;
- сохраняются только `.pdf`;
- имя очищается через `secure_filename()`;
- если файл уже есть, он попадает в `files_existing`.

Импорт из веба:

- `/gmail/fetch` вызывает `fetch_pdf_attachments()`;
- новые PDF импортируются сразу;
- существующие PDF импортируются только если `GMAIL_IMPORT_EXISTING=true`;
- перед импортом дополнительно проверяется `receipts.receipt_number`.

## Ограничения

- Универсального определения магазина нет.
- Если текст содержит `rimi`, проект пробует Rimi-парсер, но возвращает Rimi только если нашел товары.
- Все не-Rimi чеки фактически идут по Maxima-парсеру.
- Lidl в шаблоне аналитики есть как фильтр, но Lidl-парсера нет.
- PDF без текстового слоя требует Poppler и Tesseract.
- OCR использует языки `lav+eng`; если языковые пакеты не установлены, распознавание может не сработать.
- Парсер товаров зависит от расположения строк в конкретном формате чека.
- `receipt_number` берется из имени файла, а не из текста чека.
- Дубликаты определяются по имени PDF без расширения.
- Сумма чека может быть заменена суммой товаров, если итог не найден.
- Multipack вроде `6x330ml` пока не разбирается в общий объем; Price Model только ставит warning.
- `lkg`, `m1`, unsafe split decimals и glued package tokens не исправляются догадкой; новый parser отклоняет такие item candidates.
- Audit-категория `unknown` не означает ошибку: она включает обычные товары без узкой contamination signature.
- У Maxima единица количества известна как `piece` только при явном `gab.`/`gb.`; прочие строки требуют детерминированного Price Model evidence.

## Поддерживаемые магазины

Полностью или явно поддержаны кодом:

- Rimi: отдельная функция `parse_rimi_receipt()`;
- Maxima: fallback-логика в `parse_receipt()`.

## Частично поддерживаемые магазины

- Lidl: присутствует в фильтре магазина на странице `/analytics`, но отдельного парсера нет.

Другие магазины в коде не описаны.

## Известные проблемы

Из кода и данных видны такие ограничения:

- OCR зависит от внешних программ, которых может не быть в системе.
- Rimi PDF-сканы без OCR не импортируются.
- Некорректно распознанные OCR-строки могут ломать regex товаров.
- Категоризация работает по подстрокам, поэтому может давать ложные совпадения.
- В текущей базе есть категории, которых нет в `CATEGORY_OPTIONS`, например `ребенок`, `одежда`.
- В текущей базе есть `молочка`, но основной словарь использует `молочные`; `category_color()` поддерживает оба варианта.
- Список товаров, которые "чаще всего определяются неправильно", в коде не ведется. Можно видеть только частые товары категории `прочее` в текущей базе, например `Sipoli 50/70 mn, kg`, `Lēcu kraukšķi ar krēj. un sīp. USTUKIU 70g`, `Burkani sverami kg`, `Kiploki 50+ mm kg`. Это не доказательство ошибки, только признак отсутствия срабатывания правил.

## Примеры

### Rimi

Строки чека:

```text
Mellenes spainītī 400g
1 gab X 3,99 EUR 3,99
```

Полученный объект позиции:

```json
{
  "name": "Mellenes spainītī 400g",
  "quantity": 1.0,
  "price": 3.99,
  "category": "фрукты"
}
```

### Rimi со скидкой

Строки чека:

```text
Tomāti ķekaros sarkanie kg 2. šķ.
1,234 kg X 2,49 EUR/kg 3,07
Gala cena 2,49
```

Полученный объект позиции:

```json
{
  "name": "Tomāti ķekaros sarkanie kg 2. šķ.",
  "quantity": 1.234,
  "price": 2.49,
  "category": "овощи"
}
```

### Maxima

Строки чека:

```text
Gāzēts dzēriens PEPSI MAX 1L PET D
1,49 X 2,000
```

Полученный объект позиции зависит от наличия цены в конце строки или скидочной строки `cena ar atlaidi`. Если цена есть в конце строки, объект будет вида:

```json
{
  "name": "Gāzēts dzēriens PEPSI MAX 1L PET D",
  "quantity": 2.0,
  "price": 1.49,
  "category": "напитки"
}
```

Если цена не найдена, `prepare_receipt_data()` заменит пустую цену на `0`.

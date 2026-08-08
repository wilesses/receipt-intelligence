# Receipt Tracker — Visual Redesign Implementation Plan

## Назначение

План задаёт безопасный порядок визуального редизайна. Он не содержит готового CSS, HTML, JavaScript или хрупких тестов конкретных текстовых строк.

Источник требований:

1. `VISUAL_CONSTITUTION.md` — философия и ограничения.
2. `DESIGN_SYSTEM.md` — общая визуальная грамматика.
3. `SCREEN_SPECS.md` — требования экранов.
4. Этот документ — порядок исполнения, проверки и приёмки.

---

## 1. Границы проекта

### Входит в работу

- визуальная иерархия;
- layout и responsive composition;
- типографические роли;
- surfaces, borders и spacing;
- унификация компонентов и состояний;
- системная локализация UI;
- accessibility визуальных и интерактивных состояний;
- visual regression и screen-level acceptance checks.

### Не входит

- новая бизнес-логика;
- новые backend endpoints;
- изменение модели данных;
- новый Radar или network graph;
- новые продуктовые функции;
- декоративный ребрендинг;
- тотальная замена рабочих native controls;
- буквальное копирование известных SaaS-продуктов.

### Правила исполнения

- Работать фазами, не одним большим patch.
- Внутри фазы сначала фиксировать общие паттерны, затем экраны.
- Не менять структуру данных ради удобства layout.
- Не переносить композицию Briefing на операционные экраны.
- Сохранять различия reading, register, investigation и review.
- После каждой фазы проводить визуальное ревью до перехода дальше.

---

## 2. Подготовка и baseline

### Цель

Зафиксировать текущее состояние и снизить риск визуальных регрессий.

### Действия

1. Составить актуальный список маршрутов и состояний:
   - default;
   - loading;
   - empty;
   - filtered;
   - selected;
   - expanded;
   - error;
   - drawer open;
   - mobile menu open.
2. Сохранить reference screenshots ключевых экранов на desktop и mobile.
3. Инвентаризировать:
   - page headers;
   - buttons и links;
   - filters и form controls;
   - tables/register rows;
   - chips и statuses;
   - alerts;
   - drawers;
   - navigation states.
4. Найти параллельные реализации одинакового паттерна.
5. Зафиксировать текущие accessibility и responsive defects.

### Результат

- screen/state inventory;
- screenshot baseline;
- component duplication map;
- список известных исключений.

### Gate

Ни один крупный экранный рефакторинг не начинается без baseline соответствующего маршрута и состояния.

---

## 3. Phase 1 — Foundation

### Цель

Устранить системные противоречия до переработки отдельных страниц.

### Входит

- app canvas и surface hierarchy;
- типографические роли;
- цветовая семантика;
- spacing и radius rules;
- page и section headers;
- primary, secondary, tertiary и row actions;
- form controls и filters;
- chips и statuses;
- tables, register rows и expanded state;
- alerts, empty states и evidence blocks;
- desktop и mobile shell;
- единый системный язык.

### Порядок

1. Нормализовать foundation tokens и semantic roles без смены визуальной идентичности.
2. Собрать или унифицировать общие primitives.
3. Перевести shell и navigation на единые состояния.
4. Ввести общие header, action, filter и status patterns.
5. Подготовить register, review item, comparison pair и evidence block как разные паттерны, а не одну универсальную card.
6. Удалить неиспользуемые или дублирующие стили только после подтверждения миграции.

### Сознательно не трогать

- бизнес-логику;
- data transformations;
- основную композицию Briefing;
- конкретный chart selection;
- экранную перестановку, не необходимую для foundation.

### Acceptance criteria

- одинаковые компоненты выглядят одинаково;
- один status vocabulary;
- muted, disabled, selected, active, focus и error различимы;
- один системный язык;
- page headers имеют общую анатомию;
- нет нового универсального card-компонента для всех задач;
- shell работает на desktop и mobile;
- keyboard focus и touch targets не деградировали.

### Review gate

Провести визуальное сравнение минимум на Briefing, Archive, одном review-экране и mobile shell. Исправить системные отклонения до Phase 2.

---

## 4. Phase 2 — Core documents

### Цель

Собрать главный документальный путь: найти чек, раскрыть его и проверить evidence.

### Экраны

- Архив чеков.
- Раскрытый чек.
- Evidence drawer.

### Порядок

1. Упростить information architecture архива.
2. Собрать header, summary band и filter toolbar.
3. Перевести список в receipt register.
4. Реализовать сильное expanded state.
5. Упорядочить item rows и review statuses.
6. Привести evidence summary к общей системе.
7. Перестроить drawer в последовательность «источник → подтверждено → ограничения → trace».
8. Адаптировать весь поток для mobile.

### Сохранить

- inline receipt model;
- основные receipt metadata;
- связь с source data;
- существующий смысл фильтров;
- честное отображение evidence limitations.

### Удалить

- Radar;
- повторяющие page labels;
- дублирующий period chip;
- общий parser warning из primary-слоя строк;
- повторяющиеся evidence headings;
- лишние nested surfaces.

### Acceptance criteria

- архив имеет один H1;
- строки быстро сравниваются;
- expanded receipt очевидно связан с выбранной строкой;
- товары и отклонения доминируют над parser metadata;
- drawer сохраняет контекст и имеет ясное закрытие;
- первый meaningful content виден рано на mobile;
- empty, filtered и expanded states проверены.

### Review gate

Проверить поток Archive → Expanded receipt → Evidence drawer на desktop и mobile, включая keyboard navigation и длинные названия.

---

## 5. Phase 3 — Operational review

### Цель

Превратить внутренние admin-like страницы в последовательные рабочие очереди без потери плотности.

### Экраны

- Проверка категорий.
- Похожие товары.
- Объединение товаров.
- Качество цен.
- Загрузка чеков.

### Общий порядок

1. Удалить навигационные и технические KPI-card walls.
2. Ввести общий queue summary и review item.
3. Выстроить decision hierarchy.
4. Ослабить technical metadata.
5. Унифицировать filters, statuses и row actions.
6. Сохранить уникальную композицию сравнения и bulk selection.
7. Адаптировать mobile order для каждой задачи.

### Экранные акценты

#### Category review

- toolbar → queue summary → review list;
- объект и решение первичны;
- reason и impact вторичны.

#### Similar products

- различия первичны;
- уверенность не дублируется;
- парность сохраняется на mobile.

#### Merge

- search и selection table связаны с command band;
- selected set и canonical target видны до подтверждения.

#### Price quality

- compact coverage overview;
- активная проблема перед результатами;
- диагностическая таблица сохраняет высокую, но слоистую плотность.

#### Upload

- file selection → queue → import;
- mail check остаётся secondary route;
- empty и filled states одинаково завершены.

### Сознательно не трогать

- правила категоризации;
- matching confidence calculation;
- merge semantics;
- price normalization logic;
- import mechanisms.

### Acceptance criteria

- review screens ощущаются одной системой;
- каждый экран сохраняет собственную рабочую композицию;
- row actions не конкурируют с объектом решения;
- technical metadata не маскируется под status;
- selection и destructive/irreversible последствия понятны;
- keyboard, focus, touch и long-content states проверены.

### Review gate

Провести отдельное task-based ревью каждого рабочего пути, а затем сравнительное ревью всех review screens на консистентность.

---

## 6. Phase 4 — Investigation and reading

### Цель

Укрепить аналитические режимы, не превращая их в dashboard-grid или один и тот же editorial layout.

### Экраны

- Аналитика.
- Intelligence Briefing.

### Порядок

1. Сначала переработать Analytics как investigation canvas.
2. Упорядочить filters и summary текущего среза.
3. Определить главный аналитический вопрос каждого chart.
4. Заменить непригодное категорийное представление.
5. Ограничить visual weight и data colors вторичных charts.
6. После стабилизации системы аккуратно привести Briefing к общим headers, actions и evidence patterns.
7. Сохранить уникальный editorial reading flow Briefing.

### Сознательно не трогать

- аналитические расчёты;
- доступные dimensions и filters;
- conclusion-first модель;
- доказательную тональность;
- данные только ради более красивой симметрии.

### Acceptance criteria

- Analytics отвечает на выбранный вопрос, а не показывает стену метрик;
- chart sizes отражают полезность;
- summary поддерживает исследование;
- chart meaning доступен на mobile и без hover;
- Briefing сохраняет характер и не становится marketing hero;
- следующий шаг и evidence остаются связанными с выводом.

### Review gate

Отдельно проверить режим исследования и режим чтения. Не принимать визуальную унификацию, если она стирает различия задач.

---

## 7. Phase 5 — Responsive, accessibility and polish

### Цель

Довести систему после структурных изменений, не меняя утверждённую иерархию.

### Входит

- mobile content order;
- navigation sheet;
- responsive tables и charts;
- long text и localization;
- contrast и text scaling;
- touch targets;
- focus order;
- reduced motion;
- loading, empty, disabled и error states;
- visual regression cleanup.

### Порядок

1. Проверить ключевые ширины и увеличение текста.
2. Исправить first-viewport priority.
3. Устранить horizontal overflow.
4. Проверить status recognition без цвета.
5. Проверить keyboard navigation и focus visibility.
6. Проверить touch target perception.
7. Упростить motion и обеспечить reduced-motion parity.
8. Провести cross-screen consistency audit.
9. Удалить действительно неиспользуемые legacy styles.

### Сознательно не трогать

- утверждённую hierarchy;
- desktop density операционных экранов;
- структуру разделов;
- цветовую идентичность;
- нативные conventions ради декоративной кастомизации.

### Acceptance criteria

- основная задача видна в первом mobile viewport;
- mobile не является механически сложенным desktop;
- нет horizontal overflow в поддерживаемых состояниях;
- controls пригодны для касания и клавиатуры;
- statuses различимы без цвета;
- text scaling не разрушает композицию;
- интерфейс понятен без анимации;
- экранные режимы остаются различными, а система — единой.

---

## 8. Verification strategy

### Структурные проверки

Проверять не конкретные формулировки, а устойчивые контракты:

- один page heading;
- корректная heading hierarchy;
- наличие label у controls;
- уникальные accessible names;
- semantic status role;
- правильная связь disclosure и expanded content;
- drawer semantics и focus management;
- отсутствие duplicate IDs;
- отсутствие неуправляемого overflow.

Текстовые assertions допустимы только для продуктовых терминов, которые действительно являются контрактом.

### Visual regression

Минимальный набор:

- desktop и mobile;
- default и dark-theme baseline, если поддерживаются несколько тем;
- empty, populated, filtered, selected, expanded и error states;
- drawer и menu open;
- длинные названия и крупные числа;
- reduced motion;
- increased text size.

### Task-based review

Проверять реальные пользовательские задачи:

- найти и раскрыть чек;
- проследить evidence;
- исследовать выбранный аналитический срез;
- подтвердить категорию;
- сравнить похожие товары;
- выбрать набор и задать canonical name;
- найти проблему качества цены;
- импортировать файлы.

### Constitution audit

После каждой фазы ответить:

- не появился ли generic dashboard;
- не выросло ли число поверхностей;
- не стали ли metadata и statuses конкурировать с данными;
- сохраняется ли evidence trail;
- соответствует ли каждый экран своему режиму;
- улучшилась ли скорость понимания и работы.

---

## 9. Change management

### Размер изменений

- Одна фаза — отдельная reviewable ветка или PR.
- Внутри фазы допускаются небольшие последовательные изменения по общему паттерну или экрану.
- Не смешивать Foundation с полной переработкой всех страниц.

### Зависимости

- Phase 1 обязательна для всех следующих фаз.
- Phases 2 и 3 могут выполняться после Foundation независимо, если не меняют одни и те же primitives.
- Phase 4 следует начинать после стабилизации filters, headers и evidence patterns.
- Phase 5 начинается после завершения структурных изменений.

### Решения и исключения

Для отклонения от Constitution или Design System зафиксировать:

- пользовательскую проблему;
- почему общий паттерн не подходит;
- выбранное исключение;
- влияние на desktop, mobile и accessibility;
- условия пересмотра.

---

## 10. Definition of project done

Редизайн завершён, когда:

- все заявленные экраны прошли screen-specific acceptance criteria;
- одинаковые components и statuses едины;
- reading, register, investigation и review остаются разными режимами;
- отсутствуют Radar, KPI walls и системная языковая смесь;
- нет повторяющих page titles и необоснованных nested cards;
- ключевые пользовательские задачи проверены на desktop и mobile;
- accessibility и responsive behavior не деградировали;
- visual regression suite покрывает значимые состояния;
- legacy styles удалены только после подтверждённой миграции;
- финальный Constitution audit не выявляет отклонений без документированного обоснования.

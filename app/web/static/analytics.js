(() => {
    'use strict';

    const workspace = document.querySelector('[data-analytics-workspace]');
    if (!workspace) return;

    const filters = document.getElementById('analyticsFilters');
    const trendForm = document.getElementById('analyticsTrendForm');
    const applyButton = document.getElementById('applyFilters');
    const status = document.getElementById('analyticsStatus');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const money = new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'EUR',
        minimumFractionDigits: 2,
    });
    const monthName = new Intl.DateTimeFormat('ru-RU', {
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
    });
    const charts = {
        categories: null,
        months: null,
        top: null,
        trend: null,
    };
    const chartCanvasIds = {
        categories: 'categoryChart',
        months: 'monthChart',
        top: 'topItemsChart',
        trend: 'trendChart',
    };
    const chartEmptyMessages = {
        categories: 'В выбранном срезе нет категорий.',
        months: 'Для выбранного среза нет помесячных данных.',
        top: 'В выбранном срезе нет товарных позиций.',
    };
    const chartRenderErrors = {
        categories: 'Не удалось отобразить распределение по категориям.',
        months: 'Не удалось отобразить динамику расходов.',
        top: 'Не удалось отобразить состав товаров.',
        trend: 'Не удалось отобразить историю цены.',
    };
    let lastAnalyticsData = null;
    let lastTrendData = null;
    let lastTrendName = '';

    function cssColor(name, fallback) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
    }

    function palette() {
        return {
            text: cssColor('--text-secondary', '#a6b1bd'),
            muted: cssColor('--muted', '#7f8b98'),
            line: cssColor('--line', '#283541'),
            primary: cssColor('--analytics-chart-primary', '#4da8e8'),
            category: cssColor('--analytics-chart-category', '#70a8c9'),
            product: cssColor('--analytics-chart-product', '#35b987'),
            trend: cssColor('--analytics-chart-trend', '#a98bc5'),
            surface: cssColor('--surface', '#111820'),
        };
    }

    function chartPlugins() {
        return window.ChartDataLabels ? [window.ChartDataLabels] : [];
    }

    function configureChartDefaults() {
        if (!window.Chart) return;
        const colors = palette();
        Chart.defaults.color = colors.text;
        Chart.defaults.borderColor = colors.line;
        Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
        Chart.defaults.animation = reducedMotion.matches ? false : { duration: 180 };
    }

    function destroyChart(key) {
        const canvas = document.getElementById(chartCanvasIds[key]);
        const tracked = charts[key];
        const registered = canvas && window.Chart ? Chart.getChart(canvas) : null;

        if (tracked && tracked !== registered) tracked.destroy();
        registered?.destroy();
        charts[key] = null;
    }

    function createChart(key, config) {
        const canvas = document.getElementById(chartCanvasIds[key]);
        if (!canvas) throw new Error(`Missing analytics canvas: ${key}`);

        destroyChart(key);
        try {
            charts[key] = new Chart(canvas, config);
            return charts[key];
        } catch (error) {
            Chart.getChart(canvas)?.destroy();
            charts[key] = null;
            setChartError(key, chartRenderErrors[key]);
            throw error;
        }
    }

    function setChartState(key, hasData) {
        const frame = document.querySelector(`[data-chart-frame="${key}"]`);
        if (!frame) return;
        const canvas = frame.querySelector('canvas');
        const empty = frame.querySelector('[data-chart-empty]');
        if (canvas) canvas.hidden = !hasData;
        if (empty) {
            empty.hidden = hasData;
            if (!hasData && chartEmptyMessages[key]) empty.textContent = chartEmptyMessages[key];
        }
    }

    function setChartError(key, message) {
        const frame = document.querySelector(`[data-chart-frame="${key}"]`);
        if (!frame) return;
        const canvas = frame.querySelector('canvas');
        const empty = frame.querySelector('[data-chart-empty]');
        if (canvas) canvas.hidden = true;
        if (empty) {
            empty.hidden = false;
            empty.textContent = message;
        }
    }

    function currencyTick(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return '';
        return `${numeric.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} €`;
    }

    function tooltipOptions() {
        const colors = palette();
        return {
            backgroundColor: colors.surface,
            borderColor: colors.line,
            borderWidth: 1,
            titleColor: cssColor('--text', '#f2f5f7'),
            bodyColor: colors.text,
            padding: 10,
            displayColors: false,
            callbacks: {
                label: context => money.format(Number(context.raw) || 0),
            },
        };
    }

    function commonOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'nearest' },
            animation: reducedMotion.matches ? false : { duration: 180 },
        };
    }

    function activeSlice() {
        const start = document.getElementById('startDate').value;
        const end = document.getElementById('endDate').value;
        const store = document.getElementById('storeFilter').value;
        const category = document.getElementById('categoryFilter').value;
        const item = document.getElementById('itemFilter').value.trim();
        const parts = [];
        if (start || end) parts.push(`${start || '…'} — ${end || '…'}`);
        if (store) parts.push(store);
        if (category) parts.push(category);
        if (item) parts.push(`товар: ${item}`);
        return {
            start,
            end,
            store,
            category,
            item,
            label: parts.length ? parts.join(' · ') : 'Все покупки',
        };
    }

    function localizedMonth(value) {
        if (!/^\d{4}-\d{2}$/.test(value || '')) return value || '';
        const [year, month] = value.split('-').map(Number);
        return monthName.format(new Date(Date.UTC(year, month - 1, 1))).replace(/\sг\.$/, '');
    }

    function pluralized(count, forms) {
        const absolute = Math.abs(Number(count)) % 100;
        const remainder = absolute % 10;
        if (absolute > 10 && absolute < 20) return forms[2];
        if (remainder === 1) return forms[0];
        if (remainder > 1 && remainder < 5) return forms[1];
        return forms[2];
    }

    function insightText(line) {
        switch (line.type) {
        case 'coverage':
            return `Срез охватывает ${line.period_count} ${pluralized(line.period_count, ['месяц', 'месяца', 'месяцев'])} и ${line.receipt_count} ${pluralized(line.receipt_count, ['чек', 'чека', 'чеков'])}.`;
        case 'month_change': {
            const current = localizedMonth(line.current_month);
            const previous = localizedMonth(line.previous_month);
            if (line.direction === 'unchanged') {
                return `Расходы за ${current} не изменились относительно ${previous}.`;
            }
            const verb = line.direction === 'increased' ? 'выросли' : 'снизились';
            return `Расходы за ${current} ${verb} относительно ${previous} на ${Number(line.change_percent).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}%.`;
        }
        case 'comparison_unavailable':
            return `Сравнение ${localizedMonth(line.current_month)} с ${localizedMonth(line.previous_month)} недоступно: в базовом месяце сумма равна нулю.`;
        case 'peak_month':
            return `Максимальная сумма в доступном периоде приходится на ${localizedMonth(line.month)} — ${money.format(line.amount)}.`;
        case 'largest_category':
            return `Крупнейшая категория — «${line.category}»: ${money.format(line.amount)}, или ${Number(line.share_percent).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}% суммы среза.`;
        case 'top_product':
            return `Наибольшая сумма среди товаров приходится на «${line.product}» — ${money.format(line.amount)}.`;
        default:
            return '';
        }
    }

    function renderInsightSummary(data) {
        const list = document.getElementById('analyticsInsightList');
        const empty = document.getElementById('analyticsInsightEmpty');
        const summary = data.insight_summary;
        const isEmpty = !summary || summary.state === 'empty';
        list.replaceChildren();
        list.hidden = isEmpty;
        empty.hidden = !isEmpty;
        if (isEmpty) return;

        summary.lines.slice(0, 3).forEach(line => {
            const text = insightText(line);
            if (!text) return;
            const item = document.createElement('li');
            item.textContent = text;
            list.append(item);
        });
    }

    function updateSummary(data) {
        const slice = activeSlice();
        const periodCount = data.months.labels.length;
        document.getElementById('analytics-summary-title').textContent = slice.label;
        document.getElementById('analyticsFilterState').textContent =
            slice.label === 'Все покупки' ? 'Все доступные покупки' : slice.label;
        document.getElementById('analyticsSliceDescription').textContent = periodCount
            ? `${periodCount} ${periodCount === 1 ? 'месяц' : 'месяцев'} с доступными значениями. Сумма рассчитана по позициям чеков.`
            : 'В выбранном срезе нет периодов с доступными значениями.';
        document.getElementById('totalSpent').textContent = money.format(data.total_spent);
        document.getElementById('monthlyAverage').textContent = money.format(data.monthly_average);
    }

    function renderMonthValues(data) {
        const list = document.getElementById('monthValueList');
        const toggle = document.getElementById('monthValueToggle');
        list.replaceChildren();
        list.dataset.expanded = 'false';
        data.months.labels.forEach((label, index) => {
            const group = document.createElement('div');
            const term = document.createElement('dt');
            const value = document.createElement('dd');
            if (index < data.months.labels.length - 6) group.classList.add('is-earlier-period');
            term.textContent = label;
            value.textContent = money.format(data.months.values[index] || 0);
            group.append(term, value);
            list.append(group);
        });
        toggle.hidden = data.months.labels.length <= 6;
        toggle.setAttribute('aria-expanded', 'false');
        toggle.textContent = 'Показать всю историю';
    }

    function renderMonths(data) {
        destroyChart('months');
        const hasData = data.months.labels.length > 0;
        setChartState('months', hasData);
        renderMonthValues(data);
        if (!hasData) return;

        const colors = palette();
        const canvas = document.getElementById('monthChart');
        canvas.setAttribute(
            'aria-label',
            `Динамика расходов: ${data.months.labels.map((label, index) => `${label} — ${money.format(data.months.values[index] || 0)}`).join('; ')}`
        );
        createChart('months', {
            type: 'line',
            data: {
                labels: data.months.labels,
                datasets: [{
                    label: 'Расходы',
                    data: data.months.values,
                    borderColor: colors.primary,
                    backgroundColor: `${colors.primary}1f`,
                    borderWidth: 2,
                    fill: true,
                    tension: .24,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: colors.surface,
                    pointBorderColor: colors.primary,
                    pointBorderWidth: 2,
                }],
            },
            options: {
                ...commonOptions(),
                layout: { padding: { top: 22, right: 12 } },
                plugins: {
                    legend: { display: false },
                    tooltip: tooltipOptions(),
                    datalabels: {
                        display: context => context.chart.data.labels.length <= 8,
                        align: 'top',
                        anchor: 'end',
                        color: colors.text,
                        formatter: value => currencyTick(value),
                        font: { size: 10, weight: '600' },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: window.innerWidth <= 560 ? 5 : 8,
                        },
                    },
                    y: {
                        beginAtZero: true,
                        border: { display: false },
                        grid: { color: colors.line },
                        ticks: { callback: currencyTick, maxTicksLimit: 5 },
                    },
                },
            },
            plugins: chartPlugins(),
        });
    }

    function horizontalBarOptions(colors) {
        return {
            ...commonOptions(),
            indexAxis: 'y',
            layout: { padding: { right: 64 } },
            plugins: {
                legend: { display: false },
                tooltip: tooltipOptions(),
                datalabels: {
                    anchor: 'end',
                    align: 'end',
                    clamp: true,
                    color: colors.text,
                    formatter: value => currencyTick(value),
                    font: { size: 10, weight: '600' },
                },
            },
            scales: {
                x: {
                    beginAtZero: true,
                    border: { display: false },
                    grid: { color: colors.line },
                    ticks: { callback: currencyTick, maxTicksLimit: 4 },
                },
                y: {
                    border: { display: false },
                    grid: { display: false },
                    ticks: { color: colors.text, autoSkip: false },
                },
            },
        };
    }

    function renderCategories(data) {
        destroyChart('categories');
        const hasData = data.categories.labels.length > 0;
        setChartState('categories', hasData);
        if (!hasData) return;

        const frame = document.querySelector('[data-chart-frame="categories"]');
        frame.style.setProperty('--analytics-category-height', `${Math.min(520, Math.max(260, data.categories.labels.length * 38))}px`);
        const colors = palette();
        const canvas = document.getElementById('categoryChart');
        canvas.setAttribute(
            'aria-label',
            `Расходы по категориям: ${data.categories.labels.map((label, index) => `${label} — ${money.format(data.categories.values[index] || 0)}`).join('; ')}`
        );
        createChart('categories', {
            type: 'bar',
            data: {
                labels: data.categories.labels,
                datasets: [{
                    label: 'Сумма',
                    data: data.categories.values,
                    backgroundColor: colors.category,
                    hoverBackgroundColor: colors.primary,
                    borderRadius: 3,
                    barThickness: 18,
                }],
            },
            options: horizontalBarOptions(colors),
            plugins: chartPlugins(),
        });
    }

    function renderTopLinks(labels) {
        const list = document.getElementById('topItemList');
        list.replaceChildren();
        labels.forEach(name => {
            const item = document.createElement('li');
            const link = document.createElement('a');
            link.href = `/item/${encodeURIComponent(name)}`;
            link.textContent = name;
            item.append(link);
            list.append(item);
        });
        document.getElementById('topItemLinks').hidden = labels.length === 0;
    }

    function renderTopItems(data) {
        destroyChart('top');
        const hasData = data.top.labels.length > 0;
        setChartState('top', hasData);
        renderTopLinks(data.top.labels);
        if (!hasData) return;

        const colors = palette();
        const canvas = document.getElementById('topItemsChart');
        canvas.setAttribute(
            'aria-label',
            `Товары с наибольшей суммой: ${data.top.labels.map((label, index) => `${label} — ${money.format(data.top.values[index] || 0)}`).join('; ')}`
        );
        createChart('top', {
            type: 'bar',
            data: {
                labels: data.top.labels,
                datasets: [{
                    label: 'Сумма',
                    data: data.top.values,
                    backgroundColor: colors.product,
                    hoverBackgroundColor: colors.trend,
                    borderRadius: 3,
                    barThickness: 16,
                }],
            },
            options: horizontalBarOptions(colors),
            plugins: chartPlugins(),
        });
    }

    function renderAnalytics(data) {
        configureChartDefaults();
        updateSummary(data);
        renderInsightSummary(data);
        renderMonths(data);
        renderCategories(data);
        renderTopItems(data);
    }

    async function loadAnalytics() {
        const slice = activeSlice();
        const params = new URLSearchParams({
            start: slice.start,
            end: slice.end,
            store: slice.store,
            category: slice.category,
            item: slice.item,
        });
        workspace.classList.add('is-loading');
        applyButton.disabled = true;
        status.textContent = 'Обновление среза…';

        try {
            const response = await fetch(`/analytics/data?${params.toString()}`);
            if (!response.ok) throw new Error(`Analytics request failed: ${response.status}`);
            lastAnalyticsData = await response.json();
            renderAnalytics(lastAnalyticsData);
            status.textContent = 'Срез обновлён';
        } catch (_) {
            status.textContent = 'Не удалось обновить данные';
        } finally {
            workspace.classList.remove('is-loading');
            applyButton.disabled = false;
        }
    }

    function renderTrend(data, itemName) {
        destroyChart('trend');
        const canvas = document.getElementById('trendChart');
        const message = document.getElementById('trendMsg');
        const frame = document.querySelector('[data-chart-frame="trend"]');
        const values = data.values.map(value => (Number.isFinite(value) && value > 0 ? value : null));
        const hasData = data.labels.length > 0 && values.some(value => value !== null);
        canvas.hidden = !hasData;
        message.hidden = hasData;
        if (!hasData) {
            frame.dataset.state = 'empty';
            message.textContent = `Для «${itemName}» нет доступной истории цены.`;
            return;
        }

        frame.dataset.state = 'ready';
        const colors = palette();
        canvas.setAttribute(
            'aria-label',
            `Динамика цены товара ${itemName}: ${data.labels.map((label, index) => `${label} — ${money.format(values[index] || 0)}`).join('; ')}`
        );
        createChart('trend', {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Цена за единицу',
                    data: values,
                    borderColor: colors.trend,
                    backgroundColor: `${colors.trend}1f`,
                    borderWidth: 2,
                    fill: true,
                    tension: .24,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                }],
            },
            options: {
                ...commonOptions(),
                plugins: {
                    legend: { display: false },
                    tooltip: tooltipOptions(),
                    datalabels: {
                        display: context => context.chart.data.labels.length <= 8,
                        align: 'top',
                        anchor: 'end',
                        color: colors.text,
                        formatter: value => currencyTick(value),
                        font: { size: 10, weight: '600' },
                    },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { maxRotation: 0, maxTicksLimit: 8 } },
                    y: {
                        beginAtZero: true,
                        border: { display: false },
                        grid: { color: colors.line },
                        ticks: { callback: currencyTick, maxTicksLimit: 5 },
                    },
                },
            },
            plugins: chartPlugins(),
        });
    }

    async function loadTrend() {
        const input = document.getElementById('itemTrendInput');
        const itemName = input.value.trim();
        if (!itemName) {
            input.focus();
            destroyChart('trend');
            lastTrendData = null;
            lastTrendName = '';
            const frame = document.querySelector('[data-chart-frame="trend"]');
            const canvas = document.getElementById('trendChart');
            const message = document.getElementById('trendMsg');
            frame.dataset.state = 'empty';
            canvas.hidden = true;
            message.hidden = false;
            message.textContent =
                'Выберите товар — здесь появится его помесячная динамика цены за единицу.';
            return;
        }

        const message = document.getElementById('trendMsg');
        const frame = document.querySelector('[data-chart-frame="trend"]');
        frame.dataset.state = 'loading';
        message.hidden = false;
        message.textContent = 'Загрузка истории…';
        try {
            const response = await fetch(`/analytics/item_trend?item=${encodeURIComponent(itemName)}`);
            if (!response.ok) throw new Error(`Trend request failed: ${response.status}`);
            lastTrendData = await response.json();
            lastTrendName = itemName;
            renderTrend(lastTrendData, lastTrendName);
        } catch (_) {
            destroyChart('trend');
            document.getElementById('trendChart').hidden = true;
            frame.dataset.state = 'error';
            message.hidden = false;
            message.textContent = 'Не удалось загрузить историю цены.';
        }
    }

    filters.addEventListener('submit', event => {
        event.preventDefault();
        loadAnalytics();
    });
    trendForm.addEventListener('submit', event => {
        event.preventDefault();
        loadTrend();
    });
    document.getElementById('monthValueToggle').addEventListener('click', event => {
        const list = document.getElementById('monthValueList');
        const expanded = event.currentTarget.getAttribute('aria-expanded') === 'true';
        event.currentTarget.setAttribute('aria-expanded', String(!expanded));
        event.currentTarget.textContent = expanded ? 'Показать всю историю' : 'Скрыть ранние месяцы';
        list.dataset.expanded = String(!expanded);
    });
    window.addEventListener('receipt-intelligence:themechange', () => {
        if (lastAnalyticsData) renderAnalytics(lastAnalyticsData);
        if (lastTrendData) renderTrend(lastTrendData, lastTrendName);
    });

    if (!window.Chart) {
        status.textContent = 'Графики недоступны';
        document.querySelectorAll('[data-chart-empty]').forEach(message => {
            message.hidden = false;
            message.textContent = 'Не удалось загрузить библиотеку графиков.';
        });
        return;
    }

    configureChartDefaults();
    loadAnalytics();
})();

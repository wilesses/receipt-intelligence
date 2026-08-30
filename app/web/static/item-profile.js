(function () {
    const root = document.querySelector('[data-product-trend]');
    if (!root) return;

    const canvas = root.querySelector('canvas');
    const canvasFrame = root.querySelector('[data-trend-canvas]');
    const state = root.querySelector('[data-trend-state]');
    const valueList = root.querySelector('[data-trend-values]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let chart = null;
    let trendData = null;

    function chartColors() {
        const styles = getComputedStyle(document.documentElement);
        return {
            text: styles.getPropertyValue('--text-secondary').trim() || '#a6b1bd',
            line: styles.getPropertyValue('--line').trim() || '#3a3a3a',
            primary: styles.getPropertyValue('--analytics-chart-primary').trim() || '#17d1ac',
            surface: styles.getPropertyValue('--surface').trim() || '#202020',
        };
    }

    function destroyChart() {
        if (chart) {
            chart.destroy();
            chart = null;
        }
        if (window.Chart && canvas) {
            const ownedChart = Chart.getChart(canvas);
            if (ownedChart) ownedChart.destroy();
        }
    }

    function showState(message) {
        destroyChart();
        canvasFrame.hidden = true;
        state.hidden = false;
        state.textContent = message;
    }

    function populateAccessibleValues(points, unitLabel) {
        valueList.replaceChildren();
        points.forEach((point) => {
            const item = document.createElement('li');
            item.textContent = `${point.label}: ${point.value.toFixed(2)} ${unitLabel}`;
            valueList.appendChild(item);
        });
    }

    function renderChart() {
        if (!trendData) return;
        if (trendData.status !== 'ready') {
            showState('Недостаточно сопоставимой истории цен для этого товара.');
            return;
        }
        if (!window.Chart) {
            showState('График сейчас недоступен. Все покупки сохранены в истории ниже.');
            return;
        }

        const points = trendData.labels
            .map((label, index) => ({ label, value: Number(trendData.values[index]) }))
            .filter((point) => Number.isFinite(point.value) && point.value > 0);
        const unitLabel = trendData.unit_label || '';

        if (points.length < 2) {
            showState(points.length === 1
                ? 'Есть одна сопоставимая точка — для динамики нужен ещё один период.'
                : 'Сопоставимой истории цен пока нет.');
            return;
        }

        destroyChart();
        const colors = chartColors();
        populateAccessibleValues(points, unitLabel);
        canvasFrame.hidden = false;
        state.hidden = true;
        canvas.setAttribute(
            'aria-label',
            `Медианная сопоставимая цена: ${points.map(point => `${point.label} — ${point.value.toFixed(2)} ${unitLabel}`).join('; ')}`
        );

        Chart.defaults.color = colors.text;
        Chart.defaults.borderColor = colors.line;
        chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: points.map((point) => point.label),
                datasets: [{
                    label: `Медианная сопоставимая цена, ${unitLabel}`,
                    data: points.map((point) => point.value),
                    borderColor: colors.primary,
                    backgroundColor: `${colors.primary}1f`,
                    borderWidth: 2,
                    pointBackgroundColor: colors.surface,
                    pointBorderColor: colors.primary,
                    pointBorderWidth: 2,
                    pointRadius: points.length > 18 ? 0 : 3,
                    pointHoverRadius: 5,
                    fill: true,
                    tension: 0.24,
                    spanGaps: false,
                }],
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                animation: reducedMotion.matches ? false : { duration: 180 },
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        displayColors: false,
                        callbacks: {
                            label: (context) => `${Number(context.raw).toFixed(2)} ${unitLabel}`,
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: colors.text, maxRotation: 0 },
                    },
                    y: {
                        beginAtZero: false,
                        border: { display: false },
                        grid: { color: colors.line },
                        ticks: {
                            color: colors.text,
                            callback: (value) => `${value} ${unitLabel}`,
                        },
                    },
                },
            },
        });
    }

    async function loadTrend() {
        try {
            const response = await fetch(root.dataset.trendUrl, { headers: { Accept: 'application/json' } });
            if (!response.ok) throw new Error(`Trend request failed: ${response.status}`);
            trendData = await response.json();
            if (!trendData || !Array.isArray(trendData.labels) || !Array.isArray(trendData.values)) {
                throw new Error('Trend response has an unexpected shape');
            }
            renderChart();
        } catch (error) {
            showState('Не удалось показать график. История покупок ниже остаётся доступной.');
        }
    }

    window.addEventListener('receipt-intelligence:themechange', renderChart);
    reducedMotion.addEventListener?.('change', renderChart);
    loadTrend();
})();

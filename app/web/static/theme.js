(() => {
    'use strict';

    const STORAGE_KEY = 'receipt-intelligence:theme:v1';
    const ALLOWED = new Set(['system', 'light', 'dark']);
    const root = document.documentElement;
    const control = document.querySelector('[data-theme-control]');
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');

    function resolveTheme(choice) {
        return choice === 'system' ? (systemTheme.matches ? 'dark' : 'light') : choice;
    }

    function applyTheme(choice, persist = false) {
        const safeChoice = ALLOWED.has(choice) ? choice : 'system';
        const resolved = resolveTheme(safeChoice);

        root.dataset.theme = resolved;
        root.dataset.themeChoice = safeChoice;
        root.dataset.bsTheme = resolved;
        root.style.colorScheme = resolved;
        document.querySelector('[data-theme-color]')?.setAttribute(
            'content',
            resolved === 'dark' ? '#161616' : '#f7f8f6'
        );
        if (control) control.value = safeChoice;

        if (persist) {
            try {
                localStorage.setItem(STORAGE_KEY, safeChoice);
            } catch (_) {}
        }

        window.dispatchEvent(new CustomEvent('receipt-intelligence:themechange', {
            detail: { choice: safeChoice, resolved },
        }));
    }

    control?.addEventListener('change', (event) => applyTheme(event.target.value, true));
    systemTheme.addEventListener?.('change', () => {
        if (root.dataset.themeChoice === 'system') applyTheme('system');
    });
    applyTheme(root.dataset.themeChoice);
})();

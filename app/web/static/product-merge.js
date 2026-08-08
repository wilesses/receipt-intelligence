(() => {
    const form = document.querySelector('[data-merge-form]');
    if (!form) return;

    const checkboxes = Array.from(form.querySelectorAll('input[name="selected_names"]'));
    const selectedCount = form.querySelector('[data-selected-count]');
    const affectedRows = form.querySelector('[data-affected-rows]');
    const affectedReceipts = form.querySelector('[data-affected-receipts]');
    const selectedList = form.querySelector('[data-selected-list]');
    const resetButton = form.querySelector('[data-reset-selection]');
    const canonicalInput = form.querySelector('input[name="canonical_name"]');
    const canonicalError = form.querySelector('[data-canonical-error]');
    const submitButton = form.querySelector('[data-merge-submit]');

    const selectedCheckboxes = () => checkboxes.filter(checkbox => checkbox.checked);

    const renderSelection = () => {
        const selected = selectedCheckboxes();
        let rowTotal = 0;
        let receiptTotal = 0;

        checkboxes.forEach(checkbox => {
            const row = checkbox.closest('[data-selection-row]');
            const isSelected = checkbox.checked;
            row?.setAttribute('data-selected', String(isSelected));
            const state = row?.querySelector('[data-selected-state]');
            if (state) state.textContent = isSelected ? 'Выбран' : 'Не выбран';
            if (isSelected) {
                rowTotal += Number.parseInt(checkbox.dataset.itemCount || '0', 10);
                receiptTotal += Number.parseInt(checkbox.dataset.receiptCount || '0', 10);
            }
        });

        if (selectedCount) selectedCount.textContent = String(selected.length);
        if (affectedRows) affectedRows.textContent = String(rowTotal);
        if (affectedReceipts) affectedReceipts.textContent = String(receiptTotal);
        if (submitButton) submitButton.disabled = selected.length === 0;
        if (resetButton) resetButton.disabled = selected.length === 0;

        if (selectedList) {
            selectedList.replaceChildren();
            if (selected.length === 0) {
                const placeholder = document.createElement('li');
                placeholder.dataset.selectionPlaceholder = '';
                placeholder.textContent = 'Товары ещё не выбраны.';
                selectedList.append(placeholder);
            } else {
                selected.forEach(checkbox => {
                    const item = document.createElement('li');
                    item.textContent = checkbox.value;
                    selectedList.append(item);
                });
            }
        }
    };

    const clearCanonicalError = () => {
        canonicalInput?.setCustomValidity('');
        if (canonicalError) canonicalError.textContent = '';
    };

    checkboxes.forEach(checkbox => checkbox.addEventListener('change', renderSelection));
    canonicalInput?.addEventListener('input', clearCanonicalError);

    resetButton?.addEventListener('click', () => {
        checkboxes.forEach(checkbox => { checkbox.checked = false; });
        if (canonicalInput) canonicalInput.value = '';
        clearCanonicalError();
        renderSelection();
        checkboxes[0]?.focus();
    });

    form.addEventListener('submit', event => {
        const selected = selectedCheckboxes();
        const canonicalName = canonicalInput?.value.trim() || '';

        if (selected.length === 0) {
            event.preventDefault();
            checkboxes[0]?.focus();
            return;
        }

        if (!canonicalName) {
            event.preventDefault();
            const message = 'Введите каноническое название без одних пробелов.';
            canonicalInput?.setCustomValidity(message);
            if (canonicalError) canonicalError.textContent = message;
            canonicalInput?.reportValidity();
            canonicalInput?.focus();
            return;
        }

        if (canonicalInput) canonicalInput.value = canonicalName;
        clearCanonicalError();
    });

    renderSelection();
})();

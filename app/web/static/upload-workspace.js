(function () {
    const workspace = document.querySelector('[data-upload-workspace]');
    if (!workspace) return;

    const dropzone = workspace.querySelector('#dropzone');
    const fileInput = workspace.querySelector('#fileInput');
    const uploadBtn = workspace.querySelector('#uploadBtn');
    const gmailBtn = workspace.querySelector('#gmailBtn');
    const fileList = workspace.querySelector('#fileList');
    const fileCounter = workspace.querySelector('#fileCounter');
    const commandState = workspace.querySelector('[data-upload-command-state]');
    const feedback = workspace.querySelector('.upload-feedback');
    const status = workspace.querySelector('#status');
    const results = workspace.querySelector('#results');
    const progressBar = workspace.querySelector('#progressBar');
    const progressContainer = workspace.querySelector('#progressContainer');
    let filesToUpload = [];

    function formatFileCount(count) {
        const lastTwo = count % 100;
        const last = count % 10;
        if (lastTwo >= 11 && lastTwo <= 14) return `${count} файлов`;
        if (last === 1) return `${count} файл`;
        if (last >= 2 && last <= 4) return `${count} файла`;
        return `${count} файлов`;
    }

    function formatFileSize(size) {
        if (!Number.isFinite(size) || size <= 0) return 'Размер не определён';
        if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} КБ`;
        return `${(size / (1024 * 1024)).toFixed(1)} МБ`;
    }

    function createQueueEmpty() {
        const empty = document.createElement('div');
        empty.className = 'upload-queue-empty';
        empty.dataset.uploadEmpty = '';

        const title = document.createElement('strong');
        title.textContent = 'Очередь пока пуста';
        const copy = document.createElement('p');
        copy.textContent = 'Выбранные PDF появятся здесь до начала импорта.';
        empty.append(title, copy);
        return empty;
    }

    function createFileRecord(file, index) {
        const record = document.createElement('article');
        record.className = 'upload-file-record';

        const identity = document.createElement('div');
        identity.className = 'upload-file-identity';
        const order = document.createElement('span');
        order.textContent = String(index + 1).padStart(2, '0');
        const copy = document.createElement('div');
        const name = document.createElement('strong');
        name.textContent = file.name;
        const metadata = document.createElement('small');
        metadata.textContent = `PDF · ${formatFileSize(file.size)}`;
        copy.append(name, metadata);
        identity.append(order, copy);

        const state = document.createElement('span');
        state.className = 'upload-file-state';
        state.textContent = 'Готов к импорту';
        record.append(identity, state);
        return record;
    }

    function renderFileList() {
        fileList.replaceChildren();
        fileCounter.textContent = formatFileCount(filesToUpload.length);
        uploadBtn.disabled = filesToUpload.length === 0;

        if (filesToUpload.length === 0) {
            fileList.append(createQueueEmpty());
            commandState.textContent = 'Сначала выберите хотя бы один PDF-файл.';
            return;
        }

        const records = document.createDocumentFragment();
        filesToUpload.forEach((file, index) => records.append(createFileRecord(file, index)));
        fileList.append(records);
        commandState.textContent = `${formatFileCount(filesToUpload.length)} будут обработаны последовательно.`;
    }

    function setFeedback(message, tone = 'neutral') {
        feedback.hidden = false;
        status.className = `upload-status is-${tone}`;
        status.textContent = message;
    }

    function createResultBlock(title, items, tone, formatItem) {
        if (!items || items.length === 0) return null;
        const block = document.createElement('section');
        block.className = `upload-result-block is-${tone}`;
        const heading = document.createElement('h3');
        heading.textContent = title;
        const list = document.createElement('ul');
        items.forEach((item) => {
            const entry = document.createElement('li');
            entry.textContent = formatItem(item);
            list.append(entry);
        });
        block.append(heading, list);
        return block;
    }

    function renderUploadResults(result) {
        results.replaceChildren();
        const uploaded = createResultBlock(
            'Импортировано',
            result.uploaded,
            'success',
            (item) => `${item.file} — ${item.message || 'Готово'}`,
        );
        const errors = createResultBlock(
            'Требуют внимания',
            result.errors,
            'error',
            (item) => `${item.file}: ${item.error}`,
        );
        if (uploaded) results.append(uploaded);
        if (errors) results.append(errors);
    }

    function renderMailResults(result) {
        results.replaceChildren();
        const imported = createResultBlock(
            'Импортировано из почты',
            result.imported,
            'success',
            (item) => `${item.file} — ${item.message || 'Готово'}`,
        );
        const errors = createResultBlock(
            'Требуют внимания',
            result.errors,
            'error',
            (item) => `${item.file}: ${item.error}`,
        );
        const skipped = createResultBlock(
            'Пропущено',
            result.skipped_files,
            'neutral',
            (item) => item,
        );
        [imported, errors, skipped].filter(Boolean).forEach((block) => results.append(block));
        if (!results.childElementCount) {
            const empty = document.createElement('p');
            empty.className = 'upload-results-empty';
            empty.textContent = 'Новых PDF-вложений не найдено.';
            results.append(empty);
        }
    }

    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        filesToUpload = Array.from(fileInput.files);
        renderFileList();
    });

    dropzone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropzone.classList.add('is-dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('is-dragover');
    });

    dropzone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-dragover');
        filesToUpload = Array.from(event.dataTransfer.files);
        renderFileList();
    });

    uploadBtn.addEventListener('click', async () => {
        if (filesToUpload.length === 0) {
            setFeedback('Выберите хотя бы один PDF-файл.', 'error');
            return;
        }

        const formData = new FormData();
        filesToUpload.forEach((file) => formData.append('pdfs', file));
        results.replaceChildren();
        setFeedback('Импортируем выбранные файлы…', 'busy');
        progressContainer.hidden = false;
        progressBar.style.setProperty('--progress-scale', '.35');
        progressBar.setAttribute('aria-valuenow', '35');
        uploadBtn.disabled = true;

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const result = await response.json();
            progressBar.style.setProperty('--progress-scale', '1');
            progressBar.setAttribute('aria-valuenow', '100');

            if (response.ok && result.status === 'ok') {
                setFeedback(`Импорт завершён: ${result.uploaded.length}, требуют внимания: ${result.errors.length}.`, result.errors.length ? 'warning' : 'success');
                renderUploadResults(result);
            } else {
                setFeedback(result.message || 'Не удалось импортировать файлы.', 'error');
            }
        } catch (error) {
            setFeedback('Не удалось подключиться к серверу.', 'error');
        } finally {
            uploadBtn.disabled = filesToUpload.length === 0;
        }
    });

    gmailBtn.addEventListener('click', async () => {
        results.replaceChildren();
        setFeedback('Проверяем вложения в почте…', 'busy');
        gmailBtn.disabled = true;

        try {
            const response = await fetch('/gmail/fetch', { method: 'POST' });
            const result = await response.json();
            if (!response.ok || result.status !== 'ok') {
                setFeedback(result.message || 'Не удалось проверить почту.', 'error');
                return;
            }

            const foundPdfCount = result.files_saved.length + (result.files_existing?.length || 0);
            setFeedback(`Проверено писем: ${result.emails_checked}. Найдено PDF: ${foundPdfCount}.`, result.errors.length ? 'warning' : 'success');
            renderMailResults(result);
        } catch (error) {
            setFeedback('Не удалось подключиться к Gmail.', 'error');
        } finally {
            gmailBtn.disabled = false;
        }
    });

    renderFileList();
})();

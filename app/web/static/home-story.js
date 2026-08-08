(() => {
    'use strict';

    const VERSION = 1;
    const KEY_PREFIX = 'receipt-intelligence:story:v1:';
    const MONTH_KEY_PATTERN = /^\d{4}-\d{2}$/;
    const metadataElement = document.getElementById('story-metadata');
    const story = document.querySelector('.home-document');

    if (!metadataElement || !story) return;

    function isNonEmptyString(value) {
        return typeof value === 'string' && value.trim().length > 0;
    }

    function isValidReceiptId(value) {
        return value === null || (Number.isInteger(value) && value >= 0);
    }

    function isValidMetadata(value) {
        return Boolean(
            value
            && MONTH_KEY_PATTERN.test(value.month_key)
            && isNonEmptyString(value.signature)
            && typeof value.has_story === 'boolean'
            && value.has_story
            && isValidReceiptId(value.last_receipt_id)
        );
    }

    function isValidViewedState(value) {
        return Boolean(
            value
            && value.version === VERSION
            && isNonEmptyString(value.signature)
            && isNonEmptyString(value.viewed_at)
            && !Number.isNaN(Date.parse(value.viewed_at))
            && isValidReceiptId(value.last_receipt_id)
        );
    }

    function determineStoryMode(metadata, viewedState) {
        if (!isValidMetadata(metadata) || !isValidViewedState(viewedState)) return 'new';
        return viewedState.signature === metadata.signature ? 'repeat' : 'update';
    }

    function parseMetadata() {
        try {
            const value = JSON.parse(metadataElement.textContent);
            return isValidMetadata(value) ? value : null;
        } catch (_) {
            return null;
        }
    }

    function readViewedState(storageKey) {
        try {
            const raw = localStorage.getItem(storageKey);
            if (!raw) return null;
            return JSON.parse(raw);
        } catch (_) {
            return null;
        }
    }

    const metadata = parseMetadata();
    const storageKey = metadata ? `${KEY_PREFIX}${metadata.month_key}` : null;
    const viewedState = storageKey ? readViewedState(storageKey) : null;
    let mode = determineStoryMode(metadata, viewedState);
    let hasPersisted = false;

    const monthDetails = document.getElementById('story-month-details');
    const highlighted = document.querySelector('.story-highlighted');
    const insightDetails = document.getElementById('story-insight-copy-details');
    const evidenceDetails = document.querySelector('.story-evidence');
    const archiveLink = document.querySelector('.story-archive-link');
    const replayButton = document.querySelector('.story-replay');
    const replayLabel = replayButton ? replayButton.firstChild : null;
    const debugVisit = document.querySelector('[data-debug-visit]');
    const debugReplay = document.querySelector('[data-debug-replay]');
    const isCinematic = story.dataset.storyPresentation === 'cinematic';

    function setHidden(element, hidden) {
        if (element) element.hidden = hidden;
    }

    function applyMode(nextMode) {
        const isRepeat = nextMode === 'repeat';
        const isUpdate = nextMode === 'update';
        const isReplay = nextMode === 'replay';

        story.dataset.storyMode = nextMode;
        setHidden(monthDetails, isRepeat && !isCinematic);
        setHidden(highlighted, isUpdate && !isCinematic);
        setHidden(insightDetails, isRepeat && !isCinematic);
        setHidden(evidenceDetails, isRepeat && !isCinematic);
        setHidden(archiveLink, isRepeat || isUpdate);

        if (replayButton) {
            replayButton.setAttribute('aria-expanded', String(isReplay));
            replayButton.setAttribute('aria-disabled', String(isReplay));
            if (replayLabel) replayLabel.textContent = isReplay ? 'История раскрыта ' : 'Повторить историю ';
        }

        document.documentElement.dataset.storyMode = nextMode;
        delete document.documentElement.dataset.storyBootstrapMode;
        if (debugVisit) debugVisit.value = nextMode;
        if (debugReplay) debugReplay.value = String(isReplay);
        mode = nextMode;
        document.dispatchEvent(new CustomEvent('story:modechange', {
            detail: { mode: nextMode },
        }));
    }

    function persistViewedState() {
        if (hasPersisted || !metadata || !storageKey) return;
        try {
            localStorage.setItem(storageKey, JSON.stringify({
                version: VERSION,
                signature: metadata.signature,
                viewed_at: new Date().toISOString(),
                last_receipt_id: metadata.last_receipt_id,
            }));
            hasPersisted = true;
        } catch (_) {}
    }

    function observeMeaningfulView() {
        if (isCinematic) {
            document.addEventListener('story:sequencecomplete', persistViewedState);
            return;
        }

        const insight = document.querySelector('[data-story-act="insight"]');
        const workspace = document.querySelector('[data-story-act="workspace"]');
        const targets = [insight, workspace].filter(Boolean);

        if ('IntersectionObserver' in window && targets.length) {
            const observer = new IntersectionObserver((entries) => {
                if (!entries.some((entry) => entry.isIntersecting)) return;
                persistViewedState();
                observer.disconnect();
            }, { threshold: 0.2 });
            targets.forEach((target) => observer.observe(target));
            return;
        }

        targets.forEach((target) => target.addEventListener('focusin', persistViewedState, { once: true }));
        window.addEventListener('pagehide', () => {
            if (window.scrollY > 0) persistViewedState();
        }, { once: true });
    }

    if (replayButton) {
        replayButton.addEventListener('click', () => {
            if (mode === 'replay') return;
            applyMode('replay');
        });

        document.addEventListener('story:sequencecomplete', () => {
            if (mode !== 'replay') return;
            mode = 'repeat';
            replayButton.setAttribute('aria-expanded', 'false');
            replayButton.setAttribute('aria-disabled', 'false');
            if (replayLabel) replayLabel.textContent = 'Повторить историю ';
            if (debugReplay) debugReplay.value = 'false';
        });
    }

    if (archiveLink) archiveLink.addEventListener('click', persistViewedState);

    applyMode(mode);
    observeMeaningfulView();
})();

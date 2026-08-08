(() => {
    const drawer = document.querySelector('.receipt-drawer');
    const scrim = document.querySelector('.receipt-drawer-scrim');
    if (!drawer || !scrim) return;

    const triggers = document.querySelectorAll('[data-open-receipt-drawer]');
    const closeControls = document.querySelectorAll('[data-close-receipt-drawer]');
    const closeButton = drawer.querySelector('[data-close-receipt-drawer]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let activeTrigger = null;
    let state = 'closed';
    let generation = 0;
    let entryFrame = null;
    let transitionCleanup = null;

    function setText(selector, value, fallback = '—') {
        const target = drawer.querySelector(selector);
        if (target) target.textContent = value || fallback;
    }

    function cancelPending() {
        if (entryFrame !== null) {
            cancelAnimationFrame(entryFrame);
            entryFrame = null;
        }
        transitionCleanup?.();
        transitionCleanup = null;
    }

    function updateDrawer(trigger) {
        const receiptId = trigger.dataset.receiptId || '';
        const store = trigger.dataset.receiptStore || 'Магазин не указан';

        setText('[data-receipt-drawer-identity]', `${store}, чек #${receiptId}`);
        setText('[data-receipt-drawer-id]', receiptId ? `#${receiptId}` : '');
        setText('[data-receipt-drawer-store]', store);
        setText('[data-receipt-drawer-number]', trigger.dataset.receiptNumber, 'Не указан');
        setText('[data-receipt-drawer-item-count]', trigger.dataset.receiptItemCount, '0');
        setText('[data-receipt-drawer-review-count]', trigger.dataset.receiptReviewCount, '0');
    }

    function finishClose() {
        if (state !== 'closing') return;
        cancelPending();
        drawer.hidden = true;
        scrim.hidden = true;
        document.body.classList.remove('drawer-open');
        state = 'closed';
        if (activeTrigger?.isConnected && !activeTrigger.disabled) activeTrigger?.focus();
        activeTrigger = null;
    }

    function waitForExit(expectedGeneration) {
        const finish = () => {
            if (generation !== expectedGeneration || state !== 'closing') return;
            finishClose();
        };
        const onTransitionEnd = event => {
            if (
                event.target === drawer &&
                (event.propertyName === 'transform' || event.propertyName === 'opacity')
            ) finish();
        };
        const timer = window.setTimeout(finish, reducedMotion.matches ? 160 : 280);
        drawer.addEventListener('transitionend', onTransitionEnd);
        transitionCleanup = () => {
            window.clearTimeout(timer);
            drawer.removeEventListener('transitionend', onTransitionEnd);
        };
    }

    function openDrawer(trigger) {
        updateDrawer(trigger);
        activeTrigger = trigger;

        if (state === 'open' || state === 'opening') {
            closeButton?.focus();
            return;
        }

        const wasClosing = state === 'closing';
        const expectedGeneration = ++generation;
        cancelPending();

        drawer.hidden = false;
        scrim.hidden = false;
        document.body.classList.add('drawer-open');
        state = 'opening';

        const show = () => {
            entryFrame = null;
            if (generation !== expectedGeneration || state !== 'opening') return;
            drawer.classList.add('is-open');
            scrim.classList.add('is-open');
            state = 'open';
            closeButton?.focus();
        };

        if (wasClosing) show();
        else entryFrame = requestAnimationFrame(show);
    }

    function closeDrawer() {
        if (state === 'closed' || state === 'closing') return;
        const hadOpenClass = drawer.classList.contains('is-open');
        const expectedGeneration = ++generation;
        cancelPending();
        state = 'closing';
        drawer.classList.remove('is-open');
        scrim.classList.remove('is-open');
        if (hadOpenClass) waitForExit(expectedGeneration);
        else finishClose();
    }

    triggers.forEach(trigger => {
        trigger.addEventListener('click', () => openDrawer(trigger));
    });
    closeControls.forEach(control => {
        control.addEventListener('click', closeDrawer);
    });

    document.addEventListener('keydown', event => {
        if (drawer.hidden) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            closeDrawer();
            return;
        }
        if (event.key !== 'Tab') return;

        const focusable = Array.from(
            drawer.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')
        );
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!drawer.contains(document.activeElement)) {
            event.preventDefault();
            (event.shiftKey ? last : first).focus();
        } else if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
})();

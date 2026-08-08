(() => {
    'use strict';

    const story = document.querySelector('.home-document');
    if (!story) return;

    const VISIT_MODES = new Set(['new', 'update', 'repeat', 'replay']);
    const presentation = 'cinematic';
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const supportsMotion = 'animate' in Element.prototype;
    const easing = {
        standard: 'cubic-bezier(.2, 0, 0, 1)',
        emphasized: 'cubic-bezier(.16, 1, .3, 1)',
    };
    const debug = {
        phase: document.querySelector('[data-debug-phase]'),
        progress: document.querySelector('[data-debug-progress]'),
        reduced: document.querySelector('[data-debug-reduced]'),
    };

    function clamp(value, min = 0, max = 1) {
        return Math.min(max, Math.max(min, value));
    }

    function segment(progress, start, end) {
        return clamp((progress - start) / (end - start));
    }

    function setOutput(output, value) {
        if (!output) return;
        output.value = String(value);
        output.textContent = String(value);
    }

    function setPhase(phase, progress = null) {
        document.documentElement.dataset.storyMotionPhase = phase;
        setOutput(debug.phase, phase);
        if (progress !== null) setOutput(debug.progress, Number(progress).toFixed(3));
        setOutput(debug.reduced, reducedMotion.matches);
    }

    function normalizedText(element) {
        return element?.textContent.replace(/\s+/g, '') || '';
    }

    function focusStoryStart() {
        const heading = story.querySelector('#story-month-title');
        if (!heading) return;
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
        heading.addEventListener('blur', () => heading.removeAttribute('tabindex'), { once: true });
    }

    class MotionRuntime {
        constructor(root) {
            this.root = root;
            this.animations = new Set();
            this.timers = new Set();
            this.handoffObserver = null;
            this.handoff = null;
            this.sequenceComplete = false;
            this.destinationVisible = false;
            this.generation = 0;
        }

        animate(element, keyframes, options = {}) {
            if (!element || reducedMotion.matches || !supportsMotion) return null;
            const animation = element.animate(keyframes, {
                duration: 300,
                easing: easing.standard,
                fill: 'backwards',
                ...options,
            });
            this.animations.add(animation);
            animation.finished.catch(() => {}).finally(() => this.animations.delete(animation));
            return animation;
        }

        animateGroup(elements, keyframes, options = {}) {
            const { stagger = 0, delay = 0, ...animationOptions } = options;
            Array.from(elements).forEach((element, index) => {
                this.animate(element, keyframes, {
                    ...animationOptions,
                    delay: delay + index * stagger,
                });
            });
        }

        after(delay, callback) {
            const generation = this.generation;
            const timer = window.setTimeout(() => {
                this.timers.delete(timer);
                if (generation === this.generation) callback();
            }, delay);
            this.timers.add(timer);
            return timer;
        }

        cancelHandoff() {
            if (!this.handoff) return;
            const { clone, animation, source, destination, controls, cleanup } = this.handoff;
            cleanup();
            animation?.cancel();
            clone.remove();
            source.removeAttribute('data-motion-shared-hidden');
            destination.removeAttribute('data-motion-shared-hidden');
            controls.forEach((element) => {
                element.style.removeProperty('opacity');
                element.style.removeProperty('transform');
            });
            this.handoff = null;
        }

        cancel() {
            this.generation += 1;
            this.animations.forEach((animation) => animation.cancel());
            this.animations.clear();
            this.timers.forEach((timer) => window.clearTimeout(timer));
            this.timers.clear();
            this.handoffObserver?.disconnect();
            this.handoffObserver = null;
            this.sequenceComplete = false;
            this.destinationVisible = false;
            this.cancelHandoff();
            this.root.querySelectorAll('.story-timeline-list.is-motion-line').forEach((line) => {
                line.classList.remove('is-motion-line');
                line.style.removeProperty('--story-line-progress');
                line.style.removeProperty('--story-line-duration');
            });
        }

        armHandoff() {
            if (reducedMotion.matches || !supportsMotion) return;
            const destination = this.root.querySelector('[data-story-total-destination]');
            if (!destination || !('IntersectionObserver' in window)) return;
            this.handoffObserver?.disconnect();
            this.handoffObserver = new IntersectionObserver((entries) => {
                this.destinationVisible = entries.some((entry) => entry.isIntersecting);
                if (this.destinationVisible && this.sequenceComplete) this.scheduleHandoff();
            }, { threshold: .45, rootMargin: '0px 0px -4% 0px' });
            this.handoffObserver.observe(destination);
        }

        completeSequence() {
            this.sequenceComplete = true;
            setPhase('complete');
            document.dispatchEvent(new CustomEvent('story:sequencecomplete', {
                detail: { presentation, visitMode: story.dataset.storyMode },
            }));
            if (this.destinationVisible) this.scheduleHandoff();
        }

        scheduleHandoff() {
            if (this.handoff || reducedMotion.matches) return;
            let idleTimer = null;
            const cleanupIdle = () => {
                window.removeEventListener('scroll', onScroll);
                if (idleTimer) window.clearTimeout(idleTimer);
            };
            const begin = () => {
                cleanupIdle();
                this.beginHandoff();
            };
            const onScroll = () => {
                if (idleTimer) window.clearTimeout(idleTimer);
                idleTimer = window.setTimeout(begin, 120);
            };
            window.addEventListener('scroll', onScroll, { passive: true });
            onScroll();
        }

        beginHandoff() {
            if (this.handoff || reducedMotion.matches || document.hidden) return;
            const source = this.root.querySelector('[data-story-total-source] strong');
            const destination = this.root.querySelector('[data-story-total-destination] dd');
            if (!source || !destination || normalizedText(source) !== normalizedText(destination)) return;

            const sourceRect = source.getBoundingClientRect();
            const destinationRect = destination.getBoundingClientRect();
            if (!sourceRect.width || !destinationRect.width || !destinationRect.height) return;

            const sourceVisible = sourceRect.bottom > 0 && sourceRect.top < window.innerHeight;
            const startScale = sourceVisible ? 1 : (window.innerWidth < 600 ? .72 : .62);
            const cinematicDock = this.presentation === 'cinematic';
            const startLeft = sourceVisible
                ? sourceRect.left
                : cinematicDock
                    ? window.innerWidth - sourceRect.width * startScale - 28
                    : clamp(sourceRect.left, 20, window.innerWidth - sourceRect.width * startScale - 20);
            const startTop = sourceVisible
                ? sourceRect.top
                : cinematicDock
                    ? window.innerHeight - sourceRect.height * startScale - 28
                    : 20;
            const targetScale = Math.max(.12, destinationRect.height / sourceRect.height);
            const targetLeft = destinationRect.right - sourceRect.width * targetScale;
            const targetTop = destinationRect.top + (destinationRect.height - sourceRect.height * targetScale) / 2;
            const clone = source.cloneNode(true);
            clone.classList.add('story-total-clone');
            clone.setAttribute('aria-hidden', 'true');
            clone.style.left = `${startLeft}px`;
            clone.style.top = `${startTop}px`;
            clone.style.width = `${sourceRect.width}px`;
            clone.style.height = `${sourceRect.height}px`;

            const computed = getComputedStyle(source);
            ['color', 'fontFamily', 'fontSize', 'fontWeight', 'fontVariantNumeric', 'letterSpacing', 'lineHeight', 'whiteSpace']
                .forEach((property) => { clone.style[property] = computed[property]; });

            const controls = Array.from(this.root.querySelectorAll(
                '.is-story-workspace .receipt-context, .is-story-workspace .receipts-import, .is-story-workspace .receipt-filter-panel'
            ));
            const cancel = () => this.cancelHandoff();
            const cleanup = () => {
                window.removeEventListener('scroll', cancel);
                window.removeEventListener('resize', cancel);
                window.removeEventListener('orientationchange', cancel);
                document.removeEventListener('visibilitychange', cancel);
            };

            document.body.appendChild(clone);
            source.setAttribute('data-motion-shared-hidden', '');
            destination.setAttribute('data-motion-shared-hidden', '');
            controls.forEach((element) => { element.style.opacity = '.72'; });
            setPhase('handoff');

            const animation = this.animate(clone, [
                { transform: `translate3d(0, 0, 0) scale(${startScale})`, opacity: 1 },
                { transform: `translate3d(${targetLeft - startLeft}px, ${targetTop - startTop}px, 0) scale(${targetScale})`, opacity: 1 },
            ], { duration: 340, easing: easing.emphasized, fill: 'forwards' });

            this.handoff = { clone, animation, source, destination, controls, cleanup };
            window.addEventListener('scroll', cancel, { passive: true, once: true });
            window.addEventListener('resize', cancel, { once: true });
            window.addEventListener('orientationchange', cancel, { once: true });
            document.addEventListener('visibilitychange', cancel, { once: true });

            animation?.finished.then(() => {
                if (!this.handoff) return;
                cleanup();
                clone.remove();
                source.removeAttribute('data-motion-shared-hidden');
                destination.removeAttribute('data-motion-shared-hidden');
                this.handoff = null;
                this.animateGroup(controls, [
                    { opacity: .72, transform: 'translateY(4px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: 180 });
                controls.forEach((element) => element.style.removeProperty('opacity'));
                setPhase('workspace');
            }).catch(() => {});
        }
    }

    function prepareReplay() {
        focusStoryStart();
        if (!reducedMotion.matches) story.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function playProductProfile(runtime, mode, options = {}) {
        const compact = mode === 'update';
        const fullDuration = compact ? 2640 : 3480;
        const monthLabel = story.querySelector('.story-act-month .story-index');
        const monthTitle = story.querySelector('#story-month-title');
        const period = story.querySelector('.story-period');
        const line = story.querySelector('.story-timeline-list');
        const allMarkers = story.querySelector('.story-timeline-list');
        const highlightMarkers = story.querySelectorAll('.story-timeline-event.is-highlighted .story-event-marker');
        const receipts = story.querySelectorAll('.story-highlighted li');
        const receiptTotals = story.querySelectorAll('.story-receipt-total');
        const remainder = story.querySelector('.story-remainder');
        const total = story.querySelector('[data-story-total-source] strong');
        const insightTitle = story.querySelector('#story-insight-title');
        const metric = story.querySelector('.story-metric');
        const evidence = story.querySelectorAll('.story-evidence li');
        const links = story.querySelectorAll('.story-destination-link, .story-archive-link:not([hidden])');

        document.documentElement.dataset.storyMotionReady = 'true';
        document.documentElement.dataset.storyMotionProfile = compact ? 'product-update' : 'product-full';
        setPhase(compact ? 'a1-update' : 'a1');

        runtime.animate(monthLabel, [
            { opacity: .42, transform: 'translateY(24px) scale(.96)' },
            { opacity: 1, transform: 'translateY(0) scale(1)' },
        ], { duration: compact ? 220 : 300, easing: easing.emphasized });
        runtime.animate(monthTitle, [
            { opacity: .38, transform: 'translateY(42px) scale(.91)' },
            { opacity: 1, transform: 'translateY(0) scale(1)' },
        ], { duration: compact ? 280 : 420, delay: 60, easing: easing.emphasized });
        runtime.animate(period, [
            { opacity: .45, transform: 'translateY(20px)' },
            { opacity: 1, transform: 'translateY(0)' },
        ], { duration: compact ? 220 : 320, delay: 120 });

        runtime.after(compact ? 220 : 340, () => setPhase(compact ? 'a2-update' : 'a2'));
        if (line) {
            line.classList.add('is-motion-line');
            line.style.setProperty('--story-line-progress', '0');
            line.style.setProperty('--story-line-duration', compact ? '420ms' : '620ms');
            runtime.after(compact ? 220 : 340, () => line.style.setProperty('--story-line-progress', '1'));
        }
        runtime.animate(allMarkers, [
            { opacity: .35, transform: 'scale(.96)' },
            { opacity: 1, transform: 'scale(1)' },
        ], { duration: compact ? 320 : 520, delay: compact ? 260 : 420 });
        runtime.animateGroup(highlightMarkers, [
            { opacity: .38, transform: 'scale(.44)' },
            { opacity: 1, transform: 'scale(1)' },
        ], { duration: compact ? 180 : 240, delay: compact ? 360 : 540, stagger: compact ? 35 : 55, easing: easing.emphasized });
        if (!compact) {
            runtime.animateGroup(receipts, [
                { opacity: .22, transform: 'translateY(38px) scale(.94)' },
                { opacity: 1, transform: 'translateY(0) scale(1)' },
            ], { duration: 360, delay: 760, stagger: 70, easing: easing.emphasized });
        }

        runtime.after(compact ? 620 : 1120, () => setPhase(compact ? 'a3-update' : 'a3'));
        runtime.animate(remainder, [
            { opacity: .35, transform: 'translateY(18px)' },
            { opacity: 1, transform: 'translateY(0)' },
        ], { duration: compact ? 220 : 300, delay: compact ? 620 : 1120 });
        runtime.animateGroup(receiptTotals, [
            { opacity: .4, transform: 'translateX(-16px)' },
            { opacity: 1, transform: 'translateX(0)' },
        ], { duration: 280, delay: compact ? 700 : 1220, stagger: compact ? 35 : 55 });
        runtime.animate(story.querySelector('.story-highlighted'), [
            { opacity: 1, transform: 'scale(1)' },
            { opacity: .62, transform: 'scale(.965)' },
            { opacity: .82, transform: 'scale(.985)' },
        ], { duration: 640, delay: compact ? 650 : 1180, easing: easing.standard });
        runtime.animate(total, [
            { opacity: .35, transform: 'translateY(38px) scale(.82)' },
            { opacity: 1, transform: 'translateY(0) scale(1)' },
        ], { duration: compact ? 360 : 480, delay: compact ? 860 : 1480, easing: easing.emphasized });

        runtime.after(compact ? 1100 : 1880, () => setPhase(compact ? 'a4-update' : 'a4'));
        runtime.animate(insightTitle, [
            { opacity: .28, transform: 'translateY(44px) scale(.95)' },
            { opacity: 1, transform: 'translateY(0) scale(1)' },
        ], { duration: compact ? 340 : 440, delay: compact ? 1100 : 1880, easing: easing.emphasized });
        runtime.animate(metric, [
            { opacity: .34, transform: 'translateY(24px)' },
            { opacity: 1, transform: 'translateY(0)' },
        ], { duration: compact ? 280 : 340, delay: compact ? 1380 : 2220 });
        runtime.animateGroup(evidence, [
            { opacity: .3, transform: 'translateY(28px)' },
            { opacity: 1, transform: 'translateY(0)' },
        ], { duration: compact ? 260 : 320, delay: compact ? 1600 : 2440, stagger: compact ? 60 : 80 });

        runtime.after(compact ? 2080 : 2880, () => setPhase(compact ? 'a5-update' : 'a5'));
        runtime.animateGroup(links, [
            { opacity: .42, transform: 'translateY(18px)' },
            { opacity: 1, transform: 'translateY(0)' },
        ], { duration: compact ? 240 : 300, delay: compact ? 2080 : 2880, stagger: 80 });
        runtime.after(fullDuration, () => runtime.completeSequence());

        if (options.armHandoff !== false) runtime.armHandoff();
    }

    // Deprecated compatibility implementation. Production always instantiates CinematicStoryController.
    class ProductMotionController {
        constructor(root) {
            this.root = root;
            this.runtime = new MotionRuntime(root);
        }

        start(mode) {
            this.runtime.cancel();
            document.documentElement.removeAttribute('data-story-cinematic-active');
            this.root.removeAttribute('data-cinematic-phase');
            if (mode === 'repeat' || reducedMotion.matches || !supportsMotion) {
                document.documentElement.dataset.storyMotionProfile = `${presentation}-static`;
                setPhase('static', mode === 'repeat' ? 1 : 0);
                return;
            }
            if (mode === 'replay') prepareReplay();
            playProductProfile(this.runtime, mode);
        }

        cancel() {
            this.runtime.cancel();
        }
    }

    class CinematicStoryController {
        constructor(root) {
            this.root = root;
            this.runtime = new MotionRuntime(root);
            this.narrative = root.querySelector('[data-story-narrative]');
            this.monthAct = root.querySelector('[data-story-act="month"]');
            this.insightAct = root.querySelector('[data-story-act="insight"]');
            this.workspace = root.querySelector('[data-story-act="workspace"]');
            this.opening = root.querySelector('.story-opening-copy');
            this.monthTitle = root.querySelector('#story-month-title');
            this.period = root.querySelector('.story-period');
            this.totalBlock = root.querySelector('[data-story-total-source]');
            this.totalLabel = this.totalBlock?.querySelector('span');
            this.total = this.totalBlock?.querySelector('strong');
            this.receipts = Array.from(root.querySelectorAll('[data-story-receipt]')).slice(0, 6);
            this.remainder = root.querySelector('[data-story-remainder]');
            this.insightTitle = root.querySelector('#story-insight-title');
            this.metric = root.querySelector('.story-metric');
            this.evidenceBlock = root.querySelector('.story-evidence');
            this.evidence = Array.from(root.querySelectorAll('.story-evidence li'));
            this.destinationLink = root.querySelector('.story-destination-link');
            this.skipButton = root.querySelector('[data-story-skip]');
            this.generation = 0;
            this.base = null;
            this.skipButton?.addEventListener('click', () => this.skip());
        }

        start(mode) {
            this.cancel();
            document.documentElement.dataset.storyCinematicActive = 'true';
            document.documentElement.dataset.storyMotionReady = 'true';
            this.root.dataset.cinematicPhase = 'preparing';

            if (mode === 'repeat' || reducedMotion.matches || !supportsMotion || !this.narrative || !this.receipts.length) {
                document.documentElement.dataset.storyMotionProfile = 'cinematic-static';
                this.settleSummary('static');
                setPhase('static', mode === 'repeat' ? 1 : 0);
                return;
            }
            const compact = mode === 'update';
            document.documentElement.dataset.storyMotionProfile = compact ? 'cinematic-update' : 'cinematic-autoplay';
            if (mode === 'replay') prepareReplay();
            this.play(compact, this.generation);
        }

        async frame() {
            await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }

        isCurrent(generation) {
            return generation === this.generation;
        }

        setState(phase, progress) {
            this.root.dataset.cinematicPhase = phase;
            setPhase(phase, progress);
        }

        async motion(element, keyframes, options, generation) {
            if (!element || !this.isCurrent(generation)) return false;
            const animation = this.runtime.animate(element, keyframes, { fill: 'both', ...options });
            if (!animation) return false;
            try {
                await animation.finished;
                if (!this.isCurrent(generation)) return false;
                animation.commitStyles?.();
                animation.cancel();
                return true;
            } catch (_) {
                return false;
            }
        }

        async hold(duration, generation) {
            await this.motion(this.narrative, [{ opacity: 1 }, { opacity: 1 }], {
                duration,
                easing: 'linear',
            }, generation);
        }

        measureBase() {
            const stage = this.narrative.getBoundingClientRect();
            const rect = (element) => {
                const value = element?.getBoundingClientRect();
                return value ? { x: value.left + value.width / 2, y: value.top + value.height / 2 } : null;
            };
            this.base = {
                stage,
                opening: rect(this.opening),
                total: rect(this.totalBlock),
                receipts: this.receipts.map(rect),
            };
        }

        transformTo(base, x, y, scale = 1, rotate = 0, prefix = '') {
            return `${prefix} translate3d(${(x - base.x).toFixed(2)}px, ${(y - base.y).toFixed(2)}px, 0) scale(${scale}) rotate(${rotate}deg)`.trim();
        }

        sceneTargets(sceneTwo = false) {
            const stage = this.base.stage;
            const mobile = window.innerWidth <= 767;
            const center = sceneTwo
                ? {
                    x: mobile ? stage.left + stage.width * .5 : stage.left + stage.width * .21,
                    y: stage.top + stage.height * (mobile ? .23 : .49),
                }
                : { x: stage.left + stage.width * .5, y: stage.top + stage.height * .55 };
            const offsets = mobile
                ? [[-8, -6], [10, 3], [-15, 8], [16, 12], [-20, 15], [21, 18]]
                : [[-20, -8], [18, 2], [-32, 11], [29, 16], [-41, 22], [40, 28]];
            return { center, offsets };
        }

        receiptFrames(sceneTwo = false) {
            const { center, offsets } = this.sceneTargets(sceneTwo);
            return this.receipts.map((receipt, index) => {
                const base = this.base.receipts[index];
                const [x, y] = offsets[index] || [0, 0];
                const scale = index === 0 ? (sceneTwo ? .78 : .86) : (sceneTwo ? .69 : .76);
                const rotate = [-2.4, 1.8, -1.2, 2.7, -3.1, 3.4][index] || 0;
                return {
                    element: receipt,
                    transform: this.transformTo(base, center.x + x, center.y + y, scale, rotate),
                    opacity: index === 0 ? .72 : Math.max(.18, .38 - index * .035),
                };
            });
        }

        async play(compact, generation) {
            await this.frame();
            if (!this.isCurrent(generation)) return;
            this.measureBase();
            this.skipButton?.removeAttribute('hidden');
            if (this.insightAct) this.insightAct.inert = true;

            this.setState(compact ? 'update-month' : 'month', 0);
            await this.motion(this.monthTitle, [
                { opacity: 0, transform: 'translateY(24px) scale(.94)' },
                { opacity: 1, transform: 'translateY(0) scale(1)' },
            ], { duration: compact ? 380 : 560, easing: easing.emphasized }, generation);
            if (!this.isCurrent(generation)) return;

            this.setState('receipts', .18);
            const entryOffsets = [[-190, -80], [70, -150], [190, -60], [-170, 120], [40, 165], [180, 105]];
            const visibleReceipts = compact ? this.receipts.slice(0, 3) : this.receipts;
            await Promise.all(visibleReceipts.map((receipt, index) => this.motion(receipt, [
                { opacity: 0, transform: `translate3d(${entryOffsets[index][0]}px, ${entryOffsets[index][1]}px, 0) scale(.94)` },
                { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1)' },
            ], {
                duration: compact ? 420 : 560,
                delay: index * (compact ? 90 : 150),
                easing: easing.emphasized,
            }, generation)));
            if (!this.isCurrent(generation)) return;

            this.setState('assembly', .42);
            const stack = this.receiptFrames(false);
            await Promise.all(stack.map(({ element, transform, opacity }, index) => this.motion(element, [
                { opacity: index < visibleReceipts.length ? 1 : 0, transform: getComputedStyle(element).transform },
                { opacity, transform },
            ], { duration: compact ? 620 : 920, easing: easing.emphasized }, generation)));
            if (!this.isCurrent(generation)) return;

            this.setState('total', .62);
            const sceneOne = this.sceneTargets(false).center;
            const monthTarget = { x: sceneOne.x, y: sceneOne.y - (window.innerWidth <= 767 ? 145 : 154) };
            await Promise.all([
                this.motion(this.opening, [
                    { opacity: 1, transform: getComputedStyle(this.opening).transform },
                    { opacity: 1, transform: this.transformTo(this.base.opening, monthTarget.x, monthTarget.y, window.innerWidth <= 767 ? .54 : .62, 0, 'translateX(-50%)') },
                ], { duration: compact ? 460 : 650, easing: easing.emphasized }, generation),
                this.motion(this.totalLabel, [
                    { opacity: 0, transform: 'translateY(12px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: compact ? 260 : 380, delay: compact ? 120 : 180 }, generation),
                this.motion(this.total, [
                    { opacity: 0, transform: 'translateY(28px) scale(.78)' },
                    { opacity: 1, transform: 'translateY(0) scale(1)' },
                ], { duration: compact ? 460 : 650, delay: compact ? 90 : 140, easing: easing.emphasized }, generation),
            ]);
            if (!this.isCurrent(generation)) return;
            await this.hold(compact ? 260 : 520, generation);
            if (!this.isCurrent(generation)) return;

            this.setState('explanation', .76);
            if (this.insightAct) this.insightAct.inert = false;
            const sceneTwo = this.sceneTargets(true).center;
            const monthTwo = {
                x: sceneTwo.x,
                y: sceneTwo.y - (window.innerWidth <= 767 ? 100 : 142),
            };
            await Promise.all([
                this.motion(this.totalBlock, [
                    { transform: 'translate(-50%, -50%) translate3d(0, 0, 0)' },
                    { transform: this.transformTo(this.base.total, sceneTwo.x, sceneTwo.y, window.innerWidth <= 767 ? .82 : .74, 0, 'translate(-50%, -50%)') },
                ], { duration: compact ? 620 : 860, easing: easing.emphasized }, generation),
                this.motion(this.opening, [
                    { transform: getComputedStyle(this.opening).transform },
                    { transform: this.transformTo(this.base.opening, monthTwo.x, monthTwo.y, window.innerWidth <= 767 ? .44 : .49, 0, 'translateX(-50%)') },
                ], { duration: compact ? 620 : 860, easing: easing.emphasized }, generation),
                this.motion(this.insightAct, [
                    { opacity: 0, transform: 'translate3d(42px, 0, 0)' },
                    { opacity: 1, transform: 'translate3d(0, 0, 0)' },
                ], { duration: compact ? 520 : 760, delay: compact ? 80 : 140, easing: easing.emphasized }, generation),
                ...this.receipts.map((element) => this.motion(element, [
                    { opacity: Number.parseFloat(getComputedStyle(element).opacity), transform: getComputedStyle(element).transform },
                    { opacity: 0, transform: `${getComputedStyle(element).transform} scale(.94)` },
                ], { duration: compact ? 620 : 860, easing: easing.emphasized }, generation)),
            ]);
            if (!this.isCurrent(generation)) return;

            this.setState('evidence', .88);
            await Promise.all([
                this.motion(this.insightTitle, [
                    { opacity: 0, transform: 'translateY(28px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: compact ? 420 : 560, easing: easing.emphasized }, generation),
                this.motion(this.metric, [
                    { opacity: 0, transform: 'translateY(20px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: compact ? 360 : 480, delay: compact ? 120 : 220 }, generation),
                this.motion(this.evidenceBlock, [
                    { opacity: 0, transform: 'translateY(20px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: compact ? 360 : 480, delay: compact ? 180 : 300 }, generation),
                ...this.evidence.map((item, index) => this.motion(item, [
                    { opacity: 0, transform: 'translateY(18px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: compact ? 300 : 420, delay: (compact ? 180 : 300) + index * 90 }, generation)),
                this.motion(this.destinationLink, [
                    { opacity: 0, transform: 'translateY(14px)' },
                    { opacity: 1, transform: 'translateY(0)' },
                ], { duration: compact ? 300 : 420, delay: compact ? 260 : 440 }, generation),
            ]);
            if (!this.isCurrent(generation)) return;
            await this.hold(compact ? 420 : 720, generation);
            if (!this.isCurrent(generation)) return;

            this.skipButton?.setAttribute('hidden', '');
            this.settleSummary('complete');
            this.runtime.completeSequence();
        }

        settleSummary(phase = 'static') {
            this.skipButton?.setAttribute('hidden', '');
            if (this.insightAct) this.insightAct.inert = false;
            this.root.dataset.cinematicPhase = phase;
            [this.narrative, this.opening, this.monthTitle, this.totalBlock, this.totalLabel, this.total,
                ...this.receipts, this.insightAct, this.insightTitle, this.metric, this.evidenceBlock,
                this.destinationLink, ...this.evidence]
                .filter(Boolean)
                .forEach((element) => {
                    element.style.removeProperty('opacity');
                    element.style.removeProperty('transform');
                    element.style.removeProperty('filter');
                });
        }

        async skip() {
            if (reducedMotion.matches) return;
            this.generation += 1;
            this.runtime.cancel();
            const generation = this.generation;
            await this.frame();
            if (!this.isCurrent(generation)) return;
            this.settleSummary('complete');
            this.runtime.completeSequence();
        }

        cancel() {
            this.generation += 1;
            this.runtime.cancel();
            this.base = null;
            this.root.removeAttribute('data-cinematic-phase');
            this.insightAct?.removeAttribute('inert');
            this.skipButton?.setAttribute('hidden', '');
            [this.narrative, this.opening, this.monthTitle, this.totalBlock, this.totalLabel, this.total,
                this.remainder, this.insightAct, this.insightTitle, this.metric, this.evidenceBlock, this.destinationLink,
                ...this.receipts, ...this.evidence]
                .filter(Boolean)
                .forEach((element) => {
                    element.style.removeProperty('opacity');
                    element.style.removeProperty('transform');
                    element.style.removeProperty('filter');
                });
        }
    }

    const controller = new CinematicStoryController(story);

    function start(mode) {
        const nextMode = VISIT_MODES.has(mode) ? mode : 'new';
        setOutput(debug.reduced, reducedMotion.matches);
        controller.start(nextMode);
    }

    document.addEventListener('story:modechange', (event) => start(event.detail?.mode));
    reducedMotion.addEventListener?.('change', () => start(story.dataset.storyMode));
    start(story.dataset.storyMode);
})();

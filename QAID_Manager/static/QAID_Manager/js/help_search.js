(function () {
    const MIN_QUERY = 2;
    const MAX_RESULTS = 20;

    let blocks = [];
    let activeResultIndex = -1;
    let inputEl;
    let resultsEl;
    let statusEl;
    let clearBtn;

    function normalize(text) {
        return (text || '').toLowerCase().replace(/\s+/g, ' ').trim();
    }

    function tokenize(query) {
        return normalize(query).split(' ').filter(Boolean);
    }

    function getBlockText(block) {
        return block.contentElements.map((el) => el.textContent).join(' ');
    }

    function matchesQuery(block, tokens) {
        if (!tokens.length) {
            return true;
        }
        const hay = normalize(getBlockText(block));
        return tokens.every((token) => hay.includes(token));
    }

    function scoreBlock(block, tokens, query) {
        const title = normalize(block.title);
        const hay = normalize(getBlockText(block));
        const q = normalize(query);
        let score = 0;

        if (q && title.includes(q)) {
            score += 60;
        }
        tokens.forEach((token) => {
            if (title.includes(token)) {
                score += 12;
            }
            if (hay.includes(token)) {
                score += 2;
            }
        });
        return score;
    }

    function buildBlocks() {
        const container = document.getElementById('help-guide');
        if (!container) {
            return [];
        }

        const out = [];
        container.querySelectorAll('section[id]').forEach((section) => {
            const sectionTitle = (section.querySelector('h2')?.textContent || '')
                .replace(/\s+/g, ' ')
                .trim();
            const sectionId = section.id;
            const indexedDetails = new Set();

            for (const child of section.children) {
                if (child.tagName === 'H2') {
                    continue;
                }
                if (child.tagName === 'H3') {
                    break;
                }
                if (child.matches('details.help-details')) {
                    const summary = child.querySelector('summary');
                    out.push({
                        element: child,
                        contentElements: [child],
                        title: summary ? summary.textContent.trim() : sectionTitle,
                        sectionTitle,
                        sectionId,
                        kind: 'details',
                    });
                    indexedDetails.add(child);
                }
            }

            const overviewEls = [];
            for (const child of section.children) {
                if (child.tagName === 'H3') {
                    break;
                }
                if (child.tagName === 'H2' || child.matches('details.help-details')) {
                    continue;
                }
                if (['P', 'OL', 'UL', 'DIV'].includes(child.tagName)) {
                    overviewEls.push(child);
                }
            }
            if (overviewEls.length) {
                out.push({
                    element: overviewEls[0],
                    contentElements: overviewEls,
                    title: sectionTitle,
                    sectionTitle,
                    sectionId,
                    kind: 'section',
                });
            }

            section.querySelectorAll(':scope > h3').forEach((h3) => {
                const contentEls = [h3];
                let el = h3.nextElementSibling;
                while (el && el.tagName !== 'H3') {
                    contentEls.push(el);
                    el = el.nextElementSibling;
                }
                out.push({
                    element: h3,
                    contentElements: contentEls,
                    title: h3.textContent.replace(/\s+/g, ' ').trim(),
                    sectionTitle,
                    sectionId,
                    kind: 'subsection',
                });
            });

            section.querySelectorAll('details.help-details').forEach((details) => {
                if (indexedDetails.has(details)) {
                    return;
                }
                const summary = details.querySelector('summary');
                out.push({
                    element: details,
                    contentElements: [details],
                    title: summary ? summary.textContent.trim() : 'Details',
                    sectionTitle,
                    sectionId,
                    kind: 'details',
                });
            });
        });

        return out;
    }

    function snippet(text, tokens, maxLen) {
        const limit = maxLen || 130;
        const raw = (text || '').replace(/\s+/g, ' ').trim();
        if (!raw) {
            return '';
        }
        const n = normalize(raw);
        let idx = -1;
        tokens.forEach((token) => {
            const i = n.indexOf(token);
            if (i >= 0 && (idx < 0 || i < idx)) {
                idx = i;
            }
        });
        if (idx < 0) {
            return raw.length > limit ? `${raw.slice(0, limit)}…` : raw;
        }
        const start = Math.max(0, idx - 35);
        const bit = raw.slice(start, start + limit);
        const prefix = start > 0 ? '…' : '';
        const suffix = start + limit < raw.length ? '…' : '';
        return `${prefix}${bit}${suffix}`;
    }

    function clearHighlights() {
        document.querySelectorAll('.help-search-highlight').forEach((el) => {
            el.classList.remove('help-search-highlight');
        });
    }

    function clearFilter() {
        const container = document.getElementById('help-guide');
        if (!container) {
            return;
        }
        container.querySelectorAll('section[id]').forEach((section) => {
            section.classList.remove('help-search-section-hidden');
        });
        blocks.forEach((block) => {
            block.contentElements.forEach((el) => {
                el.classList.remove('help-search-hidden');
            });
        });
    }

    function applyFilter(tokens) {
        clearFilter();
        if (!tokens.length) {
            return;
        }

        const matching = new Set(blocks.filter((block) => matchesQuery(block, tokens)));

        blocks.forEach((block) => {
            const isMatch = matching.has(block);
            block.contentElements.forEach((el) => {
                el.classList.toggle('help-search-hidden', !isMatch);
            });
            if (isMatch && block.element.tagName === 'DETAILS') {
                block.element.open = true;
            }
        });

        const container = document.getElementById('help-guide');
        container.querySelectorAll('section[id]').forEach((section) => {
            const sectionHasMatch = blocks.some(
                (block) => block.sectionId === section.id && matching.has(block),
            );
            section.classList.toggle('help-search-section-hidden', !sectionHasMatch);
        });
    }

    function navigateToBlock(block) {
        if (!block) {
            return;
        }
        if (block.element.tagName === 'DETAILS') {
            block.element.open = true;
        }

        clearHighlights();
        const target = block.element;
        target.classList.add('help-search-highlight');
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        window.setTimeout(() => {
            target.classList.remove('help-search-highlight');
        }, 2400);
    }

    function renderResults(results, tokens) {
        resultsEl.innerHTML = '';
        activeResultIndex = -1;

        if (!tokens.length) {
            statusEl.textContent = 'Type at least 2 characters to search topics and functions.';
            resultsEl.hidden = true;
            return;
        }

        if (!results.length) {
            statusEl.textContent = `No matches for "${inputEl.value.trim()}". Try different keywords (e.g. wizard, dose, schedule, film).`;
            resultsEl.hidden = true;
            return;
        }

        const shown = results.slice(0, MAX_RESULTS);
        statusEl.textContent = `${results.length} match${results.length === 1 ? '' : 'es'} — click a result or press Enter to jump there.`;

        shown.forEach((block, index) => {
            const li = document.createElement('li');
            li.className = 'help-search-result';
            li.setAttribute('role', 'option');
            li.dataset.index = String(index);

            const title = document.createElement('div');
            title.className = 'help-search-result-title';
            title.textContent = block.title;

            const meta = document.createElement('div');
            meta.className = 'help-search-result-meta';
            meta.textContent = block.sectionTitle;

            const excerpt = document.createElement('div');
            excerpt.className = 'help-search-result-excerpt';
            excerpt.textContent = snippet(getBlockText(block), tokens);

            li.appendChild(title);
            li.appendChild(meta);
            li.appendChild(excerpt);
            li.addEventListener('click', () => {
                navigateToBlock(block);
            });
            resultsEl.appendChild(li);
        });

        if (results.length > MAX_RESULTS) {
            const more = document.createElement('li');
            more.className = 'help-search-result-more';
            more.textContent = `+ ${results.length - MAX_RESULTS} more — refine your search to narrow results.`;
            resultsEl.appendChild(more);
        }

        resultsEl.hidden = false;
    }

    function runSearch() {
        const query = inputEl.value.trim();
        const tokens = tokenize(query);

        clearBtn.hidden = !query;
        applyFilter(tokens);

        if (tokens.length < MIN_QUERY) {
            renderResults([], []);
            return;
        }

        const ranked = blocks
            .filter((block) => matchesQuery(block, tokens))
            .map((block) => ({
                block,
                score: scoreBlock(block, tokens, query),
            }))
            .sort((a, b) => b.score - a.score)
            .map((entry) => entry.block);

        renderResults(ranked, tokens);
    }

    function getVisibleResults() {
        return Array.from(resultsEl.querySelectorAll('.help-search-result'));
    }

    function setActiveResult(index) {
        const items = getVisibleResults();
        items.forEach((item) => item.classList.remove('is-active'));
        if (index < 0 || index >= items.length) {
            activeResultIndex = -1;
            return;
        }
        activeResultIndex = index;
        items[index].classList.add('is-active');
        items[index].scrollIntoView({ block: 'nearest' });
    }

    function handleKeydown(event) {
        const items = getVisibleResults();
        if (!items.length) {
            return;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            const next = activeResultIndex < items.length - 1 ? activeResultIndex + 1 : 0;
            setActiveResult(next);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            const prev = activeResultIndex > 0 ? activeResultIndex - 1 : items.length - 1;
            setActiveResult(prev);
        } else if (event.key === 'Enter') {
            event.preventDefault();
            const query = inputEl.value.trim();
            const tokens = tokenize(query);
            if (tokens.length < MIN_QUERY) {
                return;
            }
            const ranked = blocks
                .filter((block) => matchesQuery(block, tokens))
                .map((block) => ({
                    block,
                    score: scoreBlock(block, tokens, query),
                }))
                .sort((a, b) => b.score - a.score)
                .map((entry) => entry.block);
            const index = activeResultIndex >= 0 ? activeResultIndex : 0;
            navigateToBlock(ranked[index]);
        } else if (event.key === 'Escape') {
            inputEl.value = '';
            clearBtn.hidden = true;
            clearFilter();
            clearHighlights();
            renderResults([], []);
            inputEl.blur();
        }
    }

    function init() {
        inputEl = document.getElementById('helpSearchInput');
        resultsEl = document.getElementById('helpSearchResults');
        statusEl = document.getElementById('helpSearchStatus');
        clearBtn = document.getElementById('helpSearchClear');

        if (!inputEl || !resultsEl || !statusEl) {
            return;
        }

        blocks = buildBlocks();
        renderResults([], []);

        inputEl.addEventListener('input', runSearch);
        inputEl.addEventListener('keydown', handleKeydown);
        clearBtn.addEventListener('click', () => {
            inputEl.value = '';
            clearBtn.hidden = true;
            clearFilter();
            clearHighlights();
            renderResults([], []);
            inputEl.focus();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

/* global Chart, MiniTrend */
(function () {
    'use strict';

    var mainChart = null;
    var currentSingleTestData = null;
    var singleTestLineRefreshTimer = null;
    var overviewCharts = [];
    var apiUrls = {
        overview: '/api/statistics/overview/',
        single_test: '/api/statistics/trend/',
        linac_all_tests: '/api/statistics/linac-all/',
        category_trends: '/api/statistics/category/',
        beam_energy: '/api/statistics/beam-energy/',
        point: '/api/statistics/point/',
        export: '/statistics/export/csv/'
    };

    var PALETTE = {
        green: '#16a34a',
        greenBg: '#dcfce7',
        amber: '#d97706',
        amberBg: '#fef3c7',
        red: '#dc2626',
        redBg: '#fee2e2',
        gray: '#6b7280',
        grayBg: '#f3f4f6',
        blue: '#2563eb',
        navy: '#1f3a5f',
        series: ['#2563eb', '#16a34a', '#7c3aed', '#0891b2', '#d97706', '#dc2626']
    };

    function $(id) { return document.getElementById(id); }

    function getViewMode() {
        return ($('view_mode') && $('view_mode').value) || 'overview';
    }

    function getSelectedLinacIds() {
        var sel = $('linac_ids');
        if (!sel) return [];
        return Array.from(sel.selectedOptions)
            .map(function (o) { return o.value; })
            .filter(function (v) { return v; });
    }

    function buildParams() {
        var params = new URLSearchParams();
        params.set('view_mode', getViewMode());
        params.set('date_preset', $('date_preset').value);
        if ($('date_preset').value === 'custom') {
            params.set('date_from', $('date_from').value);
            params.set('date_to', $('date_to').value);
        }
        getSelectedLinacIds().forEach(function (id) {
            params.append('linac_ids', id);
        });
        params.set('test_category', $('test_category').value || 'all');
        if ($('qa_test_id') && $('qa_test_id').value) {
            params.set('qa_test_id', $('qa_test_id').value);
        }
        if ($('energy') && $('energy').value) {
            params.set('energy', $('energy').value);
        }
        if ($('beam_test_group') && $('beam_test_group').value) {
            params.set('beam_test_group', $('beam_test_group').value);
        }
        if ($('result_status') && $('result_status').value) {
            params.set('result_status', $('result_status').value);
        }
        if ($('include_inactive_linacs') && $('include_inactive_linacs').checked) {
            params.set('include_inactive_linacs', '1');
        }
        if ($('include_drafts') && $('include_drafts').checked) {
            params.set('include_drafts', '1');
        }
        if ($('show_only_with_data') && $('show_only_with_data').checked) {
            params.set('show_only_with_data', '1');
        }
        return params;
    }

    function showStatus(msg, type) {
        var el = $('stats_status');
        if (!el) return;
        if (!msg) {
            el.style.display = 'none';
            el.textContent = '';
            return;
        }
        el.className = 'stats-alert stats-' + (type || 'loading');
        el.textContent = msg;
        el.style.display = 'block';
    }

    function actionThresholdFromWarning(warningValue) {
        if (isNaN(warningValue)) return NaN;
        return warningValue + 0.5;
    }

    function scheduleSingleTestLineRefresh() {
        if (!currentSingleTestData || getViewMode() !== 'single_test') return;
        if (singleTestLineRefreshTimer) {
            window.clearTimeout(singleTestLineRefreshTimer);
        }
        singleTestLineRefreshTimer = window.setTimeout(function () {
            renderSingleTestTrend(currentSingleTestData);
        }, 120);
    }

    function fetchApi(mode) {
        var url = apiUrls[mode] + '?' + buildParams().toString();
        return fetch(url, { credentials: 'same-origin' }).then(function (r) {
            return r.json().then(function (j) {
                if (!r.ok || !j.success) {
                    throw new Error((j && j.error) || 'Request failed');
                }
                return j.data;
            });
        });
    }

    function trendBadgeClass(label) {
        if (label === 'Stable') return 'badge-stable';
        if (label === 'Watch') return 'badge-watch';
        if (label === 'Action') return 'badge-action';
        return 'badge-insufficient';
    }

    function classificationBadge(cls) {
        var c = (cls || '').toLowerCase();
        var label = 'Missing';
        var badgeCls = 'status-badge-missing';
        if (c === 'normal') {
            label = 'Normal';
            badgeCls = 'status-badge-normal';
        } else if (c === 'warning') {
            label = 'Warning';
            badgeCls = 'status-badge-warning';
        } else if (c === 'failed') {
            label = 'Failed';
            badgeCls = 'status-badge-failed';
        }
        return '<span class="status-badge ' + badgeCls + '">' + label + '</span>';
    }

    function matrixStatusPill(status, classification) {
        var map = {
            green: { cls: 'status-pill-normal', icon: '✓', label: 'Normal' },
            yellow: { cls: 'status-pill-warning', icon: '!', label: 'Watch' },
            red: { cls: 'status-pill-failed', icon: '✕', label: 'Fail' },
            gray: { cls: 'status-pill-missing', icon: '—', label: 'No data' }
        };
        var m = map[status] || map.gray;
        var title = (classification || m.label) + ' — click for trend';
        return '<span class="status-pill matrix-cell-pill matrix-cell-pill-compact ' + m.cls +
            '" title="' + escapeHtml(title) + '"><span class="status-pill-icon">' + m.icon +
            '</span><span class="status-pill-text">' + m.label + '</span></span>';
    }

    function borderClass(classification) {
        if (classification === 'normal') return 'border-normal';
        if (classification === 'warning') return 'border-warning';
        if (classification === 'failed') return 'border-failed';
        return 'border-missing';
    }

    function updateModeUI() {
        var mode = getViewMode();
        document.querySelectorAll('.mode-panel').forEach(function (p) {
            p.classList.toggle('active', p.getAttribute('data-mode') === mode);
        });
        document.querySelectorAll('.filter-mode-specific').forEach(function (el) {
            var modes = (el.getAttribute('data-modes') || '').split(',');
            el.classList.toggle('visible', modes.indexOf(mode) >= 0);
        });
        var testSel = $('qa_test_id');
        var isBeam = false;
        if (testSel && testSel.selectedOptions[0]) {
            isBeam = testSel.selectedOptions[0].getAttribute('data-beam') === '1';
        }
        var energyWrap = $('energy_filter_wrap');
        if (energyWrap) {
            var showEnergy = (mode === 'single_test' && isBeam) ||
                mode === 'beam_energy' ||
                (mode === 'category_trends' && $('test_category').value === 'beam');
            energyWrap.classList.toggle('visible', showEnergy);
        }
        var customDates = $('custom_dates_wrap');
        if (customDates) {
            customDates.classList.toggle('visible', $('date_preset').value === 'custom');
        }
    }

    function destroyOverviewCharts() {
        overviewCharts.forEach(function (c) {
            try { c.destroy(); } catch (e) { /* ignore */ }
        });
        overviewCharts = [];
    }

    function renderManagementDashboard(charts, reviewList) {
        destroyOverviewCharts();
        var mgmt = (charts && charts.management) || {};
        var summary = mgmt.summary || {};
        var health = mgmt.department_health || {};

        renderMgmtAnswers(summary);
        renderPendingAlert(mgmt.pending_review || {}, reviewList);
        renderHealthGauge(health);
        renderLinacCompletionCards(mgmt.linac_completion || []);
        renderMissingHeatmap(mgmt.missing_qa_heatmap || {});
        renderTopIssues(mgmt.top_issues || {});

        var reviewSummary = $('overview_review_summary');
        if (reviewSummary) {
            var cnt = (mgmt.pending_review && mgmt.pending_review.count) || reviewList.length || 0;
            reviewSummary.textContent = cnt
                ? cnt + ' item' + (cnt === 1 ? '' : 's') + ' — expand for table'
                : 'No items — expand for table';
        }

        if (typeof Chart === 'undefined') return;

        var status = health.status_counts || charts.status_counts || {};
        var healthEl = $('overview_health_chart');
        if (healthEl) {
            overviewCharts.push(new Chart(healthEl.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: ['Normal', 'Warning', 'Failed', 'No data'],
                    datasets: [{
                        data: [
                            status.green || 0,
                            status.yellow || 0,
                            status.red || 0,
                            status.gray || 0
                        ],
                        backgroundColor: [PALETTE.green, PALETTE.amber, PALETTE.red, PALETTE.gray],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '62%',
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } }
                    }
                }
            }));
        }

        var linacData = mgmt.linac_attention || charts.linac_attention || [];
        var issuesEl = $('overview_linac_issues_chart');
        if (issuesEl && linacData.length) {
            overviewCharts.push(new Chart(issuesEl.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: linacData.map(function (l) { return l.linac_name; }),
                    datasets: [
                        {
                            label: 'Warnings',
                            data: linacData.map(function (l) { return l.warnings; }),
                            backgroundColor: PALETTE.amber
                        },
                        {
                            label: 'Failures',
                            data: linacData.map(function (l) { return l.failures; }),
                            backgroundColor: PALETTE.red
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { stacked: true, grid: { display: false } },
                        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }
                    },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } }
                }
            }));
        }

        var relEl = $('overview_linac_reliability_chart');
        if (relEl && linacData.length) {
            var ranked = linacData.slice().sort(function (a, b) {
                return a.reliability_score - b.reliability_score;
            });
            overviewCharts.push(new Chart(relEl.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: ranked.map(function (l) { return l.linac_name; }),
                    datasets: [{
                        label: 'Reliability score',
                        data: ranked.map(function (l) { return l.reliability_score; }),
                        backgroundColor: ranked.map(function (l) {
                            if (l.reliability_score >= 85) return PALETTE.green;
                            if (l.reliability_score >= 60) return PALETTE.amber;
                            return PALETTE.red;
                        })
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    scales: {
                        x: { min: 0, max: 100, grid: { color: '#eef2f6' } },
                        y: { grid: { display: false } }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                afterLabel: function (ctx) {
                                    var row = ranked[ctx.dataIndex];
                                    return 'Warnings: ' + row.warnings + ', Failures: ' + row.failures +
                                        ', Missing months: ' + row.missing_months;
                                }
                            }
                        }
                    }
                }
            }));
        }

        var catData = charts.category_attention || [];
        var catEl = $('overview_category_chart');
        if (catEl && catData.length) {
            overviewCharts.push(new Chart(catEl.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: catData.map(function (c) { return c.label; }),
                    datasets: [
                        {
                            label: 'Warnings',
                            data: catData.map(function (c) { return c.warnings; }),
                            backgroundColor: PALETTE.amber
                        },
                        {
                            label: 'Failures',
                            data: catData.map(function (c) { return c.failures; }),
                            backgroundColor: PALETTE.red
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { stacked: true, grid: { display: false } },
                        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }
                    },
                    plugins: { legend: { position: 'bottom', labels: { boxWidth: 12 } } }
                }
            }));
        }
    }

    function renderMgmtAnswers(summary) {
        var el = $('overview_mgmt_answers');
        if (!el) return;

        var allComplete = summary.all_linacs_qa_complete;
        var missingList = (summary.linacs_missing_qa || []).map(function (l) {
            return l.linac_name;
        });
        var failList = (summary.linacs_with_failures || []).map(function (l) {
            return l.linac_name;
        });
        var topLinac = summary.top_attention_linac;

        var answers = [
            {
                q: 'QA completed for all LINACs?',
                a: allComplete ? 'Yes — all months covered' : 'No — gaps remain',
                tone: allComplete ? 'ok' : 'warn'
            },
            {
                q: 'LINACs missing QA',
                a: missingList.length ? missingList.join(', ') : 'None in period',
                tone: missingList.length ? 'warn' : 'ok'
            },
            {
                q: 'LINACs with failed results',
                a: failList.length ? failList.join(', ') : 'None in period',
                tone: failList.length ? 'bad' : 'ok'
            },
            {
                q: 'Results pending review',
                a: String(summary.pending_review_count || 0),
                tone: (summary.pending_review_count || 0) > 0 ? 'warn' : 'ok'
            },
            {
                q: 'Highest management attention',
                a: topLinac
                    ? topLinac.linac_name + ' (score ' + topLinac.reliability_score + ')'
                    : '—',
                tone: topLinac && topLinac.reliability_score < 70 ? 'bad' : 'ok'
            }
        ];

        el.innerHTML = answers.map(function (item) {
            return '<div class="overview-answer-card tone-' + item.tone + '">' +
                '<div class="overview-answer-q">' + escapeHtml(item.q) + '</div>' +
                '<div class="overview-answer-a">' + escapeHtml(item.a) + '</div></div>';
        }).join('');
    }

    function renderPendingAlert(pending, reviewList) {
        var el = $('overview_pending_alert');
        if (!el) return;
        var count = pending.count || 0;
        var preview = pending.preview || reviewList.slice(0, 5);
        var tone = count > 0 ? 'alert-active' : 'alert-clear';

        var html = '<div class="overview-alert-inner ' + tone + '">' +
            '<div class="overview-alert-count">' + count + '</div>' +
            '<div class="overview-alert-text">' +
            '<strong>Pending review</strong>' +
            '<span>Warning &amp; failed QA results</span></div></div>';

        if (preview.length) {
            html += '<ul class="overview-alert-list">';
            preview.forEach(function (r) {
                var cls = r.classification === 'failed' ? 'failed' : 'warning';
                html += '<li class="overview-alert-item clickable-review" data-test-id="' + r.test_id +
                    '" data-linac-id="' + r.linac_id + '" data-energy="' + escapeHtml(r.energy || '') + '">' +
                    '<span class="overview-alert-item-title">' + escapeHtml(r.test_name) + '</span>' +
                    '<span class="overview-alert-item-meta">' + escapeHtml(r.linac_name) + ' · ' + r.date +
                    ' · <span class="status-badge status-badge-' + cls + '">' +
                    (cls === 'failed' ? 'Failed' : 'Warning') + '</span></span></li>';
            });
            html += '</ul>';
        } else {
            html += '<p class="overview-alert-empty">No warning or failed results in this period.</p>';
        }
        el.innerHTML = html;

        el.querySelectorAll('.clickable-review').forEach(function (row) {
            row.addEventListener('click', function () {
                drillDownSingleTest(
                    row.getAttribute('data-test-id'),
                    [row.getAttribute('data-linac-id')],
                    row.getAttribute('data-energy') || null
                );
            });
        });
    }

    function renderHealthGauge(health) {
        var gauge = $('overview_health_gauge');
        var sub = $('overview_health_sub');
        if (!gauge) return;
        var label = health.health_label || '—';
        var score = health.health_score != null ? health.health_score : '—';
        var completion = health.overall_completion_pct != null ? health.overall_completion_pct : '—';
        var tone = label === 'Good' ? 'ok' : (label === 'Watch' ? 'warn' : 'bad');
        gauge.innerHTML = '<div class="overview-gauge-value tone-' + tone + '">' + score + '</div>' +
            '<div class="overview-gauge-label">' + escapeHtml(label) + ' · QA Index</div>' +
            '<div class="overview-gauge-sub">Monthly QA completion: ' + completion + '%</div>';
        if (sub) {
            sub.textContent = 'QA Index ' + score + ' · Monthly completion ' + completion + '%';
        }
    }

    function renderLinacCompletionCards(linacs) {
        var el = $('overview_linac_completion');
        if (!el) return;
        if (!linacs.length) {
            el.innerHTML = '<p class="stats-empty-inline">No LINACs in filter.</p>';
            return;
        }
        el.innerHTML = linacs.map(function (l) {
            var statusCls = 'completion-' + (l.status || 'at_risk');
            return '<div class="overview-completion-card ' + statusCls + '">' +
                '<div class="overview-completion-header">' +
                '<span class="overview-completion-name">' + escapeHtml(l.linac_name) + '</span>' +
                '<span class="overview-completion-pct">' + l.completion_pct + '%</span></div>' +
                '<div class="overview-completion-bar"><div class="overview-completion-fill" style="width:' +
                Math.min(100, l.completion_pct) + '%"></div></div>' +
                '<div class="overview-completion-meta">' + l.completed_months + ' / ' +
                l.total_months + ' months with QA</div></div>';
        }).join('');
    }

    function renderMissingHeatmap(heatmap) {
        var el = $('overview_missing_heatmap');
        if (!el) return;
        var months = heatmap.month_labels || [];
        var rows = heatmap.rows || [];
        if (!rows.length) {
            el.innerHTML = '<p class="stats-empty-inline">No LINAC data.</p>';
            return;
        }

        var colWidth = months.length > 12 ? '28px' : '36px';
        var html = '<div class="stats-heatmap" style="--heat-col:' + colWidth + '">';
        html += '<div class="stats-heatmap-row stats-heatmap-header">';
        html += '<span class="stats-heatmap-linac">LINAC</span>';
        months.forEach(function (m) {
            html += '<span class="stats-heatmap-month" title="' + escapeHtml(m) + '">' +
                escapeHtml(m.slice(5)) + '</span>';
        });
        html += '</div>';

        rows.forEach(function (row) {
            html += '<div class="stats-heatmap-row">';
            html += '<span class="stats-heatmap-linac">' + escapeHtml(row.linac_name) + '</span>';
            (row.months || []).forEach(function (cell) {
                var cls = cell.has_qa ? 'heat-ok' : 'heat-miss';
                var tip = row.linac_name + ' · ' + cell.label + ' — ' +
                    (cell.has_qa ? 'QA completed' : 'Missing QA');
                html += '<span class="stats-heatmap-cell ' + cls + '" title="' + escapeHtml(tip) + '"></span>';
            });
            html += '</div>';
        });
        html += '<div class="stats-heatmap-legend">' +
            '<span><i class="heat-ok"></i> QA completed</span>' +
            '<span><i class="heat-miss"></i> Missing QA</span></div>';
        html += '</div>';
        el.innerHTML = html;
    }

    function renderTopIssues(issues) {
        var el = $('overview_top_issues');
        if (!el) return;
        var blocks = [
            { key: 'failed', title: 'Failed results', empty: 'No failed results.', tone: 'bad' },
            { key: 'missing', title: 'Missing QA months', empty: 'All months have QA records.', tone: 'warn' },
            { key: 'repeated_warnings', title: 'Repeated warnings', empty: 'No repeated warning patterns.', tone: 'warn' }
        ];

        el.innerHTML = blocks.map(function (block) {
            var items = issues[block.key] || [];
            var body = '';
            if (!items.length) {
                body = '<p class="overview-issue-empty">' + block.empty + '</p>';
            } else {
                body = '<ul class="overview-issue-list">' + items.map(function (item) {
                    var clickable = item.test_id ? ' clickable-issue' : '';
                    var attrs = item.test_id
                        ? ' data-test-id="' + item.test_id + '" data-linac-id="' + item.linac_id +
                        '" data-energy="' + escapeHtml(item.energy || '') + '"'
                        : '';
                    var meta = item.linac_name || item.month || '';
                    if (item.count) meta += (meta ? ' · ' : '') + item.count + ' warnings';
                    if (item.date) meta += (meta ? ' · ' : '') + item.date;
                    if (item.value != null) meta += (meta ? ' · ' : '') + item.value + ' ' + (item.unit || '');
                    return '<li class="overview-issue-item' + clickable + '"' + attrs + '>' +
                        '<span class="overview-issue-title">' + escapeHtml(item.title) + '</span>' +
                        (meta ? '<span class="overview-issue-meta">' + escapeHtml(meta) + '</span>' : '') +
                        '</li>';
                }).join('') + '</ul>';
            }
            return '<div class="overview-issue-block tone-' + block.tone + '">' +
                '<h4>' + block.title + '</h4>' + body + '</div>';
        }).join('');

        el.querySelectorAll('.clickable-issue').forEach(function (row) {
            row.addEventListener('click', function () {
                drillDownSingleTest(
                    row.getAttribute('data-test-id'),
                    [row.getAttribute('data-linac-id')],
                    row.getAttribute('data-energy') || null
                );
            });
        });
    }

    function buildMiniTrendCardHtml(opts) {
        var cls = opts.borderClass || 'border-missing';
        var attrs = opts.dataAttrs || '';
        var title = escapeHtml(opts.title);
        var badge = opts.trendLabel
            ? '<span class="' + trendBadgeClass(opts.trendLabel) + '">' + escapeHtml(opts.trendLabel) + '</span>'
            : classificationBadge(opts.classification);

        var body = '';
        if (opts.hasData === false) {
            body = '<p class="mini-trend-meta">No data in selected period.</p>';
        } else {
            body = '<div class="mini-trend-latest">' + escapeHtml(String(opts.latestValue)) +
                (opts.unit ? ' <span class="unit">' + escapeHtml(opts.unit) + '</span>' : '') +
                '</div>';
            if (opts.warningCount != null || opts.failureCount != null) {
                body += '<div class="mini-trend-meta">Warnings: ' + (opts.warningCount || 0) +
                    ' &nbsp; Failures: ' + (opts.failureCount || 0) + '</div>';
            }
            if (opts.lastQa) {
                body += '<div class="mini-trend-meta">Last QA: ' + escapeHtml(opts.lastQa) + '</div>';
            }
            body += '<div class="mini-trend-spark-wrap"><canvas class="mini-trend-canvas" ' +
                (opts.canvasAttr || '') + '></canvas></div>' +
                '<div class="mini-trend-open"><span class="stats-btn stats-btn-sm stats-btn-secondary">Open trend</span></div>';
        }

        var extraClass = opts.extraClass ? ' ' + opts.extraClass : '';
        return '<div class="mini-trend-card ' + cls + extraClass + '" ' + attrs + '>' +
            '<div class="mini-trend-card-header"><h4>' + title + '</h4>' + badge + '</div>' +
            (opts.subtitle ? '<div class="mini-trend-meta">' + escapeHtml(opts.subtitle) + '</div>' : '') +
            body + '</div>';
    }

    function renderSparklineSection(sparklines) {
        var sparkContainer = $('overview_sparklines');
        if (!sparkContainer) return;

        if (!sparklines.length) {
            sparkContainer.innerHTML = '<p class="stats-empty-inline">No warning or failed trends to chart in this period.</p>';
            return;
        }

        var sh = '<h3>Tests needing attention — trend preview</h3><div class="mini-trend-grid">';
        sparklines.forEach(function (s, idx) {
            var latestVal = '—';
            var lastDate = '';
            if (s.mini_series && s.mini_series.length) {
                var lastPt = s.mini_series[s.mini_series.length - 1];
                latestVal = lastPt.value;
                lastDate = lastPt.date || '';
            }
            sh += buildMiniTrendCardHtml({
                borderClass: borderClass(s.classification || 'warning'),
                extraClass: 'overview-spark-card',
                dataAttrs: 'data-test-id="' + s.test_id + '" data-linac-id="' + s.linac_id +
                    '" data-energy="' + escapeHtml(s.energy || '') + '"',
                title: s.title,
                subtitle: s.linac_name,
                classification: s.classification,
                latestValue: latestVal,
                unit: s.unit || '',
                lastQa: lastDate,
                hasData: true,
                canvasAttr: 'data-spark-index="' + idx + '"'
            });
        });
        sh += '</div>';
        sparkContainer.innerHTML = sh;

        sparklines.forEach(function (s, idx) {
            var canvas = sparkContainer.querySelector('[data-spark-index="' + idx + '"]');
            if (canvas && window.MiniTrend) {
                MiniTrend.drawSparkline(canvas, s.mini_series || [], s.classification);
            }
        });

        sparkContainer.querySelectorAll('.overview-spark-card').forEach(function (card) {
            card.addEventListener('click', function () {
                drillDownSingleTest(
                    card.getAttribute('data-test-id'),
                    [card.getAttribute('data-linac-id')],
                    card.getAttribute('data-energy') || null
                );
            });
        });
    }

    function renderMatrixTable(matrix) {
        var linacs = matrix.linacs || [];
        var sections = matrix.sections || [];
        var rows = matrix.rows || [];
        if (!sections.length && rows.length) {
            sections = [{ label: 'All tests', category: 'all', rows: rows }];
        }

        var mhtml = '<div class="stats-matrix-scroll-inner">';
        sections.forEach(function (section) {
            mhtml += '<div class="matrix-section">';
            mhtml += '<h3 class="matrix-section-title">' + escapeHtml(section.label) + '</h3>';
            mhtml += '<table class="stats-matrix"><thead><tr><th>Test</th>';
            linacs.forEach(function (l) {
                mhtml += '<th>' + escapeHtml(l.name) + '</th>';
            });
            mhtml += '</tr></thead><tbody>';
            (section.rows || []).forEach(function (row) {
                mhtml += '<tr><th>' + escapeHtml(row.test_name) + '</th>';
                (row.cells || []).forEach(function (cell) {
                    var tip = escapeHtml(cell.linac_name) + ' · ' +
                        escapeHtml(row.test_name) + ' · ' +
                        escapeHtml(cell.classification || 'no data') +
                        ' — click for trend';
                    mhtml += '<td class="matrix-cell" ' +
                        'data-test-id="' + cell.test_id + '" data-linac-id="' + cell.linac_id + '" ' +
                        'title="' + tip + '">' +
                        matrixStatusPill(cell.status, cell.classification) + '</td>';
                });
                mhtml += '</tr>';
            });
            mhtml += '</tbody></table></div>';
        });
        mhtml += '</div>';
        return mhtml;
    }

    function renderOverview(data) {
        var review = data.review_list || [];
        renderManagementDashboard(data.charts || {}, review);
        $('matrix_container').innerHTML = renderMatrixTable(data.matrix || {});

        document.querySelectorAll('.matrix-cell').forEach(function (cell) {
            cell.addEventListener('click', function () {
                drillDownSingleTest(
                    cell.getAttribute('data-test-id'),
                    [cell.getAttribute('data-linac-id')],
                    null
                );
            });
        });

        var rhtml = '<table class="stats-table"><thead><tr>' +
            '<th>Date</th><th>LINAC</th><th>Test</th><th>Energy</th>' +
            '<th class="num">Value</th><th>Classification</th><th>Reason</th></tr></thead><tbody>';
        if (!review.length) {
            rhtml += '<tr><td colspan="7" class="text-muted">No warning or failed results in this period.</td></tr>';
        }
        review.forEach(function (r) {
            var cls = (r.reason || '').toLowerCase().indexOf('fail') >= 0 ? 'failed' : 'warning';
            rhtml += '<tr class="clickable review-row" data-test-id="' + r.test_id +
                '" data-linac-id="' + r.linac_id + '" data-energy="' + escapeHtml(r.energy || '') + '">' +
                '<td>' + r.date + '</td><td>' + escapeHtml(r.linac_name) + '</td>' +
                '<td>' + escapeHtml(r.test_name) + '</td><td>' + escapeHtml(r.energy || '—') + '</td>' +
                '<td class="num">' + r.value + ' ' + escapeHtml(r.unit || '') + '</td>' +
                '<td>' + classificationBadge(cls) + '</td>' +
                '<td>' + escapeHtml(r.reason) + '</td></tr>';
        });
        rhtml += '</tbody></table>';
        $('review_list_container').innerHTML = rhtml;

        document.querySelectorAll('.review-row').forEach(function (row) {
            row.addEventListener('click', function () {
                drillDownSingleTest(
                    row.getAttribute('data-test-id'),
                    [row.getAttribute('data-linac-id')],
                    row.getAttribute('data-energy') || null
                );
            });
        });
    }

    function updateSingleTestHeader(data) {
        var sub = $('single_test_chart_subtitle');
        var badge = $('single_test_trend_badge');
        if (!sub) return;

        var test = data.test || {};
        var parts = [test.name || 'Selected test'];
        if (test.energy) parts.push(test.energy);
        var linacNames = (data.series || []).map(function (s) { return s.label; }).filter(Boolean);
        if (linacNames.length === 1) {
            parts.push(linacNames[0]);
        } else if (linacNames.length > 1) {
            parts.push('Multiple LINACs');
        } else {
            parts.push('All LINACs');
        }
        sub.textContent = parts.join(' — ');

        if (badge) {
            badge.innerHTML = data.trend_label
                ? '<span class="' + trendBadgeClass(data.trend_label) + '">' +
                escapeHtml(data.trend_label) + '</span>'
                : '';
        }
    }

    function renderSingleTestTrend(data) {
        currentSingleTestData = data;
        updateSingleTestHeader(data);

        var lines = data.reference_lines || {};
        var customBaseline = parseFloat($('line_baseline').value);
        var customWarn = parseFloat($('line_warning').value);
        var customAction = parseFloat($('line_action').value);
        if (!isNaN(customBaseline)) lines.baseline = customBaseline;
        if (!isNaN(customWarn)) {
            lines.upper_warning = customWarn;
            lines.lower_warning = -customWarn;
        }
        if (isNaN(customAction) && !isNaN(customWarn)) {
            customAction = actionThresholdFromWarning(customWarn);
        }
        if (!isNaN(customAction)) {
            if (!isNaN(customWarn) && customAction <= customWarn) {
                customAction = actionThresholdFromWarning(customWarn);
            }
            lines.upper_action = customAction;
            lines.lower_action = -customAction;
        }
        if ($('line_warning')) $('line_warning').placeholder = String(lines.upper_warning || 'auto');
        if ($('line_action')) $('line_action').placeholder = String(lines.upper_action || 'auto');

        var ctx = $('main_trend_chart').getContext('2d');
        if (mainChart) {
            mainChart.destroy();
            mainChart = null;
        }

        var datasets = (data.series || []).map(function (s, i) {
            var c = PALETTE.series[i % PALETTE.series.length];
            return {
                label: s.label,
                data: (s.points || []).map(function (p) {
                    return { x: p.x, y: p.y, meta: p.meta };
                }),
                borderColor: c,
                backgroundColor: c,
                showLine: true,
                borderWidth: 2.5,
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.15
            };
        });

        mainChart = new Chart(ctx, {
            type: 'line',
            data: { datasets: datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                parsing: false,
                interaction: { mode: 'nearest', intersect: false },
                scales: {
                    x: {
                        type: 'category',
                        title: { display: true, text: 'Date performed', font: { weight: '600' } },
                        grid: { color: '#eef2f6' }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Value (' + ((data.test && data.test.unit) || '') + ')',
                            font: { weight: '600' }
                        },
                        grid: { color: '#eef2f6' }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: { boxWidth: 14, padding: 16, font: { size: 12 } }
                    },
                    tooltip: {
                        backgroundColor: '#1f3a5f',
                        padding: 12,
                        callbacks: {
                            title: function (items) {
                                return items[0] && items[0].label ? items[0].label : '';
                            },
                            label: function (ctx) {
                                var m = ctx.raw.meta || {};
                                return (m.linac_name || ctx.dataset.label) + ': ' + ctx.raw.y +
                                    ' ' + (m.unit || '') + ' (' + (m.classification || '') + ')';
                            }
                        }
                    },
                    annotation: {
                        annotations: buildAnnotations(lines)
                    }
                },
                onClick: function (evt, elements) {
                    if (!elements.length) return;
                    var pt = elements[0].element.$context.raw.meta;
                    if (pt) showDetailPanel(pt.qa_record_id, pt.test_id, pt.energy);
                }
            }
        });

        var gs = data.summary || {};
        var g = gs.global || {};
        var summaryHtml = '<div class="stats-panel-header" style="margin-bottom:12px;">' +
            '<p class="stats-panel-subtitle">Summary statistics for the selected test and period.</p></div>' +
            '<div class="stats-table-wrap"><table class="stats-table"><thead><tr><th>Scope</th>' +
            '<th class="num">Count</th><th class="num">Latest</th><th class="num">Mean</th>' +
            '<th class="num">Min</th><th class="num">Max</th><th class="num">SD</th>' +
            '<th class="num">Warnings</th><th class="num">Failures</th><th>Trend</th></tr></thead><tbody>';
        summaryHtml += rowSummary('All', g);
        (gs.per_linac || []).forEach(function (r) {
            summaryHtml += rowSummary(r.linac_name, r);
        });
        summaryHtml += '</tbody></table></div>';
        $('single_test_summary').innerHTML = summaryHtml;

        var tbody = '';
        (data.table_rows || []).forEach(function (r) {
            tbody += '<tr class="clickable" data-qa-id="' + r.qa_record_id +
                '" data-test-id="' + r.test_id + '" data-energy="' + escapeHtml(r.energy || '') + '">' +
                '<td>' + r.date + '</td><td>' + escapeHtml(r.linac_name) + '</td>' +
                '<td>' + escapeHtml(r.test_name) + '</td><td>' + escapeHtml(r.energy || '—') + '</td>' +
                '<td class="num">' + r.value + '</td><td>' + escapeHtml(r.unit || '') + '</td>' +
                '<td class="num">±' + (r.action_threshold != null ? r.action_threshold : '—') + '</td>' +
                '<td>' + classificationBadge(r.classification) + '</td>' +
                '<td>' + escapeHtml(r.status_name || '—') + '</td>' +
                '<td>' + escapeHtml(r.note || '—') + '</td>' +
                '<td>' + escapeHtml(r.source_type || '—') + '</td>' +
                '<td><a href="/qa-detail/' + r.qa_record_id + '/" class="stats-btn stats-btn-sm stats-btn-secondary" ' +
                'onclick="event.stopPropagation();">Open record</a></td></tr>';
        });
        $('single_test_table_body').innerHTML = tbody ||
            '<tr><td colspan="12" class="text-muted">No data.</td></tr>';

        document.querySelectorAll('#single_test_table_body tr.clickable').forEach(function (tr) {
            tr.addEventListener('click', function (e) {
                if (e.target.closest('a')) return;
                showDetailPanel(
                    tr.getAttribute('data-qa-id'),
                    tr.getAttribute('data-test-id'),
                    tr.getAttribute('data-energy') || null
                );
            });
        });
    }

    function rowSummary(name, r) {
        return '<tr><td>' + escapeHtml(name) + '</td>' +
            '<td class="num">' + (r.count || 0) + '</td>' +
            '<td class="num">' + (r.latest != null ? r.latest : '—') + '</td>' +
            '<td class="num">' + (r.mean != null ? r.mean : '—') + '</td>' +
            '<td class="num">' + (r.min != null ? r.min : '—') + '</td>' +
            '<td class="num">' + (r.max != null ? r.max : '—') + '</td>' +
            '<td class="num">' + (r.stdev != null ? r.stdev : '—') + '</td>' +
            '<td class="num">' + (r.warning_count || 0) + '</td>' +
            '<td class="num">' + (r.failure_count || 0) + '</td>' +
            '<td><span class="' + trendBadgeClass(r.trend_label) + '">' +
            escapeHtml(r.trend_label || '') + '</span></td></tr>';
    }

    function buildAnnotations(lines) {
        var a = {};
        function hline(id, y, color, label, dashed) {
            if (y == null || isNaN(y)) return;
            a[id] = {
                type: 'line',
                yMin: y,
                yMax: y,
                borderColor: color,
                borderWidth: id.indexOf('baseline') >= 0 ? 1.5 : 2,
                borderDash: dashed ? [6, 4] : [],
                label: {
                    display: !!label,
                    content: label,
                    position: 'start',
                    backgroundColor: 'rgba(255,255,255,0.9)',
                    color: color,
                    font: { size: 11, weight: '600' }
                }
            };
        }
        hline('baseline', lines.baseline, '#6b7280', 'Reference', false);
        hline('upper_warn', lines.upper_warning, PALETTE.amber, 'Warning', true);
        hline('lower_warn', lines.lower_warning, PALETTE.amber, '', true);
        hline('upper_action', lines.upper_action, PALETTE.red, 'Action', true);
        hline('lower_action', lines.lower_action, PALETTE.red, '', true);
        return a;
    }

    function renderGroupedTrends(data, containerId, tableBodyId) {
        var container = $(containerId);
        var allCards = [];
        var html = '<section class="stats-panel" style="box-shadow:none;border:none;padding:0 0 8px;">' +
            '<div class="stats-panel-header"><h2 class="stats-panel-title">' +
            escapeHtml(data.title || '') + '</h2></div></section>';

        (data.groups || []).forEach(function (group) {
            html += '<div class="group-block"><h3 class="stats-group-title">' +
                escapeHtml(group.group_label) + '</h3><div class="mini-trend-grid">';
            (group.cards || []).forEach(function (card) {
                var globalIdx = allCards.length;
                allCards.push(card);
                var cls = card.has_data
                    ? borderClass(card.latest_classification)
                    : 'no-data border-missing';
                var energySuffix = card.energy ? ' · ' + card.energy : '';
                html += buildMiniTrendCardHtml({
                    borderClass: cls,
                    dataAttrs: 'data-test-id="' + card.test_id + '" data-energy="' +
                        escapeHtml(card.energy || '') + '"',
                    title: card.test_name + energySuffix,
                    trendLabel: card.trend_label,
                    latestValue: card.latest_value,
                    unit: card.unit,
                    warningCount: card.warning_count,
                    failureCount: card.failure_count,
                    lastQa: card.last_qa_date,
                    hasData: card.has_data,
                    canvasAttr: 'data-card-index="' + globalIdx + '"'
                });
            });
            html += '</div></div>';
        });
        container.innerHTML = html;

        MiniTrend.renderMiniTrendCards(container, allCards);

        container.querySelectorAll('.mini-trend-card[data-test-id]').forEach(function (card) {
            card.addEventListener('click', function () {
                var linacIds = getSelectedLinacIds();
                drillDownSingleTest(
                    card.getAttribute('data-test-id'),
                    linacIds.length ? linacIds : null,
                    card.getAttribute('data-energy') || null
                );
            });
        });

        var tbody = '';
        (data.summary_table || []).forEach(function (r) {
            tbody += '<tr><td>' + escapeHtml(r.test_name) + '</td><td>' +
                escapeHtml(r.category) + '</td><td>' + escapeHtml(r.energy || '—') + '</td>' +
                '<td class="num">' + (r.latest != null ? r.latest : '—') + '</td>' +
                '<td>' + escapeHtml(r.unit || '') + '</td>' +
                '<td><span class="' + trendBadgeClass(r.trend_label) + '">' +
                escapeHtml(r.trend_label || '') + '</span></td>' +
                '<td class="num">' + (r.warning_count || 0) + '</td>' +
                '<td class="num">' + (r.failure_count || 0) + '</td>' +
                '<td>' + escapeHtml(r.last_qa_date || '—') + '</td>' +
                '<td><button type="button" class="stats-btn stats-btn-sm stats-btn-secondary open-trend-btn" ' +
                'data-test-id="' + r.test_id + '" data-energy="' + escapeHtml(r.energy || '') +
                '">Open trend</button></td></tr>';
        });
        $(tableBodyId).innerHTML = tbody ||
            '<tr><td colspan="10" class="text-muted">No data.</td></tr>';

        document.querySelectorAll('.open-trend-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                drillDownSingleTest(
                    btn.getAttribute('data-test-id'),
                    getSelectedLinacIds(),
                    btn.getAttribute('data-energy') || null
                );
            });
        });
    }

    function showDetailPanel(qaRecordId, testId, energy) {
        var params = new URLSearchParams({ test_id: testId });
        if (energy) params.set('energy', energy);
        fetch(apiUrls.point + qaRecordId + '/?' + params.toString(), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (j) {
                if (!j.success) throw new Error(j.error || 'Failed');
                var d = j.data;
                var html = '<div class="stats-detail-grid">' +
                    detailItem('Value', d.value + ' ' + (d.unit || '')) +
                    detailItem('Classification', classificationBadge(d.classification)) +
                    detailItem('Warning', '±' + (d.warning_threshold != null ? d.warning_threshold : '—')) +
                    detailItem('Action', '±' + (d.action_threshold != null ? d.action_threshold : '—')) +
                    detailItem('Date', d.date) +
                    detailItem('LINAC', escapeHtml(d.linac_name)) +
                    detailItem('Test', escapeHtml(d.test_name)) +
                    detailItem('Performer', escapeHtml(d.performer || '—')) +
                    detailItem('Status', escapeHtml(d.status_name || '—')) +
                    '</div>';

                if (d.note) {
                    html += '<div class="stats-detail-section"><h4>Notes</h4><p>' +
                        escapeHtml(d.note) + '</p></div>';
                }

                html += '<div class="stats-detail-section">' +
                    '<a href="' + d.qa_detail_url + '" class="stats-btn stats-btn-primary">Open QA record</a></div>';

                if (d.film_image_url) {
                    html += '<div class="stats-detail-section"><h4>Evidence</h4>' +
                        '<div class="stats-film-frame"><img src="' + escapeHtml(d.film_image_url) +
                        '" alt="Film QA image"></div></div>';
                }

                $('detail_panel_content').innerHTML = html;
                var panel = $('detail_panel');
                panel.classList.add('visible');
                panel.setAttribute('aria-hidden', 'false');
                panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            })
            .catch(function (e) {
                showStatus(e.message, 'error');
            });
    }

    function detailItem(label, value) {
        return '<div class="stats-detail-item"><label>' + label + '</label>' +
            '<div class="value">' + value + '</div></div>';
    }

    function drillDownSingleTest(testId, linacIds, energy) {
        $('view_mode').value = 'single_test';
        $('qa_test_id').value = testId;
        var sel = $('linac_ids');
        if (sel && linacIds && linacIds.length) {
            Array.from(sel.options).forEach(function (o) {
                o.selected = linacIds.indexOf(o.value) >= 0 ||
                    linacIds.indexOf(String(o.value)) >= 0;
            });
        }
        if (energy && $('energy')) {
            $('energy').value = energy;
        }
        updateModeUI();
        applyFilters();
        var panel = document.querySelector('.mode-panel[data-mode="single_test"]');
        if (panel) panel.scrollIntoView({ behavior: 'smooth' });
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function applyFilters() {
        var mode = getViewMode();
        updateModeUI();
        showStatus('Loading statistics…', 'loading');
        fetchApi(mode).then(function (data) {
            showStatus('', '');
            if (mode === 'overview') renderOverview(data);
            else if (mode === 'single_test') renderSingleTestTrend(data);
            else if (mode === 'linac_all_tests') {
                renderGroupedTrends(data, 'linac_all_container', 'linac_all_table_body');
            } else if (mode === 'category_trends') {
                renderGroupedTrends(data, 'category_trends_container', 'category_trends_table_body');
            } else if (mode === 'beam_energy') {
                renderGroupedTrends(data, 'beam_energy_container', 'beam_energy_table_body');
            }
        }).catch(function (e) {
            showStatus(e.message || 'Error loading statistics.', 'error');
        });
    }

    function exportCsv() {
        window.location.href = apiUrls.export + '?' + buildParams().toString();
    }

    function init() {
        if (typeof Chart !== 'undefined') {
            var annPlugin = window['chartjs-plugin-annotation'];
            if (annPlugin) {
                Chart.register(annPlugin.default || annPlugin);
            }
        }
        updateModeUI();
        $('view_mode').addEventListener('change', updateModeUI);
        $('date_preset').addEventListener('change', updateModeUI);
        $('qa_test_id').addEventListener('change', updateModeUI);
        $('test_category').addEventListener('change', updateModeUI);
        $('line_baseline').addEventListener('input', scheduleSingleTestLineRefresh);
        $('line_warning').addEventListener('input', scheduleSingleTestLineRefresh);
        $('line_action').addEventListener('input', scheduleSingleTestLineRefresh);
        $('apply_filters').addEventListener('click', applyFilters);
        $('export_csv').addEventListener('click', exportCsv);
        $('close_detail').addEventListener('click', function () {
            var panel = $('detail_panel');
            panel.classList.remove('visible');
            panel.setAttribute('aria-hidden', 'true');
        });
        applyFilters();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

/**
 * Lightweight sparkline renderer for Statistics mini-trend cards.
 */
(function (global) {
    'use strict';

    function drawSparkline(canvas, series, classification) {
        if (!canvas || !series || !series.length) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width = canvas.offsetWidth || 200;
        var h = canvas.height = 50;
        ctx.clearRect(0, 0, w, h);

        var values = series.map(function (p) { return p.value; });
        var min = Math.min.apply(null, values);
        var max = Math.max.apply(null, values);
        var range = max - min || 1;
        var pad = 4;

        var color = '#16a34a';
        if (classification === 'warning') color = '#d97706';
        if (classification === 'failed') color = '#dc2626';
        if (classification === 'missing') color = '#9ca3af';

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (var i = 0; i < values.length; i++) {
            var x = pad + (i / Math.max(values.length - 1, 1)) * (w - 2 * pad);
            var y = h - pad - ((values[i] - min) / range) * (h - 2 * pad);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        if (values.length === 1) {
            var x0 = w / 2;
            var y0 = h / 2;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x0, y0, 3, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function renderMiniTrendCards(container, cards) {
        if (!container) return;
        container.querySelectorAll('.mini-trend-canvas').forEach(function (canvas) {
            var idx = canvas.getAttribute('data-card-index');
            if (idx === null || !cards[idx]) return;
            var card = cards[idx];
            drawSparkline(canvas, card.mini_series || [], card.latest_classification || 'missing');
        });
    }

    global.MiniTrend = {
        drawSparkline: drawSparkline,
        renderMiniTrendCards: renderMiniTrendCards
    };
})(window);

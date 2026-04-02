/* ============================================================
   TRADING BOT DASHBOARD  —  app.js (Oanda Edition)
   Fetches data from Flask API and renders everything.
   ============================================================ */

const API = '/api/run';
const API_STATUS = '/api/status';
const API_ACCOUNT = '/api/account';
const API_ORDER = '/api/order';
const API_CLOSE = '/api/close';

let charts = {};
let currentMode = 'SIMULADOR';
let currentDecision = null;
let currentGestion = null;

// ── Colour references ────────────────────────────────────────
const C = {
    green: '#10b981',
    red: '#ef4444',
    blue: '#3b82f6',
    yellow: '#f59e0b',
    purple: '#8b5cf6',
    text2: '#94a3b8',
    text3: '#475569',
    grid: 'rgba(255,255,255,0.05)',
};

// ============================================================
// MAIN: load data from API and render everything
// ============================================================
async function loadData() {
    setStatus('loading');
    toggleRefreshSpin(true);

    try {
        // 1. Check Status and Mode
        const statusRes = await fetch(API_STATUS);
        if (statusRes.ok) {
            const statusData = await statusRes.json();
            currentMode = statusData.modo;
            updateModeUI(statusData);
        }

        // 2. Fetch Market Data & Analysis
        const res = await fetch(API);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.error) {
            showToast(data.error, 'err');
            setStatus('err');
            return;
        }

        currentDecision = data.decision;
        currentGestion = data.gestion;

        renderKPIs(data);
        renderCandleChart(data);
        renderRSIChart(data);
        renderMACDChart(data);
        renderDecision(data);
        renderConfluences(data);
        renderIndicators(data);

        // 3. Fetch Account Info (Oanda only)
        if (currentMode === 'OANDA') {
            fetchAccountInfo();
        }

        setStatus('ok');
    } catch (err) {
        console.error(err);
        setStatus('err');
        showToast("Error al conectar con el servidor", 'err');
    } finally {
        toggleRefreshSpin(false);
        hideLoader();
    }
}

// ============================================================
// OANDA ACCOUNT & ORDERS
// ============================================================
async function fetchAccountInfo() {
    try {
        const res = await fetch(API_ACCOUNT);
        const data = await res.json();

        if (data.error) return;

        const acct = data.cuenta;
        const pos = data.posiciones;

        document.getElementById('accountBar').style.display = 'block';
        document.getElementById('acctBalance').textContent = `${acct.balance.toLocaleString()} ${acct.moneda}`;
        document.getElementById('acctNav').textContent = `${acct.nav.toLocaleString()} ${acct.moneda}`;
        document.getElementById('acctPl').textContent = `${acct.pl_abierto.toLocaleString()} ${acct.moneda}`;
        document.getElementById('acctPl').className = `acct-value mono ${acct.pl_abierto >= 0 ? 'pos-pl-pos' : 'pos-pl-neg'}`;
        document.getElementById('acctMargen').textContent = `${acct.margen_libre.toLocaleString()} ${acct.moneda}`;
        document.getElementById('acctPosiciones').textContent = acct.trades_abiertos;

        renderPositions(pos);
    } catch (e) {
        console.error("Account fetch error:", e);
    }
}

function renderPositions(posiciones) {
    const sec = document.getElementById('positionsSection');
    const body = document.getElementById('positionsBody');

    if (!posiciones || posiciones.length === 0) {
        sec.style.display = 'none';
        return;
    }

    sec.style.display = 'block';
    let html = `<table class="positions-table">
        <thead>
            <tr>
                <th>Instrumento</th>
                <th>Dirección</th>
                <th>Unidades</th>
                <th>Precio Entrada</th>
                <th>P&L</th>
            </tr>
        </thead>
        <tbody>`;

    posiciones.forEach(p => {
        html += `<tr>
            <td>${p.instrumento}</td>
            <td class="${p.direccion === 'LONG' ? 'pos-long' : 'pos-short'}">${p.direccion}</td>
            <td>${p.unidades}</td>
            <td>${p.precio_medio.toFixed(5)}</td>
            <td class="${p.pl >= 0 ? 'pos-pl-pos' : 'pos-pl-neg'}">${p.pl.toFixed(2)}</td>
        </tr>`;
    });

    html += `</tbody></table>`;
    body.innerHTML = html;
}

async function ejecutarSenal() {
    if (!currentDecision || currentDecision.direccion === 'NEUTRAL') {
        showToast("No hay una señal válida para ejecutar", 'err');
        return;
    }

    const units = document.getElementById('unitsInput').value;
    const btn = document.getElementById('btnExecute');
    btn.disabled = true;

    try {
        const payload = {
            direccion: currentDecision.direccion,
            unidades: parseInt(units),
            stop_loss: currentGestion ? currentGestion.stop_loss : null,
            take_profit: currentGestion ? currentGestion.take_profit : null
        };

        const res = await fetch(API_ORDER, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await res.json();
        if (result.ok) {
            showToast(`Orden ${currentDecision.direccion} enviada con éxito`, 'ok');
            loadData();
        } else {
            showToast(`Error: ${result.error}`, 'err');
        }
    } catch (e) {
        showToast("Error de conexión al enviar orden", 'err');
    } finally {
        btn.disabled = false;
    }
}

async function cerrarPosicion() {
    if (!confirm("¿Estás seguro de que quieres cerrar todas las posiciones de este instrumento?")) return;

    try {
        const res = await fetch(API_CLOSE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instrumento: null })
        });
        const result = await res.json();
        if (result.ok) {
            showToast("Posiciones cerradas correctamente", 'ok');
            loadData();
        } else {
            showToast(`Error: ${result.error}`, 'err');
        }
    } catch (e) {
        showToast("Error al cerrar posiciones", 'err');
    }
}

// ============================================================
// UI HELPERS
// ============================================================
function updateModeUI(status) {
    const badge = document.getElementById('modeBadge');
    const text = document.getElementById('modeText');
    const icon = document.getElementById('modeIcon');
    const footer = document.getElementById('footerModo');
    const executeArea = document.getElementById('executeArea');

    // Update Auto-Trading UI
    const btnAuto = document.getElementById('btnAutoTrading');
    const txtAuto = document.getElementById('autoText');
    if (status.auto_trading) {
        btnAuto.classList.add('auto-active');
        txtAuto.textContent = 'AUTO ON';
    } else {
        btnAuto.classList.remove('auto-active');
        txtAuto.textContent = 'AUTO OFF';
    }

    if (status.modo === 'OANDA' || status.modo === 'ALPACA') {
        badge.className = `mode-badge ${status.modo.toLowerCase()}`;
        text.textContent = `VIVO: ${status.instrumento}`;
        icon.textContent = '●';
        footer.textContent = `${status.modo} (${status.instrumento})`;
        document.getElementById('acctInstrumento').textContent = status.instrumento;
        executeArea.style.display = 'flex';
    } else {
        badge.className = 'mode-badge sim';
        text.textContent = 'SIMULADOR';
        icon.textContent = '◎';
        footer.textContent = 'Modo Simulador';
        executeArea.style.display = 'none';
        document.getElementById('accountBar').style.display = 'none';
        document.getElementById('positionsSection').style.display = 'none';
    }
}

async function toggleAutoTrading() {
    try {
        const res = await fetch('/api/toggle-auto', { method: 'POST' });
        const result = await res.json();
        if (result.ok) {
            showToast(`Automatización ${result.auto_trading ? 'ACTIVA' : 'DESACTIVADA'}`, result.auto_trading ? 'ok' : 'err');
            loadData();
        }
    } catch (e) {
        showToast("Error al activar automatización", 'err');
    }
}

// -- Polling Autorefresh (Every 30s) --
setInterval(loadData, 30000);


function showToast(msg, type) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = `toast show toast-${type}`;
    setTimeout(() => t.classList.remove('show'), 4000);
}

function setStatus(state) {
    const badge = document.getElementById('statusBadge');
    const text = document.getElementById('statusText');
    badge.className = 'status-badge ' + state;
    if (state === 'ok') { text.textContent = 'Actualizado'; }
    else if (state === 'err') { text.textContent = 'Error'; }
    else { text.textContent = 'Procesando...'; }
}

function toggleRefreshSpin(on) {
    document.getElementById('btnRefresh').classList.toggle('spinning', on);
}

function hideLoader() {
    const el = document.getElementById('loaderOverlay');
    if (el) {
        el.classList.add('hidden');
        setTimeout(() => el.style.display = 'none', 400);
    }
}

// ============================================================
// DASHBOARD RENDERING: Resistant to null/NaN
// ============================================================
const f5 = (v, d = 5) => (v !== null && v !== undefined) ? v.toFixed(d) : "--";

function renderKPIs(data) {
    const m = data.mercado;
    const dec = data.decision;
    const conf = data.confluencias;
    const ind = data.indicadores;

    const dirColor = dec.direccion === 'LONG' ? C.green : dec.direccion === 'SHORT' ? C.red : C.text2;

    const cards = [
        { label: 'Precio Actual', value: f5(m.close), sub: `Var. ${f5(m.variacion, 2)}%`, color: m.variacion >= 0 ? C.green : C.red, icon: '📈' },
        { label: 'Señal Alerta', value: dec.direccion, sub: dec.razon, color: dirColor, icon: '🎯' },
        { label: 'RSI (14)', value: f5(ind.rsi, 1), sub: ind.rsi < 35 ? 'Sobreventa' : ind.rsi > 65 ? 'Sobrecompra' : 'Neutral', color: ind.rsi < 35 ? C.green : ind.rsi > 65 ? C.red : C.text2, icon: '📊' },
        { label: 'Confluencias L', value: conf.total_long, sub: `Min: ${conf.min}`, color: conf.total_long >= conf.min ? C.green : C.text2, icon: '🟢' },
        { label: 'Confluencias S', value: conf.total_short, sub: `Min: ${conf.min}`, color: conf.total_short >= conf.min ? C.red : C.text2, icon: '🔴' },
        { label: 'Instrumento', value: m.instrumento, sub: currentMode, color: C.blue, icon: '🌐' },
    ];

    const row = document.getElementById('kpiRow');
    row.innerHTML = cards.map(c => `
    <div class="kpi-card" style="--kpi-color:${c.color}">
      <span class="kpi-label">${c.label}</span>
      <span class="kpi-value" style="color:${c.color}">${c.value}</span>
      <span class="kpi-sub">${c.sub}</span>
      <span class="kpi-icon">${c.icon}</span>
    </div>
  `).join('');
}

function renderDecision(data) {
    const dec = data.decision;
    const body = document.getElementById('decisionBody');
    const card = document.getElementById('decisionCard');
    const btn = document.getElementById('btnExecute');
    const btnText = document.getElementById('btnExecuteText');

    card.classList.remove('dec-long', 'dec-short', 'dec-neutral');
    btn.classList.remove('short-mode');
    btn.disabled = true;

    if (dec.direccion === 'LONG') {
        body.textContent = '🟢 COMPRA (LONG)';
        card.classList.add('dec-long');
        btn.disabled = false;
        btnText.textContent = 'Abrir LONG';
    } else if (dec.direccion === 'SHORT') {
        body.textContent = '🔴 VENTA (SHORT)';
        card.classList.add('dec-short');
        btn.classList.add('short-mode');
        btn.disabled = false;
        btnText.textContent = 'Abrir SHORT';
    } else {
        body.textContent = '⚪ SIN OPERACIÓN';
        card.classList.add('dec-neutral');
        btnText.textContent = 'Esperando Señal';
    }

    document.getElementById('decisionReason').textContent = dec.razon;
    document.getElementById('patternPill').textContent = data.patron || 'Sin patrón';

    if (data.gestion) {
        document.getElementById('riskTable').style.display = 'block';
        const g = data.gestion;
        const rows = [
            ['Stop Loss', f5(g.stop_loss)],
            ['Take Profit', f5(g.take_profit)],
            ['Riesgo/Unidad', f5(g.riesgo_por_unidad)],
            ['Unidades Sugeridas', Math.round(g.tamano_posicion) || "--"],
            ['Ratio R:B', `1 : ${f5(g.ratio_riesgo, 2)}`]
        ];
        document.getElementById('riskData').innerHTML = rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');
    } else {
        document.getElementById('riskTable').style.display = 'none';
    }
}

function renderConfluences(data) {
    const c = data.confluencias;
    document.getElementById('confBadges').innerHTML = `
    <span class="conf-badge long">▲ ${c.total_long}</span>
    <span class="conf-badge short">▼ ${c.total_short}</span>
  `;

    const buildList = (list) => list.length ? list.map(i => `<div class="conf-item">${i}</div>`).join('') : '<p class="conf-empty">No hay señales presentes</p>';
    document.getElementById('confColumns').innerHTML = `
    <div class="conf-col long-col"><h3>▲ LONG</h3>${buildList(c.long)}</div>
    <div class="conf-col short-col"><h3>▼ SHORT</h3>${buildList(c.short)}</div>
  `;
}

function renderIndicators(data) {
    const ind = data.indicadores;
    const items = [
        { name: 'EMA 20', val: f5(ind.ema_20), cls: 'val-blue' },
        { name: 'EMA 50', val: f5(ind.ema_50), cls: 'val-yellow' },
        { name: 'EMA 200', val: f5(ind.ema_200), cls: 'val-purple' },
        { name: 'RSI (14)', val: f5(ind.rsi, 2), cls: ind.rsi < 35 ? 'val-green' : ind.rsi > 65 ? 'val-red' : '' },
        { name: 'MACD Hist', val: f5(ind.macd_histogram), cls: ind.macd_histogram >= 0 ? 'val-green' : 'val-red' },
        { name: 'ATR (14)', val: f5(ind.atr), cls: '' },
        { name: 'BB Sup', val: f5(ind.bb_superior), cls: '' },
        { name: 'BB Inf', val: f5(ind.bb_inferior), cls: '' }
    ];
    document.getElementById('indicatorsGrid').innerHTML = items.map(i => `
    <div class="ind-card"><span class="ind-name">${i.name}</span><span class="ind-value ${i.cls}">${i.val}</span></div>
  `).join('');
}

// ============================================================
// CHARTS LOGIC (UNCHANGED)
// ============================================================
function renderCandleChart(data) {
    const el = document.getElementById('candleChart'); el.innerHTML = '';
    const chart = LightweightCharts.createChart(el, chartOptions(el, 400));
    charts.candle = chart;

    const candleSeries = chart.addCandlestickSeries({ upColor: C.green, downColor: C.red, borderUpColor: C.green, borderDownColor: C.red, wickUpColor: C.green, wickDownColor: C.red });
    candleSeries.setData(data.candles);

    const volSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'vol', scaleMargins: { top: 0.8, bottom: 0 } });
    volSeries.setData(data.series.volume);

    chart.addLineSeries({ color: C.blue, lineWidth: 1 }).setData(data.series.ema_20);
    chart.addLineSeries({ color: C.yellow, lineWidth: 1 }).setData(data.series.ema_50);
    chart.addLineSeries({ color: C.purple, lineWidth: 1 }).setData(data.series.ema_200);

    chart.timeScale().fitContent();
    makeResponsive(chart, el);
}

function renderRSIChart(data) {
    const el = document.getElementById('rsiChart'); el.innerHTML = '';
    const chart = LightweightCharts.createChart(el, chartOptions(el, 200));
    charts.rsi = chart;
    const s = chart.addLineSeries({ color: C.blue, lineWidth: 2 });
    s.setData(data.series.rsi);
    s.createPriceLine({ price: 65, color: C.red, lineWidth: 1, lineStyle: 2 });
    s.createPriceLine({ price: 35, color: C.green, lineWidth: 1, lineStyle: 2 });
    chart.timeScale().fitContent();
    makeResponsive(chart, el);
}

function renderMACDChart(data) {
    const el = document.getElementById('macdChart'); el.innerHTML = '';
    const chart = LightweightCharts.createChart(el, chartOptions(el, 200));
    charts.macd = chart;
    const h = chart.addHistogramSeries();
    h.setData(data.series.macd_histogram.map(p => ({ time: p.time, value: p.value, color: p.value >= 0 ? C.green : C.red })));
    chart.addLineSeries({ color: C.blue, lineWidth: 1 }).setData(data.series.macd);
    chart.addLineSeries({ color: C.yellow, lineWidth: 1 }).setData(data.series.macd_signal);
    chart.timeScale().fitContent();
    makeResponsive(chart, el);
}

function chartOptions(el, height) {
    return { width: el.clientWidth || 800, height, layout: { background: { color: 'transparent' }, textColor: C.text2, fontSize: 11 }, grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } }, timeScale: { borderColor: C.grid, timeVisible: true } };
}

function makeResponsive(chart, el) {
    new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth })).observe(el);
}

document.addEventListener('DOMContentLoaded', loadData);

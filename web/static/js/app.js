/* ═══════════════════════════════════════════════════════════
   MERA VICTORINO — Pro Dashboard v3.0
   WebSocket-driven, selective updates, sparklines
   ═══════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────
const S = {
  auto: false,
  connected: false,
  lastData: null,
  prevEquity: 0,
  prevPl: 0,
  equityHistory: [],
  plHistory: [],
  consoleFilter: 'all',
  consoleLogs: [],
  maxConsole: 80,
  maxSparkline: 30,
  latency: null,
  reconnectAttempt: 0,
  maxReconnect: 50,
  pollFallbackId: null,
  securityEnabled: false,
};

// ── Auth Modal Logic ──────────────────────────────────────
let authPromiseResolve = null;

function requestAuth(title, msg) {
  const modal = document.getElementById('authModal');
  const titleEl = document.getElementById('modalTitle');
  const msgEl = document.getElementById('modalMsg');
  const input = document.getElementById('modalPin');
  
  if (titleEl) titleEl.textContent = title || 'Security Access';
  if (msgEl) msgEl.textContent = msg || 'Please enter your PIN to continue.';
  if (input) {
    input.value = '';
    setTimeout(() => input.focus(), 100);
  }
  if (modal) modal.style.display = 'flex';

  return new Promise((resolve) => {
    authPromiseResolve = resolve;
  });
}

function submitAuthModal() {
  const input = document.getElementById('modalPin');
  const val = input ? input.value : null;
  closeAuthModal(val);
}

function closeAuthModal(value) {
  const modal = document.getElementById('authModal');
  if (modal) modal.style.display = 'none';
  if (authPromiseResolve) {
    authPromiseResolve(value);
    authPromiseResolve = null;
  }
}

// ── Socket.IO Connection with Auto-Reconnect ──────────────
let socket = null;
let pingStart = 0;

function initSocket() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = io(location.origin, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: S.maxReconnect,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000,
    timeout: 8000,
  });

  socket.on('connect', () => {
    S.connected = true;
    S.reconnectAttempt = 0;
    setConnectionStatus('connected', 'Connected');
    addConsoleLog('info', `WebSocket connected [${socket.id}]`);
    clearFallbackPoll();
  });

  socket.on('disconnect', (reason) => {
    S.connected = false;
    setConnectionStatus('disconnected', 'Disconnected');
    addConsoleLog('warn', `WebSocket disconnected: ${reason}`);
    startFallbackPoll();
  });

  socket.on('reconnect_attempt', (attempt) => {
    S.reconnectAttempt = attempt;
    setConnectionStatus('reconnecting', `Retry ${attempt}`);
  });

  socket.on('reconnect_failed', () => {
    setConnectionStatus('disconnected', 'Failed');
    addConsoleLog('error', 'Max reconnection attempts reached. Using HTTP fallback.');
    startFallbackPoll();
  });

  // ── Data Stream ──────────────────────────────
  socket.on('data_update', (data) => {
    updateDashboard(data);
  });

  // ── Latency Pong ─────────────────────────────
  socket.on('pong_latency', () => {
    S.latency = Date.now() - pingStart;
    updateLatencyBadge();
  });

  // ── Console Events from Server ───────────────
  socket.on('console_event', (evt) => {
    addConsoleLog(evt.type || 'info', evt.msg || '');
  });
}

// ── Latency Ping ──────────────────────────────────────────
function pingLatency() {
  if (!socket || !S.connected) return;
  pingStart = Date.now();
  socket.emit('ping_latency');
}

function updateLatencyBadge() {
  const el = document.getElementById('latencyBadge');
  const val = document.getElementById('latencyValue');
  if (!el || !val) return;
  const ms = S.latency;
  val.textContent = ms !== null ? `${ms}ms` : '— ms';
  el.className = 'latency-badge ' + (ms === null ? '' : ms < 150 ? 'good' : ms < 500 ? 'warn' : 'bad');
}

// ── Connection Status Badge ───────────────────────────────
function setConnectionStatus(cls, label) {
  const el = document.getElementById('connStatus');
  const lbl = document.getElementById('connLabel');
  if (el) el.className = 'conn-status ' + cls;
  if (lbl) lbl.textContent = label;
}

// ── HTTP Fallback Polling ─────────────────────────────────
function startFallbackPoll() {
  if (S.pollFallbackId) return;
  S.pollFallbackId = setInterval(async () => {
    try {
      const res = await fetch('/api/summary');
      if (!res.ok) return;
      const data = await res.json();
      updateDashboard(data);
    } catch (e) { /* silent */ }
  }, 5000);
}

function clearFallbackPoll() {
  if (S.pollFallbackId) {
    clearInterval(S.pollFallbackId);
    S.pollFallbackId = null;
  }
}

// ═══ Dashboard Update (Selective Rendering) ═══════════════
function updateDashboard(data) {
  if (!data) return;
  const prev = S.lastData;
  S.lastData = data;

  // 1. Mode & Bot State
  updateIfChanged('modeLabel', `${data.mode} v3.0`);
  S.auto = data.auto;
  updateToggleButton(data.auto);

  // 2. Equity
  const eq = data.equity || 0;
  const eqText = '$' + formatNum(eq);
  updateIfChanged('equity', eqText, eq !== S.prevEquity ? (eq > S.prevEquity ? 'flash-up' : 'flash-down') : null);
  S.prevEquity = eq;

  // Sparkline
  S.equityHistory.push(eq);
  if (S.equityHistory.length > S.maxSparkline) S.equityHistory.shift();
  drawSparkline('equitySpark', S.equityHistory, '#818cf8');

  // 3. P/L
  const pl = data.pl || 0;
  const plEl = document.getElementById('plTotal');
  if (plEl) {
    plEl.textContent = (pl >= 0 ? '+' : '') + '$' + pl.toFixed(2);
    plEl.className = pl >= 0 ? 'stat-sub up' : 'stat-sub down';
  }

  // Day P/L
  const dayPl = data.day_pl || 0;
  updateIfChanged('dayPl', (dayPl >= 0 ? '+' : '') + '$' + dayPl.toFixed(2));
  const dayPlEl = document.getElementById('dayPl');
  if (dayPlEl) dayPlEl.className = 'stat-value ' + (dayPl >= 0 ? 'up' : 'down');
  S.plHistory.push(dayPl);
  if (S.plHistory.length > S.maxSparkline) S.plHistory.shift();
  drawSparkline('plSpark', S.plHistory, dayPl >= 0 ? '#34d399' : '#f87171');

  // 4. Crypto P/L Breakdown
  const plC = data.pl_crypto || 0;
  const plCR = data.pl_crypto_realized || 0;
  updateIfChanged('plCrypto', (plC >= 0 ? '+' : '') + '$' + plC.toFixed(2));
  const plCEl = document.getElementById('plCrypto');
  if (plCEl) plCEl.className = 'stat-value ' + (plC >= 0 ? 'up' : 'down');
  updateIfChanged('plCryptoRealized', 'Realiz.: ' + (plCR >= 0 ? '+' : '') + '$' + plCR.toFixed(2));

  // 5. Stocks P/L Breakdown
  const plS = data.pl_stocks || 0;
  const plSR = data.pl_stocks_realized || 0;
  updateIfChanged('plStocks', (plS >= 0 ? '+' : '') + '$' + plS.toFixed(2));
  const plSEl = document.getElementById('plStocks');
  if (plSEl) plSEl.className = 'stat-value ' + (plS >= 0 ? 'up' : 'down');
  updateIfChanged('plStocksRealized', 'Realiz.: ' + (plSR >= 0 ? '+' : '') + '$' + plSR.toFixed(2));

  // 6. Buying Power
  updateIfChanged('bp', '$' + formatNum(data.bp || 0));

  // 7. Stats Row
  const posCount = (data.pos || []).length;
  const ordCount = (data.orders || []).length;
  updateIfChanged('posCount', String(posCount));
  updateIfChanged('orderCount', String(ordCount));
  updateIfChanged('posBadge', String(posCount));
  const openPlTotal = (data.pos || []).reduce((a, p) => a + (p.p || 0), 0);
  const openPlEl = document.getElementById('openPl');
  if (openPlEl) {
    openPlEl.textContent = (openPlTotal >= 0 ? '+' : '') + '$' + openPlTotal.toFixed(2);
    openPlEl.className = 'stat-value ' + (openPlTotal >= 0 ? 'up' : 'down');
  }
  updateIfChanged('providerLabel', data.mode || '—');
  S.securityEnabled = data.security_enabled || false;

  // 8. Watchlist (only if changed)
  const watchStr = JSON.stringify(data.summary);
  if (!prev || JSON.stringify(prev.summary) !== watchStr) {
    renderWatchlist(data.summary || {});
  }

  // 7. Positions (only if changed)
  const posStr = JSON.stringify(data.pos);
  if (!prev || JSON.stringify(prev.pos) !== posStr) {
    renderPositions(data.pos || []);
  }

  // 8. Closed Positions (only if changed)
  const closedStr = JSON.stringify(data.closed);
  if (!prev || JSON.stringify(prev.closed) !== closedStr) {
    renderClosed(data.closed || []);
  }

  // 9. History
  const histStr = JSON.stringify(data.history);
  if (!prev || JSON.stringify(prev.history) !== histStr) {
    renderHistory(data.history || []);
  }

  // 10. Orders
  const ordStr = JSON.stringify(data.orders);
  if (!prev || JSON.stringify(prev.orders) !== ordStr) {
    renderOrders(data.orders || []);
  }

  lucide.createIcons();
}

// ── Selective DOM Update ──────────────────────────────────
function updateIfChanged(id, text, flashClass) {
  const el = document.getElementById(id);
  if (!el || el.textContent === text) return;
  el.textContent = text;
  if (flashClass) {
    el.classList.remove('flash-up', 'flash-down');
    void el.offsetWidth; // force reflow
    el.classList.add(flashClass);
    setTimeout(() => el.classList.remove(flashClass), 700);
  }
}

// ── Toggle Button ─────────────────────────────────────────
function updateToggleButton(active) {
  const btn = document.getElementById('toggleBtn');
  if (!btn) return;
  btn.className = 'btn-toggle ' + (active ? 'btn-on' : 'btn-off');
  btn.innerHTML = active
    ? '<i data-lucide="square" style="width:14px;height:14px"></i><span>Stop Bot</span>'
    : '<i data-lucide="play" style="width:14px;height:14px"></i><span>Start Bot</span>';
}

// ── Watchlist ─────────────────────────────────────────────
function renderWatchlist(summary) {
  const el = document.getElementById('watchlist');
  if (!el) return;
  const entries = Object.entries(summary);
  if (entries.length === 0) {
    el.innerHTML = '<div style="font-size:0.7rem;color:var(--dim-2)">Waiting for scan…</div>';
    return;
  }
  el.innerHTML = entries.map(([sym, d]) => {
    const dir = (d.dir || 'Neutral').toUpperCase();
    const time = formatTime(d.time);
    return `
      <div class="watch-item">
        <span class="watch-sym">${sym}</span>
        <div style="display:flex;align-items:center;gap:0.4rem">
          <span class="watch-dir ${dir.toLowerCase()}">${dir}</span>
          <span style="font-size:0.6rem;color:var(--dim-2)">${time}</span>
        </div>
      </div>
    `;
  }).join('');
}

// ── Positions Table ───────────────────────────────────────
function renderPositions(pos) {
  const table = document.getElementById('posTable');
  const cards = document.getElementById('posCards');
  if (!table) return;

  if (pos.length === 0) {
    table.innerHTML = '<tr><td colspan="6" class="empty-row">No open positions</td></tr>';
    if (cards) cards.innerHTML = '<div style="text-align:center;padding:1.5rem 0;color:var(--dim-2)">No open positions</div>';
    return;
  }

  table.innerHTML = pos.map(p => `
    <tr>
      <td style="font-weight:700">${p.s}</td>
      <td><span class="badge ${p.d === 'LONG' ? 'up' : 'down'}">${p.d === 'LONG' ? 'Buy' : 'Sell'}</span></td>
      <td class="mono">${p.q}</td>
      <td class="mono">$${formatNum(p.v || 0)}</td>
      <td class="mono">$${p.e}</td>
      <td class="mono">$${p.c}</td>
      <td class="${p.p >= 0 ? 'up' : 'down'}" style="font-weight:700;font-family:var(--mono)">
        ${p.p >= 0 ? '+' : ''}$${p.p.toFixed(2)} <span style="opacity:0.6;font-size:0.7rem">(${p.pct.toFixed(2)}%)</span>
      </td>
      <td style="color:var(--dim-2);font-size:0.75rem;white-space:nowrap">${formatTime(p.t)}</td>
    </tr>
  `).join('');

  if (cards) {
    cards.innerHTML = pos.map(p => `
      <div class="pos-card">
        <div class="pos-card-header">
          <span class="pos-card-symbol">${p.s} <span style="font-size:0.6rem;opacity:0.5">[${p.d === 'LONG' ? 'BUY' : 'SELL'}]</span></span>
          <span class="badge ${p.p >= 0 ? 'up' : 'down'}">${p.pct.toFixed(2)}%</span>
        </div>
        <div class="pos-card-body">
          <div class="pos-card-stat"><span class="pos-card-label">Qty</span><span class="pos-card-value">${p.q}</span></div>
          <div class="pos-card-stat"><span class="pos-card-label">Entry</span><span class="pos-card-value">$${p.e}</span></div>
          <div class="pos-card-stat"><span class="pos-card-label">Current</span><span class="pos-card-value">$${p.c}</span></div>
          <div class="pos-card-stat"><span class="pos-card-label">P/L</span><span class="pos-card-value ${p.p >= 0 ? 'up' : 'down'}">${p.p >= 0 ? '+' : ''}$${p.p.toFixed(2)}</span></div>
        </div>
      </div>
    `).join('');
  }
}

// ── Closed Positions ──────────────────────────────────────
function renderClosed(closed) {
  const el = document.getElementById('closedTable');
  if (!el) return;
  if (!closed || closed.length === 0) {
    el.innerHTML = '<tr><td colspan="7" class="empty-row">No hay actividad todavía</td></tr>';
    return;
  }
  el.innerHTML = closed.map(c => `
    <tr>
      <td style="font-weight:700">${c.s}</td>
      <td><span class="badge ${c.side === 'BUY' ? 'up' : 'down'}">${c.side}</span></td>
      <td class="mono">${c.q}</td>
      <td class="mono">$${c.p}</td>
      <td class="mono">${c.entry ? '$' + c.entry : '—'}</td>
      <td class="${(c.pl || 0) >= 0 ? 'up' : 'down'}" style="font-weight:700;font-family:var(--mono)">
        ${c.pl !== null ? ((c.pl >= 0 ? '+' : '') + '$' + c.pl.toFixed(2)) : '—'}
      </td>
      <td style="color:var(--dim-2);font-size:0.75rem">${formatTime(c.time)}</td>
    </tr>
  `).join('');
}

// ── History ───────────────────────────────────────────────
function renderHistory(history) {
  const el = document.getElementById('historyList');
  if (!el) return;
  if (!history || history.length === 0) {
    el.innerHTML = '<div style="font-size:0.7rem;color:var(--dim-2);padding:0.5rem 0">No activity yet</div>';
    return;
  }
  el.innerHTML = history.map(h => `
    <div class="hist-item">
      <div>
        <span class="hist-sym ${h.type.includes('LONG') ? 'up' : h.type.includes('SHORT') ? 'down' : ''}">${h.sym}</span>
        <span class="badge" style="font-size:0.55rem;margin-left:0.3rem">${h.type}</span>
        <div class="hist-meta">${h.reason}</div>
      </div>
      <div style="text-align:right">
        <span class="hist-price">$${h.price}</span>
        <div class="hist-meta">${formatTime(h.time)}</div>
      </div>
    </div>
  `).join('');
}

// ── Orders ────────────────────────────────────────────────
let lastOrdersData = [];
function renderOrders(orders) {
  if (orders) lastOrdersData = orders;
  const el = document.getElementById('pendingOrders');
  if (!el) return;
  const search = (document.getElementById('orderSearch')?.value || '').toUpperCase();
  const filtered = lastOrdersData.filter(o => o.symbol.toUpperCase().includes(search));

  if (filtered.length === 0) {
    el.innerHTML = `<div style="font-size:0.75rem;color:var(--dim-2);padding:0.5rem 0.6rem">${lastOrdersData.length > 0 ? 'No matches.' : 'No pending orders.'}</div>`;
    return;
  }
  el.innerHTML = filtered.map(o => `
    <div class="order-item">
      <span><span class="badge ${o.side === 'buy' ? 'up' : 'down'}">${o.side.toUpperCase()}</span> <b>${o.symbol}</b> ×${o.qty}</span>
      <span style="color:var(--dim-2);font-size:0.65rem">${o.status} — ${formatTime(o.created_at)}</span>
    </div>
  `).join('');
}
function filterOrders() { renderOrders(); }

// ═══ Sparkline Renderer (Canvas – ultra-light) ════════════
function drawSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || data.length < 2) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = w / (data.length - 1);

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + '40');
  grad.addColorStop(1, color + '00');

  ctx.beginPath();
  ctx.moveTo(0, h);
  data.forEach((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 2);
    if (i === 0) ctx.lineTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.lineTo(w, h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 2);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

// ═══ Event Console ════════════════════════════════════════
function addConsoleLog(type, msg) {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  S.consoleLogs.unshift({ type, msg, time });
  if (S.consoleLogs.length > S.maxConsole) S.consoleLogs.pop();
  renderConsole();
}

function renderConsole() {
  const el = document.getElementById('consoleBody');
  if (!el) return;
  const logs = S.consoleFilter === 'all'
    ? S.consoleLogs
    : S.consoleLogs.filter(l => l.type === S.consoleFilter);

  el.innerHTML = logs.slice(0, 40).map(l => `
    <div class="console-line">
      <span class="console-time">${l.time}</span>
      <span class="console-tag ${l.type}">${l.type}</span>
      <span class="console-msg">${escapeHtml(l.msg)}</span>
    </div>
  `).join('');
}

function setConsoleFilter(filter, btn) {
  S.consoleFilter = filter;
  document.querySelectorAll('.console-filter').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderConsole();
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ═══ Actions ══════════════════════════════════════════════
async function toggleBot() {
  let pwd = null;
  if (S.securityEnabled) {
    pwd = await requestAuth('Security PIN Required', 'Please enter your Bot Security PIN to toggle the bot state:');
    if (!pwd) return;
  }

  try {
    const body = {};
    if (pwd) body.password = pwd;

    const res = await fetch('/api/toggle', { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    
    if (res.status === 401) {
      alert('Invalid PIN. Action rejected.');
      addConsoleLog('error', 'Auth failed: Invalid PIN');
      return;
    }
    
    if (!res.ok) throw new Error('Update failed');
    const d = await res.json();
    S.auto = d.state;
    addConsoleLog('info', `Bot toggled manually → ${S.auto ? 'ACTIVE' : 'STANDBY'}`);
  } catch (e) {
    addConsoleLog('error', 'Toggle failed: ' + e.message);
  }
}

async function cancelAllOrders() {
  if (!confirm('Cancel all pending orders?')) return;
  
  let pwd = null;
  if (S.securityEnabled) {
    pwd = await requestAuth('Confirm Cancellation', 'Enter Bot Security PIN to confirm cancellation:');
    if (!pwd) return;
  }

  try {
    const body = {};
    if (pwd) body.password = pwd;

    const res = await fetch('/api/cancel_all', { 
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    
    if (res.status === 401) {
      alert('Invalid PIN. Action rejected.');
      return;
    }

    const data = await res.json();
    if (data.ok) {
      // addConsoleLog handled by server broadcast
    } else {
      addConsoleLog('error', 'Cancel failed: ' + (data.error || 'unknown'));
    }
  } catch (e) {
    addConsoleLog('error', 'Connection error during cancel.');
  }
}

// ── Panel Collapse ────────────────────────────────────────
function togglePanel(bodyId, btn) {
  const body = document.getElementById(bodyId);
  if (!body) return;
  body.classList.toggle('collapsed');
  if (btn) btn.classList.toggle('collapsed');
}

// ── Utility ───────────────────────────────────────────────
function formatNum(n) {
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatTime(s) {
  if (!s) return '—';
  try {
    const d = new Date(s);
    if (isNaN(d.getTime())) return s;
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const timeStr = d.toLocaleTimeString('es-ES', { hour12: false, hour: '2-digit', minute: '2-digit' });
    if (isToday) return timeStr;
    const dateStr = d.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
    return `${dateStr} ${timeStr}`;
  } catch (e) { return s; }
}

// ═══ Bootstrap ════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  initSocket();
  addConsoleLog('info', 'Dashboard v3.0 initialized.');

  // Latency ping every 5s
  setInterval(pingLatency, 5000);
  setTimeout(pingLatency, 1000);

  // Initial HTTP fetch in case socket is slow
  setTimeout(async () => {
    if (!S.lastData) {
      try {
        const res = await fetch('/api/summary');
        if (res.ok) updateDashboard(await res.json());
      } catch(e) {}
    }
  }, 2000);

  // Initial performance chart load
  refreshPerformanceChart();

  // Modal event listeners
  document.getElementById('modalPin')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') submitAuthModal();
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAuthModal(null);
  });
});

// ── Performance Chart (Capital Evolution) ────────────────────
let currentPerformancePeriod = 'MONTH';
let perfChart = null;
let perfSeries = null;

async function setPerformancePeriod(period) {
  currentPerformancePeriod = period;
  const btns = document.querySelectorAll('#tfSelector .tf-btn');
  btns.forEach(b => {
    b.classList.toggle('active', b.getAttribute('onclick')?.includes(period));
  });
  refreshPerformanceChart();
}
window.setPerformancePeriod = setPerformancePeriod; // Make global for onclick

async function refreshPerformanceChart() {
  try {
    const res = await fetch(`/api/portfolio_history?period=${currentPerformancePeriod}`);
    const data = await res.json();
    if (data.error) return;
    renderPerformanceChart(data);
  } catch (e) {}
}

function renderPerformanceChart(data) {
  const el = document.getElementById('performanceChart');
  if (!el) return;

  if (!perfChart) {
    perfChart = LightweightCharts.createChart(el, {
      width: el.clientWidth,
      height: 300,
      layout: {
        background: { color: 'transparent' },
        textColor: '#64748b',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(100, 120, 180, 0.05)' },
        horzLines: { color: 'rgba(100, 120, 180, 0.05)' },
      },
      timeScale: {
        borderColor: 'rgba(100, 120, 180, 0.1)',
        timeVisible: true,
      },
    });

    perfSeries = perfChart.addAreaSeries({
      lineColor: '#818cf8',
      topColor: 'rgba(129, 140, 248, 0.3)',
      bottomColor: 'rgba(129, 140, 248, 0)',
      lineWidth: 2,
    });

    new ResizeObserver(() => {
      perfChart.applyOptions({ width: el.clientWidth });
    }).observe(el);
  }

  const formattedData = data.map(d => ({
    time: d.time,
    value: d.value
  })).sort((a, b) => a.time - b.time);

  perfSeries.setData(formattedData);
  perfChart.timeScale().fitContent();
}

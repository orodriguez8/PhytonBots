// Unified Dashboard JS with Dual View (Table & Cards)
const state = { auto: false, busy: false };

async function refresh() {
    if (state.busy) return;
    try {
        const res = await fetch('/api/summary');
        if (!res.ok) throw new Error();
        const data = await res.json();
        updateUI(data);
    } catch (e) { console.warn("Poll failed", e); }
}

function updateUI(data) {
    // 1. Core State & Status
    state.auto = data.auto;
    const statusEl = document.getElementById('statusMode');
    statusEl.innerHTML = `<span class="status-dot"></span>${data.mode} — ${data.auto ? 'ACTIVE' : 'STANDBY'}`;
    statusEl.parentElement.className = `glass ${data.auto ? 'active' : ''}`;
    
    // 2. Control Button
    const btn = document.getElementById('toggleBtn');
    btn.className = `btn ${data.auto ? 'btn-on' : 'btn-off'}`;
    btn.innerHTML = data.auto ? '<i data-lucide="power"></i> STOP BOT' : '<i data-lucide="play"></i> START BOT';
    
    // 3. Main Stats
    document.getElementById('equity').innerText = `$${data.equity.toLocaleString()}`;
    document.getElementById('bp').innerText = `$${(data.bp || 0).toLocaleString()}`;
    const plEl = document.getElementById('plTotal');

    plEl.innerText = `${data.pl >= 0 ? '+' : ''}$${data.pl.toFixed(2)}`;
    plEl.className = data.pl >= 0 ? 'up' : 'down';
    
    // 4. Watchlist
    const watchEl = document.getElementById('watch');
    watchEl.innerHTML = Object.entries(data.summary).map(([s, d]) => `
        <div class="sym-card ${d.dir.toLowerCase()}">
            <b style="font-size:0.9rem">${s}</b>
            <span style="font-size:0.6rem;opacity:0.7">${d.dir}</span>
            <span style="font-size:0.55rem;opacity:0.5">${d.time}</span>
        </div>
    `).join('');
    
    // 5. Positions - DUAL VIEW (Table for Desktop, Cards for Mobile)
    const posTable = document.getElementById('posTable');
    const posCards = document.getElementById('posCards');
    
    if (data.pos.length > 0) {
        // Desktop Table
        posTable.innerHTML = data.pos.map(p => `
            <tr>
                <td style="font-weight:700">${p.s}</td>
                <td>${p.q}</td>
                <td>$${p.e}</td>
                <td>$${p.c}</td>
                <td class="${p.p >= 0 ? 'up' : 'down'}" style="font-weight:700">
                    ${p.p >= 0 ? '+' : ''}$${p.p.toFixed(2)} (${p.pct.toFixed(2)}%)
                </td>
            </tr>
        `).join('');

        // Mobile Cards
        posCards.innerHTML = data.pos.map(p => `
            <div class="pos-card">
                <div class="pos-card-header">
                    <span class="pos-card-symbol">${p.s}</span>
                    <span class="badge ${p.p >= 0 ? 'up' : 'down'}" style="font-size:0.7rem; font-weight:800; border:1px solid currentColor; padding:2px 8px; border-radius:6px">
                        ${p.pct.toFixed(2)}%
                    </span>
                </div>
                <div class="pos-card-body">
                    <div class="pos-card-stat">
                        <span class="pos-card-label">Qty</span>
                        <span class="pos-card-value">${p.q}</span>
                    </div>
                    <div class="pos-card-stat">
                        <span class="pos-card-label">Entry</span>
                        <span class="pos-card-value">$${p.e}</span>
                    </div>
                    <div class="pos-card-stat">
                        <span class="pos-card-label">Current</span>
                        <span class="pos-card-value">$${p.c}</span>
                    </div>
                </div>
                <div class="pos-card-footer">
                    <div class="pos-card-stat">
                        <span class="pos-card-label">Profit/Loss</span>
                        <span class="pos-card-pl ${p.p >= 0 ? 'up' : 'down'}">
                            ${p.p >= 0 ? '+' : ''}$${p.p.toFixed(2)}
                        </span>
                    </div>
                </div>
            </div>
        `).join('');
    } else {
        const empty = `<div style="text-align:center; color:var(--dim); padding:2rem 0; width:100%">No open positions</div>`;
        posTable.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem 0; color:var(--dim)">No open positions</td></tr>`;
        posCards.innerHTML = empty;
    }

    // 6. History
    const histEl = document.getElementById('history');
    histEl.innerHTML = data.history.map(h => `
        <div class="hist-item">
            <div style="display:flex; flex-direction:column">
                <b class="${h.type.includes('LONG') ? 'up' : 'down'}">${h.sym} — ${h.type}</b>
                <span class="hist-meta">${h.reason}</span>
            </div>
            <div style="text-align:right">
                <b>$${h.price}</b><br/>
                <span class="hist-meta">${h.time}</span>
            </div>
        </div>
    `).join('');

    // 7. Orders
    updateOrders(data);
    
    lucide.createIcons();
}

function updateOrders(data) {
    const ordersEl = document.getElementById('pendingOrders');
    if (!data.orders || data.orders.length === 0) {
        ordersEl.innerHTML = `<span style="font-size:0.8rem; color:var(--dim)">No pending orders.</span>`;
        return;
    }
    ordersEl.innerHTML = data.orders.map(o => `
        <div class="sym-card" style="display:flex; justify-content:space-between; width:100%; margin-bottom:0.4rem; padding:0.5rem; border:1px solid var(--border)">
            <span><b class="${o.side == 'buy' ? 'up' : 'down'}">${o.side.toUpperCase()}</b> ${o.symbol} x${o.qty}</span>
            <span style="font-size:0.7rem; opacity:0.6">${o.status} @ ${o.created_at}</span>
        </div>
    `).join('');
}

async function toggle() {
    try {
        const res = await fetch('/api/toggle', { method: 'POST' });
        if (!res.ok) throw new Error();
        const d = await res.json();
        state.auto = d.state;
        refresh();
    } catch (e) { console.error("Toggle failed", e); }
}

refresh();
setInterval(refresh, 5000);
lucide.createIcons();

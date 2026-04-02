// Unified Dashboard JS
const state = { auto: false, busy: false };

async function refresh() {
    if (state.busy) return;
    try {
        const res = await fetch('/api/summary');
        if (!res.ok) throw new Error();
        const data = await res.json();
        
        // Update State
        state.auto = data.auto;
        updateUI(data);
    } catch (e) {
        console.warn("Poll failed", e);
    }
}

function updateUI(data) {
    // Mode & Status
    const statusEl = document.getElementById('statusMode');
    statusEl.innerHTML = `<span class="status-dot"></span>${data.mode} — ${data.auto ? 'AUTORUN ON' : 'STANDBY'}`;
    statusEl.parentElement.className = `glass ${data.auto ? 'active' : ''}`;
    
    // Toggle Button
    const btn = document.getElementById('toggleBtn');
    btn.className = `btn ${data.auto ? 'btn-on' : 'btn-off'}`;
    btn.innerHTML = data.auto ? '<i data-lucide="power"></i> STOP BOT' : '<i data-lucide="play"></i> START BOT';
    
    // Stats
    document.getElementById('equity').innerText = `$${data.equity.toLocaleString()}`;
    const plEl = document.getElementById('plTotal');
    plEl.innerText = `${data.pl >= 0 ? '+' : ''}$${data.pl.toFixed(2)}`;
    plEl.className = data.pl >= 0 ? 'up' : 'down';
    
    // Watchlist
    const watchEl = document.getElementById('watch');
    watchEl.innerHTML = Object.entries(data.summary).map(([s, d]) => `
        <div class="sym-card ${d.dir.toLowerCase()}">
            <b style="font-size:0.9rem">${s}</b>
            <span style="font-size:0.6rem;opacity:0.7">${d.time}</span>
            <span style="font-weight:700; font-size:0.7rem">${d.dir}</span>
        </div>
    `).join('');
    
    // Positions
    const posTable = document.getElementById('posTable');
    if (data.pos.length > 0) {
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
    } else {
        posTable.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--dim); border:none; padding:2rem 0">No open positions</td></tr>`;
    }

    // History
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

    lucide.createIcons();
}

async function toggle() {
    try {
        const res = await fetch('/api/toggle', { method: 'POST' });
        const d = await res.json();
        state.auto = d.state;
        refresh();
    } catch (e) { alert("Action failed"); }
}

// Initial Sync
refresh();
setInterval(refresh, 5000); // Efficient 5s polling
lucide.createIcons();

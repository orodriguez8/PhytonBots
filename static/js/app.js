// State
let autoTradingActive = false;

// Initialize Lucide icons
lucide.createIcons();

// API Calls
async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        autoTradingActive = data.auto_trading;
        
        document.getElementById('modeText').textContent = data.modo;
        updateButtonsUI();
        
        // Update watchlist/summary status
        const summary = document.getElementById('watchlistStatus');
        if (data.last_run_log) {
            summary.innerHTML = Object.entries(data.last_run_log).map(([symbol, log]) => `
                <div class="symbol-chip ${log.dir.toLowerCase()}">
                    <span>${symbol}</span>
                    <span class="small-dir">${log.dir}</span>
                </div>
            `).join('');
        }
    } catch (e) { console.error("Error status", e); }
}

async function fetchAccount() {
    try {
        const res = await fetch('/api/account');
        const data = await res.json();
        
        document.getElementById('totalEquity').textContent = `$${data.equity.toLocaleString()}`;
        const plEl = document.getElementById('totalPL');
        plEl.textContent = `${data.pl_total >= 0 ? '+' : ''}$${data.pl_total.toFixed(2)}`;
        plEl.className = `sub ${data.pl_total >= 0 ? 'up' : 'down'}`;

        // Update positions
        const table = document.getElementById('positionsTable');
        if (data.posiciones && data.posiciones.length > 0) {
            table.innerHTML = data.posiciones.map(p => `
                <tr>
                    <td style="font-weight: 600;">${p.symbol}</td>
                    <td>${p.qty}</td>
                    <td>$${p.entry_price}</td>
                    <td>$${p.current_price}</td>
                    <td class="${p.pl >= 0 ? 'up' : 'down'}" style="font-weight: 600;">
                        ${p.pl >= 0 ? '+' : ''}$${p.pl.toFixed(2)} (${p.pl_pct >= 0 ? '+' : ''}${p.pl_pct}%)
                    </td>
                </tr>
            `).join('');
        } else {
            table.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); border: none;">No hay posiciones abiertas</td></tr>`;
        }

        // History
        const histList = document.getElementById('historyList');
        if (data.history && data.history.length > 0) {
            histList.innerHTML = data.history.map(h => `
                <li class="history-item">
                    <div class="hist-info">
                        <span class="hist-type ${h.type.toLowerCase() === 'long' ? 'up' : h.type.toLowerCase() === 'short' ? 'down' : ''}">
                            ${h.symbol} ${h.type}
                        </span>
                        <span class="hist-time">${h.time} — $${h.price}</span>
                    </div>
                    <span style="font-size: 0.75rem; color: var(--text-dim); text-align: right; max-width: 150px;">
                        ${h.reason.split(' ').slice(0,2).join(' ')}...
                    </span>
                </li>
            `).join('');
        } else {
            histList.innerHTML = `<li style="text-align: center; padding: 2rem 0; color: var(--text-dim); font-size: 0.8125rem;">Sin actividad</li>`;
        }

    } catch (e) { console.error("Error account", e); }
}

async function toggleAutomation() {
    const btn = document.getElementById('toggleBtn');
    btn.disabled = true;
    
    try {
        const res = await fetch('/api/toggle-auto', { method: 'POST' });
        const data = await res.json();
        autoTradingActive = data.auto_trading;
        updateButtonsUI();
    } catch (e) {
        alert("Error al cambiar estado: " + e.message);
    } finally {
        btn.disabled = false;
    }
}

function updateButtonsUI() {
    const btn = document.getElementById('toggleBtn');
    const statusDot = document.getElementById('statusDot');
    const autoLabel = document.getElementById('autoTradingStatus');

    if (autoTradingActive) {
        btn.innerHTML = '<i data-lucide="power"></i> Detener Automatización';
        btn.className = 'btn btn-danger';
        statusDot.className = 'dot active';
        autoLabel.textContent = 'AUTO: ON';
        autoLabel.className = 'auto-on';
    } else {
        btn.innerHTML = '<i data-lucide="play"></i> Iniciar Automatización';
        btn.className = 'btn btn-success';
        statusDot.className = 'dot';
        autoLabel.textContent = 'AUTO: OFF';
        autoLabel.className = '';
    }
    lucide.createIcons();
}

// Initial Load
fetchStatus();
fetchAccount();

// Polling
setInterval(fetchStatus, 5000); // Check status every 5s
setInterval(fetchAccount, 10000); // Check account every 10s

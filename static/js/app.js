// Initialize Lucide icons
lucide.createIcons();

// API Calls
async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('modeText').textContent = data.modo;
        document.getElementById('symbolText').textContent = data.symbol;
        document.getElementById('autoTradingStatus').textContent = `AUTO: ${data.auto_trading ? 'ON' : 'OFF'}`;
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
    } catch (e) { console.error("Error account", e); }
}

async function runAnalysis() {
    const btn = document.getElementById('runBtn');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i data-lucide="loader-2"></i> Analizando...';
    btn.disabled = true;
    lucide.createIcons();

    try {
        const res = await fetch('/api/run');
        const data = await res.json();

        if (data.error) throw new Error(data.error);

        // Update UI
        document.getElementById('lastPrice').textContent = `$${data.last_price.toLocaleString()}`;
        
        const badge = document.getElementById('decisionBadge');
        badge.textContent = data.direction;
        badge.className = `decision-badge bg-${data.direction.toLowerCase()}`;
        
        document.getElementById('decisionReason').textContent = data.reason;

        // Confluences
        const c = data.confluences;
        document.getElementById('longCount').textContent = `${c.total_long}/${c.min}`;
        document.getElementById('longBar').style.width = `${Math.min(100, (c.total_long / c.min) * 100)}%`;
        
        document.getElementById('shortCount').textContent = `${c.total_short}/${c.min}`;
        document.getElementById('shortBar').style.width = `${Math.min(100, (c.total_short / c.min) * 100)}%`;

        // History
        const histList = document.getElementById('historyList');
        if (data.history && data.history.length > 0) {
            histList.innerHTML = data.history.map(h => `
                <li class="history-item">
                    <div class="hist-info">
                        <span class="hist-type ${h.type.toLowerCase() === 'long' ? 'up' : h.type.toLowerCase() === 'short' ? 'down' : ''}">
                            ${h.type === 'NEUTRAL' ? 'ANALISIS' : h.type}
                        </span>
                        <span class="hist-time">${h.time} — $${h.price}</span>
                    </div>
                    <span style="font-size: 0.75rem; color: var(--text-dim); text-align: right; max-width: 150px;">
                        ${h.reason.split(' ')[0]}...
                    </span>
                </li>
            `).join('');
        }

        // Refresh account to see if position changed (if auto-trading was on)
        fetchAccount();

    } catch (e) {
        alert("Error ejecutando el bot: " + e.message);
    } finally {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
        lucide.createIcons();
    }
}

// Initial Load
fetchStatus();
fetchAccount();
// Refresh account every 30s
setInterval(fetchAccount, 30000);

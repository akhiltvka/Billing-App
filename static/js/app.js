/**
 * app.js — Main SPA Controller, Router, Global Utilities & Dashboard
 * Meat Products of India — Billing & Inventory Management App
 */

// ─── Global State ────────────────────────────────────────────────────────────
const App = {
  currentPage: null,
  settings: {},
  currency: '₹',

  // ── Navigation ──────────────────────────────────────────────────────────
  navigate(page) {
    // Role gate — silently redirect to dashboard if not permitted
    if (Auth.currentUser && !Auth.can(page)) {
      const role = Auth.currentUser.role;
      const fallback = (Auth.ROLE_PAGES[role] || ['billing'])[0];
      if (page !== fallback) { this.navigate(fallback); return; }
      return;
    }
    // Update sidebar active state
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.page === page);
    });

    // Update topbar
    const titles = {
      dashboard:        ['📊 Dashboard',       'Overview of today\'s business'],
      billing:          ['🧾 New Bill / POS',  'Create a new sale invoice'],
      bills:            ['📋 Bill History',    'View and manage all bills'],
      inventory:        ['📦 Products',        'Manage product catalog and stock'],
      'stock-in':       ['⬆️ Stock In',        'Record incoming stock from suppliers'],
      'purchase-orders':['🛒 Purchase Orders', 'Manage supplier purchase orders'],
      categories:       ['🏷️ Categories',      'Manage product categories'],
      customers:        ['👥 Customers',       'Manage customer database'],
      suppliers:        ['🚚 Suppliers',       'Manage supplier database'],
      expenses:         ['💸 Income & Expenses', 'Record and track expenses & other income'],
      accounts:         ['📒 Chart of Accounts', 'Manage double-entry ledger accounts, assets, liabilities, and opening balances'],
      reports:          ['📈 Reports',         'Analytics, GST & sales reports'],
      settings:         ['⚙️ Settings',        'Configure shop details and preferences'],
      users:            ['👥 User Management', 'Manage staff accounts and access control'],
    };

    const [title, subtitle] = titles[page] || ['', ''];
    document.getElementById('topbar-title').textContent = title;
    document.getElementById('topbar-subtitle').textContent = subtitle;

    this.currentPage = page;
    const content = document.getElementById('page-content');
    content.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

    // Route to module
    const routes = {
      dashboard:         () => this.renderDashboard(),
      billing:           () => Billing.render(),
      bills:             () => Billing.renderHistory(),
      inventory:         () => Inventory.render(),
      'stock-in':        () => Inventory.renderStockIn(),
      'purchase-orders': () => Inventory.renderPurchaseOrders(),
      categories:        () => Inventory.renderCategories(),
      customers:         () => Customers.render(),
      suppliers:         () => Suppliers.render(),
      expenses:          () => this.renderExpenses(),
      accounts:          () => Accounts.render(),
      reports:           () => Reports.render(),
      settings:          () => Settings.render(),
      users:             () => UsersAdmin.render(),
    };

    const fn = routes[page];
    if (fn) {
      try { fn(); }
      catch (e) { console.error(e); App.toast('Page load error: ' + e.message, 'error'); }
    }
  },

  // ── API Helper ──────────────────────────────────────────────────────────
  async api(path, method = 'GET', body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch('/api' + path, opts);
    if (res.status === 401) {
      Auth.currentUser = null;
      const overlay = document.getElementById('login-overlay');
      if (overlay && overlay.style.display === 'none') {
        overlay.style.display = 'flex';
        overlay.classList.remove('hidden');
        setTimeout(() => document.getElementById('login-username')?.focus(), 200);
        App.toast('Session expired. Please sign in again.', 'warning');
      }
      throw new Error('Authentication required');
    }
    if (res.status === 403) {
      throw new Error('You do not have permission to perform this action.');
    }
    const json = await res.json();
    if (json.status === 'error') throw new Error(json.message);
    return json.data;
  },

  // ── Toast Notifications ─────────────────────────────────────────────────
  toast(message, type = 'info') {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span class="toast-icon">${icons[type]}</span><span class="toast-msg">${message}</span>`;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), 3100);
  },

  // ── Modal ───────────────────────────────────────────────────────────────
  showModal(html, id = 'main-modal') {
    const existing = document.getElementById(id);
    if (existing) existing.remove();
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = id;
    overlay.innerHTML = html;
    overlay.addEventListener('click', e => { if (e.target === overlay) App.closeModal(id); });
    document.getElementById('modals-container').appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('active'));
  },

  closeModal(id = 'main-modal') {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('active');
    setTimeout(() => el.remove(), 300);
  },

  // ── Confirm Dialog ──────────────────────────────────────────────────────
  confirm(message, title = 'Confirm', onConfirm = null) {
    App.showModal(`
      <div class="modal confirm-dialog">
        <div class="confirm-icon">⚠️</div>
        <h3>${title}</h3>
        <p>${message}</p>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-danger" id="confirm-ok-btn">Confirm</button>
        </div>
      </div>
    `);
    document.getElementById('confirm-ok-btn').onclick = () => {
      App.closeModal();
      if (onConfirm) onConfirm();
    };
  },

  // ── GST Helper ──────────────────────────────────────────────────────────
  isGstEnabled() {
    return this.settings.gst_enabled !== 'false' && this.settings.gst_enabled !== false;
  },

  // ── Formatting ──────────────────────────────────────────────────────────
  fmt(amount, decimals = 2) {
    const sym = this.currency || '₹';
    return `${sym}${parseFloat(amount || 0).toFixed(decimals)}`;
  },

  fmtNum(n, decimals = 3) {
    return parseFloat(n || 0).toFixed(decimals);
  },

  fmtDate(dt) {
    if (!dt) return '—';
    const d = new Date(dt);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  },

  fmtDateTime(dt) {
    if (!dt) return '—';
    const d = new Date(dt);
    return d.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  },

  fmtTime(dt) {
    if (!dt) return '';
    return new Date(dt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  },

  stockBadge(current, min) {
    if (current <= 0)           return '<span class="badge badge-danger">Out of Stock</span>';
    if (current <= min)         return '<span class="badge badge-warning">Low Stock</span>';
    return '<span class="badge badge-success">In Stock</span>';
  },

  // ── Clock ───────────────────────────────────────────────────────────────
  startClock() {
    const update = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const dateStr = now.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
      const clockEl = document.getElementById('sidebar-clock');
      const dateEl = document.getElementById('topbar-date');
      if (clockEl) clockEl.textContent = timeStr;
      if (dateEl) dateEl.textContent = dateStr;
    };
    update();
    setInterval(update, 1000);
  },

  // ─────────────────────────────────────────────────────────────────────────
  // DASHBOARD
  // ─────────────────────────────────────────────────────────────────────────
  async renderDashboard() {
    try {
      const data = await App.api('/reports/dashboard');
      const lowStockProducts = data.low_stock_count > 0
        ? `<span class="nav-badge">${data.low_stock_count}</span>` : '';

      document.getElementById('page-content').innerHTML = `
        <div class="page-enter">
          <!-- Stat Cards -->
          <div class="stat-grid">
            <div class="stat-card">
              <div class="stat-icon">💰</div>
              <div class="stat-label">Today's Sales</div>
              <div class="stat-value">${App.fmt(data.today_sales)}</div>
              <div class="stat-sub">${data.today_bills} transaction${data.today_bills !== 1 ? 's' : ''}</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">📅</div>
              <div class="stat-label">Month Sales</div>
              <div class="stat-value">${App.fmt(data.month_sales)}</div>
              <div class="stat-sub">Current month</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">💸</div>
              <div class="stat-label">Today's Expenses</div>
              <div class="stat-value stat-negative">${App.fmt(data.today_expenses)}</div>
              <div class="stat-sub">Recorded today</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">📦</div>
              <div class="stat-label">Products</div>
              <div class="stat-value">${data.total_products}</div>
              <div class="stat-sub ${data.low_stock_count > 0 ? 'stat-warning' : ''}">
                ${data.low_stock_count > 0 ? `⚠️ ${data.low_stock_count} low stock` : '✅ All stocked'}
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">👥</div>
              <div class="stat-label">Customers</div>
              <div class="stat-value">${data.total_customers}</div>
              <div class="stat-sub">Registered</div>
            </div>
          </div>

          <div class="grid-2" style="gap:20px">
            <!-- Sales Chart -->
            <div class="card">
              <div class="card-title"><span class="card-title-icon">📊</span> Last 7 Days Sales</div>
              <div id="sales-chart"></div>
            </div>

            <!-- Top Products -->
            <div class="card">
              <div class="card-title"><span class="card-title-icon">🏆</span> Top Products This Month</div>
              ${data.top_products.length === 0
                ? '<div class="empty-state"><div class="empty-state-icon">🥩</div><p>No sales yet this month</p></div>'
                : `<div class="table-wrap">
                    <table>
                      <thead><tr>
                        <th>#</th><th>Product</th>
                        <th class="text-right">Qty Sold</th>
                        <th class="text-right">Revenue</th>
                      </tr></thead>
                      <tbody>
                        ${data.top_products.map((p, i) => `
                          <tr>
                            <td><span class="badge badge-gold">${i + 1}</span></td>
                            <td class="font-semibold">${p.product_name}</td>
                            <td class="td-number">${App.fmtNum(p.qty)}</td>
                            <td class="td-number text-gold">${App.fmt(p.revenue)}</td>
                          </tr>`).join('')}
                      </tbody>
                    </table>
                  </div>`
              }
            </div>
          </div>

          <div class="gold-divider"></div>

          <div class="grid-2" style="gap:20px;margin-top:0">
            <!-- Payment Modes -->
            <div class="card">
              <div class="card-title"><span class="card-title-icon">💳</span> Today's Payment Modes</div>
              ${data.payment_breakdown.length === 0
                ? '<div class="empty-state"><div class="empty-state-icon">💳</div><p>No transactions today</p></div>'
                : `<div style="display:flex;flex-direction:column;gap:12px">
                    ${data.payment_breakdown.map(p => {
                      const icon = {cash:'💵', upi:'📱', card:'💳'}[p.payment_mode] || '💰';
                      return `<div style="display:flex;align-items:center;justify-content:space-between;padding:12px;background:var(--bg-input);border-radius:var(--r-md);border:1px solid var(--border)">
                        <div style="display:flex;align-items:center;gap:10px">
                          <span style="font-size:22px">${icon}</span>
                          <div>
                            <div class="font-semibold" style="text-transform:capitalize">${p.payment_mode}</div>
                            <div class="text-muted text-sm">${p.count} transaction${p.count !== 1 ? 's' : ''}</div>
                          </div>
                        </div>
                        <div class="font-bold text-gold" style="font-size:16px">${App.fmt(p.total)}</div>
                      </div>`;
                    }).join('')}
                  </div>`
              }
            </div>

            <!-- Quick Actions -->
            <div class="card">
              <div class="card-title"><span class="card-title-icon">⚡</span> Quick Actions</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <button class="btn btn-primary btn-lg" onclick="App.navigate('billing')" style="flex-direction:column;height:70px;gap:4px">
                  <span style="font-size:22px">🧾</span><span>New Bill</span>
                </button>
                <button class="btn btn-secondary btn-lg" onclick="App.navigate('stock-in')" style="flex-direction:column;height:70px;gap:4px">
                  <span style="font-size:22px">⬆️</span><span>Stock In</span>
                </button>
                <button class="btn btn-secondary btn-lg" onclick="App.navigate('expenses')" style="flex-direction:column;height:70px;gap:4px">
                  <span style="font-size:22px">💸</span><span>Add Expense</span>
                </button>
                <button class="btn btn-secondary btn-lg" onclick="App.navigate('reports')" style="flex-direction:column;height:70px;gap:4px">
                  <span style="font-size:22px">📈</span><span>Reports</span>
                </button>
              </div>

              ${data.low_stock_count > 0 ? `
                <div style="margin-top:16px;padding:12px 14px;background:var(--warning-bg);border:1px solid rgba(243,156,18,0.3);border-radius:var(--r-md);display:flex;align-items:center;gap:10px;cursor:pointer" onclick="App.navigate('inventory')">
                  <span style="font-size:20px">⚠️</span>
                  <div>
                    <div class="font-semibold text-warning">${data.low_stock_count} product${data.low_stock_count > 1 ? 's' : ''} low on stock</div>
                    <div class="text-muted text-sm">Click to view inventory</div>
                  </div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>
      `;

      // Render sales chart
      App.renderBarChart('sales-chart', data.daily_sales);

    } catch (e) {
      document.getElementById('page-content').innerHTML = `
        <div class="empty-state"><div class="empty-state-icon">⚠️</div>
        <h3>Failed to load dashboard</h3><p>${e.message}</p></div>`;
    }
  },

  renderBarChart(containerId, dailyData) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!dailyData || dailyData.length === 0) {
      container.innerHTML = '<div class="empty-state" style="padding:30px"><div class="empty-state-icon">📊</div><p>No data yet</p></div>';
      return;
    }
    const maxVal = Math.max(...dailyData.map(d => d.total), 1);
    const bars = dailyData.map(d => {
      const pct = (d.total / maxVal) * 150;
      const day = new Date(d.day).toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit' });
      return `<div class="bar-item">
        <div class="bar" style="height:${pct}px">
          <div class="bar-tooltip">${App.fmt(d.total)}<br>${d.bills} bills</div>
        </div>
        <span class="bar-label">${day}</span>
      </div>`;
    }).join('');
    container.innerHTML = `<div class="bar-chart">${bars}</div>`;
  },

  // ─────────────────────────────────────────────────────────────────────────
  // EXPENSES PAGE
  // ─────────────────────────────────────────────────────────────────────────
  // ── Income & Expenses ───────────────────────────────────────────────────
  async renderExpenses() {
    const content = document.getElementById('page-content');
    const today = new Date().toISOString().split('T')[0];
    try {
      const items = await App.api(`/expenses?from=${today}&to=${today}`);
      const expenses = items.filter(i => (i.entry_type || 'expense') === 'expense');
      const incomes  = items.filter(i => i.entry_type === 'income');

      const expTotal = expenses.reduce((s, e) => s + floatVal(e.amount), 0);
      const incTotal = incomes.reduce((s, e) => s + floatVal(e.amount), 0);
      const netTotal = incTotal - expTotal;

      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>💸 Income &amp; Expenses</h1>
              <p>Record and track daily operational expenses &amp; non-sales income</p>
            </div>
            <div style="display:flex;gap:10px">
              <button class="btn btn-primary" onclick="App.showAddExpenseModal('expense')">➕ Add Expense</button>
              <button class="btn btn-success" onclick="App.showAddExpenseModal('income')">💰 Add Other Income</button>
            </div>
          </div>

          <div class="stat-grid" style="margin-bottom:20px">
            <div class="stat-card">
              <div class="stat-icon">💸</div>
              <div class="stat-label">Today's Expenses</div>
              <div class="stat-value stat-negative">${App.fmt(expTotal)}</div>
              <div class="stat-sub">${expenses.length} entries</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">💰</div>
              <div class="stat-label">Today's Other Income</div>
              <div class="stat-value text-success">${App.fmt(incTotal)}</div>
              <div class="stat-sub">${incomes.length} entries</div>
            </div>
            <div class="stat-card">
              <div class="stat-icon">⚖️</div>
              <div class="stat-label">Net Daily Cashflow</div>
              <div class="stat-value ${netTotal >= 0 ? 'text-success' : 'text-danger'}">${App.fmt(netTotal)}</div>
              <div class="stat-sub">Income - Expenses</div>
            </div>
          </div>

          <div class="card">
            <div class="card-title"><span class="card-title-icon">📋</span> Today's Income &amp; Expense Register (${items.length} entries)</div>
            ${items.length === 0
              ? '<div class="empty-state"><div class="empty-state-icon">💸</div><h3>No transactions recorded today</h3></div>'
              : `<div class="table-wrap">
                  <table>
                    <thead><tr>
                      <th>Type</th><th>Category</th><th>Description</th>
                      <th>Payment Mode</th><th class="text-right">Amount (₹)</th><th>Date</th><th style="text-align:right">Action</th>
                    </tr></thead>
                    <tbody id="expense-tbody">
                      ${items.map(e => {
                        const isInc = e.entry_type === 'income';
                        return `
                        <tr>
                          <td><span class="badge badge-${isInc ? 'success' : 'danger'}">${isInc ? '💰 Income' : '💸 Expense'}</span></td>
                          <td class="font-bold">${e.category}</td>
                          <td class="td-muted">${e.description || '—'}</td>
                          <td><span class="badge badge-info">${(e.payment_mode || 'cash').toUpperCase()}</span></td>
                          <td class="td-number font-bold ${isInc ? 'text-success' : 'text-danger'}">${isInc ? '+' : '-'}${App.fmt(e.amount)}</td>
                          <td class="td-muted">${App.fmtDate(e.date)}</td>
                          <td style="text-align:right">
                            <button class="btn btn-danger btn-sm btn-icon" onclick="App.deleteExpense(${e.id})" title="Delete entry">🗑️</button>
                          </td>
                        </tr>`;
                      }).join('')}
                    </tbody>
                  </table>
                </div>`
            }
          </div>
        </div>`;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  showAddExpenseModal(entryType = 'expense') {
    const isInc = entryType === 'income';
    const expenseCats = ['Rent', 'Electricity', 'Water', 'Labour / Salary', 'Freight / Transport', 'Packaging', 'Cleaning', 'Maintenance', 'Miscellaneous Expense'];
    const incomeCats  = ['Rental Income', 'Scrap Sales', 'Delivery Charges Income', 'Interest Received', 'Commission Income', 'Subsidy / Cash Back', 'Miscellaneous Income'];

    const categories = isInc ? incomeCats : expenseCats;

    App.showModal(`
      <div class="modal-card" style="max-width:500px">
        <div class="modal-header">
          <h3>${isInc ? '💰 Add Other Income (Non-Sales)' : '💸 Add Expense'}</h3>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <input type="hidden" id="exp-type" value="${isInc ? 'income' : 'expense'}">
          <div class="form-group mb-16">
            <label class="form-label required">Category</label>
            <select class="form-control" id="exp-category">
              ${categories.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
          </div>
          <div class="form-group mb-16">
            <label class="form-label">Description / Particulars</label>
            <input class="form-control" id="exp-desc" placeholder="${isInc ? 'e.g. Scrap boxes sale receipt' : 'e.g. Monthly shop electricity bill'}">
          </div>
          <div class="grid-2 mb-16">
            <div class="form-group">
              <label class="form-label required">Amount (₹)</label>
              <input class="form-control" id="exp-amount" type="number" step="0.01" min="0" placeholder="0.00">
            </div>
            <div class="form-group">
              <label class="form-label required">Payment Mode</label>
              <select class="form-control" id="exp-pmode">
                <option value="cash" selected>Cash</option>
                <option value="upi">UPI / GPay / PhonePe</option>
                <option value="bank_transfer">Bank Transfer / NEFT</option>
                <option value="card">Debit / Credit Card</option>
              </select>
            </div>
          </div>
          <div class="form-group mb-16">
            <label class="form-label">Date</label>
            <input class="form-control" id="exp-date" type="date" value="${new Date().toISOString().split('T')[0]}">
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-${isInc ? 'success' : 'primary'}" onclick="App.saveExpense()">${isInc ? 'Save Income' : 'Save Expense'}</button>
        </div>
      </div>`);
  },

  async saveExpense() {
    const amount = parseFloat(document.getElementById('exp-amount').value);
    if (!amount || amount <= 0) { App.toast('Enter a valid amount', 'error'); return; }
    const entryType = document.getElementById('exp-type')?.value || 'expense';

    try {
      await App.api('/expenses', 'POST', {
        entry_type: entryType,
        category: document.getElementById('exp-category').value,
        description: document.getElementById('exp-desc').value,
        amount,
        payment_mode: document.getElementById('exp-pmode').value,
        date: document.getElementById('exp-date').value,
      });
      App.closeModal();
      App.toast(`${entryType === 'income' ? 'Income' : 'Expense'} entry recorded successfully`, 'success');
      App.renderExpenses();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async deleteExpense(id) {
    App.confirm('Delete this transaction entry?', 'Delete Entry', async () => {
      await App.api(`/expenses/${id}`, 'DELETE');
      App.toast('Deleted', 'success');
      App.renderExpenses();
    });
  },

  applySettings(settings) {
    if (!settings) return;
    this.settings = { ...this.settings, ...settings };
    this.currency = this.settings.currency_symbol || '₹';
    const shopName = this.settings.shop_name || 'Meat Products of India';
    const shopTagline = this.settings.shop_tagline || 'Fresh. Pure. Delicious.';

    // 1. Update Login Brand Name & Tagline
    const loginBrand = document.getElementById('login-brand-name');
    if (loginBrand) {
      const words = shopName.trim().split(/\s+/);
      if (words.length > 2) {
        const main = words.slice(0, -2).join(' ') || words[0];
        const rest = words.slice(-2).join(' ');
        loginBrand.innerHTML = `${main}<br><span>${rest}</span>`;
      } else if (words.length === 2) {
        loginBrand.innerHTML = `${words[0]}<br><span>${words[1]}</span>`;
      } else {
        loginBrand.textContent = shopName;
      }
    }

    const loginTagline = document.getElementById('login-brand-tagline');
    if (loginTagline) loginTagline.textContent = shopTagline;

    const loginSubtitle = document.getElementById('login-shop-subtitle');
    if (loginSubtitle) loginSubtitle.textContent = `Sign in to ${shopName}`;

    // 2. Update Sidebar Header & Footer Shop Names
    const sbName = document.getElementById('sidebar-shop-name');
    if (sbName) sbName.textContent = shopName;

    const sbFooter = document.getElementById('sidebar-footer-shop-name');
    if (sbFooter) sbFooter.textContent = shopName;

    // 3. Document Title & in-app titlebar
    document.title = `${shopName} — Billing & Inventory`;
    const winTitle = document.getElementById('win-titlebar-title');
    if (winTitle) winTitle.textContent = `${shopName} — Billing & Inventory`;
  },

  // ── Window Control Actions (Desktop App Mode) ────────────────────────────
  // Called by the Minimize / Maximize / Close buttons in the custom title bar.
  // Always shows a confirmation dialog first.
  windowAction(action) {
    const shopName = this.settings.shop_name || 'Meat Products of India';

    const configs = {
      minimize: {
        title:   '🗕  Minimize Application',
        message: `Minimize the ${shopName} application window?\n\nThe app will continue running in the background.`,
        btnText: 'Minimize',
        btnCls:  'btn-secondary',
      },
      maximize: {
        title:   '🗖  Maximize / Restore Window',
        message: `Maximize or restore the ${shopName} application window?`,
        btnText: 'Maximize / Restore',
        btnCls:  'btn-secondary',
      },
      close: {
        title:   '✕  Exit Application',
        message: `Exit ${shopName}?\n\nAll unsaved changes will be lost.`,
        btnText: 'Exit Application',
        btnCls:  'btn-danger',
      },
    };

    const cfg = configs[action];
    if (!cfg) return;

    // Show confirmation modal
    const id = 'win-action-modal-' + Date.now();
    const overlay = document.createElement('div');
    overlay.id = id;
    overlay.style.cssText = `
      position: fixed; inset: 0; z-index: 999999;
      background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
    `;
    overlay.innerHTML = `
      <div style="
        background: var(--bg-card);
        border: 1px solid var(--border-strong);
        border-radius: 12px;
        box-shadow: 0 24px 64px rgba(0,0,0,0.5);
        padding: 28px 32px;
        min-width: 340px;
        max-width: 420px;
        font-family: 'Inter', 'Segoe UI', sans-serif;
      ">
        <div style="font-size:18px;font-weight:700;color:var(--text-primary);margin-bottom:14px;">${cfg.title}</div>
        <div style="font-size:14px;color:var(--text-secondary);white-space:pre-line;line-height:1.6;margin-bottom:24px;">${cfg.message}</div>
        <div style="display:flex;gap:10px;justify-content:flex-end;">
          <button class="btn btn-ghost" onclick="document.getElementById('${id}').remove()" style="min-width:90px;">Cancel</button>
          <button class="btn ${cfg.btnCls}" id="${id}-confirm" style="min-width:130px;">${cfg.btnText}</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    // Close on backdrop click
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

    // Confirm button handler
    document.getElementById(`${id}-confirm`).addEventListener('click', () => {
      overlay.remove();
      if (action === 'minimize' && window.pywebview) {
        window.pywebview.api.minimize_window();
      } else if (action === 'maximize' && window.pywebview) {
        window.pywebview.api.toggle_maximize();
        // Toggle the maximize ↔ restore icon
        const btn = document.getElementById('btn-win-maximize');
        if (btn) {
          const isMax = btn.dataset.maximized === 'true';
          btn.dataset.maximized = isMax ? 'false' : 'true';
          btn.innerHTML        = isMax ? '&#x2610;' : '&#x2750;';   // ☐ restore / ❐ maximized
          btn.title            = isMax ? 'Maximize' : 'Restore';
        }
      } else if (action === 'close') {
        if (window.pywebview) {
          window.pywebview.api.close_window();
        } else {
          window.close();
        }
      }
    });
  },

  // ── Post-Login Initialization (called by Auth after login) ────────────────
  async postAuthInit(user) {
    try {
      const settings = await App.api('/settings');
      this.applySettings(settings);
    } catch (e) {
      console.warn('Could not load settings:', e.message);
    }
    // Navigate to first allowed page for this role
    const firstPage = (user.pages || ['billing'])[0];
    this.navigate(firstPage);
    this.checkLicenseState();
  },

  // ── License & Subscription Management ────────────────────────────────────
  licenseInfo: null,

  async checkLicenseState() {
    try {
      const res = await fetch('/api/license/status');
      const json = await res.json();
      if (json.status === 'ok' && json.data) {
        this.licenseInfo = json.data;
        this.renderLicenseBanner(json.data);
      }
    } catch(e) {
      console.warn('License status check failed:', e.message);
    }
  },

  renderLicenseBanner(info) {
    const bar = document.getElementById('license-banner-bar');
    if (!bar || !info) return;

    if (info.status === 'trial') {
      bar.innerHTML = `
        <div style="background:linear-gradient(90deg, #1E293B, #0F172A);border-bottom:1px solid #334155;color:#F1F5F9;padding:8px 16px;display:flex;align-items:center;justify-content:space-between;font-size:13px;cursor:pointer" onclick="App.showActivationModal()">
          <div>⏳ <strong>FREE TRIAL VERSION:</strong> <span class="text-gold font-bold">${info.days_left} days remaining</span> in trial period.</div>
          <div style="display:flex;gap:8px;align-items:center">
            <span style="color:var(--gold);font-weight:600">Activate 1-Year License (₹${info.price_inr})</span>
            <span class="badge badge-gold">Activate ⚡</span>
          </div>
        </div>`;
      bar.style.display = 'block';
    } else if (info.status === 'grace') {
      bar.innerHTML = `
        <div style="background:linear-gradient(90deg, #7C2D12, #991B1B);border-bottom:1px solid #B91C1C;color:#FEF2F2;padding:9px 16px;display:flex;align-items:center;justify-content:space-between;font-size:13px;cursor:pointer" onclick="App.showActivationModal()">
          <div>⚠️ <strong>SUBSCRIPTION EXPIRED:</strong> <span class="font-bold">${info.days_left} days remaining</span> in 10-day Grace Period! Activate now to avoid software lock.</div>
          <div style="display:flex;gap:8px;align-items:center">
            <span style="font-weight:700">Renew Subscription (₹${info.price_inr})</span>
            <span class="badge badge-warning">Activate Now 🔑</span>
          </div>
        </div>`;
      bar.style.display = 'block';
    } else if (info.status === 'expired') {
      bar.innerHTML = `
        <div style="background:linear-gradient(90deg, #991B1B, #450A0A);border-bottom:1px solid #EF4444;color:#FEF2F2;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;font-size:13px;cursor:pointer" onclick="App.showActivationModal()">
          <div>🔒 <strong>SOFTWARE LOCKED:</strong> Subscription &amp; Grace Period Expired. Please enter your 12-digit activation key.</div>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="badge badge-danger" style="font-size:12px;padding:4px 10px">Enter 12-Digit Key 🔑</span>
          </div>
        </div>`;
      bar.style.display = 'block';
    } else if (info.status === 'active' && info.days_left <= 30) {
      bar.innerHTML = `
        <div style="background:linear-gradient(90deg, #064E3B, #022C22);border-bottom:1px solid #059669;color:#ECFDF5;padding:8px 16px;display:flex;align-items:center;justify-content:space-between;font-size:13px;cursor:pointer" onclick="App.showActivationModal()">
          <div>🔑 <strong>SUBSCRIPTION ACTIVE:</strong> <span class="font-bold">${info.days_left} days remaining</span> until renewal (${info.expires_at}).</div>
          <div><span class="badge badge-success">Renew Key ⚡</span></div>
        </div>`;
      bar.style.display = 'block';
    } else {
      bar.innerHTML = '';
      bar.style.display = 'none';
    }
  },

  showActivationModal() {
    const info = this.licenseInfo || { machine_id: 'FETCHING...', price_inr: 5000, upi_id: 'mpi.billing@upi', upi_name: 'MPI Billing Software' };
    const upiQrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(`upi://pay?pa=${info.upi_id}&pn=${encodeURIComponent(info.upi_name)}&am=${info.price_inr}&cu=INR`)}`;

    const html = `
      <div class="modal-card" style="max-width:580px">
        <div class="modal-header">
          <h3>🔑 Software Activation &amp; Subscription Renewal</h3>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div style="background:var(--bg-input);padding:14px;border-radius:var(--r-md);border:1px solid var(--border);margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
            <div>
              <div style="font-size:12px;color:var(--text-muted)">Outlet Machine Hardware ID:</div>
              <div class="font-bold text-gold" style="font-family:monospace;font-size:15px">${info.machine_id}</div>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText('${info.machine_id}');App.toast('Machine ID copied','info')">📋 Copy ID</button>
          </div>

          <!-- Option A: Automatic Cloud Activation & UPI -->
          <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);border-radius:var(--r-md);padding:16px;margin-bottom:16px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <div style="font-size:15px;font-weight:700;color:var(--text-success)">💰 Annual Subscription: ₹${info.price_inr || 5000} / Year</div>
              <button class="btn btn-success btn-sm" onclick="App.syncCloudLicense()">⚡ Auto-Check Cloud Approval</button>
            </div>
            
            <div style="display:flex;gap:14px;align-items:center;background:var(--bg-card);padding:12px;border-radius:var(--r-md);border:1px solid var(--border);margin-bottom:12px">
              <img src="${upiQrUrl}" alt="UPI Payment QR Code" style="width:105px;height:105px;border-radius:6px;border:1px solid var(--border)">
              <div style="font-size:13px;line-height:1.5;flex:1">
                <div style="font-weight:700;color:var(--text-primary)">Pay Direct via UPI:</div>
                <div style="font-family:monospace;color:var(--gold);font-weight:700;font-size:14px;margin:2px 0">${info.upi_id || 'mpi.billing@upi'}</div>
                <div style="color:var(--text-muted);font-size:12px">After paying via UPI, developer will approve your Machine ID online for automatic activation!</div>
              </div>
            </div>

            <!-- Optional UTR Notification -->
            <div style="display:flex;gap:8px">
              <input type="text" id="utr-input" class="form-control form-control-sm" placeholder="Optional: Enter UTR / UPI Ref No..." style="font-size:12px">
              <button class="btn btn-secondary btn-sm" onclick="App.notifyPayment()" style="white-space:nowrap">📩 Notify Developer</button>
            </div>
          </div>

          <!-- Option B: Manual 12-Digit Key -->
          <div class="form-group mb-16" style="border-top:1px solid var(--border);padding-top:14px">
            <label class="form-label">Or Enter 12-Digit Alphanumeric Key (Offline/Manual):</label>
            <input type="text" id="activation-key-input" class="form-control" placeholder="e.g. A9K2-M7W3-P4X8" style="font-family:monospace;font-size:18px;letter-spacing:2px;text-transform:uppercase;text-align:center" oninput="App.formatKeyInput(this)">
          </div>

          <div id="activation-msg-box"></div>
        </div>
        <div class="modal-footer" style="justify-content:space-between">
          <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
          <button class="btn btn-primary" onclick="App.submitActivationKey()">⚡ Activate Key Manually</button>
        </div>
      </div>`;
    App.showModal(html);
  },

  async syncCloudLicense() {
    const msgBox = document.getElementById('activation-msg-box');
    if (msgBox) msgBox.innerHTML = `<div class="loading-overlay" style="padding:10px"><div class="spinner"></div> Checking online approval status on developer cloud server...</div>`;
    try {
      const res = await App.api('/license/sync-cloud', 'POST');
      App.toast(res.message || 'Cloud check finished', 'info');
      await this.checkLicenseState();
      if (this.licenseInfo && this.licenseInfo.status === 'active') {
        App.toast('🎉 Subscription approved & activated for 365 Days!', 'success');
        App.closeModal();
      } else {
        if (msgBox) msgBox.innerHTML = `<div class="badge badge-info mb-12" style="display:block;padding:10px;text-align:center">${res.message}</div>`;
      }
    } catch(e) {
      if (msgBox) msgBox.innerHTML = `<div class="badge badge-warning mb-12" style="display:block;padding:10px;text-align:center">⚠️ ${e.message}</div>`;
    }
  },

  async notifyPayment() {
    const utrEl = document.getElementById('utr-input');
    const utr = (utrEl?.value || '').trim();
    if (!utr) { App.toast('Please enter UTR or UPI Reference No', 'error'); return; }
    try {
      await App.api('/license/notify-payment', 'POST', { utr_number: utr });
      App.toast('Payment notification sent to developer portal!', 'success');
    } catch(e) {
      App.toast(e.message, 'error');
    }
  },

  formatKeyInput(el) {
    let v = el.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
    if (v.length > 12) v = v.slice(0, 12);
    let formatted = v;
    if (v.length > 8) {
      formatted = `${v.slice(0,4)}-${v.slice(4,8)}-${v.slice(8)}`;
    } else if (v.length > 4) {
      formatted = `${v.slice(0,4)}-${v.slice(4)}`;
    }
    el.value = formatted;
  },

  async submitActivationKey() {
    const el = document.getElementById('activation-key-input');
    const msgBox = document.getElementById('activation-msg-box');
    if (!el) return;

    const rawKey = el.value.trim();
    if (!rawKey) {
      if (msgBox) msgBox.innerHTML = `<div class="badge badge-danger mb-12" style="display:block;padding:8px;text-align:center">Please enter your 12-digit activation key</div>`;
      return;
    }

    if (msgBox) msgBox.innerHTML = `<div class="loading-overlay" style="padding:10px"><div class="spinner"></div> Verifying online internet connection &amp; key signature...</div>`;

    try {
      const res = await App.api('/license/activate', 'POST', { key: rawKey });
      App.toast('Subscription successfully activated!', 'success');
      App.closeModal();
      await this.checkLicenseState();
      if (this.currentPage === 'settings') {
        Settings.render();
      }
    } catch(e) {
      if (msgBox) msgBox.innerHTML = `<div class="badge badge-danger mb-12" style="display:block;padding:10px;white-space:normal;text-align:center">❌ Activation Failed: ${e.message}</div>`;
    }
  },

  // ── Initialization ─────────────────────────────────────────────────────────
  async init() {
    this.startClock();

    // ── Desktop App Mode Detection ─────────────────────────────────────────
    // pywebview injects window.pywebview when running as a desktop app.
    // We wait up to 500ms for it to appear, then decide.
    const checkDesktopMode = () => {
      if (typeof window.pywebview !== 'undefined') {
        document.body.classList.add('desktop-mode');
        const bar = document.getElementById('win-titlebar');
        if (bar) bar.style.display = 'flex';
      }
    };
    // Check immediately + after a short delay (pywebview loads async)
    checkDesktopMode();
    setTimeout(checkDesktopMode, 400);

    // Pre-fetch settings so login screen displays configured shop_name immediately
    try {
      const res = await fetch('/api/settings');
      const json = await res.json();
      if (json.status === 'ok' && json.data) {
        this.applySettings(json.data);
      }
    } catch(e) {}

    // Try to restore existing session (no page reload needed)
    const hasSession = await Auth.checkSession();
    if (!hasSession) {
      // Focus username field
      setTimeout(() => document.getElementById('login-username')?.focus(), 200);
    }
  },
};

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  App.init();
  LoginAnimations.start();
});

// ── Login Screen Animations ───────────────────────────────────────────────────
const LoginAnimations = {

  start() {
    this.startParticles();
    this.startTypewriter();
  },

  // ── Floating particle canvas ──────────────────────────────────────────────
  startParticles() {
    const canvas = document.getElementById('login-particles');
    if (!canvas) return;

    const ctx   = canvas.getContext('2d');
    let W, H, particles = [];

    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      W = canvas.width  = rect.width  || canvas.offsetWidth;
      H = canvas.height = rect.height || canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const GOLD    = 'rgba(212,175,55,';
    const CRIMSON = 'rgba(180,40,40,';

    class Particle {
      constructor() { this.reset(); }
      reset() {
        this.x    = Math.random() * W;
        this.y    = Math.random() * H;
        this.r    = 0.8 + Math.random() * 2.2;
        this.vx   = (Math.random() - 0.5) * 0.35;
        this.vy   = -0.15 - Math.random() * 0.35;
        this.life = 0;
        this.maxLife = 180 + Math.random() * 160;
        this.color   = Math.random() > 0.5 ? GOLD : CRIMSON;
      }
      update() {
        this.x += this.vx;
        this.y += this.vy;
        this.life++;
        if (this.life > this.maxLife || this.y < -10) this.reset();
      }
      draw() {
        const alpha = Math.sin((this.life / this.maxLife) * Math.PI) * 0.55;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
        ctx.fillStyle = this.color + alpha + ')';
        ctx.fill();
      }
    }

    // Spawn initial particles
    for (let i = 0; i < 55; i++) {
      const p = new Particle();
      p.life = Math.floor(Math.random() * p.maxLife); // stagger lifetimes
      particles.push(p);
    }

    const loop = () => {
      if (!document.getElementById('login-particles')) return; // stop if removed
      ctx.clearRect(0, 0, W, H);
      particles.forEach(p => { p.update(); p.draw(); });
      requestAnimationFrame(loop);
    };
    loop();
  },

  // ── Typewriter tagline ────────────────────────────────────────────────────
  startTypewriter() {
    const el = document.querySelector('#login-brand-tagline .tagline-text');
    if (!el) return;

    const phrases = [
      'Fresh. Pure. Delicious.',
      'Quality You Can Trust.',
      'Your Trusted Meat Partner.',
      'Farm Fresh. Every Day.',
    ];

    let phraseIdx = 0, charIdx = 0, deleting = false, paused = false;

    const tick = () => {
      if (paused) return;
      const phrase = phrases[phraseIdx];

      if (!deleting) {
        el.textContent = phrase.slice(0, ++charIdx);
        if (charIdx === phrase.length) {
          deleting = true;
          paused = true;
          setTimeout(() => { paused = false; tick(); }, 2600);
          return;
        }
      } else {
        el.textContent = phrase.slice(0, --charIdx);
        if (charIdx === 0) {
          deleting = false;
          phraseIdx = (phraseIdx + 1) % phrases.length;
          paused = true;
          setTimeout(() => { paused = false; tick(); }, 400);
          return;
        }
      }
      setTimeout(tick, deleting ? 45 : 75);
    };
    setTimeout(tick, 1200); // slight startup delay
  },
};

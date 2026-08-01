/**
 * reports.js — Reports & Analytics Module
 * Meat Products of India — Billing & Inventory Management App
 */

const Reports = {

  async render() {
    const content = document.getElementById('page-content');
    const today = new Date().toISOString().split('T')[0];
    const monthStart = today.slice(0, 8) + '01';

    content.innerHTML = `
      <div class="page-enter">
        <div class="page-header">
          <div class="page-header-left">
            <h1>📈 Reports &amp; Financial Statements</h1>
            <p>Sales, GST, Financial Statements (P&amp;L, Balance Sheet, Trial Balance), Stock, Assets &amp; Yield Insights</p>
          </div>
        </div>

        <div class="tabs mb-20" style="overflow-x:auto;flex-wrap:nowrap">
          <button class="tab-btn active" id="tab-sales" onclick="Reports.showTab('sales')">📊 Sales Report</button>
          <button class="tab-btn" id="tab-financial" onclick="Reports.showTab('financial')">📑 Financial Statements</button>
          <button class="tab-btn" id="tab-accounts" onclick="Reports.showTab('accounts')">📒 Chart of Accounts &amp; Assets</button>
          <button class="tab-btn" id="tab-margins" onclick="Reports.showTab('margins')">📐 Margins &amp; Wastage</button>
          <button class="tab-btn" id="tab-yield" onclick="Reports.showTab('yield')">🥩 Butchery Yields</button>
          ${App.isGstEnabled() ? '<button class="tab-btn" id="tab-gst" onclick="Reports.showTab(\'gst\')">🏛️ GST Report</button>' : ''}
          <button class="tab-btn" id="tab-stock" onclick="Reports.showTab('stock')">📦 Stock Valuation</button>
          <button class="tab-btn" id="tab-top" onclick="Reports.showTab('top')">🏆 Top Products</button>
        </div>

        <!-- Sales Report Tab -->
        <div id="content-sales" class="tab-content active">
          <div class="filter-row">
            <input type="date" id="sr-from" class="form-control" style="width:160px" value="${monthStart}">
            <span class="text-muted">to</span>
            <input type="date" id="sr-to" class="form-control" style="width:160px" value="${today}">
            <select id="sr-ptype" class="form-control" style="width:150px">
              <option value="">All Types</option>
              <option value="perishable">Fresh Meat</option>
              <option value="general">Packaged Goods</option>
            </select>
            <button class="btn btn-primary" onclick="Reports.loadSales()">📊 Generate</button>
            <button class="btn btn-secondary" onclick="Reports.setRange('today')">Today</button>
            <button class="btn btn-secondary" onclick="Reports.setRange('week')">This Week</button>
            <button class="btn btn-secondary" onclick="Reports.setRange('month')">This Month</button>
          </div>
          <div id="sr-content"><div class="empty-state"><div class="empty-state-icon">📊</div><p>Select date range and click Generate</p></div></div>
        </div>

        <!-- Financial Statements Tab -->
        <div id="content-financial" class="tab-content">
          <div class="filter-row mb-16" style="flex-wrap:wrap">
            <label class="form-label" style="margin:0;align-self:center">Statement Type:</label>
            <select id="fin-type" class="form-control" style="width:200px" onchange="Reports.toggleFinDates()">
              <option value="pl">Profit &amp; Loss (P&amp;L)</option>
              <option value="tb">Trial Balance</option>
              <option value="bs">Balance Sheet</option>
            </select>
            <span id="fin-date-wrap" style="display:inline-flex;gap:8px;align-items:center">
              <input type="date" id="fin-from" class="form-control" style="width:150px" value="${monthStart}">
              <span class="text-muted">to</span>
              <input type="date" id="fin-to" class="form-control" style="width:150px" value="${today}">
            </span>
            <button class="btn btn-primary" onclick="Reports.loadFinancialStatement()">📑 Generate</button>
            <button class="btn btn-secondary" onclick="Reports.exportTallyXml()" title="Export Tally XML">📥 Tally XML Export</button>
            <button class="btn btn-secondary" onclick="Reports.showTab('accounts')" title="Manage Ledger Accounts &amp; Opening Balances">📒 Chart of Accounts &amp; Assets</button>
          </div>
          <div id="fin-content"><div class="empty-state"><div class="empty-state-icon">📑</div><p>Select financial statement type and click Generate</p></div></div>
        </div>

        <!-- Chart of Accounts & Asset Balances Tab -->
        <div id="content-accounts" class="tab-content">
          <div class="filter-row mb-16" style="justify-content:space-between">
            <div style="display:flex;gap:10px;align-items:center">
              <select id="acc-group-filter" class="form-control" style="width:180px" onchange="Reports.renderAccountsTable()">
                <option value="">All Groups</option>
                <option value="Asset">Assets</option>
                <option value="Liability">Liabilities</option>
                <option value="Equity">Equity</option>
                <option value="Income">Income</option>
                <option value="Expense">Expense</option>
              </select>
              <input type="text" id="acc-search" class="form-control" placeholder="Search account..." style="width:220px" oninput="Reports.renderAccountsTable()">
            </div>
            <button class="btn btn-primary" onclick="Reports.showAddAccountModal()">➕ Add Ledger Account / Asset</button>
          </div>
          <div id="accounts-content"><div class="loading-overlay"><div class="spinner"></div></div></div>
        </div>

        <!-- Margins & Wastage Tab -->
        <div id="content-margins" class="tab-content">
          <div class="filter-row mb-16">
            <input type="date" id="m-from" class="form-control" style="width:160px" value="${monthStart}">
            <span class="text-muted">to</span>
            <input type="date" id="m-to" class="form-control" style="width:160px" value="${today}">
            <button class="btn btn-primary" onclick="Reports.loadMarginsAndWastage()">📐 Generate Analysis</button>
          </div>
          <div id="margins-content"><div class="empty-state"><div class="empty-state-icon">📐</div><p>Click Generate Analysis to view gross margins and wastage reports</p></div></div>
        </div>

        <!-- Butchery Yields Tab -->
        <div id="content-yield" class="tab-content">
          <div class="filter-row mb-16">
            <input type="date" id="y-from" class="form-control" style="width:160px" value="${monthStart}">
            <span class="text-muted">to</span>
            <input type="date" id="y-to" class="form-control" style="width:160px" value="${today}">
            <label style="display:inline-flex;align-items:center;gap:6px;margin:0;font-size:13px">
              Variance Threshold (%):
              <input type="number" id="y-thresh" class="form-control" style="width:80px" value="5" step="1">
            </label>
            <button class="btn btn-primary" onclick="Reports.loadConversionYield()">🥩 Generate Yield Report</button>
          </div>
          <div id="yield-content"><div class="empty-state"><div class="empty-state-icon">🥩</div><p>Click Generate to view stock processing yields &amp; variance flags</p></div></div>
        </div>

        <!-- GST Report Tab -->
        <div id="content-gst" class="tab-content">
          <div class="filter-row">
            <input type="date" id="gr-from" class="form-control" style="width:160px" value="${monthStart}">
            <span class="text-muted">to</span>
            <input type="date" id="gr-to" class="form-control" style="width:160px" value="${today}">
            <button class="btn btn-primary" onclick="Reports.loadGST()">🏛️ Generate</button>
            <button class="btn btn-secondary" onclick="Reports.setGSTRange('month')">This Month</button>
          </div>
          <div id="gr-content"><div class="empty-state"><div class="empty-state-icon">🏛️</div><p>Select period and click Generate</p></div></div>
        </div>

        <!-- Stock Report Tab -->
        <div id="content-stock" class="tab-content">
          <button class="btn btn-primary mb-16" onclick="Reports.loadStock()">📦 Load Stock Valuation Report</button>
          <div id="stock-content"></div>
        </div>

        <!-- Top Products Tab -->
        <div id="content-top" class="tab-content">
          <div class="filter-row">
            <input type="date" id="tp-from" class="form-control" style="width:160px" value="${monthStart}">
            <span class="text-muted">to</span>
            <input type="date" id="tp-to" class="form-control" style="width:160px" value="${today}">
            <button class="btn btn-primary" onclick="Reports.loadTopProducts()">🏆 Generate</button>
          </div>
          <div id="top-content"><div class="empty-state"><div class="empty-state-icon">🏆</div><p>Click Generate to see top products</p></div></div>
        </div>
      </div>`;
  },

  showTab(tab) {
    ['sales', 'financial', 'accounts', 'margins', 'yield', 'gst', 'stock', 'top'].forEach(t => {
      document.getElementById(`tab-${t}`)?.classList.toggle('active', t === tab);
      document.getElementById(`content-${t}`)?.classList.toggle('active', t === tab);
    });
    if (tab === 'accounts') {
      this.loadAccounts();
    }
  },

  toggleFinDates() {
    const type = document.getElementById('fin-type').value;
    const dateWrap = document.getElementById('fin-date-wrap');
    if (type === 'tb' || type === 'bs') {
      const today = new Date().toISOString().split('T')[0];
      dateWrap.innerHTML = `
        <label class="form-label" style="margin:0;align-self:center">As of Date:</label>
        <input type="date" id="fin-asof" class="form-control" style="width:160px" value="${today}">
      `;
    } else {
      const today = new Date().toISOString().split('T')[0];
      const monthStart = today.slice(0, 8) + '01';
      dateWrap.innerHTML = `
        <input type="date" id="fin-from" class="form-control" style="width:150px" value="${monthStart}">
        <span class="text-muted">to</span>
        <input type="date" id="fin-to" class="form-control" style="width:150px" value="${today}">
      `;
    }
  },

  setRange(period) {
    const today = new Date();
    let from = today;
    if (period === 'week') from = new Date(today - 6 * 86400000);
    if (period === 'month') from = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById('sr-from').value = from.toISOString().split('T')[0];
    document.getElementById('sr-to').value = today.toISOString().split('T')[0];
    this.loadSales();
  },

  setGSTRange(period) {
    const today = new Date();
    const from = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById('gr-from').value = from.toISOString().split('T')[0];
    document.getElementById('gr-to').value = today.toISOString().split('T')[0];
    this.loadGST();
  },

  // ── Chart of Accounts & Assets ──────────────────────────────────────────
  allAccounts: [],

  async loadAccounts() {
    const el = document.getElementById('accounts-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
    try {
      const accounts = await App.api('/ledger/accounts');
      this.allAccounts = accounts || [];
      this.renderAccountsTable();
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  renderAccountsTable() {
    const groupFilter = document.getElementById('acc-group-filter')?.value || '';
    const searchQuery = (document.getElementById('acc-search')?.value || '').trim().toLowerCase();
    const el = document.getElementById('accounts-content');

    let filtered = this.allAccounts;
    if (groupFilter) {
      filtered = filtered.filter(a => a.account_group === groupFilter);
    }
    if (searchQuery) {
      filtered = filtered.filter(a =>
        a.name.toLowerCase().includes(searchQuery) ||
        (a.account_type || '').toLowerCase().includes(searchQuery)
      );
    }

    let totAssets = 0, totLiab = 0, totEquity = 0;
    this.allAccounts.forEach(a => {
      const op = floatVal(a.opening_balance);
      const typ = (a.opening_balance_type || 'dr').toLowerCase();
      if (a.account_group === 'Asset') {
        totAssets += (typ === 'dr' ? op : -op);
      } else if (a.account_group === 'Liability') {
        totLiab += (typ === 'cr' ? op : -op);
      } else if (a.account_group === 'Equity') {
        totEquity += (typ === 'cr' ? op : -op);
      }
    });

    el.innerHTML = `
      <div class="stat-grid mb-16">
        <div class="stat-card">
          <div class="stat-icon">🏛️</div>
          <div class="stat-label">Opening Assets Balance</div>
          <div class="stat-value text-success">${App.fmt(totAssets)}</div>
          <div class="stat-sub">Reflects in Balance Sheet</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⚖️</div>
          <div class="stat-label">Opening Liabilities</div>
          <div class="stat-value text-danger">${App.fmt(totLiab)}</div>
          <div class="stat-sub">Payable obligations</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">💎</div>
          <div class="stat-label">Opening Equity / Capital</div>
          <div class="stat-value text-info">${App.fmt(totEquity)}</div>
          <div class="stat-sub">Owner capital</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📒</div>
          <div class="stat-label">Total Ledger Accounts</div>
          <div class="stat-value text-gold">${this.allAccounts.length}</div>
          <div class="stat-sub">${filtered.length} shown</div>
        </div>
      </div>

      <div class="card">
        <div class="card-title"><span class="card-title-icon">📜</span> Ledger Chart of Accounts</div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Account Name</th>
                <th>Group</th>
                <th>Account Type</th>
                <th>Opening Balance (₹)</th>
                <th>Type</th>
                <th>Category</th>
                <th style="text-align:right">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.length === 0 ? '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No accounts found</td></tr>' :
                filtered.map(a => `
                <tr>
                  <td class="font-bold">${a.name}</td>
                  <td><span class="badge badge-${a.account_group === 'Asset' ? 'success' : a.account_group === 'Liability' ? 'danger' : a.account_group === 'Equity' ? 'info' : 'gold'}">${a.account_group}</span></td>
                  <td class="td-muted">${a.account_type || a.account_group}</td>
                  <td class="font-bold">${App.fmt(a.opening_balance || 0)}</td>
                  <td><span class="badge badge-secondary">${(a.opening_balance_type || 'dr').toUpperCase()}</span></td>
                  <td>${a.is_system ? '<span class="badge badge-info">System</span>' : '<span class="badge badge-gold">Custom Asset/Ledger</span>'}</td>
                  <td style="text-align:right">
                    <button class="btn btn-secondary btn-sm" onclick="Reports.showEditAccountModal(${a.id})" title="Edit Account / Opening Balance">✏️ Edit</button>
                    <button class="btn btn-secondary btn-sm" onclick="Reports.showAccountStatementModal(${a.id})" title="View Ledger Statement">📜 Statement</button>
                  </td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>`;
  },

  showAddAccountModal() {
    const html = `
      <div class="modal-card" style="max-width:520px">
        <div class="modal-header">
          <h3>➕ Add Ledger Account / Asset</h3>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group mb-16">
            <label class="form-label required">Account Name (e.g. Cold Storage Refrigerator, Delivery Vehicle, Capital):</label>
            <input type="text" id="new-acc-name" class="form-control" placeholder="Enter account name...">
          </div>
          <div class="grid-2 mb-16">
            <div class="form-group">
              <label class="form-label required">Account Group:</label>
              <select id="new-acc-group" class="form-control" onchange="Reports.onAddGroupChange()">
                <option value="Asset" selected>Asset (Equipment, Machinery, Cash, Bank)</option>
                <option value="Liability">Liability (Loans, Dues, Payables)</option>
                <option value="Equity">Equity (Capital, Reserves)</option>
                <option value="Income">Income (Revenue, Sales)</option>
                <option value="Expense">Expense (Direct/Indirect Expenses)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Account Sub-Type:</label>
              <input type="text" id="new-acc-type" class="form-control" placeholder="e.g. Fixed Asset, Current Asset" value="Fixed Asset">
            </div>
          </div>
          <div class="grid-2 mb-16">
            <div class="form-group">
              <label class="form-label">Opening Balance (₹):</label>
              <input type="number" id="new-acc-bal" class="form-control" placeholder="0.00" step="0.01" value="0.00">
            </div>
            <div class="form-group">
              <label class="form-label">Balance Side:</label>
              <select id="new-acc-bal-type" class="form-control">
                <option value="dr" selected>Debit (Dr) — Assets / Expenses</option>
                <option value="cr">Credit (Cr) — Liabilities / Capital / Income</option>
              </select>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Reports.saveNewAccount()">Save Account</button>
        </div>
      </div>`;
    App.showModal(html);
  },

  onAddGroupChange() {
    const grp = document.getElementById('new-acc-group')?.value;
    const typeInput = document.getElementById('new-acc-type');
    const balTypeSelect = document.getElementById('new-acc-bal-type');
    if (grp === 'Asset') {
      if (typeInput) typeInput.value = 'Fixed Asset';
      if (balTypeSelect) balTypeSelect.value = 'dr';
    } else if (grp === 'Liability') {
      if (typeInput) typeInput.value = 'Current Liability';
      if (balTypeSelect) balTypeSelect.value = 'cr';
    } else if (grp === 'Equity') {
      if (typeInput) typeInput.value = 'Capital';
      if (balTypeSelect) balTypeSelect.value = 'cr';
    } else if (grp === 'Income') {
      if (typeInput) typeInput.value = 'Operating Income';
      if (balTypeSelect) balTypeSelect.value = 'cr';
    } else if (grp === 'Expense') {
      if (typeInput) typeInput.value = 'Indirect Expense';
      if (balTypeSelect) balTypeSelect.value = 'dr';
    }
  },

  async saveNewAccount() {
    const name = (document.getElementById('new-acc-name')?.value || '').trim();
    const group = document.getElementById('new-acc-group')?.value;
    const accType = (document.getElementById('new-acc-type')?.value || group).trim();
    const bal = floatVal(document.getElementById('new-acc-bal')?.value || '0');
    const balType = document.getElementById('new-acc-bal-type')?.value || 'dr';

    if (!name) { App.toast('Account name is required', 'error'); return; }

    try {
      await App.api('/ledger/accounts', 'POST', {
        name,
        account_group: group,
        account_type: accType,
        opening_balance: bal,
        opening_balance_type: balType
      });
      App.toast(`Ledger account '${name}' created successfully`, 'success');
      App.closeModal();
      this.loadAccounts();
    } catch(e) {
      App.toast(e.message, 'error');
    }
  },

  showEditAccountModal(accId) {
    const acc = this.allAccounts.find(a => a.id === accId);
    if (!acc) return;

    const html = `
      <div class="modal-card" style="max-width:520px">
        <div class="modal-header">
          <h3>✏️ Edit Ledger Account / Balance</h3>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group mb-16">
            <label class="form-label required">Account Name:</label>
            <input type="text" id="edit-acc-name" class="form-control" value="${acc.name}" ${acc.is_system ? 'disabled title="System account names cannot be changed"' : ''}>
            ${acc.is_system ? '<small class="text-muted">System account name is protected for automated postings</small>' : ''}
          </div>
          <div class="grid-2 mb-16">
            <div class="form-group">
              <label class="form-label required">Account Group:</label>
              <select id="edit-acc-group" class="form-control" ${acc.is_system ? 'disabled' : ''}>
                <option value="Asset" ${acc.account_group === 'Asset' ? 'selected' : ''}>Asset</option>
                <option value="Liability" ${acc.account_group === 'Liability' ? 'selected' : ''}>Liability</option>
                <option value="Equity" ${acc.account_group === 'Equity' ? 'selected' : ''}>Equity</option>
                <option value="Income" ${acc.account_group === 'Income' ? 'selected' : ''}>Income</option>
                <option value="Expense" ${acc.account_group === 'Expense' ? 'selected' : ''}>Expense</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Account Sub-Type:</label>
              <input type="text" id="edit-acc-type" class="form-control" value="${acc.account_type || acc.account_group}">
            </div>
          </div>
          <div class="grid-2 mb-16">
            <div class="form-group">
              <label class="form-label">Opening Balance (₹):</label>
              <input type="number" id="edit-acc-bal" class="form-control" step="0.01" value="${acc.opening_balance || 0}">
            </div>
            <div class="form-group">
              <label class="form-label">Balance Side:</label>
              <select id="edit-acc-bal-type" class="form-control">
                <option value="dr" ${(acc.opening_balance_type || 'dr').toLowerCase() === 'dr' ? 'selected' : ''}>Debit (Dr)</option>
                <option value="cr" ${(acc.opening_balance_type || 'dr').toLowerCase() === 'cr' ? 'selected' : ''}>Credit (Cr)</option>
              </select>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Reports.saveEditAccount(${acc.id})">Update Account</button>
        </div>
      </div>`;
    App.showModal(html);
  },

  async saveEditAccount(accId) {
    const name = (document.getElementById('edit-acc-name')?.value || '').trim();
    const group = document.getElementById('edit-acc-group')?.value;
    const accType = (document.getElementById('edit-acc-type')?.value || group).trim();
    const bal = floatVal(document.getElementById('edit-acc-bal')?.value || '0');
    const balType = document.getElementById('edit-acc-bal-type')?.value || 'dr';

    try {
      await App.api(`/ledger/accounts/${accId}`, 'PUT', {
        name,
        account_group: group,
        account_type: accType,
        opening_balance: bal,
        opening_balance_type: balType
      });
      App.toast('Ledger account updated successfully', 'success');
      App.closeModal();
      this.loadAccounts();
    } catch(e) {
      App.toast(e.message, 'error');
    }
  },

  async showAccountStatementModal(accId) {
    App.showModal(`
      <div class="modal-card" style="max-width:800px">
        <div class="modal-header">
          <h3>📜 Ledger Account Statement</h3>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="modal-body" id="statement-modal-body">
          <div class="loading-overlay"><div class="spinner"></div></div>
        </div>
      </div>
    `);

    try {
      const res = await App.api(`/ledger/accounts/${accId}/statement`);
      const acc = res.account || {};
      const entries = res.entries || [];
      const bodyEl = document.getElementById('statement-modal-body');

      bodyEl.innerHTML = `
        <div class="stat-grid mb-16">
          <div class="stat-card">
            <div class="stat-label">Account Name</div>
            <div class="stat-value text-gold" style="font-size:16px">${acc.name}</div>
            <div class="stat-sub">${acc.account_group} (${acc.account_type || ''})</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Opening Balance</div>
            <div class="stat-value text-info">${App.fmt(res.opening_balance)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Closing Balance</div>
            <div class="stat-value text-success">${App.fmt(res.closing_balance)}</div>
          </div>
        </div>

        <div class="table-wrap" style="max-height:360px;overflow-y:auto">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Voucher No</th>
                <th>Narration</th>
                <th>Debit (₹)</th>
                <th>Credit (₹)</th>
                <th>Running Bal (₹)</th>
              </tr>
            </thead>
            <tbody>
              ${entries.length === 0 ? '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No voucher entries found for this account</td></tr>' :
                entries.map(e => `
                <tr>
                  <td class="td-muted">${e.voucher_date || ''}</td>
                  <td><span class="badge badge-info">${e.voucher_type}</span></td>
                  <td class="font-bold text-gold">${e.voucher_no}</td>
                  <td class="td-muted">${e.narration || ''}</td>
                  <td class="${e.debit > 0 ? 'font-bold text-success' : ''}">${e.debit > 0 ? App.fmt(e.debit) : '—'}</td>
                  <td class="${e.credit > 0 ? 'font-bold text-danger' : ''}">${e.credit > 0 ? App.fmt(e.credit) : '—'}</td>
                  <td class="font-bold">${App.fmt(e.running_balance)}</td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>
      `;
    } catch(e) {
      document.getElementById('statement-modal-body').innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── Sales Report ────────────────────────────────────────────────────────
  async loadSales() {
    const from  = document.getElementById('sr-from').value;
    const to    = document.getElementById('sr-to').value;
    const ptype = document.getElementById('sr-ptype')?.value || '';
    const el    = document.getElementById('sr-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
    try {
      const data  = await App.api(`/reports/sales?from=${from}&to=${to}&product_type=${ptype}`);
      const t     = data.totals || {};
      const bills = data.bills  || [];
      const pt    = data.by_product_type || {};

      el.innerHTML = `
        <div class="stat-grid mb-16">
          <div class="stat-card">
            <div class="stat-icon">💰</div>
            <div class="stat-label">Total Revenue</div>
            <div class="stat-value text-gold">${App.fmt(t.total_revenue || 0)}</div>
            <div class="stat-sub">${t.bill_count || 0} bills</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">🏷️</div>
            <div class="stat-label">Tax Collected</div>
            <div class="stat-value text-primary">${App.fmt((t.total_cgst || 0) + (t.total_sgst || 0) + (t.total_igst || 0))}</div>
            <div class="stat-sub">CGST+SGST+IGST</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">🥩</div>
            <div class="stat-label">Fresh Meat Sales</div>
            <div class="stat-value text-success">${App.fmt(pt.perishable?.total_sales || 0)}</div>
            <div class="stat-sub">Margin: ${App.fmt(pt.perishable?.gross_margin || 0)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">📦</div>
            <div class="stat-label">Packaged Goods</div>
            <div class="stat-value text-info">${App.fmt(pt.general?.total_sales || 0)}</div>
            <div class="stat-sub">Margin: ${App.fmt(pt.general?.gross_margin || 0)}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title"><span class="card-title-icon">📜</span> Sales Register (${bills.length} bills)</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Bill No</th><th>Date</th><th>Customer</th><th>Items</th><th>Subtotal</th><th>GST</th><th>Total</th><th>Status</th></tr></thead>
              <tbody>
                ${bills.length === 0 ? '<tr><td colspan="8" style="text-align:center;color:var(--text-muted)">No bills found in this period</td></tr>' :
                  bills.map(b => `
                  <tr>
                    <td class="font-bold text-gold">${b.bill_no}</td>
                    <td class="td-muted">${App.fmtDate(b.date)}</td>
                    <td>${b.customer_name || 'Walk-in'}</td>
                    <td class="td-muted" style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${b.products || '—'}</td>
                    <td>${App.fmt(b.subtotal)}</td>
                    <td>${App.fmt((b.cgst || 0) + (b.sgst || 0) + (b.igst || 0))}</td>
                    <td class="font-bold">${App.fmt(b.grand_total)}</td>
                    <td><span class="badge badge-${b.status === 'paid' ? 'success' : 'warning'}">${b.status}</span></td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── Financial Statements (P&L, Trial Balance, Balance Sheet) ──────────────
  async loadFinancialStatement() {
    const type = document.getElementById('fin-type').value;
    const el   = document.getElementById('fin-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

    try {
      if (type === 'tb') {
        const asof = document.getElementById('fin-asof')?.value || new Date().toISOString().split('T')[0];
        const tb = await App.api(`/reports/trial-balance?as_of=${asof}`);
        const accounts = tb.accounts || [];
        el.innerHTML = `
          <div class="card">
            <div class="card-title"><span class="card-title-icon">⚖️</span> Trial Balance (As of ${tb.as_of || asof})</div>
            <div class="table-wrap mb-16">
              <table>
                <thead><tr><th>Account Name</th><th>Account Group</th><th>Debit (₹)</th><th>Credit (₹)</th><th>Closing Balance (₹)</th><th>Side</th></tr></thead>
                <tbody>
                  ${accounts.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">No ledger entries found</td></tr>' :
                    accounts.map(a => `
                    <tr>
                      <td class="font-bold">${a.account_name}</td>
                      <td><span class="badge badge-info">${a.account_group}</span></td>
                      <td>${App.fmtNum(a.debit_total)}</td>
                      <td>${App.fmtNum(a.credit_total)}</td>
                      <td class="font-bold">${App.fmtNum(a.closing_balance)}</td>
                      <td><span class="badge badge-${a.balance_side === 'Dr' ? 'success' : 'gold'}">${a.balance_side}</span></td>
                    </tr>`).join('')}
                </tbody>
              </table>
            </div>
            <div class="filter-row" style="justify-content:space-between">
              <div>
                <strong>Total Debit:</strong> ${App.fmt(tb.total_debit || 0)} |
                <strong>Total Credit:</strong> ${App.fmt(tb.total_credit || 0)}
              </div>
              <div><span class="badge badge-${tb.is_balanced ? 'success' : 'danger'}">${tb.is_balanced ? '✓ BALANCED' : '⚠️ UNBALANCED'}</span></div>
            </div>
          </div>`;

      } else if (type === 'bs') {
        const asof = document.getElementById('fin-asof')?.value || new Date().toISOString().split('T')[0];
        const bs = await App.api(`/reports/balance-sheet?as_of=${asof}`);
        const assets      = bs.assets      || [];
        const liabilities = bs.liabilities || [];
        const equity      = bs.equity      || [];

        el.innerHTML = `
          <div class="stat-grid mb-16">
            <div class="stat-card"><div class="stat-label">Total Assets</div><div class="stat-value text-success">${App.fmt(bs.total_assets || 0)}</div></div>
            <div class="stat-card"><div class="stat-label">Total Liabilities</div><div class="stat-value text-danger">${App.fmt(bs.total_liabilities || 0)}</div></div>
            <div class="stat-card"><div class="stat-label">Total Equity</div><div class="stat-value text-info">${App.fmt(bs.total_equity || 0)}</div></div>
            <div class="stat-card"><div class="stat-label">Balance Check</div><div class="stat-value"><span class="badge badge-${bs.is_balanced ? 'success' : 'danger'}">${bs.is_balanced ? '✓ Balanced' : '⚠️ Unbalanced'}</span></div></div>
          </div>
          <div class="grid-2">
            <div class="card">
              <div class="card-title"><span class="card-title-icon">🏛️</span> Assets</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Asset Account</th><th>Type</th><th>Balance (₹)</th></tr></thead>
                  <tbody>
                    ${assets.map(a => `<tr><td class="font-bold">${a.account_name}</td><td class="td-muted">${a.account_type || ''}</td><td class="font-bold">${App.fmt(a.amount)}</td></tr>`).join('')}
                    <tr style="background:var(--bg-input)"><td class="font-bold" colspan="2">Total Assets</td><td class="font-bold text-success">${App.fmt(bs.total_assets || 0)}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="card">
              <div class="card-title"><span class="card-title-icon">⚖️</span> Liabilities &amp; Equity</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Account</th><th>Type</th><th>Balance (₹)</th></tr></thead>
                  <tbody>
                    ${liabilities.map(a => `<tr><td class="font-bold">${a.account_name}</td><td class="td-muted">${a.account_type || ''}</td><td class="font-bold">${App.fmt(a.amount)}</td></tr>`).join('')}
                    ${equity.map(a => `<tr><td class="font-bold">${a.account_name}</td><td class="td-muted">${a.account_type || ''}</td><td class="font-bold">${App.fmt(a.amount)}</td></tr>`).join('')}
                    <tr style="background:var(--bg-input)"><td class="font-bold" colspan="2">Total Liabilities &amp; Equity</td><td class="font-bold text-info">${App.fmt(bs.total_liabilities_equity || 0)}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>`;

      } else {
        const from = document.getElementById('fin-from')?.value || new Date().toISOString().split('T')[0].slice(0, 8) + '01';
        const to   = document.getElementById('fin-to')?.value   || new Date().toISOString().split('T')[0];
        const pl = await App.api(`/reports/profit-loss?from=${from}&to=${to}`);
        const incomeAccounts  = pl.income_accounts  || [];
        const expenseAccounts = pl.expense_accounts || [];
        const totalIncome     = pl.total_income  || 0;
        const totalExpense    = pl.total_expense || 0;
        const netProfit       = pl.net_profit    || 0;

        el.innerHTML = `
          <div class="stat-grid mb-16">
            <div class="stat-card"><div class="stat-label">Total Income</div><div class="stat-value text-gold">${App.fmt(totalIncome)}</div></div>
            <div class="stat-card"><div class="stat-label">Total Expenses</div><div class="stat-value text-danger">${App.fmt(totalExpense)}</div></div>
            <div class="stat-card"><div class="stat-label">Net Profit / (Loss)</div><div class="stat-value ${netProfit >= 0 ? 'text-success' : 'text-danger'}">${App.fmt(netProfit)}</div></div>
            <div class="stat-card"><div class="stat-label">Period</div><div class="stat-value" style="font-size:14px">${from} → ${to}</div></div>
          </div>
          <div class="grid-2">
            <div class="card">
              <div class="card-title"><span class="card-title-icon">💰</span> Income Accounts</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Account</th><th>Group</th><th>Amount (₹)</th></tr></thead>
                  <tbody>
                    ${incomeAccounts.length === 0 ? '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">No income entries</td></tr>' :
                      incomeAccounts.map(a => `<tr><td class="font-bold">${a.account_name}</td><td class="td-muted">${a.account_group || ''}</td><td class="font-bold text-success">${App.fmt(a.net_amount)}</td></tr>`).join('')}
                    <tr style="background:var(--bg-input)"><td class="font-bold" colspan="2">Total Income</td><td class="font-bold text-gold">${App.fmt(totalIncome)}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div class="card">
              <div class="card-title"><span class="card-title-icon">💸</span> Expense Accounts</div>
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Account</th><th>Group</th><th>Amount (₹)</th></tr></thead>
                  <tbody>
                    ${expenseAccounts.length === 0 ? '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">No expense entries</td></tr>' :
                      expenseAccounts.map(a => `<tr><td class="font-bold">${a.account_name}</td><td class="td-muted">${a.account_group || ''}</td><td class="font-bold text-danger">${App.fmt(a.net_amount)}</td></tr>`).join('')}
                    <tr style="background:var(--bg-input)"><td class="font-bold" colspan="2">Total Expenses</td><td class="font-bold text-danger">${App.fmt(totalExpense)}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div class="card" style="margin-top:16px">
            <div class="card-title"><span class="card-title-icon">📊</span> Summary (${from} to ${to})</div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Line Item</th><th style="text-align:right">Amount (₹)</th></tr></thead>
                <tbody>
                  <tr><td>Total Income</td><td style="text-align:right" class="font-bold text-success">${App.fmt(totalIncome)}</td></tr>
                  <tr><td>Less: Total Expenses</td><td style="text-align:right" class="text-danger">(${App.fmt(totalExpense)})</td></tr>
                  <tr style="background:var(--bg-card-hover)"><td><strong>NET PROFIT / (LOSS)</strong></td><td style="text-align:right" class="font-bold ${netProfit >= 0 ? 'text-success' : 'text-danger'}"><strong>${App.fmt(netProfit)}</strong></td></tr>
                </tbody>
              </table>
            </div>
          </div>`;
      }
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  async exportTallyXml() {
    const from = document.getElementById('fin-from')?.value || new Date().toISOString().split('T')[0].slice(0, 8) + '01';
    const to   = document.getElementById('fin-to')?.value   || new Date().toISOString().split('T')[0];
    try {
      window.open(`/api/reports/tally-xml?from=${from}&to=${to}`, '_blank');
      App.toast('Tally XML export initiated', 'success');
    } catch(e) { App.toast(e.message, 'error'); }
  },

  // ── Category Margins & Wastage ───────────────────────────────────────────
  async loadMarginsAndWastage() {
    const from = document.getElementById('m-from').value;
    const to   = document.getElementById('m-to').value;
    const el   = document.getElementById('margins-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

    try {
      const [marginData, wastageData] = await Promise.all([
        App.api(`/reports/margin-by-category?from=${from}&to=${to}`),
        App.api(`/reports/wastage?from=${from}&to=${to}`)
      ]);

      const cats = marginData.categories || [];
      const wastage = wastageData;

      el.innerHTML = `
        <div class="card mb-20">
          <div class="card-title"><span class="card-title-icon">📐</span> Gross Margin by Category</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Master Category</th><th>Qty Sold</th><th>Revenue (₹)</th><th>Cost (₹)</th><th>Gross Margin (₹)</th><th>Margin %</th></tr></thead>
              <tbody>
                ${cats.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">No sales in this period</td></tr>' :
                  cats.map(c => `
                  <tr>
                    <td class="font-bold">${c.category_name || 'Uncategorized'}</td>
                    <td>${App.fmtNum(c.quantity_sold)}</td>
                    <td>${App.fmt(c.revenue)}</td>
                    <td>${App.fmt(c.cost)}</td>
                    <td class="font-bold text-success">${App.fmt(c.gross_margin)}</td>
                    <td><span class="badge badge-gold">${c.margin_percent}%</span></td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title"><span class="card-title-icon">⚠️</span> Wastage &amp; Loss Summary (Total Loss: ${App.fmt(wastage.total_wastage_cost || 0)})</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Product Name</th><th>Product Type</th><th>Wastage Units</th><th>Total Cost (₹)</th><th>Reasons</th></tr></thead>
              <tbody>
                ${(wastage.wastage_summary || []).length === 0 ? '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No wastage recorded in this period</td></tr>' :
                  (wastage.wastage_summary || []).map(w => `
                  <tr>
                    <td class="font-bold">${w.product_name}</td>
                    <td><span class="badge badge-info">${w.product_type}</span></td>
                    <td>${App.fmtNum(w.total_wastage_purchase_units)} ${w.purchase_unit || 'kg'}</td>
                    <td class="font-bold text-danger">${App.fmt(w.total_wastage_cost)}</td>
                    <td class="td-muted">${w.reasons || 'Processing loss'}</td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── Conversion Yield Report ──────────────────────────────────────────────
  async loadConversionYield() {
    const from   = document.getElementById('y-from').value;
    const to     = document.getElementById('y-to').value;
    const thresh = document.getElementById('y-thresh').value || '5';
    const el     = document.getElementById('yield-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';

    try {
      const result      = await App.api(`/reports/conversion-yield?from=${from}&to=${to}&variance_threshold=${thresh}`);
      const conversions = result.conversions || [];

      if (conversions.length === 0) {
        el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🥩</div><h3>No conversions recorded in this date range</h3></div>';
        return;
      }

      el.innerHTML = `
        <div class="card">
          <div class="card-title"><span class="card-title-icon">🥩</span> Butchery Processing &amp; Yield Variance Log</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Conversion No</th><th>Date</th><th>Input Product</th><th>Input Qty</th><th>Overall Yield</th><th>Outputs &amp; Yield Variances</th><th>Status</th></tr></thead>
              <tbody>
                ${conversions.map(cnv => `
                  <tr>
                    <td class="font-bold text-gold">${cnv.conversion_no}</td>
                    <td class="td-muted">${App.fmtDate(cnv.conversion_date)}</td>
                    <td class="font-bold">${cnv.input_product_name}</td>
                    <td>${App.fmtNum(cnv.input_quantity)} ${cnv.input_unit || 'kg'}</td>
                    <td><span class="badge badge-gold">${cnv.yield_percent || 0}%</span></td>
                    <td>
                      <div style="display:flex;flex-direction:column;gap:4px">
                        ${(cnv.outputs || []).map(o => `
                          <div style="font-size:12px">
                            <strong>${o.output_product_name}:</strong> ${App.fmtNum(o.output_quantity)} ${o.output_unit || 'kg'}
                            (${o.actual_yield_percent}% vs exp ${o.expected_yield_percent}%)
                            ${o.is_flagged ? '<span class="badge badge-danger">⚠️ VAR ' + o.variance_percent + '%</span>' : ''}
                          </div>`).join('')}
                      </div>
                    </td>
                    <td><span class="badge badge-${cnv.has_variance_flag ? 'warning' : 'success'}">${cnv.has_variance_flag ? '⚠️ Variance Flag' : '✓ Normal'}</span></td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── GST Report ───────────────────────────────────────────────────────────
  async loadGST() {
    const from = document.getElementById('gr-from').value;
    const to   = document.getElementById('gr-to').value;
    const el   = document.getElementById('gr-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
    try {
      const result  = await App.api(`/reports/gst?from=${from}&to=${to}`);
      const summary = result.gst_summary || [];

      let totTaxable = 0, totCgst = 0, totSgst = 0, totIgst = 0, totGst = 0;
      summary.forEach(r => {
        totTaxable += r.taxable  || 0;
        totCgst    += r.cgst     || 0;
        totSgst    += r.sgst     || 0;
        totIgst    += r.igst     || 0;
        totGst     += r.total_gst || 0;
      });

      el.innerHTML = `
        <div class="stat-grid mb-16">
          <div class="stat-card"><div class="stat-label">Taxable Value</div><div class="stat-value text-gold">${App.fmt(totTaxable)}</div></div>
          <div class="stat-card"><div class="stat-label">CGST Total</div><div class="stat-value text-info">${App.fmt(totCgst)}</div></div>
          <div class="stat-card"><div class="stat-label">SGST Total</div><div class="stat-value text-info">${App.fmt(totSgst)}</div></div>
          <div class="stat-card"><div class="stat-label">Total GST Collected</div><div class="stat-value text-success">${App.fmt(totGst)}</div></div>
        </div>

        <div class="card">
          <div class="card-title"><span class="card-title-icon">🏛️</span> GST Summary By Rate</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>GST Rate</th><th>Type</th><th>Taxable Amount</th><th>CGST</th><th>SGST</th><th>IGST</th><th>Total GST</th></tr></thead>
              <tbody>
                ${summary.length === 0 ? '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No GST-applicable sales in this period</td></tr>' :
                  summary.map(r => `
                  <tr>
                    <td><span class="badge badge-gold">${r.gst_rate}%</span></td>
                    <td><span class="badge badge-info">${r.is_interstate ? 'Interstate (IGST)' : 'Intrastate (CGST+SGST)'}</span></td>
                    <td>${App.fmt(r.taxable)}</td>
                    <td>${App.fmt(r.cgst)}</td>
                    <td>${App.fmt(r.sgst)}</td>
                    <td>${App.fmt(r.igst)}</td>
                    <td class="font-bold text-success">${App.fmt(r.total_gst)}</td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── Stock Report ─────────────────────────────────────────────────────────
  async loadStock() {
    const el = document.getElementById('stock-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
    try {
      const data     = await App.api('/reports/stock');
      const prods    = data.products    || [];
      const totalVal = data.total_value || 0;

      el.innerHTML = `
        <div class="stat-card mb-16" style="max-width:300px">
          <div class="stat-label">Total Stock Valuation</div>
          <div class="stat-value text-gold">${App.fmt(totalVal)}</div>
          <div class="stat-sub">${prods.length} active products</div>
        </div>

        <div class="card">
          <div class="card-title"><span class="card-title-icon">📦</span> Stock Valuation Register</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Code</th><th>Product Name</th><th>Category</th><th>Current Stock</th><th>Purchase Price</th><th>Stock Value</th><th>Status</th></tr></thead>
              <tbody>
                ${prods.length === 0 ? '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No products found</td></tr>' :
                  prods.map(p => `
                  <tr>
                    <td class="font-bold text-gold">${p.code || '—'}</td>
                    <td class="font-bold">${p.name}</td>
                    <td class="td-muted">${p.category_name || 'Uncategorized'}</td>
                    <td>${App.fmtNum(p.current_stock)} ${p.purchase_unit || 'kg'}</td>
                    <td>${App.fmt(p.purchase_price)}</td>
                    <td class="font-bold">${App.fmt(p.stock_value)}</td>
                    <td>${p.current_stock <= p.min_stock ? '<span class="badge badge-warning">Low Stock</span>' : '<span class="badge badge-success">OK</span>'}</td>
                  </tr>`).join('')}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── Top Products ─────────────────────────────────────────────────────────
  async loadTopProducts() {
    const from = document.getElementById('tp-from').value;
    const to   = document.getElementById('tp-to').value;
    const el   = document.getElementById('top-content');
    el.innerHTML = '<div class="loading-overlay"><div class="spinner"></div></div>';
    try {
      const products = await App.api(`/reports/top-products?from=${from}&to=${to}`);
      const list = Array.isArray(products) ? products : (products.products || []);

      if (list.length === 0) {
        el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🏆</div><h3>No sales in this period</h3></div>';
        return;
      }

      const maxRevenue = list[0].total_revenue;
      el.innerHTML = `
        <div class="card">
          <div class="card-title"><span class="card-title-icon">🏆</span> Top Products by Revenue (${from} to ${to})</div>
          <div style="display:flex;flex-direction:column;gap:12px">
            ${list.map((p, i) => {
              const barPct = (p.total_revenue / maxRevenue) * 100;
              const medals = ['🥇','🥈','🥉'];
              return `
                <div style="padding:14px;background:var(--bg-input);border-radius:var(--r-md);border:1px solid var(--border)">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <div style="display:flex;align-items:center;gap:10px">
                      <span style="font-size:22px">${medals[i] || `<span class="badge badge-info">${i+1}</span>`}</span>
                      <div>
                        <div class="font-bold">${p.product_name}</div>
                        <div class="text-muted text-sm">${App.fmtNum(p.total_qty)} ${p.unit || 'kg'} sold across ${p.bill_count} bills</div>
                      </div>
                    </div>
                    <div class="font-bold text-gold" style="font-size:16px">${App.fmt(p.total_revenue)}</div>
                  </div>
                  <div class="stock-bar">
                    <div class="stock-bar-fill ok" style="width:${barPct}%"></div>
                  </div>
                </div>`;
            }).join('')}
          </div>
        </div>`;
    } catch(e) {
      el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },
};

function floatVal(val) {
  const f = parseFloat(val);
  return isNaN(f) ? 0.0 : f;
}

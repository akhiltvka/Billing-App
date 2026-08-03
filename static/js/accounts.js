/**
 * accounts.js — Standalone Chart of Accounts & Assets Module
 * Meat Products of India — Billing & Inventory Management App
 */

const Accounts = {
  allAccounts: [],

  async render() {
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="page-enter">
        <div class="page-header">
          <div class="page-header-left">
            <h1>📒 Chart of Accounts &amp; Assets</h1>
            <p>Manage double-entry ledger accounts, opening balances, assets, liabilities, equity &amp; view account statements</p>
          </div>
          ${Auth.can('accounts.manage') ? '<button class="btn btn-primary" onclick="Accounts.showAddAccountModal()">➕ Add Ledger Account / Asset</button>' : ''}
        </div>

        <div class="filter-row mb-16" style="justify-content:space-between">
          <div style="display:flex;gap:10px;align-items:center">
            <select id="acc-group-filter" class="form-control" style="width:180px" onchange="Accounts.renderAccountsTable()">
              <option value="">All Groups</option>
              <option value="Asset">Assets</option>
              <option value="Liability">Liabilities</option>
              <option value="Equity">Equity</option>
              <option value="Income">Income</option>
              <option value="Expense">Expense</option>
            </select>
            <input type="text" id="acc-search" class="form-control" placeholder="Search account name..." style="width:240px" oninput="Accounts.renderAccountsTable()">
          </div>
        </div>

        <div id="accounts-page-content">
          <div class="loading-overlay"><div class="spinner"></div></div>
        </div>
      </div>`;

    await this.loadAccounts();
  },

  async loadAccounts() {
    const el = document.getElementById('accounts-page-content');
    if (!el) return;
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
    const el = document.getElementById('accounts-page-content');
    if (!el) return;

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
                    <button class="btn btn-secondary btn-sm" onclick="Accounts.showEditAccountModal(${a.id})" title="Edit Account / Opening Balance">✏️ Edit</button>
                    <button class="btn btn-secondary btn-sm" onclick="Accounts.showAccountStatementModal(${a.id})" title="View Ledger Statement">📜 Statement</button>
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
              <select id="new-acc-group" class="form-control" onchange="Accounts.onAddGroupChange()">
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
          <button class="btn btn-primary" onclick="Accounts.saveNewAccount()">Save Account</button>
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
          <button class="btn btn-primary" onclick="Accounts.saveEditAccount(${acc.id})">Update Account</button>
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
};

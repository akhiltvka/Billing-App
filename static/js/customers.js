/**
 * customers.js — Customer Management Module
 * Meat Products of India — Billing & Inventory Management App
 */

const Customers = {

  async render() {
    const content = document.getElementById('page-content');
    try {
      const customers = await App.api('/customers');
      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>👥 Customers</h1>
              <p>${customers.length} registered customers</p>
            </div>
            <button class="btn btn-primary" onclick="Customers.showModal()">➕ Add Customer</button>
          </div>

          <div class="filter-row">
            <div class="search-bar" style="flex:1;max-width:340px">
              <span class="search-icon">🔎</span>
              <input id="cust-search" type="text" placeholder="Search by name or phone…"
                oninput="Customers.filter(this.value)">
            </div>
          </div>

          ${customers.length === 0
            ? '<div class="empty-state"><div class="empty-state-icon">👥</div><h3>No customers yet</h3><p>Add your first customer</p></div>'
            : `<div class="card">
                <div class="table-wrap">
                  <table>
                    <thead><tr>
                      <th>#</th><th>Name</th><th>Phone</th><th>Email</th>
                      ${App.isGstEnabled() ? '<th>GSTIN</th>' : ''}<th>Loyalty Points</th><th class="text-right">Credit</th><th>Since</th><th>Actions</th>
                    </tr></thead>
                    <tbody id="cust-tbody">
                      ${customers.map((c, i) => `
                        <tr data-name="${c.name.toLowerCase()}" data-phone="${c.phone || ''}">
                          <td class="td-muted">${i + 1}</td>
                          <td class="font-bold">${c.name}</td>
                          <td>${c.phone || '—'}</td>
                          <td class="td-muted">${c.email || '—'}</td>
                          ${App.isGstEnabled() ? `<td class="td-muted">${c.gstin || '—'}</td>` : ''}
                          <td class="font-bold text-gold">⭐ ${parseFloat(c.loyalty_points || 0).toFixed(2)}</td>
                          <td class="td-number ${c.credit_balance > 0 ? 'text-warning' : 'text-muted'}">
                            ${c.credit_balance > 0 ? App.fmt(c.credit_balance) : '—'}
                          </td>
                          <td class="td-muted">${App.fmtDate(c.created_at)}</td>
                          <td>
                            <div style="display:flex;gap:6px">
                              <button class="btn btn-secondary btn-sm" onclick="Customers.viewHistory(${c.id},'${c.name}')" title="View History & Points">📋</button>
                              ${Auth.can('customers.manage') ? `
                              <button class="btn btn-secondary btn-sm btn-icon" onclick="Customers.showModal(${JSON.stringify(JSON.stringify(c))})" title="Edit">✏️</button>
                              <button class="btn btn-danger btn-sm btn-icon" onclick="Customers.delete(${c.id},'${c.name}')" title="Delete">🗑️</button>` : ''}
                            </div>
                          </td>
                        </tr>`).join('')}
                    </tbody>
                  </table>
                </div>
              </div>`}
        </div>`;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  filter(q) {
    const rows = document.querySelectorAll('#cust-tbody tr');
    rows.forEach(r => {
      const match = r.dataset.name.includes(q.toLowerCase()) || r.dataset.phone.includes(q);
      r.style.display = match ? '' : 'none';
    });
  },

  showModal(customerJson = null) {
    const c = customerJson ? (typeof customerJson === 'string' ? JSON.parse(customerJson) : customerJson) : null;
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">👤</span> ${c ? 'Edit' : 'Add'} Customer</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label required">Full Name</label>
          <input class="form-control" id="c-name" value="${c?.name || ''}" placeholder="Customer's full name">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Mobile Number (10 digits)</label>
            <input class="form-control" id="c-phone" value="${c?.phone || ''}" placeholder="10-digit mobile number" maxlength="10" oninput="this.value=this.value.replace(/[^0-9]/g,'')">
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-control" id="c-email" type="email" value="${c?.email || ''}" placeholder="email@example.com">
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Address</label>
          <textarea class="form-control" id="c-address">${c?.address || ''}</textarea>
        </div>
        ${App.isGstEnabled() ? `
        <div class="form-group">
          <label class="form-label">GSTIN (for B2B customers)</label>
          <input class="form-control" id="c-gstin" value="${c?.gstin || ''}" placeholder="15-character GSTIN">
        </div>` : '<input type="hidden" id="c-gstin" value="">'}
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Customers.save(${c?.id || 'null'})">${c ? 'Update' : 'Add'} Customer</button>
        </div>
      </div>`);
  },

  async save(id) {
    const name = document.getElementById('c-name').value.trim();
    if (!name) { App.toast('Name required', 'error'); return; }
    const phone = document.getElementById('c-phone').value.trim();
    if (phone && !/^\d{10}$/.test(phone)) {
      App.toast('Phone number must be exactly 10 digits', 'error');
      return;
    }
    const payload = {
      name,
      phone,
      email:   document.getElementById('c-email').value,
      address: document.getElementById('c-address').value,
      gstin:   document.getElementById('c-gstin').value,
    };
    try {
      if (id) {
        await App.api(`/customers/${id}`, 'PUT', payload);
        App.toast('Customer updated', 'success');
      } else {
        await App.api('/customers', 'POST', payload);
        App.toast('Customer added', 'success');
      }
      App.closeModal();
      this.render();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async delete(id, name) {
    App.confirm(`Delete customer "${name}"?`, 'Delete Customer', async () => {
      await App.api(`/customers/${id}`, 'DELETE');
      App.toast('Customer deleted', 'warning');
      this.render();
    });
  },

  async viewHistory(id, name) {
    try {
      const data = await App.api(`/customers/${id}`);
      let loyaltyData = null;
      try {
        loyaltyData = await App.api(`/customers/${id}/loyalty`);
      } catch(e) {}

      const bills = data.bills || [];
      const totalSpent = bills.reduce((s, b) => s + b.grand_total, 0);
      const loyaltyPts = loyaltyData ? loyaltyData.loyalty_points : (data.loyalty_points || 0);
      const ptsValRupees = loyaltyData ? loyaltyData.points_value_rupees : 0;
      const ledger = (loyaltyData && loyaltyData.ledger) ? loyaltyData.ledger : [];

      App.showModal(`
        <div class="modal modal-lg" style="max-height:90vh;display:flex;flex-direction:column">
          <div class="modal-header">
            <div class="modal-title"><span class="modal-title-icon">📋</span> ${name} — Purchase &amp; Loyalty History</div>
            <button class="modal-close" onclick="App.closeModal()">✕</button>
          </div>
          <div style="padding:16px;overflow-y:auto;flex:1">
            <div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap">
              <div class="stat-card" style="flex:1;min-width:140px">
                <div class="stat-label">Total Spent</div>
                <div class="stat-value text-gold" style="font-size:20px">${App.fmt(totalSpent)}</div>
              </div>
              <div class="stat-card" style="flex:1;min-width:140px">
                <div class="stat-label">Total Bills</div>
                <div class="stat-value" style="font-size:20px">${bills.length}</div>
              </div>
              <div class="stat-card" style="flex:1;min-width:140px;background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.3)">
                <div class="stat-label" style="color:var(--gold)">⭐ Loyalty Balance</div>
                <div class="stat-value text-gold" style="font-size:20px">${loyaltyPts.toFixed(2)} <span style="font-size:12px;color:var(--text-muted)">(₹${ptsValRupees.toFixed(2)})</span></div>
              </div>
              ${data.credit_balance > 0 ? `
              <div class="stat-card" style="flex:1;min-width:140px">
                <div class="stat-label">Outstanding</div>
                <div class="stat-value text-warning" style="font-size:20px">${App.fmt(data.credit_balance)}</div>
              </div>` : ''}
            </div>

            <!-- Tab Buttons -->
            <div style="display:flex;gap:8px;border-bottom:1px solid var(--border);margin-bottom:12px">
              <button class="btn btn-secondary btn-sm" id="tab-cust-bills-btn" onclick="document.getElementById('tab-cust-bills').style.display='block';document.getElementById('tab-cust-loyalty').style.display='none';this.className='btn btn-primary btn-sm';document.getElementById('tab-cust-loyalty-btn').className='btn btn-secondary btn-sm'">
                📜 Purchase Bills (${bills.length})
              </button>
              <button class="btn btn-secondary btn-sm" id="tab-cust-loyalty-btn" onclick="document.getElementById('tab-cust-bills').style.display='none';document.getElementById('tab-cust-loyalty').style.display='block';this.className='btn btn-primary btn-sm';document.getElementById('tab-cust-bills-btn').className='btn btn-secondary btn-sm'">
                ⭐ Loyalty Points Ledger (${ledger.length})
              </button>
            </div>

            <!-- Bills Tab -->
            <div id="tab-cust-bills">
              ${bills.length === 0
                ? '<div class="empty-state"><div class="empty-state-icon">📋</div><h3>No purchases yet</h3></div>'
                : `<div class="table-wrap scroll-list">
                    <table>
                      <thead><tr><th>Bill No</th><th>Date</th><th class="text-right">Amount</th><th>Actions</th></tr></thead>
                      <tbody>
                        ${bills.map(b => `
                          <tr>
                            <td class="font-bold text-gold">${b.bill_no}</td>
                            <td class="td-muted">${App.fmtDateTime(b.date)}</td>
                            <td class="td-number">${App.fmt(b.grand_total)}</td>
                            <td>
                              <button class="btn btn-secondary btn-sm" onclick="Billing.showPrintPreviewModal(${b.id}, 'a4', '${b.print_token || ''}')" title="Print Full Invoice (A4)">🖨️ Print</button>
                              <button class="btn btn-secondary btn-sm" onclick="Billing.showPrintPreviewModal(${b.id}, 'thermal', '${b.print_token || ''}')" title="Print Thermal Receipt">🧾 Thermal</button>
                            </td>
                          </tr>`).join('')}
                      </tbody>
                    </table>
                  </div>`}
            </div>

            <!-- Loyalty Ledger Tab -->
            <div id="tab-cust-loyalty" style="display:none">
              ${ledger.length === 0
                ? '<div class="empty-state"><div class="empty-state-icon">⭐</div><h3>No loyalty point transactions yet</h3></div>'
                : `<div class="table-wrap scroll-list">
                    <table>
                      <thead><tr><th>#</th><th>Date</th><th>Reason</th><th class="text-right">Points Change</th></tr></thead>
                      <tbody>
                        ${ledger.map((l, idx) => `
                          <tr>
                            <td class="td-muted">${idx + 1}</td>
                            <td class="td-muted">${App.fmtDateTime(l.created_at)}</td>
                            <td class="font-semibold">${App.escapeHtml(l.reason || 'Loyalty Transaction')}</td>
                            <td class="td-number font-bold ${l.points_change >= 0 ? 'text-success' : 'text-danger'}">
                              ${l.points_change >= 0 ? '+' : ''}${l.points_change.toFixed(2)} pts
                            </td>
                          </tr>`).join('')}
                      </tbody>
                    </table>
                  </div>`}
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
          </div>
        </div>`);
    } catch(e) { App.toast(e.message, 'error'); }
  },
};

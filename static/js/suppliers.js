/**
 * suppliers.js — Supplier Management Module
 * Meat Products of India — Billing & Inventory Management App
 */

const Suppliers = {

  async render() {
    const content = document.getElementById('page-content');
    try {
      const suppliers = await App.api('/suppliers');
      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>🚚 Suppliers</h1>
              <p>${suppliers.length} registered suppliers</p>
            </div>
            ${Auth.can('suppliers.manage') ? '<button class="btn btn-primary" onclick="Suppliers.showModal()">➕ Add Supplier</button>' : ''}
          </div>

          ${suppliers.length === 0
            ? '<div class="empty-state"><div class="empty-state-icon">🚚</div><h3>No suppliers yet</h3><p>Add your meat and product suppliers</p></div>'
            : `<div class="grid-auto">
                ${suppliers.map(s => `
                  <div class="card" style="padding:20px">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px">
                      <div>
                        <div style="font-size:16px;font-weight:700">${s.name}</div>
                        ${s.contact_person ? `<div class="text-muted text-sm">Contact: ${s.contact_person}</div>` : ''}
                      </div>
                      ${Auth.can('suppliers.manage') ? `
                      <div style="display:flex;gap:6px">
                        <button class="btn btn-secondary btn-sm btn-icon" onclick="Suppliers.showModal(${JSON.stringify(JSON.stringify(s))})" title="Edit">✏️</button>
                        <button class="btn btn-danger btn-sm btn-icon" onclick="Suppliers.delete(${s.id},'${s.name}')" title="Delete">🗑️</button>
                      </div>` : ''}
                    </div>
                    <div style="display:flex;flex-direction:column;gap:8px">
                      ${s.phone ? `<div style="display:flex;align-items:center;gap:8px;font-size:13px"><span>📞</span><span>${s.phone}</span></div>` : ''}
                      ${s.email ? `<div style="display:flex;align-items:center;gap:8px;font-size:13px"><span>✉️</span><span class="text-muted">${s.email}</span></div>` : ''}
                      ${s.address ? `<div style="display:flex;align-items:center;gap:8px;font-size:13px"><span>📍</span><span class="text-muted">${s.address}</span></div>` : ''}
                      ${App.isGstEnabled() && s.gstin ? `<div style="display:flex;align-items:center;gap:8px;font-size:13px"><span>🏛️</span><span class="badge badge-info">${s.gstin}</span></div>` : ''}
                    </div>
                    ${s.balance > 0 ? `<div style="margin-top:12px;padding:8px 12px;background:var(--warning-bg);border-radius:var(--r-md);font-size:13px;color:var(--warning);font-weight:600">
                      ⚠️ Balance Due: ${App.fmt(s.balance)}
                    </div>` : ''}
                  </div>`).join('')}
              </div>`}
        </div>`;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  showModal(supplierJson = null) {
    const s = supplierJson ? (typeof supplierJson === 'string' ? JSON.parse(supplierJson) : supplierJson) : null;
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">🚚</span> ${s ? 'Edit' : 'Add'} Supplier</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label required">Business / Supplier Name</label>
          <input class="form-control" id="s-name" value="${s?.name || ''}" placeholder="e.g., Fresh Farms Pvt. Ltd.">
        </div>
        <div class="form-group">
          <label class="form-label">Contact Person</label>
          <input class="form-control" id="s-contact" value="${s?.contact_person || ''}" placeholder="Name of contact person">
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Phone Number (10 digits)</label>
            <input class="form-control" id="s-phone" value="${s?.phone || ''}" placeholder="10-digit mobile number" maxlength="10" oninput="this.value=this.value.replace(/[^0-9]/g,'')">
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input class="form-control" id="s-email" type="email" value="${s?.email || ''}" placeholder="email@supplier.com">
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Address</label>
          <textarea class="form-control" id="s-address">${s?.address || ''}</textarea>
        </div>
        ${App.isGstEnabled() ? `
        <div class="form-group">
          <label class="form-label">GSTIN</label>
          <input class="form-control" id="s-gstin" value="${s?.gstin || ''}" placeholder="15-character GSTIN">
        </div>` : '<input type="hidden" id="s-gstin" value="">'}
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Suppliers.save(${s?.id || 'null'})">${s ? 'Update' : 'Add'} Supplier</button>
        </div>
      </div>`);
  },

  async save(id) {
    const name = document.getElementById('s-name').value.trim();
    if (!name) { App.toast('Name required', 'error'); return; }
    const phone = document.getElementById('s-phone').value.trim();
    if (phone && !/^\d{10}$/.test(phone)) {
      App.toast('Phone number must be exactly 10 digits', 'error');
      return;
    }
    const payload = {
      name,
      contact_person: document.getElementById('s-contact').value,
      phone,
      email:  document.getElementById('s-email').value,
      address: document.getElementById('s-address').value,
      gstin:  document.getElementById('s-gstin').value,
    };
    try {
      if (id) {
        await App.api(`/suppliers/${id}`, 'PUT', payload);
        App.toast('Supplier updated', 'success');
      } else {
        await App.api('/suppliers', 'POST', payload);
        App.toast('Supplier added', 'success');
      }
      App.closeModal();
      this.render();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async delete(id, name) {
    App.confirm(`Delete supplier "${name}"?`, 'Delete Supplier', async () => {
      await App.api(`/suppliers/${id}`, 'DELETE');
      App.toast('Supplier deleted', 'warning');
      this.render();
    });
  },
};

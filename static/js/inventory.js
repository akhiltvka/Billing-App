/**
 * inventory.js — Products, Categories, Stock-In, Purchase Orders
 * Meat Products of India — Billing & Inventory Management App
 */

const Inventory = {

  // ─── Main Page — delegated to Tally Prime–style module ────────────────────
  async render() {
    // Delegate to the Tally Prime–style inventory module.
    // All product/category modals below are still called by TallyInventory.
    if (typeof TallyInventory !== 'undefined') {
      return TallyInventory.render();
    }
    // Fallback: plain product list (should not reach here normally)
    const content = document.getElementById('page-content');
    content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>TallyInventory module not loaded</h3></div>`;
  },


  filterProducts(searchVal) {
    const q = (searchVal !== undefined ? searchVal : (document.getElementById('prod-search')?.value || '')).toLowerCase();
    const catId = document.getElementById('cat-filter')?.value || '';
    const lowOnly = document.getElementById('low-stock-only')?.checked || false;

    let filtered = this._allProducts || [];
    if (q) filtered = filtered.filter(p => p.name.toLowerCase().includes(q) || (p.barcode && p.barcode.includes(q)));
    if (catId) filtered = filtered.filter(p => String(p.category_id) === catId);
    if (lowOnly) filtered = filtered.filter(p => p.current_stock <= p.min_stock);

    const grid = document.getElementById('product-grid');
    if (!grid) return;

    if (filtered.length === 0) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="empty-state-icon">📦</div><h3>No products found</h3>
        <p>Try adjusting your search or filter</p></div>`;
      return;
    }

    grid.innerHTML = filtered.map(p => {
      const stockPct = p.min_stock > 0 ? Math.min((p.current_stock / (p.min_stock * 3)) * 100, 100) : 100;
      const fillClass = p.current_stock <= 0 ? 'zero'
        : p.current_stock <= p.min_stock ? 'critical'
        : p.current_stock <= p.min_stock * 2 ? 'low' : 'ok';
      const lowBadge = p.current_stock <= p.min_stock
        ? `<span class="badge badge-warning" style="font-size:10px">⚠️ Low</span>`
        : '';
      return `
        <div class="product-card ${p.current_stock <= p.min_stock ? 'low-stock' : ''}">
          <div class="product-card-header">
            <div>
              <div class="product-card-name">
                ${p.name}
                <span class="badge badge-gold" style="font-family:monospace;font-size:11px;padding:2px 6px;margin-left:4px">[${p.code || 'N/A'}]</span>
              </div>
              <div class="product-card-cat">${p.category_name || 'Uncategorised'}</div>
            </div>
            <div style="display:flex;gap:4px;flex-direction:column;align-items:flex-end">
              ${lowBadge}
              <div style="display:flex;gap:4px">
                ${(Auth.can('inventory.edit') || Auth.isRole('admin','md','manager')) ? `<button class="btn btn-secondary btn-sm btn-icon" onclick="Inventory.showProductModalById(${p.id})" title="Edit">✏️</button>` : ''}
                ${(Auth.can('inventory.delete') || Auth.isRole('admin','md','manager')) ? `<button class="btn btn-danger btn-sm btn-icon" onclick="Inventory.deleteProduct(${p.id},'${App.escapeHtml(p.name).replace(/'/g, "\\'")}')" title="Deactivate">🗑️</button>` : ''}
                <button class="btn btn-secondary btn-sm btn-icon" style="background:rgba(139,92,246,.1);border-color:rgba(139,92,246,.3);color:#7c3aed" onclick="Inventory.printProductBarcode(${p.id},'${p.name.replace(/'/g,"\\'")}',${'"' + (p.barcode||p.code) + '"'},${p.selling_price},'${p.unit}','${p.code}')" title="Print Barcode">🏷️</button>
              </div>
            </div>
          </div>

          <div class="stock-bar">
            <div class="stock-bar-fill ${fillClass}" style="width:${stockPct}%"></div>
          </div>

          <div class="product-metrics">
            <div>
              <div class="product-metric-label">Current Stock</div>
              <div class="product-metric-value ${p.current_stock <= 0 ? 'text-danger' : p.current_stock <= p.min_stock ? 'text-warning' : 'text-success'}">
                ${App.fmtNum(p.current_stock)} ${p.unit}
              </div>
            </div>
            <div>
              <div class="product-metric-label">Min Stock</div>
              <div class="product-metric-value">${App.fmtNum(p.min_stock)} ${p.unit}</div>
            </div>
            <div>
              <div class="product-metric-label">Selling Price</div>
              <div class="product-metric-value text-gold">${App.fmt(p.selling_price)}/${p.unit}</div>
            </div>
            <div>
              <div class="product-metric-label">Purchase Price</div>
              <div class="product-metric-value">${App.fmt(p.purchase_price)}/${p.unit}</div>
            </div>
          </div>

          <div style="margin-top:12px;display:flex;gap:6px">
            ${Auth.can('stock.in') ? `
            <button class="btn btn-success btn-sm" style="flex:1" onclick="Inventory.quickStockIn(${JSON.stringify(JSON.stringify(p))})">
              ⬆️ Stock In
            </button>` : ''}
            <button class="btn btn-secondary btn-sm" onclick="Inventory.showStockHistory(${p.id},'${p.name}')">
              📋 History
            </button>
          </div>
        </div>`;
    }).join('');
  },

  // ─── Product Modal ────────────────────────────────────────────────────────
  async showProductModalById(id) {
    if (!id) return this.showProductModal(null);
    let p = (this._allProducts || []).find(x => x.id == id) || (typeof TallyInventory !== 'undefined' ? (TallyInventory._products || []).find(x => x.id == id) : null);
    if (!p) {
      try {
        const prods = await App.api('/products?active=true');
        if (Array.isArray(prods)) {
          this._allProducts = prods;
          p = prods.find(x => x.id == id) || null;
        }
      } catch(e) {}
    }
    this.showProductModal(p || id);
  },

  toggleOpeningStock(checked) {
    const row = document.getElementById('p-openstock-row');
    const openstockInput = document.getElementById('p-openstock');
    const purchasedateInput = document.getElementById('p-purchasedate');
    if (row) {
      row.style.display = checked ? 'flex' : 'none';
    }
    if (openstockInput) {
      openstockInput.disabled = !checked;
    }
    if (purchasedateInput) {
      purchasedateInput.disabled = !checked;
    }
  },

  async checkAndShowMissingDatesModal() {
    try {
      const res = await App.api('/stock/missing-purchase-dates');
      const batches = Array.isArray(res) ? res : (res && res.data ? res.data : []);
      if (batches.length > 0) {
        this.showMissingDatesModal(batches);
        return true;
      }
    } catch(e) {
      console.error("Error checking missing purchase dates:", e);
    }
    return false;
  },

  showMissingDatesModal(batches) {
    const today = new Date().toISOString().slice(0, 10);
    const rowsHtml = batches.map((b, idx) => `
      <tr class="missing-date-row" data-batch-id="${b.batch_id}">
        <td style="font-weight:700;text-align:left">${b.product_name} <span class="text-muted" style="font-size:11px">[${b.product_code}]</span></td>
        <td class="num">${App.fmtNum(b.quantity_remaining)} ${b.unit}</td>
        <td><code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:4px">${b.batch_no || 'N/A'}</code></td>
        <td>
          <input type="date" class="form-control msi-date-input" style="width:100%;height:32px" max="${today}" value="${today}">
        </td>
      </tr>
    `).join('');

    App.showModal(`
      <div class="modal" style="max-width:700px;width:95vw">
        <div class="modal-header" style="background:var(--warning-bg);border-bottom:1px solid rgba(243,156,18,0.2);color:var(--warning)">
          <div class="modal-title" style="color:var(--warning);font-weight:bold"><span class="modal-title-icon">⚠️</span> Enter Missing Stock Purchase Dates</div>
        </div>
        <div style="padding:12px 0">
          <p class="text-muted text-sm" style="text-align:left">
            The following active stock batches are missing purchase dates. 
            Purchase date is required for stock entry tracking. Please specify the purchase date for each batch below to proceed.
          </p>
        </div>
        <div class="table-wrap mb-16" style="max-height:300px;overflow-y:auto">
          <table class="table" style="width:100%">
            <thead>
              <tr>
                <th style="text-align:left">Product</th>
                <th class="num">Remaining Qty</th>
                <th>Batch No.</th>
                <th style="width:160px">Date of Purchase *</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
        <div class="modal-footer" style="display:flex;justify-content:flex-end;gap:8px">
          <button class="btn btn-primary" onclick="Inventory.saveMissingPurchaseDates()">💾 Save Purchase Dates</button>
        </div>
      </div>`, { closable: false });
  },

  async saveMissingPurchaseDates() {
    const rows = document.querySelectorAll('.missing-date-row');
    const updates = [];
    for (const r of rows) {
      const batchId = r.dataset.batchId;
      const dateInput = r.querySelector('.msi-date-input');
      const dateVal = dateInput ? dateInput.value : '';
      if (!dateVal) {
        App.toast('All purchase dates are required to proceed', 'error');
        dateInput?.focus();
        return;
      }
      updates.push({ batch_id: parseInt(batchId), purchase_date: dateVal });
    }

    try {
      await App.api('/stock/missing-purchase-dates', 'POST', { updates });
      App.toast('Purchase dates updated successfully!', 'success');
      
      const modal = document.getElementById('main-modal');
      if (modal) {
        modal.removeAttribute('data-closable');
        App.closeModal('main-modal');
      }
      
      if (App.currentPage === 'stock-in') {
        this.renderStockIn();
      } else {
        this.render();
      }
    } catch(e) {
      App.toast(e.message, 'error');
    }
  },

  async showProductModal(productJson = null) {
    let p = null;
    if (typeof productJson === 'number' || (typeof productJson === 'string' && /^\d+$/.test(productJson))) {
      const pid = parseInt(productJson);
      p = (this._allProducts || []).find(x => x.id === pid) || (typeof TallyInventory !== 'undefined' ? (TallyInventory._products || []).find(x => x.id === pid) : null);
      if (!p) {
        try {
          const prods = await App.api('/products?active=true');
          if (Array.isArray(prods)) {
            this._allProducts = prods;
            p = prods.find(x => x.id === pid) || null;
          }
        } catch(e) {}
      }
    } else if (productJson) {
      p = typeof productJson === 'string' ? JSON.parse(productJson) : productJson;
    }

    const cats = this._categories || await App.api('/categories');
    await this.loadUnits();
    const title = p ? `Edit Product — ${p.name}` : 'Add New Product (Product Entry)';

    App.showModal(`
      <div class="modal modal-lg">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">📦</span> ${title}</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-row">
          <div class="form-group" style="flex:2">
            <label class="form-label required">Product Name</label>
            <input class="form-control" id="p-name" value="${p?.name ? App.escapeHtml(p.name) : ''}" placeholder="e.g., Chicken Breast"
              oninput="if(!${p?.id ? 'true' : 'false'}) { const c = this.value.replace(/[^a-zA-Z0-9]/g,'').toUpperCase().slice(0,4); if(c.length===4) document.getElementById('p-code').value=c; }">
          </div>
          <div class="form-group" style="flex:1">
            <label class="form-label required">4-Letter Code (Unique)</label>
            <input class="form-control" id="p-code" maxlength="4" style="text-transform:uppercase;font-weight:700;letter-spacing:2px" value="${p?.code || ''}" placeholder="CHIC">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label required">Category</label>
            <select class="form-control" id="p-cat">
              <option value="">— Select —</option>
              ${cats.map(c => `<option value="${c.id}" ${p?.category_id == c.id ? 'selected' : ''}>${App.escapeHtml(c.name)} ${App.isGstEnabled() ? `(GST ${c.gst_rate}%)` : ''}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
              <label class="form-label required" style="margin-bottom:0">Unit</label>
              <button type="button" class="btn btn-secondary btn-sm" style="padding:1px 6px;font-size:11px;height:22px" onclick="Inventory.showManageUnitsModal()" title="Manage or Add Custom Units">⚙️ Units</button>
            </div>
            <select class="form-control" id="p-unit">
              ${(this.units && this.units.length > 0 ? this.units : [
                {name:'kg', is_discrete:0},{name:'g', is_discrete:0},{name:'litre', is_discrete:0},{name:'ml', is_discrete:0},
                {name:'piece', is_discrete:1},{name:'pcs', is_discrete:1},{name:'pack', is_discrete:1},{name:'dozen', is_discrete:1},
                {name:'box', is_discrete:1},{name:'bottle', is_discrete:1},{name:'can', is_discrete:1},{name:'tray', is_discrete:1},
                {name:'tin', is_discrete:1},{name:'strip', is_discrete:1},{name:'bag', is_discrete:1},{name:'nos', is_discrete:1}
              ]).map(u =>
                `<option value="${u.name}" ${p?.unit === u.name ? 'selected' : ''}>${u.name} (${u.is_discrete ? 'Whole Number' : 'Decimal'})</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="form-row">
          ${App.isGstEnabled() ? `
          <div class="form-group">
            <label class="form-label">HSN Code</label>
            <input class="form-control" id="p-hsn" value="${p?.hsn_code || ''}" placeholder="e.g., 0207">
          </div>` : '<input type="hidden" id="p-hsn" value="">'}
          <div class="form-group">
            <label class="form-label">Min Stock (low-stock alert)</label>
            <input class="form-control" id="p-minstock" type="number" step="0.001" value="${p?.min_stock || 1}">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label required">Purchase Price (₹) ${(!Auth.can('inventory.edit_price') && !Auth.isRole('admin', 'md', 'manager')) ? '<span class="text-muted" style="font-size:10px">(Read-only)</span>' : ''}</label>
            <div class="input-group">
              <div class="input-group-prefix">₹</div>
              <input class="form-control" id="p-purchase" type="number" step="0.01" value="${p?.purchase_price || ''}" ${(!Auth.can('inventory.edit_price') && !Auth.isRole('admin', 'md', 'manager')) ? 'readonly title="Requires inventory.edit_price permission"' : ''}>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label required">Selling Price (₹) ${(!Auth.can('inventory.edit_price') && !Auth.isRole('admin', 'md', 'manager')) ? '<span class="text-muted" style="font-size:10px">(Read-only)</span>' : ''}</label>
            <div class="input-group">
              <div class="input-group-prefix">₹</div>
              <input class="form-control" id="p-selling" type="number" step="0.01" value="${p?.selling_price || ''}" ${(!Auth.can('inventory.edit_price') && !Auth.isRole('admin', 'md', 'manager')) ? 'readonly title="Requires inventory.edit_price permission"' : ''}>
            </div>
          </div>
        </div>
        <div class="form-row">
          ${App.isGstEnabled() ? `
          <div class="form-group">
            <label class="form-label">GST Rate (%)</label>
            <select class="form-control" id="p-gst">
              ${[0,5,12,18,28].map(r => `<option value="${r}" ${p?.gst_rate == r ? 'selected' : ''}>${r}%</option>`).join('')}
            </select>
          </div>` : '<input type="hidden" id="p-gst" value="0">'}
          <div class="form-group">
            <label class="form-label">Barcode (optional)</label>
            <input class="form-control" id="p-barcode" value="${p?.barcode || ''}" placeholder="Leave blank to skip">
          </div>
          <div class="form-group">
            <label class="form-label">Shelf Life (Days)</label>
            <input class="form-control" id="p-shelflife" type="number" min="1" step="1" value="${p?.shelf_life_days || ''}" placeholder="e.g. 3">
          </div>
        </div>
        ${!p ? `
        <div class="form-group mb-12">
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-weight:600">
            <input type="checkbox" id="p-enable-openstock" onchange="Inventory.toggleOpeningStock(this.checked)" style="width:16px;height:16px;accent-color:var(--crimson)">
            <span>Specify Opening Stock / Balance</span>
          </label>
        </div>
        <div class="form-row" id="p-openstock-row" style="display:none">
          <div class="form-group">
            <label class="form-label required">Opening Stock Qty</label>
            <input class="form-control" id="p-openstock" type="number" step="0.001" placeholder="0" value="0" disabled>
          </div>
          <div class="form-group">
            <label class="form-label required">Purchase Date *</label>
            <input class="form-control" id="p-purchasedate" type="date" value="${new Date().toISOString().split('T')[0]}" disabled>
          </div>
        </div>` : ''}
        <div class="modal-footer" style="display:flex;justify-content:space-between;align-items:center;margin-top:16px">
          <div>
            ${p ? `<button type="button" class="btn btn-danger btn-sm" onclick="Inventory.deleteProduct(${p.id}, '${App.escapeHtml(p.name).replace(/'/g, "\\'")}')">🗑️ Remove Item</button>` : ''}
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <span class="text-muted" style="font-size:11px">Press <kbd style="background:rgba(0,0,0,0.12);padding:2px 6px;border-radius:4px;font-family:sans-serif">F2</kbd> or <kbd style="background:rgba(0,0,0,0.12);padding:2px 6px;border-radius:4px;font-family:sans-serif">Ctrl+Enter</kbd> to save</span>
            <button type="button" class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
            <button type="button" class="btn btn-primary" onclick="Inventory.saveProduct(${p?.id || 'null'})">
              ${p ? '💾 Update Product' : '➕ Add Product'}
            </button>
          </div>
        </div>
      </div>`);

    // Add F2 or Ctrl+Enter shortcut handler to modal
    setTimeout(() => {
      const nameInput = document.getElementById('p-name');
      if (nameInput) nameInput.focus();

      const modalKeyHandler = (e) => {
        const overlay = document.getElementById('main-modal');
        if (!overlay || !overlay.classList.contains('active')) {
          window.removeEventListener('keydown', modalKeyHandler, true);
          return;
        }
        if (e.key === 'F2' || (e.key === 'Enter' && (e.ctrlKey || e.metaKey))) {
          e.preventDefault();
          e.stopPropagation();
          Inventory.saveProduct(p?.id || null);
        }
      };
      window.addEventListener('keydown', modalKeyHandler, true);
    }, 80);

    // Auto-fill GST from category
    document.getElementById('p-cat')?.addEventListener('change', function() {
      const cat = (Inventory._categories || []).find(c => String(c.id) === this.value);
      if (cat) document.getElementById('p-gst').value = cat.gst_rate;
    });
  },

  async saveProduct(id) {
    const name = document.getElementById('p-name').value.trim();
    if (!name) { App.toast('Product name required', 'error'); return; }
    const code = document.getElementById('p-code').value.trim().toUpperCase();
    if (!code || code.length !== 4) { App.toast('4-letter product code is required (e.g. CHIC)', 'error'); return; }
    // Check for duplicate names or codes locally
    const allProds = this._allProducts || (typeof TallyInventory !== 'undefined' ? TallyInventory._products : []) || [];
    const dupName = allProds.find(p => p.id != id && (p.name || '').trim().toLowerCase() === name.toLowerCase());
    if (dupName) {
      App.toast(`Product duplication is not allowed. A product named "${dupName.name}" already exists in the catalog!`, 'error');
      document.getElementById('p-name')?.focus();
      return;
    }
    const dupCode = allProds.find(p => p.id != id && (p.code || '').trim().toUpperCase() === code);
    if (dupCode) {
      App.toast(`Product code "${code}" already exists on product "${dupCode.name}". Please choose a unique 4-letter code!`, 'error');
      document.getElementById('p-code')?.focus();
      return;
    }

    const purchasePrice = parseFloat(document.getElementById('p-purchase')?.value || 0) || 0;
    const sellingPrice = parseFloat(document.getElementById('p-selling')?.value || 0) || 0;
    const hsnVal = document.getElementById('p-hsn')?.value || '';
    const gstVal = document.getElementById('p-gst')?.value || '0';

    const enableOpenstock = document.getElementById('p-enable-openstock')?.checked || false;
    let openStock = 0;
    let purchaseDate = null;
    if (!id && enableOpenstock) {
      openStock = parseFloat(document.getElementById('p-openstock')?.value || 0);
      purchaseDate = document.getElementById('p-purchasedate')?.value || '';
      if (!purchaseDate) {
        App.toast('Purchase date is required when specifying opening stock', 'error');
        document.getElementById('p-purchasedate')?.focus();
        return;
      }
    }

    const payload = {
      name,
      code,
      category_id: parseInt(document.getElementById('p-cat')?.value) || null,
      hsn_code:    hsnVal,
      unit:        document.getElementById('p-unit')?.value || 'kg',
      purchase_price: purchasePrice,
      selling_price: sellingPrice,
      gst_rate:    parseFloat(gstVal) || 0,
      min_stock:   parseFloat(document.getElementById('p-minstock')?.value || 1) || 1,
      current_stock: id ? undefined : (enableOpenstock ? openStock : 0),
      purchase_date: id ? undefined : (enableOpenstock ? purchaseDate : null),
      barcode:     document.getElementById('p-barcode')?.value || null,
      shelf_life_days: parseInt(document.getElementById('p-shelflife')?.value) || null,
    };

    try {
      if (id) {
        await App.api(`/products/${id}`, 'PUT', payload);
        App.toast('Product updated', 'success');
      } else {
        await App.api('/products', 'POST', payload);
        App.toast('Product added', 'success');
      }
      App.closeModal();
      if (typeof TallyInventory !== 'undefined' && TallyInventory._currentView === 'products') {
        TallyInventory.openProducts();
      } else if (typeof TallyInventory !== 'undefined') {
        TallyInventory.render();
      } else {
        this.render();
      }
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async deleteProduct(id, name) {
    if (!name && typeof id === 'object') {
      name = id.name;
      id = id.id;
    }
    
    let prod = null;
    try {
      prod = await App.api(`/products/${id}`);
    } catch(e) {
      prod = { id, name: name || `Item #${id}`, bill_count: 0 };
    }

    const pName = prod.name || name || `Item #${id}`;
    const billCount = prod.bill_count || 0;

    if (billCount > 0) {
      App.showModal(`
        <div class="modal" style="max-width:500px;border-top:5px solid #dc2626">
          <div class="modal-header">
            <div class="modal-title text-danger" style="display:flex;align-items:center;gap:8px;font-weight:800;color:#dc2626">
              <span style="font-size:24px">🚫</span> CANNOT DELETE BILLED PRODUCT
            </div>
            <button class="modal-close" onclick="App.closeModal()">✕</button>
          </div>
          <div style="padding:18px 20px">
            <div style="background:rgba(239,68,68,0.08);border:1.5px solid rgba(239,68,68,0.3);border-radius:8px;padding:14px;margin-bottom:16px">
              <div style="font-weight:800;color:#991b1b;font-size:15px;margin-bottom:6px">
                "${App.escapeHtml(pName)}" is billed in ${billCount} invoice(s)!
              </div>
              <div style="font-size:13px;color:#7f1d1d;line-height:1.6">
                This product cannot be deleted until all <strong>${billCount} associated bill(s)</strong> are deleted or cancelled first.<br><br>
                <em>This rule guarantees accounting integrity and accurate historical audit logs.</em>
              </div>
            </div>
            <p style="font-size:12px;color:#64748b;margin:0">To remove this product from your catalog, please cancel or delete the corresponding invoices in <strong>Bill History</strong> first.</p>
          </div>
          <div class="modal-footer" style="display:flex;justify-content:flex-end;gap:10px;padding:12px 20px;background:#f8fafc;border-top:1px solid #e2e8f0">
            <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
            <button class="btn btn-primary" onclick="App.closeModal(); Billing.renderHistory();">📜 Go to Bill History</button>
          </div>
        </div>
      `);
      return;
    }

    App.showModal(`
      <div class="modal" style="max-width:500px;border-top:5px solid #ef4444">
        <div class="modal-header">
          <div class="modal-title text-danger" style="display:flex;align-items:center;gap:8px;font-weight:800;color:#dc2626">
            <span style="font-size:24px">⚠️</span> CAUTION: Deactivate Product
          </div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div style="padding:16px 20px">
          <div style="background:rgba(239,68,68,0.08);border:1.5px solid rgba(239,68,68,0.3);border-radius:8px;padding:14px;margin-bottom:16px">
            <div style="font-weight:800;color:#991b1b;font-size:16px;margin-bottom:8px">
              Are you sure you want to deactivate "${App.escapeHtml(pName)}"?
            </div>
            <div style="font-size:13px;color:#7f1d1d;line-height:1.6">
              • The product will be <strong>hidden from POS billing</strong> and stock screens.<br>
              • No active bills exist for this product.<br>
              • You can reactivate this product anytime from Stock Items.
            </div>
          </div>
          <p style="font-size:13px;color:#475569;margin:0">Click below to confirm deactivation of this product catalog item.</p>
        </div>
        <div class="modal-footer" style="display:flex;justify-content:flex-end;gap:10px;padding:12px 20px;background:#f8fafc;border-top:1px solid #e2e8f0">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-danger" style="background:#dc2626;border-color:#dc2626;font-weight:700;padding:8px 20px" onclick="Inventory._confirmDeleteProduct(${id})">
            🗑️ Yes, Deactivate Product
          </button>
        </div>
      </div>
    `);
  },

  async _confirmDeleteProduct(id) {
    try {
      await App.api(`/products/${id}`, 'DELETE');
      App.toast('Product deactivated successfully', 'warning');
      App.closeModal();
      if (typeof TallyInventory !== 'undefined' && TallyInventory._currentView === 'products') {
        TallyInventory.openProducts();
      } else if (typeof TallyInventory !== 'undefined') {
        TallyInventory.render();
      } else {
        this.render();
      }
    } catch(e) {
      App.showModal(`
        <div class="modal" style="max-width:480px;border-top:5px solid #dc2626">
          <div class="modal-header">
            <div class="modal-title text-danger" style="font-weight:800;color:#dc2626">🚫 Deactivation Blocked</div>
            <button class="modal-close" onclick="App.closeModal()">✕</button>
          </div>
          <div style="padding:16px 20px;font-size:14px;color:#7f1d1d;line-height:1.5">
            ${App.escapeHtml(e.message)}
          </div>
          <div class="modal-footer" style="display:flex;justify-content:flex-end;padding:12px 20px;background:#f8fafc">
            <button class="btn btn-secondary" onclick="App.closeModal()">OK</button>
          </div>
        </div>
      `);
    }
  },

  async quickStockIn(productJson) {
    const hasMissing = await this.checkAndShowMissingDatesModal();
    if (hasMissing) return;

    const p = typeof productJson === 'string' ? JSON.parse(productJson) : productJson;
    const suppliers = await App.api('/suppliers');
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">⬆️</span> Quick Stock In</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div style="padding:4px 0 16px">
          <div class="badge badge-gold" style="font-size:13px;padding:6px 14px">${p.name}</div>
          <div class="text-muted text-sm mt-8">Current: ${App.fmtNum(p.current_stock)} ${p.unit}</div>
        </div>
        <div class="form-group">
          <label class="form-label required">Date of Purchase</label>
          <input class="form-control" id="si-purchasedate" type="date" value="${new Date().toISOString().slice(0,10)}">
        </div>
        <div class="form-group">
          <label class="form-label required">Quantity (${p.unit})</label>
          <input class="form-control" id="si-qty" type="number" step="0.001" placeholder="0" autofocus>
        </div>
        <div class="form-group">
          <label class="form-label">Purchase Price (₹/${p.unit})</label>
          <input class="form-control" id="si-price" type="number" step="0.01" value="${p.purchase_price}">
        </div>
        <div class="form-group">
          <label class="form-label">Supplier</label>
          <select class="form-control" id="si-supplier">
            <option value="">— Select supplier —</option>
            ${suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Expiry Date</label>
          <input class="form-control" id="si-expiry" type="date">
        </div>
        <div class="form-group">
          <label class="form-label">Notes</label>
          <input class="form-control" id="si-notes" placeholder="Optional">
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-success" onclick="Inventory.saveStockIn(${p.id})">⬆️ Add Stock</button>
        </div>
      </div>`);
  },

  async saveStockIn(productId) {
    const qty = parseFloat(document.getElementById('si-qty').value);
    if (!qty || qty <= 0) { App.toast('Enter valid quantity', 'error'); return; }
    try {
      await App.api('/stock/in', 'POST', {
        product_id:    productId,
        quantity:      qty,
        purchase_date: document.getElementById('si-purchasedate')?.value || new Date().toISOString().slice(0,10),
        unit_price:    parseFloat(document.getElementById('si-price').value) || 0,
        supplier_id:   parseInt(document.getElementById('si-supplier').value) || null,
        expiry_date:   document.getElementById('si-expiry').value || null,
        notes:         document.getElementById('si-notes').value,
      });
      App.closeModal();
      App.toast('Stock added successfully', 'success');
      this.render();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async showWastageModal() {
    const products = await App.api('/products?active=true');
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">⚠️</span> Record Wastage</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label required">Product</label>
          <select class="form-control" id="w-product">
            <option value="">— Select product —</option>
            ${products.map(p => `<option value="${p.id}" data-stock="${p.current_stock}" data-unit="${p.unit}">${p.name} (${App.fmtNum(p.current_stock)} ${p.unit})</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label required">Quantity Lost</label>
          <input class="form-control" id="w-qty" type="number" step="0.001" placeholder="0">
        </div>
        <div class="form-group">
          <label class="form-label required">Reason</label>
          <select class="form-control" id="w-reason">
            <option>Expired</option><option>Spoiled</option><option>Damaged</option>
            <option>Lost</option><option>Other</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Notes</label>
          <textarea class="form-control" id="w-notes" placeholder="Additional details"></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-danger" onclick="Inventory.saveWastage()">⚠️ Record Wastage</button>
        </div>
      </div>`);
  },

  async saveWastage() {
    const productId = document.getElementById('w-product').value;
    const qty = parseFloat(document.getElementById('w-qty').value);
    if (!productId) { App.toast('Select product', 'error'); return; }
    if (!qty || qty <= 0) { App.toast('Enter valid quantity', 'error'); return; }
    const reason = document.getElementById('w-reason').value;
    const notes = `${reason}: ${document.getElementById('w-notes').value}`;
    try {
      await App.api('/stock/wastage', 'POST', { product_id: parseInt(productId), quantity: qty, notes });
      App.closeModal();
      App.toast('Wastage recorded', 'warning');
      this.render();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async showStockHistory(productId, productName) {
    const txns = await App.api(`/stock/transactions?product_id=${productId}&limit=50`);
    App.showModal(`
      <div class="modal modal-lg">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">📋</span> Stock History — ${productName}</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        ${txns.length === 0
          ? '<div class="empty-state"><div class="empty-state-icon">📋</div><h3>No transactions yet</h3></div>'
          : `<div class="table-wrap" style="max-height:400px;overflow-y:auto">
              <table>
                <thead><tr>
                  <th>Date</th><th>Type</th><th>Quantity</th>
                  <th class="text-right">Unit Price</th><th>Supplier</th><th>Notes</th>
                </tr></thead>
                <tbody>
                  ${txns.map(t => {
                    const typeMap = { in:'<span class="badge badge-success">📦 In</span>',
                      out:'<span class="badge badge-crimson">📤 Out</span>',
                      wastage:'<span class="badge badge-warning">⚠️ Wastage</span>',
                      adjustment:'<span class="badge badge-info">🔧 Adj</span>' };
                    return `<tr>
                      <td class="td-muted">${App.fmtDateTime(t.date)}</td>
                      <td>${typeMap[t.type] || t.type}</td>
                      <td class="font-bold">${App.fmtNum(t.quantity)}</td>
                      <td class="td-number">${t.unit_price ? App.fmt(t.unit_price) : '—'}</td>
                      <td class="td-muted">${t.supplier_name || '—'}</td>
                      <td class="td-muted" style="font-size:12px">${t.notes || '—'}</td>
                    </tr>`;
                  }).join('')}
                </tbody>
              </table>
            </div>`}
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
        </div>
      </div>`);
  },

  // ─── Stock-In Page ────────────────────────────────────────────────────────
  async renderStockIn() {
    const hasMissing = await this.checkAndShowMissingDatesModal();
    if (hasMissing) {
      const content = document.getElementById('page-content');
      content.innerHTML = `
        <div class="page-enter">
          <div class="card" style="text-align:center;padding:40px;border:2px dashed var(--warning)">
            <span style="font-size:48px">⚠️</span>
            <h2>Missing Stock Purchase Dates</h2>
            <p class="text-muted mt-8">Please enter the purchase dates for your missing stock batches in the popup window before proceeding to Stock In.</p>
            <button class="btn btn-primary mt-16" onclick="Inventory.checkAndShowMissingDatesModal()">📋 Open Missing Dates Window</button>
          </div>
        </div>`;
      return;
    }

    const content = document.getElementById('page-content');
    try {
      const [products, suppliers, txns, pending] = await Promise.all([
        App.api('/products?active=true'),
        App.api('/suppliers'),
        App.api('/stock/transactions?type=in&limit=50'),
        App.api('/stock/pending'),
      ]);

      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>⬆️ Stock In & Verification</h1>
              <p>Record incoming stock and verify accountant stock entries</p>
            </div>
            <div style="display:flex;gap:8px">
              ${(Auth.can('stock.in') || Auth.isRole('admin','md','manager')) ? `
              <button class="btn btn-primary" style="background:#7c3aed;border-color:#7c3aed;font-weight:700" onclick="Inventory.showBulkStockInModal()">
                📊 Bulk Stock Entry
              </button>` : ''}
              ${(Auth.can('inventory.create') || Auth.isRole('admin','md','manager')) ? `
              <button class="btn btn-secondary" onclick="Inventory.showProductModal()">
                ➕ New Product
              </button>` : ''}
            </div>
          </div>

          ${pending.length > 0 ? `
          <div class="card mb-16" style="border:2px solid var(--warning);background:rgba(243,156,18,0.06)">
            <div class="card-title" style="color:var(--warning)">
              <span class="card-title-icon">⏳</span> Stock Verification Queue (${pending.length} Pending Approval)
            </div>
            <p class="text-muted text-sm mb-16">
              Stock entries submitted by Accountant require Manager or Managing Director approval before adding to inventory.
            </p>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>Submitted By</th><th>Product</th><th>Code</th><th>Qty</th><th>Price</th><th>Supplier</th><th>Date</th><th>Verification Action</th></tr>
                </thead>
                <tbody>
                  ${pending.map(p => `
                    <tr>
                      <td><span class="badge badge-info">👤 @${p.created_by || 'accountant'}</span></td>
                      <td class="font-bold">${p.product_name}</td>
                      <td><span class="badge badge-gold" style="font-family:monospace">[${p.product_code || ''}]</span></td>
                      <td class="font-bold text-success">+${App.fmtNum(p.quantity)} ${p.unit || ''}</td>
                      <td>${p.unit_price ? App.fmt(p.unit_price) : '—'}</td>
                      <td class="td-muted">${p.supplier_name || '—'}</td>
                      <td class="td-muted">${App.fmtDateTime(p.date)}</td>
                      <td>
                        ${Auth.isRole('admin', 'manager', 'md') ? `
                          <div style="display:flex;gap:6px">
                            <button class="btn btn-success btn-sm" onclick="Inventory.verifyStock(${p.id}, 'approve')">✅ Approve & Add</button>
                            <button class="btn btn-danger btn-sm" onclick="Inventory.verifyStock(${p.id}, 'reject')">❌ Reject</button>
                          </div>
                        ` : '<span class="badge badge-warning">⏳ Awaiting Manager / MD Approval</span>'}
                      </td>
                    </tr>`).join('')}
                </tbody>
              </table>
            </div>
          </div>` : ''}

          <div class="grid-2" style="gap:20px;align-items:start">
            <div class="card">
              <div class="card-title"><span class="card-title-icon">⬆️</span> Add Stock Entry</div>
              ${Auth.isRole('accountant') ? `
                <div style="padding:8px 12px;background:var(--info-bg);border:1px solid rgba(52,152,219,.3);border-radius:var(--r-md);font-size:12px;color:var(--info);margin-bottom:12px">
                  ℹ️ Stock entries submitted by Accountant will be sent to Manager / MD for verification before updating inventory stock.
                </div>
              ` : ''}
              <div class="form-group">
                <label class="form-label required">Product</label>
                <select class="form-control" id="si-product">
                  <option value="">— Select product —</option>
                  ${products.map(p => `<option value="${p.id}" data-price="${p.purchase_price}" data-unit="${p.unit}">${p.name} [${p.code || ''}] (Current: ${App.fmtNum(p.current_stock)} ${p.unit})</option>`).join('')}
                </select>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label required">Date of Purchase</label>
                  <input class="form-control" id="si-purchasedate" type="date" value="${new Date().toISOString().slice(0,10)}">
                </div>
                <div class="form-group">
                  <label class="form-label required">Quantity</label>
                  <input class="form-control" id="si-qty" type="number" step="0.001" placeholder="0">
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Purchase Price (₹)</label>
                  <input class="form-control" id="si-price" type="number" step="0.01" placeholder="0.00">
                </div>
                <div class="form-group">
                  <label class="form-label">Supplier</label>
                  <select class="form-control" id="si-supplier">
                    <option value="">— Optional —</option>
                    ${suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
                  </select>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Expiry Date</label>
                  <input class="form-control" id="si-expiry" type="date">
                </div>
                <div class="form-group">
                  <label class="form-label">Notes / Batch / Invoice Ref</label>
                  <input class="form-control" id="si-notes" placeholder="Invoice number, batch, etc.">
                </div>
              </div>
              <button class="btn btn-success w-full" onclick="Inventory.submitStockIn()">⬆️ Add Stock Entry</button>
            </div>

            <div class="card">
              <div class="card-title"><span class="card-title-icon">📋</span> Recent Stock In</div>
              ${txns.length === 0
                ? '<div class="empty-state"><div class="empty-state-icon">📦</div><p>No stock entries yet</p></div>'
                : `<div class="table-wrap">
                    <table>
                      <thead><tr><th>Product</th><th>Qty</th><th>Status</th><th>Submitted By</th><th>Pur. Date</th></tr></thead>
                      <tbody>
                        ${txns.map(t => `
                          <tr>
                            <td class="font-semibold">${t.product_name || '—'}</td>
                            <td class="font-bold text-success">+${App.fmtNum(t.quantity)}</td>
                            <td>${t.status === 'approved'
                              ? '<span class="badge badge-success">Approved</span>'
                              : t.status === 'rejected'
                              ? '<span class="badge badge-danger">Rejected</span>'
                              : `<div style="display:flex;align-items:center;gap:6px">
                                   <span class="badge badge-warning">Pending Approval</span>
                                   ${(Auth.isRole('admin', 'md', 'manager') || Auth.can('stock.verify')) ? `
                                     <button class="btn btn-success btn-sm" onclick="Inventory.verifyStock(${t.id}, 'approve')" style="padding:2px 8px;font-size:10.5px;font-weight:700">✅ Approve & Add</button>
                                   ` : ''}
                                 </div>`}</td>
                            <td class="td-muted">@${t.created_by || 'system'}</td>
                            <td class="td-muted">${t.purchase_date ? App.fmtDate(t.purchase_date) : App.fmtDateTime(t.date)}</td>
                          </tr>`).join('')}
                      </tbody>
                    </table>
                  </div>`}
            </div>
          </div>
        </div>`;

      document.getElementById('si-product')?.addEventListener('change', function() {
        const opt = this.options[this.selectedIndex];
        const price = opt.dataset.price;
        if (price) document.getElementById('si-price').value = price;
      });
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  async verifyStock(txId, action) {
    try {
      const res = await App.api(`/stock/verify/${txId}`, 'POST', { action });
      App.toast(res.message, action === 'approve' ? 'success' : 'warning');
      this.renderStockIn();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async submitStockIn() {
    const productId = parseInt(document.getElementById('si-product').value);
    const qty = parseFloat(document.getElementById('si-qty').value);
    if (!productId) { App.toast('Select product', 'error'); return; }
    if (!qty || qty <= 0) { App.toast('Enter valid quantity', 'error'); return; }
    try {
      await App.api('/stock/in', 'POST', {
        product_id:    productId,
        quantity:      qty,
        purchase_date: document.getElementById('si-purchasedate')?.value || new Date().toISOString().slice(0,10),
        unit_price:    parseFloat(document.getElementById('si-price').value) || 0,
        supplier_id:   parseInt(document.getElementById('si-supplier').value) || null,
        expiry_date:   document.getElementById('si-expiry').value || null,
        notes:         document.getElementById('si-notes').value,
      });
      App.toast('Stock added!', 'success');
      this.renderStockIn();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  printProductBarcode(productId, productName, barcodeVal, price, unit, code) {
    const item = {
      id: productId,
      name: productName,
      code: code || '',
      barcode: barcodeVal || code || '',
      selling_price: price || 0,
      unit: unit || '',
      qty: 1,
    };
    const encoded = btoa(JSON.stringify([item]));
    window.open(`/printables/barcodes?items=${encodeURIComponent(encoded)}`, '_blank');
  },

  // ─── Categories Page ──────────────────────────────────────────────────────
  async renderCategories() {
    const content = document.getElementById('page-content');
    try {
      const cats = await App.api('/categories');
      this._categories = cats;
      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>🏷️ Categories</h1>
              <p>Manage product categories with GST rates and hierarchy</p>
            </div>
            <button class="btn btn-primary" onclick="Inventory.showCategoryModal()">➕ Add Category</button>
          </div>
          <div class="card">
            <div class="table-wrap">
              <table>
                <thead><tr><th>Category</th><th>Master Item</th><th>HSN Code</th><th>GST Rate</th><th>Description</th><th>Actions</th></tr></thead>
                <tbody>
                  ${cats.map(c => {
                    const parentCat = c.parent_category_id ? cats.find(p => p.id === c.parent_category_id) : null;
                    return `
                    <tr>
                      <td class="font-bold">${c.name}</td>
                      <td>${parentCat ? `<span class="badge badge-info">📁 ${parentCat.name}</span>` : '<span class="text-muted">— Master Item —</span>'}</td>
                      <td><span class="badge badge-info" style="display:inline-flex">${c.hsn_code || '—'}</span></td>
                      <td><span class="badge badge-gold">${c.gst_rate}%</span></td>
                      <td class="td-muted">${c.description || '—'}</td>
                      <td>
                        <div style="display:flex;gap:6px">
                          <button class="btn btn-secondary btn-sm btn-icon" onclick="Inventory.showCategoryModal(${c.id})" title="Edit">✏️</button>
                          <button class="btn btn-danger btn-sm btn-icon" onclick="Inventory.deleteCategory(${c.id},'${c.name.replace(/'/g, "\\'")}')" title="Delete">🗑️</button>
                        </div>
                      </td>
                    </tr>`;
                  }).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>`;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  showCategoryModal(catId = null) {
    const c = (catId && this._categories) ? this._categories.find(item => item.id === catId) : null;
    const allCats = this._categories || [];
    const parentOptions = allCats
      .filter(cat => !c || cat.id !== c.id)
      .map(cat => `<option value="${cat.id}" ${c?.parent_category_id == cat.id ? 'selected' : ''}>${cat.name}</option>`)
      .join('');

    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">🏷️</span> ${c ? 'Edit' : 'Add'} Category</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label required">Category Name</label>
          <input class="form-control" id="cat-name" value="${c?.name ? c.name.replace(/"/g, '&quot;') : ''}" placeholder="e.g., Chicken">
        </div>
        <div class="form-group">
          <label class="form-label">Master Item (optional)</label>
          <select class="form-control" id="cat-parent">
            <option value="">-- None (Master Item) --</option>
            ${parentOptions}
          </select>
        </div>
        ${App.isGstEnabled() ? `
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">HSN Code</label>
            <input class="form-control" id="cat-hsn" value="${c?.hsn_code ? c.hsn_code.replace(/"/g, '&quot;') : ''}" placeholder="e.g., 0207">
          </div>
          <div class="form-group">
            <label class="form-label">GST Rate (%)</label>
            <select class="form-control" id="cat-gst">
              ${[0,5,12,18,28].map(r => `<option value="${r}" ${c?.gst_rate == r ? 'selected' : ''}>${r}%</option>`).join('')}
            </select>
          </div>
        </div>` : '<input type="hidden" id="cat-hsn" value=""><input type="hidden" id="cat-gst" value="0">'}
        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea class="form-control" id="cat-desc">${c?.description || ''}</textarea>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Inventory.saveCategory(${c?.id || 'null'})">${c ? 'Update' : 'Add'} Category</button>
        </div>
      </div>`);
  },

  async saveCategory(id) {
    const name = document.getElementById('cat-name').value.trim();
    if (!name) { App.toast('Category name required', 'error'); return; }
    const parentVal = document.getElementById('cat-parent')?.value;
    const payload = {
      name,
      parent_category_id: parentVal ? parseInt(parentVal) : null,
      hsn_code: document.getElementById('cat-hsn').value.trim(),
      gst_rate: parseFloat(document.getElementById('cat-gst').value || 0),
      description: document.getElementById('cat-desc').value.trim(),
    };
    try {
      if (id && id !== 'null') {
        await App.api(`/categories/${id}`, 'PUT', payload);
        App.toast('Category updated', 'success');
      } else {
        await App.api('/categories', 'POST', payload);
        App.toast('Category added', 'success');
      }
      App.closeModal();
      this.renderCategories();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async deleteCategory(id, name) {
    App.confirm(`Delete category "${name}"?`, 'Delete Category', async () => {
      await App.api(`/categories/${id}`, 'DELETE');
      App.toast('Deleted', 'success');
      this.renderCategories();
    });
  },

  // ─── Purchase Orders Page ─────────────────────────────────────────────────
  async renderPurchaseOrders() {
    const content = document.getElementById('page-content');
    try {
      const [pos, suppliers, products] = await Promise.all([
        App.api('/purchase-orders'),
        App.api('/suppliers'),
        App.api('/products?active=true'),
      ]);

      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>🛒 Purchase Orders</h1>
              <p>Record purchases from suppliers</p>
            </div>
            <button class="btn btn-primary" onclick="Inventory.showPOModal()">➕ New Purchase Order</button>
          </div>

          <div class="card">
            ${pos.length === 0
              ? '<div class="empty-state"><div class="empty-state-icon">🛒</div><h3>No purchase orders yet</h3></div>'
              : `<div class="table-wrap">
                  <table>
                    <thead><tr><th>PO No</th><th>Supplier</th><th>Date</th><th class="text-right">Total</th><th class="text-right">Paid</th><th>Status</th></tr></thead>
                    <tbody>
                      ${pos.map(po => `
                        <tr>
                          <td class="font-bold text-gold">${po.po_no}</td>
                          <td>${po.supplier_name || '—'}</td>
                          <td class="td-muted">${App.fmtDateTime(po.date)}</td>
                          <td class="td-number">${App.fmt(po.total)}</td>
                          <td class="td-number ${po.amount_paid >= po.total ? 'text-success' : 'text-warning'}">${App.fmt(po.amount_paid)}</td>
                          <td><span class="badge badge-success">${po.status}</span></td>
                        </tr>`).join('')}
                    </tbody>
                  </table>
                </div>`}
          </div>
        </div>`;

      this._suppliers = suppliers;
      this._products = products;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  _poItems: [],

  showPOModal() {
    this._poItems = [];
    const suppliers = this._suppliers || [];
    const products = this._products || [];
    App.showModal(`
      <div class="modal modal-xl">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">🛒</span> New Purchase Order</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Supplier</label>
            <select class="form-control" id="po-supplier">
              <option value="">— Select supplier —</option>
              ${suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Notes</label>
            <input class="form-control" id="po-notes" placeholder="Invoice number, reference…">
          </div>
        </div>
        <div class="divider"></div>
        <div class="section-title">📦 Items</div>
        <div style="display:flex;gap:12px;margin-bottom:12px;align-items:flex-end">
          <div class="form-group" style="flex:2;margin-bottom:0">
            <label class="form-label">Product</label>
            <select class="form-control" id="po-add-product">
              <option value="">— Select —</option>
              ${products.map(p => `<option value="${p.id}" data-price="${p.purchase_price}" data-name="${p.name}" data-unit="${p.unit}">${p.name} (${p.unit})</option>`).join('')}
            </select>
          </div>
          <div class="form-group" style="flex:1;margin-bottom:0">
            <label class="form-label">Quantity</label>
            <input class="form-control" id="po-add-qty" type="number" step="0.001" placeholder="0">
          </div>
          <div class="form-group" style="flex:1;margin-bottom:0">
            <label class="form-label">Price/unit (₹)</label>
            <input class="form-control" id="po-add-price" type="number" step="0.01" placeholder="0">
          </div>
          <button class="btn btn-success" onclick="Inventory.addPOItem()">➕ Add</button>
        </div>
        <div id="po-items-table"><div class="empty-state" style="padding:20px"><p>Add items above</p></div></div>
        <div class="divider"></div>
        <div style="display:flex;justify-content:flex-end;gap:16px;align-items:center">
          <div style="font-size:16px;font-weight:700">Total: <span id="po-total" class="text-gold">₹0.00</span></div>
        </div>
        <div class="form-group mt-16">
          <label class="form-label">Amount Paid (₹)</label>
          <input class="form-control" id="po-paid" type="number" step="0.01" placeholder="0">
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Inventory.savePO()">💾 Create Purchase Order & Update Stock</button>
        </div>
      </div>`);

    document.getElementById('po-add-product')?.addEventListener('change', function() {
      const opt = this.options[this.selectedIndex];
      if (opt.dataset.price) document.getElementById('po-add-price').value = opt.dataset.price;
    });
  },

  addPOItem() {
    const productEl = document.getElementById('po-add-product');
    const opt = productEl.options[productEl.selectedIndex];
    if (!productEl.value) { App.toast('Select product', 'error'); return; }
    const qty = parseFloat(document.getElementById('po-add-qty').value);
    const price = parseFloat(document.getElementById('po-add-price').value);
    if (!qty || qty <= 0) { App.toast('Enter valid quantity', 'error'); return; }
    if (!price || price < 0) { App.toast('Enter valid price', 'error'); return; }
    this._poItems.push({
      product_id: parseInt(productEl.value),
      product_name: opt.dataset.name,
      unit: opt.dataset.unit,
      quantity: qty,
      unit_price: price,
    });
    productEl.value = '';
    document.getElementById('po-add-qty').value = '';
    document.getElementById('po-add-price').value = '';
    this.renderPOItems();
  },

  renderPOItems() {
    const total = this._poItems.reduce((s, i) => s + i.quantity * i.unit_price, 0);
    document.getElementById('po-total').textContent = App.fmt(total);
    document.getElementById('po-paid').value = total.toFixed(2);
    if (this._poItems.length === 0) {
      document.getElementById('po-items-table').innerHTML = '<div class="empty-state" style="padding:20px"><p>Add items above</p></div>';
      return;
    }
    document.getElementById('po-items-table').innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr><th>Product</th><th>Qty</th><th>Price</th><th class="text-right">Amount</th><th></th></tr></thead>
          <tbody>
            ${this._poItems.map((i, idx) => `
              <tr>
                <td class="font-semibold">${i.product_name} <span class="text-muted">(${i.unit})</span></td>
                <td>${App.fmtNum(i.quantity)}</td>
                <td>${App.fmt(i.unit_price)}</td>
                <td class="td-number font-bold">${App.fmt(i.quantity * i.unit_price)}</td>
                <td><button class="btn btn-danger btn-sm btn-icon" onclick="Inventory._poItems.splice(${idx},1);Inventory.renderPOItems()">✕</button></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  },

  async savePO() {
    if (this._poItems.length === 0) { App.toast('Add at least one item', 'error'); return; }
    try {
      await App.api('/purchase-orders', 'POST', {
        supplier_id: parseInt(document.getElementById('po-supplier').value) || null,
        notes:       document.getElementById('po-notes').value,
        amount_paid: parseFloat(document.getElementById('po-paid').value) || 0,
        status:      'received',
        items:       this._poItems,
      });
      App.closeModal();
      App.toast('Purchase order created & stock updated!', 'success');
      this.renderPurchaseOrders();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  // ─── Bulk Stock Entry ──────────────────────────────────────────────────────
  async showBulkStockInModal() {
    const hasMissing = await this.checkAndShowMissingDatesModal();
    if (hasMissing) return;

    const [products, suppliers] = await Promise.all([
      App.api('/products?active=true'),
      App.api('/suppliers')
    ]);
    const today = new Date().toISOString().slice(0, 10);
    this._bulkProducts = products;
    this._bulkSuppliers = suppliers;

    const prodOptions = products.map(p =>
      `<option value="${p.id}" data-price="${p.purchase_price||0}" data-unit="${p.purchase_unit||p.unit||'kg'}">${p.name} [${p.code||''}] (Stock: ${App.fmtNum(p.current_stock)} ${p.unit||''})</option>`
    ).join('');

    const renderRow = (idx) => `
      <tr class="bulk-stock-row" id="bsi-row-${idx}">
        <td style="text-align:center;color:#888;font-weight:600">${idx + 1}</td>
        <td>
          <select class="form-control bsi-product" data-row="${idx}" onchange="Inventory._onBulkProductChange(this, ${idx})">
            <option value="">— Select Product —</option>
            ${prodOptions}
          </select>
        </td>
        <td>
          <input type="number" step="0.001" min="0" placeholder="0" class="form-control bsi-qty num" data-row="${idx}" oninput="Inventory._recalcBulkTotals()">
        </td>
        <td class="bsi-unit-cell" id="bsi-unit-${idx}" style="text-align:center;color:#666;font-size:12px">—</td>
        <td>
          <input type="number" step="0.01" min="0" placeholder="0.00" class="form-control bsi-price num" data-row="${idx}" oninput="Inventory._recalcBulkTotals()">
        </td>
        <td>
          <input type="date" class="form-control bsi-expiry" data-row="${idx}">
        </td>
        <td>
          <input type="text" placeholder="Batch No." class="form-control bsi-batch" data-row="${idx}">
        </td>
        <td class="num font-bold bsi-amt-cell" id="bsi-amt-${idx}">—</td>
        <td style="text-align:center">
          <button class="btn btn-sm btn-danger" style="padding:2px 8px" onclick="Inventory._removeBulkRow(${idx})">🗑️</button>
        </td>
      </tr>`;

    let rowsHtml = '';
    for (let i = 0; i < 5; i++) {
      rowsHtml += renderRow(i);
    }

    App.showModal(`
      <div class="modal modal-maximized">
        <div class="modal-header" style="background:linear-gradient(135deg, #1e1b4b, #312e81);color:#fff;padding:14px 24px;margin-bottom:0;border-bottom:none;flex:0 0 auto">
          <div class="modal-title" style="color:#fff;font-size:18px;font-weight:700"><span class="modal-title-icon">📊</span> Bulk Stock Entry — Maximized Spreadsheet Mode</div>
          <button class="modal-close" style="color:#fff;font-size:22px" onclick="App.closeModal()">✕</button>
        </div>
        
        <div style="padding:20px;flex:1 1 auto;display:flex;flex-direction:column;overflow:hidden;background:var(--bg-card)">
          <!-- Top Header Form -->
          <div class="grid-4 mb-16" style="gap:16px;background:rgba(99,102,241,0.05);padding:16px;border-radius:8px;border:1px solid rgba(99,102,241,0.15);flex:0 0 auto">
            <div>
              <label class="form-label required" style="font-weight:700;color:#4338ca">Date of Purchase *</label>
              <input type="date" class="form-control" id="bsi-purchasedate" value="${today}" max="${today}" style="border-color:#6366f1;font-weight:600;height:36px">
            </div>
            <div>
              <label class="form-label">Supplier / Party</label>
              <select class="form-control" id="bsi-supplier" style="height:36px">
                <option value="">— Select Supplier (Optional) —</option>
                ${suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
              </select>
            </div>
            <div>
              <label class="form-label">Invoice / Ref No.</label>
              <input type="text" class="form-control" id="bsi-ref" placeholder="e.g. INV-9821" style="height:36px">
            </div>
            <div>
              <label class="form-label">Notes / Remarks</label>
              <input type="text" class="form-control" id="bsi-notes" placeholder="Bulk purchase remarks…" style="height:36px">
            </div>
          </div>

          <!-- Spreadsheet Table (Expands to fill remaining screen height) -->
          <div class="table-wrap mb-16" style="flex:1 1 auto;overflow-y:auto;border:1px solid var(--border);border-radius:8px">
            <table class="table" style="margin:0;width:100%">
              <thead style="position:sticky;top:0;z-index:10;background:var(--bg-input)">
                <tr>
                  <th style="width:40px;text-align:center">#</th>
                  <th style="min-width:280px">Product Item *</th>
                  <th style="width:130px" class="num">Quantity *</th>
                  <th style="width:80px;text-align:center">Unit</th>
                  <th style="width:140px" class="num">Purchase Price (₹)</th>
                  <th style="width:150px">Expiry Date</th>
                  <th style="width:140px">Batch No.</th>
                  <th style="width:140px" class="num">Amount (₹)</th>
                  <th style="width:60px;text-align:center">Action</th>
                </tr>
              </thead>
              <tbody id="bsi-table-body">
                ${rowsHtml}
              </tbody>
            </table>
          </div>

          <!-- Footer Controls & Action Bar -->
          <div style="display:flex;align-items:center;justify-content:space-between;background:var(--bg-input);padding:14px 20px;border-radius:8px;border:1px solid var(--border);flex:0 0 auto">
            <div style="display:flex;gap:8px">
              <button class="btn btn-secondary" onclick="Inventory._addBulkRow(1)">＋ Add 1 Row</button>
              <button class="btn btn-secondary" onclick="Inventory._addBulkRow(5)">＋ Add 5 Rows</button>
              <button class="btn btn-secondary" onclick="Inventory._addBulkRow(10)">＋ Add 10 Rows</button>
            </div>
            <div style="display:flex;align-items:center;gap:24px;font-size:14px">
              <span>Items: <strong id="bsi-total-items" style="font-size:15px">0</strong></span>
              <span>Total Qty: <strong id="bsi-total-qty" style="font-size:15px">0</strong></span>
              <span>Total Value: <strong id="bsi-total-val" style="color:#166534;font-size:18px;font-weight:800">₹0.00</strong></span>
            </div>
            <div style="display:flex;gap:12px">
              <button class="btn btn-secondary" onclick="App.closeModal()" style="padding:8px 18px">Cancel</button>
              <button class="btn btn-success" style="background:#16a34a;padding:10px 28px;font-weight:700;font-size:15px" onclick="Inventory.saveBulkStockIn()">
                💾 Save Bulk Stock Entry
              </button>
            </div>
          </div>
        </div>
      </div>`);

    this._bulkRowCount = 5;
    this._recalcBulkTotals();
  },

  _onBulkProductChange(sel, idx) {
    const opt = sel.selectedOptions[0];
    const price = opt?.dataset.price || '';
    const unit  = opt?.dataset.unit  || '—';
    const priceInp = document.querySelector(`.bsi-price[data-row="${idx}"]`);
    const unitCell = document.getElementById(`bsi-unit-${idx}`);
    if (priceInp && !priceInp.value) priceInp.value = price;
    if (unitCell) unitCell.textContent = unit;
    this._recalcBulkTotals();
  },

  _addBulkRow(count = 1) {
    const tbody = document.getElementById('bsi-table-body');
    if (!tbody || !this._bulkProducts) return;
    const prodOptions = this._bulkProducts.map(p =>
      `<option value="${p.id}" data-price="${p.purchase_price||0}" data-unit="${p.purchase_unit||p.unit||'kg'}">${p.name} [${p.code||''}] (Stock: ${App.fmtNum(p.current_stock)} ${p.unit||''})</option>`
    ).join('');

    for (let c = 0; c < count; c++) {
      const idx = this._bulkRowCount++;
      const tr = document.createElement('tr');
      tr.className = 'bulk-stock-row';
      tr.id = `bsi-row-${idx}`;
      tr.innerHTML = `
        <td style="text-align:center;color:#888;font-weight:600">${idx + 1}</td>
        <td>
          <select class="form-control bsi-product" data-row="${idx}" onchange="Inventory._onBulkProductChange(this, ${idx})">
            <option value="">— Select Product —</option>
            ${prodOptions}
          </select>
        </td>
        <td>
          <input type="number" step="0.001" min="0" placeholder="0" class="form-control bsi-qty num" data-row="${idx}" oninput="Inventory._recalcBulkTotals()">
        </td>
        <td class="bsi-unit-cell" id="bsi-unit-${idx}" style="text-align:center;color:#666;font-size:12px">—</td>
        <td>
          <input type="number" step="0.01" min="0" placeholder="0.00" class="form-control bsi-price num" data-row="${idx}" oninput="Inventory._recalcBulkTotals()">
        </td>
        <td>
          <input type="date" class="form-control bsi-expiry" data-row="${idx}">
        </td>
        <td>
          <input type="text" placeholder="Batch No." class="form-control bsi-batch" data-row="${idx}">
        </td>
        <td class="num font-bold bsi-amt-cell" id="bsi-amt-${idx}">—</td>
        <td style="text-align:center">
          <button class="btn btn-sm btn-danger" style="padding:2px 8px" onclick="Inventory._removeBulkRow(${idx})">🗑️</button>
        </td>`;
      tbody.appendChild(tr);
    }
  },

  _removeBulkRow(idx) {
    const tr = document.getElementById(`bsi-row-${idx}`);
    if (tr) tr.remove();
    this._recalcBulkTotals();
  },

  _recalcBulkTotals() {
    const rows = document.querySelectorAll('.bulk-stock-row');
    let validItems = 0, totalQty = 0, totalVal = 0;
    rows.forEach(r => {
      const pid = r.querySelector('.bsi-product')?.value;
      const qty = parseFloat(r.querySelector('.bsi-qty')?.value) || 0;
      const price = parseFloat(r.querySelector('.bsi-price')?.value) || 0;
      const amtCell = r.querySelector('.bsi-amt-cell');
      if (pid && qty > 0) {
        validItems++;
        totalQty += qty;
        const lineAmt = qty * price;
        totalVal += lineAmt;
        if (amtCell) amtCell.textContent = `₹${lineAmt.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
      } else if (amtCell) {
        amtCell.textContent = '—';
      }
    });

    const ti = document.getElementById('bsi-total-items');
    const tq = document.getElementById('bsi-total-qty');
    const tv = document.getElementById('bsi-total-val');
    if (ti) ti.textContent = validItems;
    if (tq) tq.textContent = App.fmtNum(totalQty);
    if (tv) tv.textContent = `₹${totalVal.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  },

  async saveBulkStockIn() {
    const pDate = document.getElementById('bsi-purchasedate')?.value;
    if (!pDate) { App.toast('Date of Purchase is required', 'error'); return; }

    const rows = document.querySelectorAll('.bulk-stock-row');
    const items = [];
    rows.forEach(r => {
      const pid = r.querySelector('.bsi-product')?.value;
      const qty = parseFloat(r.querySelector('.bsi-qty')?.value) || 0;
      const price = parseFloat(r.querySelector('.bsi-price')?.value) || 0;
      const expiry = r.querySelector('.bsi-expiry')?.value || null;
      const batchNo = r.querySelector('.bsi-batch')?.value || null;
      if (pid && qty > 0) {
        items.push({
          product_id: parseInt(pid),
          quantity: qty,
          unit_price: price,
          expiry_date: expiry,
          batch_no: batchNo
        });
      }
    });

    if (items.length === 0) {
      App.toast('Select at least one product with quantity > 0', 'error');
      return;
    }

    const payload = {
      purchase_date: pDate,
      supplier_id: parseInt(document.getElementById('bsi-supplier')?.value) || null,
      reference: document.getElementById('bsi-ref')?.value || '',
      notes: document.getElementById('bsi-notes')?.value || 'Bulk Stock Entry',
      items: items
    };

    try {
      const res = await App.api('/stock/bulk-in', 'POST', payload);
      App.closeModal();
      App.toast(res.message || 'Bulk stock entry saved successfully!', 'success');
      if (typeof TallyInventory !== 'undefined' && TallyInventory._currentView === 'summary') {
        TallyInventory.render();
      } else {
        this.renderStockIn();
      }
    } catch(e) {
      App.toast(e.message, 'error');
    }
  },

  // ─── Units Master Management ─────────────────────────────────────────────
  units: [],

  async loadUnits() {
    try {
      const res = await App.api('/units');
      this.units = (res && res.units) ? res.units : [];
      return this.units;
    } catch(e) {
      this.units = [
        { id: 1, name: 'kg', symbol: 'kg', is_discrete: 0 },
        { id: 2, name: 'g', symbol: 'g', is_discrete: 0 },
        { id: 3, name: 'litre', symbol: 'l', is_discrete: 0 },
        { id: 4, name: 'ml', symbol: 'ml', is_discrete: 0 },
        { id: 5, name: 'piece', symbol: 'pc', is_discrete: 1 },
        { id: 6, name: 'pcs', symbol: 'pcs', is_discrete: 1 },
        { id: 7, name: 'pack', symbol: 'pkt', is_discrete: 1 },
        { id: 8, name: 'dozen', symbol: 'doz', is_discrete: 1 },
        { id: 9, name: 'box', symbol: 'box', is_discrete: 1 },
        { id: 10, name: 'bottle', symbol: 'btl', is_discrete: 1 },
        { id: 11, name: 'can', symbol: 'can', is_discrete: 1 },
        { id: 12, name: 'tray', symbol: 'tray', is_discrete: 1 },
        { id: 13, name: 'tin', symbol: 'tin', is_discrete: 1 },
        { id: 14, name: 'nos', symbol: 'nos', is_discrete: 1 }
      ];
      return this.units;
    }
  },

  async showManageUnitsModal() {
    await this.loadUnits();
    const modalHtml = `
      <div class="modal modal-lg" style="max-width:560px">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">⚙️</span> Manage Product Units</div>
          <button class="modal-close" onclick="App.closeModal('modal-manage-units')">✕</button>
        </div>
        <div class="modal-body" style="padding:16px 20px">
          <div style="background:var(--bg-input, #1E293B);padding:14px;border-radius:8px;border:1px solid var(--border);margin-bottom:18px">
            <h4 style="margin-top:0;margin-bottom:10px;font-size:13px;color:var(--gold, #F59E0B);text-transform:uppercase;letter-spacing:0.5px">➕ Add New Custom Unit</h4>
            <div style="display:flex;gap:10px;flex-wrap:wrap">
              <div style="flex:2;min-width:140px">
                <label style="font-size:11px;font-weight:600;display:block;margin-bottom:4px">Unit Name *</label>
                <input id="new-unit-name" class="form-control" placeholder="e.g. carton, bundle, roll" style="padding:6px 10px;font-size:13px">
              </div>
              <div style="flex:1;min-width:90px">
                <label style="font-size:11px;font-weight:600;display:block;margin-bottom:4px">Symbol</label>
                <input id="new-unit-symbol" class="form-control" placeholder="e.g. ctn" style="padding:6px 10px;font-size:13px">
              </div>
            </div>
            <div style="margin-top:10px">
              <label style="font-size:11px;font-weight:600;display:block;margin-bottom:6px">Quantity Type *</label>
              <div style="display:flex;gap:16px;font-size:12px">
                <label style="display:inline-flex;align-items:center;gap:5px;cursor:pointer">
                  <input type="radio" name="new-unit-discrete" value="1" checked> 📦 Whole Number Only (pack, piece, carton)
                </label>
                <label style="display:inline-flex;align-items:center;gap:5px;cursor:pointer">
                  <input type="radio" name="new-unit-discrete" value="0"> ⚖️ Allows Decimals (kg, litre, meter)
                </label>
              </div>
            </div>
            <div style="margin-top:12px;text-align:right">
              <button type="button" class="btn btn-primary btn-sm" onclick="Inventory.saveCustomUnit()">+ Add Unit</button>
            </div>
          </div>

          <h4 style="margin-top:0;margin-bottom:10px;font-size:13px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px">Active Units</h4>
          <div style="max-height:260px;overflow-y:auto;border:1px solid var(--border);border-radius:6px">
            <table style="width:100%;border-collapse:collapse;font-size:12px">
              <thead>
                <tr style="background:var(--bg-input);border-bottom:1px solid var(--border)">
                  <th style="padding:8px 12px;text-align:left">Unit Name</th>
                  <th style="padding:8px 12px;text-align:left">Symbol</th>
                  <th style="padding:8px 12px;text-align:center">Quantity Mode</th>
                  <th style="padding:8px 12px;text-align:center;width:60px">Action</th>
                </tr>
              </thead>
              <tbody id="manage-units-tbody">
                ${(this.units || []).map(u => `
                  <tr style="border-bottom:1px solid var(--border)">
                    <td style="padding:8px 12px;font-weight:600">${App.escapeHtml(u.name)}</td>
                    <td style="padding:8px 12px;color:var(--text-muted)">${App.escapeHtml(u.symbol || u.name)}</td>
                    <td style="padding:8px 12px;text-align:center">
                      <span class="badge ${u.is_discrete ? 'badge-gold' : 'badge-secondary'}" style="font-size:10px">
                        ${u.is_discrete ? 'Whole Number' : 'Decimal'}
                      </span>
                    </td>
                    <td style="padding:8px 12px;text-align:center">
                      <button type="button" class="btn btn-danger btn-sm btn-icon" style="width:22px;height:22px;font-size:10px" onclick="Inventory.deleteCustomUnit(${u.id}, '${App.escapeHtml(u.name)}')" title="Remove Unit">✕</button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
        <div class="modal-footer" style="padding:10px 20px">
          <button type="button" class="btn btn-secondary" onclick="App.closeModal('modal-manage-units')">Close</button>
        </div>
      </div>
    `;
    App.showModal(modalHtml, { id: 'modal-manage-units' });
  },

  async saveCustomUnit() {
    const nameEl = document.getElementById('new-unit-name');
    const symbolEl = document.getElementById('new-unit-symbol');
    const isDiscreteEl = document.querySelector('input[name="new-unit-discrete"]:checked');
    const name = (nameEl?.value || '').trim().toLowerCase();
    const symbol = (symbolEl?.value || '').trim() || name;
    const is_discrete = isDiscreteEl ? parseInt(isDiscreteEl.value) : 1;

    if (!name) {
      App.toast('Unit name is required', 'warning');
      return;
    }

    try {
      await App.api('/units', 'POST', { name, symbol, is_discrete });
      App.toast(`Unit "${name}" added successfully!`, 'success');
      await this.loadUnits();

      const tbody = document.getElementById('manage-units-tbody');
      if (tbody) {
        tbody.innerHTML = (this.units || []).map(u => `
          <tr style="border-bottom:1px solid var(--border)">
            <td style="padding:8px 12px;font-weight:600">${App.escapeHtml(u.name)}</td>
            <td style="padding:8px 12px;color:var(--text-muted)">${App.escapeHtml(u.symbol || u.name)}</td>
            <td style="padding:8px 12px;text-align:center">
              <span class="badge ${u.is_discrete ? 'badge-gold' : 'badge-secondary'}" style="font-size:10px">
                ${u.is_discrete ? 'Whole Number' : 'Decimal'}
              </span>
            </td>
            <td style="padding:8px 12px;text-align:center">
              <button type="button" class="btn btn-danger btn-sm btn-icon" style="width:22px;height:22px;font-size:10px" onclick="Inventory.deleteCustomUnit(${u.id}, '${App.escapeHtml(u.name)}')" title="Remove Unit">✕</button>
            </td>
          </tr>
        `).join('');
      }

      const pUnit = document.getElementById('p-unit');
      if (pUnit) {
        pUnit.innerHTML = (this.units || []).map(u =>
          `<option value="${u.name}" ${u.name === name ? 'selected' : ''}>${u.name} (${u.is_discrete ? 'Whole Number' : 'Decimal'})</option>`
        ).join('');
      }
      if (nameEl) nameEl.value = '';
      if (symbolEl) symbolEl.value = '';
    } catch(e) {
      App.toast(e.message || 'Failed to add unit', 'error');
    }
  },

  async deleteCustomUnit(uid, uname) {
    App.confirm(`Remove unit "${uname}"?`, 'Delete Unit', async () => {
      try {
        await App.api(`/units/${uid}`, 'DELETE');
        App.toast(`Unit "${uname}" removed.`, 'success');
        await this.loadUnits();

        const tbody = document.getElementById('manage-units-tbody');
        if (tbody) {
          tbody.innerHTML = (this.units || []).map(u => `
            <tr style="border-bottom:1px solid var(--border)">
              <td style="padding:8px 12px;font-weight:600">${App.escapeHtml(u.name)}</td>
              <td style="padding:8px 12px;color:var(--text-muted)">${App.escapeHtml(u.symbol || u.name)}</td>
              <td style="padding:8px 12px;text-align:center">
                <span class="badge ${u.is_discrete ? 'badge-gold' : 'badge-secondary'}" style="font-size:10px">
                  ${u.is_discrete ? 'Whole Number' : 'Decimal'}
                </span>
              </td>
              <td style="padding:8px 12px;text-align:center">
                <button type="button" class="btn btn-danger btn-sm btn-icon" style="width:22px;height:22px;font-size:10px" onclick="Inventory.deleteCustomUnit(${u.id}, '${App.escapeHtml(u.name)}')" title="Remove Unit">✕</button>
              </td>
            </tr>
          `).join('');
        }

        const pUnit = document.getElementById('p-unit');
        if (pUnit) {
          const curVal = pUnit.value;
          pUnit.innerHTML = (this.units || []).map(u =>
            `<option value="${u.name}" ${u.name === curVal ? 'selected' : ''}>${u.name} (${u.is_discrete ? 'Whole Number' : 'Decimal'})</option>`
          ).join('');
        }
      } catch(e) {
        App.toast(e.message || 'Failed to remove unit', 'error');
      }
    });
  },
};

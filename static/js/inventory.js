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
                <button class="btn btn-secondary btn-sm btn-icon" onclick="Inventory.showProductModal(${JSON.stringify(JSON.stringify(p))})" title="Edit">✏️</button>
                <button class="btn btn-danger btn-sm btn-icon" onclick="Inventory.deleteProduct(${p.id},'${p.name}')" title="Deactivate">🗑️</button>
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
            <button class="btn btn-success btn-sm" style="flex:1" onclick="Inventory.quickStockIn(${JSON.stringify(JSON.stringify(p))})">
              ⬆️ Stock In
            </button>
            <button class="btn btn-secondary btn-sm" onclick="Inventory.showStockHistory(${p.id},'${p.name}')">
              📋 History
            </button>
          </div>
        </div>`;
    }).join('');
  },

  // ─── Product Modal ────────────────────────────────────────────────────────
  async showProductModal(productJson = null) {
    const p = productJson ? (typeof productJson === 'string' ? JSON.parse(productJson) : productJson) : null;
    const cats = this._categories || await App.api('/categories');
    const title = p ? 'Edit Product' : 'Add New Product';

    App.showModal(`
      <div class="modal modal-lg">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">📦</span> ${title}</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-row">
          <div class="form-group" style="flex:2">
            <label class="form-label required">Product Name</label>
            <input class="form-control" id="p-name" value="${p?.name || ''}" placeholder="e.g., Chicken Breast"
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
              ${cats.map(c => `<option value="${c.id}" ${p?.category_id == c.id ? 'selected' : ''}>${c.name} ${App.isGstEnabled() ? `(GST ${c.gst_rate}%)` : ''}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label required">Unit</label>
            <select class="form-control" id="p-unit">
              ${['kg','g','piece','pack','dozen','litre','ml'].map(u =>
                `<option ${p?.unit === u ? 'selected' : ''}>${u}</option>`).join('')}
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
            <label class="form-label required">Purchase Price (₹)</label>
            <div class="input-group">
              <div class="input-group-prefix">₹</div>
              <input class="form-control" id="p-purchase" type="number" step="0.01" value="${p?.purchase_price || ''}">
            </div>
          </div>
          <div class="form-group">
            <label class="form-label required">Selling Price (₹)</label>
            <div class="input-group">
              <div class="input-group-prefix">₹</div>
              <input class="form-control" id="p-selling" type="number" step="0.01" value="${p?.selling_price || ''}">
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
        </div>
        ${!p ? `
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Opening Stock</label>
            <input class="form-control" id="p-openstock" type="number" step="0.001" placeholder="0" value="0">
          </div>
        </div>` : ''}
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Inventory.saveProduct(${p?.id || 'null'})">
            ${p ? '💾 Update Product' : '➕ Add Product'}
          </button>
        </div>
      </div>`);

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
    const selling = parseFloat(document.getElementById('p-selling').value);
    if (!selling) { App.toast('Selling price required', 'error'); return; }

    const payload = {
      name,
      code,
      category_id: parseInt(document.getElementById('p-cat').value) || null,
      hsn_code:    document.getElementById('p-hsn').value,
      unit:        document.getElementById('p-unit').value,
      purchase_price: parseFloat(document.getElementById('p-purchase').value) || 0,
      selling_price: selling,
      gst_rate:    parseFloat(document.getElementById('p-gst').value) || 0,
      min_stock:   parseFloat(document.getElementById('p-minstock').value) || 1,
      current_stock: id ? undefined : parseFloat(document.getElementById('p-openstock')?.value || 0),
      barcode:     document.getElementById('p-barcode')?.value || null,
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
      this.render();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async deleteProduct(id, name) {
    App.confirm(`Deactivate "${name}"? It will be hidden but bill history preserved.`, 'Deactivate Product', async () => {
      await App.api(`/products/${id}`, 'DELETE');
      App.toast('Product deactivated', 'warning');
      this.render();
    });
  },

  async quickStockIn(productJson) {
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
        product_id:  productId,
        quantity:    qty,
        unit_price:  parseFloat(document.getElementById('si-price').value) || 0,
        supplier_id: parseInt(document.getElementById('si-supplier').value) || null,
        expiry_date: document.getElementById('si-expiry').value || null,
        notes:       document.getElementById('si-notes').value,
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
                        ${Auth.isRole('admin', 'manager') ? `
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
                  <label class="form-label required">Quantity</label>
                  <input class="form-control" id="si-qty" type="number" step="0.001" placeholder="0">
                </div>
                <div class="form-group">
                  <label class="form-label">Purchase Price (₹)</label>
                  <input class="form-control" id="si-price" type="number" step="0.01" placeholder="0.00">
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">Supplier</label>
                  <select class="form-control" id="si-supplier">
                    <option value="">— Optional —</option>
                    ${suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
                  </select>
                </div>
                <div class="form-group">
                  <label class="form-label">Expiry Date</label>
                  <input class="form-control" id="si-expiry" type="date">
                </div>
              </div>
              <div class="form-group">
                <label class="form-label">Notes / Batch / Invoice Ref</label>
                <input class="form-control" id="si-notes" placeholder="Invoice number, batch, etc.">
              </div>
              <button class="btn btn-success w-full" onclick="Inventory.submitStockIn()">⬆️ Add Stock Entry</button>
            </div>

            <div class="card">
              <div class="card-title"><span class="card-title-icon">📋</span> Recent Stock In</div>
              ${txns.length === 0
                ? '<div class="empty-state"><div class="empty-state-icon">📦</div><p>No stock entries yet</p></div>'
                : `<div class="table-wrap">
                    <table>
                      <thead><tr><th>Product</th><th>Qty</th><th>Status</th><th>Submitted By</th><th>Date</th></tr></thead>
                      <tbody>
                        ${txns.map(t => `
                          <tr>
                            <td class="font-semibold">${t.product_name || '—'}</td>
                            <td class="font-bold text-success">+${App.fmtNum(t.quantity)}</td>
                            <td>${t.status === 'approved'
                              ? '<span class="badge badge-success">Approved</span>'
                              : t.status === 'rejected'
                              ? '<span class="badge badge-danger">Rejected</span>'
                              : '<span class="badge badge-warning">Pending Approval</span>'}</td>
                            <td class="td-muted">@${t.created_by || 'system'}</td>
                            <td class="td-muted">${App.fmtDateTime(t.date)}</td>
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
        product_id:  productId,
        quantity:    qty,
        unit_price:  parseFloat(document.getElementById('si-price').value) || 0,
        supplier_id: parseInt(document.getElementById('si-supplier').value) || null,
        expiry_date: document.getElementById('si-expiry').value || null,
        notes:       document.getElementById('si-notes').value,
      });
      App.toast('Stock added!', 'success');
      this.renderStockIn();
    } catch(e) { App.toast(e.message, 'error'); }
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
};

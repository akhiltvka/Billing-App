/**
 * billing.js — Point of Sale (POS) / Billing Module
 * Meat Products of India — Billing & Inventory Management App
 *
 * Features:
 *   - Upcoming Bill Number Preview
 *   - Hold & Resume Bills (Queue system)
 *   - Mandatory Rejection / Cancellation Reason
 *   - First-time Quick Customer Creation at POS
 */

const Billing = {
  cart: [],
  customer: null,
  paymentMode: 'cash',
  discountPct: 0,
  products: [],
  _heldBills: JSON.parse(localStorage.getItem('mpi_held_bills') || '[]'),

  // ─── Render POS Page ─────────────────────────────────────────────────────
  async render() {
    const heldCount = this._heldBills.length;

    document.getElementById('page-content').innerHTML = `
      <div class="page-enter" style="height:100%">
        <div class="pos-layout">

          <!-- Left: Product Search + Cart -->
          <div class="pos-left">

            <!-- Customer Panel -->
            <div class="card customer-panel" style="padding:14px 16px">
              <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                <div style="flex:1;min-width:240px;position:relative">
                  <div class="form-label mb-8" style="display:flex;justify-content:space-between;align-items:center">
                    <span>Customer (optional)</span>
                    <button class="btn btn-secondary btn-sm" onclick="Billing.showQuickCustomerModal()" title="Shortcut: F11 or Alt+C or Ctrl+N" style="padding:2px 8px;font-size:11px">
                      ➕ Quick Add Customer <kbd style="font-family:sans-serif;background:rgba(0,0,0,0.12);padding:1px 4px;border-radius:3px;font-size:10px;margin-left:3px">F11 / Alt+C</kbd>
                    </button>
                  </div>
                  <div style="display:flex;gap:8px">
                    <input id="customer-search" class="form-control" placeholder="Search by name or phone…" oninput="Billing.searchCustomer(this.value)" onfocus="Billing.searchCustomer(this.value)" onclick="Billing.searchCustomer(this.value)" onblur="setTimeout(()=>Billing._hideCustomerDropdown(),180)" autocomplete="off" style="flex:1">
                    <button id="btn-clear-customer" class="btn btn-secondary" onclick="Billing.clearCustomer()" title="Reset to Walk-in Customer" style="padding:0 12px;font-size:12px;white-space:nowrap;display:flex;align-items:center;gap:4px">👤 Walk-in</button>
                  </div>
                </div>
                <div id="customer-info" style="min-width:180px">
                  <div class="badge badge-info" id="customer-badge">👤 Walk-in Customer</div>
                </div>
              </div>
            </div>

            <!-- Product Search -->
            <div class="card" style="padding:14px 16px">
              <div class="form-label mb-8">🔍 Search Product (name, 4-letter code e.g. CHIC, or barcode)</div>
              <div class="product-search-wrap">
                <div class="search-bar" style="font-size:15px">
                  <span class="search-icon">🔎</span>
                  <input id="product-search" type="text" placeholder="Type product name, 4-letter code, or scan barcode…"
                    oninput="Billing.searchProduct(this.value)"
                    onkeydown="Billing.onSearchKey(event)"
                    autocomplete="off">
                </div>
                <div id="product-results" class="product-search-results"></div>
              </div>
            </div>

            <!-- Cart Items -->
            <div class="cart-items-wrap" id="cart-table">
              <div class="empty-state" id="cart-empty">
                <div class="empty-state-icon">🛒</div>
                <h3>Cart is empty</h3>
                <p>Search and add products above</p>
              </div>
            </div>
          </div>

          <!-- Right: Bill Summary -->
          <div class="pos-right">
            <div style="padding:14px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
              <div>
                <div style="font-family:'Inter',sans-serif;font-size:15px;font-weight:700">📄 Bill Summary</div>
                <div style="font-size:12px;color:var(--text-muted)">Upcoming: <span id="pos-bill-no" class="font-bold text-gold">Loading…</span></div>
              </div>
              ${Auth.can('billing.hold') ? `
              <button class="btn btn-secondary btn-sm" onclick="Billing.showHeldBillsModal()" title="Held Bills (F6)">
                ⏸️ Held Bills <span id="held-bills-badge"></span>
              </button>` : ''}
            </div>

            <div class="customer-panel" style="padding:12px 16px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <span class="form-label">Discount % ${!Auth.can('billing.give_discount') ? '<span class="text-muted" style="font-size:10px">(Staff Cap: 10%)</span>' : ''}</span>
                <span id="discount-display" class="text-gold font-bold">0%</span>
              </div>
              <input type="range" id="discount-slider" min="0" max="${Auth.can('billing.give_discount') ? 50 : 10}" value="0" step="0.5"
                style="width:100%;accent-color:var(--crimson);cursor:pointer"
                oninput="Billing.setDiscount(this.value)">
              <div style="display:flex;gap:6px;margin-top:8px">
                ${(Auth.can('billing.give_discount') ? [0,5,10,15,20] : [0,2.5,5,7.5,10]).map(d =>
                  `<button class="btn btn-secondary btn-sm" style="flex:1;padding:4px" onclick="Billing.setDiscount(${d})">${d}%</button>`
                ).join('')}
              </div>
            </div>

            <!-- Totals -->
            <div class="bill-summary-panel" style="flex:1;overflow-y:auto">
              <div class="bill-row">
                <span>Subtotal</span>
                <span class="amount" id="sum-subtotal">₹0.00</span>
              </div>
              <div class="bill-row">
                <span>Discount</span>
                <span class="amount text-danger" id="sum-discount">— ₹0.00</span>
              </div>
              ${App.isGstEnabled() ? `
              <div class="bill-row" style="font-size:12px;color:var(--text-muted)">
                <span>CGST</span>
                <span id="sum-cgst">₹0.00</span>
              </div>
              <div class="bill-row" style="font-size:12px;color:var(--text-muted)">
                <span>SGST</span>
                <span id="sum-sgst">₹0.00</span>
              </div>` : ''}
              <!-- Grand Total Display with Extra Large Font -->
              <div class="bill-row total" style="padding:14px 16px;background:rgba(217,119,6,0.15);border:1px solid rgba(217,119,6,0.3);border-radius:var(--r-md);margin-top:12px;display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:16px;font-weight:700;color:var(--text-primary)">Grand Total</span>
                <span class="amount" id="sum-total" style="font-size:32px;font-weight:900;color:var(--gold);letter-spacing:0.5px">₹0.00</span>
              </div>

              <!-- Payment Mode -->
              <div style="margin-top:16px">
                <div class="form-label mb-8">Payment Mode</div>
                <div class="payment-modes">
                  <div class="payment-mode-btn active" data-mode="cash" onclick="Billing.setPayment('cash')">
                    <span style="font-size:18px">💵</span>Cash
                  </div>
                  <div class="payment-mode-btn" data-mode="upi" onclick="Billing.setPayment('upi')">
                    <span style="font-size:18px">📱</span>UPI
                  </div>
                  <div class="payment-mode-btn" data-mode="card" onclick="Billing.setPayment('card')">
                    <span style="font-size:18px">💳</span>Card
                  </div>
                </div>
              </div>

              <!-- Amount Received & Change / Balance Calculation -->
              <div class="form-group" style="margin-top:12px">
                <label class="form-label" style="display:flex;justify-content:space-between;align-items:center">
                  <span>Amount Received (₹)</span>
                  <span style="font-size:11px;color:var(--text-muted)">Cash paid by customer</span>
                </label>
                <div class="input-group">
                  <div class="input-group-prefix" style="font-weight:700">₹</div>
                  <input class="form-control" id="amount-paid" type="number" step="1" placeholder="0.00" style="font-size:18px;font-weight:700"
                    oninput="Billing.calcChange()" onfocus="this.select()">
                </div>
                <!-- Quick Cash Note Presets -->
                <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap">
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;flex:1" onclick="Billing.setQuickCash('exact')">Exact</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;flex:1" onclick="Billing.setQuickCash(100)">₹100</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;flex:1" onclick="Billing.setQuickCash(200)">₹200</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;flex:1" onclick="Billing.setQuickCash(500)">₹500</button>
                  <button type="button" class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;flex:1" onclick="Billing.setQuickCash(2000)">₹2000</button>
                </div>
              </div>

              <!-- Balance / Return Change Output -->
              <div class="bill-row" style="font-size:15px;font-weight:700;padding:10px 12px;background:var(--bg-input);border-radius:var(--r-sm);margin-top:8px;display:flex;justify-content:space-between;align-items:center">
                <span id="change-label">Return Change</span>
                <span class="amount" id="sum-change" style="font-size:22px;font-weight:800;color:var(--text-muted)">₹0.00</span>
              </div>

              <!-- Notes -->
              <div class="form-group mt-8">
                <label class="form-label">Notes</label>
                <input class="form-control" id="bill-notes" placeholder="Optional bill note">
              </div>
            </div>

            <!-- Action Buttons -->
            <div style="padding:16px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:10px">
              <button class="btn btn-gold btn-xl w-full" id="btn-save-bill" onclick="Billing.saveBill()">
                💾 Save & Print Bill
              </button>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:4px">
                <button class="btn btn-primary btn-sm" onclick="Billing.startNewBill()" title="Start New Bill (F1)" style="padding:8px 6px;font-weight:600">
                  ✨ New Bill
                </button>
                <button class="btn btn-secondary btn-sm" onclick="Billing.saveBill(false)" style="padding:8px 6px;font-weight:600">
                  💾 Save Only
                </button>
                <button class="btn btn-warning btn-sm" onclick="Billing.holdCurrentBill()" title="Hold Bill (F5)" style="padding:8px 6px;font-weight:600">
                  ⏸️ Hold Bill
                </button>
                <button class="btn btn-danger btn-sm" onclick="Billing.clearCart()" style="padding:8px 6px;font-weight:600">
                  🗑️ Clear Cart
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>`;

    // Load products, customers, upcoming bill number & held count
    try {
      const [prods, nextNumData, heldData, custsData] = await Promise.all([
        App.api('/products?active=true'),
        App.api('/bills/next-number'),
        App.api('/billing/held'),
        App.api('/customers')
      ]);
      this.products = prods;
      this.allCustomers = Array.isArray(custsData) ? custsData : (custsData?.data || []);
      const el = document.getElementById('pos-bill-no');
      if (el) el.textContent = nextNumData.next_bill_no;

      const heldList = Array.isArray(heldData) ? heldData : (heldData.held_bills || heldData.data || []);
      const badgeEl = document.getElementById('held-bills-badge');
      if (badgeEl) badgeEl.textContent = `(${heldList.length})`;
    } catch(e) { App.toast('Could not load POS data', 'error'); }

    // Initialize keyboard shortcuts for POS
    if (typeof BillingShortcuts !== 'undefined') {
      BillingShortcuts.init({
        onNewBill:        () => Billing.startNewBill(),
        onSearchItem:     () => document.getElementById('product-search')?.focus(),
        onSearchCustomer: () => document.getElementById('customer-search')?.focus(),
        onNewCustomer:    () => Billing.showQuickCustomerModal(),
        onHoldBill:       () => Billing.holdCurrentBill(),
        onRecallBill:     () => Billing.loadHeldBills(),
        onSaveAndPrint:   () => Billing.saveBill(true),
        onSaveOnly:       () => Billing.saveBill(false),
        onEscape:         () => App.closeModal(),
      });
    }
  },

  // ─── Quick Add First-Time Customer ─────────────────────────────────────────
  showQuickCustomerModal() {
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">➕</span> Quick Add Customer</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label required">Customer Full Name</label>
          <input class="form-control" id="qc-name" placeholder="e.g., John Doe" autofocus>
        </div>
        <div class="form-group">
          <label class="form-label required">Mobile Phone Number (10 digits)</label>
          <input class="form-control" id="qc-phone" placeholder="10-digit mobile number" maxlength="10" oninput="this.value=this.value.replace(/[^0-9]/g,'')">
        </div>
        <div class="form-group">
          <label class="form-label">GSTIN (optional for B2B)</label>
          <input class="form-control" id="qc-gstin" placeholder="15-digit GSTIN">
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Billing.saveQuickCustomer()">💾 Add & Select for Bill</button>
        </div>
      </div>`);
  },

  async saveQuickCustomer() {
    const name = document.getElementById('qc-name').value.trim();
    const phone = document.getElementById('qc-phone').value.trim();
    const gstin = document.getElementById('qc-gstin').value.trim();

    if (!name) { App.toast('Customer name is required', 'error'); return; }
    if (!phone) { App.toast('Phone number is required', 'error'); return; }
    if (!/^\d{10}$/.test(phone)) {
      App.toast('Phone number must be exactly 10 digits', 'error');
      return;
    }

    try {
      const newCust = await App.api('/customers', 'POST', { name, phone, gstin });
      this.customer = newCust;
      App.closeModal();
      App.toast(`Customer "${name}" added & selected!`, 'success');

      // Update badge
      const badge = document.getElementById('customer-badge');
      if (badge) {
        badge.innerHTML = `👤 <strong>${newCust.name}</strong> (${newCust.phone})`;
        badge.className = 'badge badge-gold';
      }
      const searchInput = document.getElementById('customer-search');
      if (searchInput) searchInput.value = newCust.name;
    } catch(e) { App.toast(e.message, 'error'); }
  },

  // ─── Hold & Recall Bills ───────────────────────────────────────────────────
  async holdCurrentBill() {
    if (!this.cart || this.cart.length === 0) {
      App.toast('Cart is empty. Add products before holding.', 'warning');
      return;
    }

    const totalEl = document.getElementById('sum-total');
    const total = parseFloat(totalEl?.textContent?.replace(/[₹,]/g,'') || 0);

    const payload = {
      terminal_id: 'POS-1',
      customer_id: this.customer?.id || null,
      customer_name: this.customer?.name || null,
      items: this.cart,
      discount_percent: this.discountPct,
      payment_mode: this.paymentMode,
      total: total,
      notes: document.getElementById('bill-notes')?.value || ''
    };

    try {
      const res = await App.api('/billing/hold', 'POST', payload);
      const ref = res.reference_code || res.reference || (res.data && (res.data.reference_code || res.data.reference)) || 'Held';
      App.toast(`Bill held! Reference: ${ref} (${this.cart.length} items)`, 'info');

      // Reset current active cart
      this.cart = [];
      this.customer = null;
      this.discountPct = 0;
      this._selectedCartIndex = undefined;
      this.render();
    } catch(e) {
      App.toast('Failed to hold bill: ' + e.message, 'error');
    }
  },

  async showHeldBillsModal() {
    try {
      const res = await App.api('/billing/held');
      const heldList = Array.isArray(res) ? res : (res.held_bills || res.data || []);
      const canDelete = typeof Auth !== 'undefined' && Auth.isRole && Auth.isRole('admin', 'manager', 'md');

      App.showModal(`
        <div class="modal modal-lg">
          <div class="modal-header">
            <div class="modal-title"><span class="modal-title-icon">⏸️</span> Held Bills (${heldList.length})</div>
            <button class="modal-close" onclick="App.closeModal()">✕</button>
          </div>
          ${heldList.length === 0
            ? '<div class="empty-state"><div class="empty-state-icon">⏸️</div><h3>No held bills</h3><p>You can hold active bills on the POS screen (Press F5).</p></div>'
            : `<div style="display:flex;flex-direction:column;gap:12px;max-height:400px;overflow-y:auto">
                ${heldList.map(h => `
                  <div style="padding:16px;background:var(--bg-input);border:1px solid var(--border);border-radius:var(--r-md);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
                    <div>
                      <div style="display:flex;align-items:center;gap:8px">
                        <span class="badge badge-gold font-bold" style="font-family:monospace;font-size:12px">${h.reference || ('HOLD-' + h.id)}</span>
                        <span style="font-weight:700;font-size:15px;color:var(--text-primary)">
                          ${h.customer_name ? `👤 ${h.customer_name}` : (h.customer_master_name ? `👤 ${h.customer_master_name}` : '👤 Walk-in Customer')}
                        </span>
                      </div>
                      <div class="text-muted text-xs mt-4">
                        Held at ${App.fmtDateTime(h.time_held || h.created_at)} • ${h.item_count || (h.items || []).length} item${(h.items || []).length !== 1 ? 's' : ''} • Terminal: ${h.terminal_id || 'POS-1'} ${h.cashier_name ? '• By: ' + h.cashier_name : ''}
                      </div>
                      <div style="font-size:12px;margin-top:4px;color:var(--text-secondary)">
                        ${(h.items || []).map(i => `${i.product_name || i.name} (${i.quantity} ${i.unit || 'unit'})`).join(', ')}
                      </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:12px">
                      <div style="font-size:18px;font-weight:800;color:var(--gold)">${App.fmt(h.total || h.total_amount)}</div>
                      <button class="btn btn-success btn-sm" onclick="Billing.resumeHeldBill(${h.id})">▶️ Recall</button>
                      ${canDelete ? `<button class="btn btn-danger btn-sm btn-icon" onclick="Billing.discardHeldBill(${h.id}, '${h.reference || ('HOLD-' + h.id)}')">🗑️</button>` : ''}
                    </div>
                  </div>`).join('')}
               </div>`}
          <div class="modal-footer">
            <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
          </div>
        </div>`);
    } catch(e) {
      App.toast('Failed to load held bills: ' + e.message, 'error');
    }
  },

  async resumeHeldBill(id) {
    if (this.cart.length > 0) {
      App.confirm('Your current active cart is not empty. Replace active cart with recalled bill?', 'Recall Bill', () => {
        this._doResumeHeldBill(id);
      });
      return;
    }

    this._doResumeHeldBill(id);
  },

  async _doResumeHeldBill(id) {
    try {
      const res = await App.api(`/billing/recall/${id}`, 'POST');
      const data = res.data || res;
      this.cart = data.cart || data.items || [];
      this.customer = data.customer_id ? { id: data.customer_id, name: data.customer_name } : null;
      this.discountPct = data.discount_percent || 0;
      this.paymentMode = data.payment_mode || 'cash';
      this._selectedCartIndex = undefined;

      App.closeModal();
      const ref = data.reference_code || data.reference || `HOLD-${id}`;
      App.toast(`Held bill ${ref} recalled into active cart!`, 'success');
      this.render();
    } catch(e) {
      App.toast('Failed to recall bill: ' + e.message, 'error');
    }
  },

  async discardHeldBill(id, refCode) {
    App.confirm(`Delete held bill ${refCode || id}?`, 'Delete Held Bill', async () => {
      try {
        await App.api(`/billing/held/${id}`, 'DELETE');
        App.toast(`Held bill ${refCode || id} deleted`, 'warning');
        this.showHeldBillsModal();
      } catch(e) {
        App.toast('Failed to delete held bill: ' + e.message, 'error');
      }
    });
  },

  // ─── Product Search ───────────────────────────────────────────────────────
  async searchProduct(query) {
    const resultsEl = document.getElementById('product-results');
    if (!query || query.length < 1) { resultsEl.classList.remove('show'); return; }
    try {
      const products = await App.api(`/products?q=${encodeURIComponent(query)}&active=true`);
      if (products.length === 0) {
        resultsEl.innerHTML = '<div class="search-result-item"><span class="text-muted">No products found</span></div>';
      } else {
        resultsEl.innerHTML = products.slice(0, 10).map(p => `
          <div class="search-result-item" onclick="Billing.addToCart(${JSON.stringify(JSON.stringify(p))})">
            <div>
              <div class="item-name">${p.name} <span class="badge badge-gold" style="font-family:monospace;font-size:11px;padding:1px 5px">[${p.code || ''}]</span></div>
              <div class="item-meta">${p.category_name || ''} • ${p.unit} • HSN: ${p.hsn_code || 'N/A'}</div>
            </div>
            <div style="text-align:right">
              <div class="item-price">${App.fmt(p.selling_price)}/${p.unit}</div>
              <div class="item-stock">${App.stockBadge(p.current_stock, p.min_stock)}</div>
            </div>
          </div>`).join('');
      }
      resultsEl.classList.add('show');
    } catch(e) { resultsEl.classList.remove('show'); }
  },

  async onSearchKey(e) {
    if (e.key === 'Escape') {
      document.getElementById('product-results').classList.remove('show');
      document.getElementById('product-search').value = '';
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const val = document.getElementById('product-search').value.trim();
      if (!val) return;
      try {
        const bResult = await App.api(`/products/barcode/${encodeURIComponent(val)}`);
        if (bResult) {
          this.addToCart(bResult);
          document.getElementById('product-search').value = '';
          document.getElementById('product-results').classList.remove('show');
          return;
        }
      } catch(err) {
        const resultsEl = document.getElementById('product-results');
        const firstItem = resultsEl.querySelector('.search-result-item');
        if (firstItem) {
          firstItem.click();
        }
      }
    }
  },

  addToCart(productJson) {
    const p = typeof productJson === 'string' ? JSON.parse(productJson) : productJson;
    document.getElementById('product-results').classList.remove('show');
    document.getElementById('product-search').value = '';

    const price = (p.product_type === 'general' && p.mrp) ? p.mrp : p.selling_price;

    const existing = this.cart.find(i => i.product_id === p.id);
    if (existing) {
      existing.quantity = parseFloat((existing.quantity + 1).toFixed(3));
      this.renderCart();
      return;
    }

    this.cart.push({
      product_id:   p.id,
      product_name: p.name,
      code:         p.code || '',
      hsn_code:     p.hsn_code || '',
      unit:         p.unit,
      unit_price:   price,
      gst_rate:     p.gst_rate || 0,
      quantity:     1,
      current_stock: p.current_stock,
      product_type: p.product_type || 'perishable',
      is_price_inclusive_of_tax: p.is_price_inclusive_of_tax ?? 1,
    });
    this.renderCart();
    App.toast(`${p.name} added to cart`, 'success');
  },

  // ─── Render Cart ──────────────────────────────────────────────────────────
  renderCart() {
    const container = document.getElementById('cart-table');
    if (this.cart.length === 0) {
      container.innerHTML = `
        <div class="empty-state" id="cart-empty">
          <div class="empty-state-icon">🛒</div>
          <h3>Cart is empty</h3>
          <p>Search and add products above</p>
        </div>`;
      this.updateTotals();
      return;
    }

    container.innerHTML = `
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr>
            <th style="padding:10px 14px;text-align:left;background:var(--bg-input);font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.8px;white-space:nowrap">Product</th>
            <th style="padding:10px 14px;text-align:center;background:var(--bg-input);font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.8px">Qty</th>
            <th style="padding:10px 14px;text-align:right;background:var(--bg-input);font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.8px">Rate</th>
            ${App.isGstEnabled() ? '<th style="padding:10px 14px;text-align:right;background:var(--bg-input);font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.8px">GST%</th>' : ''}
            <th style="padding:10px 14px;text-align:right;background:var(--bg-input);font-size:11px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.8px">Amount</th>
            <th style="padding:10px 8px;background:var(--bg-input)"></th>
          </tr>
        </thead>
        <tbody>
          ${this.cart.map((item, idx) => {
            const lineAmt = item.quantity * item.unit_price;
            const isSelected = this._selectedCartIndex === idx || (this._selectedCartIndex === undefined && idx === this.cart.length - 1);
            if (isSelected) this._selectedCartIndex = idx;
            return `
              <tr class="${isSelected ? 'selected' : ''}" style="border-bottom:1px solid var(--border);cursor:pointer;${isSelected ? 'background:rgba(217,119,6,0.15);' : ''}" onclick="Billing.selectCartRow(${idx})">
                <td style="padding:10px 14px">
                  <div style="font-weight:600">${item.product_name} <span class="badge badge-gold" style="font-family:monospace;font-size:10px;padding:1px 4px">[${item.code || ''}]</span></div>
                  <div style="font-size:11px;color:var(--text-muted)">${item.unit} ${App.isGstEnabled() && item.hsn_code ? '• HSN:' + item.hsn_code : ''}</div>
                </td>
                <td style="padding:10px 8px;text-align:center">
                  <div style="display:inline-flex;align-items:center;gap:4px" onclick="event.stopPropagation()">
                    <button class="btn btn-secondary btn-sm btn-icon" style="width:24px;height:24px;font-size:12px" onclick="Billing.changeQty(${idx}, -0.5)">−</button>
                    <input type="number" value="${item.quantity}" step="0.05" min="0.001" style="width:65px;text-align:center;padding:2px 4px;font-weight:700" class="form-control" onchange="Billing.setQty(${idx}, this.value)">
                    <button class="btn btn-secondary btn-sm btn-icon" style="width:24px;height:24px;font-size:12px" onclick="Billing.changeQty(${idx}, 0.5)">+</button>
                  </div>
                </td>
                <td style="padding:10px 14px;text-align:right" onclick="event.stopPropagation()">
                  <input type="number" value="${item.unit_price}" step="0.50" style="width:75px;text-align:right;padding:2px 4px" class="form-control" onchange="Billing.setPrice(${idx}, this.value)">
                </td>
                ${App.isGstEnabled() ? `<td style="padding:10px 14px;text-align:right;font-size:12px;color:var(--text-muted)">${item.gst_rate}%</td>` : ''}
                <td style="padding:10px 14px;text-align:right;font-weight:700;color:var(--gold)">${App.fmt(lineAmt)}</td>
                <td style="padding:10px 8px;text-align:center" onclick="event.stopPropagation()">
                  <button class="btn btn-danger btn-sm btn-icon" style="width:24px;height:24px;font-size:11px" onclick="Billing.removeItem(${idx})">✕</button>
                </td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>`;

    this.updateTotals();
  },

  selectCartRow(idx) {
    this._selectedCartIndex = idx;
    const rows = document.querySelectorAll('#cart-table tbody tr');
    rows.forEach((r, i) => {
      const isSel = i === idx;
      r.classList.toggle('selected', isSel);
      r.style.background = isSel ? 'rgba(217,119,6,0.15)' : '';
    });
  },

  changeQty(idx, delta) {
    if (!this.cart[idx]) return;
    const newQty = parseFloat((this.cart[idx].quantity + delta).toFixed(3));
    if (newQty <= 0) { this.removeItem(idx); return; }
    this.cart[idx].quantity = newQty;
    this.renderCart();
  },

  setQty(idx, val) {
    if (!this.cart[idx]) return;
    const v = parseFloat(val);
    if (!v || v <= 0) { this.removeItem(idx); return; }
    this.cart[idx].quantity = parseFloat(v.toFixed(3));
    this.renderCart();
  },

  setPrice(idx, val) {
    if (!this.cart[idx]) return;
    const v = parseFloat(val);
    if (v >= 0) this.cart[idx].unit_price = v;
    this.renderCart();
  },

  removeItem(idx) {
    this.cart.splice(idx, 1);
    this.renderCart();
  },

  startNewBill() {
    if (this.cart && this.cart.length > 0) {
      App.confirm('Start a new bill? Current cart items will be cleared.', 'Start New Bill', () => {
        this.cart = [];
        this.customer = null;
        this.discountPct = 0;
        this._selectedCartIndex = undefined;
        this.render();
        App.toast('New bill started', 'info');
      });
      return;
    }
    this.cart = [];
    this.customer = null;
    this.discountPct = 0;
    this._selectedCartIndex = undefined;
    this.render();
    App.toast('New bill started', 'info');
  },

  clearCart() {
    if (this.cart.length === 0) return;
    App.confirm('Clear all items from the current cart?', 'Clear Cart', () => {
      this.cart = [];
      this.discountPct = 0;
      const dSlider = document.getElementById('discount-slider');
      if (dSlider) dSlider.value = 0;
      this.renderCart();
    });
  },

  // ─── Customer Selection ───────────────────────────────────────────────────
  // ─── Customer Dropdown Portal ─────────────────────────────────────────────
  _getOrCreateCustomerDropdown() {
    let el = document.getElementById('customer-results');
    if (!el) {
      el = document.createElement('div');
      el.id = 'customer-results';
      el.className = 'customer-results-portal';
      document.body.appendChild(el);
    }
    return el;
  },

  _positionCustomerDropdown() {
    const input = document.getElementById('customer-search');
    const el = document.getElementById('customer-results');
    if (!input || !el) return;
    const rect = input.getBoundingClientRect();
    el.style.top   = (rect.bottom + 4) + 'px';
    el.style.left  = rect.left + 'px';
    el.style.width = rect.width + 'px';
  },

  _hideCustomerDropdown() {
    const el = document.getElementById('customer-results');
    if (el) el.style.display = 'none';
  },

  _renderCustomerList(list, el) {
    el.innerHTML = list.map((c, idx) => `
      <div class="cr-item" onmousedown="event.preventDefault(); Billing.selectCustomerByIndex(${idx})">
        <div>
          <div class="cr-name">👤 ${App.escapeHtml(c.name)}</div>
          <div class="cr-meta">📞 ${App.escapeHtml(c.phone || 'No phone')}${c.gstin ? ' &bull; GSTIN: ' + App.escapeHtml(c.gstin) : ''}</div>
        </div>
        <span class="cr-select">Select ➔</span>
      </div>`).join('');
  },

  async searchCustomer(query = '') {
    const el = this._getOrCreateCustomerDropdown();
    this._positionCustomerDropdown();

    const qStr = (query || '').trim().toLowerCase();
    const rawQ = (query || '').trim();

    // If cache not loaded yet, fetch directly from API right away
    if (!this.allCustomers || this.allCustomers.length === 0) {
      el.innerHTML = '<div style="padding:12px 14px;color:#94A3B8;font-size:12px">Loading customers…</div>';
      el.style.display = 'block';
      try {
        const data = await App.api('/customers');
        this.allCustomers = Array.isArray(data) ? data : [];
      } catch(e) { this.allCustomers = []; }
    }

    // Instant local filter
    let list = this.allCustomers || [];
    if (qStr.length > 0) {
      list = list.filter(c =>
        (c.name  && c.name.toLowerCase().includes(qStr))  ||
        (c.phone && c.phone.includes(rawQ))               ||
        (c.email && c.email.toLowerCase().includes(qStr)) ||
        (c.gstin && c.gstin.toLowerCase().includes(qStr))
      );
    }

    this.lastCustomerResults = list;

    if (list.length === 0) {
      if (qStr.length > 0) {
        const safeQ = rawQ.replace(/'/g, "\\'");
        const isNum = /^\+?\d+$/.test(rawQ);
        el.innerHTML = `<div onmousedown="event.preventDefault(); Billing.showQuickCustomerModal(); setTimeout(()=>{ const f=document.getElementById('${isNum?'qc-phone':'qc-name'}'); if(f){f.value='${safeQ}';f.focus();} },150)" style="cursor:pointer;color:#059669;padding:12px 14px;font-weight:600;font-size:13px">
          ➕ No match — <strong style="text-decoration:underline">Click to Add "${rawQ}"</strong>
        </div>`;
      } else {
        el.innerHTML = '<div style="padding:12px 14px;color:#94A3B8;font-size:12px">Start typing to search saved customers…</div>';
      }
    } else {
      this._renderCustomerList(list, el);
    }

    el.style.display = 'block';

    // Background server sync for accuracy
    try {
      const freshList = await App.api(`/customers?q=${encodeURIComponent(rawQ)}`);
      if (freshList && Array.isArray(freshList) && el.style.display === 'block') {
        this.lastCustomerResults = freshList;
        if (freshList.length > 0) {
          this._renderCustomerList(freshList, el);
        }
      }
    } catch(e) { /* ignore */ }
  },

  selectCustomerByIndex(idx) {
    if (!this.lastCustomerResults || !this.lastCustomerResults[idx]) return;
    const c = this.lastCustomerResults[idx];
    this.customer = c;

    const input = document.getElementById('customer-search');
    if (input) input.value = c.name;

    this._hideCustomerDropdown();

    const badge = document.getElementById('customer-badge');
    if (badge) {
      badge.innerHTML = `👤 <strong>${App.escapeHtml(c.name)}</strong> (${App.escapeHtml(c.phone || 'No phone')})`;
      badge.className = 'badge badge-gold';
    }

    const btnClear = document.getElementById('btn-clear-customer');
    if (btnClear) {
      btnClear.innerHTML = '✕ Clear';
      btnClear.className = 'btn btn-danger';
      btnClear.title = 'Clear customer selection';
    }
  },

  selectCustomer(cJson) {
    const c = typeof cJson === 'string' ? JSON.parse(cJson) : cJson;
    if (!c) return;
    this.customer = c;
    const input = document.getElementById('customer-search');
    if (input) input.value = c.name;
    this._hideCustomerDropdown();
    const badge = document.getElementById('customer-badge');
    if (badge) {
      badge.innerHTML = `👤 <strong>${App.escapeHtml(c.name)}</strong> (${App.escapeHtml(c.phone || 'No phone')})`;
      badge.className = 'badge badge-gold';
    }
    const btnClear = document.getElementById('btn-clear-customer');
    if (btnClear) {
      btnClear.innerHTML = '✕ Clear';
      btnClear.className = 'btn btn-danger';
      btnClear.title = 'Clear customer selection';
    }
  },

  clearCustomer() {
    this.customer = null;
    const input = document.getElementById('customer-search');
    if (input) input.value = '';
    this._hideCustomerDropdown();
    const badge = document.getElementById('customer-badge');
    if (badge) {
      badge.innerHTML = '👤 Walk-in Customer';
      badge.className = 'badge badge-info';
    }
    const btnClear = document.getElementById('btn-clear-customer');
    if (btnClear) {
      btnClear.innerHTML = '👤 Walk-in';
      btnClear.className = 'btn btn-secondary';
      btnClear.title = 'Reset to Walk-in Customer';
    }
  },

  // ─── Discount & Totals Calculations ─────────────────────────────────────
  setDiscount(pct) {
    this.discountPct = parseFloat(pct) || 0;
    const dDisplay = document.getElementById('discount-display');
    if (dDisplay) dDisplay.textContent = `${this.discountPct}%`;
    const dSlider = document.getElementById('discount-slider');
    if (dSlider) dSlider.value = this.discountPct;
    this.updateTotals();
  },

  setPayment(mode) {
    this.paymentMode = mode;
    document.querySelectorAll('.payment-mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
  },

  updateTotals() {
    let rawSubtotal = 0;
    let cgstTotal = 0;
    let sgstTotal = 0;

    this.cart.forEach(i => {
      const lineRaw = i.quantity * i.unit_price;
      const lineTaxable = lineRaw * (1 - this.discountPct / 100);
      rawSubtotal += lineTaxable;
      cgstTotal += lineTaxable * (i.gst_rate / 2) / 100;
      sgstTotal += lineTaxable * (i.gst_rate / 2) / 100;
    });

    const discountAmt = (this.cart.reduce((s, i) => s + i.quantity * i.unit_price, 0)) * (this.discountPct / 100);
    const grandTotal = rawSubtotal + cgstTotal + sgstTotal;

    const elSub = document.getElementById('sum-subtotal');
    const elDisc = document.getElementById('sum-discount');
    const elCgst = document.getElementById('sum-cgst');
    const elSgst = document.getElementById('sum-sgst');
    const elTot = document.getElementById('sum-total');
    const elPaid = document.getElementById('amount-paid');

    if (elSub) elSub.textContent = App.fmt(this.cart.reduce((s, i) => s + i.quantity * i.unit_price, 0));
    if (elDisc) elDisc.textContent = discountAmt > 0 ? `− ${App.fmt(discountAmt)}` : '— ₹0.00';
    if (elCgst) elCgst.textContent = App.fmt(cgstTotal);
    if (elSgst) elSgst.textContent = App.fmt(sgstTotal);
    if (elTot) elTot.textContent = App.fmt(grandTotal);

    if (elPaid && !elPaid.value) {
      elPaid.value = grandTotal > 0 ? grandTotal.toFixed(2) : '';
    }
    this.calcChange();
  },

  setQuickCash(val) {
    const totalEl = document.getElementById('sum-total');
    const total = parseFloat(totalEl?.textContent?.replace(/[^\d.]/g, '') || 0);
    const paidInput = document.getElementById('amount-paid');
    if (!paidInput) return;

    if (val === 'exact') {
      paidInput.value = total > 0 ? total.toFixed(2) : '';
    } else {
      paidInput.value = parseFloat(val).toFixed(2);
    }
    this.calcChange();
  },

  calcChange() {
    const totalEl = document.getElementById('sum-total');
    const total = parseFloat(totalEl?.textContent?.replace(/[^\d.]/g, '') || 0);
    const paidInput = document.getElementById('amount-paid');
    const paidVal = paidInput ? paidInput.value.trim() : '';
    const paid = parseFloat(paidVal) || 0;

    const labelEl = document.getElementById('change-label');
    const elChange = document.getElementById('sum-change');
    if (!elChange) return;

    if (paidVal === '' || paid === 0) {
      if (labelEl) labelEl.textContent = 'Return Change';
      elChange.textContent = '₹0.00';
      elChange.style.color = 'var(--text-muted)';
      return;
    }

    const diff = paid - total;
    if (diff >= 0) {
      if (labelEl) labelEl.textContent = 'Return Change';
      elChange.textContent = App.fmt(diff);
      elChange.style.color = '#10B981'; // Emerald Green
    } else {
      if (labelEl) labelEl.textContent = 'Balance Due';
      elChange.textContent = App.fmt(Math.abs(diff));
      elChange.style.color = '#EF4444'; // Warning Red
    }
  },

  // ─── Save & Print Bill ───────────────────────────────────────────────────
  async saveBill(print = true) {
    if (this.cart.length === 0) {
      App.toast('Cart is empty. Add products first.', 'error');
      return;
    }

    const btn = document.getElementById('btn-save-bill');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Saving Bill…'; }

    try {
      const totalEl = document.getElementById('sum-total');
      const total = parseFloat(totalEl?.textContent?.replace(/[₹,]/g,'') || 0);
      const paid = parseFloat(document.getElementById('amount-paid')?.value || total);

      const payload = {
        customer_id:     this.customer?.id || null,
        customer_name:   this.customer?.name || document.getElementById('customer-search')?.value || 'Walk-in Customer',
        customer_phone:  this.customer?.phone || '',
        customer_gstin:  this.customer?.gstin || '',
        discount_percent: this.discountPct,
        amount_paid:     paid,
        payment_mode:    this.paymentMode,
        notes:           document.getElementById('bill-notes')?.value || '',
        items: this.cart.map(i => ({
          product_id:   i.product_id,
          product_name: i.product_name,
          hsn_code:     i.hsn_code,
          unit:         i.unit,
          quantity:     i.quantity,
          unit_price:   i.unit_price,
          gst_rate:     i.gst_rate,
        })),
      };

      const bill = await App.api('/bills', 'POST', payload);
      App.toast(`Bill ${bill.bill_no} saved successfully!`, 'success');

      this.cart = [];
      this.customer = null;
      this.discountPct = 0;

      if (print) {
        window.open(`/invoice/${bill.id}`, '_blank');
      }

      this.render();
    } catch(e) {
      App.toast(e.message, 'error');
      if (btn) { btn.disabled = false; btn.textContent = '💾 Save & Print Bill'; }
    }
  },

  // ─── Bill History ─────────────────────────────────────────────────────────
  async renderHistory() {
    const today = new Date().toISOString().split('T')[0];
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="page-enter">
        <div class="page-header">
          <div class="page-header-left">
            <h1>📋 Bill History</h1>
            <p>View, reprint, and manage sales bills</p>
          </div>
        </div>
        <div class="filter-row">
          <div class="search-bar" style="flex:1;max-width:300px">
            <span class="search-icon">🔎</span>
            <input id="bill-search" type="text" placeholder="Search bill no, customer…" oninput="Billing.loadHistory()">
          </div>
          <input type="date" id="bill-from" class="form-control" style="width:160px" value="${today}" onchange="Billing.loadHistory()">
          <span class="text-muted">to</span>
          <input type="date" id="bill-to" class="form-control" style="width:160px" value="${today}" onchange="Billing.loadHistory()">
          <button class="btn btn-secondary" onclick="Billing.loadHistory()">🔍 Filter</button>
          <button class="btn btn-secondary" onclick="Billing.clearDateFilter()">All Time</button>
        </div>
        <div id="bills-summary" style="margin-bottom:16px"></div>
        <div class="card">
          <div id="bills-table"><div class="loading-overlay"><div class="spinner"></div></div></div>
        </div>
      </div>`;
    this.loadHistory();
  },

  async loadHistory() {
    const q = document.getElementById('bill-search')?.value || '';
    const from = document.getElementById('bill-from')?.value || '';
    const to = document.getElementById('bill-to')?.value || '';
    try {
      const data = await App.api(`/bills?q=${encodeURIComponent(q)}&from=${from}&to=${to}&limit=100`);
      const bills = data.bills || [];
      const totalRevenue = bills.reduce((s, b) => s + b.grand_total, 0);

      document.getElementById('bills-summary').innerHTML = `
        <div style="display:flex;gap:12px;flex-wrap:wrap">
          <div class="stat-card" style="flex:1;min-width:160px">
            <div class="stat-label">Bills Shown</div>
            <div class="stat-value">${bills.length}</div>
          </div>
          <div class="stat-card" style="flex:1;min-width:160px">
            <div class="stat-label">Total Revenue</div>
            <div class="stat-value">${App.fmt(totalRevenue)}</div>
          </div>
        </div>`;

      if (bills.length === 0) {
        document.getElementById('bills-table').innerHTML = `
          <div class="empty-state"><div class="empty-state-icon">📋</div>
          <h3>No bills found</h3><p>Try adjusting the date filter</p></div>`;
        return;
      }

      document.getElementById('bills-table').innerHTML = `
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>Bill No</th><th>Date & Time</th><th>Customer</th>
              <th class="text-right">Amount</th>${App.isGstEnabled() ? '<th>GST</th>' : ''}
              <th>Payment</th><th>Status</th><th>Actions</th>
            </tr></thead>
            <tbody>
              ${bills.map(b => {
                const payIcon = {cash:'💵',upi:'📱',card:'💳'}[b.payment_mode] || '💰';
                return `<tr>
                  <td class="font-bold text-gold">${b.bill_no}</td>
                  <td class="td-muted">${App.fmtDateTime(b.date)}</td>
                  <td>
                    <div class="font-semibold">${b.customer_name || 'Walk-in'}</div>
                    <div class="td-muted">${b.customer_phone || ''}</div>
                  </td>
                  <td class="td-number font-bold">${App.fmt(b.grand_total)}</td>
                  ${App.isGstEnabled() ? `<td class="td-muted text-right">${App.fmt((b.cgst || 0) + (b.sgst || 0))}</td>` : ''}
                  <td>${payIcon} <span style="text-transform:capitalize">${b.payment_mode}</span></td>
                  <td>${b.status === 'paid'
                    ? '<span class="badge badge-success">Paid</span>'
                    : `<div>
                         <span class="badge badge-danger">Cancelled</span>
                         ${b.cancel_reason ? `<div style="font-size:11px;color:var(--danger);margin-top:4px;font-style:italic">Reason: ${b.cancel_reason}</div>` : ''}
                       </div>`}</td>
                  <td>
                    <div style="display:flex;gap:6px">
                      <button class="btn btn-secondary btn-sm" onclick="window.open('/invoice/${b.id}','_blank')" title="Print Full Invoice (A4)">🖨️</button>
                      <button class="btn btn-secondary btn-sm" onclick="window.open('/invoice/${b.id}/thermal','_blank')" title="Print Thermal Receipt">🧾</button>
                      ${b.status === 'paid' && Auth.can('billing.void_bill')
                        ? `<button class="btn btn-danger btn-sm" onclick="Billing.promptCancelBill(${b.id},'${b.bill_no}')" title="Cancel Bill">✕ Cancel</button>`
                        : ''}
                    </div>
                  </td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>`;
    } catch(e) {
      document.getElementById('bills-table').innerHTML =
        `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  clearDateFilter() {
    document.getElementById('bill-from').value = '';
    document.getElementById('bill-to').value = '';
    this.loadHistory();
  },

  // ─── Mandatory Rejection / Cancellation Reason Prompt ─────────────────────
  promptCancelBill(id, billNo) {
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">⚠️</span> Cancel / Reject Bill ${billNo}</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <p class="text-muted text-sm mb-16">Stock will be restored. Please specify the mandatory cancellation reason below:</p>
        <div class="form-group">
          <label class="form-label required">Select Rejection / Cancellation Reason</label>
          <select class="form-control" id="cancel-reason-select" onchange="if(this.value==='Other') document.getElementById('cancel-reason-other').focus()">
            <option value="Wrong item or quantity entered">Wrong item or quantity entered</option>
            <option value="Customer requested cancellation">Customer requested cancellation</option>
            <option value="Payment attempt failed">Payment attempt failed</option>
            <option value="Duplicate bill generated">Duplicate bill generated</option>
            <option value="Quality / Product return issue">Quality / Product return issue</option>
            <option value="Other">Other (Specify below)</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Additional Details / Notes</label>
          <textarea class="form-control" id="cancel-reason-notes" placeholder="Enter reason details..."></textarea>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Keep Bill</button>
          <button class="btn btn-danger" onclick="Billing.confirmCancelBill(${id}, '${billNo}')">⚠️ Confirm Cancellation</button>
        </div>
      </div>`);
  },

  async confirmCancelBill(id, billNo) {
    const sel = document.getElementById('cancel-reason-select').value;
    const notes = document.getElementById('cancel-reason-notes').value.trim();
    let finalReason = sel;
    if (sel === 'Other' || notes) {
      finalReason = notes ? `${sel}: ${notes}` : sel;
    }

    if (!finalReason) {
      App.toast('Cancellation reason is required', 'error');
      return;
    }

    try {
      await App.api(`/bills/${id}`, 'DELETE', { reason: finalReason });
      App.closeModal();
      App.toast(`Bill ${billNo} cancelled & stock restored!`, 'warning');
      this.loadHistory();
    } catch(e) { App.toast(e.message, 'error'); }
  },
};

// Global click-outside listener to hide search dropdowns
document.addEventListener('click', (e) => {
  const custSearch = document.getElementById('customer-search');
  const custResults = document.getElementById('customer-results');
  if (custResults && custSearch && !custSearch.contains(e.target) && !custResults.contains(e.target)) {
    custResults.style.display = 'none';
    custResults.classList.remove('show');
  }

  const prodSearch = document.getElementById('product-search');
  const prodResults = document.getElementById('product-results');
  if (prodResults && prodSearch && !prodSearch.contains(e.target) && !prodResults.contains(e.target)) {
    prodResults.style.display = 'none';
    prodResults.classList.remove('show');
  }
});

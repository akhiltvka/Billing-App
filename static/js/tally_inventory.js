/**
 * tally_inventory.js — Tally Prime–Style Inventory Management Module
 * Meat Products of India — Billing & Inventory Management App
 *
 * Views:
 *   render()            → Stock Summary Register (main view)
 *   openItemLedger(id)  → Stock Ledger drill-down
 *   openVoucher(type)   → Full-screen voucher (stock-in / wastage / PO)
 *   openCategories()    → Category master list
 *   openProducts()      → Product master list (alt view)
 */

const TallyInventory = {

  // ─── State ────────────────────────────────────────────────────────────────
  _products:       [],
  _categories:     [],
  _selectedIdx:    0,
  _filteredRows:   [],
  _currentView:    'summary',   // 'summary' | 'ledger' | 'voucher' | 'categories'
  _currentProduct: null,
  _periodFrom:     '',
  _periodTo:       '',
  _searchQ:        '',
  _voucherRows:    1,
  _fkeyHandler:    null,
  _keyNavHandler:  null,
  _suppliers:      [],

  // ─── Utility ──────────────────────────────────────────────────────────────
  _today() {
    return new Date().toISOString().slice(0, 10);
  },

  _monthStart() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
  },

  _fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' });
  },

  _fmtNum(n, dec = 3) {
    if (n === null || n === undefined || n === '') return '—';
    const v = parseFloat(n);
    if (isNaN(v)) return '—';
    return v.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  },

  _fmtAmt(n) {
    if (n === null || n === undefined || n === '') return '—';
    const v = parseFloat(n);
    if (isNaN(v)) return '—';
    return '₹' + v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  _stockClass(p) {
    if (p.closing <= 0) return 'stock-zero';
    if (p.closing <= p.min_stock * 0.5) return 'stock-critical';
    if (p.closing <= p.min_stock) return 'stock-low';
    return '';
  },

  _stockNumClass(p) {
    if (p.closing <= 0) return 'tally-stock-zero';
    if (p.closing <= p.min_stock * 0.5) return 'tally-stock-critical';
    if (p.closing <= p.min_stock) return 'tally-stock-low';
    return 'tally-stock-ok';
  },

  _stockBadge(p) {
    if (p.closing <= 0)                     return `<span class="tally-badge tally-badge-zero">ZERO</span>`;
    if (p.closing <= p.min_stock * 0.5)     return `<span class="tally-badge tally-badge-critical">⚠ CRITICAL</span>`;
    if (p.closing <= p.min_stock)           return `<span class="tally-badge tally-badge-low">LOW</span>`;
    return '';
  },

  // ─── Layout Helpers ───────────────────────────────────────────────────────
  _renderHeader(title, breadcrumbs = [], showSearch = true) {
    const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const crumbs = breadcrumbs.length
      ? breadcrumbs.map((b, i) =>
          i < breadcrumbs.length - 1
            ? `<span class="tally-breadcrumb-link" onclick="${b.onclick || ''}">${b.label}</span><span class="tally-breadcrumb-sep">›</span>`
            : `<span style="color:var(--text-secondary)">${b.label}</span>`
        ).join('')
      : '';

    return `
      <div class="tally-header">
        <div class="tally-header-title">📦 ${title}</div>
        ${crumbs ? `<div class="tally-header-breadcrumb">${crumbs}</div>` : '<div style="flex:1"></div>'}
        ${showSearch ? `
        <div class="tally-header-search">
          🔎 <input id="tally-search" type="text" placeholder="Search items…"
            value="${this._searchQ}"
            oninput="TallyInventory._onSearch(this.value)">
        </div>` : ''}
        <div class="tally-header-date">📅 ${today}</div>
        <div class="tally-header-btns">
          <button class="tally-hbtn" onclick="TallyInventory.render()">↺ Refresh</button>
          ${Auth.can('stock.in') ? '<button class="tally-hbtn tally-hbtn-primary" onclick="TallyInventory.openVoucher(\'stock-in\')">+ Stock-In</button>' : ''}
        </div>
      </div>`;
  },

  _renderPeriodBar() {
    return `
      <div class="tally-period-bar">
        <label>Period:</label>
        <input type="date" id="tally-from" value="${this._periodFrom}" max="${this._today()}">
        <span style="color:#888">to</span>
        <input type="date" id="tally-to"   value="${this._periodTo}"   max="${this._today()}">
        <button class="tally-period-apply" onclick="TallyInventory._applyPeriod()">Apply</button>
        <button class="tally-period-apply" style="background:#555" onclick="TallyInventory._resetPeriod()">Current Month</button>
        <span class="tally-period-info">
          ${this._fmtDate(this._periodFrom)} — ${this._fmtDate(this._periodTo)}
        </span>
      </div>`;
  },

  _renderFKeyBar(context = 'summary') {
    const rawKeys = {
      summary: [
        { key:'F2', desc:'Period', onclick:"document.getElementById('tally-from')?.focus()" },
        { key:'F5', desc:'Stock-In',      perm:'stock.in', onclick:"TallyInventory.openVoucher('stock-in')" },
        { key:'F6', desc:'Wastage',       perm:'stock.wastage', onclick:"TallyInventory.openVoucher('wastage')" },
        { key:'F8', desc:'Purchase Order', perm:'purchase.view', onclick:"TallyInventory.openVoucher('po')" },
        { key:'F9', desc:'Categories',    perm:'inventory.view', onclick:"TallyInventory.openCategories()" },
        { key:'F10', desc:'Products',     perm:'inventory.view', onclick:"TallyInventory.openProducts()" },
        { key:'Enter', desc:'Drill Down', onclick:"TallyInventory._drillDown()" },
      ],
      ledger: [
        { key:'Esc', desc:'Back',         onclick:"TallyInventory.render()" },
        { key:'F5', desc:'Stock-In',      perm:'stock.in', onclick:"TallyInventory.openVoucher('stock-in',TallyInventory._currentProduct)" },
        { key:'F6', desc:'Wastage',       perm:'stock.wastage', onclick:"TallyInventory.openVoucher('wastage',TallyInventory._currentProduct)" },
        { key:'F3', desc:'Batch Detail',  onclick:"TallyInventory._toggleBatchSection()" },
      ],
      voucher: [
        { key:'Alt+S', desc:'Save',        onclick:"TallyInventory._submitVoucher()" },
        { key:'Alt+D', desc:'Add Row',     onclick:"TallyInventory._addVoucherRow()" },
        { key:'Esc',   desc:'Cancel',      onclick:"TallyInventory.render()" },
      ],
      categories: [
        { key:'Esc', desc:'Back',          onclick:"TallyInventory.render()" },
        { key:'F5', desc:'Add Category',   perm:'inventory.create', onclick:"Inventory.showCategoryModal()" },
      ],
    };

    const bar = (rawKeys[context] || rawKeys.summary).filter(k => !k.perm || Auth.can(k.perm));
    return `
      <div class="tally-fkey-bar">
        ${bar.map(k => `
          <button class="tally-fkey" data-key="${k.key}" onclick="${k.onclick}" title="${k.key}: ${k.desc}">
            <span class="tally-fkey-label">${k.key}</span>
            <span class="tally-fkey-desc">${k.desc}</span>
          </button>`).join('')}
        <div class="tally-fkey-spacer"></div>
      </div>`;
  },

  // ─── Period Management ────────────────────────────────────────────────────
  _applyPeriod() {
    const f = document.getElementById('tally-from')?.value;
    const t = document.getElementById('tally-to')?.value;
    if (f) this._periodFrom = f;
    if (t) this._periodTo   = t;
    this.render();
  },

  _resetPeriod() {
    this._periodFrom = this._monthStart();
    this._periodTo   = this._today();
    this.render();
  },

  _onSearch(q) {
    this._searchQ = q.toLowerCase();
    this._renderRegisterRows();
    this._selectedIdx = 0;
    this._highlightRow(0);
  },

  // ═══════════════════════════════════════════════════════════════════════════
  //  MAIN VIEW — Stock Summary Register
  // ═══════════════════════════════════════════════════════════════════════════
  async render() {
    this._currentView = 'summary';
    this._destroyKeyListeners();

    if (!this._periodFrom) this._periodFrom = this._monthStart();
    if (!this._periodTo)   this._periodTo   = this._today();

    const content = document.getElementById('page-content');
    // Show loading skeleton
    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Inventory — Stock Summary')}
        ${this._renderPeriodBar()}
        <div class="tally-body">
          <div class="tally-register-wrap">
            ${[...Array(8)].map(() => `<div class="tally-shimmer"></div>`).join('')}
          </div>
        </div>
        ${this._renderFKeyBar('summary')}
      </div>`;

    try {
      const [summary, suppliers] = await Promise.all([
        App.api(`/stock/summary?from=${this._periodFrom}&to=${this._periodTo}`),
        App.api('/suppliers').catch(() => []),
      ]);
      this._products  = summary;
      this._suppliers = suppliers;
      this._renderSummaryView(summary);
    } catch(e) {
      document.getElementById('page-content').innerHTML =
        `<div class="tally-shell">
           ${this._renderHeader('Inventory')}
           <div class="tally-empty"><div class="tally-empty-icon">⚠️</div><p>${e.message}</p></div>
           ${this._renderFKeyBar()}
         </div>`;
    }
  },

  _renderSummaryView(products) {
    const content = document.getElementById('page-content');

    // Group by category
    const groups = {};
    products.forEach(p => {
      const g = p.category_name || 'Uncategorised';
      if (!groups[g]) groups[g] = [];
      groups[g].push(p);
    });

    // Totals
    const totals = products.reduce((acc, p) => ({
      opening:  acc.opening  + (p.opening  || 0),
      inward:   acc.inward   + (p.inward   || 0),
      outward:  acc.outward  + (p.outward  || 0),
      closing:  acc.closing  + (p.closing  || 0),
      value:    acc.value    + (p.stock_value || 0),
    }), { opening: 0, inward: 0, outward: 0, closing: 0, value: 0 });

    const lowCount      = products.filter(p => p.closing <= p.min_stock && p.closing > 0).length;
    const criticalCount = products.filter(p => p.closing <= 0).length;

    // Build the flat ordered list for keyboard nav
    this._filteredRows = products;
    this._selectedIdx  = 0;

    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Inventory — Stock Summary', [], true)}
        ${this._renderPeriodBar()}
        <div class="tally-body">
          <!-- Register Table -->
          <div class="tally-register-wrap" id="tally-register-wrap" tabindex="0">
            <table class="tally-register" id="tally-register">
              <colgroup>
                <col class="col-name"><col class="col-group"><col class="col-unit">
                <col class="col-opening"><col class="col-inward"><col class="col-outward">
                <col class="col-closing"><col class="col-value">
              </colgroup>
              <thead>
                <tr>
                  <th>Stock Item</th>
                  <th>Group</th>
                  <th>Unit</th>
                  <th class="num">Opening</th>
                  <th class="num">Inward</th>
                  <th class="num">Outward</th>
                  <th class="num">Closing</th>
                  <th class="num">Value (₹)</th>
                </tr>
              </thead>
              <tbody id="tally-tbody"></tbody>
              <tfoot>
                <tr>
                  <td colspan="3">Total (${products.length} items
                    ${criticalCount > 0 ? `<span class="tally-badge tally-badge-zero">${criticalCount} zero</span>` : ''}
                    ${lowCount > 0 ? `<span class="tally-badge tally-badge-low">${lowCount} low</span>` : ''}
                  )</td>
                  <td class="num">${this._fmtNum(totals.opening)}</td>
                  <td class="num">${this._fmtNum(totals.inward)}</td>
                  <td class="num">${this._fmtNum(totals.outward)}</td>
                  <td class="num" style="font-weight:800;color:#1B2A47">${this._fmtNum(totals.closing)}</td>
                  <td class="num" style="font-weight:800;color:#1B2A47">₹${totals.value.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <!-- Right Detail Panel -->
          <div class="tally-detail-panel" id="tally-detail-panel">
            <div class="tally-detail-header">Item Details</div>
            <div id="tally-detail-body">
              <div class="tally-empty" style="padding:30px 14px;font-size:12px">
                <div class="tally-empty-icon" style="font-size:28px">👆</div>
                <p>Select an item to view details</p>
              </div>
            </div>
            <div class="tally-kbd-hints">
              <kbd class="tally-kbd">↑↓</kbd> Navigate &nbsp;
              <kbd class="tally-kbd">Enter</kbd> Drill down<br>
              <kbd class="tally-kbd">F5</kbd> Stock-In &nbsp;
              <kbd class="tally-kbd">F6</kbd> Wastage<br>
              <kbd class="tally-kbd">F8</kbd> Purchase Order
            </div>
          </div>
        </div>
        ${this._renderFKeyBar('summary')}
      </div>`;

    // Render rows and initialise keyboard navigation
    this._renderRegisterRows();
    this._initKeyNav();

    // Focus wrap for keyboard
    setTimeout(() => {
      document.getElementById('tally-register-wrap')?.focus();
    }, 50);
  },

  _renderRegisterRows() {
    const tbody = document.getElementById('tally-tbody');
    if (!tbody) return;

    // Filter
    const q = this._searchQ;
    const filtered = q
      ? this._products.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.category_name || '').toLowerCase().includes(q) ||
          (p.code || '').toLowerCase().includes(q))
      : this._products;

    this._filteredRows = filtered;

    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="tally-empty" style="padding:40px;text-align:center;color:#aaa">No items found</td></tr>`;
      return;
    }

    // Group by category
    const groups = {};
    filtered.forEach(p => {
      const g = p.category_name || 'Uncategorised';
      if (!groups[g]) groups[g] = [];
      groups[g].push(p);
    });

    let rowIdx = 0;
    let html = '';

    Object.entries(groups).forEach(([group, items]) => {
      const gTotal = items.reduce((a, p) => a + (p.closing || 0), 0);
      const gValue = items.reduce((a, p) => a + (p.stock_value || 0), 0);

      html += `
        <tr class="tally-group-header">
          <td colspan="7" style="padding-left:8px">▼ ${group} <span style="font-weight:400;color:#666;font-size:11px">(${items.length} items)</span></td>
          <td class="num" style="text-align:right">₹${gValue.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
        </tr>`;

      items.forEach(p => {
        const sc   = this._stockClass(p);
        const snc  = this._stockNumClass(p);
        const badge = this._stockBadge(p);
        const unit  = p.sale_unit || p.unit || '—';
        html += `
          <tr class="tally-row ${sc}" id="tally-row-${rowIdx}" data-idx="${rowIdx}" data-id="${p.id}"
              onclick="TallyInventory._selectRow(${rowIdx})"
              ondblclick="TallyInventory.openItemLedger(${p.id})">
            <td class="item-name">
              <span class="tally-row-arrow">▶</span>${p.name}${badge}
            </td>
            <td>${p.category_name || '—'}</td>
            <td>${unit}</td>
            <td class="num">${this._fmtNum(p.opening)}</td>
            <td class="num" style="color:#1a6e2c">${p.inward > 0 ? '+'+this._fmtNum(p.inward) : this._fmtNum(p.inward)}</td>
            <td class="num" style="color:#b32020">${p.outward > 0 ? '-'+this._fmtNum(p.outward) : this._fmtNum(p.outward)}</td>
            <td class="num ${snc}">${this._fmtNum(p.closing)}</td>
            <td class="num">₹${(p.stock_value||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}</td>
          </tr>`;
        rowIdx++;
      });
    });

    tbody.innerHTML = html;
    this._highlightRow(this._selectedIdx);
  },

  _selectRow(idx) {
    this._selectedIdx = idx;
    this._highlightRow(idx);
    const p = this._filteredRows[idx];
    if (p) this._renderDetailPanel(p);
  },

  _highlightRow(idx) {
    document.querySelectorAll('.tally-row').forEach(r => r.classList.remove('selected'));
    const row = document.getElementById(`tally-row-${idx}`);
    if (row) {
      row.classList.add('selected');
      row.scrollIntoView({ block: 'nearest' });
    }
  },

  _renderDetailPanel(p) {
    const body = document.getElementById('tally-detail-body');
    if (!body) return;

    const unit    = p.sale_unit || p.unit || '';
    const punit   = p.purchase_unit || p.unit || '';
    const sc      = this._stockNumClass(p);
    const expiryWarning = p.days_to_expiry !== undefined && p.days_to_expiry < 7
      ? `<span class="tally-badge tally-badge-expiring">Exp soon</span>` : '';

    body.innerHTML = `
      <div class="tally-detail-section">
        <div class="tally-detail-section-title">${p.name}</div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Code</span>
          <span class="tally-detail-value" style="font-family:monospace">${p.code || '—'}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Category</span>
          <span class="tally-detail-value">${p.category_name || '—'}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Sale Unit</span>
          <span class="tally-detail-value">${unit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Purchase Unit</span>
          <span class="tally-detail-value">${punit}</span>
        </div>
      </div>

      <div class="tally-detail-section">
        <div class="tally-detail-section-title">Stock Position</div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Opening</span>
          <span class="tally-detail-value">${this._fmtNum(p.opening)} ${unit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Inward</span>
          <span class="tally-detail-value ok">+${this._fmtNum(p.inward)} ${punit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Outward</span>
          <span class="tally-detail-value warn">-${this._fmtNum(p.outward)} ${unit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Closing</span>
          <span class="tally-detail-value ${sc}" style="font-size:14px;font-weight:800">${this._fmtNum(p.closing)} ${unit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Min Level</span>
          <span class="tally-detail-value">${this._fmtNum(p.min_stock)} ${unit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Stock Value</span>
          <span class="tally-detail-value gold">${this._fmtAmt(p.stock_value)}</span>
        </div>
      </div>

      <div class="tally-detail-section">
        <div class="tally-detail-section-title">Pricing</div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Purchase Rate</span>
          <span class="tally-detail-value">${this._fmtAmt(p.purchase_price)}/${punit}</span>
        </div>
        <div class="tally-detail-row">
          <span class="tally-detail-label">Selling Rate</span>
          <span class="tally-detail-value gold">${this._fmtAmt(p.selling_price)}/${unit}</span>
        </div>
        ${p.conversion_factor && p.conversion_factor !== 1 ? `
        <div class="tally-detail-row">
          <span class="tally-detail-label">Conversion</span>
          <span class="tally-detail-value">1 ${punit} = ${p.conversion_factor} ${unit}</span>
        </div>` : ''}
      </div>

      <div class="tally-detail-actions">
        <button class="tally-action-btn" onclick="TallyInventory.openItemLedger(${p.id})">
          📋 View Ledger
        </button>
        <button class="tally-action-btn" onclick="TallyInventory.openVoucher('stock-in', ${JSON.stringify(JSON.stringify(p))})">
          ⬆ Stock Receipt
        </button>
        <button class="tally-action-btn" onclick="TallyInventory.openVoucher('wastage', ${JSON.stringify(JSON.stringify(p))})">
          ⚠ Record Wastage
        </button>
        <button class="tally-action-btn" onclick="Inventory.showProductModal(${JSON.stringify(JSON.stringify(p))})">
          ✏ Edit Item
        </button>
      </div>`;
  },

  // ═══════════════════════════════════════════════════════════════════════════
  //  KEYBOARD NAVIGATION
  // ═══════════════════════════════════════════════════════════════════════════
  _initKeyNav() {
    this._destroyKeyListeners();

    this._keyNavHandler = (e) => {
      if (this._currentView !== 'summary') return;

      const tag = document.activeElement?.tagName;
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;

      switch (e.key) {
        case 'ArrowDown':
        case 'j':
          e.preventDefault();
          this._selectedIdx = Math.min(this._selectedIdx + 1, (this._filteredRows.length || 1) - 1);
          this._highlightRow(this._selectedIdx);
          this._renderDetailPanel(this._filteredRows[this._selectedIdx]);
          break;

        case 'ArrowUp':
        case 'k':
          e.preventDefault();
          this._selectedIdx = Math.max(this._selectedIdx - 1, 0);
          this._highlightRow(this._selectedIdx);
          this._renderDetailPanel(this._filteredRows[this._selectedIdx]);
          break;

        case 'Enter':
          e.preventDefault();
          this._drillDown();
          break;

        case 'F5':
          e.preventDefault();
          this.openVoucher('stock-in', JSON.stringify(this._filteredRows[this._selectedIdx] || null));
          break;

        case 'F6':
          e.preventDefault();
          this.openVoucher('wastage', JSON.stringify(this._filteredRows[this._selectedIdx] || null));
          break;

        case 'F8':
          e.preventDefault();
          this.openVoucher('po');
          break;

        case 'F9':
          e.preventDefault();
          this.openCategories();
          break;

        case 'F10':
          e.preventDefault();
          this.openProducts();
          break;

        case '/':
        case 'f':
          if (e.key === 'f' && !e.ctrlKey) break;
          e.preventDefault();
          document.getElementById('tally-search')?.focus();
          break;

        case 'Escape':
          e.preventDefault();
          this._searchQ = '';
          const s = document.getElementById('tally-search');
          if (s) s.value = '';
          this._renderRegisterRows();
          break;
      }
    };

    this._fkeyHandler = (e) => {
      const tag = document.activeElement?.tagName;
      if (['INPUT','SELECT','TEXTAREA'].includes(tag)) {
        if (e.key === 'Escape') { document.activeElement.blur(); return; }
      }
      if (e.key === 'F5' || e.key === 'F6' || e.key === 'F8' || e.key === 'F9' || e.key === 'F10') {
        e.preventDefault();
        this._keyNavHandler(e);
      }
    };

    document.addEventListener('keydown', this._keyNavHandler);
    document.addEventListener('keydown', this._fkeyHandler);
  },

  _destroyKeyListeners() {
    if (this._keyNavHandler) {
      document.removeEventListener('keydown', this._keyNavHandler);
      this._keyNavHandler = null;
    }
    if (this._fkeyHandler) {
      document.removeEventListener('keydown', this._fkeyHandler);
      this._fkeyHandler = null;
    }
  },

  _drillDown() {
    const p = this._filteredRows[this._selectedIdx];
    if (p) this.openItemLedger(p.id);
  },

  // ═══════════════════════════════════════════════════════════════════════════
  //  STOCK LEDGER — Drill-down view
  // ═══════════════════════════════════════════════════════════════════════════
  async openItemLedger(productId) {
    this._currentView = 'ledger';
    this._destroyKeyListeners();

    const p = this._products.find(x => x.id === productId) || { id: productId, name: 'Item' };
    this._currentProduct = p;

    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Stock Ledger', [
          { label: 'Stock Summary', onclick: 'TallyInventory.render()' },
          { label: p.name }
        ], false)}
        <div class="tally-body" style="flex-direction:column">
          <div class="tally-ledger-wrap">
            ${[...Array(6)].map(() => `<div class="tally-shimmer"></div>`).join('')}
          </div>
        </div>
        ${this._renderFKeyBar('ledger')}
      </div>`;

    try {
      const [txns, batches] = await Promise.all([
        App.api(`/stock/transactions?product_id=${productId}&limit=200&from=${this._periodFrom}&to=${this._periodTo}`),
        App.api(`/products/${productId}/batches`),
      ]);
      this._renderLedgerView(p, txns, batches);
    } catch(e) {
      App.showToast('Error loading ledger: ' + e.message, 'error');
      this.render();
    }
  },

  _renderLedgerView(p, txns, batches) {
    const content = document.getElementById('page-content');
    const unit = p.sale_unit || p.unit || '';
    const punit = p.purchase_unit || p.unit || '';

    // Compute running balance (transactions are newest-first; reverse for running balance)
    const ordered = [...txns].reverse();
    let runningBal = p.closing || 0;
    // First pass: tag each with balance
    ordered.forEach((tx, i) => {
      tx._balance = runningBal;
    });
    // Reverse again for display (newest first)
    const display = [...ordered].reverse();

    // Totals
    const totalIn  = txns.filter(t => t.type === 'in').reduce((a, t) => a + t.quantity, 0);
    const totalOut = txns.filter(t => t.type !== 'in').reduce((a, t) => a + t.quantity, 0);

    const vTypeMeta = {
      in:      { label: 'Stock Receipt', cls: 'vtype-in' },
      out:     { label: 'Stock Issue',   cls: 'vtype-out' },
      wastage: { label: 'Wastage',       cls: 'vtype-wastage' },
    };

    const batchRows = batches.filter(b => b.quantity > 0);
    const today = new Date();
    const batchHtml = batchRows.length
      ? batchRows.map(b => {
          const exp = b.expiry_date ? new Date(b.expiry_date) : null;
          const daysLeft = exp ? Math.floor((exp - today) / 86400000) : null;
          let bCls = 'batch-ok';
          if (daysLeft !== null && daysLeft < 0)  bCls = 'batch-expired';
          else if (daysLeft !== null && daysLeft < 7) bCls = 'batch-expiring';
          return `
            <tr class="${bCls}">
              <td>${b.batch_no || '—'}</td>
              <td>${this._fmtDate(b.manufacture_date) || '—'}</td>
              <td>${this._fmtDate(b.expiry_date) || '—'}</td>
              <td class="num">${this._fmtNum(b.quantity)}</td>
              <td class="num" style="color:#8B6914">${this._fmtAmt((b.quantity||0)*(p.purchase_price||0))}</td>
              <td>${daysLeft === null ? '—' : daysLeft < 0
                  ? `<span style="color:#b32020;font-weight:700">EXPIRED</span>`
                  : daysLeft < 7
                    ? `<span style="color:#a06000;font-weight:700">${daysLeft}d left</span>`
                    : `<span style="color:#1a6e2c">${daysLeft}d</span>`}</td>
            </tr>`;
        }).join('')
      : `<tr><td colspan="6" style="text-align:center;color:#aaa;padding:12px">No active batches</td></tr>`;

    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Stock Ledger', [
          { label: 'Stock Summary', onclick: 'TallyInventory.render()' },
          { label: p.name }
        ], false)}
        <div class="tally-period-bar">
          <span style="color:#1B2A47;font-weight:700">Period: ${this._fmtDate(this._periodFrom)} — ${this._fmtDate(this._periodTo)}</span>
          <span style="margin-left:20px;color:#555">Closing Balance: <strong style="font-family:monospace;color:#1B2A47">${this._fmtNum(p.closing)} ${unit}</strong></span>
          <span style="margin-left:16px;color:#1a6e2c">Inward: <strong>${this._fmtNum(totalIn)} ${punit}</strong></span>
          <span style="margin-left:16px;color:#b32020">Outward: <strong>${this._fmtNum(totalOut)} ${unit}</strong></span>
          <button class="tally-period-apply" style="margin-left:auto" onclick="TallyInventory.render()">← Back</button>
        </div>
        <div class="tally-body" style="flex-direction:column;overflow:auto">
          <div class="tally-ledger-wrap">
            <table class="tally-ledger-table">
              <colgroup>
                <col class="col-date"><col class="col-vtype"><col class="col-vno">
                <col class="col-party"><col class="col-inward"><col class="col-outward">
                <col class="col-close"><col class="col-rate"><col class="col-value">
              </colgroup>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Ref/Batch</th>
                  <th>Party</th>
                  <th class="num">Inward (${punit})</th>
                  <th class="num">Outward (${unit})</th>
                  <th class="num">Balance (${unit})</th>
                  <th class="num">Rate</th>
                  <th class="num">Value</th>
                </tr>
              </thead>
              <tbody>
                ${display.length === 0
                  ? `<tr><td colspan="9" style="text-align:center;padding:40px;color:#aaa">No transactions in this period</td></tr>`
                  : display.map(tx => {
                    const vm  = vTypeMeta[tx.type] || { label: tx.type, cls: 'vtype-out' };
                    const isIn = tx.type === 'in';
                    const rate = tx.unit_price || 0;
                    const val  = (tx.quantity || 0) * rate;
                    return `
                      <tr>
                        <td style="white-space:nowrap">${this._fmtDate(tx.date)}</td>
                        <td><span class="vtype-badge ${vm.cls}">${vm.label}</span></td>
                        <td style="font-family:monospace;font-size:11px">${tx.batch_no || tx.reference_no || '—'}</td>
                        <td>${tx.supplier_name || '—'}</td>
                        <td class="num" style="color:#1a6e2c">${isIn ? this._fmtNum(tx.quantity) : ''}</td>
                        <td class="num" style="color:#b32020">${!isIn ? this._fmtNum(tx.quantity) : ''}</td>
                        <td class="num" style="font-weight:700">${this._fmtNum(tx._balance)}</td>
                        <td class="num">${rate ? this._fmtAmt(rate) : '—'}</td>
                        <td class="num">${val ? this._fmtAmt(val) : '—'}</td>
                      </tr>`;
                  }).join('')}
              </tbody>
              <tfoot>
                <tr>
                  <td colspan="4">Period Total</td>
                  <td class="num" style="color:#1a6e2c">${this._fmtNum(totalIn)}</td>
                  <td class="num" style="color:#b32020">${this._fmtNum(totalOut)}</td>
                  <td class="num" style="font-weight:700">${this._fmtNum(p.closing)}</td>
                  <td colspan="2"></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <!-- Batch Summary Panel -->
          <div class="tally-batch-section">
            <div class="tally-batch-section-title">🗂 Batch / Lot Summary — ${p.name}</div>
            <table class="tally-batch-table">
              <thead>
                <tr>
                  <th>Batch No.</th>
                  <th>Mfg Date</th>
                  <th>Expiry</th>
                  <th class="num">Closing Qty (${unit})</th>
                  <th class="num">Value</th>
                  <th>Shelf Life</th>
                </tr>
              </thead>
              <tbody>${batchHtml}</tbody>
            </table>
          </div>
        </div>
        ${this._renderFKeyBar('ledger')}
      </div>`;
  },

  // ═══════════════════════════════════════════════════════════════════════════
  //  VOUCHER FORMS — Full-screen Tally-style entry
  // ═══════════════════════════════════════════════════════════════════════════
  _voucherMeta: {
    'stock-in': {
      title:     'Stock Receipt',
      titleIcon: '⬆',
      color:     '#1a6e2c',
      vno:       'SR',
      hasSupplier: true,
      hasExpiry:   true,
      btnLabel:  'Accept Receipt',
    },
    'wastage': {
      title:     'Wastage Voucher',
      titleIcon: '⚠',
      color:     '#b32020',
      vno:       'WV',
      hasSupplier: false,
      hasExpiry:   false,
      btnLabel:  'Record Wastage',
    },
    'po': {
      title:     'Purchase Order',
      titleIcon: '📋',
      color:     '#1B2A47',
      vno:       'PO',
      hasSupplier: true,
      hasExpiry:   false,
      btnLabel:  'Place Order',
    },
  },

  _voucherState: {
    type:     'stock-in',
    date:     '',
    supplier: '',
    refNo:    '',
    reason:   '',
    narration:'',
    rows:     [],
  },

  async openVoucher(type, productJson = null) {
    this._currentView = 'voucher';
    this._destroyKeyListeners();

    const meta = this._voucherMeta[type] || this._voucherMeta['stock-in'];
    const preset = productJson ? (typeof productJson === 'string' ? JSON.parse(productJson) : productJson) : null;

    const [products, categories, suppliers] = await Promise.all([
      this._products.length ? Promise.resolve(this._products) : App.api('/products?active=true'),
      this._categories.length ? Promise.resolve(this._categories) : App.api('/categories'),
      this._suppliers.length ? Promise.resolve(this._suppliers) : App.api('/suppliers'),
    ]);
    this._products   = products;
    this._categories = categories;
    this._suppliers  = suppliers;

    this._voucherState = {
      type,
      date:      this._today(),
      supplier:  '',
      refNo:     '',
      reason:    '',
      narration: '',
      rows: [this._emptyVoucherRow(preset)],
    };

    this._renderVoucherForm(meta, suppliers, products);
    this._initVoucherKeyListeners();
  },

  _emptyVoucherRow(preset = null) {
    return {
      productId:   preset?.id || '',
      batchNo:     '',
      expiryDate:  '',
      mfgDate:     '',
      qty:         '',
      rate:        preset?.purchase_price || '',
      amount:      '',
    };
  },

  _renderVoucherForm(meta, suppliers, products) {
    const vs      = this._voucherState;
    const type    = vs.type;
    const content = document.getElementById('page-content');
    const today   = this._today();

    const productOptions = products.map(p =>
      `<option value="${p.id}" data-rate="${p.purchase_price || 0}" data-unit="${p.purchase_unit || p.unit || ''}">${p.name} [${p.code}]</option>`
    ).join('');

    const supplierOptions = suppliers.map(s =>
      `<option value="${s.id}">${s.name}</option>`
    ).join('');

    const rowHtml = vs.rows.map((r, i) => this._renderVoucherRowHtml(r, i, productOptions, meta)).join('');

    content.innerHTML = `
      <div class="tally-voucher-shell">
        <!-- Header -->
        <div class="tally-voucher-header">
          <div class="tally-voucher-title" style="color:${meta.color}">${meta.titleIcon} ${meta.title}</div>
          <div class="tally-voucher-meta">
            <span>Voucher No.: <strong>${meta.vno}-${Date.now().toString().slice(-4)}</strong></span>
            <span>Date: <strong id="vhdr-date">${this._fmtDate(today)}</strong></span>
            ${meta.hasSupplier && vs.supplier ? `<span id="vhdr-party">Party: <strong></strong></span>` : ''}
          </div>
        </div>

        <!-- Body -->
        <div class="tally-voucher-body">
          <!-- Top fields -->
          <div class="tally-voucher-top">
            <div class="tally-field">
              <label>Date</label>
              <input type="date" id="v-date" value="${today}" max="${today}"
                onchange="TallyInventory._voucherState.date=this.value;document.getElementById('vhdr-date').textContent=TallyInventory._fmtDate(this.value)">
            </div>
            ${meta.hasSupplier ? `
            <div class="tally-field">
              <label>Supplier / Party</label>
              <select id="v-supplier" onchange="TallyInventory._voucherState.supplier=this.value">
                <option value="">— Select Supplier —</option>
                ${supplierOptions}
              </select>
            </div>` : `<div class="tally-field">
              <label>Reason for ${type === 'wastage' ? 'Wastage' : 'Issue'}</label>
              <input type="text" id="v-reason" placeholder="e.g. Spoilage, trimming loss, quality rejection"
                onchange="TallyInventory._voucherState.reason=this.value">
            </div>`}
            <div class="tally-field">
              <label>Reference No.</label>
              <input type="text" id="v-refno" placeholder="Invoice / PO / Challan No."
                onchange="TallyInventory._voucherState.refNo=this.value">
            </div>
          </div>

          <!-- Items table -->
          <div class="tally-voucher-items">
            <table class="tally-items-table" id="voucher-items-table">
              <colgroup>
                <col class="col-sno"><col class="col-item">
                ${meta.hasExpiry ? `<col class="col-batch"><col class="col-expiry">` : '<col class="col-batch">'}
                <col class="col-qty"><col class="col-unit"><col class="col-rate"><col class="col-amount">
              </colgroup>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Stock Item</th>
                  ${meta.hasExpiry ? `<th>Batch No.</th><th>Expiry Date</th>` : `<th>Batch / Ref</th>`}
                  <th class="num">Quantity</th>
                  <th>Unit</th>
                  <th class="num">Rate (₹)</th>
                  <th class="num">Amount (₹)</th>
                </tr>
              </thead>
              <tbody id="voucher-rows">
                ${rowHtml}
              </tbody>
            </table>
            <button class="tally-add-row-btn" onclick="TallyInventory._addVoucherRow()">
              ＋ Add Item Row &nbsp;<kbd class="tally-kbd">Alt+D</kbd>
            </button>
          </div>

          <!-- Bottom: narration + totals -->
          <div class="tally-voucher-bottom">
            <div class="tally-narration tally-field">
              <label>Narration</label>
              <textarea id="v-narration" placeholder="Optional notes / remarks…"
                onchange="TallyInventory._voucherState.narration=this.value"></textarea>
            </div>
            <div class="tally-totals-box">
              <div class="tally-totals-row">
                <span class="tally-totals-label">Items</span>
                <span class="tally-totals-value" id="v-total-items">0</span>
              </div>
              <div class="tally-totals-row">
                <span class="tally-totals-label">Total Qty</span>
                <span class="tally-totals-value" id="v-total-qty">0</span>
              </div>
              <div class="tally-totals-row grand">
                <span class="tally-totals-label">Grand Total</span>
                <span class="tally-totals-value" id="v-grand-total">₹0.00</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer bar -->
        <div class="tally-voucher-footer">
          <button class="tally-vbtn save" onclick="TallyInventory._submitVoucher()">
            <span class="tally-vbtn-key">Alt+S</span> ${meta.btnLabel}
          </button>
          <button class="tally-vbtn" onclick="TallyInventory._addVoucherRow()">
            <span class="tally-vbtn-key">Alt+D</span> Add Row
          </button>
          <button class="tally-vbtn cancel" onclick="TallyInventory.render()">
            <span class="tally-vbtn-key">Esc</span> Cancel
          </button>
        </div>
      </div>`;

    this._recalcVoucherTotals();
    // Auto-focus first product field
    setTimeout(() => document.querySelector('.v-product-sel')?.focus(), 80);
  },

  _renderVoucherRowHtml(row, idx, productOptions, meta) {
    return `
      <tr class="tally-item-row" id="vrow-${idx}">
        <td style="text-align:center;color:#888;font-size:11px;padding:5px 4px">${idx + 1}</td>
        <td>
          <select class="v-product-sel" data-row="${idx}" onchange="TallyInventory._onVoucherProductChange(this,${idx})">
            <option value="">— Select Item —</option>
            ${productOptions}
          </select>
        </td>
        <td>
          <input type="text" placeholder="Batch No." class="v-batch"
            data-row="${idx}" value="${row.batchNo || ''}"
            onchange="TallyInventory._voucherState.rows[${idx}].batchNo=this.value">
        </td>
        ${meta.hasExpiry ? `
        <td>
          <input type="date" class="v-expiry" data-row="${idx}" value="${row.expiryDate || ''}"
            onchange="TallyInventory._voucherState.rows[${idx}].expiryDate=this.value">
        </td>` : ''}
        <td>
          <input type="number" placeholder="0" step="0.001" min="0" class="v-qty num"
            data-row="${idx}" value="${row.qty || ''}"
            oninput="TallyInventory._onVoucherQtyChange(this,${idx})">
        </td>
        <td>
          <input type="text" class="v-unit" data-row="${idx}" value="${row.unit || ''}" readonly
            style="background:#F0F0F0;color:#555;cursor:default">
        </td>
        <td>
          <input type="number" placeholder="0.00" step="0.01" min="0" class="v-rate num"
            data-row="${idx}" value="${row.rate || ''}"
            oninput="TallyInventory._onVoucherQtyChange(this,${idx})">
        </td>
        <td class="amount-cell" id="vrow-amt-${idx}">—</td>
      </tr>`;
  },

  _onVoucherProductChange(sel, idx) {
    const pid  = sel.value;
    const opt  = sel.selectedOptions[0];
    const rate = opt?.dataset.rate || '';
    const unit = opt?.dataset.unit || '';
    const row  = this._voucherState.rows[idx];
    if (row) {
      row.productId = pid;
      row.rate = rate;
      row.unit = unit;
    }
    const rateInput = document.querySelector(`.v-rate[data-row="${idx}"]`);
    const unitInput = document.querySelector(`.v-unit[data-row="${idx}"]`);
    if (rateInput) rateInput.value = rate;
    if (unitInput) unitInput.value = unit;
    this._recalcVoucherTotals();
  },

  _onVoucherQtyChange(inp, idx) {
    const row = this._voucherState.rows[idx];
    if (!row) return;
    const qty  = parseFloat(document.querySelector(`.v-qty[data-row="${idx}"]`)?.value) || 0;
    const rate = parseFloat(document.querySelector(`.v-rate[data-row="${idx}"]`)?.value) || 0;
    const amt  = qty * rate;
    row.qty    = qty;
    row.rate   = rate;
    row.amount = amt;
    const amtCell = document.getElementById(`vrow-amt-${idx}`);
    if (amtCell) amtCell.textContent = amt > 0 ? `₹${amt.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}` : '—';
    this._recalcVoucherTotals();
  },

  _addVoucherRow() {
    const state   = this._voucherState;
    const meta    = this._voucherMeta[state.type];
    const idx     = state.rows.length;
    state.rows.push(this._emptyVoucherRow());

    const productOptions = this._products.map(p =>
      `<option value="${p.id}" data-rate="${p.purchase_price || 0}" data-unit="${p.purchase_unit || p.unit || ''}">${p.name} [${p.code}]</option>`
    ).join('');

    const tbody = document.getElementById('voucher-rows');
    if (!tbody) return;
    const tr = document.createElement('tr');
    tr.classList.add('tally-item-row');
    tr.id = `vrow-${idx}`;
    tr.innerHTML = this._renderVoucherRowHtml(state.rows[idx], idx, productOptions, meta);
    tbody.appendChild(tr);
    tr.querySelector('.v-product-sel')?.focus();
  },

  _recalcVoucherTotals() {
    const rows = this._voucherState.rows;
    let totalQty = 0, grandTotal = 0, items = 0;
    rows.forEach(r => {
      const qty = parseFloat(r.qty) || 0;
      const rate= parseFloat(r.rate) || 0;
      if (r.productId && qty > 0) {
        items++;
        totalQty  += qty;
        grandTotal += qty * rate;
      }
    });
    const ti = document.getElementById('v-total-items');
    const tq = document.getElementById('v-total-qty');
    const gt = document.getElementById('v-grand-total');
    if (ti) ti.textContent = items;
    if (tq) tq.textContent = this._fmtNum(totalQty);
    if (gt) gt.textContent = `₹${grandTotal.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  },

  async _submitVoucher() {
    const vs   = this._voucherState;
    const meta = this._voucherMeta[vs.type];

    // Collect live form values
    vs.date     = document.getElementById('v-date')?.value     || vs.date;
    vs.supplier = document.getElementById('v-supplier')?.value || vs.supplier;
    vs.refNo    = document.getElementById('v-refno')?.value    || vs.refNo;
    vs.reason   = document.getElementById('v-reason')?.value   || vs.reason;
    vs.narration= document.getElementById('v-narration')?.value|| vs.narration;

    // Collect row values from DOM
    vs.rows.forEach((row, idx) => {
      row.productId  = document.querySelector(`.v-product-sel[data-row="${idx}"]`)?.value  || row.productId;
      row.batchNo    = document.querySelector(`.v-batch[data-row="${idx}"]`)?.value        || row.batchNo;
      row.expiryDate = document.querySelector(`.v-expiry[data-row="${idx}"]`)?.value       || row.expiryDate;
      row.qty        = parseFloat(document.querySelector(`.v-qty[data-row="${idx}"]`)?.value)  || row.qty;
      row.rate       = parseFloat(document.querySelector(`.v-rate[data-row="${idx}"]`)?.value) || row.rate;
    });

    const validRows = vs.rows.filter(r => r.productId && parseFloat(r.qty) > 0);
    if (!validRows.length) {
      App.showToast('Add at least one item with quantity > 0', 'error'); return;
    }

    const btn = document.querySelector('.tally-vbtn.save');
    if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

    try {
      for (const row of validRows) {
        const payload = {
          product_id: parseInt(row.productId),
          quantity:   parseFloat(row.qty),
          unit_price: parseFloat(row.rate) || 0,   // API field: unit_price
          date:       vs.date,
          notes:      vs.narration || vs.reason || '',
          reference:  vs.refNo || '',              // API field: reference
        };

        if (vs.type === 'stock-in') {
          if (row.batchNo)    payload.batch_no         = row.batchNo;
          if (row.expiryDate) payload.expiry_date      = row.expiryDate;
          if (row.mfgDate)    payload.manufacture_date = row.mfgDate;
          if (vs.supplier)    payload.supplier_id      = parseInt(vs.supplier);
          await App.api('/stock/in', { method: 'POST', body: JSON.stringify(payload) });

        } else if (vs.type === 'wastage') {
          payload.reason = vs.reason || 'Manual wastage entry';
          await App.api('/stock/wastage', { method: 'POST', body: JSON.stringify(payload) });

        } else if (vs.type === 'po') {
          // PO is per-voucher, not per-row (first valid row's product used for now)
          const poPayload = {
            supplier_id:     parseInt(vs.supplier),
            product_id:      parseInt(row.productId),
            quantity_ordered: parseFloat(row.qty),
            price_per_unit:  parseFloat(row.rate) || 0,
            expected_date:   row.expiryDate || '',
            notes:           vs.narration || '',
          };
          await App.api('/purchase-orders', { method: 'POST', body: JSON.stringify(poPayload) });
        }
      }
      App.showToast(`${meta.title} saved successfully`, 'success');
      this._periodFrom = this._monthStart();
      this._periodTo   = this._today();
      this.render();
    } catch(e) {
      App.showToast('Error: ' + e.message, 'error');
      if (btn) { btn.disabled = false; btn.innerHTML = `<span class="tally-vbtn-key">Alt+S</span> ${meta.btnLabel}`; }
    }
  },

  _initVoucherKeyListeners() {
    this._destroyKeyListeners();
    this._fkeyHandler = (e) => {
      if (e.altKey && e.key === 's') { e.preventDefault(); this._submitVoucher(); }
      if (e.altKey && e.key === 'd') { e.preventDefault(); this._addVoucherRow(); }
      if (e.key === 'Escape') { e.preventDefault(); this.render(); }
    };
    document.addEventListener('keydown', this._fkeyHandler);
  },

  // ═══════════════════════════════════════════════════════════════════════════
  //  CATEGORIES VIEW
  // ═══════════════════════════════════════════════════════════════════════════
  async openCategories() {
    this._currentView = 'categories';
    this._destroyKeyListeners();

    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Stock Groups (Categories)', [
          { label: 'Stock Summary', onclick: 'TallyInventory.render()' },
          { label: 'Stock Groups' }
        ], false)}
        <div class="tally-body" style="padding:0">
          <div style="flex:1;overflow:auto">
            ${[...Array(4)].map(() => `<div class="tally-shimmer"></div>`).join('')}
          </div>
        </div>
        ${this._renderFKeyBar('categories')}
      </div>`;

    try {
      const cats = await App.api('/categories');
      this._categories = cats;
      this._renderCategoriesView(cats);
    } catch(e) {
      App.showToast(e.message, 'error');
    }
  },

  _renderCategoriesView(cats) {
    const content = document.getElementById('page-content');
    const rows = cats.map(c => `
      <tr style="border-bottom:1px solid #EBEBEB;cursor:pointer" onclick="">
        <td style="padding:8px 14px;font-weight:600;color:#1B2A47">${c.name}</td>
        <td style="padding:8px 14px;color:#555">GST ${c.gst_rate || 0}%</td>
        <td style="padding:8px 14px;color:#555">${c.hsn_code || '—'}</td>
        <td style="padding:8px 14px">
          <button class="tally-hbtn" onclick="Inventory.showCategoryModal(${c.id})">✏ Edit</button>
        </td>
      </tr>`).join('');

    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Stock Groups (Categories)', [
          { label: 'Stock Summary', onclick: 'TallyInventory.render()' },
          { label: 'Stock Groups' }
        ], false)}
        <div class="tally-body" style="padding:0">
          <div style="flex:1;overflow:auto;background:#fff">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
              <thead>
                <tr style="background:#D8DCE8;border-bottom:2px solid #B0B4C0">
                  <th style="padding:7px 14px;text-align:left;font-size:12px;color:#1B2A47;font-weight:700">Category Name</th>
                  <th style="padding:7px 14px;text-align:left;font-size:12px;color:#1B2A47;font-weight:700">GST Rate</th>
                  <th style="padding:7px 14px;text-align:left;font-size:12px;color:#1B2A47;font-weight:700">HSN Code</th>
                  <th style="padding:7px 14px;text-align:left;font-size:12px;color:#1B2A47;font-weight:700">Actions</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </div>
        ${this._renderFKeyBar('categories')}
      </div>`;
  },

  // ═══════════════════════════════════════════════════════════════════════════
  //  PRODUCTS MASTER LIST
  // ═══════════════════════════════════════════════════════════════════════════
  async openProducts() {
    this._currentView = 'products';
    this._destroyKeyListeners();
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="tally-shell">
        ${this._renderHeader('Stock Items (Masters)', [
          { label: 'Stock Summary', onclick: 'TallyInventory.render()' },
          { label: 'Stock Items' }
        ], false)}
        <div class="tally-body" style="flex-direction:column;overflow:auto;background:#fff">
          ${[...Array(6)].map(() => `<div class="tally-shimmer" style="margin:6px 10px"></div>`).join('')}
        </div>
        ${this._renderFKeyBar('categories')}
      </div>`;

    try {
      const [products, cats] = await Promise.all([
        App.api('/products?active=true'),
        App.api('/categories'),
      ]);
      this._products   = products;
      this._categories = cats;

      const catMap = {};
      cats.forEach(c => { catMap[c.id] = c.name; });

      const rows = products.map(p => {
        const unit  = p.sale_unit || p.unit;
        const punit = p.purchase_unit || p.unit;
        const sc    = p.current_stock <= 0 ? 'color:#b32020;font-weight:700'
                    : p.current_stock <= p.min_stock ? 'color:#a06000;font-weight:700'
                    : 'color:#1a6e2c';
        return `
          <tr style="border-bottom:1px solid #EBEBEB;cursor:pointer"
              ondblclick="Inventory.showProductModal(${JSON.stringify(JSON.stringify(p))})">
            <td style="padding:6px 14px;font-weight:600;color:#1B2A47;font-family:monospace">${p.code}</td>
            <td style="padding:6px 14px;font-weight:600">${p.name}</td>
            <td style="padding:6px 14px;color:#555">${catMap[p.category_id] || '—'}</td>
            <td style="padding:6px 14px;text-align:right;font-family:monospace;${sc}">${(p.current_stock||0).toFixed(3)} ${unit}</td>
            <td style="padding:6px 14px;text-align:right;font-family:monospace;color:#555">${(p.min_stock||0).toFixed(3)} ${unit}</td>
            <td style="padding:6px 14px;text-align:right;font-family:monospace">₹${parseFloat(p.purchase_price||0).toFixed(2)}/${punit}</td>
            <td style="padding:6px 14px;text-align:right;font-family:monospace;color:#8B6914">₹${parseFloat(p.selling_price||0).toFixed(2)}/${unit}</td>
            <td style="padding:6px 14px">
              <button class="tally-hbtn" onclick="Inventory.showProductModal(${JSON.stringify(JSON.stringify(p))})">✏</button>
              <button class="tally-hbtn" style="color:#4AE84A" onclick="TallyInventory.openVoucher('stock-in',${JSON.stringify(JSON.stringify(p))})">⬆</button>
            </td>
          </tr>`;
      }).join('');

      content.innerHTML = `
        <div class="tally-shell">
          ${this._renderHeader('Stock Items (Masters)', [
            { label: 'Stock Summary', onclick: 'TallyInventory.render()' },
            { label: 'Stock Items' }
          ], false)}
          <div class="tally-body" style="flex-direction:column;overflow:auto;background:#fff">
            <table style="width:100%;border-collapse:collapse;font-size:12.5px">
              <thead style="position:sticky;top:0;z-index:5">
                <tr style="background:#D8DCE8;border-bottom:2px solid #B0B4C0">
                  <th style="padding:6px 14px;text-align:left;font-size:11.5px;color:#1B2A47">Code</th>
                  <th style="padding:6px 14px;text-align:left;font-size:11.5px;color:#1B2A47">Name</th>
                  <th style="padding:6px 14px;text-align:left;font-size:11.5px;color:#1B2A47">Group</th>
                  <th style="padding:6px 14px;text-align:right;font-size:11.5px;color:#1B2A47">Closing Stock</th>
                  <th style="padding:6px 14px;text-align:right;font-size:11.5px;color:#1B2A47">Min Stock</th>
                  <th style="padding:6px 14px;text-align:right;font-size:11.5px;color:#1B2A47">Purchase Rate</th>
                  <th style="padding:6px 14px;text-align:right;font-size:11.5px;color:#1B2A47">Selling Rate</th>
                  <th style="padding:6px 14px;font-size:11.5px;color:#1B2A47">Actions</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
          ${this._renderFKeyBar('categories')}
        </div>`;
    } catch(e) {
      App.showToast(e.message, 'error');
    }
  },
};

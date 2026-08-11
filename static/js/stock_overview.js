const StockOverview = {
  _data: null,
  _filters: {
    category: '',
    supplier: '',
    status: '',
    month: '',
    search: ''
  },
  _viewMode: 'product', // 'product', 'category', 'flat'
  _expandedRows: new Set(),
  _catChart: null,
  _monthChart: null,

  getBatchUnitCost(b) {
    if (b.unit_cost && b.unit_cost > 0) return b.unit_cost;
    if (b.unit_price && b.unit_price > 0) return b.unit_price;
    if (b.purchase_price && b.purchase_price > 0) return b.purchase_price;
    // Fallback to selling price if purchase cost is 0
    return b.selling_price || 0;
  },

  async render() {
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="loading-overlay">
        <div class="spinner"></div>
        <div>Loading Stock Overview...</div>
      </div>
    `;

    try {
      const data = await App.api('/stock/detailed-overview');
      this._data = data;
      this.renderLayout();
      this.populateFilterDropdowns();
      this.updateMetrics();
      this.renderAlerts();
      this.renderCharts();
      this.applyFilters();
    } catch(e) {
      console.error(e);
      App.toast("Error loading stock overview: " + e.message, "error");
      content.innerHTML = `<div class="card error-card">⚠️ Error loading data: ${e.message}</div>`;
    }
  },

  renderLayout() {
    const content = document.getElementById('page-content');
    content.innerHTML = `
      <div class="page-enter">
        <!-- 4-Card Horizontal Metric Grid -->
        <div class="so-kpi-grid mb-16">
          <div class="so-kpi-card" style="border-left:4px solid var(--gold)">
            <div>
              <div class="metric-label">Total Stock Value (Cost)</div>
              <div class="metric-value text-gold" id="so-metric-cost-val" style="font-size:24px;font-weight:800;margin:4px 0">₹0.00</div>
            </div>
            <div class="metric-sub" id="so-metric-cost-sub" style="font-size:11px;color:var(--text-muted)">Based on batch unit costs / pricing</div>
          </div>

          <div class="so-kpi-card" style="border-left:4px solid var(--primary, #6366f1)">
            <div>
              <div class="metric-label">Retail Value (Selling)</div>
              <div class="metric-value text-primary" id="so-metric-retail-val" style="font-size:24px;font-weight:800;margin:4px 0">₹0.00</div>
            </div>
            <div class="metric-sub" id="so-metric-retail-sub" style="font-size:11px;color:var(--text-muted)">Potential sales revenue</div>
          </div>

          <div class="so-kpi-card" style="border-left:4px solid var(--warning, #f59e0b)">
            <div>
              <div class="metric-label">Stock Alerts</div>
              <div class="metric-value text-warning" id="so-metric-alerts-val" style="font-size:24px;font-weight:800;margin:4px 0">0</div>
            </div>
            <div class="metric-sub" style="font-size:11px;color:var(--warning)" id="so-metric-alerts-sub">Low/out of stock items</div>
          </div>

          <div class="so-kpi-card" style="border-left:4px solid #EF4444">
            <div>
              <div class="metric-label">Expiry Warnings</div>
              <div class="metric-value text-danger" id="so-metric-expiry-val" style="font-size:24px;font-weight:800;margin:4px 0">0</div>
            </div>
            <div class="metric-sub" style="font-size:11px;color:#EF4444" id="so-metric-expiry-sub">Expired / Expiring soon</div>
          </div>
        </div>

        <!-- Dual Charts & Alerts Row -->
        <div style="display:grid;grid-template-columns:1.4fr 0.6fr;gap:16px;margin-bottom:16px" class="so-dashboard-row">
          <!-- Charts Section (Dual Side-by-Side) -->
          <div class="card" style="display:flex;flex-direction:column">
            <div class="card-title" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <span>📊 Stock Visual Analytics</span>
              <span class="text-muted" style="font-size:11px">Real-time inventory breakdown</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;flex:1;align-items:center">
              <div>
                <div style="text-align:center;font-weight:600;font-size:12px;margin-bottom:6px;color:var(--text-secondary)">Value by Category</div>
                <div style="height:210px;position:relative;display:flex;justify-content:center;align-items:center">
                  <canvas id="so-chart-cat-canvas" style="max-height:200px"></canvas>
                </div>
              </div>
              <div>
                <div style="text-align:center;font-weight:600;font-size:12px;margin-bottom:6px;color:var(--text-secondary)">Monthly Purchases</div>
                <div style="height:210px;position:relative;display:flex;justify-content:center;align-items:center">
                  <canvas id="so-chart-month-canvas" style="max-height:200px"></canvas>
                </div>
              </div>
            </div>
          </div>

          <!-- Alert Panel -->
          <div class="card" style="display:flex;flex-direction:column;height:300px">
            <div class="card-title" style="color:#EF4444;margin-bottom:8px">⚠️ Critical Stock Alerts</div>
            <div id="so-alerts-list" style="flex:1;overflow-y:auto;font-size:12px;display:flex;flex-direction:column;gap:6px;padding-right:4px">
              <!-- populated dynamically -->
            </div>
          </div>
        </div>

        <!-- Filter Chips & Interactive Controls Card -->
        <div class="card mb-16" style="padding:14px">
          <!-- Quick Status Filter Chips -->
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px">
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              <div class="so-chip active" id="so-chip-all" onclick="StockOverview.setStatusChip('')">All Items</div>
              <div class="so-chip" id="so-chip-low_stock" onclick="StockOverview.setStatusChip('low_stock')">⚠️ Low Stock</div>
              <div class="so-chip" id="so-chip-out_of_stock" onclick="StockOverview.setStatusChip('out_of_stock')">❌ Out of Stock</div>
              <div class="so-chip" id="so-chip-expiring_soon" onclick="StockOverview.setStatusChip('expiring_soon')">⏳ Expiring (30d)</div>
              <div class="so-chip" id="so-chip-expired" onclick="StockOverview.setStatusChip('expired')">🚨 Expired</div>
              <div class="so-chip" id="so-chip-normal" onclick="StockOverview.setStatusChip('normal')">✓ Healthy</div>
            </div>

            <!-- View Mode Switcher Buttons -->
            <div style="display:flex;gap:4px;background:var(--bg-input);padding:3px;border-radius:6px;border:1px solid var(--border)">
              <button class="btn btn-secondary btn-xs ${this._viewMode === 'product' ? 'active' : ''}" id="so-vm-product" onclick="StockOverview.setViewMode('product')" style="padding:4px 8px;font-size:11px;border:none">📦 By Product</button>
              <button class="btn btn-secondary btn-xs ${this._viewMode === 'category' ? 'active' : ''}" id="so-vm-category" onclick="StockOverview.setViewMode('category')" style="padding:4px 8px;font-size:11px;border:none">🏷️ By Category</button>
              <button class="btn btn-secondary btn-xs ${this._viewMode === 'flat' ? 'active' : ''}" id="so-vm-flat" onclick="StockOverview.setViewMode('flat')" style="padding:4px 8px;font-size:11px;border:none">📋 All Batches</button>
            </div>
          </div>

          <!-- Secondary Filters Row -->
          <div style="display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr auto;gap:8px;align-items:end">
            <div>
              <label class="form-label" style="font-size:11px;margin-bottom:2px">Search Product / Code / Batch</label>
              <input type="text" class="form-control form-control-sm" id="so-filter-search" placeholder="Type product name, code, or batch no..." oninput="StockOverview.onFilterChange()">
            </div>
            <div>
              <label class="form-label" style="font-size:11px;margin-bottom:2px">Category</label>
              <select class="form-control form-control-sm" id="so-filter-category" onchange="StockOverview.onFilterChange()">
                <option value="">All Categories</option>
              </select>
            </div>
            <div>
              <label class="form-label" style="font-size:11px;margin-bottom:2px">Supplier</label>
              <select class="form-control form-control-sm" id="so-filter-supplier" onchange="StockOverview.onFilterChange()">
                <option value="">All Suppliers</option>
              </select>
            </div>
            <div>
              <label class="form-label" style="font-size:11px;margin-bottom:2px">Purchase Month</label>
              <select class="form-control form-control-sm" id="so-filter-month" onchange="StockOverview.onFilterChange()">
                <option value="">All Months</option>
              </select>
            </div>
            <div>
              <button class="btn btn-secondary btn-sm" onclick="StockOverview.resetFilters()" style="height:32px;padding:0 12px">Reset Filters</button>
            </div>
          </div>
        </div>

        <!-- Inventory Table / Expandable View -->
        <div class="card">
          <div class="card-title" style="display:flex;justify-content:space-between;align-items:center">
            <span id="so-table-title">📦 Current Inventory Batches</span>
            <div style="display:flex;gap:8px;align-items:center">
              <span class="text-muted" style="font-size:11px" id="so-records-count">0 items found</span>
              <button class="btn btn-secondary btn-sm" onclick="StockOverview.exportTable()">📥 Export CSV</button>
            </div>
          </div>
          <div id="so-table-container" class="table-wrap" style="max-height:550px;overflow-y:auto">
            <!-- Table content rendered dynamically based on view mode -->
          </div>
        </div>
      </div>
    `;
  },

  populateFilterDropdowns() {
    const batches = this._data.batches;
    
    // Categories
    const categories = Array.from(new Set(batches.map(b => b.category_name).filter(Boolean))).sort();
    const catSel = document.getElementById('so-filter-category');
    if (catSel) {
      catSel.innerHTML = '<option value="">All Categories</option>';
      categories.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        catSel.appendChild(opt);
      });
    }

    // Suppliers
    const suppliers = Array.from(new Set(batches.map(b => b.supplier_name).filter(Boolean))).sort();
    const supSel = document.getElementById('so-filter-supplier');
    if (supSel) {
      supSel.innerHTML = '<option value="">All Suppliers</option>';
      suppliers.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        supSel.appendChild(opt);
      });
    }

    // Purchase Months (YYYY-MM)
    const months = Array.from(new Set(batches.map(b => b.purchase_date ? b.purchase_date.slice(0, 7) : null).filter(Boolean))).sort().reverse();
    const monthSel = document.getElementById('so-filter-month');
    if (monthSel) {
      monthSel.innerHTML = '<option value="">All Months</option>';
      months.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        monthSel.appendChild(opt);
      });
    }
  },

  updateMetrics() {
    const batches = this._data.batches;
    const outOfStock = this._data.out_of_stock;
    const today = new Date();
    
    let totalCostVal = 0;
    let totalRetailVal = 0;
    let lowStockCount = 0;
    let expiredCount = 0;
    let expiringSoonCount = 0;
    
    const productStocks = {};
    const productMins = {};
    
    batches.forEach(b => {
      totalCostVal += b.quantity_remaining * this.getBatchUnitCost(b);
      totalRetailVal += b.quantity_remaining * (b.selling_price || 0);
      
      productStocks[b.product_id] = (productStocks[b.product_id] || 0) + b.quantity_remaining;
      productMins[b.product_id] = b.min_stock;
      
      if (b.expiry_date) {
        const exp = new Date(b.expiry_date);
        const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));
        if (diffDays < 0) {
          expiredCount++;
        } else if (diffDays <= 30) {
          expiringSoonCount++;
        }
      }
    });

    // Out-of-stock products
    outOfStock.forEach(p => {
      productStocks[p.product_id] = 0;
      productMins[p.product_id] = p.min_stock;
    });

    // Count low stock products
    Object.keys(productMins).forEach(pid => {
      const stock = productStocks[pid] || 0;
      const min = productMins[pid] || 0;
      if (stock <= min) {
        lowStockCount++;
      }
    });

    // Fix double currency symbol by using App.fmt directly
    document.getElementById('so-metric-cost-val').textContent = App.fmt(totalCostVal);
    document.getElementById('so-metric-retail-val').textContent = App.fmt(totalRetailVal);
    
    document.getElementById('so-metric-alerts-val').textContent = lowStockCount;
    document.getElementById('so-metric-alerts-sub').textContent = `${outOfStock.length} items out of stock | ${lowStockCount - outOfStock.length} low stock`;
    
    document.getElementById('so-metric-expiry-val').textContent = expiredCount + expiringSoonCount;
    document.getElementById('so-metric-expiry-sub').textContent = `${expiredCount} expired | ${expiringSoonCount} expiring (30d)`;
  },

  renderAlerts() {
    const batches = this._data.batches;
    const outOfStock = this._data.out_of_stock;
    const container = document.getElementById('so-alerts-list');
    if (!container) return;
    
    const today = new Date();
    const alerts = [];

    // Out of Stock alerts
    outOfStock.forEach(p => {
      alerts.push({
        type: 'danger',
        title: `${p.product_name} [${p.product_code}]`,
        text: `Completely OUT OF STOCK (Min: ${p.min_stock} ${p.unit})`
      });
    });

    // Expired or Expiring Soon batches
    batches.forEach(b => {
      if (b.expiry_date) {
        const exp = new Date(b.expiry_date);
        const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));
        if (diffDays < 0) {
          alerts.push({
            type: 'expired',
            title: `${b.product_name} (Batch: ${b.batch_no || 'N/A'})`,
            text: `EXPIRED on ${b.expiry_date} (Qty: ${App.fmtNum(b.quantity_remaining)} ${b.unit})`
          });
        } else if (diffDays <= 30) {
          alerts.push({
            type: 'warning',
            title: `${b.product_name} (Batch: ${b.batch_no || 'N/A'})`,
            text: `Expiring in ${diffDays} days on ${b.expiry_date} (Qty: ${App.fmtNum(b.quantity_remaining)} ${b.unit})`
          });
        }
      }
    });

    if (alerts.length === 0) {
      container.innerHTML = `
        <div style="text-align:center;color:var(--text-muted);padding-top:60px">
          <span style="font-size:32px">🎉</span>
          <div style="font-weight:700;margin-top:8px">All Stock Healthy</div>
          <div>No expired batches or out-of-stock items detected.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = alerts.map(a => {
      let bg = 'rgba(239, 68, 68, 0.08)';
      let border = 'rgba(239, 68, 68, 0.25)';
      let color = '#ef4444';
      let icon = '❌';
      if (a.type === 'warning') {
        bg = 'rgba(245, 158, 11, 0.08)';
        border = 'rgba(245, 158, 11, 0.25)';
        color = '#f59e0b';
        icon = '⏳';
      } else if (a.type === 'expired') {
        bg = 'rgba(185, 28, 28, 0.12)';
        border = 'rgba(185, 28, 28, 0.4)';
        color = '#b91c1c';
        icon = '🚨';
      }

      return `
        <div style="background:${bg};border:1px solid ${border};border-radius:6px;padding:8px 10px;color:var(--text-primary);border-left:4px solid ${color};text-align:left">
          <div style="font-weight:700;display:flex;align-items:center;gap:6px">
            <span>${icon}</span>
            <span>${a.title}</span>
          </div>
          <div style="color:var(--text-secondary);font-size:11px;margin-top:2px">${a.text}</div>
        </div>
      `;
    }).join('');
  },

  renderCharts() {
    if (typeof Chart === 'undefined') return;

    const batches = this._data.batches;

    // 1. Doughnut Chart: Category Distribution
    const catCanvas = document.getElementById('so-chart-cat-canvas');
    if (catCanvas) {
      if (this._catChart) this._catChart.destroy();
      const categoriesMap = {};
      batches.forEach(b => {
        const cat = b.category_name || 'Uncategorized';
        const cost = b.quantity_remaining * this.getBatchUnitCost(b);
        categoriesMap[cat] = (categoriesMap[cat] || 0) + cost;
      });

      const catLabels = Object.keys(categoriesMap);
      const catValues = Object.values(categoriesMap).map(v => Math.round(v));
      const colors = ['#6366F1', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#8B5CF6', '#3B82F6', '#06B6D4'];

      this._catChart = new Chart(catCanvas.getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: catLabels,
          datasets: [{ data: catValues, backgroundColor: colors.slice(0, catLabels.length) }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { color: 'var(--text-primary)', font: { size: 9 }, boxWidth: 10 } },
            tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${App.fmt(ctx.raw)}` } }
          }
        }
      });
    }

    // 2. Bar Chart: Monthly Purchases
    const monthCanvas = document.getElementById('so-chart-month-canvas');
    if (monthCanvas) {
      if (this._monthChart) this._monthChart.destroy();
      const monthsMap = {};
      batches.forEach(b => {
        const month = b.purchase_date ? b.purchase_date.slice(0, 7) : 'Unknown';
        const cost = b.quantity_remaining * this.getBatchUnitCost(b);
        monthsMap[month] = (monthsMap[month] || 0) + cost;
      });

      const monthLabels = Object.keys(monthsMap).sort();
      const monthValues = monthLabels.map(m => Math.round(monthsMap[m]));

      this._monthChart = new Chart(monthCanvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: monthLabels,
          datasets: [{
            label: 'Purchased Value',
            data: monthValues,
            backgroundColor: 'rgba(99, 102, 241, 0.85)',
            borderColor: '#6366F1',
            borderRadius: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { display: false }, ticks: { color: 'var(--text-muted)', font: { size: 9 } } },
            y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { color: 'var(--text-muted)', font: { size: 9 } } }
          },
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => ` Value: ${App.fmt(ctx.raw)}` } }
          }
        }
      });
    }
  },

  setStatusChip(status) {
    this._filters.status = status;
    document.querySelectorAll('.so-chip').forEach(el => el.classList.remove('active'));
    const chipId = status ? `so-chip-${status}` : 'so-chip-all';
    document.getElementById(chipId)?.classList.add('active');
    
    const sel = document.getElementById('so-filter-status');
    if (sel) sel.value = status;
    
    this.applyFilters();
  },

  setViewMode(mode) {
    this._viewMode = mode;
    document.getElementById('so-vm-product')?.classList.toggle('active', mode === 'product');
    document.getElementById('so-vm-category')?.classList.toggle('active', mode === 'category');
    document.getElementById('so-vm-flat')?.classList.toggle('active', mode === 'flat');
    
    this.applyFilters();
  },

  toggleExpand(key) {
    if (this._expandedRows.has(key)) {
      this._expandedRows.delete(key);
    } else {
      this._expandedRows.add(key);
    }
    this.applyFilters();
  },

  onFilterChange() {
    this._filters.search = document.getElementById('so-filter-search')?.value.trim().toLowerCase() || '';
    this._filters.category = document.getElementById('so-filter-category')?.value || '';
    this._filters.supplier = document.getElementById('so-filter-supplier')?.value || '';
    this._filters.status = document.getElementById('so-filter-status')?.value || '';
    this._filters.month = document.getElementById('so-filter-month')?.value || '';
    
    // Update chip active status if dropdown status changed
    document.querySelectorAll('.so-chip').forEach(el => el.classList.remove('active'));
    const chipId = this._filters.status ? `so-chip-${this._filters.status}` : 'so-chip-all';
    document.getElementById(chipId)?.classList.add('active');

    this.applyFilters();
  },

  resetFilters() {
    this._filters = { category: '', supplier: '', status: '', month: '', search: '' };
    if (document.getElementById('so-filter-search')) document.getElementById('so-filter-search').value = '';
    if (document.getElementById('so-filter-category')) document.getElementById('so-filter-category').value = '';
    if (document.getElementById('so-filter-supplier')) document.getElementById('so-filter-supplier').value = '';
    if (document.getElementById('so-filter-status')) document.getElementById('so-filter-status').value = '';
    if (document.getElementById('so-filter-month')) document.getElementById('so-filter-month').value = '';
    
    document.querySelectorAll('.so-chip').forEach(el => el.classList.remove('active'));
    document.getElementById('so-chip-all')?.classList.add('active');

    this.applyFilters();
  },

  applyFilters() {
    const batches = this._data.batches;
    const outOfStock = this._data.out_of_stock;
    const today = new Date();

    // Filter Batches
    let filteredBatches = batches.filter(b => {
      if (this._filters.search) {
        const term = this._filters.search;
        const nameMatch = (b.product_name || '').toLowerCase().includes(term);
        const codeMatch = (b.product_code || '').toLowerCase().includes(term);
        const batchMatch = (b.batch_no || '').toLowerCase().includes(term);
        if (!nameMatch && !codeMatch && !batchMatch) return false;
      }
      
      if (this._filters.category && b.category_name !== this._filters.category) return false;
      if (this._filters.supplier && b.supplier_name !== this._filters.supplier) return false;

      if (this._filters.month) {
        const bMonth = b.purchase_date ? b.purchase_date.slice(0, 7) : 'Unknown';
        if (bMonth !== this._filters.month) return false;
      }

      if (this._filters.status) {
        if (this._filters.status === 'out_of_stock') return false;
        if (this._filters.status === 'low_stock' && b.current_stock > b.min_stock) return false;
        
        if (this._filters.status === 'normal') {
          if (b.current_stock <= b.min_stock) return false;
          if (b.expiry_date) {
            const exp = new Date(b.expiry_date);
            const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));
            if (diffDays <= 30) return false;
          }
        }

        if (this._filters.status === 'expired') {
          if (!b.expiry_date) return false;
          const exp = new Date(b.expiry_date);
          if (exp >= today) return false;
        }

        if (this._filters.status === 'expiring_soon') {
          if (!b.expiry_date) return false;
          const exp = new Date(b.expiry_date);
          const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));
          if (diffDays < 0 || diffDays > 30) return false;
        }
      }

      return true;
    });

    // Filter Out of Stock
    let filteredOutOfStock = [];
    if (!this._filters.status || this._filters.status === 'out_of_stock' || this._filters.status === 'low_stock') {
      filteredOutOfStock = outOfStock.filter(p => {
        if (this._filters.search) {
          const term = this._filters.search;
          const nameMatch = (p.product_name || '').toLowerCase().includes(term);
          const codeMatch = (p.product_code || '').toLowerCase().includes(term);
          if (!nameMatch && !codeMatch) return false;
        }
        if (this._filters.category && p.category_name !== this._filters.category) return false;
        if (this._filters.supplier || this._filters.month) return false;
        return true;
      });
    }

    this.renderTableViews(filteredBatches, filteredOutOfStock);
  },

  renderTableViews(batches, outOfStock) {
    const container = document.getElementById('so-table-container');
    const recCount = document.getElementById('so-records-count');
    const tableTitle = document.getElementById('so-table-title');
    
    if (!container) return;

    if (this._viewMode === 'flat') {
      if (tableTitle) tableTitle.textContent = "📦 Flat Batch Inventory List";
      if (recCount) recCount.textContent = `${batches.length + outOfStock.length} records`;
      this.renderFlatTable(container, batches, outOfStock);
    } else if (this._viewMode === 'product') {
      if (tableTitle) tableTitle.textContent = "📦 Grouped Product Inventory (Click row to expand batches)";
      this.renderProductAccordion(container, batches, outOfStock);
    } else if (this._viewMode === 'category') {
      if (tableTitle) tableTitle.textContent = "🏷️ Category-wise Stock Summary";
      this.renderCategoryAccordion(container, batches, outOfStock);
    }
  },

  // ── 1. Expandable Product Accordion Table ──
  renderProductAccordion(container, batches, outOfStock) {
    const prodMap = {};
    
    outOfStock.forEach(p => {
      prodMap[p.product_id] = {
        product_id: p.product_id,
        name: p.product_name,
        code: p.product_code,
        category: p.category_name || '—',
        unit: p.unit,
        min_stock: p.min_stock,
        current_stock: 0,
        selling_price: p.selling_price,
        purchase_price: p.purchase_price,
        total_cost: 0,
        batches: []
      };
    });

    batches.forEach(b => {
      if (!prodMap[b.product_id]) {
        prodMap[b.product_id] = {
          product_id: b.product_id,
          name: b.product_name,
          code: b.product_code,
          category: b.category_name || '—',
          unit: b.unit,
          min_stock: b.min_stock,
          current_stock: 0,
          selling_price: b.selling_price,
          purchase_price: b.purchase_price,
          total_cost: 0,
          batches: []
        };
      }
      const p = prodMap[b.product_id];
      p.current_stock += b.quantity_remaining;
      p.total_cost += b.quantity_remaining * this.getBatchUnitCost(b);
      p.batches.push(b);
    });

    const prods = Object.values(prodMap);
    const recCount = document.getElementById('so-records-count');
    if (recCount) recCount.textContent = `${prods.length} products`;

    if (prods.length === 0) {
      container.innerHTML = `<div style="text-align:center;padding:32px;color:var(--text-muted)">🔍 No products found matching filters.</div>`;
      return;
    }

    const today = new Date();

    let html = `
      <table>
        <thead>
          <tr>
            <th style="width:30px"></th>
            <th style="text-align:left">Product Name [Code]</th>
            <th style="text-align:left">Category</th>
            <th class="num">Batches</th>
            <th class="num">Total Stock Qty</th>
            <th class="num">Min Req</th>
            <th class="num">Total Cost Value</th>
            <th>Stock Status</th>
            <th style="text-align:center">Actions</th>
          </tr>
        </thead>
        <tbody>
    `;

    prods.forEach(p => {
      const isExpanded = this._expandedRows.has(`prod-${p.product_id}`);
      let statusHtml = '<span class="badge badge-success">Healthy</span>';
      
      if (p.current_stock <= 0) {
        statusHtml = '<span class="badge badge-danger">Out of Stock</span>';
      } else if (p.current_stock <= p.min_stock) {
        statusHtml = '<span class="badge badge-warning">Low Stock</span>';
      }

      // Check if any batch is expired/expiring
      let hasExpired = false;
      let hasExpiring = false;
      p.batches.forEach(b => {
        if (b.expiry_date) {
          const exp = new Date(b.expiry_date);
          const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));
          if (diffDays < 0) hasExpired = true;
          else if (diffDays <= 30) hasExpiring = true;
        }
      });

      if (hasExpired) statusHtml = '<span class="badge badge-danger">Contains Expired</span>';
      else if (hasExpiring && p.current_stock > p.min_stock) statusHtml = '<span class="badge badge-warning">Expiring Soon</span>';

      html += `
        <tr class="so-expand-row" onclick="StockOverview.toggleExpand('prod-${p.product_id}')">
          <td style="text-align:center;font-weight:700;font-size:14px;color:var(--text-muted)">${isExpanded ? '▼' : '▶'}</td>
          <td style="font-weight:700;text-align:left">${p.name} <span class="text-muted" style="font-size:10px">[${p.code}]</span></td>
          <td style="text-align:left">${p.category}</td>
          <td class="num font-bold"><span style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:12px;font-size:11px">${p.batches.length} batch(es)</span></td>
          <td class="num font-bold ${p.current_stock <= 0 ? 'text-danger' : ''}">${App.fmtNum(p.current_stock)} ${p.unit}</td>
          <td class="num text-muted">${p.min_stock} ${p.unit}</td>
          <td class="num font-bold text-gold">${App.fmt(p.total_cost)}</td>
          <td>${statusHtml}</td>
          <td style="text-align:center" onclick="event.stopPropagation()">
            <button class="btn btn-secondary btn-sm" style="padding:2px 8px;font-size:11px;color:#0284c7;font-weight:700" onclick="Inventory.showStockAdjustmentModal(${p.product_id})" title="Edit / Correct Stock Balance">
              ⚙️ Edit Stock
            </button>
          </td>
        </tr>
      `;

      if (isExpanded) {
        html += `
          <tr>
            <td colspan="9" style="padding:0;background:var(--bg-input)">
              <div class="so-subtable-wrapper">
                <div style="font-size:11px;font-weight:700;margin-bottom:6px;color:var(--text-secondary);text-transform:uppercase">
                  📦 Batch Breakdown for ${p.name}
                </div>
                ${p.batches.length === 0 ? '<div style="color:var(--text-muted);font-style:italic">No active batches available. Item is out of stock.</div>' : `
                <table class="so-subtable">
                  <thead>
                    <tr>
                      <th style="text-align:left">Batch No</th>
                      <th class="num">Qty Remaining</th>
                      <th class="num">Unit Cost</th>
                      <th class="num">Batch Cost</th>
                      <th>Purchase Date</th>
                      <th>Expiry Date</th>
                      <th style="text-align:left">Supplier</th>
                      <th>Batch Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${p.batches.map(b => {
                      const exp = b.expiry_date ? new Date(b.expiry_date) : null;
                      const diffDays = exp ? Math.ceil((exp - today) / (1000 * 60 * 60 * 24)) : null;
                      let bStatus = '<span class="badge badge-success" style="font-size:10px">Normal</span>';
                      if (exp && diffDays < 0) bStatus = '<span class="badge badge-danger" style="font-size:10px">Expired</span>';
                      else if (exp && diffDays <= 30) bStatus = '<span class="badge badge-warning" style="font-size:10px">Expiring Soon</span>';

                      const unitCost = this.getBatchUnitCost(b);
                      return `
                        <tr>
                          <td style="text-align:left"><code>${b.batch_no || '—'}</code></td>
                          <td class="num font-bold">${App.fmtNum(b.quantity_remaining)} ${p.unit}</td>
                          <td class="num">${App.fmt(unitCost)}</td>
                          <td class="num font-bold">${App.fmt(b.quantity_remaining * unitCost)}</td>
                          <td>${b.purchase_date || '—'}</td>
                          <td>${b.expiry_date ? `<span style="${diffDays < 0 ? 'color:#ef4444;font-weight:700' : ''}">${b.expiry_date}</span>` : '—'}</td>
                          <td style="text-align:left">${b.supplier_name || '—'}</td>
                          <td>${bStatus}</td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>`}
              </div>
            </td>
          </tr>
        `;
      }
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  },

  // ── 2. Expandable Category Accordion ──
  renderCategoryAccordion(container, batches, outOfStock) {
    const catMap = {};
    
    batches.forEach(b => {
      const catName = b.category_name || 'Uncategorized';
      if (!catMap[catName]) {
        catMap[catName] = { name: catName, total_cost: 0, items_count: 0, batches: [] };
      }
      catMap[catName].total_cost += b.quantity_remaining * this.getBatchUnitCost(b);
      catMap[catName].batches.push(b);
    });

    outOfStock.forEach(p => {
      const catName = p.category_name || 'Uncategorized';
      if (!catMap[catName]) {
        catMap[catName] = { name: catName, total_cost: 0, items_count: 0, batches: [] };
      }
    });

    const categories = Object.values(catMap);
    const recCount = document.getElementById('so-records-count');
    if (recCount) recCount.textContent = `${categories.length} categories`;

    if (categories.length === 0) {
      container.innerHTML = `<div style="text-align:center;padding:32px;color:var(--text-muted)">🔍 No categories found matching filters.</div>`;
      return;
    }

    let html = `
      <table>
        <thead>
          <tr>
            <th style="width:30px"></th>
            <th style="text-align:left">Category Name</th>
            <th class="num">Total Batches</th>
            <th class="num">Category Stock Value</th>
          </tr>
        </thead>
        <tbody>
    `;

    categories.forEach(c => {
      const isExpanded = this._expandedRows.has(`cat-${c.name}`);
      html += `
        <tr class="so-expand-row" onclick="StockOverview.toggleExpand('cat-${c.name}')">
          <td style="text-align:center;font-weight:700;font-size:14px;color:var(--text-muted)">${isExpanded ? '▼' : '▶'}</td>
          <td style="font-weight:700;text-align:left">🏷️ ${c.name}</td>
          <td class="num font-bold">${c.batches.length} batch(es)</td>
          <td class="num font-bold text-gold">${App.fmt(c.total_cost)}</td>
        </tr>
      `;

      if (isExpanded) {
        html += `
          <tr>
            <td colspan="4" style="padding:0;background:var(--bg-input)">
              <div class="so-subtable-wrapper">
                <table class="so-subtable">
                  <thead>
                    <tr>
                      <th style="text-align:left">Product [Code]</th>
                      <th style="text-align:left">Batch No</th>
                      <th class="num">Remaining Qty</th>
                      <th class="num">Unit Price</th>
                      <th class="num">Total Cost</th>
                      <th>Purchase Date</th>
                      <th>Expiry Date</th>
                      <th style="text-align:left">Supplier</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${c.batches.map(b => {
                      const unitCost = this.getBatchUnitCost(b);
                      return `
                        <tr>
                          <td style="font-weight:700;text-align:left">${b.product_name} <span class="text-muted" style="font-size:10px">[${b.product_code}]</span></td>
                          <td style="text-align:left"><code>${b.batch_no || '—'}</code></td>
                          <td class="num font-bold">${App.fmtNum(b.quantity_remaining)} ${b.unit}</td>
                          <td class="num">${App.fmt(unitCost)}</td>
                          <td class="num font-bold">${App.fmt(b.quantity_remaining * unitCost)}</td>
                          <td>${b.purchase_date || '—'}</td>
                          <td>${b.expiry_date || '—'}</td>
                          <td style="text-align:left">${b.supplier_name || '—'}</td>
                        </tr>
                      `;
                    }).join('')}
                  </tbody>
                </table>
              </div>
            </td>
          </tr>
        `;
      }
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  },

  // ── 3. Flat Batch Inventory Table ──
  renderFlatTable(container, batches, outOfStock) {
    const today = new Date();

    if (batches.length === 0 && outOfStock.length === 0) {
      container.innerHTML = `<div style="text-align:center;padding:32px;color:var(--text-muted)">🔍 No batch entries found matching filters.</div>`;
      return;
    }

    let html = `
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Product [Code]</th>
            <th style="text-align:left">Category</th>
            <th style="text-align:left">Batch No</th>
            <th class="num">Qty On Hand</th>
            <th class="num">Purchase Price</th>
            <th class="num">Total Cost</th>
            <th>Expiry Date</th>
            <th>Purchase Date</th>
            <th style="text-align:left">Supplier</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
    `;

    // Out of Stock
    html += outOfStock.map(p => `
      <tr style="background:rgba(239, 68, 68, 0.05)">
        <td style="font-weight:700;text-align:left">${p.product_name} <span class="text-muted" style="font-size:10px">[${p.product_code}]</span></td>
        <td style="text-align:left">${p.category_name || '—'}</td>
        <td style="text-align:left"><code>OUT_OF_STOCK</code></td>
        <td class="num font-bold text-danger">0.000 ${p.unit}</td>
        <td class="num">${App.fmt(p.purchase_price)}</td>
        <td class="num font-bold">₹0.00</td>
        <td>—</td>
        <td>—</td>
        <td style="text-align:left">—</td>
        <td><span class="badge badge-danger">Out of Stock</span></td>
      </tr>
    `).join('');

    // Active Batches
    html += batches.map(b => {
      let statusHtml = '<span class="badge badge-success">Normal</span>';
      let rowStyle = '';
      
      const exp = b.expiry_date ? new Date(b.expiry_date) : null;
      const diffDays = exp ? Math.ceil((exp - today) / (1000 * 60 * 60 * 24)) : null;

      if (exp && diffDays < 0) {
        statusHtml = '<span class="badge badge-danger">Expired</span>';
        rowStyle = 'background:rgba(185, 28, 28, 0.04)';
      } else if (exp && diffDays <= 30) {
        statusHtml = '<span class="badge badge-warning">Expiring Soon</span>';
      } else if (b.current_stock <= b.min_stock) {
        statusHtml = '<span class="badge badge-warning">Low Stock</span>';
      }

      const unitCost = this.getBatchUnitCost(b);
      const cost = b.quantity_remaining * unitCost;

      return `
        <tr style="${rowStyle}">
          <td style="font-weight:700;text-align:left">${b.product_name} <span class="text-muted" style="font-size:10px">[${b.product_code}]</span></td>
          <td style="text-align:left">${b.category_name || '—'}</td>
          <td style="text-align:left"><code style="background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:4px">${b.batch_no || '—'}</code></td>
          <td class="num font-bold">${App.fmtNum(b.quantity_remaining)} ${b.unit}</td>
          <td class="num">${App.fmt(unitCost)}</td>
          <td class="num font-bold">${App.fmt(cost)}</td>
          <td>${b.expiry_date ? `<span style="${diffDays < 0 ? 'color:#ef4444;font-weight:700' : ''}">${b.expiry_date}</span>` : '—'}</td>
          <td>${b.purchase_date || '—'}</td>
          <td style="text-align:left">${b.supplier_name || '—'}</td>
          <td>${statusHtml}</td>
        </tr>
      `;
    }).join('');

    html += `</tbody></table>`;
    container.innerHTML = html;
  },

  exportTable() {
    const batches = this._data.batches;
    const outOfStock = this._data.out_of_stock;
    
    const headers = ["Product Name", "Product Code", "Category", "Batch No", "Quantity", "Unit", "Unit Cost", "Total Cost", "Expiry Date", "Purchase Date", "Supplier", "Status"];
    const rows = [headers];

    outOfStock.forEach(p => {
      rows.push([
        p.product_name, p.product_code, p.category_name || '', 'OUT_OF_STOCK', 0, p.unit, p.purchase_price, 0, '', '', '', 'Out of Stock'
      ]);
    });

    batches.forEach(b => {
      const unitCost = this.getBatchUnitCost(b);
      const cost = b.quantity_remaining * unitCost;
      rows.push([
        b.product_name, b.product_code, b.category_name || '', b.batch_no || '', b.quantity_remaining, b.unit, unitCost, cost, b.expiry_date || '', b.purchase_date || '', b.supplier_name || '', 'Active'
      ]);
    });

    const csvContent = "data:text/csv;charset=utf-8,\uFEFF" 
      + rows.map(r => r.map(val => `"${String(val).replace(/"/g, '""')}"`).join(",")).join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Stock_Overview_Report_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};

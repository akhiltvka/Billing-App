/**
 * settings.js — Application Settings Module
 * Meat Products of India — Billing & Inventory Management App
 */

const Settings = {
  _activeTab: 'all',
  _stockItemsData: null,

  setTab(tab) {
    this._activeTab = tab;
    document.querySelectorAll('.set-nav-chip').forEach(chip => {
      chip.classList.toggle('active', chip.dataset.tab === tab);
    });

    document.querySelectorAll('.set-section').forEach(sec => {
      if (tab === 'all') {
        sec.style.display = 'block';
      } else {
        sec.style.display = sec.dataset.section === tab ? 'block' : 'none';
      }
    });
  },

  toggleCustomFontField(val) {
    const group = document.getElementById('s-custom-font-group');
    if (group) {
      group.style.display = (val === 'custom') ? 'block' : 'none';
    }
    this.updateFontPreview();
  },

  updateFontPreview() {
    const fontSel = document.getElementById('s-brand-font')?.value || '';
    const customFont = document.getElementById('s-custom-brand-font')?.value || '';
    const previewText = document.getElementById('s-font-preview-text');
    const previewTagline = document.getElementById('s-font-preview-tagline');
    const shopNameInput = document.getElementById('s-shopname')?.value || 'Meat Products of India';
    const taglineInput = document.getElementById('s-tagline')?.value || '';
    
    let fontToApply = 'inherit';
    if (fontSel === 'custom' && customFont.trim()) {
      fontToApply = `"${customFont.trim()}", sans-serif`;
    } else if (fontSel && fontSel !== 'custom') {
      fontToApply = `"${fontSel}", sans-serif`;
    }

    if (previewText) {
      previewText.style.fontFamily = fontToApply;
      previewText.textContent = shopNameInput;
    }
    if (previewTagline) {
      previewTagline.textContent = taglineInput;
      previewTagline.style.display = taglineInput ? 'block' : 'none';
    }
  },

  async render() {
    const content = document.getElementById('page-content');
    try {
      const settings = await App.api('/settings');
      App.settings = settings;
      const standardFonts = ['Arial', 'Arial Black', 'Brush Script MT', 'Calibri', 'Cambria', 'Comic Sans MS', 'Consolas', 'Courier New', 'Garamond', 'Georgia', 'Impact', 'Lucida Console', 'Segoe Script', 'Segoe UI', 'Tahoma', 'Times New Roman', 'Trebuchet MS', 'Verdana'];
      const isCustomFont = settings.shop_brand_font && !standardFonts.includes(settings.shop_brand_font);

      content.innerHTML = `
        <div class="page-enter">
          <!-- Page Header -->
          <div class="page-header" style="margin-bottom:16px">
            <div class="page-header-left">
              <h1 style="font-size:24px;font-weight:800;display:flex;align-items:center;gap:10px">⚙️ System &amp; App Settings</h1>
              <p class="text-muted" style="font-size:12px;margin-top:2px">Configure outlet details, logo, receipt formatting, GST, backups, and user access</p>
            </div>
          </div>

          <!-- Section Navigation Tabs -->
          <div class="set-tab-nav">
            <div class="set-nav-chip active" data-tab="all" onclick="Settings.setTab('all')">🌐 All Settings</div>
            <div class="set-nav-chip" data-tab="shop" onclick="Settings.setTab('shop')">🏪 Outlet &amp; Logo</div>
            <div class="set-nav-chip" data-tab="billing" onclick="Settings.setTab('billing')">🧾 Billing &amp; Loyalty</div>
            <div class="set-nav-chip" data-tab="backup" onclick="Settings.setTab('backup')">💾 Cloud &amp; Drive Backups</div>
            <div class="set-nav-chip" data-tab="license" onclick="Settings.setTab('license')">🔑 License &amp; Subscription</div>
            <div class="set-nav-chip" data-tab="guides" onclick="Settings.setTab('guides')">📄 Reference Guides &amp; Tables</div>
          </div>

          <!-- Main Grid Layout -->
          <div class="grid-2" style="gap:20px;align-items:start">
            
            <!-- LEFT COLUMN -->
            <div>
              <!-- 1. Outlet & Shop Details Card -->
              <div class="set-card set-section" data-section="shop">
                <div class="set-card-header">
                  <div class="card-title" style="margin:0"><span class="card-title-icon">🏪</span> Outlet &amp; Business Profile</div>
                  <span class="badge badge-primary">Receipt Header</span>
                </div>
                
                <div class="form-group">
                  <label class="form-label required">Shop / Business Name</label>
                  <input class="form-control" id="s-shopname" value="${settings.shop_name || ''}" oninput="Settings.updateFontPreview()">
                </div>
                
                <div class="form-group">
                  <label class="form-label">Tagline</label>
                  <input class="form-control" id="s-tagline" value="${settings.shop_tagline || ''}" placeholder="e.g. Fresh Quality Meat Daily" oninput="Settings.updateFontPreview()">
                </div>
                
                <div class="form-group">
                  <label class="form-label">Address</label>
                  <textarea class="form-control" id="s-address" rows="2">${settings.shop_address || ''}</textarea>
                </div>
                
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input class="form-control" id="s-phone" value="${settings.shop_phone || ''}">
                  </div>
                  <div class="form-group">
                    <label class="form-label">Email</label>
                    <input class="form-control" id="s-email" value="${settings.shop_email || ''}">
                  </div>
                </div>

                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label">GSTIN</label>
                    <input class="form-control" id="s-gstin" value="${settings.shop_gstin || ''}" placeholder="32ABCDE1234F1Z5">
                  </div>
                  <div class="form-group">
                    <label class="form-label">FSSAI License</label>
                    <input class="form-control" id="s-fssai" value="${settings.shop_fssai || ''}">
                  </div>
                </div>

                <!-- Brand Font Selector & Live Preview -->
                <div class="form-group mb-16" style="border-top:1px solid var(--border);padding-top:14px;margin-top:14px">
                  <label class="form-label" style="font-weight:700">Name of Outlet Brand Font</label>
                  <select class="form-control" id="s-brand-font" onchange="Settings.toggleCustomFontField(this.value)">
                    <option value="" ${!settings.shop_brand_font ? 'selected' : ''}>Default Theme Font (Inter)</option>
                    ${standardFonts.map(f => `<option value="${f}" ${settings.shop_brand_font === f ? 'selected' : ''}>${f}</option>`).join('')}
                    <option value="custom" ${isCustomFont ? 'selected' : ''}>✍️ Custom Installed Font...</option>
                  </select>
                </div>

                <div class="form-group" id="s-custom-font-group" style="display: ${isCustomFont ? 'block' : 'none'}; margin-top: 10px;">
                  <label class="form-label">Enter Custom Font Name</label>
                  <input class="form-control" id="s-custom-brand-font" value="${settings.shop_brand_font || ''}" placeholder="e.g. Century Gothic, Garamond" oninput="Settings.updateFontPreview()">
                  <div class="form-hint">Type exact font name installed on your system.</div>
                </div>

                <!-- Live Font Preview Box -->
                <div class="set-font-preview-box mb-16" id="s-font-preview-card">
                  <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">Brand Font Live Preview</div>
                  <div id="s-font-preview-text" style="font-size:22px;font-weight:800;color:var(--primary);transition:all 0.2s ease">
                    ${settings.shop_name || 'Meat Products of India'}
                  </div>
                  <div id="s-font-preview-tagline" style="font-size:12px;color:var(--gold);font-weight:600;margin-top:4px;letter-spacing:0.5px;font-style:italic">
                    ${settings.shop_tagline || 'Fresh. Pure. Delicious.'}
                  </div>
                </div>

                <!-- Outlet Logo Upload Box -->
                <div class="form-group mb-16">
                  <label class="form-label">Outlet Logo</label>
                  <div style="display:flex;align-items:center;gap:14px;background:var(--bg-input);padding:14px;border-radius:var(--r-md);border:1px solid var(--border)">
                    <div id="s-logo-preview-box" style="width:52px;height:52px;border-radius:8px;background:var(--bg-card);border:1px dashed var(--border);display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0">
                      ${settings.shop_logo ? `<img src="${settings.shop_logo}" alt="Logo" style="width:100%;height:100%;object-fit:contain;">` : '<span style="font-size:28px">🥩</span>'}
                    </div>
                    <div style="flex:1">
                      <input type="file" id="s-logo-file" accept="image/png,image/jpeg,image/webp" style="display:none" onchange="Settings.handleLogoUpload(this)">
                      <div style="display:flex;gap:8px;margin-bottom:6px">
                        <button class="btn btn-secondary btn-sm" onclick="document.getElementById('s-logo-file').click()">🖼️ Upload PNG Logo</button>
                        <button class="btn btn-secondary btn-sm" id="s-btn-resize-logo" onclick="Settings.reopenLogoResizer()">📐 Resize</button>
                        ${settings.shop_logo ? '<button class="btn btn-danger btn-sm" onclick="Settings.removeLogo()">✕ Remove</button>' : ''}
                      </div>
                      <div class="text-muted" style="font-size:11px">Displays on Login screen, Sidebar header &amp; printed Invoices.</div>
                    </div>
                  </div>
                  <input type="hidden" id="s-shoplogo" value="${settings.shop_logo || ''}">
                </div>

                ${(Auth.can('settings.manage') || Auth.isRole('admin', 'md', 'manager')) ? '<button class="btn btn-primary w-full" style="padding:10px;font-size:14px;font-weight:700" onclick="Settings.saveShop()">💾 Save Outlet Profile</button>' : ''}
              </div>

              <!-- 2. Cloud & Real-Time Backups Card -->
              <div class="set-card set-section" data-section="backup">
                <div class="set-card-header">
                  <div class="card-title" style="margin:0"><span class="card-title-icon">💾</span> Backup &amp; Disaster Recovery</div>
                  <span class="badge badge-success">Automated Active</span>
                </div>
                
                <p class="text-muted text-sm mb-16">Automatic 6-hour cloud DB backups are active online. You can also download manual backups or configure real-time external USB drive mirroring below.</p>

                <!-- Actions Bar -->
                <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px">
                  <a href="/api/backup" class="btn btn-secondary w-full" download style="text-align:center">
                    ⬇️ Download Local Database Snapshot (.db)
                  </a>
                  <button class="btn btn-primary w-full" onclick="Settings.cloudBackupNow()">
                    ☁️ Backup to Cloud Server Now
                  </button>
                  <div style="padding:10px 12px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:var(--r-md);font-size:11.5px;color:var(--warning)">
                    ℹ️ <strong>Auto-Cloud Sync:</strong> App uploads encrypted snapshots every 6 hours automatically when connected online.
                  </div>
                </div>

                <!-- Real-Time External Drive Mirroring Section -->
                <div style="border-top:1px solid var(--border);padding-top:16px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                    <div style="font-weight:700;font-size:14px">🔌 Real-Time External USB Drive Mirroring</div>
                    <span id="ext-backup-status-badge" class="badge badge-secondary">⚪ Checking Status...</span>
                  </div>

                  <p class="text-muted text-sm mb-12">Save an instant mirrored copy of the database to an external USB flash drive or drive folder on every transaction. <strong>Available for all users.</strong></p>

                  <div class="form-group mb-12">
                    <label class="form-label" style="display:flex;align-items:center;gap:8px;cursor:pointer">
                      <input type="checkbox" id="ext-backup-enabled" style="width:18px;height:18px;cursor:pointer">
                      <strong style="font-size:13px">Enable Real-Time External Drive Mirroring</strong>
                    </label>
                  </div>

                  <div class="form-group mb-12">
                    <label class="form-label">Select Connected Drive / Folder</label>
                    <div style="display:flex;gap:8px">
                      <select id="ext-backup-drive-select" class="form-control" style="flex:1;font-weight:600" onchange="Settings.onDriveSelectChange(this.value)">
                        <option value="">Detecting drives...</option>
                      </select>
                      <button class="btn btn-secondary btn-sm" onclick="Settings.loadExternalBackupStatus()" title="Re-scan connected drives">🔄 Refresh</button>
                      <button class="btn btn-secondary btn-sm" onclick="Settings.browseNativeFolder()" title="Browse folder on computer">📂 Browse</button>
                    </div>
                  </div>

                  <div class="form-group mb-12">
                    <label class="form-label">Target External Backup Path</label>
                    <input class="form-control" id="ext-backup-path" placeholder="E:\MPI_Backups" style="font-family:monospace;font-size:13px">
                  </div>

                  <div class="form-group mb-16">
                    <label class="form-label">Backup Retention (Days)</label>
                    <input type="number" class="form-control" id="ext-backup-retention" value="30" min="1" max="365" style="width:120px">
                  </div>

                  <div id="ext-backup-last-info" class="text-muted text-sm mb-12" style="font-size:12px;font-style:italic">
                    Last Mirror: Checking...
                  </div>

                  <div style="display:flex;gap:10px">
                    <button class="btn btn-primary" style="flex:1" onclick="Settings.saveExternalBackupConfig()">💾 Save External Backup</button>
                    <button class="btn btn-secondary" onclick="Settings.testExternalBackup()">🧪 Test Drive Mirror</button>
                  </div>
                </div>
              </div>

            </div>

            <!-- RIGHT COLUMN -->
            <div>
              <!-- 3. Billing & Loyalty Preferences Card -->
              <div class="set-card set-section" data-section="billing">
                <div class="set-card-header">
                  <div class="card-title" style="margin:0"><span class="card-title-icon">🧾</span> Billing &amp; POS Preferences</div>
                  <span class="badge badge-gold">Configuration</span>
                </div>

                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label">Invoice Prefix</label>
                    <input class="form-control" id="s-prefix" value="${settings.bill_prefix || 'MPI'}" placeholder="MPI">
                    <div class="form-hint">Numbered MPI-00001, MPI-00002…</div>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Currency Symbol</label>
                    <input class="form-control" id="s-currency" value="${settings.currency_symbol || '₹'}">
                  </div>
                </div>

                <div class="form-group" style="margin-top:8px">
                  <label class="form-label">Default Invoice Print Format</label>
                  <select class="form-control" id="s-print-format" style="width:100%">
                    <option value="thermal" ${settings.default_print_format !== 'a4' ? 'selected' : ''}>🧾 Thermal Receipt Roll (Default)</option>
                    <option value="a4" ${settings.default_print_format === 'a4' ? 'selected' : ''}>🖨️ A4 Paper Invoice</option>
                  </select>
                </div>

                <div class="form-group" style="margin-top:8px">
                  <label class="form-label">Thermal Receipt Paper Size</label>
                  <select class="form-control" id="s-thermal-width" style="width:100%">
                    <option value="80" ${settings.thermal_paper_width !== '58' ? 'selected' : ''}>80mm (Standard Thermal Roll)</option>
                    <option value="58" ${settings.thermal_paper_width === '58' ? 'selected' : ''}>58mm (Small Thermal Roll)</option>
                  </select>
                </div>

                <div style="display:flex;flex-direction:column;gap:12px;margin-top:16px">
                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-gst" ${settings.gst_enabled === 'true' ? 'checked' : ''} ${(Auth.can('settings.gst_toggle') || Auth.isRole('admin', 'md', 'manager', 'accountant')) ? '' : 'disabled title="Requires permission"'}
                      style="width:18px;height:18px;accent-color:var(--primary)">
                    <div>
                      <div class="font-semibold">Enable GST Calculations</div>
                      <div class="text-muted text-sm">Show CGST + SGST breakdown in invoice printouts</div>
                    </div>
                  </label>

                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-print" ${settings.print_after_bill === 'true' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--primary)">
                    <div>
                      <div class="font-semibold">Auto-Print After Saving Bill</div>
                      <div class="text-muted text-sm">Automatically trigger print dialog on bill creation</div>
                    </div>
                  </label>

                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-show-print-preview" ${settings.show_print_preview === 'true' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--primary)">
                    <div>
                      <div class="font-semibold">Show Print Preview Modal Popup</div>
                      <div class="text-muted text-sm">Show invoice preview popup before sending to printer</div>
                    </div>
                  </label>

                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-lowstock" ${settings.low_stock_alert === 'true' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--primary)">
                    <div>
                      <div class="font-semibold">Low Stock Inventory Warnings</div>
                      <div class="text-muted text-sm">Show alerts when item stock levels fall below minimum limit</div>
                    </div>
                  </label>
                </div>

                <!-- Loyalty Program Settings -->
                <div style="border-top:1px solid var(--border);padding-top:16px;margin-top:16px">
                  <div style="font-weight:700;font-size:13.5px;color:var(--gold);margin-bottom:8px">⭐ Customer Loyalty Program</div>
                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px">
                    <input type="checkbox" id="s-loyalty-enabled" ${settings.loyalty_enabled !== 'false' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--gold)">
                    <div>
                      <div class="font-semibold">Enable Loyalty Points System</div>
                      <div class="text-muted text-sm">Customers earn &amp; redeem points for bill discounts</div>
                    </div>
                  </label>

                  <div class="form-row">
                    <div class="form-group">
                      <label class="form-label">Points per ₹100 Spent</label>
                      <input type="number" step="0.1" min="0" class="form-control" id="s-loyalty-rate-100" value="${((parseFloat(settings.loyalty_points_per_rupee || '0.01')) * 100).toFixed(1)}">
                    </div>
                    <div class="form-group">
                      <label class="form-label">Rupee Value per Point (₹)</label>
                      <input type="number" step="0.05" min="0" class="form-control" id="s-loyalty-val" value="${parseFloat(settings.loyalty_redemption_value || '0.50').toFixed(2)}">
                    </div>
                  </div>
                </div>

                <button class="btn btn-primary w-full mt-16" style="padding:10px;font-size:14px;font-weight:700" onclick="Settings.savePreferences()">💾 Save Preferences</button>
              </div>

              <!-- 4. License & System Card -->
              <div class="set-card set-section" data-section="license">
                <div class="set-card-header">
                  <div class="card-title" style="margin:0"><span class="card-title-icon">🔑</span> Software License &amp; Activation</div>
                  <span class="badge badge-info">Registration</span>
                </div>

                ${(() => {
                  const lic = App.licenseInfo || { status: 'trial', days_left: 10, expires_at: '—', machine_id: '—', price_inr: 12000 };
                  const badgeCls = lic.status === 'active' ? 'success' : lic.status === 'grace' ? 'warning' : lic.status === 'trial' ? 'info' : 'danger';
                  return `
                    <div style="display:flex;flex-direction:column;gap:12px">
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Subscription Status:</span>
                        <span class="badge badge-${badgeCls}">${lic.status.toUpperCase()} (${lic.days_left} days remaining)</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Yearly Rate:</span>
                        <span class="font-bold text-gold">₹${lic.price_inr || 12000} / Year</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Valid Until:</span>
                        <span class="font-semibold">${lic.expires_at || '—'}</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Hardware Machine ID:</span>
                        <span class="font-bold" style="font-family:monospace;font-size:12px;background:rgba(0,0,0,0.06);padding:2px 6px;border-radius:4px">${lic.machine_id}</span>
                      </div>
                      ${lic.active_key ? `
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Redeemed License Key:</span>
                        <span class="font-bold text-success" style="font-family:monospace;font-size:12px">${lic.active_key}</span>
                      </div>` : ''}
                      <button class="btn btn-primary w-full mt-8" onclick="App.showActivationModal()">
                        ⚡ Enter Activation Key / Renew License
                      </button>
                    </div>`;
                })()}
              </div>

            </div>

          </div>

          <!-- BOTTOM FULL-WIDTH SECTION: GUIDES & EXPANDING TABLES -->
          <div class="set-section mt-16" data-section="guides" style="margin-top:20px">
            
            <div style="font-weight:800;font-size:18px;margin-bottom:14px;display:flex;align-items:center;gap:8px">
              <span>📄 Reference Guides &amp; Interactive Tables</span>
            </div>

            <!-- 1. Expanding Stock Items Table Card -->
            <div class="set-expandable-card mb-16">
              <div class="set-expandable-header" onclick="Settings.toggleStockItemsTable()">
                <div style="display:flex;align-items:center;gap:12px">
                  <div style="width:36px;height:36px;background:rgba(201,168,76,0.12);border:1.5px solid rgba(201,168,76,0.35);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px">📦</div>
                  <div>
                    <div style="font-weight:700;font-size:14px">Stock Items Catalog Reference Table</div>
                    <div style="font-size:11px;color:var(--text-muted)">Expand to view all active product codes, categories, prices, and stock levels</div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:12px">
                  <span class="badge badge-gold" id="set-stock-count-badge">Click to Expand</span>
                  <span id="set-stock-chevron" style="font-weight:700;color:var(--text-muted)">▼</span>
                </div>
              </div>

              <div id="set-stock-table-body" class="set-expandable-body" style="display:none">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:12px">
                  <input type="text" class="form-control form-control-sm" id="set-stock-search" placeholder="Search product name or code..." style="max-width:300px" oninput="Settings.filterStockItemsTable()">
                  <div style="display:flex;gap:8px">
                    <button class="btn btn-primary btn-sm" onclick="Settings.openPrintablePreview('stock-items','📦 Stock Items Reference')">🖨️ Print / Export PDF</button>
                    <button class="btn btn-secondary btn-sm" onclick="window.open('/printables/stock-items','_blank')">↗ Open Full Page</button>
                  </div>
                </div>

                <div class="table-wrap" style="max-height:350px;overflow-y:auto">
                  <table style="width:100%;font-size:12px">
                    <thead>
                      <tr>
                        <th style="text-align:left">Code</th>
                        <th style="text-align:left">Product Name</th>
                        <th style="text-align:left">Category</th>
                        <th class="num">Unit Selling Price</th>
                        <th class="num">Current Stock</th>
                      </tr>
                    </thead>
                    <tbody id="set-stock-tbody">
                      <tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted)">⏳ Click expand to load catalog...</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- 2. Expanding POS Keyboard Shortcuts Table Card -->
            <div class="set-expandable-card mb-16">
              <div class="set-expandable-header" onclick="Settings.toggleShortcutsTable()">
                <div style="display:flex;align-items:center;gap:12px">
                  <div style="width:36px;height:36px;background:rgba(99,179,237,0.12);border:1.5px solid rgba(99,179,237,0.35);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px">⌨️</div>
                  <div>
                    <div style="font-weight:700;font-size:14px">POS Keyboard Shortcuts Guide</div>
                    <div style="font-size:11px;color:var(--text-muted)">Expand to view complete POS billing cheat sheet hotkeys</div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:12px">
                  <span class="badge badge-info">Cashier Hotkeys</span>
                  <span id="set-shortcuts-chevron" style="font-weight:700;color:var(--text-muted)">▼</span>
                </div>
              </div>

              <div id="set-shortcuts-table-body" class="set-expandable-body" style="display:none">
                <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
                  <button class="btn btn-primary btn-sm" onclick="Settings.openPrintablePreview('shortcuts','⌨️ Keyboard Shortcuts Reference')">🖨️ Print Shortcuts Guide</button>
                </div>

                <div class="table-wrap">
                  <table style="width:100%;font-size:12px">
                    <thead>
                      <tr>
                        <th style="text-align:left;width:160px">Shortcut Key</th>
                        <th style="text-align:left">Action Description</th>
                        <th style="text-align:left">Target Screen / Context</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">Ctrl + N</kbd></td><td>Start New Billing Invoice</td><td>Global / Billing Screen</td></tr>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">F2</kbd></td><td>Complete Cash Payment &amp; Save Bill</td><td>Billing POS Screen</td></tr>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">F4</kbd></td><td>Hold Current Bill</td><td>Billing POS Screen</td></tr>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">F8</kbd></td><td>Recall Held Bills List</td><td>Billing POS Screen</td></tr>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">Alt + B</kbd></td><td>Open Maximized Bulk Stock Entry</td><td>Global / Stock In</td></tr>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">Alt + D</kbd></td><td>Apply Invoice Level Discount</td><td>Billing POS Screen</td></tr>
                      <tr><td><kbd style="background:rgba(0,0,0,0.06);padding:2px 8px;border-radius:4px;font-weight:bold">Escape</kbd></td><td>Clear Cart / Close Modal Dialog</td><td>Global</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

          </div>

          <!-- Activity Log Section (Admin/MD) -->
          ${['admin','md'].includes(Auth.user?.role) ? `
          <div class="set-card set-section mt-16" data-section="license">
            <div class="set-card-header">
              <div class="card-title" style="margin:0"><span class="card-title-icon">📋</span> System Activity &amp; Audit Log</div>
              <button class="btn btn-secondary btn-sm" onclick="Settings.loadActivityLog(1)">🔄 Refresh Log</button>
            </div>
            
            <div style="display:flex;gap:10px;margin-bottom:14px">
              <select id="al-role-filter" class="form-control form-control-sm" style="max-width:160px">
                <option value="">All Staff Roles</option>
                <option value="admin">Admin</option>
                <option value="md">Managing Director</option>
                <option value="manager">Manager</option>
                <option value="counter_staff">Billing Staff</option>
              </select>
              <select id="al-action-filter" class="form-control form-control-sm" style="max-width:180px">
                <option value="">All System Actions</option>
                <option value="CREATE_BILL">Create Invoice</option>
                <option value="CANCEL_BILL">Cancel Invoice</option>
                <option value="ADD_PRODUCT">Add Product</option>
                <option value="ADD_STOCK">Record Stock</option>
              </select>
              <button class="btn btn-secondary btn-sm" onclick="Settings.loadActivityLog(1)">🔍 Filter Log</button>
            </div>

            <div id="activity-log-table" style="overflow-x:auto">
              <div class="empty-state" style="padding:20px">
                <p class="text-muted">Click Filter to view audit history</p>
              </div>
            </div>
            <div id="activity-log-pagination" style="display:flex;justify-content:center;gap:8px;padding:12px 0"></div>
          </div>` : ''}

        </div>
      `;
      
      this.updateFontPreview();
      if (['admin','md'].includes(Auth.user?.role)) {
        setTimeout(() => Settings.loadActivityLog(1), 100);
      }
      setTimeout(() => Settings.loadExternalBackupStatus(), 150);
    } catch(e) {
      console.error(e);
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  // ── Expandable Tables Handlers ──
  async toggleStockItemsTable() {
    const body = document.getElementById('set-stock-table-body');
    const chevron = document.getElementById('set-stock-chevron');
    if (!body) return;

    const isVisible = body.style.display !== 'none';
    body.style.display = isVisible ? 'none' : 'block';
    if (chevron) chevron.textContent = isVisible ? '▼' : '▲';

    if (!isVisible && !this._stockItemsData) {
      const tbody = document.getElementById('set-stock-tbody');
      if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted)">⏳ Loading stock catalog...</td></tr>`;

      try {
        const products = await App.api('/products?active=true');
        this._stockItemsData = products;
        const badge = document.getElementById('set-stock-count-badge');
        if (badge) badge.textContent = `${products.length} Products`;
        this.renderStockItemsRows(products);
      } catch(e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--crimson)">Error: ${e.message}</td></tr>`;
      }
    }
  },

  renderStockItemsRows(products) {
    const tbody = document.getElementById('set-stock-tbody');
    if (!tbody) return;

    if (!products || products.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:16px;color:var(--text-muted)">No active products found in catalog.</td></tr>`;
      return;
    }

    tbody.innerHTML = products.map(p => `
      <tr>
        <td style="font-weight:700"><code>${p.code || '—'}</code></td>
        <td style="font-weight:700;text-align:left">${p.name}</td>
        <td style="text-align:left">${p.category_name || 'Uncategorized'}</td>
        <td class="num font-bold text-primary">${App.fmt(p.selling_price)} / ${p.unit || 'unit'}</td>
        <td class="num font-bold ${p.current_stock <= 0 ? 'text-danger' : ''}">${App.fmtNum(p.current_stock)} ${p.unit || ''}</td>
      </tr>
    `).join('');
  },

  filterStockItemsTable() {
    const q = document.getElementById('set-stock-search')?.value.trim().toLowerCase() || '';
    if (!this._stockItemsData) return;

    const filtered = this._stockItemsData.filter(p => {
      const nameMatch = (p.name || '').toLowerCase().includes(q);
      const codeMatch = (p.code || '').toLowerCase().includes(q);
      const catMatch  = (p.category_name || '').toLowerCase().includes(q);
      return nameMatch || codeMatch || catMatch;
    });

    this.renderStockItemsRows(filtered);
  },

  toggleShortcutsTable() {
    const body = document.getElementById('set-shortcuts-table-body');
    const chevron = document.getElementById('set-shortcuts-chevron');
    if (!body) return;

    const isVisible = body.style.display !== 'none';
    body.style.display = isVisible ? 'none' : 'block';
    if (chevron) chevron.textContent = isVisible ? '▼' : '▲';
  },

  // ── Existing Activity Log & Backup Actions Preserved ──
  async loadActivityLog(page = 1) {
    const role   = document.getElementById('al-role-filter')?.value   || '';
    const action = document.getElementById('al-action-filter')?.value || '';
    const el = document.getElementById('activity-log-table');
    const pg = document.getElementById('activity-log-pagination');
    if (!el) return;
    el.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted)">⏳ Loading...</div>`;
    try {
      const params = new URLSearchParams({page, per_page: 30});
      if (role)   params.set('role', role);
      if (action) params.set('action', action);
      const data = await App.api('/activity-log?' + params.toString());
      const logs = data.logs || [];
      if (!logs.length) {
        el.innerHTML = `<div class="empty-state" style="padding:20px"><p class="text-muted">No activity records found.</p></div>`;
        pg.innerHTML = '';
        return;
      }
      const ACTION_ICONS = {CREATE_BILL:'🧾',CANCEL_BILL:'❌',ADD_PRODUCT:'📦',EDIT_PRODUCT:'✏️',DELETE_PRODUCT:'🗑️',ADD_STOCK:'📥',APPROVE_STOCK:'✅',CREATE_USER:'👤',EDIT_USER:'✏️',DELETE_USER:'🗑️',RESET_PASSWORD:'🔑',ADD_EXPENSE:'💸',DELETE_EXPENSE:'🗑️',TOGGLE_GST:'🔄',UPDATE_SETTINGS:'⚙️',MD_REGISTER:'👑'};
      el.innerHTML = `<table class="data-table" style="font-size:12px">
        <thead><tr>
          <th style="width:140px">Date &amp; Time</th>
          <th>User</th>
          <th>Role</th>
          <th>Action</th>
          <th>Description</th>
        </tr></thead>
        <tbody>
          ${logs.map(l => `<tr>
            <td style="white-space:nowrap;color:var(--text-muted)">${(l.created_at||'').replace('T',' ').slice(0,19)}</td>
            <td><strong>@${l.username}</strong><br><span class="text-muted" style="font-size:11px">${l.full_name}</span></td>
            <td><span class="badge badge-secondary" style="font-size:10px">${Auth.ROLE_LABELS[l.role]||l.role}</span></td>
            <td><span style="white-space:nowrap">${ACTION_ICONS[l.action]||'📌'} ${l.action.replace(/_/g,' ')}</span></td>
            <td style="max-width:260px;word-break:break-word">${l.description||'-'}</td>
          </tr>`).join('')}
        </tbody>
      </table>`;
      if (data.pages > 1) {
        pg.innerHTML = Array.from({length: data.pages}, (_,i) => i+1).map(p =>
          `<button class="btn btn-${p===page?'primary':'secondary'} btn-sm" onclick="Settings.loadActivityLog(${p})">${p}</button>`
        ).join('');
      } else { pg.innerHTML = ''; }
    } catch(e) {
      el.innerHTML = `<div style="padding:16px;color:var(--crimson)">${e.message}</div>`;
    }
  },

  _loadedLogoImg: null,

  handleLogoUpload(input) {
    const file = input.files && input.files[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      App.toast('Logo image file must be under 5MB', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        this._loadedLogoImg = img;
        this.openLogoResizerModal(e.target.result, img.width, img.height);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  },

  reopenLogoResizer() {
    const currentLogo = document.getElementById('s-shoplogo')?.value || App.settings?.shop_logo || '';
    if (!currentLogo) {
      App.toast('Please select an image file first', 'warning');
      document.getElementById('s-logo-file')?.click();
      return;
    }

    const img = new Image();
    img.onload = () => {
      this._loadedLogoImg = img;
      this.openLogoResizerModal(currentLogo, img.width, img.height);
    };
    img.src = currentLogo;
  },

  openLogoResizerModal(src, origW, origH) {
    let defaultW = 48, defaultH = 48;
    if (origW && origH) {
      if (origW >= origH) {
        defaultW = 48;
        defaultH = Math.max(8, Math.round((origH * 48) / origW));
      } else {
        defaultH = 48;
        defaultW = Math.max(8, Math.round((origW * 48) / origH));
      }
    }

    const html = `
      <div class="modal" style="max-width:640px">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">📐</span> Logo Image Resizer &amp; Scaler Tool</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="modal-body">
          <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-md);padding:12px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;font-size:12px">
            <div>
              <span class="text-muted">Original File Dimensions:</span>
              <strong class="text-gold" style="font-family:monospace;font-size:13px;margin-left:6px">${origW} × ${origH} px</strong>
            </div>
            <span class="badge badge-info">Interactive Canvas Scaling</span>
          </div>

          <div class="form-group mb-16">
            <label class="form-label" style="font-size:12px">Quick Dimension Presets:</label>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-secondary btn-sm" onclick="Settings.applyPreset(12, 12, ${origW}, ${origH})">12×12 (Micro Icon)</button>
              <button class="btn btn-secondary btn-sm" onclick="Settings.applyPreset(24, 24, ${origW}, ${origH})">24×24 (Small Icon)</button>
              <button class="btn btn-secondary btn-sm" onclick="Settings.applyPreset(48, 48, ${origW}, ${origH})">48×48 (Standard)</button>
              <button class="btn btn-secondary btn-sm" onclick="Settings.applyPreset(64, 64, ${origW}, ${origH})">64×64 (Large)</button>
              <button class="btn btn-secondary btn-sm" onclick="Settings.applyPreset(${origW}, ${origH}, ${origW}, ${origH})">Full Original</button>
            </div>
          </div>

          <div class="grid-2 mb-16" style="gap:14px">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <label class="form-label" style="margin:0">Width (px):</label>
                <input type="number" id="res-w-num" min="8" max="512" value="${defaultW}" class="form-control form-control-sm" style="width:75px;font-family:monospace;text-align:center" oninput="Settings.onWidthNumChange(this.value, ${origW}, ${origH})">
              </div>
              <input type="range" id="res-w-range" min="8" max="256" value="${defaultW}" style="width:100%;accent-color:var(--gold)" oninput="Settings.onWidthRangeChange(this.value, ${origW}, ${origH})">
            </div>
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                <label class="form-label" style="margin:0">Height (px):</label>
                <input type="number" id="res-h-num" min="8" max="512" value="${defaultH}" class="form-control form-control-sm" style="width:75px;font-family:monospace;text-align:center" oninput="Settings.onHeightNumChange(this.value, ${origW}, ${origH})">
              </div>
              <input type="range" id="res-h-range" min="8" max="256" value="${defaultH}" style="width:100%;accent-color:var(--gold)" oninput="Settings.onHeightRangeChange(this.value, ${origW}, ${origH})">
            </div>
          </div>

          <div style="margin-bottom:16px">
            <label style="display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:12.5px">
              <input type="checkbox" id="res-aspect-lock" checked style="accent-color:var(--gold)">
              <span>🔒 Lock Aspect Ratio</span>
            </label>
          </div>

          <div style="background:var(--bg-input);border:1px solid var(--border);border-radius:var(--r-md);padding:14px">
            <div class="form-label" style="font-size:12px;margin-bottom:10px">Live Canvas Output Preview:</div>
            
            <div style="display:flex;gap:14px;align-items:center;justify-content:space-around;flex-wrap:wrap">
              <div style="text-align:center">
                <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">Resized Output</div>
                <div style="width:64px;height:64px;background:#0F172A;border:1px dashed var(--gold);border-radius:8px;display:flex;align-items:center;justify-content:center;margin:0 auto">
                  <canvas id="resizer-canvas" style="max-width:100%;max-height:100%;object-fit:contain"></canvas>
                </div>
                <div id="resizer-size-text" style="font-size:10px;font-family:monospace;color:var(--gold);margin-top:4px">${defaultW}×${defaultH} px</div>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Settings.saveResizedLogo()">💾 Apply Resized Logo</button>
        </div>
      </div>
    `;

    App.showModal(html);
    setTimeout(() => this.updateResizerCanvas(defaultW, defaultH), 100);
  },

  updateResizerCanvas(targetW, targetH) {
    const canvas = document.getElementById('resizer-canvas');
    if (!canvas || !this._loadedLogoImg) return;

    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, targetW, targetH);
    ctx.drawImage(this._loadedLogoImg, 0, 0, targetW, targetH);

    const dataUrl = canvas.toDataURL('image/png');
    this._tempResizedDataUrl = dataUrl;

    const txt = document.getElementById('resizer-size-text');
    if (txt) txt.textContent = `${targetW}×${targetH} px`;
  },

  applyPreset(w, h, origW, origH) {
    const wNum = document.getElementById('res-w-num');
    const wRange = document.getElementById('res-w-range');
    const hNum = document.getElementById('res-h-num');
    const hRange = document.getElementById('res-h-range');
    if (wNum) wNum.value = w;
    if (wRange) wRange.value = Math.min(w, 256);
    if (hNum) hNum.value = h;
    if (hRange) hRange.value = Math.min(h, 256);
    this.updateResizerCanvas(w, h);
  },

  onWidthNumChange(val, origW, origH) {
    let w = parseInt(val) || 8;
    w = Math.max(8, Math.min(512, w));
    const isLocked = document.getElementById('res-aspect-lock')?.checked;
    let h = parseInt(document.getElementById('res-h-num')?.value) || 8;

    if (isLocked && origW && origH) {
      h = Math.max(8, Math.round((origH * w) / origW));
      const hNum = document.getElementById('res-h-num');
      const hRange = document.getElementById('res-h-range');
      if (hNum) hNum.value = h;
      if (hRange) hRange.value = Math.min(h, 256);
    }
    const wRange = document.getElementById('res-w-range');
    if (wRange) wRange.value = Math.min(w, 256);
    this.updateResizerCanvas(w, h);
  },

  onWidthRangeChange(val, origW, origH) {
    const wNum = document.getElementById('res-w-num');
    if (wNum) wNum.value = val;
    this.onWidthNumChange(val, origW, origH);
  },

  onHeightNumChange(val, origW, origH) {
    let h = parseInt(val) || 8;
    h = Math.max(8, Math.min(512, h));
    const isLocked = document.getElementById('res-aspect-lock')?.checked;
    let w = parseInt(document.getElementById('res-w-num')?.value) || 8;

    if (isLocked && origW && origH) {
      w = Math.max(8, Math.round((origW * h) / origH));
      const wNum = document.getElementById('res-w-num');
      const wRange = document.getElementById('res-w-range');
      if (wNum) wNum.value = w;
      if (wRange) wRange.value = Math.min(w, 256);
    }
    const hRange = document.getElementById('res-h-range');
    if (hRange) hRange.value = Math.min(h, 256);
    this.updateResizerCanvas(w, h);
  },

  onHeightRangeChange(val, origW, origH) {
    const hNum = document.getElementById('res-h-num');
    if (hNum) hNum.value = val;
    this.onHeightNumChange(val, origW, origH);
  },

  saveResizedLogo() {
    if (!this._tempResizedDataUrl) {
      App.toast('Resizing failed, please try again', 'error');
      return;
    }
    const logoInput = document.getElementById('s-shoplogo');
    if (logoInput) logoInput.value = this._tempResizedDataUrl;

    const previewBox = document.getElementById('s-logo-preview-box');
    if (previewBox) {
      previewBox.innerHTML = `<img src="${this._tempResizedDataUrl}" alt="Logo" style="width:100%;height:100%;object-fit:contain;">`;
    }

    App.closeModal();
    App.toast('Logo image resized successfully! Click "Save Outlet Profile" to persist.', 'success');
  },

  removeLogo() {
    const logoInput = document.getElementById('s-shoplogo');
    if (logoInput) logoInput.value = '';
    const previewBox = document.getElementById('s-logo-preview-box');
    if (previewBox) previewBox.innerHTML = '<span style="font-size:28px">🥩</span>';
    App.toast('Logo removed. Click "Save Outlet Profile" to save changes.', 'info');
  },

  async saveShop() {
    const fontSel = document.getElementById('s-brand-font')?.value || '';
    const customFont = document.getElementById('s-custom-brand-font')?.value || '';
    let brandFontToSave = fontSel;
    if (fontSel === 'custom') {
      brandFontToSave = customFont.trim();
    }

    const payload = {
      shop_name: document.getElementById('s-shopname')?.value.trim() || '',
      shop_tagline: document.getElementById('s-tagline')?.value.trim() || '',
      shop_address: document.getElementById('s-address')?.value.trim() || '',
      shop_phone: document.getElementById('s-phone')?.value.trim() || '',
      shop_email: document.getElementById('s-email')?.value.trim() || '',
      shop_gstin: document.getElementById('s-gstin')?.value.trim() || '',
      shop_fssai: document.getElementById('s-fssai')?.value.trim() || '',
      shop_brand_font: brandFontToSave,
      shop_logo: document.getElementById('s-shoplogo')?.value || '',
    };

    try {
      await App.api('/settings', 'POST', payload);
      App.toast('Outlet profile details saved successfully!', 'success');
      await App.refreshSettings();
    } catch(e) {
      App.toast('Error saving shop details: ' + e.message, 'error');
    }
  },

  async savePreferences() {
    const pts100 = parseFloat(document.getElementById('s-loyalty-rate-100')?.value || '1.0');
    const ptsPerRupee = (pts100 / 100).toFixed(4);

    const payload = {
      bill_prefix: document.getElementById('s-prefix')?.value.trim() || 'MPI',
      currency_symbol: document.getElementById('s-currency')?.value.trim() || '₹',
      default_print_format: document.getElementById('s-print-format')?.value || 'thermal',
      thermal_paper_width: document.getElementById('s-thermal-width')?.value || '80',
      gst_enabled: document.getElementById('s-gst')?.checked ? 'true' : 'false',
      print_after_bill: document.getElementById('s-print')?.checked ? 'true' : 'false',
      show_print_preview: document.getElementById('s-show-print-preview')?.checked ? 'true' : 'false',
      low_stock_alert: document.getElementById('s-lowstock')?.checked ? 'true' : 'false',
      loyalty_enabled: document.getElementById('s-loyalty-enabled')?.checked ? 'true' : 'false',
      loyalty_points_per_rupee: ptsPerRupee,
      loyalty_redemption_value: parseFloat(document.getElementById('s-loyalty-val')?.value || '0.50').toFixed(2),
    };

    try {
      await App.api('/settings', 'POST', payload);
      App.toast('Billing & POS preferences saved successfully!', 'success');
      await App.refreshSettings();
    } catch(e) {
      App.toast('Error saving preferences: ' + e.message, 'error');
    }
  },

  // ── Cloud & Drive Mirroring Actions ──
  async cloudBackupNow() {
    try {
      App.toast('Creating cloud backup...', 'info');
      await App.api('/cloud/backup-now', 'POST');
      App.toast('Cloud backup created successfully!', 'success');
    } catch(e) {
      App.toast('Cloud backup error: ' + e.message, 'error');
    }
  },

  async loadExternalBackupStatus() {
    const badge = document.getElementById('ext-backup-status-badge');
    const driveSel = document.getElementById('ext-backup-drive-select');
    const pathInput = document.getElementById('ext-backup-path');
    const enabledChk = document.getElementById('ext-backup-enabled');
    const retentionInput = document.getElementById('ext-backup-retention');
    const lastInfo = document.getElementById('ext-backup-last-info');

    if (!badge || !driveSel) return;

    try {
      const config = await App.api('/external-backup/status');
      
      if (enabledChk) enabledChk.checked = !!config.enabled;
      if (pathInput) pathInput.value = config.backup_path || '';
      if (retentionInput) retentionInput.value = config.retention_days || 30;

      driveSel.innerHTML = '<option value="">— Select Connected Drive —</option>';
      (config.drives || []).forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.mountpoint;
        opt.textContent = `${d.device} (${d.mountpoint}) ${d.is_removable ? '🔌 USB' : '📁 Fixed'} - ${d.free_gb} GB free`;
        driveSel.appendChild(opt);
      });

      if (config.configured_drive) {
        driveSel.value = config.configured_drive;
      }

      if (config.enabled) {
        if (config.drive_connected) {
          badge.className = 'badge badge-success';
          badge.textContent = '🟢 Drive Connected & Active';
        } else {
          badge.className = 'badge badge-danger';
          badge.textContent = '🔴 Drive Disconnected';
        }
      } else {
        badge.className = 'badge badge-secondary';
        badge.textContent = '⚪ Real-Time Drive Backup Disabled';
      }

      if (lastInfo) {
        if (config.last_backup_time) {
          lastInfo.textContent = `Last Mirror: ${config.last_backup_time.slice(0,19)} (${config.last_backup_status || 'Success'})`;
        } else {
          lastInfo.textContent = 'Last Mirror: No backups recorded yet.';
        }
      }

    } catch(e) {
      console.error('Error loading external backup status:', e);
      if (badge) {
        badge.className = 'badge badge-secondary';
        badge.textContent = '⚪ Status Unavailable';
      }
    }
  },

  onDriveSelectChange(mountpoint) {
    if (!mountpoint) return;
    const pathInput = document.getElementById('ext-backup-path');
    if (pathInput) {
      pathInput.value = mountpoint.replace(/[\/\\]+$/, '') + '\\MPI_Backups';
    }
  },

  browseNativeFolder() {
    const input = document.createElement('input');
    input.type = 'file';
    input.webkitdirectory = true;
    input.onchange = (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const path = files[0].path || files[0].webkitRelativePath;
        const dirPath = path.substring(0, path.lastIndexOf('\\') || path.lastIndexOf('/'));
        if (dirPath) {
          const pathInput = document.getElementById('ext-backup-path');
          if (pathInput) pathInput.value = dirPath;
        }
      }
    };
    input.click();
  },

  async saveExternalBackupConfig() {
    const enabled = document.getElementById('ext-backup-enabled')?.checked || false;
    const drive = document.getElementById('ext-backup-drive-select')?.value || '';
    const path = document.getElementById('ext-backup-path')?.value.trim() || '';
    const retention = parseInt(document.getElementById('ext-backup-retention')?.value || '30');

    if (enabled && !path) {
      App.toast('Please select or specify a target external backup path.', 'warning');
      return;
    }

    try {
      await App.api('/external-backup/config', 'POST', {
        enabled,
        backup_path: path,
        retention_days: retention,
        drive_mountpoint: drive
      });
      App.toast('External backup configuration saved successfully!', 'success');
      this.loadExternalBackupStatus();
    } catch(e) {
      App.toast('Error saving backup config: ' + e.message, 'error');
    }
  },

  async testExternalBackup() {
    try {
      App.toast('Testing external drive backup...', 'info');
      const res = await App.api('/external-backup/test', 'POST');
      App.toast(res.message || 'Drive backup test successful!', 'success');
      this.loadExternalBackupStatus();
    } catch(e) {
      App.toast('External backup test failed: ' + e.message, 'error');
    }
  },

  openPrintablePreview(type, title) {
    window.open(`/printables/${type}`, '_blank');
  }
};

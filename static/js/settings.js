/**
 * settings.js — Application Settings Module
 * Meat Products of India — Billing & Inventory Management App
 */

const Settings = {

  async render() {
    const content = document.getElementById('page-content');
    try {
      const settings = await App.api('/settings');

      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>⚙️ Settings</h1>
              <p>Configure shop details, GST, and preferences</p>
            </div>
          </div>

          <div class="grid-2" style="gap:20px;align-items:start">
            <!-- Shop Details -->
            <div class="card">
              <div class="card-title"><span class="card-title-icon">🏪</span> Shop Details</div>
              <div class="form-group">
                <label class="form-label required">Shop / Business Name</label>
                <input class="form-control" id="s-shopname" value="${settings.shop_name || ''}">
              </div>
              <div class="form-group">
                <label class="form-label">Tagline</label>
                <input class="form-control" id="s-tagline" value="${settings.shop_tagline || ''}">
              </div>
              <div class="form-group">
                <label class="form-label">Address</label>
                <textarea class="form-control" id="s-address" rows="3">${settings.shop_address || ''}</textarea>
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
                  <input class="form-control" id="s-gstin" value="${settings.shop_gstin || ''}" placeholder="29ABCDE1234F1Z5">
                </div>
                <div class="form-group">
                  <label class="form-label">FSSAI License</label>
                  <input class="form-control" id="s-fssai" value="${settings.shop_fssai || ''}">
                </div>
              </div>
              <div class="form-group mb-16">
                <label class="form-label">Outlet Logo (PNG / Image)</label>
                <div style="display:flex;align-items:center;gap:14px;background:var(--bg-input);padding:12px;border-radius:var(--r-md);border:1px solid var(--border)">
                  <div id="s-logo-preview-box" style="width:48px;height:48px;border-radius:6px;background:var(--bg-card);border:1px dashed var(--border);display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0">
                    ${settings.shop_logo ? `<img src="${settings.shop_logo}" alt="Logo" style="width:100%;height:100%;object-fit:contain;">` : '<span style="font-size:24px">🥩</span>'}
                  </div>
                  <div style="flex:1">
                    <input type="file" id="s-logo-file" accept="image/png,image/jpeg,image/webp" style="display:none" onchange="Settings.handleLogoUpload(this)">
                    <div style="display:flex;gap:8px;margin-bottom:4px">
                      <button class="btn btn-secondary btn-sm" onclick="document.getElementById('s-logo-file').click()">🖼️ Select PNG Logo</button>
                      ${settings.shop_logo ? '<button class="btn btn-danger btn-sm" onclick="Settings.removeLogo()">✕ Remove</button>' : ''}
                    </div>
                    <div class="text-muted" style="font-size:11px">Recommended: PNG image (12×12px up to 256×256px). Displays on Login, Titlebar, Sidebar &amp; Receipts.</div>
                  </div>
                </div>
                <input type="hidden" id="s-shoplogo" value="${settings.shop_logo || ''}">
              </div>

              <button class="btn btn-primary w-full" onclick="Settings.saveShop()">💾 Save Shop Details</button>
            </div>

            <!-- Billing Preferences -->
            <div>
              <div class="card mb-16">
                <div class="card-title"><span class="card-title-icon">🧾</span> Billing Preferences</div>
                <div class="form-row">
                  <div class="form-group">
                    <label class="form-label">Invoice Prefix</label>
                    <input class="form-control" id="s-prefix" value="${settings.bill_prefix || 'MPI'}" placeholder="MPI">
                    <div class="form-hint">Bills will be numbered MPI-00001, MPI-00002…</div>
                  </div>
                  <div class="form-group">
                    <label class="form-label">Currency Symbol</label>
                    <input class="form-control" id="s-currency" value="${settings.currency_symbol || '₹'}">
                  </div>
                </div>
                <div style="display:flex;flex-direction:column;gap:12px;margin-top:8px">
                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-gst" ${settings.gst_enabled === 'true' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--crimson)">
                    <div>
                      <div class="font-semibold">Enable GST on Bills</div>
                      <div class="text-muted text-sm">Show CGST + SGST breakdown in invoices</div>
                    </div>
                  </label>
                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-print" ${settings.print_after_bill === 'true' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--crimson)">
                    <div>
                      <div class="font-semibold">Auto-Print After Bill</div>
                      <div class="text-muted text-sm">Open print dialog after saving a bill</div>
                    </div>
                  </label>
                  <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="s-lowstock" ${settings.low_stock_alert === 'true' ? 'checked' : ''}
                      style="width:18px;height:18px;accent-color:var(--crimson)">
                    <div>
                      <div class="font-semibold">Low Stock Alerts</div>
                      <div class="text-muted text-sm">Show badge on inventory when stock is low</div>
                    </div>
                  </label>
                </div>
                <button class="btn btn-primary w-full mt-16" onclick="Settings.savePreferences()">💾 Save Preferences</button>
              </div>

              <!-- Backup & Restore -->
              <div class="card mb-16">
                <div class="card-title"><span class="card-title-icon">💾</span> Backup & Restore</div>
                <p class="text-muted text-sm mb-16">Automatic 6-hour cloud DB backups are enabled. You can also download local backups or sync to cloud on demand.</p>
                <div style="display:flex;flex-direction:column;gap:12px">
                  <a href="/api/backup" class="btn btn-secondary w-full" download>
                    ⬇️ Download Local Database Backup
                  </a>
                  <button class="btn btn-primary w-full" onclick="Settings.cloudBackupNow()">
                    ☁️ Backup to Cloud Server Now (6-Hr Auto Active)
                  </button>
                  <div style="padding:12px;background:var(--warning-bg);border:1px solid rgba(243,156,18,.3);border-radius:var(--r-md);font-size:12px;color:var(--warning)">
                    ℹ️ <strong>Auto-Backup:</strong> App automatically uploads compressed snapshots every 6 hours when connected online.
                  </div>
                </div>
              </div>

              <!-- Software License & Subscription -->
              <div class="card">
                <div class="card-title"><span class="card-title-icon">🔑</span> Software License &amp; Subscription</div>
                ${(() => {
                  const lic = App.licenseInfo || { status: 'trial', days_left: 10, expires_at: '—', machine_id: '—', price_inr: 5000 };
                  const badgeCls = lic.status === 'active' ? 'success' : lic.status === 'grace' ? 'warning' : lic.status === 'trial' ? 'info' : 'danger';
                  return `
                    <div style="display:flex;flex-direction:column;gap:12px">
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Subscription Status:</span>
                        <span class="badge badge-${badgeCls}">${lic.status.toUpperCase()} (${lic.days_left} days left)</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Yearly Rate:</span>
                        <span class="font-bold text-gold">₹${lic.price_inr || 5000} / Year / Outlet</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Valid Until:</span>
                        <span class="font-semibold">${lic.expires_at || '—'}</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Machine Hardware ID:</span>
                        <span class="font-bold" style="font-family:monospace;font-size:13px">${lic.machine_id}</span>
                      </div>
                      ${lic.active_key ? `
                      <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="text-muted text-sm">Redeemed Key:</span>
                        <span class="font-bold text-success" style="font-family:monospace;font-size:13px">${lic.active_key}</span>
                      </div>` : ''}
                      <button class="btn btn-primary w-full mt-8" onclick="App.showActivationModal()">
                        ⚡ Enter 12-Digit Activation Key / Renew
                      </button>
                    </div>`;
                })()}
              </div>
            </div>
            </div>
          </div>

          <!-- About -->
          <div class="card mt-16" style="margin-top:20px">
            <div class="card-title"><span class="card-title-icon">ℹ️</span> About This App</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px">
              <div>
                <div class="text-muted text-sm">Application</div>
                <div class="font-semibold">Meat Products of India</div>
                <div class="text-muted text-sm">Billing &amp; Inventory Manager</div>
              </div>
              <div>
                <div class="text-muted text-sm">Version</div>
                <div class="font-semibold">1.0.0</div>
                <div class="text-muted text-sm">SQLite + Flask + Vanilla JS</div>
              </div>
              <div>
                <div class="text-muted text-sm">Database</div>
                <div class="font-semibold">SQLite (Local)</div>
                <div class="text-muted text-sm">Offline — No internet required</div>
              </div>
              <div>
                <div class="text-muted text-sm">Compliance</div>
                <div class="font-semibold">GST Ready</div>
                <div class="text-muted text-sm">CGST + SGST, HSN codes</div>
              </div>
            </div>
          </div>

        ${['admin','md','manager'].includes(Auth.user?.role) ? `
        <!-- Activity Audit Log — MD/CEO & Developer only -->
        <div class="card" style="margin-top:20px">
          <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
            <div><span class="card-title-icon">📋</span> Activity Audit Log</div>
            <div style="display:flex;gap:8px;align-items:center">
              <select id="al-role-filter" class="form-control" style="width:auto;padding:4px 8px;font-size:12px">
                <option value="">All Roles</option>
                <option value="admin">Developer</option>
                <option value="md">Managing Director</option>
                <option value="manager">Manager</option>
                <option value="accountant">Accountant</option>
                <option value="counter_staff">Counter Staff</option>
              </select>
              <select id="al-action-filter" class="form-control" style="width:auto;padding:4px 8px;font-size:12px">
                <option value="">All Actions</option>
                <option value="CREATE_BILL">Bills Created</option>
                <option value="CANCEL_BILL">Bills Cancelled</option>
                <option value="ADD_PRODUCT">Products Added</option>
                <option value="ADD_STOCK">Stock Added</option>
                <option value="CREATE_USER">Users Created</option>
                <option value="DELETE_USER">Users Deleted</option>
                <option value="ADD_EXPENSE">Expenses Added</option>
                <option value="TOGGLE_GST">GST Toggled</option>
                <option value="UPDATE_SETTINGS">Settings Updated</option>
                <option value="MD_REGISTER">MD Registered</option>
              </select>
              <button class="btn btn-secondary btn-sm" onclick="Settings.loadActivityLog(1)">🔍 Filter</button>
            </div>
          </div>
          <div id="activity-log-table" style="overflow-x:auto">
            <div class="empty-state" style="padding:20px">
              <div class="empty-state-icon">📋</div>
              <p class="text-muted">Click Filter to load activity log</p>
            </div>
          </div>
          <div id="activity-log-pagination" style="display:flex;justify-content:center;gap:8px;padding:12px 0"></div>
        </div>` : ''}
      </div>`;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
    // Load activity log on page open for md/admin
    if (['admin','md'].includes(Auth.user?.role)) Settings.loadActivityLog(1);
  },

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
      // Pagination
      if (data.pages > 1) {
        pg.innerHTML = Array.from({length: data.pages}, (_,i) => i+1).map(p =>
          `<button class="btn btn-${p===page?'primary':'secondary'} btn-sm" onclick="Settings.loadActivityLog(${p})">${p}</button>`
        ).join('');
      } else { pg.innerHTML = ''; }
    } catch(e) {
      el.innerHTML = `<div style="padding:16px;color:var(--crimson)">${e.message}</div>`;
    }
  },

  handleLogoUpload(input) {
    const file = input.files && input.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      App.toast('Logo image file must be under 2MB', 'error');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const maxDim = 256;
        let w = img.width, h = img.height;
        if (w > maxDim || h > maxDim) {
          if (w > h) { h = Math.round((h * maxDim) / w); w = maxDim; }
          else { w = Math.round((w * maxDim) / h); h = maxDim; }
        }
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);

        const dataUrl = canvas.toDataURL('image/png');
        const logoInput = document.getElementById('s-shoplogo');
        if (logoInput) logoInput.value = dataUrl;

        const previewBox = document.getElementById('s-logo-preview-box');
        if (previewBox) {
          previewBox.innerHTML = `<img src="${dataUrl}" alt="Logo" style="width:100%;height:100%;object-fit:contain;">`;
        }
        App.toast('Logo selected! Click "Save Shop Details" to apply.', 'info');
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  },

  removeLogo() {
    const logoInput = document.getElementById('s-shoplogo');
    if (logoInput) logoInput.value = '';
    const previewBox = document.getElementById('s-logo-preview-box');
    if (previewBox) {
      previewBox.innerHTML = '<span style="font-size:24px">🥩</span>';
    }
    App.toast('Logo removed! Click "Save Shop Details" to save changes.', 'info');
  },

  async saveShop() {
    const payload = {
      shop_name:    document.getElementById('s-shopname').value,
      shop_tagline: document.getElementById('s-tagline').value,
      shop_address: document.getElementById('s-address').value,
      shop_phone:   document.getElementById('s-phone').value,
      shop_email:   document.getElementById('s-email').value,
      shop_gstin:   document.getElementById('s-gstin').value,
      shop_fssai:   document.getElementById('s-fssai').value,
      shop_logo:    document.getElementById('s-shoplogo')?.value || '',
    };
    try {
      await App.api('/settings', 'POST', payload);
      App.toast('Shop details & logo saved!', 'success');
      App.applySettings(payload);
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async savePreferences() {
    const payload = {
      bill_prefix:      document.getElementById('s-prefix').value,
      currency_symbol:  document.getElementById('s-currency').value,
      gst_enabled:      document.getElementById('s-gst').checked ? 'true' : 'false',
      print_after_bill: document.getElementById('s-print').checked ? 'true' : 'false',
      low_stock_alert:  document.getElementById('s-lowstock').checked ? 'true' : 'false',
    };
    try {
      await App.api('/settings', 'POST', payload);
      App.toast('Preferences saved!', 'success');
      App.currency = payload.currency_symbol;
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async cloudBackupNow() {
    App.toast('Starting cloud database backup...', 'info');
    try {
      const res = await App.api('/backup/cloud-now', 'POST');
      App.toast(res.message || 'Database snapshot uploaded to cloud!', 'success');
    } catch(e) {
      App.toast(`Cloud Backup Failed: ${e.message}`, 'error');
    }
  },
};

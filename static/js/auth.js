/**
 * auth.js — Authentication, Role-Based Access Control & Audit Notifications
 * Meat Products of India — Billing & Inventory Management App
 *
 * Roles & Permissions:
 *   admin         → Managing Director  (full access + notification alerts when Manager changes passwords)
 *   manager       → Store Manager      (access all modules including User Management; CANNOT modify Managing Director)
 *   accountant    → Accountant         (billing, reports, expenses)
 *   counter_staff → Counter Staff      (billing & customers only)
 */

const Auth = {
  currentUser: null,
  _notifications: [],
  _unreadCount: 0,

  // Pages each role is allowed to access
  ROLE_PAGES: {
    admin:         ['dashboard','billing','bills','inventory','stock-in','purchase-orders',
                    'categories','customers','suppliers','expenses','accounts','reports','settings','users'],
    md:            ['dashboard','billing','bills','inventory','stock-in','purchase-orders',
                    'categories','customers','suppliers','expenses','accounts','reports','settings','users'],
    manager:       ['dashboard','billing','bills','inventory','stock-in','purchase-orders',
                    'categories','customers','suppliers','expenses','accounts','reports','users'],
    accountant:    ['dashboard','billing','bills','customers','expenses','accounts','reports','inventory'],
    counter_staff: ['billing','bills','customers'],
    tester:        ['billing','bills','customers'],
  },

  ROLE_LABELS: {
    admin:         '🛠️ Developer Superuser',
    md:            '👑 Managing Director',
    manager:       '🏪 Store Manager',
    accountant:    '📊 Accountant',
    counter_staff: '🧾 Counter Staff',
    tester:        '🧪 Tester Staff (Demo)',
  },

  ROLE_ICON: {
    admin:         '🛠️',
    md:            '👑',
    manager:       '🏪',
    accountant:    '📊',
    counter_staff: '🧾',
    tester:        '🧪',
  },

  // ── MD/CEO Registration ────────────────────────────────────────────────────
  showMDRegisterModal() {
    const INDIAN_STATES = ['Andaman & Nicobar','Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chandigarh','Chhattisgarh','Dadra & Nagar Haveli','Daman & Diu','Delhi','Goa','Gujarat','Haryana','Himachal Pradesh','Jammu & Kashmir','Jharkhand','Karnataka','Kerala','Ladakh','Lakshadweep','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Puducherry','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal'];
    App.showModal(`
      <div class="modal-header">
        <h3 style="margin:0;display:flex;align-items:center;gap:10px">👑 Register Managing Director (MD / CEO)</h3>
      </div>
      <div class="modal-body" style="max-height:72vh;overflow-y:auto;padding-right:4px">

        <!-- Warning -->
        <div style="background:rgba(239,68,68,0.10);border:1px solid rgba(239,68,68,0.35);border-radius:var(--r-md);padding:14px;margin-bottom:18px">
          <div style="font-weight:700;color:#FCA5A5;font-size:13px;margin-bottom:6px">⚠️ IMPORTANT WARNING</div>
          <div style="font-size:12px;color:#FCA5A5;line-height:1.6">
            Strictly for the <strong>Managing Director / CEO / Business Owner</strong> of this outlet.<br>
            &nbsp;• Full authority to create &amp; manage all staff accounts<br>
            &nbsp;• Access all financial reports, settings &amp; accounts<br>
            &nbsp;• Each outlet requires a separate ₹5,000/year license.<br><br>
            <strong>⚠️ Unauthorised registration is a serious security violation.</strong>
          </div>
        </div>

        <!-- Section: MD Account -->
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--gold);margin:14px 0 10px;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:6px">👑 MD / CEO Account</div>
        <div class="form-group">
          <label class="form-label required">Full Name (MD/CEO)</label>
          <input class="form-control" id="md-fullname" type="text" placeholder="e.g. Rajesh Kumar" autocomplete="name">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label required">Username</label>
            <input class="form-control" id="md-username" type="text" placeholder="e.g. rajesh_md" autocomplete="username">
          </div>
          <div class="form-group">
            <label class="form-label">MD Group / Business Name</label>
            <input class="form-control" id="md-group-name" type="text" placeholder="e.g. Revathy Meats Pvt. Ltd.">
            <div class="form-hint">Identifies your business across all outlets</div>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label required">Password</label>
            <div style="position:relative">
              <input class="form-control" id="md-password" type="password" placeholder="Minimum 6 characters" autocomplete="new-password">
              <button onclick="const i=document.getElementById('md-password');i.type=i.type==='password'?'text':'password'" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:var(--text-muted)">👁️</button>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label required">Confirm Password</label>
            <input class="form-control" id="md-password2" type="password" placeholder="Re-enter password" autocomplete="new-password">
          </div>
        </div>

        <!-- Section: Outlet / Branch -->
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--gold);margin:14px 0 10px;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:6px">🏪 Outlet / Branch Details</div>
        <div style="background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);border-radius:var(--r-sm);padding:10px;font-size:12px;color:#A5B4FC;margin-bottom:12px">
          ℹ️ Each outlet (branch) runs on its own computer and is licensed separately at <strong>₹5,000/year</strong>. Fill in this outlet's details below.
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label required">Branch / Outlet Name</label>
            <input class="form-control" id="md-outlet-name" type="text" placeholder="e.g. Main Branch, KK Nagar Outlet">
          </div>
          <div class="form-group">
            <label class="form-label required">Branch Phone Number</label>
            <input class="form-control" id="md-outlet-phone" type="tel" placeholder="e.g. 9876543210">
          </div>
        </div>
        <div class="form-group">
          <label class="form-label required">Address Line 1</label>
          <input class="form-control" id="md-addr1" type="text" placeholder="Door No., Street Name">
        </div>
        <div class="form-group">
          <label class="form-label">Address Line 2 <span style="color:var(--text-muted);font-weight:400">(optional)</span></label>
          <input class="form-control" id="md-addr2" type="text" placeholder="Area, Landmark (optional)">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
          <div class="form-group">
            <label class="form-label required">City</label>
            <input class="form-control" id="md-city" type="text" placeholder="e.g. Chennai">
          </div>
          <div class="form-group">
            <label class="form-label required">State</label>
            <select class="form-control" id="md-state">
              <option value="">Select state...</option>
              ${INDIAN_STATES.map(s => `<option value="${s}">${s}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label required">Pincode</label>
            <input class="form-control" id="md-pincode" type="text" placeholder="6-digit pincode" maxlength="6">
          </div>
        </div>

        <div id="md-reg-error" style="display:none;padding:10px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:var(--r-sm);font-size:12.5px;color:#FCA5A5;margin-top:8px"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="md-reg-btn" onclick="Auth.submitMDRegister()" style="background:linear-gradient(135deg,#D97706,#B45309)">
          👑 Register as Managing Director
        </button>
      </div>
    `, { wide: true });
  },

  async submitMDRegister() {
    const full_name    = (document.getElementById('md-fullname').value    || '').trim();
    const username     = (document.getElementById('md-username').value     || '').trim();
    const group_name   = (document.getElementById('md-group-name').value   || '').trim();
    const password     = document.getElementById('md-password').value;
    const password2    = document.getElementById('md-password2').value;
    const outlet_name  = (document.getElementById('md-outlet-name').value  || '').trim();
    const outlet_phone = (document.getElementById('md-outlet-phone').value || '').trim();
    const addr1        = (document.getElementById('md-addr1').value        || '').trim();
    const addr2        = (document.getElementById('md-addr2').value        || '').trim();
    const city         = (document.getElementById('md-city').value         || '').trim();
    const state        = document.getElementById('md-state').value;
    const pincode      = (document.getElementById('md-pincode').value      || '').trim();
    const errDiv       = document.getElementById('md-reg-error');

    const showErr = (msg) => { errDiv.textContent = '❌ ' + msg; errDiv.style.display = ''; errDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };
    errDiv.style.display = 'none';

    if (!full_name)    return showErr('Full Name is required.');
    if (!username)     return showErr('Username is required.');
    if (password.length < 6)  return showErr('Password must be at least 6 characters.');
    if (password !== password2)   return showErr('Passwords do not match. Please re-enter.');
    if (!outlet_name)  return showErr('Branch / Outlet Name is required.');
    if (!outlet_phone) return showErr('Branch Phone Number is required.');
    if (!addr1)        return showErr('Address Line 1 is required.');
    if (!city)         return showErr('City is required.');
    if (!state)        return showErr('Please select your state.');
    if (!/^\d{6}$/.test(pincode)) return showErr('Pincode must be exactly 6 digits.');

    const btn = document.getElementById('md-reg-btn');
    btn.disabled = true; btn.textContent = '⏳ Registering...';

    try {
      const res = await fetch('/api/auth/register-md', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name, username, password, group_name,
          outlet_name, outlet_phone, addr1, addr2, city, state, pincode
        })
      });
      const json = await res.json();
      if (json.status === 'ok') {
        App.closeModal();
        // Refresh settings so login screen shows outlet name
        try {
          const s = await App.api('/settings');
          App.applySettings(s);
        } catch(_) {}
        // Refresh system info so title bar shows the new outlet code
        try {
          const si = await App.api('/license/system-info');
          App.injectSystemIdBadge(si);
        } catch(_) {}
        const oc = json.data?.outlet_code || '';
        const ocBadge = oc ? `<br><span style="font-size:18px;letter-spacing:2px;color:#FCD34D">🔐 ${oc}</span>` : '';
        App.toast('success',
          `👑 MD Registered! Outlet "${outlet_name}" configured.${ocBadge}<br><small>Keep your Outlet Code safe — staff need it to log in.</small>`, 8000);
      } else {
        showErr(json.message || 'Registration failed.');
        btn.disabled = false; btn.textContent = '👑 Register as Managing Director';
      }
    } catch (e) {
      showErr('Network error. Please try again.');
      btn.disabled = false; btn.textContent = '👑 Register as Managing Director';
    }
  },

  // ── Login ──────────────────────────────────────────────────────────────────
  async login() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const btn      = document.getElementById('login-btn');
    const errEl    = document.getElementById('login-error');

    if (!username || !password) {
      Auth.showLoginError('Please enter your username and password');
      return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ Signing in…';
    errEl.style.display = 'none';

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });
      const json = await res.json();

      if (json.status !== 'ok') {
        Auth.showLoginError(json.message || 'Invalid credentials');
        return;
      }

      const userData = json.data;

      // ── MD Multi-Outlet Confirmation ───────────────────────────────────────
      // If the MD has multiple outlets registered, ask them to confirm their outlet code
      if (userData.role === 'md' && userData.outlet_code) {
        const machineOC = App.sysInfo?.outlet_code || userData.outlet_code;
        // Ask cloud how many outlets this MD has (non-blocking, best-effort)
        let mdOutlets = [];
        try {
          const mdRes = await fetch(`https://mpi-license-server.onrender.com/api/v1/outlet/md-outlets?md_username=${encodeURIComponent(username)}`);
          const mdJson = await mdRes.json();
          mdOutlets = mdJson.outlets || [];
        } catch(_) {}

        if (mdOutlets.length > 1) {
          // Prompt the MD to confirm which outlet they're at
          const confirmed = await new Promise(resolve => {
            App.showModal(`
              <div class="modal">
                <div class="modal-header">
                  <div class="modal-title"><span class="modal-title-icon">🏪</span> Confirm Your Outlet</div>
                </div>
                <div style="padding:16px">
                  <div style="background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);border-radius:var(--r-sm);padding:12px;font-size:13px;color:#A5B4FC;margin-bottom:14px">
                    Your MD account has <strong>${mdOutlets.length} outlets</strong> registered.
                    This machine is outlet: <strong style="color:#FCD34D;font-size:14px">${machineOC}</strong>.
                    Please confirm by entering your outlet code.
                  </div>
                  <div class="form-group">
                    <label class="form-label required">Enter Outlet Code for this machine</label>
                    <input class="form-control" id="oc-confirm-input" placeholder="e.g. KK01" maxlength="4"
                      style="text-transform:uppercase;font-size:18px;letter-spacing:3px;text-align:center;font-weight:700"
                      oninput="this.value=this.value.toUpperCase()">
                  </div>
                  <div id="oc-confirm-error" style="display:none;color:#FCA5A5;font-size:12px;padding:6px 0"></div>
                </div>
                <div class="modal-footer">
                  <button class="btn btn-secondary" onclick="App.closeModal();window._ocResolve(false)">Cancel</button>
                  <button class="btn btn-primary" onclick="
                    const v=document.getElementById('oc-confirm-input').value.trim().toUpperCase();
                    if(!v){document.getElementById('oc-confirm-error').textContent='Please enter your outlet code';document.getElementById('oc-confirm-error').style.display='block';return;}
                    if(v!=='${machineOC}'){document.getElementById('oc-confirm-error').textContent='❌ Outlet code does not match this machine (${machineOC}). Use the computer assigned to your outlet.';document.getElementById('oc-confirm-error').style.display='block';return;}
                    App.closeModal();window._ocResolve(true);
                  ">✅ Confirm &amp; Sign In</button>
                </div>
              </div>`);
            window._ocResolve = resolve;
          });
          if (!confirmed) return;
        }
      }

      Auth.currentUser = userData;
      Auth.onLoginSuccess(userData);
    } catch(e) {
      Auth.showLoginError('Connection error. Is the server running?');
    } finally {
      btn.disabled = false;
      btn.textContent = '🔑 Sign In';
    }
  },

  showLoginError(msg) {
    const el = document.getElementById('login-error');
    document.getElementById('login-error-msg').textContent = msg;
    el.style.display = 'flex';
    el.classList.remove('login-error');
    void el.offsetWidth;
    el.classList.add('login-error');
  },

  togglePwd() {
    const input  = document.getElementById('login-password');
    const toggle = document.getElementById('pwd-toggle');
    if (input.type === 'password') {
      input.type = 'text';
      toggle.textContent = '🔒';
    } else {
      input.type = 'password';
      toggle.textContent = '👁️';
    }
  },

  // ── After successful login ─────────────────────────────────────────────────
  onLoginSuccess(user) {
    Auth.currentUser = user;
    Auth.applyRoleUI(user);

    // Hide login overlay with animation
    const overlay = document.getElementById('login-overlay');
    overlay.classList.add('hidden');
    setTimeout(() => { overlay.style.display = 'none'; }, 400);

    // Clear password field
    document.getElementById('login-password').value = '';

    // Init the main app
    App.postAuthInit(user);
  },

  // ── Restore session on page load ───────────────────────────────────────────
  async checkSession() {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' });
      const json = await res.json();
      if (json.status === 'ok') {
        Auth.currentUser = json.data;
        Auth.onLoginSuccess(json.data);
        return true;
      }
    } catch(e) { /* not logged in */ }
    return false;
  },

  // ── Apply role-based UI ────────────────────────────────────────────────────
  applyRoleUI(user) {
    const allowedPages = user.pages || Auth.ROLE_PAGES[user.role] || [];

    // Update topbar user widget
    const name     = user.full_name || user.username;
    const initials = name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
    document.getElementById('topbar-avatar').textContent    = initials;
    document.getElementById('topbar-user-name').textContent = name;
    document.getElementById('topbar-user-role').textContent = Auth.ROLE_LABELS[user.role] || user.role;

    // Show/hide Users management link (for admin, md and manager)
    const navUsers = document.getElementById('nav-users');
    if (navUsers) navUsers.style.display = (['admin','md','manager'].includes(user.role)) ? '' : 'none';

    // Show/hide Notification button (for admin and md)
    const notifBtn = document.getElementById('notif-btn');
    if (notifBtn) {
      notifBtn.style.display = (user.role === 'admin' || user.role === 'md') ? '' : 'none';
      if (user.role === 'admin' || user.role === 'md') Auth.fetchNotifications();
    }

    // Grey-out / hide nav items not allowed for this role
    document.querySelectorAll('.nav-item[data-page]').forEach(el => {
      const page = el.dataset.page;
      const allowed = allowedPages.includes(page);
      el.classList.toggle('nav-disabled', !allowed);
    });
  },

  // ── Notifications (Managing Director Alerts) ───────────────────────────────
  async fetchNotifications() {
    if (!Auth.isRole('admin')) return;
    try {
      const data = await App.api('/notifications');
      const badge = document.getElementById('notif-badge');
      if (badge) {
        if (data.unread_count > 0) {
          badge.textContent = data.unread_count;
          badge.style.display = 'flex';
        } else {
          badge.style.display = 'none';
        }
      }
      Auth._notifications = data.notifications || [];
      Auth._unreadCount = data.unread_count || 0;
    } catch(e) { /* ignore */ }
  },

  async showNotificationsModal() {
    await Auth.fetchNotifications();
    const notifs = Auth._notifications || [];
    App.showModal(`
      <div class="modal modal-lg">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">🔔</span> Manager Activity & Password Audit Logs</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <p class="text-muted text-sm mb-16">Audit log notifications for Managing Director when a Store Manager modifies passwords or staff accounts.</p>
        ${notifs.length === 0
          ? '<div class="empty-state"><div class="empty-state-icon">🔔</div><h3>No notifications</h3><p>No password changes logged by managers.</p></div>'
          : `<div style="display:flex;flex-direction:column;gap:10px;max-height:380px;overflow-y:auto">
              ${notifs.map(n => `
                <div style="padding:14px;background:${n.read ? 'var(--bg-input)' : 'var(--info-bg)'};border-radius:var(--r-md);border:1px solid ${n.read ? 'var(--border)' : 'rgba(2,132,199,0.3)'}">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <div style="font-weight:700;font-size:14px;color:var(--text-primary)">${n.title}</div>
                    <div class="text-muted text-xs">${App.fmtDateTime(n.created_at)}</div>
                  </div>
                  <div style="font-size:13px;color:var(--text-secondary)">${n.message}</div>
                </div>`).join('')}
             </div>`}
        <div class="modal-footer">
          ${notifs.length > 0 ? '<button class="btn btn-secondary" onclick="Auth.markNotificationsRead()">✓ Mark All as Read</button>' : ''}
          <button class="btn btn-primary" onclick="App.closeModal()">Close</button>
        </div>
      </div>`);
  },

  async markNotificationsRead() {
    try {
      await App.api('/notifications/read', 'POST');
      const badge = document.getElementById('notif-badge');
      if (badge) badge.style.display = 'none';
      App.toast('Notifications marked as read', 'success');
      App.closeModal();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  // ── Logout ─────────────────────────────────────────────────────────────────
  async logout(e) {
    if (e) e.stopPropagation();
    Auth.closeDropdown();
    App.confirm('Are you sure you want to sign out?', 'Sign Out', async () => {
      try {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
      } catch(e) { /* ignore */ }
      Auth.currentUser = null;
      // Reset UI
      document.getElementById('login-username').value = '';
      document.getElementById('login-password').value = '';
      document.getElementById('login-error').style.display = 'none';
      const overlay = document.getElementById('login-overlay');
      overlay.style.display = 'flex';
      void overlay.offsetWidth;
      overlay.classList.remove('hidden');
      // Re-grey all nav items
      document.querySelectorAll('.nav-item[data-page]').forEach(el => el.classList.add('nav-disabled'));
    });
  },

  // ── User Dropdown ──────────────────────────────────────────────────────────
  toggleDropdown() {
    const dd = document.getElementById('user-dropdown');
    dd.classList.toggle('show');
  },

  closeDropdown() {
    document.getElementById('user-dropdown')?.classList.remove('show');
  },

  // ── Profile Modal ──────────────────────────────────────────────────────────
  showProfileModal(e) {
    e.stopPropagation();
    Auth.closeDropdown();
    const u = Auth.currentUser;
    if (!u) return;
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">👤</span> My Profile</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:16px;padding:20px 0;text-align:center">
          <div class="user-card-avatar" style="width:72px;height:72px;font-size:28px">
            ${(u.full_name||u.username).split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase()}
          </div>
          <div>
            <div style="font-size:20px;font-weight:700">${u.full_name}</div>
            <div style="color:var(--text-muted);margin:4px 0">@${u.username}</div>
            <div class="role-badge role-${u.role}">${Auth.ROLE_LABELS[u.role]}</div>
          </div>
        </div>
        <div style="background:var(--bg-input);border-radius:var(--r-md);padding:16px;border:1px solid var(--border)">
          <div class="bill-row">
            <span class="text-muted">Role</span>
            <span class="font-semibold">${Auth.ROLE_LABELS[u.role]}</span>
          </div>
          <div class="bill-row">
            <span class="text-muted">Username</span>
            <span class="font-semibold">${u.username}</span>
          </div>
          <div class="bill-row">
            <span class="text-muted">Last Login</span>
            <span class="font-semibold">${u.last_login ? App.fmtDateTime(u.last_login) : 'First login'}</span>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Close</button>
          <button class="btn btn-primary" onclick="App.closeModal();Auth.showChangePwdModal({stopPropagation:()=>{}})">🔑 Change Password</button>
        </div>
      </div>`);
  },

  // ── Change Password Modal ──────────────────────────────────────────────────
  showChangePwdModal(e) {
    e.stopPropagation();
    Auth.closeDropdown();
    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title"><span class="modal-title-icon">🔑</span> Change Password</div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        <div class="form-group">
          <label class="form-label required">Current Password</label>
          <input class="form-control" id="cpwd-current" type="password" placeholder="••••••••">
        </div>
        <div class="form-group">
          <label class="form-label required">New Password</label>
          <input class="form-control" id="cpwd-new" type="password" placeholder="Min 6 characters">
        </div>
        <div class="form-group">
          <label class="form-label required">Confirm New Password</label>
          <input class="form-control" id="cpwd-confirm" type="password" placeholder="Repeat new password">
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="Auth.changePassword()">💾 Update Password</button>
        </div>
      </div>`);
  },

  async changePassword() {
    const current  = document.getElementById('cpwd-current').value;
    const newPwd   = document.getElementById('cpwd-new').value;
    const confirm  = document.getElementById('cpwd-confirm').value;
    if (!current)        { App.toast('Enter current password', 'error'); return; }
    if (newPwd.length < 6){ App.toast('New password must be at least 6 characters', 'error'); return; }
    if (newPwd !== confirm){ App.toast('Passwords do not match', 'error'); return; }
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ current_password: current, new_password: newPwd }),
      });
      const json = await res.json();
      if (json.status !== 'ok') { App.toast(json.message, 'error'); return; }
      App.closeModal();
      App.toast('Password changed successfully!', 'success');
    } catch(e) { App.toast('Error: ' + e.message, 'error'); }
  },

  // ── Permission Check ───────────────────────────────────────────────────────
  can(page) {
    if (!Auth.currentUser) return false;
    if (Auth.currentUser.role === 'admin') return true;
    const allowed = Auth.currentUser.pages || Auth.ROLE_PAGES[Auth.currentUser.role] || [];
    return allowed.includes(page);
  },

  isRole(...roles) {
    return roles.includes(Auth.currentUser?.role);
  },
};

// ── Users Management Page (Admin & Manager) ──────────────────────────────────
const UsersAdmin = {

  async render() {
    if (!Auth.isRole('admin', 'manager')) {
      document.getElementById('page-content').innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔒</div>
          <h3>Access Denied</h3>
          <p>Only the Managing Director and Manager can access user management.</p>
        </div>`;
      return;
    }

    const isManager = Auth.isRole('manager');
    const content = document.getElementById('page-content');
    try {
      const users = await App.api('/auth/users');
      content.innerHTML = `
        <div class="page-enter">
          <div class="page-header">
            <div class="page-header-left">
              <h1>👥 User Management</h1>
              <p>${users.length} user account${users.length !== 1 ? 's' : ''} ${isManager ? '• 🛡️ Managing Director accounts protected' : ''}</p>
            </div>
            <button class="btn btn-primary" onclick="UsersAdmin.showModal()">➕ Add User</button>
          </div>

          <div style="display:flex;flex-direction:column;gap:12px" id="users-list">
            ${users.map(u => {
              const isTargetAdmin = u.role === 'admin';
              const canEdit = !isManager || !isTargetAdmin;
              return `
              <div class="user-card" style="${isTargetAdmin && isManager ? 'opacity:0.8;background:var(--bg-input)' : ''}">
                <div class="user-card-avatar">
                  ${u.full_name.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase()}
                </div>
                <div class="user-card-info">
                  <div class="user-card-name">${u.full_name}</div>
                  <div class="user-card-username">@${u.username}</div>
                  <div style="margin-top:4px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                    <span class="role-badge role-${u.role}">${Auth.ROLE_LABELS[u.role]}</span>
                    ${u.active ? '<span class="badge badge-success">Active</span>' : '<span class="badge badge-danger">Inactive</span>'}
                    ${u.last_login
                      ? `<span class="text-muted text-xs">Last: ${App.fmtDateTime(u.last_login)}</span>`
                      : `<span class="text-muted text-xs">Never logged in</span>`}
                  </div>
                </div>
                <div style="display:flex;gap:8px;flex-shrink:0;align-items:center">
                  ${canEdit ? `
                    <button class="btn btn-secondary btn-sm" onclick="UsersAdmin.showModal(${JSON.stringify(JSON.stringify(u))})" title="Edit user or reset password">✏️ Edit / Reset Pwd</button>
                    ${u.id !== Auth.currentUser.id
                      ? `<button class="btn btn-danger btn-sm btn-icon" onclick="UsersAdmin.deleteUser(${u.id},'${u.username}')" title="Delete">🗑️</button>`
                      : '<span class="text-muted text-sm" style="padding:4px 8px">(You)</span>'}
                  ` : `
                    <span class="badge badge-warning" style="font-size:11px">🛡️ Managing Director (Protected)</span>
                  `}
                </div>
              </div>`;
            }).join('')}
          </div>

          <div class="gold-divider"></div>

          <!-- Role Permissions Table -->
          <div class="card">
            <div class="card-title"><span class="card-title-icon">🔒</span> Role Permissions Overview</div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th style="text-align:center">👑 Admin</th>
                    <th style="text-align:center">🏪 Manager</th>
                    <th style="text-align:center">📊 Accountant</th>
                    <th style="text-align:center">🧾 Counter</th>
                  </tr>
                </thead>
                <tbody>
                  ${[
                    ['Dashboard & Reports',            true,  true,  true,  false],
                    ['New Bill / POS',                 true,  true,  true,  true],
                    ['Bill History',                   true,  true,  true,  true],
                    ['Cancel Bills',                   true,  true,  false, false],
                    ['Products & Categories',          true,  true,  false, false],
                    ['Stock In / Purchase Orders',      true,  true,  false, false],
                    ['Wastage Recording',              true,  true,  false, false],
                    ['Customer Management',            true,  true,  true,  true],
                    ['Supplier Management',            true,  true,  false, false],
                    ['Expenses',                       true,  true,  true,  false],
                    ['GST & Sales Reports',            true,  true,  true,  false],
                    ['Change Password (Staff)',        true,  true,  false, false],
                    ['Change Password (MD)',           true,  false, false, false],
                    ['Settings & Backups',             true,  false, false, false],
                  ].map(([feat, ...perms]) => `
                    <tr>
                      <td class="font-semibold">${feat}</td>
                      ${perms.map(p => `<td style="text-align:center">${p ? '✅' : '❌'}</td>`).join('')}
                    </tr>`).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>`;
    } catch(e) {
      content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>${e.message}</h3></div>`;
    }
  },

  showModal(userJson = null) {
    const u = userJson ? (typeof userJson === 'string' ? JSON.parse(userJson) : userJson) : null;
    const isSelf = u && u.id === Auth.currentUser?.id;
    const isManager = Auth.isRole('manager');
    const outletName = App.settings?.outlet_name || App.settings?.shop_name || 'This Outlet';

    App.showModal(`
      <div class="modal">
        <div class="modal-header">
          <div class="modal-title">
            <span class="modal-title-icon">${u ? '✏️' : '➕'}</span>
            ${u ? 'Edit User &amp; Reset Password' : 'Add New User'}
          </div>
          <button class="modal-close" onclick="App.closeModal()">✕</button>
        </div>
        ${!u ? `
        <div style="background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);border-radius:var(--r-sm);padding:10px 14px;font-size:12px;color:#A5B4FC;margin-bottom:12px;display:flex;align-items:flex-start;gap:8px">
          <span style="font-size:16px;flex-shrink:0">🏪</span>
          <div><strong>Outlet:</strong> ${outletName}<br>
          <span style="opacity:.8">This user will only be able to sign in at <strong>${outletName}</strong>. They cannot access any other branch's data.</span></div>
        </div>` : ''}
        ${!u ? `
        <div class="form-group">
          <label class="form-label required">Username</label>
          <input class="form-control" id="u-username" placeholder="e.g., john.doe" autocomplete="off">
          <div class="form-hint">Username for login. Cannot be changed later.</div>
        </div>` : `
        <div class="form-group">
          <label class="form-label">Username</label>
          <input class="form-control" value="@${u.username}" disabled style="opacity:0.6">
        </div>`}
        <div class="form-group">
          <label class="form-label required">Full Name</label>
          <input class="form-control" id="u-fullname" value="${u?.full_name || ''}" placeholder="Full display name">
        </div>
        <div class="form-group">
          <label class="form-label required">Role</label>
          <select class="form-control" id="u-role" ${isSelf || (isManager && (u?.role === 'admin' || u?.role === 'md')) ? 'disabled' : ''}>
            <option value="counter_staff" ${u?.role === 'counter_staff' ? 'selected' : ''}>🧾 Counter Staff</option>
            <option value="accountant"    ${u?.role === 'accountant'    ? 'selected' : ''}>📊 Accountant</option>
            <option value="manager"       ${u?.role === 'manager'       ? 'selected' : ''}>🏪 Store Manager</option>
            <option value="md"            ${u?.role === 'md'            ? 'selected' : ''}>👑 Managing Director</option>
            ${!isManager && Auth.user?.role === 'admin' ? `<option value="admin" ${u?.role === 'admin' ? 'selected' : ''}>🛠️ Developer Superuser</option>` : ''}
          </select>
        </div>
        ${!u ? `
        <div class="form-group">
          <label class="form-label required">Password</label>
          <input class="form-control" id="u-password" type="password" placeholder="Min 6 characters" autocomplete="new-password">
        </div>` : `
        <div class="form-group">
          <label class="form-label">Reset Password <span style="color:var(--text-muted);font-weight:400">(leave blank to keep current)</span></label>
          <input class="form-control" id="u-password" type="password" placeholder="New password for staff (min 6 chars)" autocomplete="new-password">
        </div>`}
        ${u && !isSelf ? `
        <div class="form-group">
          <label style="display:flex;align-items:center;gap:10px;cursor:pointer;font-size:13px">
            <input type="checkbox" id="u-active" ${u.active ? 'checked' : ''} style="width:16px;height:16px;accent-color:var(--crimson)">
            <span>Account Active (uncheck to disable login)</span>
          </label>
        </div>` : ''}
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" onclick="UsersAdmin.save(${u?.id || 'null'})">${u ? '💾 Save Changes' : '➕ Create User'}</button>
        </div>
      </div>`);
  },

  async save(id) {
    const full_name = document.getElementById('u-fullname').value.trim();
    const role      = document.getElementById('u-role').value;
    const password  = document.getElementById('u-password').value;
    const active    = document.getElementById('u-active')?.checked ?? true;

    if (!full_name) { App.toast('Full name required', 'error'); return; }

    try {
      if (id) {
        const payload = { full_name, role, active: active ? 1 : 0 };
        if (password) payload.new_password = password;
        await App.api(`/auth/users/${id}`, 'PUT', payload);
        App.toast(password ? 'User details & password updated' : 'User updated', 'success');
      } else {
        const username = document.getElementById('u-username').value.trim();
        if (!username) { App.toast('Username required', 'error'); return; }
        if (!password || password.length < 6) { App.toast('Password must be at least 6 characters', 'error'); return; }
        await App.api('/auth/users', 'POST', { username, full_name, role, password });
        App.toast('User created successfully', 'success');
      }
      App.closeModal();
      this.render();
    } catch(e) { App.toast(e.message, 'error'); }
  },

  async deleteUser(id, username) {
    App.confirm(`Delete user "@${username}"? This cannot be undone.`, 'Delete User', async () => {
      try {
        await App.api(`/auth/users/${id}`, 'DELETE');
        App.toast('User deleted', 'warning');
        this.render();
      } catch(e) { App.toast(e.message, 'error'); }
    });
  },
};

// ── Close dropdown when clicking outside ─────────────────────────────────────
document.addEventListener('click', (e) => {
  if (!e.target.closest('#topbar-user-btn')) {
    Auth.closeDropdown();
  }
});

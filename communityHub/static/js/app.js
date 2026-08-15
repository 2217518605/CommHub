/*============================================================
  邻里汇 · SPA Application v3
============================================================*/

// ===== STATE =====
const S = {
  token: localStorage.getItem('token'),
  refreshToken: localStorage.getItem('refreshToken'),
  userId: localStorage.getItem('userId'),
  user: null,
  page: 'dashboard',
  pageNum: 1,
  pageSize: 10,
  total: 0,
  modalCb: null,
};

const API = '';

// ===== API =====
async function api(url, opts = {}) {
  const headers = {};
  if (!opts.noAuth && S.token) headers['Authorization'] = `Bearer ${S.token}`;
  if (!(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';

  const cfg = { ...opts, headers: { ...headers, ...opts.headers } };
  if (cfg.body && !(cfg.body instanceof FormData) && typeof cfg.body === 'object')
    cfg.body = JSON.stringify(cfg.body);

  try {
    let res = await fetch(API + url, cfg);
    if (res.status === 401 && S.refreshToken) {
      const ok = await refreshToken();
      if (ok) {
        headers['Authorization'] = `Bearer ${S.token}`;
        res = await fetch(API + url, { ...cfg, headers: { ...cfg.headers, ...headers } });
      }
    }
    return handleRes(res);
  } catch (e) {
    toast('网络错误: ' + e.message, 'error');
    throw e;
  }
}

async function handleRes(res) {
  if (res.headers.get('content-type')?.includes('vnd.openxmlformats')) return res.blob();
  const data = await res.json();
  if (!res.ok) { toast(data.detail || data.message || `请求失败(${res.status})`, 'error'); throw new Error(data.detail); }
  return data;
}

async function refreshToken() {
  try {
    const res = await fetch(API + '/user/token/refresh/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: S.refreshToken }),
    });
    if (res.ok) {
      const d = await res.json();
      S.token = d.access; localStorage.setItem('token', d.access);
      if (d.refresh) { S.refreshToken = d.refresh; localStorage.setItem('refreshToken', d.refresh); }
      return true;
    }
  } catch (e) { /* ignore */ }
  doLogout();
  return false;
}

// ===== AUTH =====
async function doLogin() {
  const account = document.getElementById('loginAccount').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  const errEl = document.getElementById('loginError');
  if (!account || !password) { errEl.textContent = '请输入账号和密码'; return; }
  try {
    const res = await fetch(API + '/user/user_login/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account, password }),
    });
    const data = await res.json();
    if (!res.ok) { errEl.textContent = data.detail || data.message || '登录失败'; return; }
    const d = data.data || data;
    S.token = d.access; S.refreshToken = d.refresh; S.userId = d.user_id || d.id;
    localStorage.setItem('token', S.token);
    localStorage.setItem('refreshToken', S.refreshToken);
    localStorage.setItem('userId', S.userId);
    await loadUser();
    showApp();
    toast('登录成功', 'success');
  } catch (e) { errEl.textContent = '登录失败，请检查网络'; }
}

function doLogout() {
  if (S.refreshToken) {
    api('/user/user_logout/', { method: 'POST', body: { refresh: S.refreshToken } }).catch(() => {});
  }
  S.token = null; S.refreshToken = null; S.user = null; S.userId = null;
  localStorage.clear();
  document.getElementById('loginPage').style.display = 'flex';
  document.getElementById('mainApp').style.display = 'none';
  document.getElementById('loginError').textContent = '';
}

async function loadUser() {
  if (!S.userId) return;
  try { const d = await api(`/user/user_retrieve/${S.userId}/`); S.user = d.data || d; updateTopbar(); }
  catch (e) { S.user = null; }
}

function updateTopbar() {
  if (!S.user) return;
  document.getElementById('topbarName').textContent = S.user.username || S.user.account || '用户';
  if (S.user.avatar) document.getElementById('topbarAvatar').src = S.user.avatar;
}

function showApp() {
  document.getElementById('loginPage').style.display = 'none';
  document.getElementById('mainApp').style.display = 'flex';
  go('dashboard');
}

// Enter key login
document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.getElementById('loginPage').style.display !== 'none') doLogin();
});

// ===== ROUTER =====
function go(page, data) {
  S.page = page; S.pageNum = 1;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  render(page, data);
}

async function render(page, data) {
  const ct = document.getElementById('content');
  const pages = { dashboard, profile, organizations, goods, orders, coupons };
  const fn = pages[page];
  if (!fn) return;
  ct.innerHTML = '<div class="spinner"></div>';
  try {
    const html = await fn(data);
    ct.innerHTML = `<div class="page">${html}</div>`;
    if (page === 'dashboard') setTimeout(loadStats, 200);
  } catch (e) {
    ct.innerHTML = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><p>加载失败: ${e.message}</p></div>`;
  }
}

// ===== SIDEBAR =====
function initSidebar() {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => { go(el.dataset.page); document.getElementById('sidebar').classList.remove('open'); });
  });
}

function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }

// ===== SEARCH =====
function handleGlobalSearch(e) {
  if (e.key !== 'Enter') return;
  const q = e.target.value.trim();
  if (!q) return;
  const map = { goods:1, orders:1, organizations:1 };
  go(map[S.page] ? S.page : 'goods', { search: q });
}

// ===== TOAST =====
function toast(msg, type = 'info') {
  const icons = { success: '✓', error: '✕', warning: '!', info: 'i' };
  const ct = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type]}</span><span class="toast-msg">${msg}</span><span class="toast-x" onclick="this.parentElement.remove()">✕</span>`;
  ct.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ===== MODAL =====
function showModal(title, bodyHtml, onSave, size = '') {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = bodyHtml;
  document.getElementById('modalBox').className = 'modal ' + size;
  document.getElementById('modalOverlay').style.display = 'flex';
  S.modalCb = onSave;
}

function closeModal() { document.getElementById('modalOverlay').style.display = 'none'; S.modalCb = null; }

// ===== CONFIRM =====
function showConfirm(msg, cb) {
  document.getElementById('confirmMsg').textContent = msg;
  document.getElementById('confirmBtn').onclick = () => { closeConfirm(); cb(); };
  document.getElementById('confirmOverlay').style.display = 'flex';
}

function closeConfirm() { document.getElementById('confirmOverlay').style.display = 'none'; }

// ===== PAGINATION =====
function attachPagination(container, total, pageSize, pageNum, onChange) {
  const exist = container.querySelector('.pagination');
  if (exist) exist.remove();
  const totalPages = Math.ceil(total / pageSize) || 1;
  if (totalPages <= 1) return;

  let btns = '';
  btns += `<button ${pageNum <= 1 ? 'disabled' : ''} data-p="${pageNum - 1}">‹</button>`;
  const s = Math.max(1, pageNum - 2), e = Math.min(totalPages, pageNum + 2);
  if (s > 1) { btns += `<button data-p="1">1</button>`; if (s > 2) btns += `<button disabled>…</button>`; }
  for (let i = s; i <= e; i++) btns += `<button class="${i === pageNum ? 'active' : ''}" data-p="${i}">${i}</button>`;
  if (e < totalPages) { if (e < totalPages - 1) btns += `<button disabled>…</button>`; btns += `<button data-p="${totalPages}">${totalPages}</button>`; }
  btns += `<button ${pageNum >= totalPages ? 'disabled' : ''} data-p="${pageNum + 1}">›</button>`;

  const wrap = document.createElement('div');
  wrap.className = 'pagination';
  wrap.innerHTML = btns + `<span class="info">共 ${total} 条</span>`;
  container.appendChild(wrap);

  wrap.querySelectorAll('button[data-p]').forEach(btn => {
    btn.addEventListener('click', () => { const p = +btn.dataset.p; if (p && p !== pageNum) onChange(p); });
  });
}

// ===== HELPERS =====
function fmtTime(s) { if (!s) return '-'; return new Date(s).toLocaleString('zh-CN', { hour12: false }); }
function fmtMoney(n) { return '¥' + (Number(n) || 0).toFixed(2); }
function orderStatus(s) {
  const m = { wait_pay: '待支付', wait_deliver: '待发货', wait_receive: '待收货', wait_comment: '待评价', finished: '已完成', cancelled: '已取消' };
  return m[s] || s || '-';
}
function goodsStatus(s) {
  const m = { pending: '审核中', normal: '在售', offshelf: '已下架', soldout: '已售罄' };
  return m[s] || s || '-';
}
function formData(sel) {
  const f = document.querySelector(sel); if (!f) return {};
  const d = {}; f.querySelectorAll('input,textarea,select').forEach(el => { if (el.name) d[el.name] = el.value; });
  return d;
}
function fillForm(sel, data) {
  const f = document.querySelector(sel); if (!f) return;
  Object.entries(data).forEach(([k, v]) => { const el = f.querySelector(`[name="${k}"]`); if (el) el.value = v ?? ''; });
}

// ============================================================
//  PAGES
// ============================================================

// --- DASHBOARD ---
async function dashboard() {
  if (!S.user) await loadUser();
  const u = S.user || {};
  return `
    <h1 class="page-title">仪表盘</h1>
    <div class="stat-row">
      <div class="card stat-card">
        <div class="stat-icon-wrap" style="background:var(--indigo-bg);"><svg viewBox="0 0 24 24" fill="none" stroke="var(--indigo)" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>
        <div class="stat-num">${u.username || u.account || '-'}</div>
        <div class="stat-label">欢迎回来</div>
      </div>
      <div class="card stat-card">
        <div class="stat-icon-wrap" style="background:var(--teal-bg);"><svg viewBox="0 0 24 24" fill="none" stroke="var(--teal)" stroke-width="2"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/></svg></div>
        <div class="stat-num" id="statOrg">-</div>
        <div class="stat-label">组织数量</div>
      </div>
      <div class="card stat-card">
        <div class="stat-icon-wrap" style="background:var(--rose-bg);"><svg viewBox="0 0 24 24" fill="none" stroke="var(--rose)" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg></div>
        <div class="stat-num" id="statGoods">-</div>
        <div class="stat-label">商品总数</div>
      </div>
      <div class="card stat-card">
        <div class="stat-icon-wrap" style="background:var(--amber-bg);"><svg viewBox="0 0 24 24" fill="none" stroke="var(--amber)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></div>
        <div class="stat-num" id="statOrder">-</div>
        <div class="stat-label">订单总数</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:22px" class="detail-grid">
      <div class="card">
        <div class="card-header"><div><h3>快捷操作</h3><div class="desc">常用功能入口</div></div></div>
        <div class="flex flex-col gap-3">
          <button class="btn btn-primary w-full" onclick="go('goods')">浏览商品</button>
          <button class="btn btn-accent w-full" onclick="go('orders')">我的订单</button>
          <button class="btn btn-success w-full" onclick="go('coupons')">优惠券中心</button>
          <button class="btn btn-ghost w-full" onclick="go('organizations')">组织管理</button>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><div><h3>个人资料</h3><div class="desc">账户基本信息</div></div><button class="btn btn-primary btn-sm" onclick="go('profile')">编辑</button></div>
        <dl class="detail-grid" style="grid-template-columns:1fr 1fr">
          <div class="item"><dt>账号</dt><dd>${u.account || '-'}</dd></div>
          <div class="item"><dt>用户名</dt><dd>${u.username || '-'}</dd></div>
          <div class="item"><dt>邮箱</dt><dd>${u.email || '-'}</dd></div>
          <div class="item"><dt>手机</dt><dd>${u.mobile || '-'}</dd></div>
          <div class="item"><dt>余额</dt><dd class="color-emerald" style="font-weight:700">${fmtMoney(u.balance)}</dd></div>
          <div class="item"><dt>角色</dt><dd><span class="badge badge-indigo">${u.user_type===3?'超级管理员':u.user_type===2?'管理员':u.user_type===1?'商家':'居民'}</span></dd></div>
        </dl>
      </div>
    </div>`;
}

async function loadStats() {
  try {
    const [o, g, ord] = await Promise.allSettled([
      api('/organization/organization_list/', { method: 'POST', body: {} }),
      api('/goods/goods_list_by_query_name/', { method: 'POST', body: { name: '' } }),
      api('/order/order_retrieve/', { method: 'GET' }).catch(() => ({ data: { total: '-' } })),
    ]);
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set('statOrg', o.status === 'fulfilled' ? (o.value?.data?.total ?? '-') : '-');
    set('statGoods', g.status === 'fulfilled' ? (g.value?.data?.total ?? '-') : '-');
    set('statOrder', ord.status === 'fulfilled' ? (ord.value?.data?.total ?? '-') : '-');
  } catch (e) { /* ignore */ }
}

// --- PROFILE ---
async function profile() {
  if (!S.user) await loadUser();
  const u = S.user || {};
  return `
    <h1 class="page-title">个人中心</h1>
    <div style="display:grid;grid-template-columns:280px 1fr;gap:24px" class="detail-grid">
      <div class="card text-center">
        <img src="${u.avatar || '/media/user_avatars/default_user_avatar.png'}" class="avatar-lg" style="margin:0 auto 16px;width:100px;height:100px" onerror="this.src='/media/user_avatars/default_user_avatar.png'">
        <div style="font-size:20px;font-weight:800">${u.username || u.account || '-'}</div>
        <div class="text-muted text-sm mt-1">${u.account || ''}</div>
        <div class="mt-3"><span class="badge badge-indigo">${u.user_type===3?'超级管理员':u.user_type===2?'管理员':u.user_type===1?'商家':'居民'}</span></div>
        <div style="margin-top:18px;padding-top:18px;border-top:1px solid var(--border-1)">
          <div style="font-size:28px;font-weight:900" class="color-emerald">${fmtMoney(u.balance)}</div>
          <div class="text-sm text-muted mt-1">账户余额</div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><div><h3>基本信息</h3><div class="desc">管理您的账户资料</div></div><button class="btn btn-primary btn-sm" onclick="editProfile()">编辑资料</button></div>
        <dl class="detail-grid">
          <div class="item"><dt>邮箱</dt><dd>${u.email || '-'}</dd></div>
          <div class="item"><dt>手机号</dt><dd>${u.mobile || '-'}</dd></div>
          <div class="item"><dt>出生日期</dt><dd>${u.birth_date || '-'}</dd></div>
          <div class="item"><dt>身份证</dt><dd>${u.id_card ? '****' + String(u.id_card).slice(-4) : '-'}</dd></div>
          <div class="item"><dt>注册时间</dt><dd>${fmtTime(u.create_time)}</dd></div>
          <div class="item"><dt>最后登录</dt><dd>${fmtTime(u.last_login)}</dd></div>
        </dl>
      </div>
    </div>
    <div class="card mt-4">
      <div class="card-header"><h3>账户安全</h3></div>
      <div class="btn-group">
        <button class="btn btn-ghost btn-sm" onclick="toast('请联系管理员修改密码','info')">修改密码</button>
        <button class="btn btn-danger btn-sm" onclick="doLogout()">退出登录</button>
      </div>
    </div>`;
}

function editProfile() {
  const u = S.user || {};
  const html = `
    <form id="profileForm" class="form-grid">
      <div class="form-field"><label>用户名</label><input type="text" name="username" value="${u.username||''}"></div>
      <div class="form-field"><label>邮箱</label><input type="email" name="email" value="${u.email||''}"></div>
      <div class="form-field"><label>手机号</label><input type="text" name="mobile" value="${u.mobile||''}"></div>
      <div class="form-field"><label>出生日期</label><input type="date" name="birth_date" value="${u.birth_date||''}"></div>
      <div class="form-field col-span-2"><label>身份证号</label><input type="text" name="id_card" value="${u.id_card||''}"></div>
    </form>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveProfile()">保存</button></div>`;
  showModal('编辑个人资料', html);
}

async function saveProfile() {
  const d = formData('#profileForm');
  try {
    await api(`/user/user_retrieve/${S.userId}/`, { method: 'PUT', body: d });
    S.user = { ...S.user, ...d }; updateTopbar(); closeModal();
    toast('资料已更新', 'success'); go('profile');
  } catch (e) { /* toast shown */ }
}

// --- ORGANIZATIONS ---
async function organizations(opts) {
  const q = opts?.search || '';
  let tbody = ''; let total = 0;
  try {
    const d = await api('/organization/organization_list/', { method: 'POST', body: { name: q, page: S.pageNum, page_size: S.pageSize } });
    const list = (d.data || d).list || [];
    total = (d.data || d).total || 0; S.total = total;
    if (!list.length) {
      tbody = `<tr><td colspan="8"><div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/></svg><p>暂无组织数据</p></div></td></tr>`;
    } else {
      tbody = list.map(o => `
        <tr>
          <td>${o.id}</td><td><strong>${o.org_name||'-'}</strong></td>
          <td>${o.contact_person||'-'}</td><td>${o.contact_phone||'-'}</td><td>${o.contact_email||'-'}</td>
          <td class="truncate" style="max-width:140px">${o.address||'-'}</td>
          <td>${fmtTime(o.create_time)}</td>
          <td>
            <div class="btn-group">
              <button class="btn-icon" title="编辑" onclick="editOrg(${o.id})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
              <button class="btn-icon" title="删除" onclick="delOrg(${o.id},'${(o.org_name||'').replace(/'/g,"\\'")}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
            </div>
          </td>
        </tr>`).join('');
    }
  } catch (e) { tbody = `<tr><td colspan="8"><div class="empty-state"><p>加载失败</p></div></td></tr>`; }

  const html = `
    <h1 class="page-title">组织管理</h1>
    <div class="card">
      <div class="card-header"><div><h3>组织列表</h3><div class="desc">管理机构与社区组织</div></div><div class="btn-group"><button class="btn btn-accent btn-sm" onclick="exportOrgs()">导出Excel</button><button class="btn btn-primary btn-sm" onclick="newOrg()">新建组织</button></div></div>
      <div class="search-bar">
        <input type="text" id="orgSearch" placeholder="搜索组织名称..." value="${q}" onkeyup="if(event.key==='Enter')go('organizations',{search:this.value})">
        <button class="btn btn-primary btn-sm" onclick="go('organizations',{search:document.getElementById('orgSearch')?.value||''})">搜索</button>
      </div>
      <div class="table-shell"><table><thead><tr><th>ID</th><th>名称</th><th>联系人</th><th>电话</th><th>邮箱</th><th>地址</th><th>创建时间</th><th>操作</th></tr></thead><tbody>${tbody}</tbody></table></div>
      <div id="orgPagination"></div>
    </div>`;

  setTimeout(() => {
    const ct = document.getElementById('orgPagination');
    if (ct && total > 0) attachPagination(ct, total, S.pageSize, S.pageNum, p => { S.pageNum = p; go('organizations', { search: document.getElementById('orgSearch')?.value || '' }); });
  }, 0);
  return html;
}

function newOrg() {
  showModal('新建组织', `
    <form id="orgForm" class="form-grid">
      <div class="form-field"><label>组织名称 *</label><input type="text" name="org_name" required></div>
      <div class="form-field"><label>联系人</label><input type="text" name="contact_person"></div>
      <div class="form-field"><label>联系电话</label><input type="text" name="contact_phone"></div>
      <div class="form-field"><label>联系邮箱</label><input type="email" name="contact_email"></div>
      <div class="form-field col-span-2"><label>地址</label><input type="text" name="address"></div>
      <div class="form-field col-span-2"><label>描述</label><textarea name="description"></textarea></div>
    </form>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveOrg()">创建</button></div>`);
}

async function saveOrg() {
  const d = formData('#orgForm');
  if (!d.org_name) { toast('请输入组织名称', 'warning'); return; }
  try { await api('/organization/organization_create/', { method: 'POST', body: d }); closeModal(); toast('创建成功', 'success'); go('organizations'); } catch (e) { }
}

async function editOrg(id) {
  try {
    const d = await api(`/organization/organization_retrieve/${id}/`);
    const o = d.data || d;
    showModal('编辑组织', `
      <form id="orgForm" class="form-grid">
        <div class="form-field"><label>组织名称 *</label><input type="text" name="org_name" value="${o.org_name||''}" required></div>
        <div class="form-field"><label>联系人</label><input type="text" name="contact_person" value="${o.contact_person||''}"></div>
        <div class="form-field"><label>联系电话</label><input type="text" name="contact_phone" value="${o.contact_phone||''}"></div>
        <div class="form-field"><label>联系邮箱</label><input type="email" name="contact_email" value="${o.contact_email||''}"></div>
        <div class="form-field col-span-2"><label>地址</label><input type="text" name="address" value="${o.address||''}"></div>
        <div class="form-field col-span-2"><label>描述</label><textarea name="description">${o.description||''}</textarea></div>
      </form>
      <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="updateOrg(${id})">保存</button></div>`);
  } catch (e) { }
}

async function updateOrg(id) {
  const d = formData('#orgForm');
  try { await api(`/organization/organization_retrieve/${id}/`, { method: 'PUT', body: d }); closeModal(); toast('更新成功', 'success'); go('organizations'); } catch (e) { }
}

function delOrg(id, name) {
  showConfirm(`确定要删除组织「${name}」吗？`, async () => {
    try { await api(`/organization/organization_retrieve/${id}/`, { method: 'DELETE' }); toast('已删除', 'success'); go('organizations'); } catch (e) { }
  });
}

async function exportOrgs() {
  try {
    toast('正在生成...', 'info');
    const d = await api('/organization/organization_list/', { method: 'GET' });
    if (d instanceof Blob) { const a = document.createElement('a'); a.href = URL.createObjectURL(d); a.download = 'organizations.xlsx'; a.click(); }
    else if (d.data?.file_name) window.open(API + '/organization/organization_list_export/' + d.data.file_name + '/', '_blank');
    toast('导出成功', 'success');
  } catch (e) { }
}

// --- GOODS ---
async function goods(opts) {
  const q = opts?.search || '';
  let body = ''; let total = 0;
  try {
    const d = await api('/goods/goods_list_by_query_name/', { method: 'POST', body: { name: q, page: S.pageNum, page_size: 12 } });
    const list = (d.data || d).list || [];
    total = (d.data || d).total || 0; S.total = total;
    if (!list.length) {
      body = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg><p>暂无商品</p></div>`;
    } else {
      body = `<div class="goods-grid">${list.map(g => `
        <div class="goods-card" onclick="goodsDetail(${g.id})">
          <div class="img-wrap">
            <img src="${g.small_img || g.big_img || '/media/goods_photos/default_goods_photos.png'}" alt="${g.name}" onerror="this.src='/media/goods_photos/default_goods_photos.png'">
            <span class="status-tag" style="background:${g.status==='normal'?'var(--emerald-bg)':g.status==='pending'?'var(--amber-bg)':'var(--rose-bg)'};color:${g.status==='normal'?'var(--emerald)':g.status==='pending'?'var(--amber)':'var(--rose)'}">${goodsStatus(g.status)}</span>
          </div>
          <div class="body">
            <div class="name">${g.name||'未命名'}</div>
            <div class="price">${fmtMoney(g.price)}</div>
            <div class="meta"><span>库存 ${g.number??0}</span><span>已售 ${g.sold_count??0}</span></div>
          </div>
        </div>`).join('')}</div>`;
    }
  } catch (e) { body = `<div class="empty-state"><p>加载失败</p></div>`; }

  const html = `
    <h1 class="page-title">商品管理</h1>
    <div class="card">
      <div class="card-header"><div><h3>商品列表</h3><div class="desc">浏览与管理社区商品</div></div><button class="btn btn-primary btn-sm" onclick="newGoods()">发布商品</button></div>
      <div class="search-bar">
        <input type="text" id="goodsSearch" placeholder="搜索商品..." value="${q}" onkeyup="if(event.key==='Enter')go('goods',{search:this.value})">
        <button class="btn btn-primary btn-sm" onclick="go('goods',{search:document.getElementById('goodsSearch')?.value||''})">搜索</button>
      </div>
      <div id="goodsContainer">${body}</div>
    </div>`;

  setTimeout(() => {
    const ct = document.getElementById('goodsContainer');
    if (ct && total > 0) attachPagination(ct, total, 12, S.pageNum, p => { S.pageNum = p; go('goods', { search: document.getElementById('goodsSearch')?.value || '' }); });
  }, 0);
  return html;
}

async function goodsDetail(gid) {
  try {
    const d = await api(`/goods/goods_retrieve/${gid}/`);
    const g = d.data || d;
    S.currentGoodsId = gid;
    const cmt = await renderComments(gid);
    showModal(g.name || '商品详情', `
      <div class="flex gap-4" style="flex-wrap:wrap">
        <img src="${g.big_img || g.small_img || '/media/goods_photos/default_goods_photos.png'}" style="width:260px;height:260px;object-fit:cover;border-radius:var(--r-md)" onerror="this.src='/media/goods_photos/default_goods_photos.png'">
        <div style="flex:1;min-width:240px">
          <dl class="detail-grid">
            <div class="item"><dt>名称</dt><dd>${g.name||'-'}</dd></div>
            <div class="item"><dt>价格</dt><dd style="font-size:22px;font-weight:900" class="color-rose">${fmtMoney(g.price)}</dd></div>
            <div class="item"><dt>库存</dt><dd>${g.number??0}</dd></div>
            <div class="item"><dt>已售</dt><dd>${g.sold_count??0}</dd></div>
            <div class="item"><dt>状态</dt><dd><span class="badge badge-${g.status==='normal'?'emerald':g.status==='pending'?'amber':'rose'}">${goodsStatus(g.status)}</span></dd></div>
            <div class="item"><dt>时间</dt><dd>${fmtTime(g.create_time)}</dd></div>
            <div class="item col-span-2"><dt>描述</dt><dd>${g.desc||'暂无'}</dd></div>
          </dl>
          <div class="btn-group mt-4">
            <button class="btn btn-accent btn-sm" onclick="buyGoods(${g.id},'${(g.name||'').replace(/'/g,"\\'")}',${g.price||0})">立即购买</button>
            <button class="btn btn-primary btn-sm" onclick="editGoods(${g.id})">编辑</button>
            <button class="btn btn-danger btn-sm" onclick="delGoods(${g.id},'${(g.name||'').replace(/'/g,"\\'")}')">删除</button>
          </div>
        </div>
      </div>
      ${cmt}`, null, 'modal-lg');
    setTimeout(() => initCommentEvents(gid), 100);
  } catch (e) { }
}

function newGoods() {
  showModal('发布商品', `
    <form id="goodsForm" class="form-grid" enctype="multipart/form-data">
      <div class="form-field"><label>商品名称 *</label><input type="text" name="name" required></div>
      <div class="form-field"><label>价格 *</label><input type="number" name="price" step="0.01" required></div>
      <div class="form-field"><label>库存 *</label><input type="number" name="number" required></div>
      <div class="form-field"><label>状态</label><select name="status"><option value="pending">审核中</option><option value="normal" selected>在售</option><option value="offshelf">下架</option></select></div>
      <div class="form-field col-span-2"><label>描述</label><textarea name="desc"></textarea></div>
      <div class="form-field"><label>主图</label><input type="file" name="big_img" accept="image/*"></div>
      <div class="form-field"><label>缩略图</label><input type="file" name="small_img" accept="image/*"></div>
    </form>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveGoods()">发布</button></div>`, null, 'modal-lg');
}

async function saveGoods() {
  const fd = new FormData(document.getElementById('goodsForm'));
  try { await api('/goods/goods_create/', { method: 'POST', body: fd }); closeModal(); toast('发布成功', 'success'); go('goods'); } catch (e) { }
}

async function editGoods(id) {
  const d = await api(`/goods/goods_retrieve/${id}/`);
  const g = d.data || d;
  showModal('编辑商品', `
    <form id="goodsForm" class="form-grid">
      <div class="form-field"><label>名称</label><input type="text" name="name" value="${g.name||''}" required></div>
      <div class="form-field"><label>价格</label><input type="number" name="price" step="0.01" value="${g.price||0}" required></div>
      <div class="form-field"><label>库存</label><input type="number" name="number" value="${g.number||0}" required></div>
      <div class="form-field"><label>状态</label><select name="status"><option value="pending" ${g.status==='pending'?'selected':''}>审核中</option><option value="normal" ${g.status==='normal'?'selected':''}>在售</option><option value="offshelf" ${g.status==='offshelf'?'selected':''}>下架</option></select></div>
      <div class="form-field col-span-2"><label>描述</label><textarea name="desc">${g.desc||''}</textarea></div>
    </form>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="updateGoods(${id})">保存</button></div>`, null, 'modal-lg');
}

async function updateGoods(id) {
  const d = formData('#goodsForm');
  try { await api(`/goods/goods_retrieve/${id}/`, { method: 'PUT', body: d }); closeModal(); toast('更新成功', 'success'); go('goods'); } catch (e) { }
}

function delGoods(id, name) {
  showConfirm(`确定删除「${name}」？`, async () => {
    try { await api(`/goods/goods_retrieve/${id}/`, { method: 'DELETE' }); closeModal(); toast('已删除', 'success'); go('goods'); } catch (e) { }
  });
}

async function buyGoods(gid, name, price) {
  showModal('创建订单', `
    <form id="orderForm" class="form-grid col-1">
      <div class="form-field"><label>商品</label><input type="text" value="${name}" disabled></div>
      <div class="form-field"><label>单价</label><input type="text" value="${fmtMoney(price)}" disabled></div>
      <div class="form-field"><label>数量</label><input type="number" name="good_count" value="1" min="1" required></div>
      <div class="form-field"><label>支付方式</label><select name="pay_method"><option value="alipay">支付宝</option><option value="wechat">微信</option><option value="cod">货到付款</option></select></div>
      <div class="form-field"><label>备注</label><textarea name="user_remark"></textarea></div>
    </form>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-accent" onclick="createOrder(${gid})">提交订单</button></div>`);
}

async function createOrder(gid) {
  const d = formData('#orderForm'); d.goods = gid; d.good_count = parseInt(d.good_count) || 1;
  try { await api('/order/order_retrieve/', { method: 'POST', body: d }); closeModal(); toast('订单创建成功', 'success'); go('orders'); } catch (e) { }
}

// --- COMMENTS ---
async function renderComments(goodsId) {
  let list = '';
  try {
    const d = await api('/goods/goods_comments_list/', { method: 'POST', body: { goods_id: goodsId, page: 1, page_size: 50 } });
    const items = (d.data || d).list || (d.data || d).results || [];
    if (!items.length) list = `<div class="text-center text-muted" style="padding:20px">暂无评论</div>`;
    else list = `<div class="comment-list">${items.map(c => commentItem(c)).join('')}</div>`;
  } catch (e) { list = `<div class="text-muted text-center" style="padding:20px">加载失败</div>`; }
  return `
    <div class="card mt-4" id="commentsSec">
      <div class="card-header"><h3>商品评论</h3></div>
      ${list}
      <div class="comment-input"><textarea id="newComment" placeholder="写下你的评论..."></textarea><button class="btn btn-primary btn-sm" onclick="postComment(${goodsId})" style="align-self:flex-end">发布</button></div>
    </div>`;
}

function commentItem(c) {
  const replies = (c.replies || []).map(r => commentItem(r)).join('');
  return `
    <div class="comment-item" id="cmt-${c.id}">
      <div class="comment-header">
        <img src="${c.user_avatar||'/media/user_avatars/default_user_avatar.png'}" class="comment-avatar" onerror="this.src='/media/user_avatars/default_user_avatar.png'">
        <div><div class="comment-author">${c.username||c.user_name||'匿名'}</div><div class="comment-time">${fmtTime(c.create_time)}</div></div>
      </div>
      <div class="comment-text">${c.comment_text||c.content||''}</div>
      <div class="comment-actions">
        <button onclick="likeCmt(${c.id},this)">♥ <span>${c.like_num||0}</span></button>
        <button onclick="toggleReply(${c.id})">回复</button>
      </div>
      <div id="replyBox-${c.id}" style="display:none" class="comment-input mt-2">
        <textarea id="replyText-${c.id}" placeholder="输入回复..."></textarea>
        <button class="btn btn-primary btn-xs" onclick="postReply(${c.id})" style="align-self:flex-end">回复</button>
      </div>
      ${replies ? `<div class="comment-replies">${replies}</div>` : ''}
    </div>`;
}

function initCommentEvents(gid) { /* inline handlers used */ }

async function postComment(gid) {
  const t = document.getElementById('newComment')?.value?.trim();
  if (!t) { toast('请输入评论', 'warning'); return; }
  try { await api('/goods/goods_comments_create/', { method: 'POST', body: { goods: gid, comment_text: t } }); toast('评论成功', 'success'); goodsDetail(gid); } catch (e) { }
}

async function postReply(pid) {
  const t = document.getElementById('replyText-' + pid)?.value?.trim();
  if (!t) { toast('请输入内容', 'warning'); return; }
  try { await api('/goods/goods_comments_create/', { method: 'POST', body: { parent: pid, comment_text: t } }); toast('回复成功', 'success'); go('goods'); } catch (e) { }
}

async function likeCmt(cid, btn) {
  try {
    await api('/goods/goods_comment_increase_like_num/', { method: 'POST', body: { comment_id: cid } });
    const s = btn.querySelector('span'); if (s) s.textContent = (+s.textContent || 0) + 1;
  } catch (e) { }
}

function toggleReply(cid) {
  const el = document.getElementById('replyBox-' + cid);
  if (el) el.style.display = el.style.display === 'none' ? 'flex' : 'none';
}

// --- ORDERS ---
async function orders() {
  let tbody = ''; let total = 0;
  try {
    let d; try { d = await api('/order/order_retrieve/', { method: 'GET' }); } catch (e) { d = { data: { list: [], total: 0 } }; }
    const list = (d.data || d).list || (d.data || d).results || [];
    total = (d.data || d).total || 0;
    if (!list.length) {
      tbody = `<tr><td colspan="7"><div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><p>暂无订单</p></div></td></tr>`;
    } else {
      tbody = list.map(o => `
        <tr>
          <td><code>${(o.order_number||'').slice(-12)}</code></td>
          <td>${o.goods_name||'-'}</td>
          <td style="font-weight:700">${fmtMoney(o.pay_price||o.total_price)}</td>
          <td><span class="badge badge-${o.status==='finished'?'emerald':o.status==='cancelled'?'rose':o.status==='wait_pay'?'amber':'sky'}">${orderStatus(o.status)}</span></td>
          <td>${o.pay_method==='alipay'?'支付宝':o.pay_method==='wechat'?'微信':o.pay_method==='cod'?'货到付款':o.pay_method||'-'}</td>
          <td>${fmtTime(o.create_time)}</td>
          <td>
            <div class="btn-group">
              ${o.status==='wait_pay'?`<button class="btn btn-accent btn-xs" onclick="payOrder('${o.order_number}')">付款</button>`:''}
              ${o.status==='wait_receive'?`<button class="btn btn-success btn-xs" onclick="receiveOrder('${o.order_number}')">确认收货</button>`:''}
              <button class="btn-icon" onclick="delOrder('${o.order_number}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
            </div>
          </td>
        </tr>`).join('');
    }
  } catch (e) { tbody = `<tr><td colspan="7"><div class="empty-state"><p>加载失败</p></div></td></tr>`; }

  return `
    <h1 class="page-title">订单管理</h1>
    <div class="card">
      <div class="card-header"><div><h3>订单列表</h3><div class="desc">查看与管理所有订单</div></div><button class="btn btn-accent btn-sm" onclick="go('goods')">选购商品</button></div>
      <div class="table-shell"><table><thead><tr><th>订单号</th><th>商品</th><th>金额</th><th>状态</th><th>支付</th><th>时间</th><th>操作</th></tr></thead><tbody>${tbody}</tbody></table></div>
    </div>`;
}

async function payOrder(on) {
  try {
    const d = await api('/order/order_pay/', { method: 'POST', body: { order_number: on, pay_method: 'alipay' } });
    const url = d.data?.pay_url || d.data?.alipay_url || d.pay_url;
    if (url) { window.open(url, '_blank'); toast('已打开支付页面', 'info'); }
    else toast('获取支付链接失败', 'error');
  } catch (e) { }
}

async function receiveOrder(on) {
  try { await api('/order/order_retrieve/', { method: 'PUT', body: { order_number: on, status: 'wait_comment' } }); toast('已确认收货', 'success'); go('orders'); } catch (e) { }
}

function delOrder(on) {
  showConfirm(`确定删除订单「...${on.slice(-8)}」？`, async () => {
    try { await api(`/order/order_retrieve/${on}/`, { method: 'DELETE' }); toast('已删除', 'success'); go('orders'); } catch (e) { }
  });
}

// --- COUPONS ---
async function coupons() {
  const u = S.user || {};
  const isAdmin = u.user_type >= 2;
  let tplHtml = '';

  try {
    const d = await api('/discount/coupon_template/', { method: 'GET' });
    const list = (d.data || d).list || (d.data || d).results || [];
    const active = list.filter(t => t.is_active);
    if (!active.length) {
      tplHtml = `<div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12h20"/><path d="M6 4v16"/><path d="M18 4v16"/></svg><p>暂无可用优惠券</p></div>`;
    } else {
      tplHtml = `<div class="coupon-grid">${active.map(t => `
        <div class="coupon-card">
          <div class="top">
            <div class="amount color-indigo">${t.type==='cash'?'¥'+(t.discount||0):t.type==='discount'?'打'+(t.discount||1)*10+'折':'减¥'+(t.discount||0)}</div>
            <div class="name">${t.name||'优惠券'}</div>
            <div class="desc">${t.description||''}</div>
          </div>
          <div class="divider"></div>
          <div class="bottom">
            <div class="info">${t.min_purchase>0?'满'+fmtMoney(t.min_purchase)+'可用':'无门槛'}<br>剩余${t.total_count!=null?t.total_count:'∞'}张<br>${formatShortDate(t.valid_from)}~${formatShortDate(t.valid_to)}</div>
            <button class="btn btn-accent btn-sm" onclick="claimCoupon(${t.id})">立即领取</button>
          </div>
        </div>`).join('')}</div>`;
    }
  } catch (e) { tplHtml = `<div class="empty-state"><p>加载失败</p></div>`; }

  return `
    <h1 class="page-title">优惠券中心</h1>
    ${isAdmin ? `
    <div class="card mb-4">
      <div class="card-header"><div><h3>模板管理</h3><div class="desc">创建与编辑优惠券模板</div></div><button class="btn btn-primary btn-sm" onclick="newCouponTpl()">创建模板</button></div>
    </div>` : ''}
    <div class="card">
      <div class="card-header"><h3>可领取优惠券</h3></div>
      ${tplHtml}
    </div>`;
}

function formatShortDate(s) { if (!s) return ''; return s.split('T')[0] || s.slice(0, 10); }

async function claimCoupon(tid) {
  try { await api('/discount/user_coupon/', { method: 'POST', body: { template_id: tid } }); toast('领取成功！', 'success'); } catch (e) { }
}

function newCouponTpl() {
  showModal('创建优惠券模板', `
    <form id="couponForm" class="form-grid">
      <div class="form-field"><label>名称 *</label><input type="text" name="name" required></div>
      <div class="form-field"><label>类型</label><select name="type" id="couponType" onchange="switchCouponFields()"><option value="1">满减券</option><option value="2">折扣券</option><option value="3">现金券</option></select></div>
      <div id="couponTypeFields" class="form-grid col-span-2"></div>
      <div class="form-field"><label>发放总数</label><input type="number" name="total_count" value="100"></div>
      <div class="form-field"><label>每人限领</label><input type="number" name="person_limit_count" value="1"></div>
      <div class="form-field"><label>生效时间</label><input type="datetime-local" name="valid_from"></div>
      <div class="form-field"><label>失效时间</label><input type="datetime-local" name="valid_to"></div>
      <div class="form-field col-span-2"><label>描述</label><textarea name="description"></textarea></div>
    </form>
    <div class="modal-footer"><button class="btn btn-ghost" onclick="closeModal()">取消</button><button class="btn btn-primary" onclick="saveCouponTpl()">创建</button></div>`, null, 'modal-lg');
  switchCouponFields();
}

function switchCouponFields() {
  const type = Number(document.getElementById('couponType')?.value);
  const fields = document.getElementById('couponTypeFields');
  if (!fields) return;
  if (type === 1) fields.innerHTML = '<div class="form-field"><label>满多少（元）*</label><input type="number" name="min_purchase" min="0.01" step="0.01" required placeholder="例如：100"></div><div class="form-field"><label>减多少（元）*</label><input type="number" name="discount_amount" min="0.01" step="0.01" required placeholder="例如：20"></div>';
  else if (type === 2) fields.innerHTML = '<div class="form-field col-span-2"><label>折扣（1-10）*</label><input type="number" name="discount_rate" min="1" max="10" step="0.1" required placeholder="例如：8，表示8折"></div>';
  else fields.innerHTML = '<div class="form-field col-span-2"><label>面额（元）*</label><input type="number" name="discount_amount" min="0.01" step="0.01" required placeholder="例如：20"></div>';
}

async function saveCouponTpl() {
  const d = formData('#couponForm');
  const type = Number(d.type);
  if (!d.name) { toast('请输入名称', 'warning'); return; }
  if (type === 1 && (!d.min_purchase || !d.discount_amount)) { toast('请填写满多少和减多少', 'warning'); return; }
  if (type === 2 && (!d.discount_rate || Number(d.discount_rate) < 1 || Number(d.discount_rate) > 10)) { toast('折扣请填写1到10', 'warning'); return; }
  if (type === 3 && !d.discount_amount) { toast('请填写现金券面额', 'warning'); return; }
  d.min_purchase = type === 1 ? Number(d.min_purchase) : 0;
  d.discount_amount = type === 2 ? 0 : Number(d.discount_amount);
  d.discount = type === 2 ? Number(d.discount_rate) / 10 : 1;
  delete d.discount_rate;
  try { await api('/discount/coupon_template/', { method: 'POST', body: d }); closeModal(); toast('创建成功', 'success'); go('coupons'); } catch (e) { }
}

// ===== INIT =====
async function init() {
  initSidebar();
  if (S.token && S.userId) {
    try { await loadUser(); if (S.user) { showApp(); setTimeout(loadStats, 200); return; } } catch (e) { }
  }
  document.getElementById('loginPage').style.display = 'flex';
}

// Export to window
window.doLogin = doLogin;
window.doLogout = doLogout;
window.go = go;
window.closeModal = closeModal;
window.showConfirm = showConfirm;
window.closeConfirm = closeConfirm;
window.toggleSidebar = toggleSidebar;
window.handleGlobalSearch = handleGlobalSearch;
window.toast = toast;
window.editProfile = editProfile;
window.saveProfile = saveProfile;
window.newOrg = newOrg;
window.editOrg = editOrg;
window.saveOrg = saveOrg;
window.updateOrg = updateOrg;
window.delOrg = delOrg;
window.exportOrgs = exportOrgs;
window.newGoods = newGoods;
window.editGoods = editGoods;
window.saveGoods = saveGoods;
window.updateGoods = updateGoods;
window.delGoods = delGoods;
window.goodsDetail = goodsDetail;
window.buyGoods = buyGoods;
window.createOrder = createOrder;
window.postComment = postComment;
window.postReply = postReply;
window.likeCmt = likeCmt;
window.toggleReply = toggleReply;
window.payOrder = payOrder;
window.receiveOrder = receiveOrder;
window.delOrder = delOrder;
window.claimCoupon = claimCoupon;
window.newCouponTpl = newCouponTpl;
window.saveCouponTpl = saveCouponTpl;

document.addEventListener('DOMContentLoaded', init);

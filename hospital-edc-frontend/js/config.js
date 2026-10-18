// API配置
// 同源部署：默认请求当前源；多实例 Nginx 按路径分发时（如 /project-a/）自动取路径前缀，
// 这样前端无需为每个实例单独构建。
const API_BASE = (function () {
  const m = window.location.pathname.match(/^\/(project-[^/]+)\//);
  return m ? m[1] : '';
})();

// Token管理
function getToken() {
  return sessionStorage.getItem('edc_token');
}

function setToken(t) {
  sessionStorage.setItem('edc_token', t);
}

function clearToken() {
  sessionStorage.removeItem('currentPatient');
  sessionStorage.removeItem('pendingVisitId');
  if (typeof WeeklyEntry !== 'undefined') { WeeklyEntry.stop(); WeeklyEntry.week = ''; }
  sessionStorage.removeItem('edc_token');
  sessionStorage.removeItem('edc_user');
}

// 用户信息管理
function getUser() {
  try {
    return JSON.parse(sessionStorage.getItem('edc_user') || 'null');
  } catch(e) {
    return null;
  }
}

function setUser(u) {
  sessionStorage.setItem('edc_user', JSON.stringify(u));
}

// API请求封装
async function api(method, path, body) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(API_BASE + path, opts);
  if (token !== getToken()) throw new Error('账号已切换，已忽略旧请求');
  if (res.status === 401) {
    clearToken();
    document.getElementById('login-overlay').classList.remove('hidden');
    throw new Error('登录已过期，请重新登录');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(err.detail || '请求失败');
  }
  const data = await res.json();
  if (token !== getToken()) throw new Error('账号已切换，已忽略旧请求');
  return data;
}


const STUDY_GROUP_LABELS = {
  integrated_weekly: 'A组：三一照护+周制剂', integrated_daily: 'B组：三一照护+每日注射',
  usual_weekly: 'C组：常规诊疗+周制剂', usual_daily: 'D组：常规诊疗+周制剂',
};
function escapeText(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

const STUDY_SUBGROUP_LABELS = {
  icodec: '依柯胰岛素', semaglutide: '司美格鲁肽注射液',
  icodec_semaglutide: '依柯胰岛素 + 司美格鲁肽注射液',
  daily_glp1: '利拉鲁肽/利司那肽注射液', daily_insulin: '甘精/德谷/地特胰岛素',
  daily_combination: '甘精胰岛素利司那肽注射液/德谷胰岛素利拉鲁肽注射液',
};
function fillStudySubgroups(group, targetId, selected = '') {
  const el = document.getElementById(targetId);
  if (!el) return;
  const keys = !group ? [] : Object.keys(STUDY_SUBGROUP_LABELS).slice(
    ['integrated_weekly', 'usual_weekly'].includes(group) ? 0 : 3,
    ['integrated_weekly', 'usual_weekly'].includes(group) ? 3 : 6);
  el.innerHTML = '<option value="">待确认</option>' + keys.map(k => `<option value="${k}">${escapeText(STUDY_SUBGROUP_LABELS[k])}</option>`).join('');
  el.value = keys.includes(selected) ? selected : '';
}

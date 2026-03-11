// API配置
const API_BASE = 'http://localhost:8000';

// Token管理
function getToken() {
  return sessionStorage.getItem('edc_token');
}

function setToken(t) {
  sessionStorage.setItem('edc_token', t);
}

function clearToken() {
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
  if (res.status === 401) {
    clearToken();
    document.getElementById('login-overlay').classList.remove('hidden');
    throw new Error('登录已过期，请重新登录');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }));
    throw new Error(err.detail || '请求失败');
  }
  return res.json();
}

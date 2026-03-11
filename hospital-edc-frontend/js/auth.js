// 登录功能
async function doLogin() {
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');
  errEl.textContent = '';
  if (!username || !password) {
    errEl.textContent = '请填写用户名和密码';
    return;
  }
  btn.disabled = true;
  btn.textContent = '登录中…';
  try {
    const form = new URLSearchParams({ username, password, grant_type: 'password' });
    const res = await fetch(API_BASE + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '登录失败' }));
      throw new Error(err.detail || '登录失败');
    }
    const data = await res.json();
    setToken(data.access_token);
    setUser(data.user);
    onLoginSuccess(data.user);
  } catch(e) {
    errEl.textContent = e.message || '网络错误，请检查服务是否启动';
  } finally {
    btn.disabled = false;
    btn.textContent = '登 录';
  }
}

function onLoginSuccess(user) {
  document.getElementById('login-overlay').classList.add('hidden');
  const name = user.full_name || user.username;
  document.getElementById('sidebar-username').textContent = name;
  loadDashboard();
}

function doLogout() {
  clearToken();
  document.getElementById('login-overlay').classList.remove('hidden');
  document.getElementById('login-username').value = '';
  document.getElementById('login-password').value = '';
  document.getElementById('login-error').textContent = '';
  toggleAuthForm('login'); // 退出后显示登录表单
}

// 表单切换
function toggleAuthForm(formType) {
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const loginError = document.getElementById('login-error');
  const registerError = document.getElementById('register-error');

  // 清空错误信息
  loginError.textContent = '';
  registerError.textContent = '';

  if (formType === 'register') {
    loginForm.style.display = 'none';
    registerForm.style.display = 'block';
    // 清空注册表单
    document.getElementById('register-username').value = '';
    document.getElementById('register-fullname').value = '';
    document.getElementById('register-password').value = '';
    document.getElementById('register-password-confirm').value = '';
    document.getElementById('register-invitation-code').value = '';
  } else {
    loginForm.style.display = 'block';
    registerForm.style.display = 'none';
  }
}

// 注册功能
async function doRegister() {
  const username = document.getElementById('register-username').value.trim();
  const fullname = document.getElementById('register-fullname').value.trim();
  const password = document.getElementById('register-password').value;
  const passwordConfirm = document.getElementById('register-password-confirm').value;
  const invitationCode = document.getElementById('register-invitation-code').value.trim();
  const errEl = document.getElementById('register-error');
  const btn = document.getElementById('register-btn');

  errEl.textContent = '';

  // 表单验证
  if (!username || !fullname || !password || !passwordConfirm || !invitationCode) {
    errEl.textContent = '请填写所有字段';
    return;
  }

  if (username.length < 3) {
    errEl.textContent = '用户名至少3个字符';
    return;
  }

  if (password.length < 6) {
    errEl.textContent = '密码至少6个字符';
    return;
  }

  if (password !== passwordConfirm) {
    errEl.textContent = '两次输入的密码不一致';
    return;
  }

  btn.disabled = true;
  btn.textContent = '注册中…';

  try {
    const res = await fetch(API_BASE + '/api/auth/register-with-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        username: username,
        password: password,
        full_name: fullname,
        invitation_code: invitationCode
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '注册失败' }));
      throw new Error(err.detail || '注册失败');
    }

    // 注册成功，自动登录
    errEl.textContent = '';
    errEl.style.color = '#10b981';
    errEl.textContent = '注册成功！正在登录...';

    // 等待1秒后自动登录
    setTimeout(async () => {
      document.getElementById('login-username').value = username;
      document.getElementById('login-password').value = password;
      toggleAuthForm('login');
      await doLogin();
    }, 1000);

  } catch(e) {
    errEl.style.color = '#ef4444';
    errEl.textContent = e.message || '网络错误，请检查服务是否启动';
  } finally {
    btn.disabled = false;
    btn.textContent = '注 册';
  }
}

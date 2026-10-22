// 数据导出页面（M3 北极星）
// 注意：导出是二进制文件（xlsx/zip），不能用统一的 api()（它返回 json），
// 这里参照 fetch + getToken() 手动带 Bearer 取 blob。
const ExportPage = {
  async init() {
    const user = getUser();
    if (!user) return;
    const deidentify = document.getElementById('export-deidentify');
    deidentify.checked = true;
    deidentify.disabled = true;
    document.getElementById('export-privacy-hint').textContent = '所有角色均使用脱敏导出';
    // 总中心可以选择中心范围
    if (user.role === 'main_admin') {
      document.getElementById('export-center-wrap').style.display = '';
      try {
        const centers = await api('GET', '/api/centers/?limit=1000');
        const list = centers.items || centers || [];
        const sel = document.getElementById('export-center');
        sel.innerHTML = list.sort((a,b) => a.center_code.localeCompare(b.center_code, undefined, {numeric:true})).map(c => `<label class="block text-sm"><input type="checkbox" value="${c.id}" data-export-center> ${escapeText(c.center_code)} ${escapeText(c.center_name)}</label>`).join('');
        this.toggleCenters();
        document.getElementById('export-btn').disabled = false;
      } catch (e) {
        document.getElementById('export-center').innerHTML = '中心列表加载失败 <button type="button" onclick="ExportPage.init()" class="text-blue-600">重试</button>';
        document.getElementById('export-btn').disabled = true;
      }
    }
  },

  toggleCenters() {
    const all = document.getElementById('export-all-centers').checked;
    document.querySelectorAll('[data-export-center]').forEach(el => { el.disabled = all; });
  },

  buildQuery() {
    const params = new URLSearchParams();
    params.set('format', document.getElementById('export-format').value);
    params.set('deidentify', 'true');
    const status = document.getElementById('export-status').value;
    if (status) params.set('status', status);
    const visitStatus = document.getElementById('export-visit-status').value;
    if (visitStatus) params.set('visit_status', visitStatus);
    if (getUser()?.role === 'main_admin' && !document.getElementById('export-all-centers').checked) {
      const selected = Array.from(document.querySelectorAll('[data-export-center]:checked'));
      if (!selected.length) throw new Error('请至少选择一家医院，或勾选全部中心');
      selected.forEach(el => params.append('selected_centers', el.value));
    }
    return params.toString();
  },

  async download() {
    const btn = document.getElementById('export-btn');
    const token = getToken();
    if (!token) {
      showToast('请先登录', 'error');
      return;
    }
    btn.disabled = true;
    const original = btn.innerHTML;
    btn.innerHTML = '<svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path></svg> 正在生成...';
    try {
      const res = await fetch(API_BASE + '/api/export/?' + this.buildQuery(), {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      if (res.status === 401) {
        clearToken();
        document.getElementById('login-overlay').classList.remove('hidden');
        throw new Error('登录已过期，请重新登录');
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '导出失败' }));
        throw new Error(err.detail || '导出失败');
      }
      const blob = await res.blob();
      if (token !== getToken()) throw new Error('账号已切换，已取消下载');

      // 从 Content-Disposition 取文件名（后端用 filename*=UTF-8'' 编码）
      const cd = res.headers.get('Content-Disposition') || '';
      let filename = 'EDC导出.xlsx';
      const m = cd.match(/filename\*=UTF-8''([^;]+)/);
      if (m) filename = decodeURIComponent(m[1]);

      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(a.href);
      a.remove();
      showToast('导出成功，文件已开始下载');
    } catch (e) {
      showToast('导出失败：' + e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = original;
    }
  }
};

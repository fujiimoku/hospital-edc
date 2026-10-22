// 应用初始化
document.addEventListener('DOMContentLoaded', function() {
  // 更新日期显示
  const now = new Date();
  const dateStr = now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short'
  });
  document.getElementById('header-date').textContent = dateStr;

  // 检查登录状态
  const token = getToken();
  const user = getUser();
  if (token && user) {
    document.getElementById('login-overlay').classList.add('hidden');
    document.getElementById('sidebar-username').textContent = user.full_name || user.username;
    if (new URLSearchParams(location.search).has('patient')) showPage('entry', document.querySelectorAll('.sidebar-item')[2]);
    else loadDashboard();
    if (typeof Notifs !== 'undefined') Notifs.startPolling();
  }
});

// ======= 仪表板 =======
const VISIT_TYPE_LABEL = { baseline: 'V1 基线', W12: 'V2 第12周', W26: 'V3 第26周', interim: '中间采集', M6: '6月', M12: '12月', M18: '18月', M24: '24月' };
const VISIT_STATUS_LABEL = { draft: '草稿', submitted: '待审核', qc_passed: '质控通过', signed: '已签名', locked: '已锁定' };

async function loadDashboard() {
  const page = document.getElementById('page-dashboard');
  if (!page) return;
  if (!getToken()) {
    page.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  // 并行拉取：汇总聚合 + 入组进度 + 访视完成率 + 最近患者
  const [summary, enrollment, completion, recent] = await Promise.all([
    api('GET', '/api/reports/summary').catch(() => null),
    api('GET', '/api/reports/enrollment').catch(() => null),
    api('GET', '/api/reports/visit-completion').catch(() => null),
    api('GET', '/api/patients/?limit=5').catch(() => null),
  ]);
  if (!summary) {
    page.innerHTML = `
      <div class="text-center text-red-500 py-20">
        <p>看板加载失败</p>
        <button onclick="loadDashboard()" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">重试</button>
      </div>`;
    return;
  }
  if (!getToken()) return;
  renderDashboardPage(summary, enrollment, completion, recent);
  WeeklyEntry.start();
}

function renderDashboardPage(summary, enrollment, completion, recent) {
  const dashboardPage = document.getElementById('page-dashboard');
  if (!dashboardPage) return;

  const visits = summary.visits_by_status || {};
  const pendingReview = (visits.submitted || 0) + (visits.qc_passed || 0);

  // 最近患者表（中心隔离，只能看到自己可访问的患者）
  const patients = (recent && recent.items) || [];
  const recentRows = patients.length ? patients.map(p => `
    <tr class="border-b border-gray-50 hover:bg-gray-50">
      <td class="px-4 py-2.5 font-mono text-sm">${p.patient_code}</td>
      <td class="px-4 py-2.5 text-sm">${p.full_name || p.name_initials || '-'}</td>
      <td class="px-4 py-2.5 text-sm">${p.gender === 'male' ? '男' : p.gender === 'female' ? '女' : '-'}</td>
      <td class="px-4 py-2.5 text-sm">${p.age ?? '-'}</td>
      <td class="px-4 py-2.5 text-sm">${p.center_code || '-'}</td>
      <td class="px-4 py-2.5 text-sm">${VISIT_STATUS_LABEL[p.latest_visit_status] || '未建访视'}</td>
      <td class="px-4 py-2.5 text-sm">${p.has_consent ? '<span class="text-green-500">已签署</span>' : '<span class="text-orange-500">未签署</span>'}</td>
    </tr>`).join('') : '<tr><td colspan="7" class="text-center text-gray-400 py-8">暂无患者，请先在「患者管理」中建档</td></tr>';

  // 入组进度（按中心，横向条形）
  const byCenter = (enrollment && enrollment.by_center) || [];
  const maxCenter = Math.max(1, ...byCenter.map(c => c.total));
  const centerBars = byCenter.length ? byCenter.map(c => `
    <div class="mb-2.5">
      <div class="flex items-center justify-between text-xs mb-1">
        <span class="text-gray-600">${c.center_code} ${c.center_name}</span>
        <span class="font-medium text-gray-800">${c.total}</span>
      </div>
      <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div class="h-full bg-blue-500 rounded-full" style="width:${Math.round(c.total / maxCenter * 100)}%"></div>
      </div>
    </div>`).join('') : '<div class="text-center text-gray-400 py-4 text-sm">暂无入组数据</div>';

  // 访视完成率
  const items = (completion && completion.items) || [];
  const completionRows = items.length ? items.map(i => `
    <tr class="border-b border-gray-50">
      <td class="px-3 py-2 text-sm">${VISIT_TYPE_LABEL[i.visit_type] || i.visit_type}</td>
      <td class="px-3 py-2 text-sm text-center">${i.total}</td>
      <td class="px-3 py-2 text-sm text-center">${i.done}</td>
      <td class="px-3 py-2 text-sm">
        <div class="flex items-center gap-2">
          <div class="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full ${i.rate >= 80 ? 'bg-green-500' : i.rate >= 40 ? 'bg-blue-500' : 'bg-orange-400'} rounded-full" style="width:${i.rate}%"></div>
          </div>
          <span class="text-xs text-gray-500 w-10 text-right">${i.rate}%</span>
        </div>
      </td>
    </tr>`).join('') : '<tr><td colspan="4" class="text-center text-gray-400 py-4 text-sm">暂无访视数据</td></tr>';

  dashboardPage.innerHTML = `
    <div class="max-w-6xl mx-auto">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div class="text-xs text-gray-400 mb-1">在研患者总数</div>
          <div class="text-3xl font-bold text-gray-800">${summary.patients_total || 0}</div>
          <div class="text-xs text-gray-400 mt-1">本月新入组 ${summary.patients_enrolled_this_month || 0}</div>
        </div>
        <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div class="text-xs text-gray-400 mb-1">访视总数</div>
          <div class="text-3xl font-bold text-blue-600">${summary.visits_total || 0}</div>
          <div class="text-xs text-gray-400 mt-1">待审核/待签名 ${pendingReview}</div>
        </div>
        <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div class="text-xs text-gray-400 mb-1">未关闭质疑</div>
          <div class="text-3xl font-bold ${summary.open_queries ? 'text-orange-500' : 'text-gray-800'}">${summary.open_queries || 0}</div>
          <div class="text-xs text-gray-400 mt-1">质控待处理</div>
        </div>
        <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <div class="text-xs text-gray-400 mb-1">不良事件</div>
          <div class="text-3xl font-bold ${summary.adverse_events_total ? 'text-red-500' : 'text-gray-800'}">${summary.adverse_events_total || 0}</div>
          <div class="text-xs text-gray-400 mt-1">累计记录</div>
        </div>
      </div>

      <div id="weekly-entry-panel" class="bg-white border rounded-xl p-5 mb-6">每周录入统计加载中…</div>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5 lg:col-span-2">
          <h3 class="text-sm font-semibold text-gray-700 mb-4">最近患者</h3>
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="text-xs text-gray-400 border-b border-gray-100">
                  <th class="px-4 py-2 text-left font-medium">患者编号</th>
                  <th class="px-4 py-2 text-left font-medium">姓名</th>
                  <th class="px-4 py-2 text-left font-medium">性别</th>
                  <th class="px-4 py-2 text-left font-medium">年龄</th>
                  <th class="px-4 py-2 text-left font-medium">中心</th>
                  <th class="px-4 py-2 text-left font-medium">最近访视</th>
                  <th class="px-4 py-2 text-left font-medium">知情同意</th>
                </tr>
              </thead>
              <tbody>${recentRows}</tbody>
            </table>
          </div>
        </div>
        <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h3 class="text-sm font-semibold text-gray-700 mb-4">各中心入组进度</h3>
          ${centerBars}
        </div>
      </div>

      <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h3 class="text-sm font-semibold text-gray-700 mb-3">访视完成率</h3>
        <table class="w-full">
          <thead>
            <tr class="text-xs text-gray-400 border-b border-gray-100">
              <th class="px-3 py-2 text-left font-medium">访视类型</th>
              <th class="px-3 py-2 text-center font-medium">已建访视</th>
              <th class="px-3 py-2 text-center font-medium">已完成</th>
              <th class="px-3 py-2 text-left font-medium">完成率</th>
            </tr>
          </thead>
          <tbody>${completionRows}</tbody>
        </table>
      </div>
    </div>
  `;
}


// Only aggregate counters refresh; patient/entry forms are never replaced by polling.
const WeeklyEntry = {
  timer: null, week: '', generation: 0,
  start() {
    this.stop();
    this.refresh();
    this.timer = setInterval(() => this.refresh(), 30000);
  },
  stop() { clearInterval(this.timer); this.timer = null; this.generation++; },
  async refresh() {
    const panel = document.getElementById('weekly-entry-panel');
    if (!panel || !getToken() || document.hidden || !document.getElementById('page-dashboard')?.classList.contains('active')) return;
    const generation = ++this.generation;
    try {
      const data = await api('GET', '/api/reports/weekly-entry' + (this.week ? '?week=' + encodeURIComponent(this.week) : ''));
      if (generation !== this.generation || !getToken()) return;
      const keys = Object.keys(data.groups);
      panel.innerHTML = `<div class="flex flex-wrap justify-between gap-3 mb-3"><h3 class="font-semibold">各分中心每周新建患者</h3>
        <label class="text-sm">选择周内任一天 <input type="date" value="${data.week_start}" onchange="WeeklyEntry.week=this.value; WeeklyEntry.refresh()" class="border rounded px-2 py-1"/></label>
        <button onclick="WeeklyEntry.week=''; WeeklyEntry.refresh()" class="text-blue-600 text-sm">本周</button>
        <button onclick="WeeklyEntry.refresh()" class="text-blue-600 text-sm">刷新</button></div>
        <p class="text-xs text-gray-500 mb-3">${data.week_start} 至 ${data.week_end} · 北京时间周一至周日 · 按患者建档时间计人数，不重复计算随访；组别按当前登记结果。每30秒刷新。</p>
        <div class="overflow-x-auto"><table class="w-full text-sm"><thead><tr><th class="text-left p-2">分中心</th>${keys.map(k=>`<th class="p-2">${escapeText(data.groups[k])}</th>`).join('')}<th class="p-2">未分组</th><th class="p-2">合计</th></tr></thead><tbody>
        ${data.items.map(c=>`<tr class="border-t"><td class="p-2">${escapeText(c.center_code)} ${escapeText(c.center_name)}</td>${keys.map(k=>`<td class="text-center p-2">${c.groups[k]}${c.subgroups?.[k] ? `<details class="text-xs mt-1"><summary>细分组</summary>${Object.entries(c.subgroups[k]).map(([sub,n])=>`<div class="py-1">${escapeText(data.subgroup_labels?.[sub] || '待确认')}：${n}</div>`).join('')}</details>` : ''}</td>`).join('')}<td class="text-center p-2">${c.unassigned}</td><td class="text-center p-2 font-semibold">${c.total}</td></tr>`).join('')}
        </tbody></table></div><div class="text-xs text-gray-500 mt-3">本周合计 ${data.total} 人 · 更新于 ${escapeText(new Date(data.generated_at).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai'}))}（北京时间）</div>`;
    } catch (e) {
      if (generation !== this.generation) return;
      panel.innerHTML = '<p class="text-orange-600">每周统计更新失败，当前数据不可用。</p><button class="text-blue-600" onclick="WeeklyEntry.refresh()">重试</button>';
    }
  },
};

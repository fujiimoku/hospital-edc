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
    loadDashboard();
  }
});

// ======= 仪表板 =======
async function loadDashboard() {
  try {
    const stats = await api('GET', '/api/patients/stats');

    // 更新统计数据
    const statTotal = document.getElementById('stat-total');
    const statEnrolled = document.getElementById('stat-enrolled');
    const statPendingEntry = document.getElementById('stat-pending-entry');
    const statPendingSign = document.getElementById('stat-pending-sign');

    if (statTotal) statTotal.textContent = stats.total || 0;
    if (statEnrolled) statEnrolled.textContent = `在研患者 ${stats.enrolled || 0}`;
    if (statPendingEntry) statPendingEntry.textContent = stats.pending_entry || 0;
    if (statPendingSign) statPendingSign.textContent = stats.pending_sign || 0;

    // 如果元素不存在，说明需要渲染仪表板页面
    if (!statTotal) {
      renderDashboardPage(stats);
    }
  } catch(e) {
    console.error('加载仪表板失败:', e);
    // 显示错误信息
    const dashboardPage = document.getElementById('page-dashboard');
    if (dashboardPage) {
      dashboardPage.innerHTML = `
        <div class="text-center text-red-500 py-20">
          <p>加载失败: ${e.message}</p>
          <button onclick="loadDashboard()" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">重试</button>
        </div>
      `;
    }
  }
}

function renderDashboardPage(stats) {
  const dashboardPage = document.getElementById('page-dashboard');
  if (!dashboardPage) return;

  dashboardPage.innerHTML = `
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div class="text-xs text-gray-400 mb-1">患者总数</div>
        <div id="stat-total" class="text-3xl font-bold text-gray-800">${stats.total || 0}</div>
        <div id="stat-enrolled" class="text-xs text-green-500 mt-1">在研患者 ${stats.enrolled || 0}</div>
      </div>
      <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div class="text-xs text-gray-400 mb-1">待完成表单</div>
        <div id="stat-pending-entry" class="text-3xl font-bold text-orange-500">${stats.pending_entry || 0}</div>
        <div class="text-xs text-gray-400 mt-1">需要录入</div>
      </div>
      <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div class="text-xs text-gray-400 mb-1">待签名表单</div>
        <div id="stat-pending-sign" class="text-3xl font-bold text-blue-600">${stats.pending_sign || 0}</div>
        <div class="text-xs text-gray-400 mt-1">待研究者确认</div>
      </div>
      <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div class="text-xs text-gray-400 mb-1">数据库状态</div>
        <div class="text-3xl font-bold text-green-600">✓</div>
        <div class="text-xs text-gray-400 mt-1">连接正常</div>
      </div>
    </div>
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">最近患者</h3>
      <div class="text-center text-gray-400 py-8">暂无数据</div>
    </div>
  `;
}

// ======= 数据录入 =======
async function loadEntry() {
  const entryPage = document.getElementById('page-entry');
  if (!entryPage) return;

  entryPage.innerHTML = `
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">数据录入</h3>
      <div class="text-center text-gray-400 py-20">
        <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
        </svg>
        <p>功能开发中...</p>
      </div>
    </div>
  `;
}

// ======= 知情同意 =======
async function loadConsent() {
  const consentPage = document.getElementById('page-consent');
  if (!consentPage) return;

  consentPage.innerHTML = `
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">知情同意书管理</h3>
      <div class="text-center text-gray-400 py-20">
        <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
        </svg>
        <p>功能开发中...</p>
      </div>
    </div>
  `;
}

// ======= 已录入患者 =======
async function loadRecordedPatients() {
  const recordedPage = document.getElementById('page-recorded');
  if (!recordedPage) return;

  recordedPage.innerHTML = `
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h3 class="text-lg font-semibold text-gray-800 mb-4">已录入患者</h3>
      <div class="text-center text-gray-400 py-20">
        <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
        </svg>
        <p>功能开发中...</p>
      </div>
    </div>
  `;
}

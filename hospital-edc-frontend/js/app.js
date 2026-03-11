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

// ======= 患者管理 =======
let patientSearchTimer = null;

async function loadPatients(search = '') {
  try {
    const params = search ? `?search=${encodeURIComponent(search)}` : '';
    const data = await api('GET', `/api/patients/${params}`);
    renderPatientTable(data.items || [], data.total || 0);
  } catch(e) {
    console.error('加载患者列表失败:', e);
    const patientsPage = document.getElementById('page-patients');
    if (patientsPage) {
      patientsPage.innerHTML = `
        <div class="text-center text-red-500 py-20">
          <p>加载失败: ${e.message}</p>
          <button onclick="loadPatients()" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">重试</button>
        </div>
      `;
    }
  }
}

function renderPatientTable(items, total) {
  const patientsPage = document.getElementById('page-patients');
  if (!patientsPage) return;

  patientsPage.innerHTML = `
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm">
      <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h3 class="text-lg font-semibold text-gray-800">患者列表</h3>
        <div class="flex items-center gap-3">
          <input
            type="text"
            placeholder="搜索患者..."
            class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm"
            oninput="onPatientSearch(this.value)"
          />
          <button class="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            新增患者
          </button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-gray-50 border-b border-gray-100">
            <tr>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">患者编号</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">姓名</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">性别</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">年龄</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">联系电话</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">状态</th>
              <th class="px-5 py-3 text-left text-xs font-semibold text-gray-600">创建时间</th>
            </tr>
          </thead>
          <tbody id="patient-tbody">
            ${items.length === 0 ?
              '<tr><td colspan="7" class="px-5 py-8 text-center text-gray-400">暂无患者数据</td></tr>' :
              items.map(p => `
                <tr class="hover:bg-gray-50 cursor-pointer border-b border-gray-50" onclick="selectPatient(${p.id})">
                  <td class="px-5 py-3 text-sm">${p.patient_id || '-'}</td>
                  <td class="px-5 py-3 text-sm">${p.name || '-'}</td>
                  <td class="px-5 py-3 text-sm">${p.gender === 'male' ? '男' : p.gender === 'female' ? '女' : '-'}</td>
                  <td class="px-5 py-3 text-sm">${p.age || '-'}</td>
                  <td class="px-5 py-3 text-sm">${p.phone || '-'}</td>
                  <td class="px-5 py-3 text-sm">
                    <span class="px-2 py-1 rounded text-xs ${
                      p.status === 'enrolled' ? 'bg-green-100 text-green-700' :
                      p.status === 'screening' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-700'
                    }">
                      ${p.status === 'enrolled' ? '在研' : p.status === 'screening' ? '筛选中' : '已完成'}
                    </span>
                  </td>
                  <td class="px-5 py-3 text-sm text-gray-400">${p.created_at ? new Date(p.created_at).toLocaleDateString() : '-'}</td>
                </tr>
              `).join('')
            }
          </tbody>
        </table>
      </div>
      <div class="px-6 py-4 border-t border-gray-100 text-sm text-gray-500">
        共 ${total} 条记录
      </div>
    </div>
  `;
}

function onPatientSearch(val) {
  clearTimeout(patientSearchTimer);
  patientSearchTimer = setTimeout(() => loadPatients(val), 300);
}

async function selectPatient(id) {
  console.log('选择患者:', id);
  // TODO: 实现患者详情查看
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

// 页面导航
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.getElementById('page-' + name).classList.add('fade-in');
  document.querySelectorAll('.sidebar-item').forEach(s => {
    s.classList.remove('active','text-white');
    s.style.color='';
  });
  if(el) {
    el.classList.add('active');
    el.style.color='white';
  }
  const titles = {
    dashboard:'概况',
    patients:'患者管理',
    entry:'数据录入',
    consent:'知情同意书',
    recorded:'已录入患者',
    review:'质控审计',
    export:'数据导出'
  };
  document.getElementById('page-title').textContent = titles[name] || name;

  // 加载对应页面数据
  if (name === 'patients') {
    loadPatientsPage();
  }
  if (name === 'dashboard') loadDashboard();
  if (name === 'consent') loadConsent();
  if (name === 'recorded') loadRecordedPatients();
  if (name === 'review') loadReview();
  if (name === 'entry') loadEntry();
  if (name === 'export') loadExport();
}

// 加载患者管理页面
async function loadPatientsPage() {
  const pageEl = document.getElementById('page-patients');

  // 检查是否已登录
  if (!getToken()) {
    pageEl.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  if (!pageEl.hasAttribute('data-loaded')) {
    try {
      const response = await fetch('pages/patients.html?v=20260912a');
      const html = await response.text();
      pageEl.innerHTML = html;
      pageEl.setAttribute('data-loaded', 'true');
    } catch (e) {
      console.error('加载页面失败:', e);
      pageEl.innerHTML = '<div class="text-center text-red-400 py-20">页面加载失败: ' + e.message + '</div>';
      return;
    }
  }

  // 加载患者数据
  loadPatients();
}

// 加载数据录入页面
async function loadEntry() {
  const pageEl = document.getElementById('page-entry');

  // 检查是否已登录
  if (!getToken()) {
    pageEl.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  if (!pageEl.hasAttribute('data-loaded')) {
    try {
      const response = await fetch('pages/visit-entry.html?v=20260912a');
      const html = await response.text();
      pageEl.innerHTML = html;
      pageEl.setAttribute('data-loaded', 'true');

      // 初始化数据录入模块
      if (typeof VisitEntry !== 'undefined') {
        VisitEntry.init();
      }
    } catch (e) {
      console.error('加载页面失败:', e);
      pageEl.innerHTML = '<div class="text-center text-red-400 py-20">页面加载失败: ' + e.message + '</div>';
      return;
    }
  } else if (typeof VisitEntry !== 'undefined') {
    // 已加载过：每次进入都按 sessionStorage 的当前患者重新加载，
    // 避免残留上一个患者/草稿（不同患者共用同一草稿的问题根源）
    VisitEntry.loadCurrentPatient();
  }
}

// 加载知情同意页面
async function loadConsent() {
  const pageEl = document.getElementById('page-consent');

  if (!getToken()) {
    pageEl.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  if (!pageEl.hasAttribute('data-loaded')) {
    try {
      const response = await fetch('pages/consent.html?v=20260912a');
      pageEl.innerHTML = await response.text();
      pageEl.setAttribute('data-loaded', 'true');
      if (typeof ConsentPage !== 'undefined') {
        ConsentPage.init();
      }
    } catch (e) {
      pageEl.innerHTML = '<div class="text-center text-red-400 py-20">页面加载失败: ' + e.message + '</div>';
    }
  }
}

// 加载已录入患者页面
async function loadRecordedPatients() {
  const pageEl = document.getElementById('page-recorded');

  if (!getToken()) {
    pageEl.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  if (!pageEl.hasAttribute('data-loaded')) {
    try {
      const response = await fetch('pages/recorded.html?v=20260912a');
      pageEl.innerHTML = await response.text();
      pageEl.setAttribute('data-loaded', 'true');
    } catch (e) {
      pageEl.innerHTML = '<div class="text-center text-red-400 py-20">页面加载失败: ' + e.message + '</div>';
      return;
    }
  }
  if (typeof RecordedPage !== 'undefined') {
    RecordedPage.init();
  }
}

// 加载质控审计页面
async function loadReview() {
  const pageEl = document.getElementById('page-review');

  if (!getToken()) {
    pageEl.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  if (!pageEl.hasAttribute('data-loaded')) {
    try {
      const response = await fetch('pages/review.html?v=20260912a');
      const html = await response.text();
      pageEl.innerHTML = html;
      pageEl.setAttribute('data-loaded', 'true');
    } catch (e) {
      console.error('加载页面失败:', e);
      pageEl.innerHTML = '<div class="text-center text-red-400 py-20">页面加载失败: ' + e.message + '</div>';
      return;
    }
  }
  if (typeof ReviewPage !== 'undefined') {
    ReviewPage.init();
  }
}

// 加载数据导出页面
async function loadExport() {
  const pageEl = document.getElementById('page-export');

  if (!getToken()) {
    pageEl.innerHTML = '<div class="text-center text-gray-400 py-20">请先登录</div>';
    return;
  }

  if (!pageEl.hasAttribute('data-loaded')) {
    try {
      const response = await fetch('pages/export.html?v=20260912a');
      const html = await response.text();
      pageEl.innerHTML = html;
      pageEl.setAttribute('data-loaded', 'true');
      if (typeof ExportPage !== 'undefined') {
        ExportPage.init();
      }
    } catch (e) {
      console.error('加载页面失败:', e);
      pageEl.innerHTML = '<div class="text-center text-red-400 py-20">页面加载失败: ' + e.message + '</div>';
    }
  }
}

// 标签页切换
function switchTab(name, el) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.remove('hidden');
  el.classList.add('active');
}

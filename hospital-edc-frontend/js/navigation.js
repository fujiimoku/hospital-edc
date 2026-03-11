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
    recorded:'已录入患者'
  };
  document.getElementById('page-title').textContent = titles[name] || name;

  // 加载对应页面数据
  if (name === 'patients') loadPatients();
  if (name === 'dashboard') loadDashboard();
  if (name === 'consent') loadConsent();
  if (name === 'recorded') loadRecordedPatients();
  if (name === 'entry') loadEntry();
}

// 标签页切换
function switchTab(name, el) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.remove('hidden');
  el.classList.add('active');
}

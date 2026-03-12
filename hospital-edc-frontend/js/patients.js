// 患者管理模块

// 全局变量
let patientCacheById = Object.create(null);
let patientSearchTimer = null;

// 常量定义
const genderLabel = { male: '男', female: '女' };
const statusColorApi = {
  enrolled: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  withdrawn: 'bg-gray-100 text-gray-500',
};
const statusLabelApi = { enrolled: '在研', completed: '已完成', withdrawn: '已退出' };

// 加载患者列表
async function loadPatients(search) {
  const tbody = document.getElementById('patient-table');
  if (!tbody) {
    console.error('患者表格元素未找到');
    return;
  }

  tbody.innerHTML = '<tr><td colspan="8" class="px-5 py-6 text-center text-gray-400">加载中…</td></tr>';

  try {
    const q = search ? '?search=' + encodeURIComponent(search) + '&limit=50' : '?limit=50';
    // 确保URL以斜杠结尾，避免307重定向
    const data = await api('GET', '/api/patients/' + q);
    if (!data) return;
    renderPatientTable(data.items, data.total);
  } catch(e) {
    console.error('加载患者失败:', e);
    tbody.innerHTML = '<tr><td colspan="8" class="px-5 py-6 text-center text-red-400">加载失败: ' + e.message + '</td></tr>';
  }
}

// 渲染患者表格
function renderPatientTable(items, total) {
  const tbody = document.getElementById('patient-table');
  const footer = document.getElementById('patient-list-footer');
  const title = document.getElementById('patient-list-title');

  if (!tbody || !footer || !title) {
    console.error('患者表格元素未找到');
    return;
  }

  title.textContent = '患者列表（' + total + '）';
  footer.textContent = '共 ' + total + ' 条，显示 ' + items.length + ' 条';
  patientCacheById = Object.create(null);

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="px-5 py-8 text-center text-gray-400">暂无患者数据</td></tr>';
    return;
  }

  tbody.innerHTML = items.map(p => {
    patientCacheById[p.id] = p;
    const gender = genderLabel[p.gender] || p.gender;
    const statusCls = statusColorApi[p.status] || 'bg-gray-100 text-gray-500';
    const statusTxt = statusLabelApi[p.status] || p.status || '未知';
    const enroll = p.enrollment_date ? p.enrollment_date.slice(0,10) : '—';
    const locked = !!p.has_submitted;
    const btnCls = locked ? 'text-gray-300 text-xs cursor-not-allowed' : 'text-blue-500 text-xs hover:underline';
    const btnAttr = locked
      ? 'disabled title="该患者已提交，请到【已录入患者】管理界面更改"'
      : `onclick="selectPatient(${p.id})"`;
    return `<tr class="hover:bg-blue-50/40 cursor-pointer border-t border-gray-50">
      <td class="px-5 py-3 font-mono text-blue-600 text-sm">${p.patient_code}</td>
      <td class="px-4 py-3 text-sm">${p.name_initials || '—'}</td>
      <td class="px-4 py-3 text-sm">${gender}</td>
      <td class="px-4 py-3 text-sm">${p.age || '—'}</td>
      <td class="px-4 py-3 text-sm">${enroll}</td>
      <td class="px-4 py-3 text-xs text-gray-500">—</td>
      <td class="px-4 py-3"><span class="score-badge ${statusCls}">${statusTxt}</span></td>
      <td class="px-4 py-3"><button ${btnAttr} class="${btnCls}">录入</button></td>
    </tr>`;
  }).join('');
}

// 搜索患者
function onPatientSearch(val) {
  clearTimeout(patientSearchTimer);
  patientSearchTimer = setTimeout(() => loadPatients(val), 350);
}

// 选择患者进入录入页
async function selectPatient(id) {
  // 暂时只是跳转，后续会实现完整的录入功能
  console.log('选择患者:', id);
  alert('患者录入功能正在开发中，患者ID: ' + id);
}

// 打开创建患者模态框
function openCreatePatientModal() {
  document.getElementById('modal-create-patient').classList.remove('hidden');
  document.getElementById('cp-initials').focus();
}

// 关闭创建患者模态框
function closeCreatePatientModal() {
  document.getElementById('modal-create-patient').classList.add('hidden');
  document.getElementById('cp-error').textContent = '';
  // 清空表单
  document.getElementById('cp-initials').value = '';
  document.getElementById('cp-gender').value = '';
  document.getElementById('cp-age').value = '';
  document.getElementById('cp-enroll').value = '';
}

// 提交创建患者
async function submitCreatePatient() {
  const errEl = document.getElementById('cp-error');
  const btn = document.getElementById('cp-submit-btn');
  errEl.textContent = '';
  const initials = document.getElementById('cp-initials').value.trim();
  const gender = document.getElementById('cp-gender').value;
  const age = document.getElementById('cp-age').value;
  const enroll = document.getElementById('cp-enroll').value;

  if (!initials) {
    errEl.textContent = '请填写姓名首字母';
    return;
  }
  if (!gender) {
    errEl.textContent = '请选择性别';
    return;
  }

  btn.disabled = true;
  btn.textContent = '创建中…';

  try {
    const payload = {
      name_initials: initials,
      gender,
      age: age ? parseInt(age) : null,
      enrollment_date: enroll || null,
      center_code: 'CHN-017',
    };
    const p = await api('POST', '/api/patients/', payload);
    if (!p) return;
    closeCreatePatientModal();
    showToast('✓ 患者 ' + p.patient_code + ' 创建成功');
    loadPatients();
    // 自动跳转录入页
    setTimeout(() => selectPatient(p.id), 300);
  } catch(e) {
    errEl.textContent = e.message || '创建失败';
  } finally {
    btn.disabled = false;
    btn.textContent = '创建患者';
  }
}

// Toast提示函数
function showToast(message) {
  // 创建toast元素
  const toast = document.createElement('div');
  toast.className = 'fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50';
  toast.textContent = message;
  document.body.appendChild(toast);

  // 3秒后自动消失
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

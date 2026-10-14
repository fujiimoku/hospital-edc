// 患者管理模块

// 全局变量
let patientCacheById = Object.create(null);
let patientSearchTimer = null;

const PatientImages = {
  patientId: null, generation: 0, busy: false,
  async open(id) {
    if (this.busy) return;
    this.patientId = id;
    const generation = ++this.generation;
    document.getElementById('patient-images-modal')?.remove();
    const patient = patientCacheById[id];
    const modal = document.createElement('div');
    modal.id = 'patient-images-modal';
    modal.className = 'fixed inset-0 bg-black/40 z-50 flex items-center justify-center';
    modal.innerHTML = `<div class="bg-white rounded-xl p-6 w-full max-w-2xl max-h-screen overflow-auto">
      <div class="flex justify-between"><h3 class="font-semibold">医疗费用图片 · ${escapeText(patient.patient_code)} · ${escapeText(patient.full_name || patient.name_initials)}</h3>
      <button onclick="PatientImages.close()" aria-label="关闭图片">关闭</button></div>
      <p class="text-xs text-gray-500 my-3">图片仅归档，不自动计算费用。支持 JPG、PNG、WebP，每张最多15MB。下载文件以组别和患者姓名开头，附编号与图片序号；未填写姓名时使用首字母。</p>
      <input id="patient-images-files" type="file" multiple accept="image/jpeg,image/png,image/webp" class="my-2"/>
      <button id="patient-images-upload" onclick="PatientImages.upload()" class="text-blue-600 p-2">上传所选图片</button>
      <button id="patient-images-archive" onclick="PatientImages.download('archive')" class="text-blue-600 p-2" disabled>全部打包下载</button>
      <p id="patient-images-status" role="status" class="text-sm my-2"></p>
      <div id="patient-images-list">加载中…</div></div>`;
    document.body.appendChild(modal);
    await this.refresh(id, generation);
  },
  close() {
    if (this.busy) { this.status('正在处理图片，请稍候再关闭'); return; }
    this.generation++;
    this.patientId = null;
    document.getElementById('patient-images-modal')?.remove();
  },
  status(message) { const el = document.getElementById('patient-images-status'); if (el) el.textContent = message; },
  async refresh(id = this.patientId, generation = this.generation) {
    try {
      const data = await api('GET', `/api/patients/${id}/images`);
      if (generation !== this.generation) return;
      document.getElementById('patient-images-list').innerHTML = data.items.length ? data.items.map(item =>
        `<div class="border-t py-3 flex justify-between gap-3"><span>${escapeText(item.filename)}<small class="block text-gray-500">${(item.size_bytes / 1024 / 1024).toFixed(2)} MB · ${escapeText(item.created_at || '')}</small></span><button class="text-blue-600" onclick="PatientImages.download('${item.id}/download')">下载</button></div>`).join('') : '尚未上传图片';
      document.getElementById('patient-images-archive').disabled = !data.items.length;
    } catch (error) { if (generation === this.generation) this.status(error.message); }
  },
  async request(path, options = {}) {
    const response = await fetch(API_BASE + path, {...options, headers: {Authorization: `Bearer ${getToken()}`}});
    if (response.status === 401) { clearToken(); throw new Error('登录已过期，请重新登录'); }
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === 'string' ? error.detail : `图片操作失败（${response.status}）`);
    }
    return response;
  },
  async upload() {
    if (this.busy) return;
    const input = document.getElementById('patient-images-files');
    const files = Array.from(input.files);
    if (!files.length) { this.status('请先选择图片'); return; }
    if (files.some(f => f.size > 15 * 1024 * 1024)) { this.status('每张图片不能超过15MB，请重新选择'); return; }
    const id = this.patientId;
    this.busy = true;
    input.disabled = true;
    let completed = 0;
    try {
      for (const file of files) {
        this.status(`正在上传 ${completed + 1}/${files.length}…`);
        const form = new FormData(); form.append('file', file);
        await this.request(`/api/patients/${id}/images`, {method: 'POST', body: form});
        completed++;
      }
      this.status(`已上传 ${completed} 张图片`);
      input.value = '';
    } catch (error) {
      this.status(`已成功上传 ${completed} 张；${error.message}。请仅重新选择未成功的图片。`);
      input.value = '';
    } finally {
      this.busy = false; input.disabled = false;
      await this.refresh(id);
    }
  },
  async download(suffix) {
    if (this.busy) return;
    this.busy = true; this.status('正在准备下载…');
    try {
      const response = await this.request(`/api/patients/${this.patientId}/images/${suffix}`);
      const disposition = response.headers.get('Content-Disposition') || '';
      const encoded = disposition.match(/filename\*=utf-8''([^;]+)/i);
      const plain = disposition.match(/filename="([^"]+)"/i);
      const name = encoded ? decodeURIComponent(encoded[1]) : plain?.[1];
      if (!name) throw new Error('下载文件名缺失，请联系管理员');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = name;
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      this.status('已开始下载');
    } catch (error) { this.status(error.message); }
    finally { this.busy = false; }
  },
};

// 常量定义
const genderLabel = { male: '男', female: '女' };
const statusColorApi = {
  enrolled: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  dropout: 'bg-orange-100 text-orange-700',
  withdrawn: 'bg-gray-100 text-gray-500',
};
const statusLabelApi = { enrolled: '在研', completed: '已完成', dropout: '已脱落', withdrawn: '已退出' };

// 加载患者列表
async function loadPatients(search) {
  const tbody = document.getElementById('patient-table');
  if (!tbody) {
    console.error('患者表格元素未找到');
    return;
  }

  tbody.innerHTML = '<tr><td colspan="9" class="px-5 py-6 text-center text-gray-400">加载中…</td></tr>';

  try {
    const q = search ? '?search=' + encodeURIComponent(search) + '&limit=50' : '?limit=50';
    // 确保URL以斜杠结尾，避免307重定向
    const data = await api('GET', '/api/patients/' + q);
    if (!data) return;
    renderPatientTable(data.items, data.total);
  } catch(e) {
    console.error('加载患者失败:', e);
    tbody.innerHTML = '<tr><td colspan="9" class="px-5 py-6 text-center text-red-400">加载失败: ' + e.message + '</td></tr>';
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
    tbody.innerHTML = '<tr><td colspan="9" class="px-5 py-8 text-center text-gray-400">暂无患者数据</td></tr>';
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
      <td class="px-4 py-3 text-xs text-gray-500">${STUDY_GROUP_LABELS[p.study_group] || '未分组'}<div>${escapeText(STUDY_SUBGROUP_LABELS[p.study_subgroup] || '细分组待确认')}</div></td>
      <td class="px-4 py-3"><span class="score-badge ${statusCls}">${statusTxt}</span></td>
      <td class="px-4 py-3">${['main_admin','center_admin','researcher'].includes(getUser()?.role) ? `<button onclick="PatientImages.open(${p.id})" class="text-blue-600 text-xs">图片</button>` : '—'}</td>
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
  const patient = patientCacheById[id];
  if (!patient) {
    console.error('患者不存在:', id);
    return;
  }

  // 保存当前选择的患者到sessionStorage。
  // 录入页每次进入都会据此重新加载该患者的访视列表和草稿（见 navigation.js 的 loadEntry）
  sessionStorage.setItem('currentPatient', JSON.stringify(patient));

  // 跳转到数据录入页面
  showPage('entry', document.querySelectorAll('.sidebar-item')[2]);
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
  ['cp-initials', 'cp-fullname', 'cp-idcard', 'cp-phone', 'cp-gender', 'cp-age', 'cp-marital', 'cp-enroll', 'cp-group', 'cp-subgroup'].forEach(id => {
    document.getElementById(id).value = '';
  });
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
  const fullName = document.getElementById('cp-fullname').value.trim();
  const idCard = document.getElementById('cp-idcard').value.trim();
  const phone = document.getElementById('cp-phone').value.trim();
  const marital = document.getElementById('cp-marital').value;

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
      study_group: document.getElementById('cp-group').value || null,
      study_subgroup: document.getElementById('cp-subgroup').value || null,
      name_initials: initials,
      gender,
      age: age ? parseInt(age) : null,
      enrollment_date: enroll || null,
    };
    if (fullName) payload.full_name = fullName;
    if (idCard) payload.id_card = idCard;
    if (phone) payload.phone = phone;
    if (marital) payload.marital_status = parseInt(marital);
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
function showToast(message, type = 'success') {
  // 创建toast元素
  const toast = document.createElement('div');
  const cls = type === 'error' ? 'bg-red-500' : 'bg-green-500';
  toast.className = `fixed top-4 right-4 ${cls} text-white px-4 py-2 rounded-lg shadow-lg z-50`;
  toast.textContent = message;
  document.body.appendChild(toast);

  // 3秒后自动消失
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

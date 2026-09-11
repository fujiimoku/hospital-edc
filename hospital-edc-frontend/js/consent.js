// 知情同意页
const ConsentPage = {
  _patients: [],

  async init() {
    if (!getToken()) return;
    try {
      const r = await api('GET', '/api/patients/?limit=200');
      this._patients = r.items || [];
      const sel = document.getElementById('cs-patient-select');
      sel.innerHTML = '<option value="">— 请选择患者 —</option>' +
        this._patients.map(p =>
          `<option value="${p.id}">${p.patient_code}（${p.full_name || p.name_initials || '未命名'}）</option>`
        ).join('');
    } catch (e) {
      document.getElementById('cs-patient-select').innerHTML =
        `<option value="">患者列表加载失败：${e.message}</option>`;
    }
  },

  currentPatientId() {
    return document.getElementById('cs-patient-select').value || null;
  },

  onPatientSelect() {
    const id = this.currentPatientId();
    const p = this._patients.find(x => x.id === Number(id));
    const infoEl = document.getElementById('consent-patient-info');
    const codeEl = document.getElementById('cs-subject-code');
    if (p) {
      infoEl.textContent = `${p.patient_code} | ${p.gender === 'male' ? '男' : '女'} | ${p.age ?? '-'}岁 | ${p.center_code || '-'}`;
      codeEl.value = p.patient_code;
      this.loadRecord(p.id);
    } else {
      infoEl.textContent = '请选择患者';
      codeEl.value = '';
    }
  },

  async loadRecord(patientId) {
    // 清空表单后回填已有记录（404 = 无记录，静默）
    this._clearForm();
    try {
      const data = await api('GET', '/api/consent/' + patientId);
      this._populate(data);
    } catch (e) { /* 无记录 */ }
  },

  _clearForm() {
    ['cs-version', 'cs-subject-contact', 'cs-subject-date', 'cs-proxy-name', 'cs-proxy-contact',
     'cs-proxy-date', 'cs-witness-name', 'cs-witness-contact', 'cs-witness-date',
     'cs-inv-name', 'cs-inv-contact', 'cs-inv-date', 'upload-filename'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    const badge = document.getElementById('consent-status-badge');
    if (badge) badge.classList.add('hidden');
    const info = document.getElementById('cs-uploaded-info');
    if (info) info.classList.add('hidden');
  },

  _populate(data) {
    const setV = (id, val) => {
      const el = document.getElementById(id);
      if (el && val) el.value = typeof val === 'string' && val.length === 10 && val[4] === '-' ? val.slice(0, 10) : val;
    };
    setV('cs-version', data.consent_version);
    setV('cs-subject-contact', data.subject_contact);
    setV('cs-subject-date', data.subject_signed_date);
    setV('cs-proxy-name', data.proxy_name);
    setV('cs-proxy-contact', data.proxy_contact);
    setV('cs-proxy-date', data.proxy_signed_date);
    setV('cs-witness-name', data.witness_name);
    setV('cs-witness-contact', data.witness_contact);
    setV('cs-witness-date', data.witness_signed_date);
    setV('cs-inv-name', data.investigator_name);
    setV('cs-inv-contact', data.investigator_contact);
    setV('cs-inv-date', data.investigator_signed_date);
    if (data.scan_file_path) {
      const fname = data.scan_file_path.split(/[\\/]/).pop();
      const ts = data.scan_uploaded_at ? new Date(data.scan_uploaded_at).toLocaleString('zh-CN') : '';
      const txt = document.getElementById('cs-uploaded-text');
      const info = document.getElementById('cs-uploaded-info');
      if (txt) txt.textContent = '已上传：' + fname + (ts ? '（' + ts + '）' : '');
      if (info) info.classList.remove('hidden');
    }
    if (data.subject_signed_date) {
      const badge = document.getElementById('consent-status-badge');
      if (badge) badge.classList.remove('hidden');
    }
  },

  async submit() {
    const errEl = document.getElementById('cs-error');
    const btn = document.getElementById('cs-submit-btn');
    errEl.textContent = '';
    const patientId = this.currentPatientId();
    if (!patientId) { errEl.textContent = '请先选择患者'; return; }
    const subjectDate = document.getElementById('cs-subject-date').value;
    if (!subjectDate) { errEl.textContent = '知情同意日期为必填项'; return; }

    btn.disabled = true; btn.textContent = '保存中…';
    try {
      const fd = new FormData();
      fd.append('subject_signed_date', subjectDate);
      const appendIfVal = (key, id) => {
        const el = document.getElementById(id);
        if (el && el.value.trim()) fd.append(key, el.value.trim());
      };
      appendIfVal('consent_version', 'cs-version');
      appendIfVal('subject_contact', 'cs-subject-contact');
      appendIfVal('proxy_name', 'cs-proxy-name');
      appendIfVal('proxy_contact', 'cs-proxy-contact');
      appendIfVal('proxy_signed_date', 'cs-proxy-date');
      appendIfVal('witness_name', 'cs-witness-name');
      appendIfVal('witness_contact', 'cs-witness-contact');
      appendIfVal('witness_signed_date', 'cs-witness-date');
      appendIfVal('investigator_name', 'cs-inv-name');
      appendIfVal('investigator_contact', 'cs-inv-contact');
      appendIfVal('investigator_signed_date', 'cs-inv-date');

      const fileInput = document.getElementById('cs-file-input');
      if (fileInput && fileInput.files.length > 0) {
        const file = fileInput.files[0];
        if (file.size > 10 * 1024 * 1024) { errEl.textContent = '文件大小不能超过 10MB'; return; }
        fd.append('scan_file', file);
      }

      const token = getToken();
      const res = await fetch(API_BASE + '/api/consent/' + patientId, {
        method: 'POST',
        headers: token ? { 'Authorization': 'Bearer ' + token } : {},
        body: fd,  // 不设 Content-Type，浏览器自动带 multipart boundary
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || '保存失败');
      }
      const data = await res.json();
      this._populate(data);
      showToast('知情同意记录已保存');
    } catch (e) {
      errEl.textContent = e.message || '保存失败';
    } finally {
      btn.disabled = false;
      btn.textContent = '确认并保存';
    }
  }
};

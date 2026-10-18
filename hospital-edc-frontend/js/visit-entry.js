// 访视数据录入模块
// 所有 API 调用统一走 js/config.js 的 api()（API_BASE + getToken()）
const VisitEntry = {
  currentVisit: null,
  currentPatient: null,
  _autosaveTimer: null,
  _patientGeneration: 0,
  _visitGeneration: 0,

  // 初始化
  init() {
    this.setupEventListeners();
    this.setupPageSaveButtons();
    this.initializeQuestions();
    this.loadCurrentPatient();
  },

  setupPageSaveButtons() {
    document.querySelectorAll('#entry-form-area .tab-panel').forEach(panel => {
      if (panel.querySelector('[data-page-save]')) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.pageSave = '1';
      button.className = 'mt-4 bg-blue-600 text-white rounded px-4 py-2';
      button.textContent = '保存草稿并继续填写';
      button.onclick = () => saveVisitData('draft');
      panel.appendChild(button);
    });
  },

  async loadCostPhotos() {
    const visitId = this.currentVisit?.id;
    const patientId = this.currentPatient?.id;
    if (!visitId || !patientId) return;
    const box = document.getElementById('cost-photo-list');
    if (!box) return;
    box.textContent = '正在加载照片…';
    try {
      const result = await api('GET', `/api/patients/${patientId}/images?visit_id=${visitId}`);
      if (this.currentVisit?.id !== visitId || this.currentPatient?.id !== patientId) return;
      box.innerHTML = (result.items || []).map(item => `<div>${escapeText(item.filename)} <button type="button" data-photo-download onclick="VisitEntry.downloadCostPhoto(${item.id})" class="text-blue-600">下载照片</button></div>`).join('') || '本次访视尚未上传费用照片';
    } catch (e) { box.textContent = '照片加载失败：' + e.message; }
  },

  async uploadCostPhotos() {
    if (this.currentVisit?.status !== 'draft' || this._uploadingPhotos) return;
    const input = document.getElementById('cost-photo-files');
    const files = Array.from(input.files || []);
    if (!files.length) { showToast('请先选择费用照片', 'error'); return; }
    const visitId = this.currentVisit.id;
    const patientId = this.currentPatient.id;
    this._uploadingPhotos = true;
    let count = 0;
    try {
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        const response = await fetch(API_BASE + `/api/patients/${patientId}/images?visit_id=${visitId}`, {
          method: 'POST', headers: {Authorization: `Bearer ${getToken()}`}, body: form,
        });
        if (!response.ok) throw new Error((await response.json()).detail || '上传失败');
        count++;
      }
      if (this.currentVisit?.id === visitId && this.currentPatient?.id === patientId) input.value = '';
      showToast('费用照片已保存，金额可留空');
    } catch (e) { showToast(`已上传 ${count} 张；${e.message}`, 'error'); }
    finally {
      this._uploadingPhotos = false;
      if (this.currentVisit?.id === visitId && this.currentPatient?.id === patientId) {
        document.getElementById('cost-photo-status').textContent = `本次成功上传 ${count} 张照片`;
        await this.loadCostPhotos();
      }
    }
  },

  async downloadCostPhoto(imageId) {
    try {
      const response = await fetch(API_BASE + `/api/patients/${this.currentPatient.id}/images/${imageId}/download`, {headers: {Authorization: `Bearer ${getToken()}`}});
      if (!response.ok) throw new Error('下载失败');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = decodeURIComponent(response.headers.get('Content-Disposition')?.split("filename*=utf-8''")[1] || '费用照片');
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { showToast(e.message, 'error'); }
  },

  // 加载当前患者
  async loadCurrentPatient() {
    const generation = ++this._patientGeneration;
    this.stopAutosave();
    if (this._saveQueue) await this._saveQueue;
    if (generation !== this._patientGeneration) return;
    const patientData = sessionStorage.getItem('currentPatient');
    if (patientData) {
      this.currentPatient = JSON.parse(patientData);
      this.updatePatientInfo();
      this.loadPatientVisits();
    } else {
      // 未选择患者：清空残留状态，避免显示/自动保存上一个患者的草稿
      this.currentPatient = null;
      this.resetEntryState();
      const codeEl = document.getElementById('entry-patient-code');
      const infoEl = document.getElementById('entry-patient-info');
      if (codeEl) codeEl.textContent = '未选择';
      if (infoEl) infoEl.textContent = '请在患者管理点击患者编号或“查看／录入”';
    }
  },

  // 更新患者信息显示
  updatePatientInfo() {
    if (!this.currentPatient) return;

    const codeEl = document.getElementById('entry-patient-code');
    const infoEl = document.getElementById('entry-patient-info');

    if (codeEl) {
      codeEl.textContent = this.currentPatient.patient_code;
    }
    if (infoEl) {
      const genderLabel = { male: '男', female: '女' };
      const gender = genderLabel[this.currentPatient.gender] || this.currentPatient.gender;
      infoEl.textContent = `${this.currentPatient.name_initials || ''} / ${gender} / ${this.currentPatient.age || '—'}岁`;
    }
  },

  // 重置录入页状态（切换患者/未选择患者时，清除上一个患者/访视的残留数据）
  resetEntryState() {
    ++this._visitGeneration;
    this.stopAutosave();
    document.getElementById('cost-photo-list')?.replaceChildren();
    this._supplementaryEnabled = false;
    this.currentVisit = null;
    this.updateVisitStatusBadge();
    const select = document.getElementById('entry-visit-select');
    if (select) select.innerHTML = '<option value="">选择访视…</option>';
    this.clearForms();
    const tip = document.getElementById('entry-no-visit-tip');
    const formArea = document.getElementById('entry-form-area');
    if (tip) tip.style.display = 'block';
    if (formArea) formArea.style.display = 'none';
    if (typeof QcBar !== 'undefined') QcBar.refresh();
  },

  // 清空所有表单字段（避免残留上一个访视/患者已填的数据）
  clearForms() {
    this._legacyComorbidityFlags = {};
    document.getElementById('cm-legacy-details')?.classList.add('hidden');
    const area = document.getElementById('entry-form-area');
    if (!area) return;
    area.querySelectorAll('input[type="text"], input[type="number"], input[type="date"], select, textarea').forEach(el => { el.value = ''; });
    area.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach(el => { el.checked = false; });
    // 滑块复位到默认值，并同步其分数/数值标签
    area.querySelectorAll('input[type="range"]').forEach(el => {
      el.value = el.defaultValue;
      delete el.dataset.answered;
      ['-val', '-score'].forEach(suffix => {
        const label = document.getElementById(el.id + suffix);
        if (label) label.textContent = el.value;
      });
    });
    const photoInput = document.getElementById('cost-photo-files');
    if (photoInput) photoInput.value = '';
    const photoStatus = document.getElementById('cost-photo-status');
    if (photoStatus) photoStatus.textContent = '';
    // 药物列表清空
    const medList = document.getElementById('medication-list');
    if (medList) medList.innerHTML = '';
    // 重新计算各自动汇总项（基于空表单 → 归零/待评估）
    this.calculateTotalCost();
    this.calculatePHQ9();
    this.calculateGAD7();
    this.calculateDTSQ();
    this.calculateEQ5D();
    this.calculateDietScore();
    this.calculateExerciseScore();
    this.showWarnings([]);
  },

  // 加载患者的访视列表（填充下拉框，自动选中草稿）
  async loadPatientVisits() {
    if (!this.currentPatient) return;
    const select = document.getElementById('entry-visit-select');
    if (!select) return;

    // 先清除上一个患者/访视的残留状态（停掉自动保存，防止把新患者的数据写进旧草稿）
    this.resetEntryState();

    const patient = this.currentPatient;
    const generation = this._patientGeneration;
    try {
      const visits = await api('GET', `/api/patients/${this.currentPatient.id}/visits`);
      if (this.currentPatient !== patient || generation !== this._patientGeneration) return;
      select.innerHTML = '<option value="">选择访视…</option>' + visits.map(v => {
        const typeLabel = { baseline: 'V1 基线', W12: 'V2 第12周', W26: 'V3 第26周', interim: '中间采集', M6: '历史6月', M12: '历史12月', M18: '历史18月', M24: '历史24月' }[v.visit_type] || v.visit_type;
        const statusLabel = { draft: '草稿', submitted: '待审核', qc_passed: '质控通过', signed: '已签名', locked: '已锁定' }[v.status] || v.status;
        return `<option value="${v.id}">${typeLabel}（${v.visit_date}）· ${statusLabel}</option>`;
      }).join('');
      // 自动选中最新草稿（或最新一条）；无访视时停留在"请先创建访视"提示。
      // 从质控审计页跳转时（pendingVisitId），优先定位到指定访视
      const pendingId = parseInt(sessionStorage.getItem('pendingVisitId'));
      sessionStorage.removeItem('pendingVisitId');
      const target = (pendingId && visits.find(v => v.id === pendingId))
        || visits.find(v => v.status === 'draft')
        || visits[visits.length - 1];
      if (target) {
        select.value = String(target.id);
        this.onVisitSelect(target.id);
      }
    } catch (e) {
      console.error('加载访视列表失败:', e);
      showToast('加载访视列表失败：' + e.message, 'error');
    }
  },

  // 选择访视后加载数据
  async onVisitSelect(visitId) {
    const generation = ++this._visitGeneration;
    const patient = this.currentPatient;
    this.stopAutosave();
    if (this._saveQueue) await this._saveQueue;
    if (generation !== this._visitGeneration || patient !== this.currentPatient) return;
    this.currentVisit = null;
    document.getElementById('entry-form-area').style.display = 'none';
    if (!visitId) {
      this.currentVisit = null;
      this.stopAutosave();
      this.updateVisitStatusBadge();
      return;
    }
    try {
      this.stopAutosave();
      const visit = await api('GET', `/api/visits/${visitId}`);
      if (generation !== this._visitGeneration || patient !== this.currentPatient) return;
      this.currentVisit = visit;
      document.querySelector('[data-followup-safety-tab]')?.classList.toggle('hidden', visit.visit_type === 'baseline');
      if (visit.visit_type === 'baseline' && !document.getElementById('tab-safety')?.classList.contains('hidden')) {
        document.getElementById('tab-safety').classList.add('hidden');
        document.getElementById('tab-physical').classList.remove('hidden');
      }
      this.updateVisitStatusBadge();
      if (typeof QcBar !== 'undefined') QcBar.refresh();
      this.clearForms();
      await this.loadVisitForms(visitId, generation);
      if (generation !== this._visitGeneration) return;
      await this.loadCostPhotos();
      if (generation !== this._visitGeneration) return;
      if (visit.status === 'draft') this.startAutosave();
      this.updateEditability();
      document.getElementById('entry-no-visit-tip').style.display = 'none';
      document.getElementById('entry-form-area').style.display = 'block';
    } catch (e) {
      console.error('加载访视失败:', e);
      showToast('加载访视失败：' + e.message, 'error');
    }
  },

  updateEditability() {
    const role = getUser()?.role;
    const editable = this.currentVisit?.status === 'draft' && ['researcher', 'center_admin', 'main_admin'].includes(role);
    document.querySelectorAll('#entry-form-area input, #entry-form-area select, #entry-form-area textarea, #entry-form-area button:not(.tab-btn):not([data-photo-download])').forEach(el => {
      if (!editable && !el.disabled) {
        el.dataset.edcReadOnly = '1';
        el.disabled = true;
      } else if (editable && el.dataset.edcReadOnly === '1') {
        el.disabled = false;
        delete el.dataset.edcReadOnly;
      }
    });
  },

  updateVisitStatusBadge() {
    const badge = document.getElementById('entry-visit-status');
    if (!badge) return;
    if (!this.currentVisit) { badge.classList.add('hidden'); return; }
    const map = {
      draft: ['草稿中', 'bg-blue-100 text-blue-700'],
      submitted: ['待审核', 'bg-orange-100 text-orange-700'],
      qc_passed: ['质控通过', 'bg-purple-100 text-purple-700'],
      signed: ['已签名', 'bg-green-100 text-green-700'],
      locked: ['已锁定', 'bg-gray-200 text-gray-600'],
    };
    const [label, cls] = map[this.currentVisit.status] || [this.currentVisit.status, 'bg-gray-100 text-gray-500'];
    badge.textContent = label;
    badge.className = `text-xs px-2 py-0.5 rounded-full ${cls}`;
  },

  // 加载已有表单数据并回填
  async loadVisitForms(visitId, generation = this._visitGeneration) {
    try {
      const data = await api('GET', `/api/visits/${visitId}/all-forms`);
      if (generation !== this._visitGeneration || this.currentVisit?.id !== Number(visitId)) return;
      this.fillForms(data);
    } catch (e) {
      console.error('加载表单数据失败:', e);
      throw e;
    }
  },

  // 设置事件监听
  setupEventListeners() {
    // BMI自动计算
    const heightInput = document.getElementById('pe-height');
    const weightInput = document.getElementById('pe-weight');
    if (heightInput && weightInput) {
      heightInput.addEventListener('input', () => this.calculateBMI());
      weightInput.addEventListener('input', () => this.calculateBMI());
    }

    // 腰臀比自动计算
    const waistInput = document.getElementById('pe-waist');
    const hipInput = document.getElementById('pe-hip');
    if (waistInput && hipInput) {
      waistInput.addEventListener('input', () => this.calculateWHR());
      hipInput.addEventListener('input', () => this.calculateWHR());
    }

    // 费用总计自动计算
    ['cost-drug', 'cost-exam', 'cost-service', 'cost-supply', 'cost-other'].forEach(id => {
      const input = document.getElementById(id);
      if (input) {
        input.addEventListener('input', () => this.calculateTotalCost());
      }
    });
  },

  // 计算BMI
  calculateBMI() {
    const height = parseFloat(document.getElementById('pe-height').value);
    const weight = parseFloat(document.getElementById('pe-weight').value);
    const bmiInput = document.getElementById('pe-bmi');

    if (height && weight && height > 0) {
      const bmi = (weight / Math.pow(height / 100, 2)).toFixed(1);
      bmiInput.value = bmi;
    } else {
      bmiInput.value = '';
    }
  },

  // 计算腰臀比
  calculateWHR() {
    const waist = parseFloat(document.getElementById('pe-waist').value);
    const hip = parseFloat(document.getElementById('pe-hip').value);
    const whrInput = document.getElementById('pe-whr');

    if (waist && hip && hip > 0) {
      const whr = (waist / hip).toFixed(2);
      whrInput.value = whr;
    } else {
      whrInput.value = '';
    }
  },

  // 计算总费用
  calculateTotalCost() {
    const drug = parseFloat(document.getElementById('cost-drug').value) || 0;
    const exam = parseFloat(document.getElementById('cost-exam').value) || 0;
    const hospital = parseFloat(document.getElementById('cost-service').value) || 0;
    const other = parseFloat(document.getElementById('cost-other').value) || 0;

    const supply = parseFloat(document.getElementById('cost-supply')?.value) || 0;
    const total = drug + exam + hospital + supply + other;
    document.getElementById('cost-total').textContent = `¥ ${total.toFixed(2)}`;
  },

  // 初始化问卷
  initializeQuestions() {
    this.initPHQ9();
    this.initGAD7();
    this.initEQ5D();
    this.initDTSQ();
    this.initDietAssessment();
    this.initExerciseAssessment();
    this.initMealRecords();
  },

  // Likert 单选组通用渲染（0-3 计分）
  _renderLikert(containerId, questions, namePrefix, onChange, options = ['完全不会', '好几天', '超过一周', '几乎每天']) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = questions.map((q, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm text-gray-700 mb-3">${i + 1}. ${q}</div>
        <div class="flex gap-3">
          ${[0, 1, 2, 3].map(score => `
            <label class="flex-1 cursor-pointer">
              <input type="radio" name="${namePrefix}-q${i}" value="${score}" class="hidden ${namePrefix}-radio" onchange="VisitEntry.${onChange}()"/>
              <div class="border-2 border-gray-200 rounded-lg p-2 text-center text-sm hover:border-blue-400 transition">
                <div class="font-semibold text-gray-700">${score}</div>
                <div class="text-xs text-gray-400">${options[score]}</div>
              </div>
            </label>
          `).join('')}
        </div>
      </div>
    `).join('');
    container.querySelectorAll(`.${namePrefix}-radio`).forEach(radio => {
      radio.addEventListener('change', (e) => {
        const label = e.target.closest('label');
        label.parentElement.querySelectorAll('label > div').forEach(div => {
          div.classList.remove('border-blue-500', 'bg-blue-50');
          div.classList.add('border-gray-200');
        });
        label.querySelector('div').classList.remove('border-gray-200');
        label.querySelector('div').classList.add('border-blue-500', 'bg-blue-50');
      });
    });
  },

  // 初始化PHQ-9问卷
  initPHQ9() {
    const questions = [
      '做事时提不起劲或没有兴趣',
      '感到心情低落，沮丧或绝望',
      '入睡困难、睡不安稳或睡眠过多',
      '感到疲惫或没有活力',
      '食欲不振或吃太多',
      '感觉自己很糟，觉得自己很失败或让自己失望',
      '做事专注有困难，例如阅读报纸和看电视时',
      '感到说话速度缓慢到别人已察觉？或正好相反，烦躁或坐立不安，动来动去的情况更胜于平常',
      '有不如死掉或用某种方式伤害自己的念头'
    ];
    this._renderLikert('phq9-questions', questions, 'phq9', 'calculatePHQ9', ['完全不会', '好几天', '一半以上的天数', '几乎每天']);
  },

  // 计算PHQ-9总分
  calculatePHQ9() {
    let total = 0;
    for (let i = 0; i < 9; i++) {
      const selected = document.querySelector(`input[name="phq9-q${i}"]:checked`);
      if (selected) {
        total += parseInt(selected.value);
      }
    }

    document.getElementById('phq9-score').textContent = total;


  },

  // 初始化GAD-7问卷
  initGAD7() {
    const questions = [
      '感到紧张、焦虑或急切',
      '不能停止或控制担忧',
      '对各种各样的事情担忧过多',
      '很难放松下来',
      '由于不安而无法静坐',
      '变得容易急躁',
      '感到似乎有可怕的事情发生而害怕'
    ];
    this._renderLikert('gad7-questions', questions, 'gad7', 'calculateGAD7');
  },

  // 计算GAD-7总分
  calculateGAD7() {
    let total = 0;
    for (let i = 0; i < 7; i++) {
      const selected = document.querySelector(`input[name="gad7-q${i}"]:checked`);
      if (selected) {
        total += parseInt(selected.value);
      }
    }

    document.getElementById('gad7-score').textContent = total;


  },

  // 初始化EQ-5D-5L
  initEQ5D() {
    const dims = [
      { label: '1. 行动能力', opts: ['我四处走动没有任何困难', '我四处走动有一点困难', '我四处走动有中度困难', '我四处走动有严重困难', '我无法四处走动'] },
      { label: '2. 自己照顾自己', opts: ['我自己洗澡或穿衣没有困难', '我自己洗澡或穿衣有一点困难', '我自己洗澡或穿衣有中度困难', '我自己洗澡或穿衣有严重困难', '我无法自己洗澡或穿衣'] },
      { label: '3. 日常活动', opts: ['我进行日常活动没有困难', '我进行日常活动有一点困难', '我进行日常活动有中度困难', '我进行日常活动有严重困难', '我无法进行日常活动'] },
      { label: '4. 疼痛/不舒服', opts: ['我没有任何疼痛或不舒服', '我有一点疼痛或不舒服', '我有中度的疼痛或不舒服', '我有严重的疼痛或不舒服', '我有非常严重的疼痛或不舒服'] },
      { label: '5. 焦虑或沮丧', opts: ['我没有焦虑或沮丧', '我有一点焦虑或沮丧', '我有中度焦虑或沮丧', '我有严重的焦虑或沮丧', '我有非常严重的焦虑或沮丧'] },
    ];
    const container = document.getElementById('eq5d-questions');
    if (!container) return;
    container.innerHTML = dims.map((dim, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-2">${dim.label}</div>
        <div class="space-y-1">${dim.opts.map((opt, j) => `
          <label class="flex items-center gap-2 cursor-pointer text-sm py-1 px-2 rounded hover:bg-blue-50">
            <input type="radio" name="eq5d-q${i}" value="${j + 1}" class="accent-blue-500 flex-shrink-0" onchange="VisitEntry.calculateEQ5D()"/>
            <span>${opt}</span>
          </label>`).join('')}
        </div>
      </div>
    `).join('');
  },

  // EQ-5D 摘要（已答维度数）
  calculateEQ5D() {
    const answered = ['eq5d-q0', 'eq5d-q1', 'eq5d-q2', 'eq5d-q3', 'eq5d-q4']
      .filter(n => document.querySelector(`input[name="${n}"]:checked`)).length;
    const vasVal = document.getElementById('eq5d-vas-val');
    if (vasVal) {
      const vas = document.getElementById('eq5d-vas');
      vasVal.textContent = vas?.dataset.answered === '1' ? vas.value : '未填写';
    }
    const summary = document.getElementById('eq5d-summary');
    if (summary) summary.textContent = `已答 ${answered} / 5 个维度`;
  },

  // 初始化DTSQ
  initDTSQ() {
    const items = [
      '1. 总体而言，您对目前的糖尿病治疗方案满意吗？',
      '2. 您认为目前的治疗方案在控制血糖方面效果如何？',
      '3. 您是否因治疗方案带来的不便而感到困扰？（如注射次数、服药频率等）',
      '4. 您对治疗方案的灵活性满意吗？（如调整剂量、适应生活方式变化的能力）',
      '5. 您是否担心治疗方案的不良反应（如低血糖、体重增加等）？',
      '6. 您认为目前的治疗方案对日常生活的干扰程度如何？',
      '7. 如果可以重新选择，您是否愿意继续使用目前的治疗方案？',
      '9. 您对治疗方案的费用负担满意吗？',
      '10. 您认为治疗方案的学习和操作难度如何？',
    ];
    const satisfaction = ['非常不满意', '比较不满意', '既非满意也非不满意', '比较满意', '非常满意'];
    const options = [satisfaction,
      ['完全无效','效果很差','效果一般','效果较好','效果非常好'],
      ['极度困扰','比较困扰','轻微困扰','几乎不困扰','完全不困扰'], satisfaction,
      ['极度担心','比较担心','轻微担心','几乎不担心','完全不担心'],
      ['严重干扰','比较干扰','轻微干扰','几乎不干扰','完全不干扰'],
      ['绝对不愿意','不太愿意','不确定','比较愿意','绝对愿意'], satisfaction,
      ['非常困难','比较困难','一般','比较容易','非常容易']];
    const container = document.getElementById('dtsq-questions');
    if (!container) return;
    const openBlock = document.getElementById('dtsq-open-text')?.parentElement;
    container.innerHTML = items.map((q, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm text-gray-700 mb-3">${q}</div>
        <div class="flex gap-2">
          ${options[i].map((label, v) => `
            <label class="flex-1 cursor-pointer">
              <input type="radio" name="dtsq-q${i}" value="${v + 1}" class="hidden dtsq-radio" onchange="VisitEntry.calculateDTSQ()"/>
              <div class="border-2 border-gray-200 rounded-lg px-1 py-2 text-center text-xs hover:border-blue-400 transition">
                ${v + 1}级<br/><span class="text-gray-400">${label}</span>
              </div>
            </label>
          `).join('')}
        </div>
      </div>
    `).join('');
    if (openBlock) container.insertBefore(openBlock, container.children[7]);
    container.querySelectorAll('.dtsq-radio').forEach(radio => {
      radio.addEventListener('change', (e) => {
        const label = e.target.closest('label');
        label.parentElement.querySelectorAll('label > div').forEach(div => {
          div.classList.remove('border-blue-500', 'bg-blue-50');
          div.classList.add('border-gray-200');
        });
        label.querySelector('div').classList.remove('border-gray-200');
        label.querySelector('div').classList.add('border-blue-500', 'bg-blue-50');
      });
    });
  },

  // 显示已答题数：CRF 未定义总分规则
  calculateDTSQ() {
    let total = 0;
    for (let i = 0; i < 9; i++) {
      const selected = document.querySelector(`input[name="dtsq-q${i}"]:checked`);
      if (selected) {
        total += 1;
      }
    }
    document.getElementById('dtsq-score').textContent = total;
  },

  // 初始化饮食评估
  initDietAssessment() {
    const questions = [
      { q: '每天吃早餐', max: 10 },
      { q: '每天吃3餐', max: 10 },
      { q: '每天吃蔬菜', max: 15 },
      { q: '每天吃水果', max: 15 },
      { q: '每天喝牛奶或豆浆', max: 10 },
      { q: '每周吃鱼类', max: 10 },
      { q: '控制油盐摄入', max: 10 },
      { q: '少吃油炸食品', max: 10 },
      { q: '少喝含糖饮料', max: 10 }
    ];

    const container = document.getElementById('diet-questions');
    if (!container) return;

    container.innerHTML = questions.map((item, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm text-gray-700">${i + 1}. ${item.q}</div>
          <div class="text-sm font-semibold text-blue-600">
            <span id="diet-q${i}-score">0</span> / ${item.max}
          </div>
        </div>
        <input type="range" min="0" max="${item.max}" value="0" step="1"
          class="w-full accent-blue-500" id="diet-q${i}"
          oninput="document.getElementById('diet-q${i}-score').textContent = this.value; VisitEntry.calculateDietScore()"/>
      </div>
    `).join('');
  },

  // 计算饮食评估总分
  calculateDietScore() {
    let total = 0;
    for (let i = 0; i < 9; i++) {
      const input = document.getElementById(`diet-q${i}`);
      if (input) {
        total += parseInt(input.value);
      }
    }

    document.getElementById('diet-score').textContent = total;

    const levelEl = document.getElementById('diet-level');
    if (total < 46) {
      levelEl.textContent = '差';
      levelEl.className = 'score-badge bg-gray-700 text-white';
    } else if (total < 66) {
      levelEl.textContent = '尚可';
      levelEl.className = 'score-badge bg-red-100 text-red-700';
    } else if (total < 86) {
      levelEl.textContent = '一般';
      levelEl.className = 'score-badge bg-yellow-100 text-yellow-700';
    } else {
      levelEl.textContent = '良好';
      levelEl.className = 'score-badge bg-green-100 text-green-700';
    }
  },

  // 初始化运动评估
  initExerciseAssessment() {
    const questions = [
      { q: '每周运动次数', max: 10 },
      { q: '每次运动时长（分钟）', max: 10 },
      { q: '运动强度（轻/中/重）', max: 10 },
      { q: '日常活动量', max: 10 },
      { q: '久坐时间控制', max: 10 }
    ];

    const container = document.getElementById('exercise-questions');
    if (!container) return;

    container.innerHTML = questions.map((item, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm text-gray-700">${i + 1}. ${item.q}</div>
          <div class="text-sm font-semibold text-blue-600">
            <span id="exercise-q${i}-score">0</span> / ${item.max}
          </div>
        </div>
        <input type="range" min="0" max="${item.max}" value="0" step="1"
          class="w-full accent-blue-500" id="exercise-q${i}"
          oninput="document.getElementById('exercise-q${i}-score').textContent = this.value; VisitEntry.calculateExerciseScore()"/>
      </div>
    `).join('');
  },

  // 计算运动评估总分
  calculateExerciseScore() {
    let total = 0;
    for (let i = 0; i < 5; i++) {
      const input = document.getElementById(`exercise-q${i}`);
      if (input) {
        total += parseInt(input.value);
      }
    }

    document.getElementById('exercise-score').textContent = total;

    const levelEl = document.getElementById('exercise-level');
    if (total < 21) {
      levelEl.textContent = '差';
      levelEl.className = 'score-badge bg-gray-700 text-white';
    } else if (total < 31) {
      levelEl.textContent = '尚可';
      levelEl.className = 'score-badge bg-red-100 text-red-700';
    } else if (total < 41) {
      levelEl.textContent = '一般';
      levelEl.className = 'score-badge bg-yellow-100 text-yellow-700';
    } else {
      levelEl.textContent = '良好';
      levelEl.className = 'score-badge bg-green-100 text-green-700';
    }
  },

  // 初始化膳食记录
  initMealRecords() {
    const meals = ['早餐', '午餐', '晚餐', '加餐'];
    const container = document.getElementById('meal-records');
    if (!container) return;

    container.innerHTML = meals.map((meal, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">${meal}</div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-xs text-gray-500 mb-1 block">食物名称</label>
            <input type="text" id="meal-${i}-food" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：米饭、鸡蛋"/>
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">摄入量</label>
            <input type="text" id="meal-${i}-amount" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：1碗、2个"/>
          </div>
        </div>
      </div>
    `).join('');
  },

  // 添加药物
  addMedication(med = {}) {
    const container = document.getElementById('medication-list');
    if (!container) return;
    const index = container.children.length;

    const medDiv = document.createElement('div');
    medDiv.className = 'border border-gray-200 rounded-lg p-4';
    medDiv.innerHTML = `
      <div class="flex justify-between mb-3"><span>药物 ${index + 1}</span><button onclick="this.closest('.medication-row').remove()" class="text-red-500 text-xs">删除</button></div>
      <div class="grid grid-cols-3 gap-3">
      ${[['treatment_type','治疗类型（糖尿病／高血压／降脂等）','text'],['drug_name','药剂名','text'],['route','给药途径','text'],['dose','用药剂量','text'],['frequency','用药频率（请写完整中文，如每周两次）','text'],['start_date','开始日期','date'],['end_date','结束日期（如有）','date']].map(([key,label,type]) => `<label class="text-xs text-gray-500">${label}<input type="${type}" data-med-field="${key}" value="${escapeText(med[key])}" class="w-full border rounded-lg p-2 text-sm"/></label>`).join('')}
      <label class="text-xs text-gray-500">正在进行<select data-med-field="is_ongoing" class="w-full border rounded-lg p-2"><option value="true">是</option><option value="false">否</option></select></label></div>`;
    medDiv.classList.add('medication-row');
    medDiv.querySelector('[data-med-field="is_ongoing"]').value = med.is_ongoing === false ? 'false' : 'true';
    // Native selects open on click; custom and historical values remain editable.
    const choices = {
      treatment_type: ['糖尿病','高血压','降脂','抗血小板','抗凝'],
      route: ['口服','皮下注射'],
    };
    for (const [key, values] of Object.entries(choices)) {
      const input = medDiv.querySelector(`[data-med-field="${key}"]`);
      const select = document.createElement('select');
      select.dataset.medField = key;
      select.className = input.className;
      select.innerHTML = '<option value="">请选择</option>' + values.map(v => `<option value="${v}">${v}</option>`).join('') + '<option value="__other__">其他（请填写）</option>';
      const custom = document.createElement('input');
      custom.type = 'text';
      custom.dataset.medOther = key;
      custom.className = input.className + ' mt-2';
      custom.placeholder = '请输入其他' + (key === 'route' ? '给药途径' : '治疗类型');
      const value = med[key] || '';
      select.value = value && !values.includes(value) ? '__other__' : value;
      custom.value = select.value === '__other__' ? value : '';
      custom.hidden = select.value !== '__other__';
      select.onchange = () => { custom.hidden = select.value !== '__other__'; };
      input.replaceWith(select);
      select.after(custom);
    }
    if (!document.getElementById('med-options-frequency')) {
      const list = document.createElement('datalist');
      list.id = 'med-options-frequency';
      list.innerHTML = ['必要时','每小时一次','每四小时一次','每六小时一次','每八小时一次','每十二小时一次','每日一次','每日两次','每日三次','隔日一次','每周一次','每周两次','每两周一次','每月一次'].map(v => `<option value="${v}"></option>`).join('');
      document.getElementById('tab-medication').appendChild(list);
    }
    medDiv.querySelector('[data-med-field="frequency"]').setAttribute('list', 'med-options-frequency');
    container.appendChild(medDiv);
  },

  // ===== 数据回填 =====
  fillForms(data) {
    const pe = data.physical_exam;
    if (pe) {
      this.setInputValue('pe-height', pe.height_cm);
      this.setInputValue('pe-weight', pe.weight_kg);
      this.setInputValue('pe-sbp', pe.sbp_mmhg);
      this.setInputValue('pe-dbp', pe.dbp_mmhg);
      this.setInputValue('pe-hr', pe.heart_rate);
      this.setInputValue('pe-waist', pe.waist_cm);
      this.setInputValue('pe-hip', pe.hip_cm);
      this.calculateBMI();
      this.calculateWHR();
    }

    const lab = data.lab_results;
    if (lab) {
      this.setInputValue('lab-fbg', lab.fasting_glucose);
      this.setInputValue('lab-hba1c', lab.hba1c);
      this.setInputValue('lab-tc', lab.tc);
      this.setInputValue('lab-tg', lab.tg);
      this.setInputValue('lab-hdl', lab.hdl_c);
      this.setInputValue('lab-ldl', lab.ldl_c);
      this.setInputValue('lab-alt', lab.alt);
      this.setInputValue('lab-ast', lab.ast);
      this.setInputValue('lab-cr', lab.scr);
      this.setInputValue('lab-test-date', lab.test_date);
      this.setInputValue('lab-bun', lab.bun);
      this.setInputValue('lab-egfr', lab.egfr);
      this.setInputValue('lab-ua', lab.ua);
    }

    const cm = data.comorbidity;
    this._legacyComorbidityFlags = Object.fromEntries(this.comorbidityFlags.map(k => [k, cm?.[k] ?? false]));
    const legacyNames = ['黄斑病变','非增殖性','增殖性','周围神经病变','自主神经病变','既往愈合溃疡','活动性溃疡'];
    const selectedLegacy = this.comorbidityFlags.flatMap((k,i) => cm?.[k] ? [legacyNames[i]] : []);
    document.getElementById('cm-legacy-details')?.classList.toggle('hidden', !selectedLegacy.length);
    const legacySummary = document.getElementById('cm-legacy-summary');
    if (legacySummary) legacySummary.textContent = selectedLegacy.join('、');
    if (cm) {
      for (const field of this.comorbidityFields) this.setInputValue('cm-' + field, cm[field]);
    }
    const safety = data.followup_safety;
    if (safety) {
      this.setInputValue('safety-hypoglycemia', safety.hypoglycemia);
      this.setInputValue('safety-other', safety.other);
      for (const field of this.safetyFlags) this.setChecked('safety-' + field, safety[field]);
    }
    this.fillPatientProfile();
    this._legacyCost = !!data.cost_indicators && data.cost_indicators.crf_version !== 1;
    this._legacyDtsq = !!data.questionnaires?.dtsq && data.questionnaires.dtsq.crf_version !== 1;
    document.getElementById('cost-legacy-warning')?.classList.toggle('hidden', !this._legacyCost);
    document.getElementById('dtsq-legacy-warning')?.classList.toggle('hidden', !this._legacyDtsq);

    // 用药
    const medList = document.getElementById('medication-list');
    if (medList) medList.innerHTML = '';
    (data.medications || []).forEach(m => this.addMedication(m));

    // 费用
    const cost = data.cost_indicators;
    if (cost) {
      this.setInputValue('cost-drug', cost.drug_cost);
      this.setInputValue('cost-exam', cost.lab_cost);
      this.setInputValue('cost-service', cost.service_cost);
      this.setInputValue('cost-other', cost.other_cost);
      this.setInputValue('cost-supply', cost.supply_cost);
      this.calculateTotalCost();
    }

    // 问卷
    const qs = data.questionnaires || {};
    this._loadedQuestionnaires = new Set(Object.keys(qs));
    const phq9 = qs.phq9;
    document.querySelectorAll('[name="phq9-symptoms"]').forEach(el => {
      el.checked = (phq9?.phq9_symptoms || '').split(',').includes(el.value);
    });
    if (phq9) {
      for (let i = 0; i < 9; i++) {
        this.setRadio(`phq9-q${i}`, phq9[`q${i + 1}`]);
      }
      this.calculatePHQ9();
    }
    const gad7 = qs.gad7;
    if (gad7) {
      for (let i = 0; i < 7; i++) {
        this.setRadio(`gad7-q${i}`, gad7[`q${i + 1}`]);
      }
      this.calculateGAD7();
    }
    const eq5d = qs.eq5d;
    if (eq5d) {
      this.setRadio('eq5d-q0', eq5d.eq_mobility);
      this.setRadio('eq5d-q1', eq5d.eq_self_care);
      this.setRadio('eq5d-q2', eq5d.eq_usual_activity);
      this.setRadio('eq5d-q3', eq5d.eq_pain);
      this.setRadio('eq5d-q4', eq5d.eq_anxiety);
      const vas = document.getElementById('eq5d-vas');
      if (vas && eq5d.eq_vas_score != null) {
        vas.value = eq5d.eq_vas_score;
        vas.dataset.answered = '1';
        document.getElementById('eq5d-vas-val').textContent = eq5d.eq_vas_score;
      }
    }
    const dtsq = qs.dtsq;
    if (dtsq) {
      for (let i = 0; i < 9; i++) {
        this.setRadio(`dtsq-q${i}`, dtsq[`q${i + 1}`]);
      }
      this.calculateDTSQ();
      this.setInputValue('dtsq-open-text', dtsq.dtsq_open_text);
    }

    // 生活方式
    const ls = data.lifestyle;
    if (ls) {
      if (ls.diet_scores_json) {
        try {
          const scores = JSON.parse(ls.diet_scores_json);
          scores.forEach((v, i) => {
            const input = document.getElementById(`diet-q${i}`);
            if (input) {
              input.value = v;
              const label = document.getElementById(`diet-q${i}-score`);
              if (label) label.textContent = v;
            }
          });
          this.calculateDietScore();
        } catch (e) { /* 忽略历史脏数据 */ }
      }
      if (ls.exercise_scores_json) {
        try {
          const scores = JSON.parse(ls.exercise_scores_json);
          scores.forEach((v, i) => {
            const input = document.getElementById(`exercise-q${i}`);
            if (input) {
              input.value = v;
              const label = document.getElementById(`exercise-q${i}-score`);
              if (label) label.textContent = v;
            }
          });
          this.calculateExerciseScore();
        } catch (e) { /* 忽略历史脏数据 */ }
      }
    }

    // 膳食记录
    (data.meal_records || []).forEach((r, i) => {
      if (i < 4) {
        this.setInputValue(`meal-${i}-food`, r.dish_name);
        this.setInputValue(`meal-${i}-amount`, r.estimated_amount);
      }
    });
  },

  // 设置输入值
  setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input && value !== null && value !== undefined) {
      input.value = value;
    }
  },

  setChecked(id, value) {
    const el = document.getElementById(id);
    if (el) el.checked = !!value;
  },

  setRadio(name, value) {
    if (value === null || value === undefined) return;
    const radio = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (radio) {
      radio.checked = true;
      radio.dispatchEvent(new Event('change'));
    }
  },

  // ===== 数据收集（与后端 schema 字段名对齐）=====
  collectFormData() {
    return {
      physical_exam: {
        height_cm: this.getInputValue('pe-height'),
        weight_kg: this.getInputValue('pe-weight'),
        sbp_mmhg: this.getInputValue('pe-sbp'),
        dbp_mmhg: this.getInputValue('pe-dbp'),
        heart_rate: this.getInputValue('pe-hr'),
        waist_cm: this.getInputValue('pe-waist'),
        hip_cm: this.getInputValue('pe-hip'),
      },
      lab_results: {
        fasting_glucose: this.getInputValue('lab-fbg'),
        hba1c: this.getInputValue('lab-hba1c'),
        tc: this.getInputValue('lab-tc'),
        tg: this.getInputValue('lab-tg'),
        hdl_c: this.getInputValue('lab-hdl'),
        ldl_c: this.getInputValue('lab-ldl'),
        alt: this.getInputValue('lab-alt'),
        ast: this.getInputValue('lab-ast'),
        scr: this.getInputValue('lab-cr'),
        test_date: document.getElementById('lab-test-date')?.value || null,
        bun: this.getInputValue('lab-bun'),
        egfr: this.getInputValue('lab-egfr'),
        ua: this.getInputValue('lab-ua'),
      },
      comorbidity: this.collectComorbidity(),
      followup_safety: {
        hypoglycemia: this.getInputValue('safety-hypoglycemia'),
        ...Object.fromEntries(this.safetyFlags.map(k => [k, document.getElementById('safety-' + k)?.checked || false])),
        other: document.getElementById('safety-other')?.value.trim() || null,
      },
      medications: this.collectMedications(),
      cost_indicators: {
        crf_version: 1,
        supply_cost: this.getInputValue('cost-supply'),
        drug_cost: this.getInputValue('cost-drug'),
        lab_cost: this.getInputValue('cost-exam'),
        service_cost: this.getInputValue('cost-service'),
        other_cost: this.getInputValue('cost-other'),
      },
      questionnaires: {
        phq9: { ...this.collectLikert('phq9-q', 9), phq9_symptoms: Array.from(document.querySelectorAll('[name="phq9-symptoms"]:checked')).map(el => el.value).join(',') || null },
        gad7: this.collectLikert('gad7-q', 7),
        eq5d: this.collectEQ5D(),
        dtsq: this.collectDTSQ(),
      },
      lifestyle: {
        diet_scores_json: JSON.stringify(this.collectSliders('diet-q', 9)),
        exercise_scores_json: JSON.stringify(this.collectSliders('exercise-q', 5)),
      },
      meal_records: this.collectMealRecords(),
    };
  },

  comorbidityFields: ['hypertension','ckd','chd','angina','mi','stroke','dr','dn','df'].flatMap(k => [k, k + '_date']).concat(['hypertension_cause','ckd_cause','other_conditions']),
  comorbidityFlags: ['dr_macular','dr_non_proliferative','dr_proliferative','dn_peripheral','dn_autonomic','df_healed_ulcer','df_active_ulcer'],
  safetyFlags: ['symptomatic','nocturnal','severe','gastrointestinal','allergy'],
  profileFields: ['age','study_group','study_subgroup','visit_number','enrollment_date','employment_status','education_level','insurance_coverage','smoking_history','smoking_per_day','drinking_history','drinking_per_day'],
  collectComorbidity() {
    const result = {};
    for (const k of this.comorbidityFields) {
      const value = document.getElementById('cm-' + k)?.value;
      result[k] = value === '' || value == null ? null : (k.includes('_') ? value.trim() : Number(value));
    }
    // Retain legacy structured flags; the new free-text field does not erase them.
    for (const k of this.comorbidityFlags) result[k] = this._legacyComorbidityFlags?.[k] ?? false;
    return result;
  },
  fillPatientProfile() {
    if (!this.currentPatient) return;
    fillStudySubgroups(this.currentPatient.study_group, 'bp-study_subgroup', this.currentPatient.study_subgroup);
    for (const k of this.profileFields) this.setInputValue('bp-' + k, this.currentPatient[k]);
    for (const kind of ['smoking','drinking']) {
      if (this.currentPatient[kind + '_history'] == null && this.currentPatient[kind + '_status'] != null) {
        this.setInputValue('bp-' + kind + '_history', this.currentPatient[kind + '_status'] === 1 ? 1 : 2);
      }
    }
  },
  async savePatientProfile(verbose = true) {
    if (!this.currentPatient || this.currentVisit?.status !== 'draft') return;
    const payload = {};
    for (const k of this.profileFields) {
      const raw = document.getElementById('bp-' + k)?.value;
      payload[k] = raw === '' || raw == null ? null : (['study_group','study_subgroup','visit_number','enrollment_date'].includes(k) ? raw.trim() : Number(raw));
    }
    try {
      const changes = Object.fromEntries(Object.entries(payload).filter(([k, v]) => (this.currentPatient[k] ?? null) !== v));
      if (!Object.keys(changes).length) return true;
      this.currentPatient = await api('PUT', `/api/patients/${this.currentPatient.id}`, changes);
      sessionStorage.setItem('currentPatient', JSON.stringify(this.currentPatient));
      this.updatePatientInfo();
      if (verbose) showToast('基本信息已保存');
      return true;
    } catch (e) { if (verbose) showToast(e.message, 'error'); return false; }
  },

  // 获取输入值
  getInputValue(id) {
    const input = document.getElementById(id);
    if (!input || input.value === '') return null;
    return parseFloat(input.value) || input.value;
  },

  // 收集药物数据
  collectMedications() {
    const medications = [];
    const container = document.getElementById('medication-list');
    if (!container) return medications;

    container.querySelectorAll('.medication-row').forEach(row => {
      const item = {};
      row.querySelectorAll('[data-med-field]').forEach(el => {
        item[el.dataset.medField] = el.dataset.medField === 'is_ongoing' ? el.value === 'true' : el.value.trim() || null;
      });
      for (const key of ['route', 'treatment_type']) {
        if (item[key] === '__other__') item[key] = row.querySelector(`[data-med-other="${key}"]`).value.trim() || null;
      }
      if (Object.entries(item).some(([k,v]) => k !== 'is_ongoing' && v != null)) medications.push(item);
    });

    return medications;
  },

  // 收集 Likert 问卷（PHQ-9/GAD-7）：{q1..qn}
  collectLikert(prefix, count) {
    const result = {};
    for (let i = 0; i < count; i++) {
      const selected = document.querySelector(`input[name="${prefix}${i}"]:checked`);
      result[`q${i + 1}`] = selected ? parseInt(selected.value) : null;
    }
    return result;
  },

  // 收集 EQ-5D
  collectEQ5D() {
    const dims = ['eq_mobility', 'eq_self_care', 'eq_usual_activity', 'eq_pain', 'eq_anxiety'];
    const result = {};
    dims.forEach((field, i) => {
      const selected = document.querySelector(`input[name="eq5d-q${i}"]:checked`);
      result[field] = selected ? parseInt(selected.value) : null;
    });
    const vas = document.getElementById('eq5d-vas');
    result.eq_vas_score = vas?.dataset.answered === '1' ? parseInt(vas.value) : null;
    return result;
  },

  // 收集 DTSQ
  collectDTSQ() {
    const result = this.collectLikert('dtsq-q', 9);
    result.crf_version = 1;
    result.dtsq_open_text = document.getElementById('dtsq-open-text')?.value?.trim() || null;
    return result;
  },

  // 收集滑杆分值
  collectSliders(prefix, count) {
    const scores = [];
    for (let i = 0; i < count; i++) {
      const input = document.getElementById(`${prefix}${i}`);
      scores.push(input ? parseInt(input.value) : 0);
    }
    return scores;
  },

  // 收集膳食记录
  collectMealRecords() {
    const records = [];
    const mealNames = ['早餐', '午餐', '晚餐', '加餐'];
    for (let i = 0; i < 4; i++) {
      const food = document.getElementById(`meal-${i}-food`)?.value?.trim();
      const amount = document.getElementById(`meal-${i}-amount`)?.value?.trim();
      if (food) {
        records.push({ meal_time: mealNames[i], dish_name: food, estimated_amount: amount });
      }
    }
    return records;
  },

  // ===== 草稿自动保存 =====
  startAutosave() {
    this.stopAutosave();
    this._autosaveTimer = setInterval(() => {
      if (this.currentVisit && this.currentVisit.status === 'draft') {
        this.saveAllForms(false); // 静默保存
      }
    }, 30000);
  },

  stopAutosave() {
    if (this._autosaveTimer) {
      clearInterval(this._autosaveTimer);
      this._autosaveTimer = null;
    }
  },

  // 展示后端核查告警
  showWarnings(warnings) {
    const box = document.getElementById('entry-warnings');
    const list = document.getElementById('entry-warnings-list');
    if (!box || !list) return;
    if (!warnings || !warnings.length) {
      box.classList.add('hidden');
      return;
    }
    list.innerHTML = warnings.map(w => `<li>${w.message}</li>`).join('');
    box.classList.remove('hidden');
  },

  // 提交前必填校验
  validateForSubmit() {
    const errors = [];
    if (!this.currentVisit) {
      errors.push('请先创建或选择访视');
    } else if (!this.currentVisit.visit_date) {
      errors.push('访视日期不能为空');
    }
    const height = document.getElementById('pe-height')?.value;
    const weight = document.getElementById('pe-weight')?.value;
    if (!height) errors.push('身高为必填项');
    if (!weight) errors.push('体重为必填项');
    return errors;
  },

  // 保存全部表单到后端（各表单独立接口）
  saveAllForms(verbose = true) {
    const visitId = this.currentVisit?.id;
    const run = async () => {
      if (this.currentVisit?.id !== visitId) return false;
      return this._saveAllForms(verbose);
    };
    this._saveQueue = (this._saveQueue || Promise.resolve()).then(run, run);
    return this._saveQueue;
  },

  async _saveAllForms(verbose = true) {
    if (!this.currentVisit || this.currentVisit.status !== 'draft') return false;
    const visitId = this.currentVisit.id;
    const data = this.collectFormData();
    if (!await this.savePatientProfile(verbose)) return false;
    if (this.currentVisit?.id !== visitId) return false;
    const allWarnings = [];
    const tasks = [
      ['physical-exam', data.physical_exam],
      ['lab-results', data.lab_results],
      ['comorbidity', data.comorbidity],
      ...(!this._legacyCost || document.getElementById('cost-reviewed')?.checked ? [['cost-indicators', data.cost_indicators]] : []),
      ...(this.currentVisit.visit_type !== 'baseline' ? [['followup-safety', data.followup_safety]] : []),
      ['medications', { medications: data.medications }],
      ...(this._supplementaryEnabled ? [['lifestyle', data.lifestyle], ['meal-records', { records: data.meal_records }]] : []),
    ];
    for (const [endpoint, payload] of tasks) {
      try {
        const res = await api('POST', `/api/visits/${visitId}/${endpoint}`, payload);
        if (res.warnings) allWarnings.push(...res.warnings);
      } catch (e) {
        if (verbose) showToast(`${endpoint} 保存失败：${e.message}`, 'error');
        return false;
      }
    }
    // 问卷：逐类型提交
    for (const qType of ['phq9', 'gad7', 'eq5d', 'dtsq']) {
      if (qType === 'dtsq' && this._legacyDtsq && !document.getElementById('dtsq-reviewed')?.checked) continue;
      const payload = data.questionnaires[qType];
      if ((['phq9', 'gad7'].includes(qType) && this._loadedQuestionnaires?.has(qType)) || Object.entries(payload).some(([k, v]) => k !== 'crf_version' && v !== null && v !== undefined)) {
        try {
          await api('POST', `/api/visits/${visitId}/questionnaire`, {
            questionnaire_type: qType,
            ...payload,
          });
          (this._loadedQuestionnaires ||= new Set()).add(qType);
        } catch (e) {
          if (verbose) showToast(`${qType} 保存失败：${e.message}`, 'error');
          return false;
        }
      }
    }
    this.showWarnings(allWarnings);
    return true;
  },
};

// 显示新建访视模态框
function showNewVisitModal() {
  if (!VisitEntry.currentPatient) {
    showToast('请在患者管理点击患者编号或“查看／录入”', 'error');
    return;
  }
  document.getElementById('modal-new-visit').classList.remove('hidden');
  // 设置默认日期为今天
  document.getElementById('nv-date').valueAsDate = new Date();
}

// 关闭新建访视模态框
function closeNewVisitModal() {
  document.getElementById('modal-new-visit').classList.add('hidden');
  document.getElementById('nv-error').textContent = '';
}

// 提交新建访视
async function submitNewVisit() {
  const errEl = document.getElementById('nv-error');
  const btn = document.getElementById('nv-submit-btn');
  errEl.textContent = '';

  const visitType = document.getElementById('nv-type').value;
  const visitDate = document.getElementById('nv-date').value;

  if (!visitDate) {
    errEl.textContent = '请选择就诊日期';
    return;
  }

  if (!VisitEntry.currentPatient) {
    errEl.textContent = '未选择患者';
    return;
  }

  btn.disabled = true;
  btn.textContent = '创建中…';

  try {
    const visit = await api('POST', `/api/patients/${VisitEntry.currentPatient.id}/visits`, {
      visit_type: visitType,
      visit_date: visitDate,
    });

    VisitEntry.currentVisit = visit;

    // 刷新访视下拉框并选中
    await VisitEntry.loadPatientVisits();

    // 隐藏提示，显示表单
    document.getElementById('entry-no-visit-tip').style.display = 'none';
    document.getElementById('entry-form-area').style.display = 'block';

    closeNewVisitModal();
    showToast('✓ 访视创建成功，可以开始录入数据');
  } catch (error) {
    console.error('创建访视失败:', error);
    errEl.textContent = error.message || '创建失败';
  } finally {
    btn.disabled = false;
    btn.textContent = '创建';
  }
}

// Tab切换
function switchEntryTab(tabName) {
  // 更新tab按钮状态
  document.querySelectorAll('#page-entry .tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');

  // 更新tab内容
  document.querySelectorAll('#page-entry .tab-panel').forEach(panel => {
    panel.classList.add('hidden');
  });
  document.getElementById(`tab-${tabName}`).classList.remove('hidden');

  // 切换 tab 时静默保存草稿
  if (VisitEntry.currentVisit && VisitEntry.currentVisit.status === 'draft') {
    VisitEntry.saveAllForms(false);
  }
}

// 保存访视数据（draft=存草稿；submitted=保存并提交审核）
async function saveVisitData(status) {
  if (VisitEntry._savingVisit) return;
  VisitEntry._savingVisit = true;
  const targetVisit = VisitEntry.currentVisit;
  try {
    if (!VisitEntry.currentVisit) {
      showToast('请先创建或选择访视', 'error');
      return;
    }
    if (VisitEntry.currentVisit.status !== 'draft') {
      showToast('该访视只读；待审核可选择原因后撤回修改，已审核须由总管理员退回草稿', 'error');
      return;
    }

    if (VisitEntry._uploadingPhotos) { showToast('请等待费用照片上传完成', 'error'); return; }
    if (status === 'submitted') {
      const errors = VisitEntry.validateForSubmit();
      if (errors.length) {
        showToast(errors[0], 'error');
        return;
      }
    }

    const ok = await VisitEntry.saveAllForms(true);
    if (!ok) return;
    if (VisitEntry.currentVisit !== targetVisit) return;

    if (status === 'submitted') {
      await api('POST', `/api/visits/${targetVisit.id}/submit`);
      targetVisit.status = 'submitted';
      if (VisitEntry.currentVisit !== targetVisit) return;
      VisitEntry.updateEditability();
      VisitEntry.updateVisitStatusBadge();
      if (typeof QcBar !== 'undefined') QcBar.refresh();
      VisitEntry.stopAutosave();
      showToast('✓ 已提交审核');
      showSubmissionSuccess();
    } else {
      showToast('✓ 草稿已保存，可继续填写');
    }
  } catch (error) {
    console.error('保存失败:', error);
    showToast('保存失败：' + error.message, 'error');
  } finally {
    VisitEntry._savingVisit = false;
  }
}

function showSubmissionSuccess() {
  document.getElementById('submission-success')?.remove();
  const dialog = document.createElement('dialog');
  dialog.id = 'submission-success';
  dialog.className = 'rounded-xl p-6 max-w-md w-full shadow-xl';
  dialog.setAttribute('aria-labelledby', 'submission-success-title');
  dialog.innerHTML = `<h2 id="submission-success-title" class="text-xl font-semibold text-green-700">提交成功</h2>
    <p class="my-4">本次访视已提交审核。您可以从患者管理的“查看／录入”再次进入，查看审核状态或新建访视。待审核时如需更正，可选择原因后撤回修改。</p>
    <button type="button" autofocus class="bg-blue-600 text-white rounded-lg px-5 py-2">知道了</button>`;
  dialog.querySelector('button').onclick = () => dialog.close();
  dialog.addEventListener('close', () => dialog.remove(), {once: true});
  document.body.appendChild(dialog);
  dialog.showModal();
}

// 页面加载时初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => VisitEntry.init());
} else {
  VisitEntry.init();
}

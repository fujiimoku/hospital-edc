// 访视数据录入模块
// 所有 API 调用统一走 js/config.js 的 api()（API_BASE + getToken()）
const VisitEntry = {
  currentVisit: null,
  currentPatient: null,
  _autosaveTimer: null,

  // 初始化
  init() {
    this.setupEventListeners();
    this.initializeQuestions();
    this.loadCurrentPatient();
  },

  // 加载当前患者
  loadCurrentPatient() {
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
      if (infoEl) infoEl.textContent = '请先在【患者管理】选择患者';
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
    this.stopAutosave();
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
    const area = document.getElementById('entry-form-area');
    if (!area) return;
    area.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(el => { el.value = ''; });
    area.querySelectorAll('input[type="checkbox"], input[type="radio"]').forEach(el => { el.checked = false; });
    // 滑块复位到默认值，并同步其分数/数值标签
    area.querySelectorAll('input[type="range"]').forEach(el => {
      el.value = el.defaultValue;
      ['-val', '-score'].forEach(suffix => {
        const label = document.getElementById(el.id + suffix);
        if (label) label.textContent = el.value;
      });
    });
    // 药物列表清空
    const medList = document.getElementById('medication-list');
    if (medList) medList.innerHTML = '';
    // 重新计算各自动汇总项（基于空表单 → 归零/待评估）
    this.calculateTotalCost();
    this.calculatePHQ9();
    this.calculateGAD7();
    this.calculateDTSQ();
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

    try {
      const visits = await api('GET', `/api/patients/${this.currentPatient.id}/visits/`);
      select.innerHTML = '<option value="">选择访视…</option>' + visits.map(v => {
        const typeLabel = { baseline: '基线', M6: '6月', M12: '12月', M18: '18月', M24: '24月' }[v.visit_type] || v.visit_type;
        const statusLabel = { draft: '草稿', submitted: '待审核', qc_passed: '质控通过', signed: '已签名', locked: '已锁定' }[v.status] || v.status;
        return `<option value="${v.id}">${typeLabel}（${v.visit_date}）· ${statusLabel}</option>`;
      }).join('');
      // 自动选中最新草稿（或最新一条）；无访视时停留在"请先创建访视"提示
      const draft = visits.find(v => v.status === 'draft') || visits[visits.length - 1];
      if (draft) {
        select.value = String(draft.id);
        this.onVisitSelect(draft.id);
      }
    } catch (e) {
      console.error('加载访视列表失败:', e);
      showToast('加载访视列表失败：' + e.message, 'error');
    }
  },

  // 选择访视后加载数据
  async onVisitSelect(visitId) {
    if (!visitId) {
      this.currentVisit = null;
      this.stopAutosave();
      this.updateVisitStatusBadge();
      return;
    }
    try {
      const visit = await api('GET', `/api/visits/${visitId}`);
      this.currentVisit = visit;
      this.updateVisitStatusBadge();
      if (typeof QcBar !== 'undefined') QcBar.refresh();
      if (visit.status === 'draft') {
        this.startAutosave();
      } else {
        this.stopAutosave();
      }
      await this.loadVisitForms(visitId);
      document.getElementById('entry-no-visit-tip').style.display = 'none';
      document.getElementById('entry-form-area').style.display = 'block';
    } catch (e) {
      console.error('加载访视失败:', e);
      showToast('加载访视失败：' + e.message, 'error');
    }
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
  async loadVisitForms(visitId) {
    try {
      const data = await api('GET', `/api/visits/${visitId}/all-forms`);
      this.fillForms(data);
    } catch (e) {
      console.error('加载表单数据失败:', e);
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
    ['cost-drug', 'cost-exam', 'cost-hospital', 'cost-other'].forEach(id => {
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
    const hospital = parseFloat(document.getElementById('cost-hospital').value) || 0;
    const other = parseFloat(document.getElementById('cost-other').value) || 0;

    const total = drug + exam + hospital + other;
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
  _renderLikert(containerId, questions, namePrefix, onChange) {
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
                <div class="text-xs text-gray-400">${['完全不会', '好几天', '超过一周', '几乎每天'][score]}</div>
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
      '感到心情低落、沮丧或绝望',
      '入睡困难、睡不安稳或睡眠过多',
      '感觉疲倦或没有活力',
      '食欲不振或吃太多',
      '觉得自己很糟糕，或觉得自己很失败，或让自己或家人失望',
      '对事物专注有困难，例如阅读报纸或看电视时',
      '动作或说话速度缓慢到别人已经察觉？或正好相反——烦躁或坐立不安、动来动去的情况更胜于平常',
      '有不如死掉或用某种方式伤害自己的念头'
    ];
    this._renderLikert('phq9-questions', questions, 'phq9', 'calculatePHQ9');
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

    const levelEl = document.getElementById('phq9-level');
    if (total <= 4) {
      levelEl.textContent = '无抑郁症状';
      levelEl.className = 'score-badge bg-green-100 text-green-700';
    } else if (total <= 9) {
      levelEl.textContent = '轻度抑郁';
      levelEl.className = 'score-badge bg-yellow-100 text-yellow-700';
    } else if (total <= 14) {
      levelEl.textContent = '中度抑郁';
      levelEl.className = 'score-badge bg-orange-100 text-orange-700';
    } else if (total <= 19) {
      levelEl.textContent = '中重度抑郁';
      levelEl.className = 'score-badge bg-red-100 text-red-700';
    } else {
      levelEl.textContent = '重度抑郁';
      levelEl.className = 'score-badge bg-red-200 text-red-800';
    }
  },

  // 初始化GAD-7问卷
  initGAD7() {
    const questions = [
      '感觉紧张、焦虑或急切',
      '不能够停止或控制担忧',
      '对各种各样的事情担忧过多',
      '很难放松下来',
      '由于不安而无法静坐',
      '变得容易烦恼或急躁',
      '感到似乎将有可怕的事情发生而害怕'
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

    const levelEl = document.getElementById('gad7-level');
    if (total <= 4) {
      levelEl.textContent = '无焦虑症状';
      levelEl.className = 'score-badge bg-green-100 text-green-700';
    } else if (total <= 9) {
      levelEl.textContent = '轻度焦虑';
      levelEl.className = 'score-badge bg-yellow-100 text-yellow-700';
    } else if (total <= 14) {
      levelEl.textContent = '中度焦虑';
      levelEl.className = 'score-badge bg-orange-100 text-orange-700';
    } else {
      levelEl.textContent = '重度焦虑';
      levelEl.className = 'score-badge bg-red-100 text-red-700';
    }
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
      vasVal.textContent = document.getElementById('eq5d-vas')?.value ?? vasVal.textContent;
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
      '8. 您对治疗方案的费用负担满意吗？',
      '9. 您认为治疗方案的学习和操作难度如何？',
    ];
    const opts = ['非常不满意', '比较不满意', '一般', '比较满意', '非常满意'];
    const container = document.getElementById('dtsq-questions');
    if (!container) return;
    container.innerHTML = items.map((q, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm text-gray-700 mb-3">${q}</div>
        <div class="flex gap-2">
          ${opts.map((label, v) => `
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

  // 计算DTSQ总分
  calculateDTSQ() {
    let total = 0;
    for (let i = 0; i < 9; i++) {
      const selected = document.querySelector(`input[name="dtsq-q${i}"]:checked`);
      if (selected) {
        total += parseInt(selected.value);
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
      <div class="flex items-center justify-between mb-3">
        <div class="text-sm font-semibold text-gray-700">药物 ${index + 1}</div>
        <button onclick="this.closest('.border').remove()" class="text-red-500 hover:text-red-700 text-xs">删除</button>
      </div>
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="text-xs text-gray-500 mb-1 block">药品名称</label>
          <input type="text" value="${med.drug_name || ''}" class="med-name w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：二甲双胍"/>
        </div>
        <div>
          <label class="text-xs text-gray-500 mb-1 block">剂量</label>
          <input type="text" value="${med.dose || ''}" class="med-dosage w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：500mg"/>
        </div>
        <div>
          <label class="text-xs text-gray-500 mb-1 block">频次</label>
          <input type="text" value="${med.frequency || ''}" class="med-frequency w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：每日2次"/>
        </div>
      </div>
    `;

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
      this.setInputValue('lab-bun', lab.bun);
    }

    const cm = data.comorbidity;
    if (cm) {
      this.setChecked('cm-hypertension', cm.hypertension === 1);
      this.setChecked('cm-ckd', cm.ckd === 1);
      this.setChecked('cm-chd', cm.chd === 1);
      this.setChecked('cm-stroke', cm.stroke === 1);
      this.setChecked('cm-retinopathy', cm.dr === 1);
      this.setChecked('cm-neuropathy', cm.dn === 1);
      this.setChecked('cm-diabetic-foot', cm.df === 1);
    }

    // 用药
    const medList = document.getElementById('medication-list');
    if (medList) medList.innerHTML = '';
    (data.medications || []).forEach(m => this.addMedication(m));

    // 费用
    const cost = data.cost_indicators;
    if (cost) {
      this.setInputValue('cost-drug', cost.drug_cost);
      this.setInputValue('cost-exam', cost.lab_cost);
      this.setInputValue('cost-hospital', cost.service_cost);
      this.setInputValue('cost-other', cost.other_cost);
      this.calculateTotalCost();
    }

    // 问卷
    const qs = data.questionnaires || {};
    const phq9 = qs.phq9;
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
        bun: this.getInputValue('lab-bun'),
      },
      comorbidity: {
        hypertension: document.getElementById('cm-hypertension')?.checked ? 1 : 0,
        ckd: document.getElementById('cm-ckd')?.checked ? 1 : 0,
        chd: document.getElementById('cm-chd')?.checked ? 1 : 0,
        stroke: document.getElementById('cm-stroke')?.checked ? 1 : 0,
        dr: document.getElementById('cm-retinopathy')?.checked ? 1 : 0,
        dn: document.getElementById('cm-neuropathy')?.checked ? 1 : 0,
        df: document.getElementById('cm-diabetic-foot')?.checked ? 1 : 0,
      },
      medications: this.collectMedications(),
      cost_indicators: {
        drug_cost: this.getInputValue('cost-drug'),
        lab_cost: this.getInputValue('cost-exam'),
        service_cost: this.getInputValue('cost-hospital'),
        other_cost: this.getInputValue('cost-other'),
      },
      questionnaires: {
        phq9: this.collectLikert('phq9-q', 9),
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

    container.querySelectorAll('.border').forEach(medDiv => {
      const drug_name = medDiv.querySelector('.med-name')?.value?.trim();
      const dose = medDiv.querySelector('.med-dosage')?.value?.trim();
      const frequency = medDiv.querySelector('.med-frequency')?.value?.trim();

      if (drug_name) {
        medications.push({ drug_name, dose, frequency });
      }
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
    result.eq_vas_score = vas ? parseInt(vas.value) : null;
    return result;
  },

  // 收集 DTSQ
  collectDTSQ() {
    const result = this.collectLikert('dtsq-q', 9);
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
  async saveAllForms(verbose = true) {
    if (!this.currentVisit) return false;
    const visitId = this.currentVisit.id;
    const data = this.collectFormData();
    const allWarnings = [];
    const tasks = [
      ['physical-exam', data.physical_exam],
      ['lab-results', data.lab_results],
      ['comorbidity', data.comorbidity],
      ['cost-indicators', data.cost_indicators],
      ['medications', { medications: data.medications }],
      ['lifestyle', data.lifestyle],
      ['meal-records', { records: data.meal_records }],
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
      const payload = data.questionnaires[qType];
      if (Object.values(payload).some(v => v !== null && v !== undefined)) {
        try {
          await api('POST', `/api/visits/${visitId}/questionnaire`, {
            questionnaire_type: qType,
            ...payload,
          });
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
    showToast('请先在【患者管理】选择患者', 'error');
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
  try {
    if (!VisitEntry.currentVisit) {
      showToast('请先创建或选择访视', 'error');
      return;
    }
    if (VisitEntry.currentVisit.status === 'locked') {
      showToast('该访视已锁定，无法修改', 'error');
      return;
    }

    if (status === 'submitted') {
      const errors = VisitEntry.validateForSubmit();
      if (errors.length) {
        showToast(errors[0], 'error');
        return;
      }
    }

    const ok = await VisitEntry.saveAllForms(true);
    if (!ok) return;

    if (status === 'submitted') {
      await api('POST', `/api/visits/${VisitEntry.currentVisit.id}/submit`);
      VisitEntry.currentVisit.status = 'submitted';
      VisitEntry.updateVisitStatusBadge();
      if (typeof QcBar !== 'undefined') QcBar.refresh();
      VisitEntry.stopAutosave();
      showToast('✓ 已提交审核');
    } else {
      showToast('✓ 草稿已保存');
    }
  } catch (error) {
    console.error('保存失败:', error);
    showToast('保存失败：' + error.message, 'error');
  }
}

// 页面加载时初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => VisitEntry.init());
} else {
  VisitEntry.init();
}

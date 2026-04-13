// 访视数据录入模块
const VisitEntry = {
  currentVisit: null,
  currentPatient: null,

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
    this.initDietAssessment();
    this.initExerciseAssessment();
    this.initMealRecords();
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

    const container = document.getElementById('phq9-questions');
    if (!container) return;

    container.innerHTML = questions.map((q, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm text-gray-700 mb-3">${i + 1}. ${q}</div>
        <div class="flex gap-3">
          ${[0, 1, 2, 3].map(score => `
            <label class="flex-1 cursor-pointer">
              <input type="radio" name="phq9-q${i}" value="${score}" class="hidden phq9-radio" onchange="VisitEntry.calculatePHQ9()"/>
              <div class="border-2 border-gray-200 rounded-lg p-2 text-center text-sm hover:border-blue-400 transition">
                <div class="font-semibold text-gray-700">${score}</div>
                <div class="text-xs text-gray-400">${['完全不会', '好几天', '超过一周', '几乎每天'][score]}</div>
              </div>
            </label>
          `).join('')}
        </div>
      </div>
    `).join('');

    // 添加选中样式
    container.querySelectorAll('.phq9-radio').forEach(radio => {
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

    const container = document.getElementById('gad7-questions');
    if (!container) return;

    container.innerHTML = questions.map((q, i) => `
      <div class="border border-gray-200 rounded-lg p-4">
        <div class="text-sm text-gray-700 mb-3">${i + 1}. ${q}</div>
        <div class="flex gap-3">
          ${[0, 1, 2, 3].map(score => `
            <label class="flex-1 cursor-pointer">
              <input type="radio" name="gad7-q${i}" value="${score}" class="hidden gad7-radio" onchange="VisitEntry.calculateGAD7()"/>
              <div class="border-2 border-gray-200 rounded-lg p-2 text-center text-sm hover:border-blue-400 transition">
                <div class="font-semibold text-gray-700">${score}</div>
                <div class="text-xs text-gray-400">${['完全不会', '好几天', '超过一周', '几乎每天'][score]}</div>
              </div>
            </label>
          `).join('')}
        </div>
      </div>
    `).join('');

    // 添加选中样式
    container.querySelectorAll('.gad7-radio').forEach(radio => {
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
    const maxScores = [10, 10, 15, 15, 10, 10, 10, 10, 10];
    let total = 0;

    maxScores.forEach((max, i) => {
      const input = document.getElementById(`diet-q${i}`);
      if (input) {
        total += parseInt(input.value);
      }
    });

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
  addMedication() {
    const container = document.getElementById('medication-list');
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
          <input type="text" class="med-name w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：二甲双胍"/>
        </div>
        <div>
          <label class="text-xs text-gray-500 mb-1 block">剂量</label>
          <input type="text" class="med-dosage w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：500mg"/>
        </div>
        <div>
          <label class="text-xs text-gray-500 mb-1 block">频次</label>
          <input type="text" class="med-frequency w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="如：每日2次"/>
        </div>
      </div>
    `;

    container.appendChild(medDiv);
  },

  // 加载访视数据
  async loadVisitData(visitId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/visits/${visitId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) throw new Error('加载访视数据失败');

      const visit = await response.json();
      this.currentVisit = visit;

      // 填充表单数据
      this.fillFormData(visit);
    } catch (error) {
      console.error('加载访视数据失败:', error);
      alert('加载访视数据失败');
    }
  },

  // 填充表单数据
  fillFormData(visit) {
    // 体格检查
    if (visit.physical_exam) {
      const pe = visit.physical_exam;
      this.setInputValue('pe-height', pe.height);
      this.setInputValue('pe-weight', pe.weight);
      this.setInputValue('pe-sbp', pe.systolic_bp);
      this.setInputValue('pe-dbp', pe.diastolic_bp);
      this.setInputValue('pe-hr', pe.heart_rate);
      this.setInputValue('pe-waist', pe.waist_circumference);
      this.setInputValue('pe-hip', pe.hip_circumference);
      this.calculateBMI();
      this.calculateWHR();
    }

    // 实验室检查
    if (visit.lab_results) {
      const lab = visit.lab_results;
      this.setInputValue('lab-fbg', lab.fasting_glucose);
      this.setInputValue('lab-ppg', lab.postprandial_glucose);
      this.setInputValue('lab-hba1c', lab.hba1c);
      this.setInputValue('lab-tc', lab.total_cholesterol);
      this.setInputValue('lab-tg', lab.triglycerides);
      this.setInputValue('lab-hdl', lab.hdl_cholesterol);
      this.setInputValue('lab-ldl', lab.ldl_cholesterol);
      this.setInputValue('lab-alt', lab.alt);
      this.setInputValue('lab-ast', lab.ast);
      this.setInputValue('lab-cr', lab.creatinine);
      this.setInputValue('lab-bun', lab.bun);
    }

    // 更多数据填充...
  },

  // 设置输入值
  setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input && value !== null && value !== undefined) {
      input.value = value;
    }
  },

  // 收集表单数据
  collectFormData() {
    return {
      physical_exam: {
        height: this.getInputValue('pe-height'),
        weight: this.getInputValue('pe-weight'),
        systolic_bp: this.getInputValue('pe-sbp'),
        diastolic_bp: this.getInputValue('pe-dbp'),
        heart_rate: this.getInputValue('pe-hr'),
        waist_circumference: this.getInputValue('pe-waist'),
        hip_circumference: this.getInputValue('pe-hip')
      },
      lab_results: {
        fasting_glucose: this.getInputValue('lab-fbg'),
        postprandial_glucose: this.getInputValue('lab-ppg'),
        hba1c: this.getInputValue('lab-hba1c'),
        total_cholesterol: this.getInputValue('lab-tc'),
        triglycerides: this.getInputValue('lab-tg'),
        hdl_cholesterol: this.getInputValue('lab-hdl'),
        ldl_cholesterol: this.getInputValue('lab-ldl'),
        alt: this.getInputValue('lab-alt'),
        ast: this.getInputValue('lab-ast'),
        creatinine: this.getInputValue('lab-cr'),
        bun: this.getInputValue('lab-bun')
      },
      comorbidity: {
        hypertension: document.getElementById('cm-hypertension')?.checked || false,
        dyslipidemia: document.getElementById('cm-dyslipidemia')?.checked || false,
        chd: document.getElementById('cm-chd')?.checked || false,
        stroke: document.getElementById('cm-stroke')?.checked || false,
        ckd: document.getElementById('cm-ckd')?.checked || false,
        retinopathy: document.getElementById('cm-retinopathy')?.checked || false,
        neuropathy: document.getElementById('cm-neuropathy')?.checked || false,
        diabetic_foot: document.getElementById('cm-diabetic-foot')?.checked || false,
        other: document.getElementById('cm-other')?.checked || false,
        other_description: document.getElementById('cm-other-desc')?.value || ''
      },
      medications: this.collectMedications(),
      cost_indicator: {
        drug_cost: this.getInputValue('cost-drug'),
        exam_cost: this.getInputValue('cost-exam'),
        hospital_cost: this.getInputValue('cost-hospital'),
        other_cost: this.getInputValue('cost-other')
      },
      questionnaires: {
        phq9: this.collectPHQ9(),
        gad7: this.collectGAD7()
      },
      lifestyle: {
        diet_score: parseInt(document.getElementById('diet-score')?.textContent || 0),
        exercise_score: parseInt(document.getElementById('exercise-score')?.textContent || 0),
        meal_records: this.collectMealRecords(),
        bad_habits: this.collectBadHabits()
      }
    };
  },

  // 获取输入值
  getInputValue(id) {
    const input = document.getElementById(id);
    if (!input || !input.value) return null;
    return parseFloat(input.value) || input.value;
  },

  // 收集药物数据
  collectMedications() {
    const medications = [];
    const container = document.getElementById('medication-list');
    if (!container) return medications;

    container.querySelectorAll('.border').forEach(medDiv => {
      const name = medDiv.querySelector('.med-name')?.value;
      const dosage = medDiv.querySelector('.med-dosage')?.value;
      const frequency = medDiv.querySelector('.med-frequency')?.value;

      if (name) {
        medications.push({ name, dosage, frequency });
      }
    });

    return medications;
  },

  // 收集PHQ-9数据
  collectPHQ9() {
    const answers = [];
    for (let i = 0; i < 9; i++) {
      const selected = document.querySelector(`input[name="phq9-q${i}"]:checked`);
      answers.push(selected ? parseInt(selected.value) : null);
    }
    return {
      answers,
      total_score: parseInt(document.getElementById('phq9-score')?.textContent || 0)
    };
  },

  // 收集GAD-7数据
  collectGAD7() {
    const answers = [];
    for (let i = 0; i < 7; i++) {
      const selected = document.querySelector(`input[name="gad7-q${i}"]:checked`);
      answers.push(selected ? parseInt(selected.value) : null);
    }
    return {
      answers,
      total_score: parseInt(document.getElementById('gad7-score')?.textContent || 0)
    };
  },

  // 收集膳食记录
  collectMealRecords() {
    const records = [];
    for (let i = 0; i < 4; i++) {
      const food = document.getElementById(`meal-${i}-food`)?.value;
      const amount = document.getElementById(`meal-${i}-amount`)?.value;
      if (food) {
        records.push({ meal_type: ['breakfast', 'lunch', 'dinner', 'snack'][i], food, amount });
      }
    }
    return records;
  },

  // 收集不良饮食习惯
  collectBadHabits() {
    const habits = [];
    for (let i = 1; i <= 8; i++) {
      if (document.getElementById(`meal-habit-${i}`)?.checked) {
        habits.push(i);
      }
    }
    return habits;
  }
};

// 显示新建访视模态框
function showNewVisitModal() {
  if (!VisitEntry.currentPatient) {
    alert('请先选择患者');
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
    const response = await fetch(`${API_BASE_URL}/api/patients/${VisitEntry.currentPatient.id}/visits`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        visit_type: visitType,
        visit_date: visitDate,
        status: 'draft'
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '创建访视失败');
    }

    const visit = await response.json();
    VisitEntry.currentVisit = visit;

    // 更新访视信息显示
    document.getElementById('entry-visit-type').textContent = {
      'baseline': '基线访视',
      'M6': '6个月随访',
      'M12': '12个月随访',
      'M18': '18个月随访',
      'M24': '24个月随访'
    }[visitType] || visitType;
    document.getElementById('entry-visit-date').textContent = visitDate;

    // 隐藏提示，显示表单
    document.getElementById('entry-no-visit-tip').style.display = 'none';
    document.getElementById('entry-form-area').style.display = 'block';

    closeNewVisitModal();
    alert('访视创建成功，可以开始录入数据');
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
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');

  // 更新tab内容
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.add('hidden');
  });
  document.getElementById(`tab-${tabName}`).classList.remove('hidden');
}

// 保存访视数据
async function saveVisitData(status) {
  try {
    const data = VisitEntry.collectFormData();
    data.status = status;

    const response = await fetch(`${API_BASE_URL}/api/visits/${VisitEntry.currentVisit.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) throw new Error('保存失败');

    alert(status === 'draft' ? '草稿已保存' : '已提交审核');
    showPage('patients', document.querySelectorAll('.sidebar-item')[1]);
  } catch (error) {
    console.error('保存失败:', error);
    alert('保存失败，请重试');
  }
}

// 页面加载时初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => VisitEntry.init());
} else {
  VisitEntry.init();
}

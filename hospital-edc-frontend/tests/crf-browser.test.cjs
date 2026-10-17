// Requires Playwright and a local browser; tests use synthetic data and stubbed HTTP only.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');

async function entryPage(t) {
  const browser = await chromium.launch({headless: true,
    ...(process.env.EDC_TEST_BROWSER ? {executablePath: process.env.EDC_TEST_BROWSER} : {})});
  t.after(() => browser.close());
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('http://edc.test/**', route => route.fulfill({contentType: 'text/html', body:
    '<html><head><meta charset="utf-8"><style>.hidden{display:none}input,select{display:block}</style></head><body><div id="page-entry">' +
    fs.readFileSync(path.join(root, 'pages/visit-entry.html'), 'utf8') + '</div></body></html>'}));
  await page.goto('http://edc.test/');
  await page.addScriptTag({path: path.join(root, 'js/config.js')});
  await page.evaluate(() => {window.showToast = () => {};});
  await page.addScriptTag({path: path.join(root, 'js/visit-entry.js')});
  await page.evaluate(() => {
    VisitEntry.currentPatient = {id: 1, patient_code: 'TEST-1', gender: 'female', study_group: 'usual_weekly'};
    VisitEntry.currentVisit = {id: 1, status: 'draft'};
    VisitEntry.fillForms({});
    document.getElementById('entry-form-area').style.display = 'block';
    window.sent = [];
    window.api = async (method, url, payload) => { window.sent.push({method, url, payload}); return {}; };
  });
  t.after(() => assert.deepEqual(errors, []));
  return page;
}

test('CRF fields, all medication columns and five costs survive load/save; empty VAS stays empty', async t => {
  const page = await entryPage(t);
  const payload = await page.evaluate(() => {
    VisitEntry.fillForms({
      lab_results: {egfr: 92.4, ua: 333.2, test_date: '2026-10-12'},
      comorbidity: {hypertension: 1, hypertension_date: '2020/02', hypertension_cause: '测试病因', angina: 0, dr_macular: true},
      cost_indicators: {drug_cost: 10.01, lab_cost: 20.02, service_cost: 30.03, supply_cost: 40.04, other_cost: 50.05, crf_version: 1},
      followup_safety: {hypoglycemia: 2, nocturnal: true, allergy: true},
      medications: [{drug_name: '测试药物"<b>', treatment_type: '糖尿病', route: '皮下注射', dose: '1单位',
                      frequency: '每周一次', start_date: '2026-01-01', end_date: '2026-09-01', is_ongoing: false}],
    });
    return VisitEntry.collectFormData();
  });
  assert.equal(payload.lab_results.egfr, 92.4);
  assert.equal(payload.lab_results.ua, 333.2);
  assert.equal(payload.comorbidity.hypertension_cause, '测试病因');
  assert.equal(payload.comorbidity.angina, 0);
  assert.equal(payload.cost_indicators.supply_cost, 40.04);
  assert.equal(payload.followup_safety.nocturnal, true);
  assert.equal(payload.medications.length, 1);
  assert.equal(payload.medications[0].drug_name, '测试药物"<b>');
  assert.equal(payload.medications[0].route, '皮下注射');
  assert.equal(payload.medications[0].start_date, '2026-01-01');
  assert.equal(payload.medications[0].is_ongoing, false);
  assert.equal(payload.questionnaires.eq5d.eq_vas_score, null);
  assert.match(await page.locator('#cost-total').innerText(), /150.15/);
  await page.evaluate(() => VisitEntry.clearForms());
  assert.equal(await page.locator('#cm-hypertension_date').inputValue(), '');
  assert.equal(await page.locator('#cm-hypertension').inputValue(), '');
  assert.equal(await page.locator('#lab-test-date').inputValue(), '');
});

test('DTSQ uses per-question response labels and original question order, never a made-up total', async t => {
  const page = await entryPage(t);
  const data = await page.evaluate(() => {
    VisitEntry.setRadio('dtsq-q1', 5);
    VisitEntry.setRadio('dtsq-q7', 4);
    VisitEntry.setRadio('dtsq-q8', 2);
    document.getElementById('dtsq-open-text').value = '建议';
    return {payload: VisitEntry.collectDTSQ(), text: document.getElementById('dtsq-questions').textContent,
            answered: document.getElementById('dtsq-score').textContent};
  });
  assert.equal(data.payload.q2, 5);
  assert.equal(data.payload.q8, 4); // storage q8 is CRF Q9
  assert.equal(data.payload.q9, 2); // storage q9 is CRF Q10
  assert.equal(data.payload.dtsq_open_text, '建议');
  assert.equal(data.answered, '3');
  assert.match(data.text, /完全无效/);
  assert.match(data.text, /极度担心/);
  assert.match(data.text, /非常困难/);
  assert.ok(data.text.indexOf('8. 您对目前') < data.text.indexOf('9. 您对治疗方案的费用'));
});

test('legacy cost and DTSQ remain untouched until reviewed; supplementary forms not silently overwritten', async t => {
  const page = await entryPage(t);
  await page.evaluate(async () => {
    VisitEntry.fillForms({cost_indicators: {service_cost: 888.25}, questionnaires: {dtsq: {q1: 4}}});
    await VisitEntry.saveAllForms(false);
  });
  let sent = await page.evaluate(() => window.sent);
  assert.ok(!sent.some(x => x.url.endsWith('/cost-indicators')));
  assert.ok(!sent.some(x => x.payload?.questionnaire_type === 'dtsq'));
  assert.ok(!sent.some(x => /lifestyle|meal-records/.test(x.url)));
  assert.equal(await page.locator('#cost-service').inputValue(), '888.25');
  await page.evaluate(async () => {
    document.getElementById('cost-reviewed').checked = true;
    document.getElementById('dtsq-reviewed').checked = true;
    await VisitEntry.saveAllForms(false);
  });
  sent = await page.evaluate(() => window.sent);
  assert.ok(sent.some(x => x.url.endsWith('/cost-indicators') && x.payload.crf_version === 1));
  assert.ok(sent.some(x => x.payload?.questionnaire_type === 'dtsq' && x.payload.crf_version === 1));
});

test('weekly board escapes center names, handles failure and invalidates requests after leaving', async t => {
  const page = await entryPage(t);
  await page.evaluate(() => {
    document.body.insertAdjacentHTML('beforeend', '<div id="page-dashboard" class="active"><div id="weekly-entry-panel"></div></div>');
    window.getToken = () => 'synthetic';
    window.api = async () => ({week_start: '2026-10-12', week_end: '2026-10-18', generated_at: '2026-10-12T12:00:00+08:00',
      groups: {usual_weekly: '常规治疗+周制剂'}, total: 2,
      items: [{center_code:'T1', center_name:'<img src=x onerror=alert(1)>', groups:{usual_weekly:2}, unassigned:0,total:2}]});
  });
  await page.addScriptTag({path: path.join(root, 'js/app.js')});
  await page.evaluate(() => WeeklyEntry.refresh());
  assert.equal(await page.locator('#weekly-entry-panel img').count(), 0);
  assert.match(await page.locator('#weekly-entry-panel').innerText(), /本周合计 2 人/);
  await page.evaluate(async () => {
    let resolve;
    window.api = () => new Promise(r => {resolve = r;});
    const request = WeeklyEntry.refresh();
    WeeklyEntry.stop();
    resolve({});
    await request;
  });
  assert.match(await page.locator('#weekly-entry-panel').innerText(), /本周合计 2 人/);
  await page.evaluate(async () => {window.api = async () => {throw new Error('offline');}; await WeeklyEntry.refresh();});
  assert.match(await page.locator('#weekly-entry-panel').innerText(), /更新失败/);
});

test('adding a medication through the visible button works', async t => {
  const page = await entryPage(t);
  await page.evaluate(() => {
    document.querySelectorAll('.tab-panel').forEach(e => e.classList.add('hidden'));
    document.getElementById('tab-medication').classList.remove('hidden');
  });
  await page.getByRole('button', {name: '添加药物', exact: true}).click();
  assert.equal(await page.locator('.medication-row').count(), 1);
});


test('every panel saves without leaving; age and PHQ/GAD are persisted; partial medication is retained', async t => {
  const page = await entryPage(t);
  await page.evaluate(() => {
    VisitEntry.setupPageSaveButtons();
    window.api = async (method, url, payload) => {
      window.sent.push({method, url, payload});
      return url.startsWith('/api/patients/') ? {...VisitEntry.currentPatient, ...payload} : {};
    };
    document.querySelectorAll('.tab-panel').forEach(e => e.classList.add('hidden'));
    document.getElementById('tab-basic').classList.remove('hidden');
  });
  assert.equal(await page.locator('[data-page-save]').count(), await page.locator('.tab-panel').count());
  assert.equal(await page.getByRole('button', {name: '抑郁量表 PHQ-9', exact: true}).isVisible(), true);
  assert.equal(await page.getByRole('button', {name: '焦虑量表 GAD-7', exact: true}).isVisible(), true);
  await page.locator('#bp-age').fill('56');
  await page.evaluate(() => {
    VisitEntry.setRadio('phq9-q0', 2);
    VisitEntry.setRadio('gad7-q0', 1);
    VisitEntry.addMedication({treatment_type: '糖尿病', dose: '1单位'});
  });
  await page.locator('#tab-basic [data-page-save]').click();
  await page.evaluate(() => VisitEntry._saveQueue);
  const sent = await page.evaluate(() => window.sent);
  assert.ok(sent.some(x => x.method === 'PUT' && x.payload.age === 56));
  assert.ok(sent.some(x => x.payload?.questionnaire_type === 'phq9' && x.payload.q1 === 2));
  assert.ok(sent.some(x => x.payload?.questionnaire_type === 'gad7' && x.payload.q1 === 1));
  assert.ok(sent.some(x => x.payload?.medications?.[0]?.dose === '1单位'));
  assert.equal(await page.locator('#tab-basic').isVisible(), true);
  await page.locator('#bp-age').fill('57');
  assert.equal(await page.locator('#bp-age').inputValue(), '57');
});

test('cost photo upload uses current visit and does not require numeric costs', async t => {
  const page = await entryPage(t);
  await page.route('**/api/patients/1/images?visit_id=1', route => route.fulfill({contentType: 'application/json', body: JSON.stringify({id: 9})}));
  await page.evaluate(() => {
    document.querySelectorAll('.tab-panel').forEach(e => e.classList.add('hidden'));
    document.getElementById('tab-cost').classList.remove('hidden');
  });
  await page.locator('#cost-photo-files').setInputFiles({name: 'cost.png', mimeType: 'image/png', buffer: Buffer.from('fixture-upload')});
  const request = page.waitForRequest(r => r.method() === 'POST' && r.url().includes('images?visit_id=1'));
  await page.getByRole('button', {name: '上传费用照片', exact: true}).click();
  assert.match((await request).headers()['content-type'], /multipart\/form-data/);
  await page.waitForFunction(() => !VisitEntry._uploadingPhotos);
  assert.match(await page.locator('#cost-photo-status').innerText(), /1/);
  assert.equal(await page.locator('#cost-drug').inputValue(), '');
});

test('failed save stays on page and never reports a saved draft', async t => {
  const page = await entryPage(t);
  const result = await page.evaluate(async () => {
    const notices = [];
    window.showToast = text => notices.push(text);
    window.api = async (method, url) => { if (url.endsWith('/lab-results')) throw new Error('测试连接失败'); return {}; };
    document.getElementById('pe-height').value = '165';
    await saveVisitData('draft');
    return {notices, height: document.getElementById('pe-height').value, status: VisitEntry.currentVisit.status};
  });
  assert.equal(result.height, '165');
  assert.equal(result.status, 'draft');
  assert.ok(result.notices.some(x => x.includes('保存失败')));
  assert.ok(!result.notices.some(x => x.includes('草稿已保存')));
});

test('Second Hospital PHQ-9/GAD-7 wording, choices, symptoms and totals match supplied form', async t => {
  const page = await entryPage(t);
  const result = await page.evaluate(async () => {
    const questions = id => Array.from(document.querySelectorAll(`#${id} > div > div:first-child`)).map(e => e.textContent.trim());
    const phq = questions('phq9-questions');
    const gad = questions('gad7-questions');
    const choices = id => Array.from(document.querySelector(`#${id} > div`).querySelectorAll('label .text-xs')).map(e => e.textContent);
    const symptomOptions = Array.from(document.querySelectorAll('[name="phq9-symptoms"]')).map(e => e.value);
    VisitEntry.fillForms({questionnaires: {phq9: {q1: 2, phq9_symptoms: '头晕,失眠,其他'}}});
    const loaded = VisitEntry.collectFormData().questionnaires.phq9;
    for (let i = 0; i < 9; i++) VisitEntry.setRadio(`phq9-q${i}`, 3);
    for (let i = 0; i < 7; i++) VisitEntry.setRadio(`gad7-q${i}`, 3);
    const totals = [document.getElementById('phq9-score').textContent, document.getElementById('gad7-score').textContent];
    await VisitEntry.saveAllForms(false);
    const saved = window.sent.filter(x => x.url.endsWith('/questionnaire'));
    document.querySelectorAll('[name="phq9-symptoms"]').forEach(e => e.checked = false);
    document.querySelectorAll('.phq9-radio').forEach(e => e.checked = false);
    await VisitEntry.saveAllForms(false);
    const cleared = window.sent.filter(x => x.payload?.questionnaire_type === 'phq9').at(-1).payload;
    VisitEntry.clearForms();
    return {phq, gad, choices: [choices('phq9-questions'), choices('gad7-questions')], symptomOptions, loaded, totals, saved, cleared,
      symptomsAfterClear: document.querySelectorAll('[name="phq9-symptoms"]:checked').length,
      levels: document.querySelectorAll('#phq9-level, #gad7-level').length};
  });
  assert.deepEqual(result.phq, [
    '1. 做事时提不起劲或没有兴趣','2. 感到心情低落，沮丧或绝望','3. 入睡困难、睡不安稳或睡眠过多',
    '4. 感到疲惫或没有活力','5. 食欲不振或吃太多','6. 感觉自己很糟，觉得自己很失败或让自己失望',
    '7. 做事专注有困难，例如阅读报纸和看电视时','8. 感到说话速度缓慢到别人已察觉？或正好相反，烦躁或坐立不安，动来动去的情况更胜于平常',
    '9. 有不如死掉或用某种方式伤害自己的念头']);
  assert.deepEqual(result.gad, ['1. 感到紧张、焦虑或急切','2. 不能停止或控制担忧','3. 对各种各样的事情担忧过多','4. 很难放松下来','5. 由于不安而无法静坐','6. 变得容易急躁','7. 感到似乎有可怕的事情发生而害怕']);
  assert.deepEqual(result.choices, [['完全不会','好几天','一半以上的天数','几乎每天'], ['完全不会','好几天','超过一周','几乎每天']]);
  assert.deepEqual(result.symptomOptions, ['头晕','头疼','失眠','脑血管疾病','心慌','胸闷','胸痛','其他']);
  assert.equal(result.loaded.phq9_symptoms, '头晕,失眠,其他');
  assert.equal(result.loaded.q1, 2);
  assert.deepEqual(result.totals, ['27','21']);
  assert.ok(result.saved.some(x => x.payload.questionnaire_type === 'phq9' && x.payload.phq9_symptoms === '头晕,失眠,其他'));
  assert.equal(result.cleared.phq9_symptoms, null);
  assert.equal(result.cleared.q1, null);
  assert.equal(result.symptomsAfterClear, 0);
  assert.equal(result.levels, 0);
});

test('correction shortcuts, custom reason, role/state boundaries and stale target protection', async t => {
  const page = await entryPage(t);
  await page.addScriptTag({path: path.join(root, 'js/qc-bar.js')});
  await page.evaluate(() => {
    window.api = async (method, url, payload) => {
      if (method === 'GET') return [];
      window.sent.push({method, url, payload});
      if (window.rejectCorrection) throw new Error('仅待审核访视可自行撤回');
      return {status: 'draft'};
    };
    VisitEntry.onVisitSelect = async id => { VisitEntry.currentVisit = {id, status: 'draft'}; VisitEntry.updateEditability(); };
  });
  for (const role of ['researcher','center_admin','main_admin','qc']) {
    for (const status of ['draft','submitted','qc_passed','signed','locked']) {
      await page.evaluate(async ({role,status}) => {setUser({role}); VisitEntry.currentVisit = {id: 1, status}; await QcBar.refresh();}, {role,status});
      assert.equal(await page.locator('#qc-btn-withdraw').isVisible(), status === 'submitted' && role !== 'qc');
      assert.equal(await page.locator('#qc-btn-reopen').isVisible(), role === 'main_admin' && ['qc_passed','signed'].includes(status));
      assert.equal(await page.locator('#qc-btn-unlock').isVisible(), role === 'main_admin' && status === 'locked');
    }
  }
  await page.evaluate(async () => {setUser({role:'researcher'}); VisitEntry.currentVisit = {id:1,status:'submitted'}; await QcBar.refresh();});
  await page.locator('#qc-btn-withdraw').click();
  await page.locator('#correction-submit').click();
  assert.match(await page.locator('#correction-error').innerText(), /请选择/);
  assert.equal(await page.evaluate(() => sent.length), 0);
  await page.locator('#correction-reason').selectOption('信息填错，需要更正');
  assert.equal(await page.locator('#correction-detail-wrap').isVisible(), false);
  await page.locator('#correction-submit').click();
  await page.waitForFunction(() => !QcBar._reasonBusy);
  assert.deepEqual(await page.evaluate(() => sent.at(-1)), {method:'POST',url:'/api/visits/1/withdraw-submission',payload:{reason:'信息填错，需要更正'}});
  assert.equal(await page.evaluate(() => VisitEntry.currentVisit.status), 'draft');
  for (const action of ['reopen','unlock']) {
    await page.evaluate(action => {VisitEntry.currentVisit = {id:1,status:action==='unlock'?'locked':'signed'}; QcBar[action]();}, action);
    await page.locator('#correction-reason').selectOption('other');
    await page.locator('#correction-detail').fill('  ');
    await page.locator('#correction-submit').click();
    assert.match(await page.locator('#correction-error').innerText(), /填写其他原因/);
    await page.locator('#correction-detail').fill('复核后更正身高');
    await page.locator('#correction-submit').click();
    await page.waitForFunction(() => !QcBar._reasonBusy);
    assert.equal(await page.evaluate(() => sent.at(-1).url), '/api/visits/1/'+action);
  }
  await page.evaluate(() => {VisitEntry.currentVisit = {id:1,status:'submitted'}; QcBar.withdraw();});
  await page.locator('#correction-reason').selectOption('误点提交，尚未填完');
  const before = await page.evaluate(() => sent.length);
  await page.evaluate(() => {VisitEntry.currentVisit = {id:2,status:'submitted'};});
  await page.locator('#correction-submit').click();
  assert.match(await page.locator('#correction-error').innerText(), /已切换/);
  assert.equal(await page.evaluate(() => sent.length), before);
  await page.getByRole('button',{name:'取消',exact:true}).last().click();
  await page.evaluate(() => {QcBar.withdraw(); window.rejectCorrection = true;});
  await page.locator('#correction-reason').selectOption('选项点错，需要重选');
  await page.locator('#correction-submit').click();
  await page.waitForFunction(() => !QcBar._reasonBusy);
  assert.match(await page.locator('#correction-error').innerText(), /仅待审核/);
  assert.equal(await page.locator('#modal-correction').isVisible(), true);
  assert.equal(await page.evaluate(() => VisitEntry.currentVisit.status), 'submitted');
});

test('disease groups and questionnaire order preserve other text and historical flags', async t => {
  const page = await entryPage(t);
  assert.equal(await page.locator('#tab-comorbidity fieldset[data-disease]').count(), 9);
  for (const key of ['hypertension','ckd','chd','angina','mi','stroke','dr','dn','df']) {
    const group = page.locator(`[data-disease="${key}"]`);
    assert.equal(await group.locator(`#cm-${key}`).count(), 1);
    assert.equal(await group.locator(`#cm-${key}_date`).count(), 1);
  }
  const tabs = await page.locator('.tab-btn').evaluateAll(nodes => nodes.map(n => n.getAttribute('onclick').match(/switchEntryTab\('([^']+)'\)/)?.[1]));
  assert.deepEqual(tabs.filter(x => ['eq5d','dtsq','phq9','gad7'].includes(x)), ['eq5d','dtsq','phq9','gad7']);
  const data = await page.evaluate(() => {
    VisitEntry.fillForms({comorbidity: {dr_macular: true, other_conditions: '其他病情'}});
    return VisitEntry.collectFormData().comorbidity;
  });
  assert.equal(data.other_conditions, '其他病情');
  assert.equal(data.dr_macular, true);
  assert.equal(await page.locator('#tab-comorbidity input[type=checkbox]').count(), 0);
  await page.evaluate(() => { VisitEntry.clearForms(); VisitEntry.fillForms({}); });
  assert.equal(await page.locator('#cm-other_conditions').inputValue(), '');
  assert.equal(await page.evaluate(() => VisitEntry.collectFormData().comorbidity.dr_macular), false);
});

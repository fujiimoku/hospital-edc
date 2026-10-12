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
    '<html><head><style>.hidden{display:none}input,select{display:block}</style></head><body><div id="page-entry">' +
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

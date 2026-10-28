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
  await page.addStyleTag({path:path.join(root,'css/main.css')});
  await page.addScriptTag({path: path.join(root, 'js/config.js')});
  await page.evaluate(() => {window.showToast = () => {};});
  await page.addScriptTag({path: path.join(root, 'js/patient-workflow.js')});
  await page.addScriptTag({path: path.join(root, 'js/entry-keyboard.js')});
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


test('unchanged saves and concurrent queued saves do not resend completed forms', async t => {
  const page=await entryPage(t);
  const result=await page.evaluate(async()=>{
    VisitEntry.savePatientProfile=async()=>true;
    window.api=async(method,url,payload)=>{sent.push({method,url,payload});await new Promise(r=>setTimeout(r,60));return {};};
    const start=performance.now();await VisitEntry.saveAllForms(false);const first={count:sent.length,ms:performance.now()-start};
    sent.length=0;const secondStart=performance.now();
    await Promise.all([VisitEntry.saveAllForms(false),VisitEntry.saveAllForms(false)]);
    return {first,repeat:sent.length,ms:performance.now()-secondStart};
  });
  console.log('save measurement',result);
  assert.equal(result.repeat,0);
});

test('Enter skips computed fields; IME and textarea Enter remain ordinary input', async t=>{
  const page=await entryPage(t);
  await page.locator('#pe-height').focus();await page.keyboard.type('170');await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'pe-weight');
  await page.keyboard.type('65');await page.keyboard.press('Enter');
  assert.notEqual(await page.evaluate(()=>document.activeElement.id),'pe-bmi');
  await page.locator('#pe-height').focus();
  await page.locator('#pe-height').dispatchEvent('keydown',{key:'Enter',isComposing:true});
  assert.equal(await page.evaluate(()=>document.activeElement.id),'pe-height');
});

test('questionnaire focus defaults are not answers; Enter confirms and moves one question', async t=>{
  const page=await entryPage(t);
  await page.evaluate(()=>{window.getUser=()=>({role:'qc'});switchEntryTab('phq9');});
  assert.equal(await page.evaluate(()=>document.activeElement.name),'phq9-q0');
  assert.equal(await page.evaluate(()=>document.activeElement.value),'0');
  assert.equal(await page.locator('#phq9-questions input:checked').count(),0);
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('input[name="phq9-q0"]:checked').inputValue(),'0');
  assert.equal(await page.evaluate(()=>document.activeElement.name),'phq9-q1');
  assert.equal(await page.locator('#phq9-questions input:checked').count(),1);
  await page.evaluate(()=>switchEntryTab('dtsq'));
  assert.equal(await page.evaluate(()=>document.activeElement.value),'5');
  assert.equal(await page.locator('#dtsq-questions input:checked').count(),0);
  await page.keyboard.press('ArrowLeft');await page.keyboard.press('Enter');
  assert.equal(await page.locator('input[name="dtsq-q0"]:checked').inputValue(),'4');
  assert.equal(await page.evaluate(()=>document.activeElement.name),'dtsq-q1');
  await page.evaluate(()=>switchEntryTab('eq5d'));
  assert.equal(await page.evaluate(()=>document.activeElement.value),'1');
  assert.equal(await page.locator('#eq5d-questions input:checked').count(),0);
  await page.evaluate(()=>{VisitEntry.setRadio('phq9-q0',2);switchEntryTab('phq9');});
  assert.equal(await page.evaluate(()=>document.activeElement.value),'2');
  await page.evaluate(()=>switchEntryTab('gad7'));
  assert.equal(await page.evaluate(()=>document.activeElement.value),'0');
  assert.equal(await page.locator('#gad7-questions input:checked').count(),0);
  assert.equal(await page.evaluate(()=>getComputedStyle(document.activeElement.closest('label')).outlineStyle),'solid');
  await page.locator('#tab-gad7').screenshot({path:path.join(root,'../artifacts/keyboard-focus-20261028.png')});
  await page.evaluate(()=>switchEntryTab('dtsq'));
  const text=page.locator('#tab-dtsq textarea').first();
  await text.focus();await page.keyboard.type('first');await page.keyboard.press('Enter');
  assert.equal(await text.inputValue(),'first\n');
  await page.keyboard.press('Control+Enter');
  assert.notEqual(await page.evaluate(()=>document.activeElement.tagName),'TEXTAREA');
});

test('busy submission is visible, rejects double click and keeps submitted controls readonly', async t=>{
  const page=await entryPage(t);
  await page.evaluate(()=>{
    setUser({role:'researcher'});
    VisitEntry.validateForSubmit=()=>[];
    VisitEntry.saveAllForms=()=>new Promise(resolve=>window.finishSave=resolve);
    window.pendingSubmit=saveVisitData('submitted');
  });
  assert.match(await page.locator('#edc-operation-status').textContent(),/正在保存并提交/);
  assert.equal(await page.locator('button[onclick="saveVisitData(\'submitted\')"]').isDisabled(),true);
  await page.evaluate(async()=>{await saveVisitData('submitted');finishSave(true);await pendingSubmit;});
  assert.equal(await page.evaluate(()=>sent.filter(x=>x.url.endsWith('/submit')).length),1);
  assert.equal(await page.locator('button[onclick="saveVisitData(\'submitted\')"]').isDisabled(),true);
  assert.equal(await page.locator('#edc-operation-status').count(),0);
});

test('photo list fetches thumbnails and requests the original only on opening', async t=>{
  const page=await entryPage(t);
  const requests=[];
  await page.route('**/api/patients/1/images/9/*',route=>{
    requests.push(route.request().url().split('/').at(-1));
    return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7WQAAAAASUVORK5CYII=','base64')});
  });
  await page.evaluate(async()=>{
    const box=document.getElementById('cost-photo-list'),item={id:9,filename:'test.png'};
    box.innerHTML=PhotoPreview.thumbnail(item);await PhotoPreview.load(box,1,[item]);
  });
  assert.deepEqual(requests,['thumbnail']);
  await page.evaluate(()=>document.querySelector('[data-private-image="9"]').click());
  await page.waitForFunction(()=>document.querySelector('dialog img')?.src.startsWith('blob:'));
  assert.deepEqual(requests,['thumbnail','download']);
  await page.locator('dialog button').click();
  assert.equal(await page.locator('dialog').count(),0);
});

test('failed form remains retryable and edit during save is not marked saved', async t=>{
  const page=await entryPage(t);
  const result=await page.evaluate(async()=>{
    VisitEntry.savePatientProfile=async()=>true;
    let fail=true;
    window.api=async(method,url,payload)=>{sent.push(url);if(url.endsWith('/lab-results')&&fail)throw Error('offline');return {};};
    const first=await VisitEntry.saveAllForms(false);sent.length=0;fail=false;
    const second=await VisitEntry.saveAllForms(false);const retry=[...sent];
    document.getElementById('pe-height').value='170';VisitEntry.markDirty();
    window.api=async()=>{document.getElementById('pe-height').value='171';VisitEntry.markDirty();return {};};
    await VisitEntry.saveAllForms(false);
    return {first,second,retry,dirty:VisitEntry._dirty};
  });
  assert.equal(result.first,false);assert.equal(result.second,true);
  assert.ok(result.retry.some(u=>u.endsWith('/lab-results')));
  assert.ok(!result.retry.some(u=>u.endsWith('/physical-exam')));
  assert.equal(result.dirty,true);
});

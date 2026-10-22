const {test} = require('node:test');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const read = p => fs.readFileSync(path.join(root,p),'utf8');
async function fixture(t, entry=false) {
  const browser = await chromium.launch({headless:true,executablePath:process.env.EDC_TEST_BROWSER});
  t.after(()=>browser.close());
  const context=await browser.newContext();
  const errors=[];
  context.on('page',page=>page.on('pageerror',e=>errors.push(e.message)));
  t.after(()=>assert.deepEqual(errors,[]));
  await context.route('http://edc.test/**',route=>{
    const url=new URL(route.request().url());
    if(url.pathname.startsWith('/api/')) {
      const id=Number(url.pathname.match(/patients\/(\d+)/)?.[1] || 0);
      let json={};
      if(url.pathname.endsWith('/visits')) json=[];
      else if(id) json={id,patient_code:`TEST-${id}`,full_name:`测试患者${id}`,gender:'female'};
      return route.fulfill({json});
    }
    const isEntry=entry || url.searchParams.has('patient');
    const scripts=['config','patient-workflow',isEntry?'visit-entry':'patients'];
    return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><style>.hidden{display:none}</style>'+read(`pages/${isEntry?'visit-entry':'patients'}.html`)+
      '<script>window.showToast=()=>{};</script>'+scripts.map(s=>`<script>${read(`js/${s}.js`)}</script>`).join('')});
  });
  const page=await context.newPage();await page.goto('http://edc.test/');
  return page;
}

test('patient tabs inherit login but isolate patient selection, preserve original filters and survive refresh',async t=>{
  const page=await fixture(t);
  await page.evaluate(()=>{
    setToken('synthetic-login');setUser({role:'researcher'});
    sessionStorage.setItem('currentPatient',JSON.stringify({id:1}));
    document.getElementById('patient-search').value='keep-filter';
    renderPatientTable([{id:33,patient_code:'TEST-33',full_name:'测试姓名'}],1);
  });
  const popup=page.waitForEvent('popup');
  await page.getByRole('button',{name:'查看／录入（新标签页）',exact:true}).click();
  const child=await popup;await child.waitForLoadState();
  await child.waitForFunction(()=>document.getElementById('entry-patient-code').textContent==='TEST-33');
  assert.equal(await child.evaluate(()=>getToken()),'synthetic-login');
  assert.equal(await child.evaluate(()=>window.opener),null);
  assert.equal(await page.evaluate(()=>JSON.parse(sessionStorage.getItem('currentPatient')).id),1);
  assert.equal(await page.locator('#patient-search').inputValue(),'keep-filter');
  await child.reload();
  await child.waitForFunction(()=>document.getElementById('entry-patient-code').textContent==='TEST-33');
  assert.match(child.url(),/patient=33/);
});

test('copy previous medications confirms replacement, preserves stopped dates and marks unsaved; failures keep contents',async t=>{
  const page=await fixture(t,true);
  await page.evaluate(()=>{
    setUser({role:'researcher'});
    VisitEntry.currentPatient={id:1}; VisitEntry.currentVisit={id:10,status:'draft'};
    VisitEntry.fillForms({});VisitEntry.addMedication({drug_name:'本次药物'});
    window.api=async()=>({source_visit:{id:9,visit_date:'2026-01-01'},medications:[{drug_name:'上次药物',end_date:'2026-01-02',is_ongoing:false}]});
    window.confirm=()=>false;
  });
  await page.evaluate(()=>VisitEntry.copyPreviousMedications());
  assert.equal(await page.evaluate(()=>VisitEntry.collectMedications()[0].drug_name),'本次药物');
  await page.evaluate(async()=>{window.confirm=()=>true;await VisitEntry.copyPreviousMedications();});
  const copied=await page.evaluate(()=>VisitEntry.collectMedications());
  assert.equal(copied.length,1);assert.equal(copied[0].drug_name,'上次药物');
  assert.equal(copied[0].end_date,'2026-01-02');assert.equal(copied[0].is_ongoing,false);
  assert.match(await page.locator('#tab-medication [data-form-progress]').textContent(),/有修改待保存/);
  await page.evaluate(async()=>{window.api=async()=>{throw new Error('offline')};await VisitEntry.copyPreviousMedications();});
  assert.deepEqual(await page.evaluate(()=>VisitEntry.collectMedications()),copied);
  await page.evaluate(async()=>{window.api=async()=>({});await VisitEntry.saveAllForms(false);});
  assert.equal(await page.evaluate(()=>VisitEntry._dirty),false);
});

test('tracking label restores old value on failed save and does not claim success',async t=>{
  const page=await fixture(t);
  await page.evaluate(()=>{
    renderPatientTable([{id:1,patient_code:'P1',tracking_status:'pending'}],1);
    window.api=async()=>{throw new Error('cannot save')};
  });
  await page.getByLabel('追踪标签').selectOption('completed');
  await page.waitForFunction(()=>document.querySelector('[aria-label="追踪标签"]').value==='pending');
  assert.equal(await page.getByLabel('追踪标签').isEnabled(),true);
});

test('progress dot switches the correct form and QC does not autosave drafts',async t=>{
  const page=await fixture(t,true);
  await page.evaluate(()=>{
    setUser({role:'qc'});VisitEntry.currentVisit={id:1,status:'draft'};
    document.getElementById('entry-form-area').style.display='block';
    VisitEntry.updateFormProgress();VisitEntry.startAutosave();
    window.api=async()=>{throw new Error('QC must not save')};
  });
  await page.locator('[onclick="switchEntryTab(\'medication\')"] [data-progress-dot]').click();
  assert.equal(await page.locator('#tab-medication').isVisible(),true);
  assert.equal(await page.locator('#tab-physical').isVisible(),false);
  assert.equal(await page.locator('.tab-btn.active').count(),1);
  assert.equal(await page.evaluate(()=>VisitEntry._autosaveTimer),null);
});

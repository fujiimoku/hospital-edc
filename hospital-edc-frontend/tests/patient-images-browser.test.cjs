const {test} = require('node:test');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');

async function pageFor(t) {
  const browser = await chromium.launch({headless: true,
    ...(process.env.EDC_TEST_BROWSER ? {executablePath: process.env.EDC_TEST_BROWSER} : {})});
  t.after(() => browser.close());
  const page = await browser.newPage({acceptDownloads: true});
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  t.after(() => assert.deepEqual(errors, []));
  await page.route('http://edc.test/', route => route.fulfill({contentType:'text/html', body:
    '<meta charset="utf-8"><style>.hidden{display:none}</style>' + fs.readFileSync(path.join(root, 'pages/patients.html'), 'utf8')}));
  await page.goto('http://edc.test/');
  await page.addScriptTag({path:path.join(root, 'js/config.js')});
  await page.addScriptTag({path:path.join(root, 'js/patient-workflow.js')});
  await page.addScriptTag({path:path.join(root, 'js/patients.js')});
  await page.evaluate(() => {
    setToken('synthetic-test-token'); setUser({role:'researcher'});
    renderPatientTable([{id:7, patient_code:'TEST-0007', name_initials:'CS', full_name:'测试姓名',
      gender:'female', study_group:'usual_daily', study_subgroup:'daily_insulin', has_submitted:true}], 1);
  });
  return page;
}

test('group selectors show exactly the three supplied options, including confirmed D label', async t => {
  const page = await pageFor(t);
  await page.getByRole('button', {name:'+ 创建患者'}).click();
  const expected = {
    integrated_weekly:['icodec','semaglutide','icodec_semaglutide'],
    integrated_daily:['daily_glp1','daily_insulin','daily_combination'],
    usual_weekly:['icodec','semaglutide','icodec_semaglutide'],
    usual_daily:['daily_glp1','daily_insulin','daily_combination'],
  };
  for (const [group, values] of Object.entries(expected)) {
    await page.selectOption('#cp-group', group);
    assert.deepEqual(await page.locator('#cp-subgroup option').evaluateAll(nodes=>nodes.map(n=>n.value)), ['',...values]);
    await page.selectOption('#cp-subgroup', values[0]);
  }
  assert.match(await page.locator('#cp-group option[value="usual_daily"]').innerText(), /D组：常规诊疗\+周制剂/);
  await page.selectOption('#cp-group', 'integrated_weekly');
  assert.equal(await page.locator('#cp-subgroup').inputValue(), '');
  await page.getByRole('button',{name:'取消',exact:true}).click();
  assert.equal(await page.locator('#cp-subgroup').inputValue(), '');
});

test('submitted patient images upload separately and downloads retain Chinese patient filename', async t => {
  const page = await pageFor(t);
  const entries = [];
  let uploaded = 0;
  const filename = 'D组-测试姓名-TEST-0007-000001.png';
  await page.route('http://edc.test/api/patients/7/images**', async route => {
    assert.equal(route.request().headers().authorization, 'Bearer synthetic-test-token');
    if (route.request().method() === 'POST') {
      uploaded++; entries.push({id:uploaded, filename, size_bytes:68});
      return route.fulfill({status:201, json:entries.at(-1)});
    }
    if (route.request().url().endsWith('/download')) return route.fulfill({body:Buffer.from('synthetic image'),
      headers:{'Content-Type':'image/png','Content-Disposition':"attachment; filename*=utf-8''"+encodeURIComponent(filename)}});
    return route.fulfill({json:{items:entries}});
  });
  assert.equal(await page.getByRole('button',{name:'查看／录入（新标签页）',exact:true}).isEnabled(), true);
  await page.getByRole('button',{name:'图片',exact:true}).click();
  await page.getByText('尚未上传图片',{exact:true}).waitFor();
  await page.setInputFiles('#patient-images-files', {name:'test.png', mimeType:'image/png', buffer:Buffer.from('stub image')});
  await page.getByRole('button',{name:'上传所选图片'}).click();
  await page.locator('#patient-images-list').getByText(filename,{exact:false}).waitFor();
  assert.equal(uploaded,1);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button',{name:'下载',exact:true}).click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(),filename);
});

test('QC can view images; stale image requests do not render for another patient', async t => {
  const page = await pageFor(t);
  await page.evaluate(() => {
    setUser({role:'qc'});
    renderPatientTable([{id:8,patient_code:'QC-1',name_initials:'QC'}],1);
  });
  assert.equal(await page.getByRole('button',{name:'图片',exact:true}).count(),1);
  const result = await page.evaluate(async () => {
    setUser({role:'researcher'});
    patientCacheById[1] = {patient_code:'P1'}; patientCacheById[2] = {patient_code:'P2'};
    let resolveFirst;
    window.api = (method, url) => url.includes('/1/') ? new Promise(resolve=>resolveFirst=resolve) : Promise.resolve({items:[]});
    const first = PatientImages.open(1);
    await PatientImages.open(2);
    resolveFirst({items:[{id:1,filename:'WRONG-PATIENT',size_bytes:1}]});
    await first;
    return document.getElementById('patient-images-modal').textContent;
  });
  assert.match(result,/P2/); assert.doesNotMatch(result,/WRONG-PATIENT/);
});

test('image deletion requires confirmation, preserves failed rows, and refreshes after success', async t => {
  const page = await pageFor(t);
  let entries = [{id:1,filename:'费用照片.png',size_bytes:68}];
  let deletes = 0;
  await page.route('http://edc.test/api/patients/7/images**', route => {
    if (route.request().method() === 'DELETE') {
      deletes++;
      if (deletes === 1) return route.fulfill({status:400,json:{detail:'仅草稿访视可删除费用照片，请先退回更正'}});
      entries = [];
      return route.fulfill({json:{deleted:true,id:1}});
    }
    return route.fulfill({json:{items:entries}});
  });
  await page.getByRole('button',{name:'图片',exact:true}).click();
  const remove = page.getByRole('button',{name:'删除',exact:true});
  await remove.waitFor();
  page.once('dialog', dialog => dialog.dismiss());
  await remove.click();
  assert.equal(deletes,0);
  page.once('dialog', dialog => dialog.accept());
  await remove.click();
  await page.getByText('仅草稿访视可删除费用照片，请先退回更正',{exact:true}).waitFor();
  assert.equal(await remove.count(),1);
  page.once('dialog', dialog => dialog.accept());
  await remove.click();
  await page.getByText('尚未上传图片',{exact:true}).waitFor();
  assert.equal(deletes,2);
  assert.equal(await page.locator('#patient-images-archive').isDisabled(),true);
});

test('visit multi-photo upload stays sequential and clears selection after a partial gateway failure', async t => {
  const page = await pageFor(t);
  await page.addScriptTag({path:path.join(root,'js/visit-entry.js')});
  await page.evaluate(() => {
    window.showToast = message => window.lastToast = message;
    document.body.insertAdjacentHTML('beforeend','<input id="cost-photo-files" type="file" multiple><p id="cost-photo-status"></p><div id="cost-photo-list"></div>');
    VisitEntry.currentPatient = {id:7}; VisitEntry.currentVisit = {id:4,status:'draft'};
  });
  let uploads = 0, active = 0, peak = 0;
  await page.route('http://edc.test/api/patients/7/images**', async route => {
    if (route.request().method() === 'POST') {
      uploads++; active++; peak = Math.max(peak,active);
      await new Promise(resolve=>setTimeout(resolve,10));
      active--;
      if (uploads === 12) return route.fulfill({status:502,contentType:'text/html',body:'Bad gateway'});
      return route.fulfill({status:201,json:{id:uploads}});
    }
    return route.fulfill({json:{items:[{id:1,filename:'已上传.png',size_bytes:68}]}});
  });
  await page.setInputFiles('#cost-photo-files',Array.from({length:20},(_,i)=>({name:`photo-${i}.png`,mimeType:'image/png',buffer:Buffer.from('synthetic')})));
  await page.evaluate(()=>VisitEntry.uploadCostPhotos());
  assert.equal(uploads,12); assert.equal(peak,1);
  assert.equal(await page.locator('#cost-photo-files').inputValue(),'');
  assert.equal(await page.locator('#cost-photo-files').isEnabled(),true);
  assert.match(await page.evaluate(()=>window.lastToast),/已上传 11 张.*502.*仅重新选择/);
  assert.equal(await page.getByRole('button',{name:'删除照片',exact:true}).count(),1);
  await page.evaluate(async()=>{VisitEntry.currentVisit.status='submitted';await VisitEntry.loadCostPhotos();});
  assert.equal(await page.getByRole('button',{name:'删除照片',exact:true}).count(),0);
});

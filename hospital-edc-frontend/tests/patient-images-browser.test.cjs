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
  assert.equal(await page.getByRole('button',{name:'查看／录入',exact:true}).isEnabled(), true);
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

test('QC does not receive image entry; stale image requests do not render for another patient', async t => {
  const page = await pageFor(t);
  await page.evaluate(() => {
    setUser({role:'qc'});
    renderPatientTable([{id:8,patient_code:'QC-1',name_initials:'QC'}],1);
  });
  assert.equal(await page.getByRole('button',{name:'图片',exact:true}).count(),0);
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

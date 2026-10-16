const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function context() {
  const controls = [{ disabled: false, dataset: {} }, { disabled: true, dataset: {} }];
  const ctx = vm.createContext({
    document: { readyState: 'loading', addEventListener() {}, querySelectorAll: () => controls },
    user: { role: 'researcher' }, controls,
    getUser: () => ctx.user, console,
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/visit-entry.js'), 'utf8'), ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/qc-bar.js'), 'utf8'), ctx);
  return ctx;
}

test('reviewed states disable editing; reopening restores only editable fields', () => {
  const ctx = context();
  for (const state of ['submitted', 'qc_passed', 'signed', 'locked']) {
    ctx.state = state;
    vm.runInContext('VisitEntry.currentVisit = {status: state}; VisitEntry.updateEditability()', ctx);
    assert.equal(ctx.controls[0].disabled, true);
    vm.runInContext("VisitEntry.currentVisit.status = 'draft'; VisitEntry.updateEditability()", ctx);
    assert.equal(ctx.controls[0].disabled, false);
    assert.equal(ctx.controls[1].disabled, true); // e.g. calculated BMI must remain disabled
  }
});

test('QC cannot edit even a draft; researcher can edit after role switch', () => {
  const ctx = context();
  ctx.user.role = 'qc';
  vm.runInContext("VisitEntry.currentVisit = {status:'draft'}; VisitEntry.updateEditability()", ctx);
  assert.equal(ctx.controls[0].disabled, true);
  ctx.user.role = 'researcher';
  vm.runInContext('VisitEntry.updateEditability()', ctx);
  assert.equal(ctx.controls[0].disabled, false);
});

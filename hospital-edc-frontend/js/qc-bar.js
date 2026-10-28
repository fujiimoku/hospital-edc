// 质控操作栏：把"提交 → 质控 → 答疑 → 签名 → 锁定"闭环搬进浏览器
// 按当前登录角色与访视状态动态显示对应按钮。
const QcBar = {

  // 主刷新：按角色/状态决定按钮，并拉取该访视的质疑列表
  async refresh() {
    const bar = document.getElementById('entry-qc-bar');
    if (!bar) return;
    const visit = (typeof VisitEntry !== 'undefined') ? VisitEntry.currentVisit : null;
    const user = getUser();
    if (!visit || !user) { bar.classList.add('hidden'); return; }
    bar.classList.remove('hidden');

    const role = user.role, st = visit.status;
    const show = (id, on) => { const b = document.getElementById(id); if (b) b.classList.toggle('hidden', !on); };

    show('qc-btn-query',  role === 'qc' && st === 'submitted');
    show('qc-btn-pass',   role === 'qc' && st === 'submitted');
    show('qc-btn-sign',   role === 'researcher' && st === 'qc_passed');
    show('qc-btn-lock',   ['qc', 'center_admin', 'main_admin'].includes(role) && st === 'signed');
    show('qc-btn-unlock', role === 'main_admin' && st === 'locked');
    show('qc-btn-reopen', role === 'main_admin' && ['qc_passed', 'signed'].includes(st));
    show('qc-btn-withdraw', ['researcher', 'center_admin', 'main_admin'].includes(role) && st === 'submitted');

    const hints = {
      draft:     '草稿中 —— 研究者可继续录入，完成后点击页面底部「提交审核」',
      submitted: role === 'qc' ? '待质控审核 —— 可对可疑字段提起质疑；全部质疑关闭后方可通过'
                               : '待质控审核 —— 误填或误提交可选择原因后撤回修改，无需等待管理员；如有质疑请在下方回复',
      qc_passed: role === 'researcher' ? '质控已通过 —— 请核对数据并签名确认' : '质控已通过 —— 等待研究者签名',
      signed:    '已签名 —— 数据只读，等待质控锁定；更正须退回草稿并重新审核签名',
      locked:    '已锁定 —— 数据封存，仅总管理员可解锁',
    };
    const hint = document.getElementById('qc-bar-hint');
    if (hint) hint.textContent = hints[st] || st;

    await this.loadQueries(visit.id, role);
  },

  // 质疑列表：open 的可答复（研究者），answered 的可关闭（质控员）
  async loadQueries(visitId, role) {
    const wrap = document.getElementById('qc-query-list');
    if (!wrap) return;
    try {
      const queries = await api('GET', `/api/queries/?visit_id=${visitId}`);
      if (!queries.length) { wrap.innerHTML = ''; return; }
      wrap.innerHTML = queries.map(q => {
        const chip = { open: '待答复', answered: '已答复', closed: '已关闭' }[q.status] || q.status;
        const chipCls = { open: 'bg-orange-100 text-orange-700', answered: 'bg-blue-100 text-blue-700', closed: 'bg-gray-100 text-gray-500' }[q.status] || 'bg-gray-100 text-gray-500';
        let actionHtml = '';
        if (q.status === 'open' && role === 'researcher') {
          actionHtml = `
            <div class="flex gap-2 mt-2">
              <input id="ans-${q.id}" class="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" placeholder="请回复质控质疑…"/>
              <button onclick="QcBar.answer(${q.id})" class="bg-blue-600 text-white text-xs px-4 rounded-lg hover:bg-blue-700">提交回答</button>
            </div>`;
        } else if (q.status === 'answered' && role === 'qc') {
          actionHtml = `
            <div class="mt-2 text-right">
              <button onclick="QcBar.close(${q.id})" class="bg-gray-700 text-white text-xs px-4 py-1.5 rounded-lg hover:bg-gray-800">确认无误，关闭质疑</button>
            </div>`;
        }
        return `
          <div class="border border-gray-100 bg-gray-50 rounded-lg px-4 py-3">
            <div class="flex items-center gap-2">
              <span class="text-xs px-2 py-0.5 rounded-full ${chipCls}">${chip}</span>
              <span class="text-sm font-medium text-gray-700">${q.field_name}</span>
              <span class="text-sm text-gray-600">${q.content}</span>
            </div>
            ${q.answer ? `<div class="text-sm text-gray-500 mt-1.5 pl-1">↳ 研究者答复：${q.answer}</div>` : ''}
            ${actionHtml}
          </div>`;
      }).join('');
    } catch (e) { /* 静默：列表加载失败不打断录入 */ }
  },

  // ── 按钮动作 ─────────────────────────────
  async _visitAction(path, okMsg, body) {
    const visit = VisitEntry.currentVisit;
    if (!visit || this._actionBusy) return;
    this._actionBusy = true;
    const finish = OperationFeedback.start('正在处理，请稍候…', '#entry-qc-bar button');
    try {
      await api('POST', `/api/visits/${visit.id}/${path}`, body);
      showToast(okMsg, 'success');
      if (VisitEntry.currentVisit?.id === visit.id) await VisitEntry.onVisitSelect(visit.id);
    } catch (e) { showToast(e.message || '操作失败', 'error'); }
    finally { this._actionBusy = false; finish(); }
  },
  qcPass() { this._visitAction('qc-review', '质控审核通过'); },
  sign()   { this._visitAction('sign', '已签名确认'); },
  lock()   { this._visitAction('lock', '访视已锁定'); },
  unlock() {
    this._reopenWithReason('unlock');
  },
  reopen() {
    this._reopenWithReason('reopen');
  },
  withdraw() { this._reopenWithReason('withdraw-submission'); },
  correctionReasons: ['信息填错，需要更正', '选项点错，需要重选', '误点提交，尚未填完', '漏填内容，需要补充'],
  _reopenWithReason(path) {
    const visit = VisitEntry.currentVisit;
    if (!visit || this._reasonBusy) return;
    this._reasonTarget = {visitId: visit.id, path};
    const select = document.getElementById('correction-reason');
    select.innerHTML = '<option value="">请选择更正原因</option>' + this.correctionReasons.map(r => `<option value="${r}">${r}</option>`).join('') + '<option value="other">其他原因</option>';
    document.getElementById('correction-detail').value = '';
    document.getElementById('correction-error').textContent = '';
    document.getElementById('correction-hint').textContent = path === 'withdraw-submission'
      ? '选择原因即可撤回草稿，无需管理员批准。修改完成后重新提交审核；已有质疑仍需处理。'
      : '操作将退回草稿，原审核和签名不再有效，更正后须重新提交、审核和签名。';
    document.getElementById('correction-submit').textContent = path === 'withdraw-submission' ? '撤回并修改' : '退回草稿';
    this.changeCorrectionReason();
    document.getElementById('modal-correction').classList.remove('hidden');
  },
  changeCorrectionReason() {
    document.getElementById('correction-detail-wrap').classList.toggle('hidden', document.getElementById('correction-reason').value !== 'other');
  },
  closeCorrection() {
    if (this._reasonBusy) return;
    document.getElementById('modal-correction').classList.add('hidden');
    this._reasonTarget = null;
  },
  async submitCorrection() {
    if (this._reasonBusy || !this._reasonTarget) return;
    const target = this._reasonTarget;
    const error = document.getElementById('correction-error');
    const choice = document.getElementById('correction-reason').value;
    const reason = choice === 'other' ? document.getElementById('correction-detail').value.trim()
      : this.correctionReasons.includes(choice) ? choice : '';
    if (!reason || reason.length > 500) { error.textContent = '请选择快捷原因，或填写其他原因（最多500字）'; return; }
    if (VisitEntry.currentVisit?.id !== target.visitId) { error.textContent = '当前访视已切换，请关闭窗口后重新操作'; return; }
    const button = document.getElementById('correction-submit');
    this._reasonBusy = true;
    const finish = OperationFeedback.start('正在退回草稿…', '#correction-submit');
    error.textContent = '';
    try {
      await api('POST', `/api/visits/${target.visitId}/${target.path}`, {reason});
      document.getElementById('modal-correction').classList.add('hidden');
      this._reasonTarget = null;
      showToast('已回到草稿，可直接修改，完成后请重新提交审核', 'success');
      if (VisitEntry.currentVisit?.id === target.visitId) await VisitEntry.onVisitSelect(target.visitId);
    } catch (e) { error.textContent = e.message || '操作失败，请重试'; }
    finally { this._reasonBusy = false; finish(); }
  },

  // ── 质疑：提起 / 答复 / 关闭 ─────────────
  showRaiseModal() {
    document.getElementById('rq-content').value = '';
    document.getElementById('rq-error').textContent = '';
    document.getElementById('modal-raise-query').classList.remove('hidden');
  },
  closeRaiseModal() { document.getElementById('modal-raise-query').classList.add('hidden'); },
  async raiseQuery() {
    const visit = VisitEntry.currentVisit;
    const field = document.getElementById('rq-field').value;
    const content = document.getElementById('rq-content').value.trim();
    const err = document.getElementById('rq-error');
    if (!content) { err.textContent = '请填写质疑内容'; return; }
    try {
      await api('POST', '/api/queries/', { visit_id: visit.id, field_name: field, content });
      showToast('质疑已提交，已通知研究者', 'success');
      this.closeRaiseModal();
      await this.refresh();
    } catch (e) { err.textContent = e.message || '提交失败'; }
  },
  async answer(queryId) {
    const input = document.getElementById(`ans-${queryId}`);
    if (!input.value.trim()) { showToast('请填写答复内容', 'error'); return; }
    try {
      await api('PATCH', `/api/queries/${queryId}/answer`, { answer: input.value.trim() });
      showToast('答复已提交', 'success');
      await this.refresh();
    } catch (e) { showToast(e.message || '提交失败', 'error'); }
  },
  async close(queryId) {
    try {
      await api('PATCH', `/api/queries/${queryId}/close`, {});
      showToast('质疑已关闭', 'success');
      await this.refresh();
    } catch (e) { showToast(e.message || '操作失败', 'error'); }
  },
};

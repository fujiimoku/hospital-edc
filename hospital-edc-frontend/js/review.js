// 质控审计页模块：集中处理待办质疑与访视状态流转
// 所有写操作复用现有后端端点（queries/visits），本页只做聚合展示与就地操作。
// 按钮可见性与后端 require_* 权限一致：
//   研究者(researcher)可答疑/签名；质控员(qc)可通过/关闭/提质疑；
//   管理员(center_admin/main_admin)三者皆可；锁定仅管理员。
const ReviewPage = {
  VISIT_TYPE_LABEL: { baseline: '基线', M6: '6月', M12: '12月', M18: '18月', M24: '24月' },
  VISIT_STATUS_LABEL: { submitted: '待质控审核', qc_passed: '质控通过', signed: '已签名' },
  _data: null,          // /api/review/queue 的缓存
  _patientsById: Object.create(null),
  _pendingQueryVisit: null,  // 提质疑模态框对应的访视

  // 权限判定（与后端 require_researcher / require_qc / require_admin 对齐）
  _canResearcher() { return ['researcher', 'main_admin', 'center_admin'].includes(this._role()); },
  _canQc()         { return ['qc', 'main_admin', 'center_admin'].includes(this._role()); },
  _canAdmin()      { return ['center_admin', 'main_admin'].includes(this._role()); },
  _role() {
    const user = getUser();
    return user ? user.role : '';
  },

  init() {
    if (!getToken()) return;
    this.refresh();
  },

  async refresh() {
    const queryList = document.getElementById('review-query-list');
    const visitList = document.getElementById('review-visit-list');
    if (!queryList || !visitList) return;
    try {
      this._data = await api('GET', '/api/review/queue');
      this._patientsById = Object.create(null);
      // 缓存患者信息供「打开详情」跳转使用
      this._data.visits.forEach(v => { this._patientsById[v.patient_id] = v; });
      this._data.queries.forEach(q => {
        if (!this._patientsById[q.patient_id]) this._patientsById[q.patient_id] = q;
      });
      this._renderCards(this._data.counts);
      this._renderQueries(this._data.queries);
      this._renderVisits(this._data.visits);
    } catch (e) {
      queryList.innerHTML = `<div class="text-center text-red-400 py-6 text-sm">加载失败: ${e.message || '未知'}</div>`;
      visitList.innerHTML = '';
    }
  },

  // ── 统计卡 ─────────────────────────────
  _renderCards(counts) {
    const el = document.getElementById('review-cards');
    if (!el || !counts) return;
    const cards = [
      { label: '待答复质疑', value: counts.to_answer, hint: '等待研究者回复', cls: counts.to_answer ? 'text-orange-500' : 'text-gray-800' },
      { label: '待关闭质疑', value: counts.to_close, hint: '等待质控确认', cls: counts.to_close ? 'text-blue-600' : 'text-gray-800' },
      { label: '待质控审核', value: counts.to_review, hint: 'submitted 访视', cls: counts.to_review ? 'text-blue-600' : 'text-gray-800' },
      { label: '待研究者签名', value: counts.to_sign, hint: 'qc_passed 访视', cls: counts.to_sign ? 'text-blue-600' : 'text-gray-800' },
      { label: '待管理员锁定', value: counts.to_lock, hint: 'signed 访视', cls: counts.to_lock ? 'text-blue-600' : 'text-gray-800' },
    ];
    el.innerHTML = cards.map(c => `
      <div class="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
        <div class="text-xs text-gray-400 mb-1">${c.label}</div>
        <div class="text-2xl font-bold ${c.cls}">${c.value}</div>
        <div class="text-xs text-gray-400 mt-1">${c.hint}</div>
      </div>`).join('');
  },

  // ── 待办质疑 ───────────────────────────
  _renderQueries(queries) {
    const el = document.getElementById('review-query-list');
    if (!el) return;
    if (!queries.length) {
      el.innerHTML = '<div class="text-center text-gray-400 py-6 text-sm">暂无待办质疑 🎉</div>';
      return;
    }
    const canResearcher = this._canResearcher(), canQc = this._canQc();
    el.innerHTML = queries.map(q => {
      const isOpen = q.status === 'open';
      const chip = isOpen
        ? '<span class="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700">待答复</span>'
        : '<span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">已答复</span>';
      let actionHtml = '';
      if (isOpen && canResearcher) {
        actionHtml = `
          <div class="flex gap-2 mt-2.5">
            <input id="rv-ans-${q.id}" class="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" placeholder="请回复质控质疑…"/>
            <button onclick="ReviewPage.answer(${q.id})" class="bg-blue-600 text-white text-xs px-4 rounded-lg hover:bg-blue-700">提交回答</button>
          </div>`;
      } else if (!isOpen && canQc) {
        actionHtml = `
          <div class="mt-2.5 text-right">
            <button onclick="ReviewPage.close(${q.id})" class="bg-gray-700 text-white text-xs px-4 py-1.5 rounded-lg hover:bg-gray-800">确认无误，关闭质疑</button>
          </div>`;
      }
      const vt = this.VISIT_TYPE_LABEL[q.visit_type] || q.visit_type;
      return `
        <div class="border border-gray-100 bg-gray-50 rounded-lg px-4 py-3">
          <div class="flex items-center gap-2 flex-wrap">
            ${chip}
            <span class="text-xs text-gray-400">${q.center_code}</span>
            <button onclick="ReviewPage.openDetail(${q.patient_id}, ${q.visit_id})"
                    class="font-mono text-sm text-blue-600 hover:underline">${this._esc(q.patient_code)}</button>
            <span class="text-sm text-gray-600">${this._esc(q.name_initials || '')}</span>
            <span class="text-xs text-gray-400">·</span>
            <span class="text-sm text-gray-600">${vt}访视（${q.visit_date || '—'}）</span>
            <span class="text-xs text-gray-400">·</span>
            <span class="text-sm font-medium text-gray-700">${this._esc(q.field_name)}</span>
          </div>
          <div class="text-sm text-gray-600 mt-1.5">${this._esc(q.content)}</div>
          ${q.answer ? `<div class="text-sm text-gray-500 mt-1.5">↳ 研究者答复：${this._esc(q.answer)}</div>` : ''}
          ${actionHtml}
        </div>`;
    }).join('');
  },

  // ── 待办访视（按流转阶段分组）──────────────
  _renderVisits(visits) {
    const el = document.getElementById('review-visit-list');
    if (!el) return;
    const groups = [
      { status: 'submitted',  title: '待质控审核', desc: '质控员审核数据，可通过或提出质疑', canAct: () => this._canQc() },
      { status: 'qc_passed',  title: '待研究者签名', desc: '研究者核对数据后签名确认', canAct: () => this._canResearcher() },
      { status: 'signed',     title: '待管理员锁定', desc: '锁定后数据封存，不可再修改', canAct: () => this._canAdmin() },
    ];
    if (!visits.length) {
      el.innerHTML = '<div class="text-center text-gray-400 py-6 text-sm">暂无待办访视 🎉</div>';
      return;
    }
    el.innerHTML = groups.map(g => {
      const items = visits.filter(v => v.status === g.status);
      const headBadge = items.length ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400';
      const rows = items.length ? items.map(v => this._visitRow(v, g.status)).join('') : '';
      return `
        <div>
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs px-2 py-0.5 rounded-full ${headBadge}">${items.length}</span>
            <span class="text-sm font-semibold text-gray-700">${g.title}</span>
            <span class="text-xs text-gray-400">${g.desc}</span>
          </div>
          ${items.length
            ? `<div class="divide-y divide-gray-50 border border-gray-100 rounded-lg">${rows}</div>`
            : '<div class="text-xs text-gray-300 pl-1 py-1">无</div>'}
        </div>`;
    }).join('');
  },

  _visitRow(v, status) {
    const vt = this.VISIT_TYPE_LABEL[v.visit_type] || v.visit_type;
    const stChip = this._statusChip(v.status);
    const openQ = v.open_queries
      ? `<span class="text-xs px-2 py-0.5 rounded-full bg-orange-100 text-orange-700" title="该访视有未关闭质疑，需全部关闭后才能通过质控">${v.open_queries} 条未关闭质疑</span>`
      : '';
    let actionHtml = '';
    if (status === 'submitted' && this._canQc()) {
      actionHtml = `
        <button onclick="ReviewPage.showRaiseModal(${v.id})" class="border border-gray-300 text-gray-600 text-xs px-3 py-1.5 rounded-lg hover:border-blue-400 hover:text-blue-600">提质疑</button>
        <button onclick="ReviewPage.visitAction(${v.id},'qc-review','质控审核通过')" class="bg-blue-600 text-white text-xs px-4 py-1.5 rounded-lg hover:bg-blue-700">通过质控</button>`;
    } else if (status === 'qc_passed' && this._canResearcher()) {
      actionHtml = `
        <button onclick="ReviewPage.visitAction(${v.id},'sign','已签名确认')" class="bg-blue-600 text-white text-xs px-4 py-1.5 rounded-lg hover:bg-blue-700">签名确认</button>`;
    } else if (status === 'signed' && this._canAdmin()) {
      actionHtml = `
        <button onclick="ReviewPage.visitAction(${v.id},'lock','访视已锁定')" class="bg-gray-700 text-white text-xs px-4 py-1.5 rounded-lg hover:bg-gray-800">锁定</button>`;
    }
    return `
      <div class="flex items-center gap-3 px-4 py-3 flex-wrap">
        <span class="text-xs text-gray-400 w-12">${v.center_code}</span>
        <button onclick="ReviewPage.openDetail(${v.patient_id}, ${v.id})"
                class="font-mono text-sm text-blue-600 hover:underline">${this._esc(v.patient_code)}</button>
        <span class="text-sm text-gray-600">${this._esc(v.name_initials || '')}</span>
        <span class="text-sm text-gray-600">${vt}访视（${v.visit_date || '—'}）</span>
        ${stChip}${openQ}
        <span class="flex-1"></span>
        <span class="flex items-center gap-2">
          ${actionHtml}
          <button onclick="ReviewPage.openDetail(${v.patient_id}, ${v.id})"
                  class="text-xs text-gray-500 hover:text-blue-600 hover:underline">打开详情</button>
        </span>
      </div>`;
  },

  _statusChip(status) {
    const map = {
      submitted: 'bg-orange-100 text-orange-700',
      qc_passed: 'bg-blue-100 text-blue-700',
      signed: 'bg-emerald-100 text-emerald-700',
    };
    const label = this.VISIT_STATUS_LABEL[status] || status;
    return `<span class="text-xs px-2 py-0.5 rounded-full ${map[status] || 'bg-gray-100 text-gray-500'}">${label}</span>`;
  },

  // ── 动作：答疑 / 关闭 / 访视流转 ────────
  async answer(queryId) {
    const input = document.getElementById(`rv-ans-${queryId}`);
    if (!input || !input.value.trim()) { showToast('请填写答复内容', 'error'); return; }
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

  async visitAction(visitId, path, okMsg) {
    try {
      await api('POST', `/api/visits/${visitId}/${path}`);
      showToast(okMsg, 'success');
      await this.refresh();
    } catch (e) { showToast(e.message || '操作失败', 'error'); }
  },

  // ── 提质疑模态框 ───────────────────────
  showRaiseModal(visitId) {
    this._pendingQueryVisit = visitId;
    document.getElementById('rq2-content').value = '';
    document.getElementById('rq2-error').textContent = '';
    document.getElementById('modal-review-query').style.display = 'flex';
  },
  closeRaiseModal() { document.getElementById('modal-review-query').style.display = 'none'; },
  async raiseQuery() {
    const visitId = this._pendingQueryVisit;
    const field = document.getElementById('rq2-field').value;
    const content = document.getElementById('rq2-content').value.trim();
    const err = document.getElementById('rq2-error');
    if (!content) { err.textContent = '请填写质疑内容'; return; }
    try {
      await api('POST', '/api/queries/', { visit_id: visitId, field_name: field, content });
      showToast('质疑已提交，已通知研究者', 'success');
      this.closeRaiseModal();
      await this.refresh();
    } catch (e) { err.textContent = e.message || '提交失败'; }
  },

  // ── 打开详情：跳到录入页并定位到该访视 ──
  openDetail(patientId, visitId) {
    const p = this._patientsById[patientId];
    if (!p) { showToast('患者信息加载失败，请刷新页面', 'error'); return; }
    sessionStorage.setItem('currentPatient', JSON.stringify({
      id: p.patient_id,
      patient_code: p.patient_code,
      name_initials: p.name_initials,
      gender: null,
      age: null,
    }));
    sessionStorage.setItem('pendingVisitId', String(visitId));
    showPage('entry', document.querySelectorAll('.sidebar-item')[2]);
  },

  // HTML 转义（质疑/答复为用户输入）
  _esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  },
};

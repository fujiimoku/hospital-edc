// Membership is filtered on the server before counting and paging.
const RecordedPage = {
  offset: 0, limit: 20, generation: 0,
  selectPatient(id) { openPatientTab(id); },
  async init(offset = 0) {
    if (!getToken()) return;
    const generation = ++this.generation;
    this.offset = Math.max(0, offset);
    const tbody = document.getElementById('recorded-table');
    const footer = document.getElementById('recorded-list-footer');
    if (!tbody) return;
    document.getElementById('recorded-prev').disabled = true;
    document.getElementById('recorded-next').disabled = true;
    tbody.innerHTML = '<tr><td colspan="7" class="p-6">加载中…</td></tr>';
    try {
      const data = await api('GET', `/api/patients/?approved_only=true&limit=${this.limit}&skip=${this.offset}&sort=center`);
      if (generation !== this.generation || !tbody.isConnected) return;
      if (!data.items.length && this.offset > 0) return this.init(Math.max(0, this.offset - this.limit));
      document.getElementById('recorded-list-title').textContent = `已录入患者（${data.total}）`;
      footer.textContent = `共 ${data.total} 人，显示 ${data.items.length ? this.offset + 1 : 0}–${this.offset + data.items.length}`;
      document.getElementById('recorded-prev').disabled = this.offset === 0;
      document.getElementById('recorded-next').disabled = this.offset + data.items.length >= data.total;
      tbody.innerHTML = data.items.map(p => `<tr class="border-t">
        <td class="p-3"><button class="text-blue-600" onclick="RecordedPage.selectPatient(${p.id})">${escapeText(p.patient_code)}</button><small class="block">${escapeText(p.center_name || '')}</small></td>
        <td class="p-3">${escapeText(p.full_name || p.name_initials || '—')}</td>
        <td class="p-3">${p.gender === 'male' ? '男' : p.gender === 'female' ? '女' : '—'}</td>
        <td class="p-3">${p.age ?? '—'}</td><td class="p-3">${escapeText(p.enrollment_date || '—')}</td>
        <td class="p-3">${patientBadges(p)}</td>
        <td class="p-3"><button class="text-blue-600" onclick="RecordedPage.selectPatient(${p.id})">查看／录入（新标签页）</button></td></tr>`).join('') || '<tr><td colspan="7" class="p-6">暂无审核通过的患者；全部患者请到患者管理查看。</td></tr>';
    } catch(e) {
      if (generation !== this.generation) return;
      tbody.innerHTML = `<tr><td colspan="7" class="p-6 text-red-600">加载失败：${escapeText(e.message)} <button onclick="RecordedPage.init(RecordedPage.offset)">重试</button></td></tr>`;
      footer.textContent = '加载失败，不能据此判断患者已删除';
    }
  }
};

// 已录入患者页：列出已提交/已锁定访视的患者，提供管理/修改入口
const RecordedPage = {
  GENDER_LABEL: { male: '男', female: '女' },
  VISIT_STATUS_TEXT: { draft: '草稿', submitted: '待审核', qc_passed: '质控通过', signed: '已签名', locked: '已锁定' },

  async init() {
    if (!getToken()) return;
    const tbody = document.getElementById('recorded-table');
    const footer = document.getElementById('recorded-list-footer');
    const title = document.getElementById('recorded-list-title');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-6 text-center text-gray-400">加载中…</td></tr>';
    try {
      const data = await api('GET', '/api/patients/?limit=200');
      const rawItems = data.items || [];
      // "已录入" = 有已提交及之后状态的访视，或已签知情同意
      let items = rawItems.filter(p => p.has_submitted || p.has_consent);
      if (!rawItems.some(p => p.has_submitted !== undefined)) {
        items = rawItems.filter(p => ['submitted', 'qc_passed', 'signed', 'locked'].includes(p.latest_visit_status));
      }
      title.textContent = '已录入患者（' + items.length + '）';
      footer.textContent = '共 ' + items.length + ' 条';
      if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-8 text-center text-gray-400">暂无已录入患者</td></tr>';
        return;
      }
      tbody.innerHTML = items.map(p => {
        const enroll = p.enrollment_date ? p.enrollment_date.slice(0, 10) : '—';
        const gender = this.GENDER_LABEL[p.gender] || p.gender || '—';
        const st = this.VISIT_STATUS_TEXT[p.latest_visit_status] || '未建访视';
        return `<tr class="hover:bg-blue-50/40 border-t border-gray-50">
          <td class="px-5 py-3 font-mono text-blue-600 text-sm">${p.patient_code}</td>
          <td class="px-4 py-3 text-sm">${p.full_name || p.name_initials || '—'}</td>
          <td class="px-4 py-3 text-sm">${gender}</td>
          <td class="px-4 py-3 text-sm">${p.age ?? '—'}</td>
          <td class="px-4 py-3 text-sm">${enroll}</td>
          <td class="px-4 py-3 text-sm">${st}</td>
          <td class="px-4 py-3"><button onclick="showPage('entry', document.querySelectorAll('.sidebar-item')[2])" class="text-blue-600 text-xs hover:underline">管理/修改</button></td>
        </tr>`;
      }).join('');
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" class="px-5 py-6 text-center text-red-400">加载失败: ${e.message || '未知'}</td></tr>`;
      footer.textContent = '—';
    }
  }
};

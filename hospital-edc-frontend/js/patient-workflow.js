// Patient tabs keep identity in the URL; credentials stay in sessionStorage.
function openPatientTab(patientId, visitId) {
  const url = new URL(window.location.href);
  url.search = '';
  url.hash = '';
  url.searchParams.set('patient', String(patientId));
  if (visitId) url.searchParams.set('visit', String(visitId));
  const child = window.open(url.href, '_blank');
  if (child) child.opener = null;
  else showToast('浏览器阻止了新标签页，请允许本站打开弹窗后重试', 'error');
}

const VISIT_PROGRESS_TEXT = {draft:'草稿',submitted:'待审核',qc_passed:'审核通过',signed:'已签名',locked:'已锁定'};
function patientBadges(patient) {
  const tracking = patient.tracking_status === 'completed' ? '已完成追踪' : '待追踪';
  return `<div class="flex flex-wrap justify-end gap-2 text-xs" aria-label="患者状态">
    <span class="rounded px-2 py-1 bg-blue-50 text-blue-700">${tracking}</span>
    <span class="rounded px-2 py-1 bg-gray-100 text-gray-700">最近访视：${escapeText(VISIT_PROGRESS_TEXT[patient.latest_visit_status] || '未建访视')}</span>
    ${patient.has_approved ? '<span class="rounded px-2 py-1 bg-green-50 text-green-700">已有审核通过访视</span>' : ''}
    ${patient.open_queries ? `<span class="rounded px-2 py-1 bg-red-50 text-red-700">待处理质疑 ${Number(patient.open_queries)}</span>` : ''}</div>`;
}
async function setPatientTracking(id, element) {
  const old = element.dataset.previous || 'pending';
  element.disabled = true;
  try {
    const result = await api('PUT', `/api/patients/${id}/tracking`, {tracking_status:element.value});
    element.dataset.previous = result.tracking_status;
    showToast('追踪标签已保存');
    if (typeof loadPatients === 'function' && document.getElementById('patient-table')) await loadPatients(undefined, patientOffset);
  } catch(e) {element.value=old;showToast(e.message,'error');}
  finally {element.disabled=false;}
}

// Authenticated previews use blob URLs, never public upload paths or tokens in URLs.
const PhotoPreview = {
  urls: new Set(),
  clear(container) {
    container?.querySelectorAll('img[data-private-image]').forEach(img => {
      if (img.src.startsWith('blob:')) {URL.revokeObjectURL(img.src);this.urls.delete(img.src);}
    });
  },
  async load(container, patientId, items) {
    const token=getToken();
    await Promise.all(items.map(async item => {
      const img=container.querySelector(`[data-private-image="${item.id}"]`);
      if (!img) return;
      try {
        const response=await fetch(API_BASE+`/api/patients/${patientId}/images/${item.id}/download`, {headers:{Authorization:`Bearer ${token}`}});
        if (!response.ok) throw new Error('预览失败');
        const blob=await response.blob();
        if (!img.isConnected || token!==getToken()) return;
        const url=URL.createObjectURL(blob);this.urls.add(url);img.src=url;
        img.onclick=()=>this.show(url,item.filename);
      } catch(e) { if (img.isConnected) img.alt='预览失败，可重试或下载查看'; }
    }));
  },
  show(url, filename) {
    const dialog=document.createElement('dialog');
    dialog.className='rounded-xl p-4 max-w-5xl w-full';
    dialog.innerHTML='<button type="button" class="float-right p-2">关闭</button><p></p><img class="max-h-screen mx-auto" alt="费用照片大图">';
    dialog.querySelector('p').textContent=filename;
    dialog.querySelector('img').src=url;
    dialog.querySelector('button').onclick=()=>dialog.close();
    dialog.addEventListener('close',()=>dialog.remove(),{once:true});
    document.body.appendChild(dialog);dialog.showModal();
  },
  thumbnail(item) {return `<img data-private-image="${item.id}" alt="加载照片预览…" class="w-32 h-24 object-contain border rounded cursor-pointer" title="点击查看大图">`;},
};
window.addEventListener('pagehide',()=>PhotoPreview.urls.forEach(url=>URL.revokeObjectURL(url)));

// 顶栏通知铃铛：未读数 + 下拉面板
const Notifs = {
  _timer: null,

  async refreshBadge() {
    if (!getToken()) return;
    try {
      const r = await api('GET', '/api/notifications/unread-count');
      const badge = document.getElementById('notif-badge');
      if (!badge) return;
      badge.textContent = r.unread;
      badge.style.display = r.unread > 0 ? '' : 'none';
    } catch (e) {
      // 静默失败（如登录过期由 api() 统一处理）
    }
  },

  async togglePanel() {
    const panel = document.getElementById('notif-panel');
    if (!panel) return;
    if (panel.style.display === 'none' || !panel.style.display) {
      await this.renderPanel();
      panel.style.display = '';
    } else {
      panel.style.display = 'none';
    }
  },

  async renderPanel() {
    const list = document.getElementById('notif-list');
    if (!list) return;
    list.innerHTML = '<div class="py-6 text-center text-gray-400 text-sm">加载中...</div>';
    try {
      const r = await api('GET', '/api/notifications/?limit=20');
      const typeLabel = { followup_window: '随访提醒', query_raised: '质控质疑' };
      if (!r.items.length) {
        list.innerHTML = '<div class="py-6 text-center text-gray-400 text-sm">暂无通知</div>';
      } else {
        list.innerHTML = r.items.map(n => `
          <div class="px-4 py-3 border-b border-gray-50 ${n.is_read ? 'opacity-60' : 'bg-blue-50/50'} cursor-pointer hover:bg-gray-50"
               onclick="Notifs.markRead(${n.id}, ${n.is_read})">
            <div class="flex items-center gap-2">
              <span class="text-xs px-1.5 py-0.5 rounded ${n.type === 'query_raised' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'}">${typeLabel[n.type] || n.type}</span>
              ${n.is_read ? '' : '<span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>'}
            </div>
            <div class="text-sm text-gray-700 mt-1">${n.content}</div>
            <div class="text-xs text-gray-400 mt-0.5">${(n.created_at || '').replace('T', ' ').slice(0, 16)}</div>
          </div>
        `).join('');
      }
      const markAll = document.getElementById('notif-mark-all');
      if (markAll) markAll.style.display = r.unread > 0 ? '' : 'none';
    } catch (e) {
      list.innerHTML = `<div class="py-6 text-center text-red-400 text-sm">加载失败：${e.message}</div>`;
    }
  },

  async markRead(id, isRead) {
    if (isRead) return;
    try {
      await api('PATCH', `/api/notifications/${id}/read`);
      this.refreshBadge();
      this.renderPanel();
    } catch (e) {
      showToast('操作失败：' + e.message, 'error');
    }
  },

  async markAllRead() {
    try {
      await api('POST', '/api/notifications/read-all');
      this.refreshBadge();
      this.renderPanel();
      showToast('已全部标记为已读');
    } catch (e) {
      showToast('操作失败：' + e.message, 'error');
    }
  },

  startPolling() {
    this.refreshBadge();
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this.refreshBadge(), 60000);
  }
};

// 点击面板外部时收起
document.addEventListener('click', (e) => {
  const panel = document.getElementById('notif-panel');
  const bell = document.getElementById('notif-bell');
  if (panel && bell && panel.style.display !== 'none' &&
      !panel.contains(e.target) && !bell.contains(e.target)) {
    panel.style.display = 'none';
  }
});

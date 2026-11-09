// Focus is a navigation hint, never an answer. Only explicit input changes data.
const EntryKeyboard = {
  reveal(el) {
    const target = el.type === 'radio' ? el.closest('label') || el : el;
    for (let parent = target.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      if (!/(auto|scroll)/.test(getComputedStyle(parent).overflowY) || parent.scrollHeight <= parent.clientHeight) continue;
      const box = target.getBoundingClientRect(), frame = parent.getBoundingClientRect();
      if (box.bottom > frame.bottom) parent.scrollTop += box.bottom - frame.bottom + 8;
      else if (box.top < frame.top) parent.scrollTop -= frame.top - box.top + 8;
      break;
    }
  },
  eligible(el) {
    return !el.disabled && !el.readOnly && !['hidden','file','button','submit'].includes(el.type)
      && el.getClientRects().length > 0;
  },
  steps(panel) {
    const result = [], groups = new Set();
    panel.querySelectorAll('input,select,textarea').forEach(el => {
      if (!this.eligible(el)) return;
      if (el.type !== 'radio') { result.push(el); return; }
      if (groups.has(el.name)) return;
      groups.add(el.name);
      const choices = [...panel.querySelectorAll('input[type="radio"]')].filter(r => r.name === el.name && this.eligible(r));
      const preferred = choices.find(r => r.checked) || choices[el.name.startsWith('dtsq-q') ? 4 : 0] || choices[0];
      choices.forEach(r => {r.tabIndex = r === preferred ? 0 : -1;});
      result.push(preferred);
    });
    return result;
  },
  focus(panel) {
    if (!panel) return;
    const steps = this.steps(panel);
    const first = ['tab-phq9','tab-gad7','tab-eq5d','tab-dtsq'].includes(panel.id)
      ? steps.find(el => el.type === 'radio') : steps[0];
    first?.focus({preventScroll:true});
  },
  setup(area) {
    if (!area) return;
    area.querySelectorAll('input[type="radio"].hidden').forEach(el => {
      el.classList.remove('hidden'); el.classList.add('edc-keyboard-radio');
      el.closest('label')?.classList.add('edc-radio-anchor');
    });
    if (area.dataset.keyboardBound) return;
    area.dataset.keyboardBound = '1';
    const hint = document.createElement('p');
    hint.className = 'text-sm text-blue-700 mb-3';
    hint.textContent = '键盘录入：回车确认并进入下一项；方向键调整量表选项。蓝框仅表示焦点，不代表已作答。多行文字用 Ctrl+回车进入下一项。';
    area.prepend(hint);
    area.addEventListener('keydown', e => {
      if (e.key !== 'Enter' || e.isComposing || e.keyCode === 229 || e.repeat || e.altKey || e.metaKey) return;
      const el = e.target;
      if (!el.matches('input,select,textarea') || !this.eligible(el)) return;
      if (el.tagName === 'TEXTAREA' && !e.ctrlKey) return; // Ctrl+Enter advances multiline text.
      const panel = el.closest('.tab-panel');
      if (!panel) return;
      e.preventDefault();
      if (!el.checkValidity()) {el.reportValidity(); return;}
      if (el.type === 'radio' && !el.checked) {
        el.checked = true;
        el.dispatchEvent(new Event('change',{bubbles:true}));
      }
      if (el.type === 'range') {
        el.dataset.answered = '1';
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
      }
      const steps = this.steps(panel);
      const index = steps.findIndex(item => item === el || (el.type === 'radio' && item.name === el.name));
      const next = steps[index + (e.shiftKey ? -1 : 1)];
      if (next) {
        next.focus({preventScroll:true});this.reveal(next);
      } else if (!e.shiftKey) {
        panel.querySelector('[data-page-save]:not(:disabled)')?.focus({preventScroll:true});
      }
    });
  },
};

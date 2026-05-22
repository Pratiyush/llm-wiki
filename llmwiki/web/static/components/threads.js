/* Thread sidebar component — P2/P3 thread list, switch, rename, export, delete */

const Threads = {
  threads: [],
  activeThreadId: null,
  loadSeq: 0,

  init() {
    this.sidebarEl = document.getElementById('thread-sidebar');
    this.listEl = document.getElementById('thread-list');
    this.newBtn = document.getElementById('thread-new-sidebar');

    this.newBtn.addEventListener('click', function() { QA._newThread(); });
    window.addEventListener('notebook:change', () => {
      this.activeThreadId = null;
      this.load();
    });
    this.load();
  },

  notebookSlug() {
    return (typeof Notebooks !== 'undefined' && Notebooks.currentSlug)
      ? Notebooks.currentSlug()
      : 'enterprise-management';
  },

  notebookQuery() {
    return 'notebook=' + encodeURIComponent(this.notebookSlug());
  },

  load() {
    var self = this;
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) {
      this.threads = [];
      this.activeThreadId = null;
      this.render();
      return;
    }
    var token = Auth.getToken();
    var slug = this.notebookSlug();
    var seq = ++this.loadSeq;
    fetch('/api/query/history?token=' + encodeURIComponent(token) + '&' + this.notebookQuery())
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (seq !== self.loadSeq || self.notebookSlug() !== slug) return;
        self.threads = data.threads || [];
        self.render();
      });
  },

  refresh() { this.load(); },

  render() {
    if (!this.listEl) return;
    var self = this;
    var html = '';
    for (var i = 0; i < this.threads.length; i++) {
      var t = this.threads[i];
      var isActive = (t.id === self.activeThreadId);
      html += '<div class="thread-item' + (isActive ? ' active' : '') + '" data-id="' + t.id + '">'
        + '<div class="thread-item-header">'
        + '<span class="thread-item-title" data-id="' + t.id + '" title="' + self.escapeHtml(t.title) + '">' + self.escapeHtml(t.title) + '</span>'
        + '</div>'
        + '<div class="thread-item-meta">'
        + '<span class="thread-item-date">' + self.escapeHtml(t.created_at) + '</span>'
        + '<span class="thread-item-actions">'
        + '<button class="thread-action-btn" data-action="export" data-id="' + t.id + '" title="导出">&#11015;</button>'
        + '<button class="thread-action-btn" data-action="delete" data-id="' + t.id + '" title="删除">&times;</button>'
        + '</span>'
        + '</div>'
        + '</div>';
    }
    this.listEl.innerHTML = html || '<div class="thread-list-empty">暂无对话</div>';

    // Bind click on title → switch thread
    this.listEl.querySelectorAll('.thread-item-title').forEach(function(el) {
      el.addEventListener('click', function() {
        var id = parseInt(el.dataset.id);
        self.switchThread(id);
      });
      el.addEventListener('dblclick', function() {
        var id = parseInt(el.dataset.id);
        self.startRename(id);
      });
    });

    // Bind action buttons
    this.listEl.querySelectorAll('.thread-action-btn').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var id = parseInt(btn.dataset.id);
        if (btn.dataset.action === 'export') self.exportThread(id);
        if (btn.dataset.action === 'delete') self.deleteThread(id);
      });
    });
  },

  setActive(threadId) {
    this.activeThreadId = threadId;
    this._updateActiveState();
  },

  _updateActiveState() {
    if (!this.listEl) return;
    var items = this.listEl.querySelectorAll('.thread-item');
    items.forEach(function(item) {
      var id = parseInt(item.dataset.id);
      if (id === Threads.activeThreadId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  },

  switchThread(threadId) {
    this.setActive(threadId);
    if (typeof QA !== 'undefined') QA.loadThread(threadId);
  },

  startRename(threadId) {
    var self = this;
    var el = this.listEl.querySelector('.thread-item-title[data-id="' + threadId + '"]');
    if (!el || el._renaming) return;
    var oldTitle = el.textContent;
    el._renaming = true;
    el.contentEditable = 'true';
    el.focus();
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);

    function finish(save) {
      el.contentEditable = 'false';
      el._renaming = false;
      if (save) {
        var newTitle = el.textContent.trim();
        if (newTitle && newTitle !== oldTitle) {
          self.confirmRename(threadId, newTitle);
        } else {
          el.textContent = oldTitle;
        }
      } else {
        el.textContent = oldTitle;
      }
    }

    el.addEventListener('keydown', function handler(e) {
      if (e.key === 'Enter') { e.preventDefault(); finish(true); }
      if (e.key === 'Escape') { e.preventDefault(); finish(false); }
    }, { once: true });
    el.addEventListener('blur', function() { finish(true); }, { once: true });
  },

  confirmRename(threadId, newTitle) {
    var token = Auth.getToken();
    fetch('/api/query/thread/' + threadId + '/rename', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token, title: newTitle, notebook_slug: this.notebookSlug() }),
    })
    .then(function(r) { return r.json(); })
    .then(function() { Threads.refresh(); });
  },

  exportThread(threadId) {
    var token = Auth.getToken();
    fetch('/api/query/messages?thread_id=' + threadId + '&token=' + encodeURIComponent(token) + '&' + this.notebookQuery())
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.messages || !data.messages.length) return;
        var today = new Date().toISOString().slice(0, 10);
        var md = '# ' + (data.title || '对话导出') + '\n\n'
          + '> 导出时间: ' + today + '\n\n---\n\n';
        data.messages.forEach(function(m) {
          md += '## 用户\n' + m.question + '\n\n';
          var cleanAnswer = m.answer.split(/##\s*追问建议/)[0].trim();
          md += '## 助手\n' + cleanAnswer + '\n\n---\n\n';
        });
        var safeName = (data.title || 'thread').replace(/[\\/:*?"<>|]/g, '').trim().slice(0, 30);
        var blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = safeName + '.md';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
  },

  deleteThread(threadId) {
    if (!confirm('确定删除此对话线程？')) return;
    var token = Auth.getToken();
    var self = this;
    fetch('/api/query/thread/' + threadId + '?token=' + encodeURIComponent(token) + '&' + this.notebookQuery(), { method: 'DELETE' })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.status === 'ok') {
          if (self.activeThreadId === threadId && typeof QA !== 'undefined') {
            QA._newThread();
          }
          self.refresh();
        }
      });
  },

  escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = text || '';
    return d.innerHTML;
  }
};

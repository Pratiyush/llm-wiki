/* Manager component */

const Manager = {
  init() {
    window.addEventListener('tab:show', (e) => {
      if (e.detail.tab === 'manage') {
        this.loadStats();
        this.loadApprovals();
        this.loadDeployLog();
        this.loadAuditFiles();
        this.loadWikiPages();
      }
    });

    document.getElementById('btn-lint')?.addEventListener('click', () => this.runAction('lint'));
    document.getElementById('btn-fix-wiki')?.addEventListener('click', () => this.runAction('fix-wiki'));
    document.getElementById('btn-build')?.addEventListener('click', () => this.runAction('build'));
    document.getElementById('btn-sync')?.addEventListener('click', () => this.runAction('sync'));

    // Wiki content management
    document.getElementById('wiki-cat-select')?.addEventListener('change', () => this.loadWikiPages());
    var searchInput = document.getElementById('wiki-global-search');
    var searchClear = document.getElementById('wiki-search-clear');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        searchClear.style.display = searchInput.value ? 'block' : 'none';
      });
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          this._doGlobalSearch();
        }
      });
      searchInput.addEventListener('focus', () => this._showSearchHistory());
      searchInput.addEventListener('blur', () => setTimeout(() => this._hideSearchHistory(), 200));
    }
    if (searchClear) {
      searchClear.addEventListener('click', () => {
        searchInput.value = '';
        searchClear.style.display = 'none';
        this.loadWikiPages();
      });
    }
  },

  async loadStats() {
    try {
      const stats = await API.getStatus();
      document.getElementById('stat-pages').textContent = stats.pages || 0;
      document.getElementById('stat-sources').textContent = stats.sources || 0;
      document.getElementById('stat-entities').textContent = stats.entities || 0;
      document.getElementById('stat-concepts').textContent = stats.concepts || 0;
    } catch (e) {
      console.error('Stats error:', e);
    }
  },

  async loadApprovals() {
    var section = document.getElementById('approval-section');
    var list = document.getElementById('approval-list');
    if (!section || !list) return;

    // Only show for logged-in leader/admin
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn() || !Auth.isLeader()) {
      section.style.display = 'none';
      return;
    }

    section.style.display = 'block';
    list.innerHTML = '<div class="loading">加载中...</div>';

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/approvals', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();

      if (!resp.ok) {
        list.innerHTML = '<div class="muted">' + (data.detail || '无权限') + '</div>';
        return;
      }

      var items = data.pending || [];
      if (items.length === 0) {
        list.innerHTML = '<div class="muted">暂无待审批内容</div>';
        return;
      }

      var html = '';
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        html += '<div class="approval-item" data-id="' + item.id + '">';
        html += '<div class="approval-header">';
        html += '<span class="approval-title">' + this._esc(item.question) + '</span>';
        html += '<span class="approval-meta">' + this._esc(item.proposer) + ' | ' + this._esc(item.department) + ' | ' + item.created_at + '</span>';
        html += '</div>';
        html += '<div class="approval-preview">' + this._esc(item.answer_preview) + '</div>';
        html += '<div class="approval-actions">';
        html += '<button class="btn btn-approve" onclick="Manager.approveItem(' + item.id + ')">通过</button>';
        html += '<button class="btn btn-reject" onclick="Manager.rejectItem(' + item.id + ')">拒绝</button>';
        html += '</div>';
        html += '</div>';
      }
      list.innerHTML = html;
    } catch (e) {
      list.innerHTML = '<div class="muted">加载失败: ' + e.message + '</div>';
    }
  },

  async approveItem(id) {
    var token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
    try {
      var resp = await fetch('/api/manage/approvals/' + id + '/approve', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this.loadApprovals();
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  async rejectItem(id) {
    var token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
    try {
      var resp = await fetch('/api/manage/approvals/' + id + '/reject', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ comment: '' }),
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this.loadApprovals();
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  _esc(text) {
    var d = document.createElement('div');
    d.textContent = text || '';
    return d.innerHTML;
  },

  async runAction(action) {
    const output = document.getElementById('manage-output');

    if (action === 'lint') {
      var includeLLM = document.getElementById('lint-include-llm');
      var body = {};
      if (includeLLM && includeLLM.checked) {
        body.include_llm = true;
      }
      // Start lint
      output.textContent = '正在启动 Lint 检查...\n';
      try {
        await API.post('/api/manage/lint', body);
      } catch (e) {
        output.textContent = '启动失败: ' + e.message;
        return;
      }
      // Poll for results
      var dots = 0;
      var pollInterval = setInterval(function() {
        dots = (dots + 1) % 4;
        var dotStr = '.'.repeat(dots);
        output.textContent = 'Lint 检查进行中' + dotStr + (body.include_llm ? '（含 LLM 深度分析）' : '') + '\n请稍候，不要关闭页面';
      }, 1000);

      var self = this;
      var poll = function() {
        fetch('/api/manage/lint').then(function(r) { return r.json(); }).then(function(result) {
          if (result.done) {
            clearInterval(pollInterval);
            self._renderLintResult(output, result);
          } else {
            setTimeout(poll, 2000);
          }
        }).catch(function() {
          setTimeout(poll, 3000);
        });
      };
      setTimeout(poll, 1500);
      return;
    }

    output.textContent = '正在执行 ' + action + '...\n';
    try {
      const result = await API.post('/api/manage/' + action, {});
      if (action === 'fix-wiki') {
        output.textContent = 'Wiki 数据修复完成:\n';
        output.textContent += '  新建实体页面: ' + (result.created_pages || 0) + ' 个\n';
        output.textContent += '  index.md 已重建: ' + (result.index_rebuilt ? '是' : '否') + '\n';
        if (result.created && result.created.length > 0) {
          output.textContent += '\n新建的实体页面:\n';
          for (var i = 0; i < result.created.length; i++) {
            output.textContent += '  + ' + result.created[i] + '\n';
          }
          if (result.created_pages > 50) {
            output.textContent += '\n  ... 共 ' + result.created_pages + ' 个（仅显示前50个）';
          }
        }
      } else {
        output.textContent = JSON.stringify(result, null, 2);
      }
    } catch (e) {
      output.textContent = '错误: ' + e.message;
    }
  },

  _renderLintResult(output, result) {
    var llmRules = ['contradiction_detection', 'claim_verification', 'summary_accuracy'];
    if (result.issues) {
      const s = result.summary || {};
      output.textContent = 'Lint 检查完成: ' + result.total + ' 个问题\n';
      output.textContent += '  错误: ' + (s.error || 0) + '  警告: ' + (s.warning || 0) + '  信息: ' + (s.info || 0) + '\n\n';
      for (var i = 0; i < result.issues.length && i < 80; i++) {
        var issue = result.issues[i];
        const icon = issue.severity === 'error' ? '\u2717' : issue.severity === 'warning' ? '\u26A0' : '\u2139';
        var llmTag = llmRules.indexOf(issue.rule) >= 0 ? ' [LLM]' : '';
        output.textContent += icon + llmTag + ' [' + (issue.rule || '?') + '] ' + (issue.page || '') + ': ' + issue.message + '\n';
      }
      if (result.issues.length > 80) {
        output.textContent += '\n... 还有 ' + (result.issues.length - 80) + ' 个问题';
      }
    } else {
      output.textContent = JSON.stringify(result, null, 2);
    }
  },

  async loadDeployLog() {
    var badge = document.getElementById('version-badge');
    var content = document.getElementById('deploy-log-content');
    if (!content) return;

    try {
      var resp = await fetch('/api/manage/deploy-log');
      var data = await resp.json();
      if (badge) badge.textContent = 'v' + data.version;

      // Parse markdown table from DEPLOY_LOG.md
      var lines = (data.log || '').split('\n');
      var html = '<table class="deploy-log-table"><thead><tr><th>版本</th><th>日期</th><th>说明</th></tr></thead><tbody>';
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.startsWith('|') && !line.startsWith('|--') && !line.startsWith('| ---') && !line.startsWith('| 版本')) {
          var cells = line.split('|').filter(function(c) { return c.trim(); });
          if (cells.length >= 3) {
            html += '<tr>';
            html += '<td class="log-version">' + this._esc(cells[0].trim()) + '</td>';
            html += '<td class="log-date">' + this._esc(cells[1].trim()) + '</td>';
            html += '<td class="log-desc">' + this._esc(cells[2].trim()) + '</td>';
            html += '</tr>';
          }
        }
      }
      html += '</tbody></table>';
      content.innerHTML = html;
    } catch (e) {
      content.innerHTML = '<div class="muted">加载失败: ' + this._esc(e.message) + '</div>';
    }
  },

  // ========== Knowledge Audit ==========

  async loadAuditFiles() {
    var section = document.getElementById('audit-section');
    if (!section) return;
    // Visible to all logged-in users
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) {
      section.style.display = 'none';
      return;
    }
    section.style.display = 'block';

    var isAdmin = Auth.isLeader();
    var list = document.getElementById('audit-file-list');
    list.innerHTML = '<div class="loading">加载中...</div>';

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/files', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      if (!resp.ok) {
        list.innerHTML = '<div class="muted">' + this._esc(data.detail || '无权限') + '</div>';
        return;
      }

      var files = data.files || [];
      if (files.length === 0) {
        list.innerHTML = '<div class="muted">暂无上传文件记录</div>';
        return;
      }

      var html = '';
      for (var i = 0; i < files.length; i++) {
        var f = files[i];
        var isOutdated = f.status === 'outdated';
        html += '<div class="audit-file-item' + (isOutdated ? ' outdated' : '') + '">';
        html += '<div class="audit-file-info">';
        html += '<div class="audit-file-name">' + this._esc(f.filename) + ' ';
        html += '<span class="status-badge ' + f.status + '">' + (isOutdated ? '已过时' : '当前') + '</span>';
        if (f.flag_count > 0) {
          html += ' <span class="status-badge pending">' + f.flag_count + ' 条标记申请</span>';
        }
        html += '</div>';
        html += '<div class="audit-file-meta">';
        html += '版本: ' + this._esc(f.version_note) + ' | ';
        html += '上传者: ' + this._esc(f.uploader) + ' | ';
        html += f.uploaded_at + ' | ';
        html += '关联知识: ' + f.lineage_count + ' 条';
        if (f.pending_count > 0) {
          html += ' <span style="color:#e74c3c">(待审核: ' + f.pending_count + ')</span>';
        }
        html += '</div></div>';
        html += '<div class="audit-file-actions">';
        if (!isOutdated) {
          html += '<button class="btn-mark-outdated" onclick="Manager.flagFile(' + f.id + ')">标记过时/错误</button>';
        }
        html += '</div></div>';
      }
      list.innerHTML = html;

      // Admin: load flags and audit queue
      if (isAdmin) {
        this.loadPendingFlags();
        this.loadAuditQueue();
      }
    } catch (e) {
      list.innerHTML = '<div class="muted">加载失败: ' + this._esc(e.message) + '</div>';
    }
  },

  async flagFile(fileId) {
    var reason = prompt('请说明标记原因（如：该文件已有新版本、内容有误等）：');
    if (reason === null) return;
    if (!reason.trim()) {
      alert('请填写标记原因');
      return;
    }

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/files/' + fileId + '/flag', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason }),
      });
      var data = await resp.json();
      if (resp.ok) {
        alert('已提交标记申请，等待管理员审核。');
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  async loadPendingFlags() {
    var section = document.getElementById('pending-flags-section');
    var list = document.getElementById('pending-flags-list');
    if (!section || !list) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/flags', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      if (!resp.ok) {
        section.style.display = 'none';
        return;
      }

      var flags = data.flags || [];
      if (flags.length === 0) {
        section.style.display = 'none';
        return;
      }

      section.style.display = 'block';
      var html = '';
      for (var i = 0; i < flags.length; i++) {
        var f = flags[i];
        html += '<div class="audit-queue-item">';
        html += '<div class="audit-file-info">';
        html += '<div class="audit-file-name">' + this._esc(f.filename);
        html += ' <span class="status-badge pending">待审核</span></div>';
        html += '<div class="audit-file-meta">';
        html += '提出者: ' + this._esc(f.reporter) + ' (' + this._esc(f.department) + ') | ';
        html += f.created_at + '<br>';
        html += '原因: ' + this._esc(f.reason) + '<br>';
        html += '版本: ' + this._esc(f.version_note) + ' | 关联知识: ' + f.lineage_count + ' 条';
        html += '</div></div>';
        html += '<div class="audit-file-actions">';
        html += '<button class="btn-audit-keep" onclick="Manager.confirmFlag(' + f.id + ')">确认过时</button>';
        html += '<button class="btn-audit-delete" onclick="Manager.rejectFlag(' + f.id + ')">驳回</button>';
        html += '</div></div>';
      }
      list.innerHTML = html;
    } catch (e) {
      section.style.display = 'none';
    }
  },

  async confirmFlag(flagId) {
    if (!confirm('确认该文件已过时？所有关联知识（含衍生知识）将进入待审核队列。')) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/flags/' + flagId + '/confirm', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        alert('已确认过时，' + data.marked_for_review + ' 条关联知识进入待审核队列。');
        this.loadAuditFiles();
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  async rejectFlag(flagId) {
    if (!confirm('驳回此标记申请？')) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/flags/' + flagId + '/reject', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this.loadAuditFiles();
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  async loadAuditQueue() {
    var queueTitle = document.getElementById('audit-queue-title');
    var queueList = document.getElementById('audit-queue-list');
    if (!queueList || !queueTitle) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/audit-queue', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      var items = data.queue || [];

      if (items.length === 0) {
        queueTitle.style.display = 'none';
        queueList.innerHTML = '';
        return;
      }

      queueTitle.style.display = 'block';
      var html = '';
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        html += '<div class="audit-queue-item" id="queue-' + item.id + '">';
        html += '<div class="audit-file-info" style="flex:1">';
        html += '<div class="audit-file-name">' + this._esc(item.wiki_path);
        if (!item.file_exists) html += ' <span style="color:#e74c3c">(文件已不存在)</span>';
        html += '</div>';
        html += '<div class="audit-file-meta">来源文件: ' + this._esc(item.source_filename) + '</div>';
        if (item.preview) {
          html += '<div style="font-size:12px;color:var(--text-muted);margin-top:4px;max-height:40px;overflow:hidden">' + this._esc(item.preview.substring(0, 100)) + '...</div>';
        }
        html += '</div>';
        html += '<div class="audit-file-actions" style="flex-shrink:0">';
        html += '<button class="btn-audit-keep" onclick="Manager.auditKeep(' + item.id + ')" title="保留此页面">保留</button>';
        if (item.file_exists) {
          html += '<button class="btn-mark-outdated" onclick="Manager.auditEdit(' + item.id + ')" title="编辑内容">编辑</button>';
          html += '<button class="btn-audit-delete" onclick="Manager.auditDelete(' + item.id + ')" title="删除此页面">删除</button>';
        }
        html += '</div></div>';
      }
      queueList.innerHTML = html;
    } catch (e) {
      queueList.innerHTML = '<div class="muted">加载失败</div>';
    }
  },

  async auditEdit(lineageId) {
    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/audit-queue/' + lineageId + '/content', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();

      var el = document.getElementById('queue-' + lineageId);
      if (!el) return;

      var content = data.content || '';
      el.innerHTML = '<div style="width:100%">'
        + '<div style="font-weight:500;margin-bottom:6px">' + this._esc(data.path) + '</div>'
        + '<textarea id="edit-queue-' + lineageId + '" style="width:100%;height:250px;font-family:var(--mono);font-size:12px;padding:8px;border:1px solid var(--border);border-radius:var(--radius);resize:vertical">'
        + this._esc(content) + '</textarea>'
        + '<div style="margin-top:8px;display:flex;gap:8px">'
        + '<button class="btn-audit-keep" onclick="Manager.auditSave(' + lineageId + ')">保存</button>'
        + '<button class="btn btn-reject" onclick="Manager.loadAuditFiles()">取消</button>'
        + '</div></div>';
    } catch (e) {
      alert('加载失败: ' + e.message);
    }
  },

  async auditSave(lineageId) {
    var textarea = document.getElementById('edit-queue-' + lineageId);
    if (!textarea) return;
    var content = textarea.value;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/audit-queue/' + lineageId + '/edit', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content }),
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        alert('保存成功');
        this.loadAuditFiles();
      } else {
        alert(data.detail || '保存失败');
      }
    } catch (e) {
      alert('保存失败: ' + e.message);
    }
  },

  async auditDelete(lineageId) {
    if (!confirm('确认删除该知识页面？此操作不可恢复。')) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/audit-queue/' + lineageId + '/delete', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this.loadAuditFiles();
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  async auditKeep(lineageId) {
    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/audit-queue/' + lineageId + '/keep', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this.loadAuditFiles();
      } else {
        alert(data.detail || '操作失败');
      }
    } catch (e) {
      alert('操作失败: ' + e.message);
    }
  },

  // ========== Wiki Content Management ==========

  _wikiPagesData: [],
  _selectedWikiPath: null,
  _wikiEditing: false,

  _encPath(p) { return p.split('/').map(function(s) { return encodeURIComponent(s); }).join('/'); },

  async loadWikiPages() {
    var section = document.getElementById('wiki-manage-section');
    if (!section) return;
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn() || !Auth.isLeader()) {
      section.style.display = 'none';
      return;
    }
    section.style.display = 'block';

    var cat = document.getElementById('wiki-cat-select').value;
    var list = document.getElementById('wiki-page-list');
    this._searchMode = false;
    list.innerHTML = '<div class="loading">加载中...</div>';

    // Reset detail panel
    this._selectedWikiPath = null;
    this._wikiEditing = false;
    document.getElementById('wiki-page-detail').innerHTML = '<div class="empty-state"><p>点击左侧页面查看内容</p></div>';

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-pages?category=' + cat, {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      if (!resp.ok) {
        list.innerHTML = '<div class="muted">' + this._esc(data.detail || '无权限') + '</div>';
        return;
      }

      this._wikiPagesData = data.pages || [];
      this._renderWikiPages(this._wikiPagesData);
    } catch (e) {
      list.innerHTML = '<div class="muted">加载失败: ' + this._esc(e.message) + '</div>';
    }
  },

  _filterWikiPages() {
    var q = (document.getElementById('wiki-search-filter').value || '').toLowerCase();
    if (!q) {
      this._renderWikiPages(this._wikiPagesData);
      return;
    }
    var filtered = this._wikiPagesData.filter(function(p) {
      return p.title.toLowerCase().indexOf(q) >= 0 || p.path.toLowerCase().indexOf(q) >= 0;
    });
    this._renderWikiPages(filtered);
  },

  _catLabel(cat) {
    var map = { sources: '源文件', syntheses: '合成答案', entities: '实体', concepts: '概念' };
    return map[cat] || cat;
  },

  _renderWikiPages(pages) {
    var list = document.getElementById('wiki-page-list');
    if (pages.length === 0) {
      list.innerHTML = '<div class="muted" style="padding:12px">暂无页面</div>';
      return;
    }

    var isSearch = this._searchMode;
    var html = '<div style="padding:6px 12px;font-size:12px;color:var(--text-muted);border-bottom:1px solid var(--border-subtle)">' + (isSearch ? '搜索结果' : '共') + ' ' + pages.length + ' 个页面</div>';
    for (var i = 0; i < pages.length; i++) {
      var p = pages[i];
      var isActive = this._selectedWikiPath === p.path ? ' active' : '';
      html += '<div class="wpage-item' + isActive + '" data-path="' + this._esc(p.path) + '" data-idx="' + i + '" onclick="Manager.selectWikiPage(' + i + ')">';
      html += '<div class="wpage-title">';
      if (isSearch && p.category) {
        html += '<span class="wpage-cat">' + this._esc(this._catLabel(p.category)) + '</span> ';
      }
      html += this._esc(p.title) + '</div>';
      html += '<div class="wpage-path">' + this._esc(p.path) + '</div>';
      html += '</div>';
    }
    list.innerHTML = html;
  },

  async selectWikiPage(idx) {
    var p = this._wikiPagesData[idx];
    if (!p) return;

    this._selectedWikiPath = p.path;
    this._wikiEditing = false;

    // Highlight active item
    var list = document.getElementById('wiki-page-list');
    var items = list.querySelectorAll('.wpage-item');
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle('active', items[i].dataset.path === p.path);
    }

    // Show loading
    var detail = document.getElementById('wiki-page-detail');
    detail.innerHTML = '<div class="loading">加载中...</div>';

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-page/' + this._encPath(p.path), {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      if (!resp.ok) {
        detail.innerHTML = '<div class="muted">加载失败: ' + this._esc(data.detail) + '</div>';
        return;
      }
      this._currentWikiContent = data.content;
      this._renderWikiDetail(p.path, data.content, false);
    } catch (e) {
      detail.innerHTML = '<div class="muted">加载失败: ' + this._esc(e.message) + '</div>';
    }
  },

  _renderWikiDetail(path, content, editing) {
    var detail = document.getElementById('wiki-page-detail');
    // Determine isSource from path, not dropdown (so it works in search results)
    var isSource = path.startsWith('sources/');
    var self = this;

    var html = '<div class="detail-header">';
    html += '<div class="detail-title">' + this._esc(path) + '</div>';
    html += '<div class="detail-actions">';
    if (editing) {
      html += '<button class="btn-audit-keep" onclick="Manager.saveWikiPage()">保存</button>';
      html += '<button class="btn btn-reject" onclick="Manager._renderWikiDetail(Manager._selectedWikiPath, Manager._currentWikiContent, false)">取消</button>';
    } else {
      html += '<button class="btn-mark-outdated" onclick="Manager._toggleWikiEdit()">编辑</button>';
      if (isSource) {
        html += '<button class="btn-audit-delete" onclick="Manager.markWikiOutdated(\'' + this._esc(path) + '\')">标记过时</button>';
      }
      html += '<button class="btn-audit-delete" onclick="Manager.deleteWikiPage(\'' + this._esc(path) + '\')">删除</button>';
    }
    html += '</div></div>';

    if (editing) {
      html += '<div class="detail-body editing"><textarea id="wiki-edit-area">' + this._esc(content) + '</textarea></div>';
    } else {
      html += '<div class="detail-body">' + this._esc(content) + '</div>';
    }

    detail.innerHTML = html;
  },

  _toggleWikiEdit() {
    this._wikiEditing = !this._wikiEditing;
    this._renderWikiDetail(this._selectedWikiPath, this._currentWikiContent, this._wikiEditing);
  },

  async saveWikiPage() {
    var textarea = document.getElementById('wiki-edit-area');
    if (!textarea) return;
    var path = this._selectedWikiPath;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-page/' + this._encPath(path), {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: textarea.value }),
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this._currentWikiContent = textarea.value;
        this._wikiEditing = false;
        this._renderWikiDetail(path, textarea.value, false);
        alert('保存成功');
      } else {
        alert(data.detail || '保存失败');
      }
    } catch (e) {
      alert('保存失败: ' + e.message);
    }
  },

  async markWikiOutdated(path) {
    var detail = document.getElementById('wiki-page-detail');
    detail.innerHTML = '<div class="loading">正在分析关联知识...</div>';

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-page/' + this._encPath(path) + '/mark-outdated', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      var data = await resp.json();
      if (data.status !== 'ok') {
        detail.innerHTML = '<div class="muted">分析失败: ' + this._esc(data.detail) + '</div>';
        return;
      }

      this._outdatedData = data;
      this._renderOutdatedReport(data);
    } catch (e) {
      detail.innerHTML = '<div class="muted">操作失败: ' + this._esc(e.message) + '</div>';
    }
  },

  _renderOutdatedReport(data) {
    var detail = document.getElementById('wiki-page-detail');
    var r = data.related;
    var total = data.total;

    var html = '<div class="detail-header">';
    html += '<div class="detail-title">过时分析: ' + this._esc(data.source_title) + '</div>';
    html += '<div class="detail-actions">';
    html += '<button class="btn-audit-delete" id="btn-batch-delete" onclick="Manager.batchDelete()">一键删除全部 (' + total + ' 项)</button>';
    html += '<button class="btn btn-reject" onclick="Manager.selectWikiPage(Manager._findPageIdx(Manager._selectedWikiPath))">返回</button>';
    html += '</div></div>';

    html += '<div style="padding:8px 0;font-size:13px;color:var(--text-secondary);border-bottom:1px solid var(--border);margin-bottom:12px">共发现 <strong>' + total + '</strong> 条关联知识，点击"一键删除"将删除以下所有内容</div>';

    // Source file
    html += this._renderOutdatedCategory('源文件', r.source, '📄');
    // Other sources
    if (r.other_sources && r.other_sources.length > 0) {
      html += this._renderOutdatedCategory('关联源文件', r.other_sources, '📄');
    }
    // Entities
    if (r.entities && r.entities.length > 0) {
      html += this._renderOutdatedCategory('实体', r.entities, '🏢');
    }
    // Concepts
    if (r.concepts && r.concepts.length > 0) {
      html += this._renderOutdatedCategory('概念', r.concepts, '💡');
    }
    // Syntheses
    if (r.syntheses && r.syntheses.length > 0) {
      html += this._renderOutdatedCategory('合成答案', r.syntheses, '💬');
    }

    detail.innerHTML = html;
  },

  _renderOutdatedCategory(label, items, icon) {
    if (!items || items.length === 0) return '';
    var html = '<div style="margin-bottom:16px">';
    html += '<div style="font-weight:600;font-size:14px;margin-bottom:6px;color:var(--text)">' + icon + ' ' + label + ' (' + items.length + ')</div>';
    for (var i = 0; i < items.length; i++) {
      html += '<div style="padding:6px 10px;background:var(--bg-alt);border-radius:var(--radius);margin-bottom:4px;font-size:13px;display:flex;justify-content:space-between">';
      html += '<span style="font-weight:500">' + this._esc(items[i].title) + '</span>';
      html += '<span style="color:var(--text-muted);font-size:11px;margin-left:8px;word-break:break-all">' + this._esc(items[i].path) + '</span>';
      html += '</div>';
    }
    html += '</div>';
    return html;
  },

  _findPageIdx(path) {
    for (var i = 0; i < this._wikiPagesData.length; i++) {
      if (this._wikiPagesData[i].path === path) return i;
    }
    return 0;
  },

  async batchDelete() {
    if (!this._outdatedData) return;
    var r = this._outdatedData.related;
    var paths = [];
    var cats = ['source', 'other_sources', 'entities', 'concepts', 'syntheses'];
    for (var c = 0; c < cats.length; c++) {
      var items = r[cats[c]] || [];
      for (var i = 0; i < items.length; i++) {
        paths.push(items[i].path);
      }
    }

    if (paths.length === 0) {
      alert('没有需要删除的内容');
      return;
    }

    if (!confirm('确认删除以下 ' + paths.length + ' 项内容？此操作不可恢复。')) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-pages/batch-delete', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: paths }),
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        alert('已删除 ' + data.deleted_count + ' 项内容');
        this._selectedWikiPath = null;
        this._outdatedData = null;
        document.getElementById('wiki-page-detail').innerHTML = '<div class="empty-state"><p>删除完成，点击左侧查看其他页面</p></div>';
        this.loadWikiPages();
      } else {
        alert(data.detail || '删除失败');
      }
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  },

  async deleteWikiPage(path) {
    if (!confirm('确认删除该页面？此操作不可恢复。\n\n' + path)) return;

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-page/' + this._encPath(path), {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      if (data.status === 'ok') {
        this._selectedWikiPath = null;
        document.getElementById('wiki-page-detail').innerHTML = '<div class="empty-state"><p>点击左侧页面查看内容</p></div>';
        this.loadWikiPages();
      } else {
        alert(data.detail || '删除失败');
      }
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  },

  // ========== Global Search ==========

  _searchMode: false,  // true when viewing search results

  async _doGlobalSearch() {
    var input = document.getElementById('wiki-global-search');
    var q = (input.value || '').trim();
    if (!q) return;

    this._saveSearchHistory(q);
    this._hideSearchHistory();

    var list = document.getElementById('wiki-page-list');
    list.innerHTML = '<div class="loading">搜索中...</div>';
    this._selectedWikiPath = null;
    this._wikiEditing = false;
    document.getElementById('wiki-page-detail').innerHTML = '<div class="empty-state"><p>点击左侧结果查看内容</p></div>';

    try {
      var token = Auth.getToken();
      var resp = await fetch('/api/manage/wiki-search?q=' + encodeURIComponent(q), {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      var data = await resp.json();
      if (!resp.ok) {
        list.innerHTML = '<div class="muted">搜索失败: ' + this._esc(data.detail) + '</div>';
        return;
      }
      var results = data.results || [];
      this._searchMode = true;
      this._wikiPagesData = results;
      this._renderWikiPages(results);
    } catch (e) {
      list.innerHTML = '<div class="muted">搜索失败: ' + this._esc(e.message) + '</div>';
    }
  },

  _getSearchHistoryKey() {
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) return null;
    return 'llmwiki_search_' + Auth.getUsername();
  },

  _getSearchHistory() {
    var key = this._getSearchHistoryKey();
    if (!key) return [];
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  },

  _saveSearchHistory(q) {
    var key = this._getSearchHistoryKey();
    if (!key) return;
    var history = this._getSearchHistory();
    // Remove duplicate
    history = history.filter(function(h) { return h !== q; });
    history.unshift(q);
    // Keep max 20
    if (history.length > 20) history = history.slice(0, 20);
    localStorage.setItem(key, JSON.stringify(history));
  },

  clearSearchHistory() {
    var key = this._getSearchHistoryKey();
    if (key) localStorage.removeItem(key);
    this._hideSearchHistory();
  },

  _showSearchHistory() {
    var history = this._getSearchHistory();
    if (history.length === 0) return;

    var container = document.getElementById('wiki-search-history');
    var listEl = document.getElementById('wiki-search-history-list');
    if (!container || !listEl) return;

    var html = '';
    for (var i = 0; i < history.length; i++) {
      html += '<div class="wiki-search-history-item" onmousedown="Manager._useSearchHistory(\'' + this._esc(history[i]).replace(/'/g, "\\'") + '\')">' + this._esc(history[i]) + '</div>';
    }
    listEl.innerHTML = html;
    container.style.display = 'block';
  },

  _hideSearchHistory() {
    var container = document.getElementById('wiki-search-history');
    if (container) container.style.display = 'none';
  },

  _useSearchHistory(q) {
    var input = document.getElementById('wiki-global-search');
    if (input) {
      input.value = q;
      document.getElementById('wiki-search-clear').style.display = 'block';
    }
    this._doGlobalSearch();
  }
};

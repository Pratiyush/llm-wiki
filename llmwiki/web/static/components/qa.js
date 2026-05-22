/* Q&A chat component — supports Agent loop and simple streaming */

const QA = {
  streaming: false,
  threadId: null,       // current conversation thread ID
  _streamBuf: [],       // buffered SSE events while streaming
  _streamReading: false, // true while ReadableStream pump is active
  historySeq: 0,

  init() {
    this.messagesEl = document.getElementById('chat-messages');
    this.inputEl = document.getElementById('chat-input');
    this.sendBtn = document.getElementById('chat-send');
    this.modelSelect = document.getElementById('model-select');

    this.sendBtn.addEventListener('click', () => this.send());
    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.send();
      }
    });

    this.inputEl.addEventListener('input', () => {
      this.inputEl.style.height = 'auto';
      this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 120) + 'px';
    });

    // Initialize thread sidebar
    if (typeof Threads !== 'undefined') {
      Threads.init();
    }

    window.addEventListener('notebook:change', () => {
      this.clearChat();
      if (typeof Threads !== 'undefined') Threads.refresh();
    });
    window.addEventListener('auth:change', () => this.updateCrossNotebookVisibility());
    this.updateCrossNotebookVisibility();

    console.log('[QA] initialized');
  },

  notebookSlug() {
    return (typeof Notebooks !== 'undefined' && Notebooks.currentSlug)
      ? Notebooks.currentSlug()
      : 'enterprise-management';
  },

  notebookQuery() {
    return 'notebook=' + encodeURIComponent(this.notebookSlug());
  },

  crossNotebookEnabled() {
    var input = document.getElementById('cross-notebook-search');
    return !!(input && input.checked);
  },

  updateCrossNotebookVisibility() {
    var row = document.getElementById('cross-notebook-row');
    if (!row) return;
    var isAdmin = typeof Auth !== 'undefined' && Auth.isAdmin && Auth.isAdmin();
    row.style.display = isAdmin ? 'flex' : 'none';
    if (!isAdmin) {
      var input = document.getElementById('cross-notebook-search');
      if (input) input.checked = false;
    }
  },

  send() {
    const question = this.inputEl.value.trim();
    if (!question || this.streaming) return;

    const model = this.modelSelect?.value || 'deepseek-v4-flash';
    const selectedOption = this.modelSelect?.selectedOptions[0];
    const mode = selectedOption?.dataset.mode || 'stream';
    const useAgent = (mode === 'agent');

    console.log('[QA] sending:', question, 'model:', model, 'mode:', mode);

    this.addMessage('user', question);
    this.inputEl.value = '';
    this.inputEl.style.height = 'auto';

    const msgEl = this.addMessage('assistant', '');
    const bubble = msgEl.querySelector('.msg-bubble');

    this.streaming = true;
    this.sendBtn.disabled = true;

    if (useAgent) {
      this._sendAgent(question, model, msgEl, bubble);
    } else {
      this._sendStream(question, model, msgEl, bubble);
    }
  },

  /* --- Load user's chat history --- */
  loadHistory() {
    var self = this;
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) return;

    self.clearChat();

    var token = Auth.getToken();
    var slug = this.notebookSlug();
    var seq = ++this.historySeq;
    fetch('/api/query/history?token=' + encodeURIComponent(token) + '&' + this.notebookQuery())
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (seq !== self.historySeq || self.notebookSlug() !== slug) return;
      if (!data.history || data.history.length === 0) return;
      self.messagesEl.innerHTML = '';
      var lastThreadId = null;
      data.history.forEach(function(item) {
        self.addMessage('user', item.question);
        var msgEl = self.addMessage('assistant', '');
        var bubble = msgEl.querySelector('.msg-bubble');
        bubble.innerHTML = self.renderMarkdown(item.answer);
        bubble._raw = item.answer;
        msgEl.dataset.msgId = item.id;
        self._bindActions(msgEl, bubble, item.question, item.answer, item.saved_to_wiki);
        if (item.thread_id) lastThreadId = item.thread_id;
      });
      self.messagesEl.scrollTop = self.messagesEl.scrollHeight;
      if (lastThreadId) {
        self.threadId = lastThreadId;
        self._updateThreadIndicator();
      }
    });
  },

  /* --- Clear chat area --- */
  clearChat() {
    if (!this.messagesEl) return;
    this.threadId = null;
    this._updateThreadIndicator();
    this.messagesEl.innerHTML = '';
    // Restore welcome with model selector
    var welcome = document.createElement('div');
    welcome.className = 'chat-welcome';
    welcome.innerHTML = '<h2>知识库问答</h2><p>输入问题，我会基于已入库的知识为你解答</p>' +
      '<div class="model-selector"><label>模型：</label>' +
      '<select id="model-select" onchange="QA.modelSelect=this">' +
      '<option value="deepseek-v4-flash" data-mode="agent" selected>DeepSeek V4 Flash（推荐）</option>' +
      '<option value="deepseek-v3.2" data-mode="agent">DeepSeek V3.2</option>' +
      '<option value="deepseek-v4-pro" data-mode="agent">DeepSeek V4 Pro</option>' +
      '<option value="kimi-k2.5" data-mode="agent">Kimi K2.5</option>' +
      '</select></div>' +
      '<label class="cross-notebook-row" id="cross-notebook-row" style="display:none">' +
      '<input type="checkbox" id="cross-notebook-search"> 跨知识库搜索</label>';
    this.messagesEl.appendChild(welcome);
    this.modelSelect = document.getElementById('model-select');
    this.updateCrossNotebookVisibility();
  },

  /* --- Clear history --- */
  clearAllHistory() {
    var self = this;
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) return;
    if (!confirm('确定清空所有问答历史？')) return;

    var token = Auth.getToken();
    fetch('/api/query/history?token=' + encodeURIComponent(token) + '&' + this.notebookQuery(), { method: 'DELETE' })
    .then(function() { self.clearChat(); });
  },

  /* --- Load a specific thread's messages --- */
  loadThread(threadId) {
    var self = this;
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) return;
    var slug = this.notebookSlug();
    var seq = ++this.historySeq;

    this.clearChat();
    this.threadId = threadId;
    this._updateThreadIndicator();

    var token = Auth.getToken();
    fetch('/api/query/messages?thread_id=' + threadId + '&token=' + encodeURIComponent(token) + '&' + this.notebookQuery())
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (seq !== self.historySeq || self.notebookSlug() !== slug) return;
        if (!data.messages || !data.messages.length) return;
        self.messagesEl.innerHTML = '';
        data.messages.forEach(function(item) {
          self.addMessage('user', item.question);
          var msgEl = self.addMessage('assistant', '');
          var bubble = msgEl.querySelector('.msg-bubble');
          bubble.innerHTML = self.renderMarkdown(
            item.answer.split(/##\s*追问建议/)[0].trim()
          );
          bubble._raw = item.answer;
          bubble.dataset.msgId = item.id;
          msgEl.dataset.msgId = item.id;
          self._bindActions(msgEl, bubble, item.question, item.answer, item.saved_to_wiki);
        });
        self.messagesEl.scrollTop = self.messagesEl.scrollHeight;
      });
  },

  /* --- Agent mode: parse JSON SSE events --- */
  _sendAgent(question, model, msgEl, bubble) {
    const self = this;
    const stepsEl = document.createElement('div');
    stepsEl.className = 'agent-steps';
    bubble.appendChild(stepsEl);

    const answerEl = document.createElement('div');
    answerEl.className = 'agent-answer';
    answerEl._raw = '';
    bubble.appendChild(answerEl);

    let fullAnswer = '';
    let pagesRead = 0;
    self._streamBuf = [];
    self._streamReading = true;

    // Flush buffered events to DOM on visibility change (tab switch back)
    function flushBuffer() {
      if (self._streamBuf.length === 0) return;
      for (var i = 0; i < self._streamBuf.length; i++) {
        var evt = self._streamBuf[i];
        self._handleAgentEvent(evt, stepsEl, answerEl);
      }
      self._streamBuf = [];
      self.messagesEl.scrollTop = self.messagesEl.scrollHeight;
    }

    var onVisChange = function() {
      if (!document.hidden) flushBuffer();
    };
    document.addEventListener('visibilitychange', onVisChange);

    var token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
    fetch('/api/query/agent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        model,
        token,
        thread_id: self.threadId,
        notebook_slug: self.notebookSlug(),
        cross_notebook: self.crossNotebookEnabled(),
      }),
    })
    .then(function(resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let done = false;

      function read() {
        reader.read().then(function(result) {
          if (result.done) {
            flushBuffer();
            self._streamReading = false;
            document.removeEventListener('visibilitychange', onVisChange);
            self._onDone(msgEl, bubble, question, fullAnswer);
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const raw = line.slice(6);
            if (raw === '[DONE]') {
              flushBuffer();
              self._streamReading = false;
              document.removeEventListener('visibilitychange', onVisChange);
              self._onDone(msgEl, bubble, question, fullAnswer);
              return;
            }
            try {
              const evt = JSON.parse(raw);
              if (evt.type === 'content' && evt.text) {
                fullAnswer += evt.text;
              }
              if (evt.type === 'done' && evt.answer) {
                fullAnswer = evt.answer;
              }
              if (evt.type === 'thread' && evt.thread_id) {
                self.threadId = evt.thread_id;
                self._updateThreadIndicator();
              }
              // If tab is visible, render immediately; otherwise buffer
              if (!document.hidden) {
                self._handleAgentEvent(evt, stepsEl, answerEl);
                self.messagesEl.scrollTop = self.messagesEl.scrollHeight;
              } else {
                self._streamBuf.push(evt);
              }
            } catch (e) {
              console.warn('[QA] skip non-JSON SSE line:', raw);
            }
          }
          read();
        }).catch(function(err) {
          console.error('[QA] agent read error:', err);
          flushBuffer();
          self._streamReading = false;
          document.removeEventListener('visibilitychange', onVisChange);
          self._onDone(msgEl, bubble, question, fullAnswer || '读取失败: ' + err.message);
        });
      }
      read();
    })
    .catch(function(err) {
      console.error('[QA] agent fetch error:', err);
      bubble.innerHTML = '请求失败: ' + err.message;
      self.streaming = false;
      self.sendBtn.disabled = false;
      self._streamReading = false;
      document.removeEventListener('visibilitychange', onVisChange);
    });
  },

  _handleAgentEvent(evt, stepsEl, answerEl) {
    switch (evt.type) {
      case 'thinking': {
        const step = document.createElement('div');
        step.className = 'agent-step agent-thinking';
        step.textContent = evt.message;
        stepsEl.appendChild(step);
        break;
      }
      case 'tool_call': {
        const step = document.createElement('div');
        step.className = 'agent-step agent-tool-call';
        const detail = evt.tool === 'search_wiki'
          ? '搜索: "' + evt.args.query + '"'
          : '阅读: ' + evt.args.path;
        step.textContent = '[工具] ' + detail;
        stepsEl.appendChild(step);
        break;
      }
      case 'tool_result': {
        const step = document.createElement('div');
        step.className = 'agent-step agent-tool-result';
        step.textContent = evt.tool === 'search_wiki'
          ? '找到 ' + evt.count + ' 条结果'
          : evt.preview.substring(0, 80) + '...';
        stepsEl.appendChild(step);
        break;
      }
      case 'content': {
        answerEl._raw = (answerEl._raw || '') + evt.text;
        answerEl.innerHTML = this.renderMarkdown(answerEl._raw);
        break;
      }
      case 'thread': {
        this.threadId = evt.thread_id;
        this._updateThreadIndicator();
        break;
      }
      case 'error': {
        answerEl.innerHTML = '<span style="color:#e74c3c">错误: ' + this.escapeHtml(evt.message) + '</span>';
        break;
      }
      case 'done': {
        stepsEl.classList.add('agent-steps-done');
        const summary = document.createElement('div');
        summary.className = 'agent-summary';
        summary.textContent = '(' + evt.iterations + ' 轮思考, 阅读 ' + evt.pages_read + ' 个页面)';
        stepsEl.appendChild(summary);
        if (evt.answer) {
          answerEl._raw = evt.answer;
          // Strip follow-up section before rendering to avoid visual flash
          answerEl.innerHTML = this.renderMarkdown(
            evt.answer.split(/##\s*追问建议/)[0].trim()
          );
        }
        break;
      }
    }
  },

  /* --- Simple streaming mode (original RAG) --- */
  _sendStream(question, model, msgEl, bubble) {
    const self = this;
    let fullAnswer = '';

    fetch('/api/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        model,
        token: (typeof Auth !== 'undefined') ? Auth.getToken() : '',
        notebook_slug: self.notebookSlug(),
        cross_notebook: self.crossNotebookEnabled(),
      }),
    })
    .then(function(resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      function read() {
        reader.read().then(function(result) {
          if (result.done) {
            self._onDone(msgEl, bubble, question, fullAnswer);
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') {
                self._onDone(msgEl, bubble, question, fullAnswer);
                return;
              }
              fullAnswer += data;
              bubble.innerHTML = self.renderMarkdown(fullAnswer);
              self.messagesEl.scrollTop = self.messagesEl.scrollHeight;
            }
          }
          read();
        }).catch(function(err) {
          self._onDone(msgEl, bubble, question, fullAnswer || '读取失败: ' + err.message);
        });
      }
      read();
    })
    .catch(function(err) {
      bubble.innerHTML = '请求失败: ' + err.message;
      self.streaming = false;
      self.sendBtn.disabled = false;
    });
  },

  /* --- Common completion handler --- */
  _onDone(msgEl, bubble, question, answer) {
    console.log('[QA] done, answer length:', answer.length);
    this.streaming = false;
    this.sendBtn.disabled = false;
    if (typeof Threads !== 'undefined') {
      Threads.setActive(this.threadId);
      Threads.refresh();
    }
    if (answer) {
      var followups = this._extractFollowups(answer);
      // Non-agent path: render clean markdown (agent path already rendered in _handleAgentEvent)
      if (!bubble.querySelector('.agent-steps') && !bubble.querySelector('.agent-answer')) {
        bubble.innerHTML = followups.length > 0
          ? this.renderMarkdown(answer.split(/##\s*追问建议/)[0].trim())
          : this.renderMarkdown(answer);
      }
      this._bindActions(msgEl, bubble, question, answer);
      if (followups.length > 0) {
        this._renderFollowupChips(msgEl, followups);
      }
    }
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  },

  /* --- Bind wikilinks + action buttons to a message --- */
  _bindActions(msgEl, bubble, question, answer, savedToWiki) {
    var self = this;
    // Bind wikilink clicks
    bubble.querySelectorAll('.wikilink').forEach(function(el) {
      el.addEventListener('click', function() {
        var raw = el.textContent.replace('[[', '').replace(']]', '').trim();
        QA.openSourcePage(raw);
      });
    });

    var actions = document.createElement('div');
    actions.className = 'msg-actions';

    // Edit button (toggle raw text editing)
    var editBtn = document.createElement('button');
    editBtn.textContent = '编辑';
    editBtn.addEventListener('click', function() {
      self._toggleEdit(bubble, editBtn, question);
    });
    actions.appendChild(editBtn);

    // Save to Wiki button
    var saveBtn = document.createElement('button');
    if (savedToWiki) {
      saveBtn.textContent = '已保存 Wiki';
      saveBtn.disabled = true;
      saveBtn.className = 'btn-saved';
    } else {
      saveBtn.textContent = this._getSaveButtonLabel();
      saveBtn.addEventListener('click', function() {
        var currentAnswer = bubble._raw || answer;
        self.saveAnswer(saveBtn, question, currentAnswer);
      });
    }
    actions.appendChild(saveBtn);

    // Export MD button
    var exportBtn = document.createElement('button');
    exportBtn.textContent = '导出MD';
    exportBtn.addEventListener('click', function() {
      var currentAnswer = bubble._raw || answer;
      self.exportMD(exportBtn, question, currentAnswer);
    });
    actions.appendChild(exportBtn);

    // Re-ask with different model
    var reaskWrap = document.createElement('span');
    reaskWrap.className = 'msg-reask';
    var reaskSel = document.createElement('select');
    reaskSel.className = 'reask-model-sel';
    reaskSel.innerHTML = '<option value="deepseek-v4-flash">V4 Flash</option>'
      + '<option value="deepseek-v3.2">V3.2</option>'
      + '<option value="deepseek-v4-pro">V4 Pro</option>'
      + '<option value="kimi-k2.5">Kimi</option>';
    reaskWrap.appendChild(reaskSel);
    var reaskBtn = document.createElement('button');
    reaskBtn.textContent = '重新回答';
    reaskBtn.addEventListener('click', function() {
      self.reAsk(question, reaskSel.value);
    });
    reaskWrap.appendChild(reaskBtn);
    actions.appendChild(reaskWrap);

    msgEl.appendChild(actions);
  },

  /* --- Toggle edit mode on a bubble --- */
  _toggleEdit(bubble, btn, question) {
    if (bubble._editing) {
      // Save edit
      var textarea = bubble.querySelector('.edit-area');
      if (textarea) {
        bubble._raw = textarea.value;
        // Re-render only the answer part (keep agent-steps if any)
        var stepsEl = bubble.querySelector('.agent-steps');
        bubble.innerHTML = '';
        if (stepsEl) bubble.appendChild(stepsEl);
        var answerEl = document.createElement('div');
        answerEl.className = 'agent-answer';
        answerEl.innerHTML = this.renderMarkdown(textarea.value);
        bubble.appendChild(answerEl);
      }
      btn.textContent = '编辑';
      bubble._editing = false;
    } else {
      // Enter edit mode
      var raw = bubble._raw || '';
      // Collect all text content from agent-answer or direct content
      if (!raw) {
        var answerEl = bubble.querySelector('.agent-answer') || bubble;
        raw = answerEl.innerText || answerEl.textContent || '';
      }
      var stepsEl = bubble.querySelector('.agent-steps');
      bubble.innerHTML = '';
      if (stepsEl) bubble.appendChild(stepsEl);

      var textarea = document.createElement('textarea');
      textarea.className = 'edit-area';
      textarea.value = raw;
      bubble.appendChild(textarea);

      btn.textContent = '完成编辑';
      bubble._editing = true;
      bubble._raw = raw;
    }
  },

  /* --- Extract follow-up suggestions from answer --- */
  _extractFollowups(text) {
    var match = text.match(/##\s*追问建议\s*\n([\s\S]*)/);
    if (!match) return [];
    var section = match[1].trim();
    var questions = [];
    var lines = section.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line.startsWith('- ')) {
        var q = line.slice(2).trim();
        if (q) questions.push(q);
      }
    }
    return questions;
  },

  /* --- Render clickable follow-up chips --- */
  _renderFollowupChips(msgEl, questions) {
    var self = this;
    var container = document.createElement('div');
    container.className = 'followup-chips';
    for (var i = 0; i < questions.length; i++) {
      (function(q) {
        var chip = document.createElement('button');
        chip.className = 'followup-chip';
        chip.textContent = q;
        chip.addEventListener('click', function() { self._sendFollowup(q); });
        container.appendChild(chip);
      })(questions[i]);
    }
    msgEl.appendChild(container);
  },

  /* --- Submit a follow-up question (preserves thread) --- */
  _sendFollowup(question) {
    if (this.streaming) return;
    this.inputEl.value = question;
    this.inputEl.style.height = 'auto';
    this.inputEl.style.height = Math.min(this.inputEl.scrollHeight, 120) + 'px';
    this.inputEl.focus();
    this.send();
  },

  /* --- Start a new conversation thread --- */
  _newThread() {
    this.threadId = null;
    this._updateThreadIndicator();
    if (typeof Threads !== 'undefined') Threads.setActive(null);
    this.clearChat();
  },

  /* --- Delete the current thread on server and locally --- */
  _deleteCurrentThread() {
    if (!this.threadId) return;
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) return;
    if (!confirm('确定删除当前对话线程及其所有消息？')) return;
    var self = this;
    var tid = this.threadId;
    var token = Auth.getToken();
    fetch('/api/query/thread/' + tid + '?token=' + encodeURIComponent(token) + '&' + this.notebookQuery(), { method: 'DELETE' })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.status === 'ok') {
          self._newThread();
        }
      });
  },

  /* --- Show/hide thread indicator bar --- */
  _updateThreadIndicator() {
    var bar = document.getElementById('chat-thread-bar');
    if (bar) {
      bar.style.display = this.threadId ? 'flex' : 'none';
    }
  },

  addMessage(role, content) {
    const div = document.createElement('div');
    div.className = 'msg msg-' + role;
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    if (role === 'user') {
      bubble.textContent = content;
    }
    div.appendChild(bubble);
    this.messagesEl.appendChild(div);
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    return div;
  },

  renderMarkdown(text) {
    // Line-by-line parser for clean structure
    var lines = text.split('\n');
    var html = '';
    var inList = false;
    var inCodeBlock = false;
    var codeLang = '';

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];

      // Fenced code blocks
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          html += '</code></pre>';
          inCodeBlock = false;
        } else {
          codeLang = line.slice(3).trim();
          html += '<pre class="md-code-block"><code>';
          inCodeBlock = true;
        }
        continue;
      }
      if (inCodeBlock) {
        html += this.escapeHtml(line) + '\n';
        continue;
      }

      // Close list if current line is not a list item
      var isOrderedList = /^\d+\.\s/.test(line);
      var isUnorderedList = /^[-*]\s/.test(line);
      if (inList && !isOrderedList && !isUnorderedList) {
        html += '</ul>';
        inList = false;
      }

      // Headings (after escaping)
      if (line.startsWith('### ')) {
        html += '<h4 class="md-h">' + this._inlineFormat(line.slice(4)) + '</h4>';
      } else if (line.startsWith('## ')) {
        html += '<h3 class="md-h">' + this._inlineFormat(line.slice(3)) + '</h3>';
      } else if (line.startsWith('# ')) {
        html += '<h3 class="md-h md-h1">' + this._inlineFormat(line.slice(2)) + '</h3>';
      }
      // Horizontal rule
      else if (/^---+$/.test(line.trim())) {
        html += '<hr class="md-hr">';
      }
      // Blockquote
      else if (line.startsWith('> ')) {
        html += '<blockquote class="md-quote">' + this._inlineFormat(line.slice(2)) + '</blockquote>';
      }
      // Ordered list
      else if (isOrderedList) {
        var content = line.replace(/^\d+\.\s/, '');
        html += '<div class="md-li md-li-ordered">' + this._inlineFormat(content) + '</div>';
      }
      // Unordered list
      else if (isUnorderedList) {
        var content = line.replace(/^[-*]\s/, '');
        html += '<div class="md-li">' + this._inlineFormat(content) + '</div>';
        if (!inList) inList = true;
      }
      // Empty line
      else if (line.trim() === '') {
        html += '<div class="md-blank"></div>';
      }
      // Normal paragraph
      else {
        html += '<p class="md-p">' + this._inlineFormat(line) + '</p>';
      }
    }
    if (inCodeBlock) html += '</code></pre>';
    if (inList) html += '</ul>';

    return html;
  },

  _inlineFormat(text) {
    var html = this.escapeHtml(text);
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
    html = html.replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink">[[$1]]</span>');
    html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');
    return html;
  },

  escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  },

  async saveAnswer(btn, question, answer) {
    // Check login status
    if (typeof Auth !== 'undefined' && !Auth.isLoggedIn()) {
      Auth.showModal();
      return;
    }

    var isLeader = typeof Auth !== 'undefined' && Auth.isLeader();
    btn.disabled = true;

    if (isLeader) {
      btn.textContent = '保存中...';
    } else {
      btn.textContent = '提交审核中...';
    }

    try {
      var token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
      var resp = await fetch('/api/query/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: question,
          answer: answer,
          token: token,
          notebook_slug: this.notebookSlug(),
        }),
      });
      var data = await resp.json();

      if (data.mode === 'direct') {
        btn.textContent = '已保存 Wiki';
        btn.disabled = true;
        btn.className = 'btn-saved';
      } else if (data.status === 'pending') {
        btn.textContent = '已提交，待审批';
        btn.disabled = true;
        btn.className = 'btn-saved';
      } else {
        btn.textContent = data.message || '操作完成';
      }
    } catch (e) {
      btn.textContent = '操作失败';
    }
  },

  _getSaveButtonLabel() {
    if (typeof Auth === 'undefined' || !Auth.isLoggedIn()) return '保存到 Wiki';
    return Auth.isLeader() ? '保存到 Wiki' : '提交审批';
  },

  async exportMD(btn, question, answer) {
    var today = new Date().toISOString().slice(0, 10);
    var defaultName = question.substring(0, 20).replace(/[\\/:*?"<>|]/g, '').trim() || '问答';

    var filename = prompt('请输入文件名（无需 .md 后缀）:', defaultName);
    if (!filename) return;
    filename = filename.trim();
    if (!filename) return;
    if (!filename.endsWith('.md')) filename += '.md';

    var content = '# ' + question + '\n\n'
      + '> 生成日期: ' + today + '\n\n'
      + '---\n\n'
      + answer + '\n';

    // Try modern File System Access API (Chrome/Edge)
    if (window.showSaveFilePicker) {
      try {
        var handle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: 'Markdown', accept: { 'text/markdown': ['.md'] } }],
        });
        var writable = await handle.createWritable();
        await writable.write(content);
        await writable.close();
        btn.textContent = '已导出';
        setTimeout(function() { btn.textContent = '导出MD'; }, 2000);
        return;
      } catch (e) {
        if (e.name === 'AbortError') return; // User cancelled
      }
    }

    // Fallback: download via blob
    var blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    btn.textContent = '已导出';
    setTimeout(function() { btn.textContent = '导出MD'; }, 2000);
  },

  reAsk(question, model) {
    if (this.streaming) return;
    // Re-ask with a fresh thread — model comparison should be independent
    this.threadId = null;
    this._updateThreadIndicator();
    var msgEl = this.addMessage('assistant', '');
    var bubble = msgEl.querySelector('.msg-bubble');
    bubble.innerHTML = '<div class="agent-step agent-thinking">正在用 ' + model + ' 重新回答...</div>';
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    this._sendAgent(question, model, msgEl, bubble);
  },

  openSourcePage(name) {
    // Switch to wiki tab
    var tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(function(t) {
      if (t.dataset.tab === 'wiki') t.click();
    });

    // Wait for tab switch, then search and open
    setTimeout(function() {
      if (typeof Browser !== 'undefined') {
        // Ensure tree is loaded
        if (!Browser.tree) {
          Browser.loadTree().then(function() {
            QA._findAndOpenPage(name);
          });
        } else {
          QA._findAndOpenPage(name);
        }
      }
    }, 300);
  },

  _findAndOpenPage(name) {
    if (!Browser.tree) return;
    // Search across all categories for matching page
    for (var cat in Browser.tree) {
      var pages = Browser.tree[cat];
      for (var i = 0; i < pages.length; i++) {
        var page = pages[i];
        if (page.title === name || page.name === name ||
            page.path.indexOf(name) !== -1 || page.title.indexOf(name) !== -1) {
          Browser.loadPage(page.path);
          return;
        }
      }
    }
    // Fallback: try API search
    fetch('/api/pages/search?q=' + encodeURIComponent(name) + '&' + this.notebookQuery())
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.results && data.results.length > 0) {
          Browser.loadPage(data.results[0].path);
        } else {
          Browser.contentEl.innerHTML = '<div class="empty-state"><p>未找到页面: ' + name + '</p></div>';
        }
      });
  }
};

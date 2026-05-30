/* Upload component — with version confirmation */

const Uploader = {
  pendingFiles: null,
  webMode: 'auto',

  init() {
    this.dropzone = document.getElementById('upload-dropzone');
    this.input = document.getElementById('upload-input');
    this.btn = document.getElementById('upload-btn');
    this.results = document.getElementById('upload-results');
    this.modal = document.getElementById('upload-confirm-modal');
    this.versionInput = document.getElementById('upload-version-note');
    this.fileInfo = document.getElementById('upload-confirm-file-info');
    this.confirmBtn = document.getElementById('upload-confirm-btn');
    this.closeBtn = document.getElementById('upload-confirm-close');

    // Click to select files
    this.btn.addEventListener('click', (e) => {
      e.stopPropagation();
      this.input.click();
    });
    this.dropzone.addEventListener('click', () => this.input.click());

    // File selected → show confirm modal
    this.input.addEventListener('change', () => {
      if (this.input.files.length) {
        this._showConfirm(this.input.files);
      }
    });

    // Drag & drop → show confirm modal
    this.dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.dropzone.classList.add('drag-over');
    });
    this.dropzone.addEventListener('dragleave', () => {
      this.dropzone.classList.remove('drag-over');
    });
    this.dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      this.dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files.length) {
        this._showConfirm(e.dataTransfer.files);
      }
    });

    // Confirm modal actions
    this.closeBtn.addEventListener('click', () => this._hideConfirm());
    this.confirmBtn.addEventListener('click', () => this._doUpload());

    this.webUrl = document.getElementById('web-import-url');
    this.webTitle = document.getElementById('web-import-title');
    this.webContent = document.getElementById('web-import-content');
    this.webNote = document.getElementById('web-import-note');
    this.webImportBtn = document.getElementById('web-import-btn');
    this.webModeAuto = document.getElementById('web-mode-auto');
    this.webModeManual = document.getElementById('web-mode-manual');
    if (this.webImportBtn) {
      this.webModeAuto.addEventListener('click', () => this._setWebMode('auto'));
      this.webModeManual.addEventListener('click', () => this._setWebMode('manual'));
      this.webImportBtn.addEventListener('click', () => this.importUrl());
    }

    window.addEventListener('notebook:change', () => {
      if (this.results) this.results.innerHTML = '';
    });
  },

  notebookSlug() {
    return (typeof Notebooks !== 'undefined' && Notebooks.currentSlug)
      ? Notebooks.currentSlug()
      : 'enterprise-management';
  },

  _showConfirm(files) {
    this.pendingFiles = files;
    var names = [];
    for (var i = 0; i < files.length; i++) {
      names.push(files[i].name + ' (' + (files[i].size / 1024).toFixed(1) + ' KB)');
    }
    this.fileInfo.textContent = '待上传: ' + names.join(', ');
    this.versionInput.value = '';
    this.modal.style.display = 'flex';
    this.versionInput.focus();
  },

  _hideConfirm() {
    this.pendingFiles = null;
    this.modal.style.display = 'none';
    this.input.value = '';
  },

  _doUpload() {
    var versionNote = this.versionInput.value.trim();
    if (!versionNote) {
      this.versionInput.style.borderColor = '#e74c3c';
      this.versionInput.focus();
      return;
    }
    this.versionInput.style.borderColor = '';
    this.modal.style.display = 'none';
    this.uploadFiles(this.pendingFiles, versionNote);
    this.pendingFiles = null;
    this.input.value = '';
  },

  async uploadFiles(files, versionNote) {
    for (const file of files) {
      const item = document.createElement('div');
      item.className = 'upload-item';
      item.innerHTML = '<div class="status pending"></div><div><strong>' + file.name + '</strong> <span class="muted">(' + (file.size / 1024).toFixed(1) + ' KB)</span><br><span class="upload-status">上传中...</span></div>';
      this.results.appendChild(item);

      try {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('version_note', versionNote || '');
        const headers = {};
        // Attach token if logged in
        if (typeof Auth !== 'undefined' && Auth.isLoggedIn()) {
          const token = Auth.getToken();
          fd.append('token', token);
          headers['Authorization'] = 'Bearer ' + token;
        }
        fd.append('notebook', this.notebookSlug());
        const resp = await fetch('/api/upload/file?notebook=' + encodeURIComponent(this.notebookSlug()), { method: 'POST', body: fd, headers: headers });
        const data = await resp.json().catch(() => ({}));

        const statusDot = item.querySelector('.status');
        const statusText = item.querySelector('.upload-status');

        if (!resp.ok) {
          statusDot.className = 'status error';
          if (resp.status === 401) {
            statusText.textContent = '登录已过期，请重新登录后再上传';
            if (typeof Auth !== 'undefined' && Auth.logout) Auth.logout();
          } else {
            statusText.textContent = data.detail || data.message || ('上传失败: HTTP ' + resp.status);
          }
        } else if (data.status === 'ok') {
          statusDot.className = 'status success';
          let detail = '转换成功 (' + data.content_length + ' 字符)';
          if (data.version_note) {
            detail += '<br>版本: ' + data.version_note;
          }
          if (data.entities_extracted || data.concepts_extracted) {
            detail += '<br>AI 提取: ' + data.entities_extracted + ' 个实体, ' + data.concepts_extracted + ' 个概念';
          }
          if (data.new_pages && data.new_pages.length) {
            detail += '<br>新建页面: ' + data.new_pages.join(', ');
          }
          detail += '<br>→ <a href="#wiki" onclick="Uploader.openPage(\'' + data.wiki_path + '\')">' + data.wiki_path + '</a>';
          statusText.innerHTML = detail;
        } else {
          statusDot.className = 'status error';
          statusText.textContent = data.message || '上传失败';
        }
      } catch (e) {
        item.querySelector('.status').className = 'status error';
        item.querySelector('.upload-status').textContent = '请求失败: ' + e.message;
      }
    }
  },

  _setWebMode(mode) {
    this.webMode = mode;
    this.webModeAuto.classList.toggle('active', mode === 'auto');
    this.webModeManual.classList.toggle('active', mode === 'manual');
    document.querySelectorAll('.web-manual-only').forEach((el) => {
      el.style.display = mode === 'manual' ? '' : 'none';
    });
  },

  async importUrl() {
    const url = (this.webUrl.value || '').trim();
    const item = document.createElement('div');
    item.className = 'upload-item';
    item.innerHTML = '<div class="status pending"></div><div><strong>' + this._escapeHtml(url || 'URL') + '</strong><br><span class="upload-status">Importing web source...</span></div>';
    this.results.appendChild(item);

    if (!url) {
      item.querySelector('.status').className = 'status error';
      item.querySelector('.upload-status').textContent = 'URL is required';
      return;
    }

    const headers = { 'Content-Type': 'application/json' };
    const body = {
      url: url,
      mode: this.webMode,
      title: this.webTitle ? this.webTitle.value.trim() : '',
      content: this.webContent ? this.webContent.value : '',
      version_note: this.webNote ? this.webNote.value.trim() : '',
      notebook: this.notebookSlug()
    };

    if (typeof Auth !== 'undefined' && Auth.isLoggedIn()) {
      const token = Auth.getToken();
      body.token = token;
      headers.Authorization = 'Bearer ' + token;
    }

    try {
      const resp = await fetch('/api/upload/url', {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(body)
      });
      const data = await resp.json().catch(() => ({}));
      const statusDot = item.querySelector('.status');
      const statusText = item.querySelector('.upload-status');

      if (!resp.ok) {
        statusDot.className = 'status error';
        statusText.textContent = data.detail || 'Import failed: HTTP ' + resp.status;
      } else if (data.status === 'ok') {
        statusDot.className = 'status success';
        statusText.innerHTML = 'Imported ' + data.content_length + ' characters'
          + '<br>URL: ' + this._escapeHtml(data.canonical_url || data.url)
          + '<br>Page: <a href="#wiki" onclick="Uploader.openPage(\'' + data.wiki_path + '\')">' + data.wiki_path + '</a>';
      } else {
        statusDot.className = 'status error';
        statusText.textContent = data.message || 'Import failed';
        if (data.code && data.code.indexOf('fetch') === 0) this._setWebMode('manual');
      }
    } catch (e) {
      item.querySelector('.status').className = 'status error';
      item.querySelector('.upload-status').textContent = 'Request failed: ' + e.message;
    }
  },

  _escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, (ch) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[ch]));
  },

  openPage(path) {
    window.location.hash = 'wiki';
    setTimeout(() => {
      if (typeof Browser !== 'undefined' && Browser.loadPage) {
        Browser.loadPage(path);
      }
    }, 200);
  }
};

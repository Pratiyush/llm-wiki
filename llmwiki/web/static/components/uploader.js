/* Upload component — with version confirmation */

const Uploader = {
  pendingFiles: null,

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

  openPage(path) {
    window.location.hash = 'wiki';
    setTimeout(() => {
      if (typeof Browser !== 'undefined' && Browser.loadPage) {
        Browser.loadPage(path);
      }
    }, 200);
  }
};

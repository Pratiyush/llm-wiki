/* Wiki browser component */

const Browser = {
  tree: null,
  currentPage: null,

  init() {
    this.sidebar = document.getElementById('wiki-sidebar');
    this.treeEl = document.getElementById('wiki-tree');
    this.contentEl = document.getElementById('wiki-content');
    this.searchInput = document.getElementById('wiki-search');

    // Search
    let searchTimer;
    this.searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => this.doSearch(), 300);
    });

    // Wikilink clicks
    this.contentEl.addEventListener('click', (e) => {
      if (e.target.classList.contains('wikilink')) {
        e.preventDefault();
        const name = e.target.textContent;
        this.navigateToName(name);
      }
    });

    // Tab show event
    window.addEventListener('tab:show', (e) => {
      if (e.detail.tab === 'wiki' && !this.tree) {
        this.loadTree();
      }
    });
  },

  async loadTree() {
    try {
      const data = await API.getTree();
      this.tree = data.tree;
      this.renderTree();
    } catch (e) {
      this.treeEl.innerHTML = `<div class="loading">加载失败: ${e.message}</div>`;
    }
  },

  renderTree() {
    if (!this.tree) return;

    const categories = {
      'sources': '源文件',
      'entities': '实体',
      'concepts': '概念',
      'syntheses': '知识页',
      'root': '概览',
    };

    let html = '';
    // Root pages first
    if (this.tree.root) {
      for (const page of this.tree.root) {
        html += this.renderItem(page);
      }
    }
    // Category sections
    for (const [cat, pages] of Object.entries(this.tree)) {
      if (cat === 'root') continue;
      const label = categories[cat] || cat;
      html += `<div class="tree-section">
        <div class="tree-section-title">${label} (${pages.length})</div>`;
      for (const page of pages) {
        html += this.renderItem(page);
      }
      html += '</div>';
    }

    this.treeEl.innerHTML = html || '<div class="muted">暂无页面</div>';

    // Click handlers
    this.treeEl.querySelectorAll('.tree-item').forEach(el => {
      el.addEventListener('click', () => {
        const path = el.dataset.path;
        this.loadPage(path);
      });
    });
  },

  renderItem(page) {
    const icon = page.type === 'source' ? '&#128196;' :
                 page.type === 'entity' ? '&#127970;' :
                 page.type === 'concept' ? '&#128161;' :
                 page.type === 'synthesis' ? '&#128218;' : '&#128209;';
    return `<a class="tree-item" data-path="${page.path}" title="${page.title}">${icon} ${page.title}</a>`;
  },

  async loadPage(path) {
    // Update active state
    this.treeEl.querySelectorAll('.tree-item').forEach(el => {
      el.classList.toggle('active', el.dataset.path === path);
    });

    this.contentEl.innerHTML = '<div class="loading">加载中...</div>';

    try {
      const data = await API.getPage(path);
      if (data.error) {
        this.contentEl.innerHTML = `<div class="empty-state"><p>页面不存在: ${path}</p></div>`;
        return;
      }
      this.currentPage = path;
      // Render metadata
      let metaHtml = '';
      if (data.meta && data.meta.title) {
        metaHtml = `<div class="page-meta muted" style="margin-bottom:16px;font-size:12px">`;
        if (data.meta.type) metaHtml += `<span style="margin-right:12px">${data.meta.type}</span>`;
        if (data.meta.last_updated) metaHtml += `<span style="margin-right:12px">更新: ${data.meta.last_updated}</span>`;
        if (data.meta.sources) metaHtml += `<span>来源: ${data.meta.sources}</span>`;
        metaHtml += '</div>';
      }
      this.contentEl.innerHTML = metaHtml + (data.html || '<p>空页面</p>');
    } catch (e) {
      this.contentEl.innerHTML = `<div class="empty-state"><p>加载失败: ${e.message}</p></div>`;
    }
  },

  async doSearch() {
    const q = this.searchInput.value.trim();
    if (!q) {
      this.renderTree();
      return;
    }
    try {
      const data = await API.search(q);
      let html = '';
      for (const r of data.results) {
        html += this.renderItem(r);
      }
      this.treeEl.innerHTML = html || '<div class="muted">未找到结果</div>';
      this.treeEl.querySelectorAll('.tree-item').forEach(el => {
        el.addEventListener('click', () => this.loadPage(el.dataset.path));
      });
    } catch (e) {
      this.treeEl.innerHTML = `<div class="muted">搜索失败</div>`;
    }
  },

  navigateToName(name) {
    if (!this.tree) return;
    for (const pages of Object.values(this.tree)) {
      for (const page of pages) {
        if (page.name === name || page.title === name) {
          this.loadPage(page.path);
          return;
        }
      }
    }
    this.contentEl.innerHTML = `<div class="empty-state"><p>未找到页面: ${name}</p></div>`;
  }
};

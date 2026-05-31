/* Notebook selector and request scoping */

const Notebooks = {
  notebooks: [],
  slug: localStorage.getItem('llmwiki-notebook') || 'enterprise-management',

  init() {
    this.selector = document.getElementById('notebook-selector');
    this.select = document.getElementById('notebook-select');
    if (!this.select) return Promise.resolve();

    this.select.addEventListener('change', () => {
      this.slug = this.select.value || 'enterprise-management';
      localStorage.setItem('llmwiki-notebook', this.slug);
      window.dispatchEvent(new CustomEvent('notebook:change', {
        detail: { slug: this.slug },
      }));
    });

    window.addEventListener('auth:change', () => this.load());
    return this.load();
  },

  currentSlug() {
    return this.slug || 'enterprise-management';
  },

  queryString() {
    return 'notebook=' + encodeURIComponent(this.currentSlug());
  },

  requestBody(extra) {
    return Object.assign({ notebook_slug: this.currentSlug() }, extra || {});
  },

  async load() {
    if (typeof Auth !== 'undefined' && !Auth.getToken()) {
      this.notebooks = [{
        slug: 'enterprise-management',
        title: '企业管理制度',
        is_default: true,
      }];
      this.render();
      return;
    }

    try {
      const data = await API.getNotebooks();
      this.notebooks = data.notebooks || [];
    } catch (e) {
      this.notebooks = [{
        slug: 'enterprise-management',
        title: '企业管理制度',
        is_default: true,
      }];
    }
    this.render();
  },

  render() {
    if (!this.select) return;
    if (!this.notebooks.length) {
      this.notebooks = [{ slug: 'enterprise-management', title: '企业管理制度', is_default: true }];
    }

    const previousSlug = this.slug;
    if (!this.notebooks.find(n => n.slug === this.slug)) {
      this.slug = 'enterprise-management';
      localStorage.setItem('llmwiki-notebook', this.slug);
    }

    this.select.innerHTML = this.notebooks.map(n => {
      const title = n.title || n.name || n.slug;
      return '<option value="' + this.escape(n.slug) + '">' + this.escape(title) + '</option>';
    }).join('');
    this.select.value = this.slug;

    const show = this.notebooks.length > 1 || (typeof Auth !== 'undefined' && Auth.isAdmin && Auth.isAdmin());
    if (this.selector) this.selector.style.display = show ? 'flex' : 'none';

    if (previousSlug !== this.slug) {
      window.dispatchEvent(new CustomEvent('notebook:change', {
        detail: { slug: this.slug },
      }));
    }
  },

  escape(s) {
    return String(s || '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[ch]));
  },
};

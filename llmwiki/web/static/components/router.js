/* Hash-based tab router */

const Router = {
  tabs: ['wiki', 'qa', 'upload', 'graph', 'manage'],

  init() {
    // Tab button clicks
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        window.location.hash = tab;
      });
    });

    // Hash change
    window.addEventListener('hashchange', () => this.navigate());

    // Initial route
    const hash = window.location.hash.slice(1) || 'qa';
    if (!this.tabs.includes(hash)) {
      window.location.hash = 'qa';
    } else {
      this.navigate();
    }
  },

  navigate() {
    const hash = window.location.hash.slice(1) || 'qa';

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === hash);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(el => {
      el.classList.toggle('active', el.id === `tab-${hash}`);
    });

    // Trigger tab-specific init
    const event = new CustomEvent('tab:show', { detail: { tab: hash } });
    window.dispatchEvent(event);
  }
};

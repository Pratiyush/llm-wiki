/* Knowledge graph viewer with vis.js */

const GraphViewer = {
  network: null,
  loadSeq: 0,

  init() {
    this.canvas = document.getElementById('graph-canvas');
    this.searchInput = document.getElementById('graph-search');

    window.addEventListener('tab:show', (e) => {
      if (e.detail.tab === 'graph' && !this.network) {
        this.loadGraph();
      }
    });

    this.searchInput?.addEventListener('input', () => {
      if (this.network) this.focusNode(this.searchInput.value.trim());
    });

    window.addEventListener('notebook:change', () => {
      this.network = null;
      if (this.canvas) {
        this.canvas.innerHTML = '<div class="loading">加载图谱中...</div>';
      }
      this.loadGraph();
    });
  },

  async loadGraph() {
    const slug = (typeof Notebooks !== 'undefined') ? Notebooks.currentSlug() : 'enterprise-management';
    const seq = ++this.loadSeq;
    try {
      const data = await API.getGraph();
      if (seq !== this.loadSeq || (typeof Notebooks !== 'undefined' && Notebooks.currentSlug() !== slug)) return;
      if (!data.nodes.length) {
        this.canvas.innerHTML = '<div class="empty-state"><p>暂无图谱数据</p></div>';
        return;
      }
      this.renderGraph(data, seq, slug);
    } catch (e) {
      if (seq !== this.loadSeq || (typeof Notebooks !== 'undefined' && Notebooks.currentSlug() !== slug)) return;
      this.canvas.innerHTML = `<div class="empty-state"><p>加载失败: ${e.message}</p></div>`;
    }
  },

  renderGraph(data, seq, slug) {
    if (seq !== this.loadSeq || (typeof Notebooks !== 'undefined' && Notebooks.currentSlug() !== slug)) return;
    // Load vis.js from CDN
    if (typeof vis === 'undefined') {
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js';
      script.onload = () => {
        if (seq !== this.loadSeq || (typeof Notebooks !== 'undefined' && Notebooks.currentSlug() !== slug)) return;
        this._createNetwork(data);
      };
      script.onerror = () => {
        if (seq !== this.loadSeq || (typeof Notebooks !== 'undefined' && Notebooks.currentSlug() !== slug)) return;
        this.canvas.innerHTML = '<div class="empty-state"><p>无法加载 vis.js，请检查网络</p></div>';
      };
      document.head.appendChild(script);
    } else {
      this._createNetwork(data);
    }
  },

  _createNetwork(data) {
    const nodes = new vis.DataSet(data.nodes.map(n => ({
      id: n.id,
      label: n.label,
      color: {
        background: n.color,
        border: n.color,
        highlight: { background: n.color, border: '#000' },
      },
      font: { size: 12, color: getComputedStyle(document.documentElement).getPropertyValue('--text').trim() },
      shape: 'dot',
      size: 16,
    })));

    const edges = new vis.DataSet(data.edges.map(e => ({
      from: e.from,
      to: e.to,
      arrows: 'to',
      color: { color: getComputedStyle(document.documentElement).getPropertyValue('--border').trim() },
    })));

    const options = {
      layout: { improvedLayout: false },
      physics: {
        barnesHut: { gravitationalConstant: -3000, springLength: 120 },
        stabilization: { iterations: 100 },
      },
      interaction: { hover: true, tooltipDelay: 200 },
    };

    this.network = new vis.Network(this.canvas, { nodes, edges }, options);

    // Click node to navigate to wiki page
    this.network.on('click', (params) => {
      if (params.nodes.length) {
        const nodeId = params.nodes[0];
        const node = data.nodes.find(n => n.id === nodeId);
        if (node) {
          // Find matching wiki page path
          const path = this._findPagePath(node.id, node.type);
          if (path) {
            window.location.hash = 'wiki';
            setTimeout(() => Browser.loadPage(path), 200);
          }
        }
      }
    });
  },

  _findPagePath(slug, type) {
    // Try to find the page in the browser's tree data
    if (!Browser.tree) return null;
    for (const [cat, pages] of Object.entries(Browser.tree)) {
      for (const page of pages) {
        if (page.name === slug) {
          return page.path;
        }
      }
    }
    return null;
  },

  focusNode(query) {
    if (!this.network || !query) return;
    const allNodes = this.network.body.data.nodes.get();
    const match = allNodes.find(n => n.label.toLowerCase().includes(query.toLowerCase()));
    if (match) {
      this.network.focus(match.id, { scale: 1.5, animation: true });
      this.network.selectNodes([match.id]);
    }
  }
};

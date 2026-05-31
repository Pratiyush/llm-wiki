/* API client */

const API = {
  async get(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`API error: ${r.status}`);
    return r.json();
  },

  async post(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`API error: ${r.status}`);
    return r.json();
  },

  notebookQuery() {
    const slug = (typeof Notebooks !== 'undefined' && Notebooks.currentSlug)
      ? Notebooks.currentSlug()
      : 'enterprise-management';
    return 'notebook=' + encodeURIComponent(slug);
  },

  notebookBody(body) {
    const slug = (typeof Notebooks !== 'undefined' && Notebooks.currentSlug)
      ? Notebooks.currentSlug()
      : 'enterprise-management';
    return Object.assign({ notebook_slug: slug }, body || {});
  },

  // Pages
  getTree: () => API.get('/api/pages/tree?' + API.notebookQuery()),
  getPage: (path) => API.get(`/api/pages/rendered/${encodeURIComponent(path)}?` + API.notebookQuery()),
  getRaw: (path) => API.get(`/api/pages/content/${encodeURIComponent(path)}?` + API.notebookQuery()),
  search: (q) => API.get(`/api/pages/search?q=${encodeURIComponent(q)}&` + API.notebookQuery()),

  // Query
  ask: (question, model) => API.post('/api/query/ask', API.notebookBody({ question, model })),
  askStream(question, model, onChunk, onDone) {
    return fetch('/api/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(API.notebookBody({ question, model })),
    }).then(async resp => {
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') { onDone && onDone(); return; }
            onChunk(data);
          }
        }
      }
      onDone && onDone();
    });
  },

  // Upload
  uploadFile: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return fetch('/api/upload/file?' + API.notebookQuery(), { method: 'POST', body: fd }).then(r => r.json());
  },

  // Graph
  getGraph: () => API.get('/api/graph/data?' + API.notebookQuery()),

  // Notebooks
  getNotebooks: () => {
    const token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
    return fetch('/api/notebooks', {
      headers: token ? { 'Authorization': 'Bearer ' + token } : {},
    }).then(r => {
      if (r.status === 401 && typeof Auth !== 'undefined' && Auth.logout) {
        Auth.logout();
      }
      if (!r.ok) throw new Error(`API error: ${r.status}`);
      return r.json();
    });
  },
  createNotebook: (body) => {
    const token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
    return fetch('/api/notebooks', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
      },
      body: JSON.stringify(body),
    }).then(async r => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || `API error: ${r.status}`);
      return data;
    });
  },
  updateNotebook: (slug, body) => {
    const token = (typeof Auth !== 'undefined') ? Auth.getToken() : '';
    return fetch('/api/notebooks/' + encodeURIComponent(slug), {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
      },
      body: JSON.stringify(body),
    }).then(async r => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.detail || `API error: ${r.status}`);
      return data;
    });
  },

  // Manage
  getStatus: () => API.get('/api/manage/status'),
  lint: () => API.post('/api/manage/lint', {}),
  build: () => API.post('/api/manage/build', {}),
  sync: () => API.post('/api/manage/sync', {}),
};

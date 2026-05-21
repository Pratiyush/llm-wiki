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

  // Pages
  getTree: () => API.get('/api/pages/tree'),
  getPage: (path) => API.get(`/api/pages/rendered/${encodeURIComponent(path)}`),
  getRaw: (path) => API.get(`/api/pages/content/${encodeURIComponent(path)}`),
  search: (q) => API.get(`/api/pages/search?q=${encodeURIComponent(q)}`),

  // Query
  ask: (question, model) => API.post('/api/query/ask', { question, model }),
  askStream(question, model, onChunk, onDone) {
    return fetch('/api/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, model }),
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
    return fetch('/api/upload/file', { method: 'POST', body: fd }).then(r => r.json());
  },

  // Graph
  getGraph: () => API.get('/api/graph/data'),

  // Manage
  getStatus: () => API.get('/api/manage/status'),
  lint: () => API.post('/api/manage/lint', {}),
  build: () => API.post('/api/manage/build', {}),
  sync: () => API.post('/api/manage/sync', {}),
};

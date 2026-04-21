"""Inline JavaScript for the static site viewer (v1.1 · #217).

Extracted from ``llmwiki/build.py`` in the #217 refactor. Byte-identical
to the pre-refactor constant — verified by ``llmwiki build`` hash.

Vanilla JS, no framework. Handles:
  - Theme toggle (light/dark/system) with localStorage persistence
  - Cmd+K command palette + fuzzy search against search-index.json
  - Keyboard shortcuts (/, g h/p/s, j/k, ?)
  - Copy-as-markdown + copy-code buttons
  - Reading progress bar on long pages
  - Sticky table headers on the sessions index
  - Filter bar on sessions table (project/model/date/text)
  - Mobile bottom nav
  - Hover-to-preview wikilinks
  - Deep-link anchors on headings
  - Related pages panel
"""

from __future__ import annotations

JS = r"""// llmwiki viewer — theme + copy + search palette + keyboard shortcuts + progress bar + filter bar
// Vanilla JS, no framework.

// ─── Theme toggle ─────────────────────────────────────────────────────────
(function () {
  const root = document.documentElement;
  // v0.5: Keep the highlight.js theme in sync with the page theme by
  // swapping which stylesheet is "disabled". Runs on page load and on every
  // toggle. Falls back silently if the tags are absent.
  function syncHljsTheme() {
    const light = document.getElementById("hljs-light");
    const dark = document.getElementById("hljs-dark");
    if (!light || !dark) return;
    let active = root.getAttribute("data-theme");
    if (!active) {
      active = (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
    }
    const isDark = active === "dark";
    light.disabled = isDark;
    dark.disabled = !isDark;
  }
  const saved = localStorage.getItem("llmwiki-theme");
  if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);
  syncHljsTheme();
  document.addEventListener("DOMContentLoaded", function () {
    syncHljsTheme();
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      // When no explicit theme is set, the page follows the OS preference.
      // Resolve that to a concrete value so the first toggle always flips.
      let current = root.getAttribute("data-theme");
      if (!current) {
        current = (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
      }
      const next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("llmwiki-theme", next);
      syncHljsTheme();
    });
  });
  // Also respond to the mobile bottom nav theme button (bound later in script.js).
  window.__llmwikiSyncHljsTheme = syncHljsTheme;
})();

// ─── Reading progress bar ────────────────────────────────────────────────
(function () {
  const bar = document.getElementById("progress-bar");
  if (!bar) return;
  function update() {
    const h = document.documentElement;
    const scrolled = h.scrollTop || document.body.scrollTop;
    const height = (h.scrollHeight || document.body.scrollHeight) - h.clientHeight;
    const pct = height > 0 ? (scrolled / height) * 100 : 0;
    bar.style.width = Math.min(100, Math.max(0, pct)) + "%";
  }
  window.addEventListener("scroll", update, { passive: true });
  update();
})();

// ─── Reading position persistence (session pages only, localStorage) ─────
(function () {
  const CAP_KEY = "llmwiki-scroll-log";
  const MAX_ENTRIES = 30;
  const article = document.querySelector(".content[itemscope]");
  if (!article) return;
  const key = location.pathname;
  let log = {};
  try { log = JSON.parse(localStorage.getItem(CAP_KEY) || "{}") || {}; } catch (e) { log = {}; }

  function restore() {
    // Restore only if deep into page (5%-95%) and no URL hash override
    if (location.hash || !log[key] || typeof log[key].pct !== "number") return;
    const pct = log[key].pct;
    if (pct <= 0.05 || pct >= 0.95) return;
    const h = document.documentElement;
    const height = h.scrollHeight - h.clientHeight;
    window.scrollTo(0, Math.max(0, height * pct));
  }
  // Restore after `load` so images/fonts are in and scrollHeight is accurate.
  // If the document is already loaded (e.g. script injected late), run now.
  if (document.readyState === "complete") restore();
  else window.addEventListener("load", restore);

  let timer = null;
  function save() {
    const h = document.documentElement;
    const height = h.scrollHeight - h.clientHeight;
    const pct = height > 0 ? h.scrollTop / height : 0;
    log[key] = { pct: Math.round(pct * 10000) / 10000, t: Date.now() };
    const entries = Object.entries(log);
    if (entries.length > MAX_ENTRIES) {
      entries.sort(function (a, b) { return (b[1].t || 0) - (a[1].t || 0); });
      log = {};
      entries.slice(0, MAX_ENTRIES).forEach(function (e) { log[e[0]] = e[1]; });
    }
    try { localStorage.setItem(CAP_KEY, JSON.stringify(log)); } catch (e) { /* quota exceeded */ }
  }
  window.addEventListener("scroll", function () {
    if (timer) return;
    timer = setTimeout(function () { timer = null; save(); }, 400);
  }, { passive: true });
})();

// ─── TOC sidebar + scroll-spy (session pages only, desktop only) ─────────
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const article = document.querySelector(".content[itemscope]");
    if (!article) return;
    const headings = article.querySelectorAll("h2[id], h3[id], h4[id]");
    if (headings.length < 3) return;
    const aside = document.createElement("aside");
    aside.className = "toc-sidebar";
    aside.setAttribute("aria-label", "Page contents");
    const title = document.createElement("div");
    title.className = "toc-title";
    title.textContent = "On this page";
    aside.appendChild(title);
    const ul = document.createElement("ul");
    const linkMap = new Map();
    headings.forEach(function (h) {
      const li = document.createElement("li");
      li.className = "toc-" + h.tagName.toLowerCase();
      const a = document.createElement("a");
      a.href = "#" + h.id;
      a.className = "toc-link";
      // The `toc` markdown extension appends a permalink anchor; strip its text.
      const clean = (h.textContent || "").replace(/\u00b6\s*$/, "").trim();
      a.textContent = clean;
      a.title = clean;
      li.appendChild(a);
      ul.appendChild(li);
      linkMap.set(h.id, a);
    });
    aside.appendChild(ul);
    document.body.appendChild(aside);
    // Scroll-spy via IntersectionObserver
    if (!("IntersectionObserver" in window)) return;
    const visible = new Set();
    function clearActive() { linkMap.forEach(function (a) { a.classList.remove("active"); }); }
    function setActive(id) {
      const link = linkMap.get(id);
      if (link) link.classList.add("active");
    }
    function applySpy() {
      clearActive();
      // Near-bottom fallback: the rootMargin creates a dead zone at the bottom
      // of the page, so the last heading would otherwise never activate.
      const doc = document.documentElement;
      const atBottom = (window.innerHeight + window.scrollY) >= (doc.scrollHeight - 24);
      if (atBottom) {
        setActive(headings[headings.length - 1].id);
        return;
      }
      if (visible.size > 0) {
        for (const h of headings) {
          if (visible.has(h.id)) { setActive(h.id); return; }
        }
      }
    }
    const obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) visible.add(e.target.id);
        else visible.delete(e.target.id);
      });
      applySpy();
    }, { rootMargin: "-80px 0px -70% 0px", threshold: 0 });
    headings.forEach(function (h) { obs.observe(h); });
    // Scroll listener handles the bottom-of-page edge case.
    window.addEventListener("scroll", applySpy, { passive: true });
  });
})();

// ─── Mobile bottom nav active-state + button wiring ──────────────────────
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // Mark the active link based on current path
    const path = location.pathname;
    document.querySelectorAll(".mobile-bottom-nav .mbn-link[data-page]").forEach(function (a) {
      const page = a.getAttribute("data-page");
      if (page === "home" && (path.endsWith("/") || path.endsWith("/index.html"))) a.classList.add("active");
      else if (page === "projects" && path.indexOf("/projects/") !== -1) a.classList.add("active");
      else if (page === "sessions" && path.indexOf("/sessions/") !== -1) a.classList.add("active");
    });
    // Wire the search button — delegate to the header palette trigger so that
    // the existing openPalette() runs (clears input, loads index, renders).
    const searchBtn = document.getElementById("mbn-search");
    if (searchBtn) {
      searchBtn.addEventListener("click", function () {
        const trigger = document.getElementById("open-palette");
        if (trigger) trigger.click();
      });
    }
    // Wire the theme button to toggle
    const themeBtn = document.getElementById("mbn-theme");
    if (themeBtn) {
      themeBtn.addEventListener("click", function () {
        const root = document.documentElement;
        let current = root.getAttribute("data-theme");
        if (!current) {
          current = (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
        }
        const next = current === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        localStorage.setItem("llmwiki-theme", next);
        if (window.__llmwikiSyncHljsTheme) window.__llmwikiSyncHljsTheme();
      });
    }
  });
})();

// ─── Copy-as-markdown (inline handler) ───────────────────────────────────
function copyMarkdown(btn) {
  const ta = btn.parentElement.querySelector(".md-source");
  if (!ta) return;
  const text = ta.value.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  const finish = function (ok) {
    btn.textContent = ok ? "Copied!" : "Failed";
    btn.classList.add("copied");
    setTimeout(function () { btn.textContent = "Copy as markdown"; btn.classList.remove("copied"); }, 1800);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
  } else {
    const tmp = document.createElement("textarea");
    tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
    document.body.appendChild(tmp); tmp.select();
    try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
    document.body.removeChild(tmp);
  }
}

// ─── Copy-code buttons on every <pre> ────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".content pre").forEach(function (pre) {
    if (pre.parentElement && pre.parentElement.classList.contains("code-wrap")) return;
    const wrap = document.createElement("div"); wrap.className = "code-wrap";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    const btn = document.createElement("button");
    btn.className = "copy-code-btn"; btn.type = "button"; btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      const code = pre.querySelector("code");
      const text = code ? code.innerText : pre.innerText;
      const finish = function (ok) {
        btn.textContent = ok ? "Copied!" : "Failed"; btn.classList.add("copied");
        setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
      } else {
        const tmp = document.createElement("textarea");
        tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
        document.body.appendChild(tmp); tmp.select();
        try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
        document.body.removeChild(tmp);
      }
    });
    wrap.appendChild(btn);
  });
});

// ─── Auto-collapse long tool results into <details> ──────────────────────
document.addEventListener("DOMContentLoaded", function () {
  // Wrap long <pre> outputs and long paragraph lists under "Tool results:"
  const markers = document.querySelectorAll(".content p strong");
  markers.forEach(function (s) {
    const text = (s.textContent || "").trim();
    if (text !== "Tool results:") return;
    const p = s.closest("p");
    if (!p) return;
    // Check if the next sibling has very long text
    let next = p.nextElementSibling;
    if (!next) return;
    const combinedText = (next.innerText || "").trim();
    if (combinedText.length < 500) return;
    // Wrap next element in a <details>
    const det = document.createElement("details");
    det.className = "collapsible-result";
    const sum = document.createElement("summary");
    sum.textContent = "Tool results (" + combinedText.length + " chars) — click to expand";
    det.appendChild(sum);
    next.parentNode.insertBefore(det, next);
    det.appendChild(next);
  });
});

// ─── Command palette (Cmd+K) + search index loader ─────────────────────
(function () {
  let idx = null;
  let idxPromise = null;
  let metaEntries = null;  // project + page entries (loaded first, fast)
  let activeIdx = 0;
  let currentResults = [];

  // Lazy-chunked loader (#47): loads the small meta index first (projects +
  // static pages), then fetches per-project session chunks in parallel on
  // first demand. Backwards-compatible with the old flat-array format.
  function loadIndex() {
    if (idx) return Promise.resolve(idx);
    if (idxPromise) return idxPromise;
    const url = window.LLMWIKI_INDEX_URL || "search-index.json";
    const base = url.substring(0, url.lastIndexOf("/") + 1);
    idxPromise = fetch(url)
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (data) {
        // Old format: flat array → return as-is
        if (Array.isArray(data)) { idx = data; return idx; }
        // New format: {entries: [...], _chunks: ["search-chunks/foo.json", ...]}
        metaEntries = data.entries || [];
        var chunkUrls = data._chunks || [];
        if (!chunkUrls.length) { idx = metaEntries; return idx; }
        return Promise.all(chunkUrls.map(function (cu) {
          return fetch(base + cu)
            .then(function (r) { return r.ok ? r.json() : []; })
            .catch(function () { return []; });
        })).then(function (chunks) {
          idx = metaEntries.slice();
          chunks.forEach(function (c) {
            if (Array.isArray(c)) { for (var i = 0; i < c.length; i++) idx.push(c[i]); }
          });
          return idx;
        });
      })
      .catch(function () { idx = []; return idx; });
    return idxPromise;
  }
  // Expose the shared loader so wikilink-preview + related-pages can reuse it
  window.__llmwikiLoadIndex = loadIndex;

  // Return the meta entries (projects + pages) synchronously if available,
  // otherwise trigger a full load. Used for instant palette rendering before
  // session chunks arrive.
  function getMetaSync() { return metaEntries || idx || []; }

  function score(entry, query) {
    if (!query) return 0;
    const q = query.toLowerCase();
    const title = (entry.title || "").toLowerCase();
    const project = (entry.project || "").toLowerCase();
    const body = (entry.body || "").toLowerCase();
    let s = 0;
    if (title === q) s += 100;
    else if (title.indexOf(q) === 0) s += 60;
    else if (title.indexOf(q) !== -1) s += 40;
    if (project.indexOf(q) !== -1) s += 20;
    if (body.indexOf(q) !== -1) s += 10;
    // Token match
    const tokens = q.split(/\s+/).filter(Boolean);
    let allMatch = true;
    tokens.forEach(function (t) {
      if (title.indexOf(t) === -1 && project.indexOf(t) === -1 && body.indexOf(t) === -1) allMatch = false;
    });
    if (allMatch && tokens.length > 1) s += 30;
    return s;
  }

  // v0.8 (#97): Dataview-style structured queries. Users can type
  // key:value pairs alongside free text to filter by metadata:
  //   type:session project:llm-wiki model:claude date:>2026-03-01 sort:date rust
  // Supported keys: type, project, model, date (range with > / <), tags, sort
  // Anything that doesn't match key:value is treated as free-text fuzzy search.
  function parseStructuredQuery(raw) {
    var filters = {};
    var freeText = [];
    var tokens = raw.split(/\s+/).filter(Boolean);
    tokens.forEach(function (t) {
      var m = t.match(/^(type|project|model|date|tags|sort):(.+)$/i);
      if (m) { filters[m[1].toLowerCase()] = m[2]; }
      else { freeText.push(t); }
    });
    return { filters: filters, freeText: freeText.join(" ") };
  }

  function matchesFilters(entry, filters) {
    if (filters.type && (entry.type || "").toLowerCase() !== filters.type.toLowerCase()) return false;
    if (filters.project && (entry.project || "").toLowerCase().indexOf(filters.project.toLowerCase()) === -1) return false;
    if (filters.model && (entry.model || "").toLowerCase().indexOf(filters.model.toLowerCase()) === -1) return false;
    if (filters.tags) {
      var want = filters.tags.toLowerCase();
      var entryBody = ((entry.body || "") + " " + (entry.title || "")).toLowerCase();
      if (entryBody.indexOf(want) === -1) return false;
    }
    if (filters.date) {
      var d = entry.date || "";
      var op = filters.date.charAt(0);
      if (op === ">" && d <= filters.date.substring(1)) return false;
      if (op === "<" && d >= filters.date.substring(1)) return false;
      if (op !== ">" && op !== "<" && d.indexOf(filters.date) === -1) return false;
    }
    return true;
  }

  function search(query) {
    if (!idx) return [];
    if (!query) return idx.slice(0, 10);
    var parsed = parseStructuredQuery(query);
    var filtered = idx;
    if (Object.keys(parsed.filters).length > 0) {
      filtered = idx.filter(function (e) { return matchesFilters(e, parsed.filters); });
    }
    var sortKey = parsed.filters.sort;
    if (sortKey === "date") {
      return filtered
        .slice()
        .sort(function (a, b) { return (b.date || "").localeCompare(a.date || ""); })
        .slice(0, 20);
    }
    if (!parsed.freeText) return filtered.slice(0, 20);
    return filtered
      .map(function (e) { return { entry: e, score: score(e, parsed.freeText) }; })
      .filter(function (r) { return r.score > 0; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 15)
      .map(function (r) { return r.entry; });
  }

  function renderResults(results) {
    const ul = document.getElementById("palette-results");
    if (!ul) return;
    currentResults = results;
    activeIdx = 0;
    ul.innerHTML = results.map(function (r, i) {
      const meta = [r.project, r.date, r.model].filter(Boolean).join(" · ");
      return '<li data-i="' + i + '" class="' + (i === 0 ? 'active' : '') + '">' +
        '<span class="result-type">' + (r.type || 'page') + '</span>' +
        '<span class="result-title">' + escapeHtml(r.title) + '</span>' +
        (meta ? '<div class="result-meta">' + escapeHtml(meta) + '</div>' : '') +
        '</li>';
    }).join("");
    ul.querySelectorAll("li").forEach(function (li) {
      li.addEventListener("click", function () {
        const i = parseInt(li.getAttribute("data-i"));
        openResult(i);
      });
    });
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function openResult(i) {
    if (!currentResults[i]) return;
    const r = currentResults[i];
    // #277: slash commands don't have URLs — copy the command text
    // to the clipboard + flash a hint instead of navigating.
    if (r.type === "slash" || !r.url) {
      try { navigator.clipboard && navigator.clipboard.writeText(r.title); } catch (e) {}
      const input = document.getElementById("palette-input");
      if (input) { input.value = r.title; input.placeholder = "copied — paste inside Claude Code"; }
      return;
    }
    const pageUrl = window.LLMWIKI_INDEX_URL || "";
    // Compute base dir from current page URL
    const pathPrefix = pageUrl.substring(0, pageUrl.lastIndexOf("/") + 1) || "";
    window.location.href = pathPrefix + r.url;
  }

  function openPalette() {
    const p = document.getElementById("palette");
    if (!p) return;
    p.setAttribute("aria-hidden", "false");
    const input = document.getElementById("palette-input");
    if (input) { input.value = ""; input.focus(); }
    // Show meta entries immediately while chunks load
    var meta = getMetaSync();
    if (meta.length && !idx) renderResults(meta.slice(0, 10));
    loadIndex().then(function () { renderResults(search(input ? input.value : "")); });
  }

  function closePalette() {
    const p = document.getElementById("palette");
    if (!p) return;
    p.setAttribute("aria-hidden", "true");
  }

  function openHelp() {
    const d = document.getElementById("help-dialog");
    if (d) d.setAttribute("aria-hidden", "false");
  }
  function closeHelp() {
    const d = document.getElementById("help-dialog");
    if (d) d.setAttribute("aria-hidden", "true");
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Wire up buttons
    const openBtn = document.getElementById("open-palette");
    if (openBtn) openBtn.addEventListener("click", openPalette);

    const backdrop = document.getElementById("palette-backdrop");
    if (backdrop) backdrop.addEventListener("click", closePalette);

    const input = document.getElementById("palette-input");
    if (input) {
      input.addEventListener("input", function () { renderResults(search(input.value)); });
      input.addEventListener("keydown", function (e) {
        const items = document.querySelectorAll("#palette-results li");
        if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(items.length - 1, activeIdx + 1); updateActive(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(0, activeIdx - 1); updateActive(); }
        else if (e.key === "Enter") { e.preventDefault(); openResult(activeIdx); }
      });
    }

    const helpBackdrop = document.getElementById("help-backdrop");
    if (helpBackdrop) helpBackdrop.addEventListener("click", closeHelp);
    const helpClose = document.getElementById("help-close");
    if (helpClose) helpClose.addEventListener("click", closeHelp);
  });

  function updateActive() {
    const items = document.querySelectorAll("#palette-results li");
    items.forEach(function (li, i) { li.classList.toggle("active", i === activeIdx); });
    const active = items[activeIdx];
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  // ─── Keyboard shortcuts ─────────────────────────────────────────────────
  let gPressed = false;
  let gPressedTimer = null;
  document.addEventListener("keydown", function (e) {
    const inInput = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT");

    // Cmd/Ctrl+K opens palette everywhere
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      openPalette();
      return;
    }
    // Esc closes palette / help / clears focus
    if (e.key === "Escape") {
      const p = document.getElementById("palette");
      const h = document.getElementById("help-dialog");
      if (p && p.getAttribute("aria-hidden") === "false") { closePalette(); return; }
      if (h && h.getAttribute("aria-hidden") === "false") { closeHelp(); return; }
      if (inInput) { e.target.blur(); return; }
    }

    // Shortcuts only work when not typing in an input
    if (inInput) return;

    if (e.key === "/") { e.preventDefault(); openPalette(); return; }
    if (e.key === "?") { e.preventDefault(); openHelp(); return; }

    // g-prefix shortcuts
    if (e.key === "g" && !gPressed) {
      gPressed = true;
      gPressedTimer = setTimeout(function () { gPressed = false; }, 1000);
      return;
    }
    if (gPressed) {
      gPressed = false;
      if (gPressedTimer) clearTimeout(gPressedTimer);
      const rel = window.LLMWIKI_INDEX_URL || "";
      const base = rel.substring(0, rel.lastIndexOf("/") + 1);
      if (e.key === "h") { window.location.href = base + "index.html"; return; }
      if (e.key === "p") { window.location.href = base + "projects/index.html"; return; }
      if (e.key === "s") { window.location.href = base + "sessions/index.html"; return; }
    }

    // j/k on sessions table
    const tbody = document.getElementById("sessions-tbody");
    if (tbody && (e.key === "j" || e.key === "k")) {
      e.preventDefault();
      const visibleRows = Array.from(tbody.querySelectorAll("tr")).filter(function (r) { return !r.hidden; });
      if (!visibleRows.length) return;
      let cur = visibleRows.findIndex(function (r) { return r.classList.contains("selected"); });
      if (cur === -1) cur = 0;
      else cur = e.key === "j" ? Math.min(visibleRows.length - 1, cur + 1) : Math.max(0, cur - 1);
      visibleRows.forEach(function (r) { r.classList.remove("selected"); });
      visibleRows[cur].classList.add("selected");
      visibleRows[cur].scrollIntoView({ block: "nearest" });
      // Enter on selected row navigates
    }
    if (e.key === "Enter" && tbody) {
      const sel = tbody.querySelector("tr.selected a");
      if (sel) { window.location.href = sel.href; }
    }
  });
})();

// ─── Sessions table filter bar ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  const tbody = document.getElementById("sessions-tbody");
  if (!tbody) return;
  const fProject = document.getElementById("filter-project");
  const fModel = document.getElementById("filter-model");
  const fFrom = document.getElementById("filter-date-from");
  const fTo = document.getElementById("filter-date-to");
  const fText = document.getElementById("filter-text");
  const fClear = document.getElementById("filter-clear");
  const fCount = document.getElementById("filter-count");

  function apply() {
    const p = fProject ? fProject.value : "";
    const m = fModel ? fModel.value : "";
    const from = fFrom ? fFrom.value : "";
    const to = fTo ? fTo.value : "";
    const txt = fText ? fText.value.toLowerCase() : "";
    let shown = 0;
    Array.from(tbody.querySelectorAll("tr")).forEach(function (r) {
      const rp = r.getAttribute("data-project") || "";
      const rm = r.getAttribute("data-model") || "";
      const rd = r.getAttribute("data-date") || "";
      const rs = (r.getAttribute("data-slug") || "").toLowerCase();
      let show = true;
      if (p && rp !== p) show = false;
      if (m && rm !== m) show = false;
      if (from && rd < from) show = false;
      if (to && rd > to) show = false;
      if (txt && rs.indexOf(txt) === -1) show = false;
      r.hidden = !show;
      if (show) shown++;
    });
    if (fCount) fCount.textContent = shown + " shown";
  }

  [fProject, fModel, fFrom, fTo, fText].forEach(function (el) {
    if (el) el.addEventListener("input", apply);
  });
  if (fClear) fClear.addEventListener("click", function () {
    if (fProject) fProject.value = "";
    if (fModel) fModel.value = "";
    if (fFrom) fFrom.value = "";
    if (fTo) fTo.value = "";
    if (fText) fText.value = "";
    apply();
  });
  apply();
});

// ─── Hover-to-preview wikilinks ───────────────────────────────────────────
// When the user hovers over a wikilink (an <a> whose text starts with "[["
// or whose href is a wiki page), fetch the target's first ~300 chars and
// show a floating preview card. Uses the client-side search index.
(function () {
  let idx = null;
  let previewEl = null;
  let hideTimer = null;

  function getPreviewEl() {
    if (previewEl) return previewEl;
    previewEl = document.createElement("div");
    previewEl.className = "wikilink-preview";
    previewEl.setAttribute("hidden", "");
    previewEl.innerHTML = '<div class="wl-title"></div><div class="wl-body"></div>';
    document.body.appendChild(previewEl);
    previewEl.addEventListener("mouseenter", function () {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    });
    previewEl.addEventListener("mouseleave", function () {
      hidePreview();
    });
    return previewEl;
  }

  function loadIndex() {
    if (idx) return Promise.resolve(idx);
    // Reuse the shared chunked loader from the palette IIFE (#47)
    if (window.__llmwikiLoadIndex) {
      return window.__llmwikiLoadIndex().then(function (data) { idx = data; return idx; });
    }
    var url = window.LLMWIKI_INDEX_URL || "search-index.json";
    return fetch(url)
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (data) {
        idx = Array.isArray(data) ? data : (data.entries || []);
        return idx;
      })
      .catch(function () { idx = []; return idx; });
  }

  function findEntry(keyOrText) {
    if (!idx) return null;
    const needle = (keyOrText || "").toLowerCase().trim();
    if (!needle) return null;
    // Try exact title match first
    for (const e of idx) {
      if ((e.title || "").toLowerCase() === needle) return e;
    }
    // Fall back to prefix
    for (const e of idx) {
      if ((e.title || "").toLowerCase().startsWith(needle)) return e;
    }
    // Fall back to substring
    for (const e of idx) {
      if ((e.title || "").toLowerCase().indexOf(needle) !== -1) return e;
    }
    return null;
  }

  function showPreview(target, entry) {
    const el = getPreviewEl();
    el.querySelector(".wl-title").textContent = entry.title || entry.id || "";
    el.querySelector(".wl-body").textContent = (entry.body || "").slice(0, 300);
    // Position below the target
    const rect = target.getBoundingClientRect();
    el.style.position = "fixed";
    el.style.top = (rect.bottom + 8) + "px";
    el.style.left = Math.min(window.innerWidth - 380, Math.max(16, rect.left)) + "px";
    el.removeAttribute("hidden");
  }

  function hidePreview() {
    if (previewEl) previewEl.setAttribute("hidden", "");
  }

  function attach(a) {
    const text = (a.textContent || "").trim();
    // Only target links that look like wikilinks (starting with [[) or that
    // point to another page in site/sessions, site/projects, or site/.
    const isWiki = text.startsWith("[[") || /sessions\/|projects\//.test(a.getAttribute("href") || "");
    if (!isWiki) return;
    let key = text.replace(/^\[\[|\]\]$/g, "").trim();
    if (!key) {
      // Derive from href
      const href = a.getAttribute("href") || "";
      const m = href.match(/([^/]+)\.html$/);
      if (m) key = m[1];
    }
    if (!key) return;

    a.addEventListener("mouseenter", function () {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
      loadIndex().then(function () {
        const entry = findEntry(key);
        if (entry) showPreview(a, entry);
      });
    });
    a.addEventListener("mouseleave", function () {
      hideTimer = setTimeout(hidePreview, 200);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".content a").forEach(attach);
  });
})();

// ─── Timeline view on sessions index ──────────────────────────────────────
// Render a compact sparkline above the sessions table showing session count
// per day over the last 60 days.
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const tbody = document.getElementById("sessions-tbody");
    if (!tbody) return;
    // Only run on the sessions index page
    const container = document.querySelector(".section .container");
    if (!container || !container.querySelector(".filter-bar")) return;

    // Collect dates
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const counts = new Map();
    rows.forEach(function (r) {
      const d = r.getAttribute("data-date");
      if (!d) return;
      counts.set(d, (counts.get(d) || 0) + 1);
    });
    if (!counts.size) return;

    // Sort dates ascending
    const dates = Array.from(counts.keys()).sort();
    const maxCount = Math.max(...counts.values());

    // Build an SVG sparkline
    const w = 800;
    const h = 60;
    const padX = 4;
    const bars = dates.map(function (d, i) {
      const count = counts.get(d);
      const barW = Math.max(2, (w - 2 * padX) / dates.length - 2);
      const x = padX + i * ((w - 2 * padX) / dates.length);
      const barH = (count / maxCount) * (h - 16);
      const y = h - barH - 4;
      return '<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + barH +
             '" fill="var(--accent)" opacity="0.7" data-date="' + d + '" data-count="' + count + '"></rect>';
    }).join("");

    const svg =
      '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" ' +
      'style="width:100%;height:' + h + 'px;display:block" aria-label="Session activity timeline">' +
      bars + '</svg>';

    // Create the timeline block
    const tl = document.createElement("div");
    tl.className = "timeline-block";
    tl.innerHTML =
      '<div class="timeline-label muted">Activity timeline · ' + dates.length +
      ' days · peak ' + maxCount + ' sessions</div>' + svg;

    // Insert above the filter bar
    const filter = container.querySelector(".filter-bar");
    if (filter) container.insertBefore(tl, filter);
  });
})();

// ─── v0.4: Related pages panel ────────────────────────────────────────────
// On a session page, find 3-5 other sessions that share wikilink targets
// or project, and display them at the bottom under a "Related pages" heading.
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const article = document.querySelector("article.content");
    if (!article) return;
    // Only on session pages (have a breadcrumb + back-to-project link)
    const backBtn = document.querySelector(".session-actions a.btn");
    if (!backBtn) return;

    // Extract current page metadata from the llmwiki:metadata comment
    const html = document.documentElement.outerHTML;
    const m = html.match(/llmwiki:metadata\n([\s\S]*?)-->/);
    if (!m) return;
    const meta = {};
    m[1].split("\n").forEach(function (line) {
      const idx = line.indexOf(":");
      if (idx > 0) {
        const k = line.slice(0, idx).trim();
        const v = line.slice(idx + 1).trim();
        if (k && v) meta[k] = v;
      }
    });
    const currentProject = meta.project || "";
    const currentSlug = meta.slug || "";
    if (!currentProject) return;

    // Reuse the shared chunked loader (#47) — includes session entries
    var loader = window.__llmwikiLoadIndex
      ? window.__llmwikiLoadIndex()
      : fetch(window.LLMWIKI_INDEX_URL || "search-index.json")
          .then(function (r) { return r.ok ? r.json() : []; })
          .then(function (d) { return Array.isArray(d) ? d : (d.entries || []); });
    loader
      .then(function (entries) {
        if (!entries || !entries.length) return;
        // Score each other session: same project = 2 pts, shared wikilink targets = +1 per token
        const scored = entries
          .filter(function (e) {
            return e.type === "session" && e.url && !e.url.endsWith(currentSlug + ".html");
          })
          .map(function (e) {
            let score = 0;
            if (e.project === currentProject) score += 2;
            return { entry: e, score: score };
          })
          .filter(function (s) { return s.score > 0; })
          .sort(function (a, b) { return b.score - a.score; })
          .slice(0, 5);
        if (!scored.length) return;

        const section = document.createElement("div");
        section.className = "related-pages";
        section.innerHTML =
          "<h3>Related pages</h3>" +
          '<ul>' +
          scored.map(function (s) {
            const href = "../../" + s.entry.url;
            const title = s.entry.title;
            const date = s.entry.date || "";
            return '<li><a href="' + href + '">' + title + '</a>' +
              (date ? ' <span class="muted">· ' + date + '</span>' : '') +
              '</li>';
          }).join("") +
          '</ul>';
        article.appendChild(section);
      })
      .catch(function () {});
  });
})();

// v0.8 (#64, #72): the v0.4 JS-based tiny-strip heatmap is gone. The 365-day
// GitLab/GitHub-style grid is now rendered at build time as pure SVG by
// llmwiki/viz_heatmap.py and inlined into index.html + each project page.
// The page CSS (--heatmap-0..4) picks up the current theme automatically —
// no JS wiring needed.

// ─── v0.4: Search result highlights ──────────────────────────────────────
// When showing search palette results, highlight the matched query in the
// title and body snippet.
(function () {
  function highlight(text, query) {
    if (!query || !text) return escapeLocalHtml(text);
    const q = query.toLowerCase();
    const lower = text.toLowerCase();
    const i = lower.indexOf(q);
    if (i === -1) return escapeLocalHtml(text);
    return escapeLocalHtml(text.slice(0, i)) +
      '<mark>' + escapeLocalHtml(text.slice(i, i + q.length)) + '</mark>' +
      escapeLocalHtml(text.slice(i + q.length));
  }
  function escapeLocalHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // Expose so the palette renderer can call it if it chooses
  window.llmwikiHighlight = highlight;
})();

// ─── v0.4: Deep-link icon next to headings ────────────────────────────────
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".content h2[id], .content h3[id], .content h4[id]").forEach(function (h) {
      if (h.querySelector(".deep-link")) return;
      const icon = document.createElement("a");
      icon.className = "deep-link";
      icon.href = "#" + h.id;
      icon.innerHTML = "🔗";
      icon.title = "Copy link to this section";
      icon.addEventListener("click", function (ev) {
        ev.preventDefault();
        const url = window.location.origin + window.location.pathname + "#" + h.id;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(function () {
            icon.textContent = "✓";
            setTimeout(function () { icon.textContent = "🔗"; }, 1200);
          });
        }
      });
      h.appendChild(icon);
    });
  });
})();
"""

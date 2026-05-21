/* llmwiki web UI — main application */

(function() {
  'use strict';

  // Theme toggle
  const themeToggle = document.getElementById('theme-toggle');
  const html = document.documentElement;
  const lightCSS = document.getElementById('hljs-light');
  const darkCSS = document.getElementById('hljs-dark');

  function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem('llmwiki-theme', theme);
    themeToggle.querySelector('.theme-icon').textContent = theme === 'dark' ? '\u263E' : '\u263C';
    if (lightCSS && darkCSS) {
      lightCSS.disabled = theme === 'dark';
      darkCSS.disabled = theme !== 'dark';
    }
  }

  // Init theme
  const saved = localStorage.getItem('llmwiki-theme');
  if (saved) {
    setTheme(saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    setTheme('dark');
  }

  themeToggle.addEventListener('click', () => {
    const current = html.getAttribute('data-theme') || 'light';
    setTheme(current === 'dark' ? 'light' : 'dark');
  });

  // Init router
  Router.init();

  // Init components
  Auth.init();
  Browser.init();
  QA.init();
  Uploader.init();
  GraphViewer.init();
  Manager.init();
})();

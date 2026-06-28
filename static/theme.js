(function () {
  const STORAGE_KEY = 'alfuttaim_theme';

  function getPreferredTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    const resolved = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', resolved);
    localStorage.setItem(STORAGE_KEY, resolved);

    document.querySelectorAll('.theme-toggle').forEach(btn => {
      const isDark = resolved === 'dark';
      btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
      btn.title = isDark ? 'Switch to light mode' : 'Switch to dark mode';
      const label = btn.querySelector('.theme-toggle-label');
      if (label) label.textContent = isDark ? 'Light' : 'Dark';
      const icon = btn.querySelector('.theme-toggle-icon');
      if (icon) {
        icon.innerHTML = isDark
          ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a1 1 0 0 1 1 1v1.07A7 7 0 0 1 19.93 11H21a1 1 0 1 1 0 2h-1.07A7 7 0 0 1 13 18.93V21a1 1 0 1 1-2 0v-1.07A7 7 0 0 1 5.07 13H4a1 1 0 1 1 0-2h1.07A7 7 0 0 1 11 5.07V4a1 1 0 0 1 1-1zm0 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10z"/></svg>'
          : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 14.5A7.5 7.5 0 0 1 9.5 3a6.5 6.5 0 1 0 11.5 11.5z"/></svg>';
      }
    });
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }

  function bindToggles() {
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      if (btn.dataset.themeBound) return;
      btn.dataset.themeBound = '1';
      btn.addEventListener('click', toggleTheme);
    });
  }

  window.initTheme = function () {
    applyTheme(getPreferredTheme());
    bindToggles();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initTheme);
  } else {
    window.initTheme();
  }
})();

(function () {
  'use strict';
  var menus = Array.from(document.querySelectorAll('.account-menu'));
  var toggles = Array.from(document.querySelectorAll('[data-theme-toggle]'));
  function syncTheme(theme) {
    document.documentElement.dataset.theme = theme;
    toggles.forEach(function (toggle) { toggle.checked = theme === 'dark'; });
  }
  syncTheme(document.documentElement.dataset.theme || 'light');
  toggles.forEach(function (toggle) {
    toggle.addEventListener('change', function () {
      var theme = toggle.checked ? 'dark' : 'light';
      syncTheme(theme);
      try { localStorage.setItem(document.body.dataset.themeKey, theme); } catch (error) { /* Private browsing may disallow storage. */ }
    });
  });
  window.addEventListener('storage', function (event) {
    if (event.key === document.body.dataset.themeKey && (event.newValue === 'dark' || event.newValue === 'light')) {
      syncTheme(event.newValue);
    }
  });
  menus.forEach(function (menu) {
    menu.addEventListener('toggle', function () {
      if (menu.open) menus.forEach(function (other) { if (other !== menu) other.open = false; });
    });
  });
  document.addEventListener('click', function (event) {
    menus.forEach(function (menu) { if (!menu.contains(event.target)) menu.open = false; });
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') menus.forEach(function (menu) {
      if (menu.open) { menu.open = false; menu.querySelector('summary').focus(); }
    });
  });
}());

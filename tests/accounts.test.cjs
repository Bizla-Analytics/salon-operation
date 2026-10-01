const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../static/js/accounts.js'), 'utf8');
const initialThemeScript = fs.readFileSync(path.join(__dirname, '../templates/base.html'), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

test('default theme is light regardless of system preference; explicit dark preference is retained', () => {
  for (const saved of [null, 'light', 'invalid', 'dark']) {
    const document = { documentElement: { dataset: {} } };
    vm.runInNewContext(initialThemeScript, {
      document, localStorage: { getItem: () => saved },
      window: { matchMedia: () => { throw new Error('System theme must not determine default'); } },
    });
    assert.equal(document.documentElement.dataset.theme, saved === 'dark' ? 'dark' : 'light');
  }
});

function fixture(theme = 'light', storageThrows = false) {
  function element() {
    return { handlers: {}, checked: false, open: false,
      addEventListener(type, handler) { this.handlers[type] = handler; },
      contains(target) { return target === this; },
      querySelector() { return { focus: () => { this.focused = true; } }; },
    };
  }
  const menus = [element(), element()];
  const toggles = [element(), element()];
  const document = { documentElement: { dataset: { theme } }, body: { dataset: { themeKey: 'hairship-theme-7' } },
    handlers: {}, querySelectorAll(selector) { return selector === '.account-menu' ? menus : toggles; },
    addEventListener(type, handler) { this.handlers[type] = handler; },
  };
  const stored = {};
  const window = { handlers: {}, addEventListener(type, handler) { this.handlers[type] = handler; } };
  vm.runInNewContext(script, { document, window, localStorage: {
    setItem(key, value) { if (storageThrows) throw new Error('Denied'); stored[key] = value; },
  } });
  return { document, window, menus, toggles, stored };
}

test('initial theme synchronizes desktop and mobile switches', () => {
  const f = fixture('dark');
  assert.ok(f.toggles.every(t => t.checked));
});
test('switch changes theme, saves per-account preference and synchronizes menus', () => {
  const f = fixture();
  f.toggles[1].checked = true;
  f.toggles[1].handlers.change();
  assert.equal(f.document.documentElement.dataset.theme, 'dark');
  assert.equal(f.stored['hairship-theme-7'], 'dark');
  assert.ok(f.toggles.every(t => t.checked));
  f.toggles[0].checked = false;
  f.toggles[0].handlers.change();
  assert.equal(f.document.documentElement.dataset.theme, 'light');
  assert.equal(f.stored['hairship-theme-7'], 'light');
  assert.ok(f.toggles.every(t => !t.checked));
});
test('theme switching still works when browser storage is unavailable', () => {
  const f = fixture('light', true);
  f.toggles[0].checked = true;
  assert.doesNotThrow(() => f.toggles[0].handlers.change());
  assert.equal(f.document.documentElement.dataset.theme, 'dark');
});
test('storage events synchronize only the current account across tabs', () => {
  const f = fixture();
  f.window.handlers.storage({ key: 'hairship-theme-8', newValue: 'dark' });
  assert.equal(f.document.documentElement.dataset.theme, 'light');
  f.window.handlers.storage({ key: 'hairship-theme-7', newValue: 'dark' });
  assert.equal(f.document.documentElement.dataset.theme, 'dark');
});
test('opening one menu closes the other, outside click and Escape dismiss', () => {
  const f = fixture();
  f.menus.forEach(m => { m.open = true; });
  f.menus[1].handlers.toggle();
  assert.equal(f.menus[0].open, false);
  f.document.handlers.click({ target: f.menus[1] });
  assert.equal(f.menus[1].open, true);
  f.document.handlers.keydown({ key: 'Escape' });
  assert.equal(f.menus[1].open, false);
  assert.equal(f.menus[1].focused, true);
  f.menus[0].open = true;
  f.document.handlers.click({ target: {} });
  assert.equal(f.menus[0].open, false);
});

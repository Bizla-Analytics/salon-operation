const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../templates/operations/service_assignments.html'), 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];

function fixture({ locked = false, removed = false } = {}) {
  const ids = {}, timers = [];
  const document = { activeElement: null, getElementById: id => ids[id],
    createTextNode: text => ({ textContent: text }), createElement: () => element() };
  function element(id) {
    const el = { id, value: '', required: false, checked: false, disabled: false, className: '',
      attributes: {}, children: [], style: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      getAttribute(name) { return this.attributes[name]; },
      removeAttribute(name) { delete this.attributes[name]; },
      appendChild(child) { this.children.push(child); },
      contains(target) { return this === target || this.children.some(child => child.contains && child.contains(target)); },
      querySelectorAll() { return this.children.filter(child => child.className && child.className.includes('combobox-option')); },
      scrollIntoView() {}, select() { this.textSelected = true; },
      focus() { if (document.activeElement !== this) { document.activeElement = this; if (this.onfocus) this.onfocus(); } },
      click() { if (this.onclick) this.onclick(); },
    };
    Object.defineProperty(el, 'innerHTML', { get: () => '', set: () => { el.children = []; } });
    if (id) ids[id] = el;
    return el;
  }
  function row(index, isLocked = false, isRemoved = false) {
    const prefix = `services-${index}`;
    const order = element(`id_${prefix}-order_number`); order.value = index + 1; order.required = true;
    const input = element(`${prefix}-service-search`); input.setAttribute('aria-labelledby', `${prefix}-service-label`);
    const label = element(`${prefix}-service-label`);
    const menu = element(`${prefix}-service-options`);
    const select = element(`id_${prefix}-service`); select.required = true; select.disabled = isLocked;
    select.options = [{ value: '', text: 'Choose a service' }, { value: '1', text: 'Facial' }, { value: '2', text: 'Threading' }];
    const staff = element(`id_${prefix}-employee`); staff.required = true;
    const chair = element(`id_${prefix}-chair`);
    const remove = element(`id_${prefix}-DELETE`); remove.checked = isRemoved;
    const box = element(); box.className = 'service-combobox'; box.children = [input, menu, select];
    box.querySelector = selector => ({ '.service-combobox-input': input, '.service-combobox-menu': menu, select })[selector];
    const result = element(); result.children = [box, order, staff, chair, remove];
    result.querySelector = selector => ({ '.service-combobox': box, '.service-combobox-input': input, 'input[name$="-DELETE"]': remove })[selector];
    result.querySelectorAll = () => [order, input, select, staff, chair, remove];
    return Object.assign(result, { order, input, label, menu, selectField: select, staff, remove });
  }
  const rows = element('assignment-rows'); rows.children = [row(0, locked, removed), row(1)];
  rows.querySelectorAll = selector => selector === '.assignment-row' ? rows.children : rows.children.map(item => item.order);
  Object.defineProperty(rows, 'lastElementChild', { get: () => rows.children.at(-1) });
  rows.insertAdjacentHTML = (_, html) => rows.children.push(row(Number(html.match(/data-index="(\d+)"/)[1])));
  const add = element('add-assignment');
  const total = element('id_services-TOTAL_FORMS'); total.value = '2';
  const template = { innerHTML: '<div data-index="__prefix__"></div>' }; ids['empty-assignment-row'] = template;
  vm.runInNewContext(source, { document, window: {}, setTimeout: fn => timers.push(fn) });
  return { document, rows, add, total, first: rows.children[0], flush: () => { while (timers.length) timers.shift()(); } };
}

test('enhanced service search uses visible validation and accessible labels', () => {
  const { first } = fixture();
  assert.equal(first.input.required, true);
  assert.equal(first.selectField.required, false);
  assert.equal(first.label.attributes.for, first.input.id);
  assert.equal(first.selectField.attributes['aria-labelledby'], 'services-0-service-label');
});

test('keyboard search highlights a result and commits its underlying service value', () => {
  const { first } = fixture();
  first.input.focus();
  first.input.value = 'thread'; first.input.oninput();
  assert.equal(first.menu.children.length, 1);
  first.input.onkeydown({ key: 'ArrowDown', preventDefault() {} });
  assert.equal(first.input.attributes['aria-activedescendant'], 'services-0-service-options-2');
  first.input.onkeydown({ key: 'Enter', preventDefault() {} });
  assert.equal(first.selectField.value, '2');
  assert.equal(first.input.value, 'Threading');
  assert.equal(first.input.attributes['aria-expanded'], 'false');
});

test('touch scrolling does not select on touchstart and choosing by click closes the menu', () => {
  const { first, document, flush } = fixture();
  first.input.focus();
  const option = first.menu.children[0];
  assert.equal(option.ontouchstart, undefined);
  document.activeElement = option; first.input.onblur(); flush();
  assert.equal(first.input.attributes['aria-expanded'], 'true');
  option.click();
  assert.equal(first.selectField.value, '1');
  assert.equal(first.input.attributes['aria-expanded'], 'false');
  first.input.focus(); document.activeElement = null; first.input.onblur(); flush();
  assert.equal(first.input.attributes['aria-expanded'], 'false');
});

test('removed blank rows do not block native validation and undo restores required fields', () => {
  const { first } = fixture({ removed: true });
  assert.equal(first.input.required, false);
  assert.equal(first.staff.required, false);
  assert.equal(first.attributes['data-removed'], 'true');
  first.remove.checked = false; first.remove.onchange();
  assert.equal(first.input.required, true);
  assert.equal(first.staff.required, true);
  assert.equal(first.selectField.required, false);
});

test('locked services stay disabled; added rows get unique indices and the next order', () => {
  const f = fixture({ locked: true });
  assert.equal(f.first.input.disabled, true);
  f.rows.children[1].order.value = '8';
  f.add.click();
  assert.equal(f.total.value, 3);
  const added = f.rows.lastElementChild;
  assert.equal(added.input.id, 'services-2-service-search');
  assert.equal(added.order.value, 9);
  assert.equal(f.document.activeElement, added.input);
});

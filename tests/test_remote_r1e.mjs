import assert from 'node:assert/strict';
import test from 'node:test';
import {uploadRecord} from '../src/videoenhancer/remote/web/add.mjs';
import {mountAdd} from '../src/videoenhancer/remote/web/add-ui.mjs';

// Only the DOM surface and persistence are simulated; the real Add flow runs unchanged.
class Element {
  constructor(tag, text = '') { this.tag = tag; this.children = []; this.text = text; }
  get isConnected() { return this.tag === 'main' || Boolean(this.parent?.isConnected); }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  set textContent(value) { this.replaceChildren(); this.text = String(value); }
  append(...children) {
    for (const child of children) { child.parent = this; this.children.push(child); }
  }
  replaceChildren(...children) {
    for (const child of this.children) child.parent = null;
    this.children = []; this.text = ''; this.append(...children);
  }
  setAttribute(name, value) { this[name] = value; }
  querySelectorAll(selector) {
    assert.ok(['button', 'input[type=file]'].includes(selector), `Unsupported selector: ${selector}`);
    return this.children.flatMap(child => [
      ...(selector === child.tag || selector === 'input[type=file]' && child.tag === 'input' && child.type === 'file' ? [child] : []),
      ...child.querySelectorAll(selector),
    ]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
function documentFixture(t) {
  const main = new Element('main');
  t.after(() => main.replaceChildren());
  return {
    createElement: tag => new Element(tag),
    createTextNode: text => new Element('#text', text),
    querySelector: selector => { assert.equal(selector, 'main'); return main; },
  };
}

function database(records) {
  const data = new Map(records.map(record => [record.id, record]));
  return {open() {
    const request = {};
    queueMicrotask(() => {
      request.result = {close() {}, transaction() {
        const tx = {objectStore() {return {
          getAll() {return {result: [...data.values()]};},
          put(value, key) {data.set(key, value); return {};},
          delete(key) {data.delete(key); return {};},
        };}};
        queueMicrotask(() => tx.oncomplete());
        return tx;
      }};
      request.onsuccess();
    });
    return request;
  }};
}
const flush = async () => {for (let i = 0; i < 30; i++) await Promise.resolve();};

for (const recovery of ['same', 'cancel', 'resume']) test(`lost start recovery: ${recovery}`, async t => {
  for (const [name, value] of Object.entries({document: documentFixture(t),
    navigator: {userAgent: 'Macintosh', maxTouchPoints: 0}, indexedDB: database([])})) {
    const old = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {configurable: true, value});
    t.after(() => {if (old) Object.defineProperty(globalThis, name, old); else delete globalThis[name];});
  }
  const main = document.querySelector('main');
  const element = (tag, text) => {const node = document.createElement(tag); if (text) node.textContent = text; return node;};
  const button = (text, click) => {const node = element('button', text); node.onclick = click; return node;};
  let starts = 0, deletes = 0, release;
  const api = async (path, options) => {
    if (path === '/api/uploads') {
      starts++;
      if (starts === 1) throw Object.assign(new Error('conflict'), {status: 409,
        upload: {id: 'lost', name: 'old.mp4', size: 2, offset: 1}});
      return {id: 'new'};
    }
    if (options?.method === 'DELETE') {deletes++; await new Promise(resolve => {release = resolve;}); return null;}
    if (path === '/api/estimate') return {entries: []};
    if (path.endsWith('/finish')) return {ready: true};
    if (path.includes('/chunk')) {
      assert.match(path, recovery === 'cancel' ? /offset=0$/ : /offset=1$/);
      await new Promise(resolve => {release = resolve;}); return {offset: 2};
    }
    return {offset: recovery === 'cancel' ? 0 : 1};
  };
  mountAdd({main, element, button, api, added: async () => {}});
  await flush();
  const input = main.querySelector('input[type=file]');
  let file = new Blob(['xy']); file.name = recovery === 'same' ? 'old.mp4' : 'new.mp4';
  Object.defineProperty(input, 'files', {configurable: true, get: () => [file]});
  let running = input.onchange(); await flush();
  if (recovery !== 'same') {
    await running;
    assert.match(main.textContent, /Another upload from this device is unfinished\./);
    const action = [...main.querySelectorAll('button')].find(node => node.textContent === (recovery === 'cancel' ? 'Cancel it' : 'Resume it'));
    assert.ok(action);
    if (recovery === 'cancel') {
      running = action.onclick(); await flush();
      assert.equal(input.disabled, true); assert.equal(starts, 1); assert.equal(deletes, 1);
      release(); await flush();
    } else {
      input.click = () => {};
      await action.onclick();
      // A wrong re-selection must keep the recovery prompt and avoid another start.
      await input.onchange(); await flush(); assert.equal(starts, 1);
      file = new Blob(['xy']); file.name = 'old.mp4';
      running = input.onchange(); await flush();
    }
  }
  assert.equal(input.disabled, true);
  assert.equal(starts, recovery === 'cancel' ? 2 : 1);
  await input.onchange();
  release(); await running;
  assert.equal(input.disabled, false);
  const records = await uploadRecord('get');
  assert.equal(records.length, 1);
  assert.equal(records[0].id, recovery === 'cancel' ? 'new' : 'lost');
});

test('resume records keep separate ids and Add removes only its own record', async t => {
  const first = {id: 'first', name: 'first.mp4', size: 1, file: new Blob(['x'])};
  const second = {id: 'second', name: 'second.mp4', size: 1, file: new Blob(['y'])};
  for (const [name, value] of Object.entries({document: documentFixture(t),
    navigator: {userAgent: 'Macintosh', maxTouchPoints: 0}, indexedDB: database([first, second])})) {
    const old = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {configurable: true, value});
    t.after(() => {if (old) Object.defineProperty(globalThis, name, old); else delete globalThis[name];});
  }
  assert.equal((await uploadRecord('get')).length, 2);
  const main = document.querySelector('main');
  const element = (tag, text) => {const node = document.createElement(tag); if (text) node.textContent = text; return node;};
  const button = (text, click) => {const node = element('button', text); node.onclick = click; return node;};
  const api = async path => path === '/api/estimate' ? {entries: []} : {ready: true, size: 1, offset: 1};
  mountAdd({main, element, button, api, added: async () => {}});
  await flush();
  let resumes = [...main.querySelectorAll('button')].filter(node => node.textContent.includes('Resume upload'));
  assert.equal(resumes.length, 2);
  await resumes[0].onclick();
  const add = [...main.querySelectorAll('button')].find(node => node.textContent === 'Add');
  await add.onclick();
  assert.deepEqual((await uploadRecord('get')).map(record => record.id), ['second']);
  await uploadRecord('put', first);
  assert.equal((await uploadRecord('get')).length, 2);
});

test('upload stays busy through create, transfer, verification and estimate, including remount', async t => {
  for (const [name, value] of Object.entries({document: documentFixture(t),
    navigator: {userAgent: 'Macintosh', maxTouchPoints: 0}, indexedDB: database([])})) {
    const old = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {configurable: true, value});
    t.after(() => {if (old) Object.defineProperty(globalThis, name, old); else delete globalThis[name];});
  }
  let release, calls = 0;
  const pending = () => new Promise(resolve => {release = resolve;});
  const api = async path => {
    if (path === '/api/uploads') {calls++; await pending(); return {id: 'new'};}
    if (path.endsWith('/new')) return {offset: 0};
    if (path.includes('/chunk')) {await pending(); return {offset: 1};}
    if (path.endsWith('/finish')) {await pending(); return {ready: true};}
    if (path === '/api/estimate') {await pending(); return {entries: []};}
    return {};
  };
  const element = (tag, text) => {const node = document.createElement(tag); if (text) node.textContent = text; return node;};
  const button = (text, click) => {const node = element('button', text); node.onclick = click; return node;};
  const main = document.querySelector('main');
  const mount = () => mountAdd({main, element, button, api, added: async () => {}});
  mount(); await flush();
  const input = main.querySelector('input[type=file]');
  const file = new Blob(['x']); file.name = 'synthetic.mp4';
  Object.defineProperty(input, 'files', {value: [file]});
  const running = input.onchange();
  for (let phase = 0; phase < 4; phase++) {
    await flush();
    assert.equal(input.disabled, true);
    assert.match(main.textContent, /Uploading… \(one at a time\)/);
    await input.onchange();
    assert.equal(calls, 1);
    if (phase === 1) {main.replaceChildren(); mount();}
    release();
  }
  await running;
  assert.equal(main.querySelector('input[type=file]').disabled, false);
});

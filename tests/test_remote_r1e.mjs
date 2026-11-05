import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from '../gui/node_modules/jsdom/lib/api.js';
import {uploadRecord} from '../src/videoenhancer/remote/web/add.mjs';
import {mountAdd} from '../src/videoenhancer/remote/web/add-ui.mjs';

// Only persistence is simulated; tests exercise the actual upload controls and API flow.
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

test('resume records keep separate ids and Add removes only its own record', async t => {
  const dom = new JSDOM('<main></main>', {url: 'https://synthetic.test'});
  t.after(() => dom.window.close());
  const first = {id: 'first', name: 'first.mp4', size: 1, file: new Blob(['x'])};
  const second = {id: 'second', name: 'second.mp4', size: 1, file: new Blob(['y'])};
  for (const [name, value] of Object.entries({window: dom.window, document: dom.window.document,
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
  const dom = new JSDOM('<main></main>', {url: 'https://synthetic.test'});
  t.after(() => dom.window.close());
  for (const [name, value] of Object.entries({window: dom.window, document: dom.window.document,
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

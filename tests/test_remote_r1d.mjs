import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from '../gui/node_modules/jsdom/lib/api.js';

test('Library returns synchronously, keeps unchanged images, diffs ids and restores scroll', async t => {
  const html = await readFile(new URL('../src/videoenhancer/remote/web/index.html', import.meta.url), 'utf8');
  const dom = new JSDOM(html, {url: 'https://synthetic.test/'});
  const {window} = dom;
  let items = [{id: 'a', name: 'Landscape', duration: 60}, {id: 'b', name: 'Portrait', duration: 90}];
  let pending, posterTime;
  window.scrollTo = (_, y) => { window.scrollY = y; };
  window.HTMLMediaElement.prototype.pause = () => {};
  window.HTMLMediaElement.prototype.load = () => {};
  const values = {window, document: window.document, navigator: {userAgent: 'Macintosh', maxTouchPoints: 0},
    location: window.location, history: window.history, sessionStorage: window.sessionStorage,
    matchMedia: () => ({matches: false}), fetch: async (path, options) => {
      if (path.endsWith("/poster")) { posterTime = JSON.parse(options.body).time; return {ok: true, json: async () => ({etag: "new-poster"})}; }
      if (path === '/api/library' && pending) await pending;
      const data = path === '/api/session' ? {paired: true, notifications_on: true} :
        path === '/api/library' ? {items} : path === '/api/jobs/active' ? {jobs: []} : {};
      return {ok: true, json: async () => data};
    }};
  for (const [name, value] of Object.entries(values)) {
    const old = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {configurable: true, value});
    t.after(() => {if (old) Object.defineProperty(globalThis, name, old); else delete globalThis[name];});
  }
  t.mock.timers.enable({apis: ['setTimeout']});
  t.after(() => dom.window.close());
  await import('../src/videoenhancer/remote/web/app.mjs?test=r1d');
  const flush = async () => {for (let n = 0; n < 20; n++) await Promise.resolve();};
  await flush();
  const document = window.document;
  assert.equal(document.querySelector('header'), null);
  const images = [...document.querySelectorAll('.videos img')];
  assert.equal(images.length, 2);
  assert.equal(document.querySelector('.video-row').textContent, '');
  assert.equal(document.querySelector('.video-row').getAttribute('aria-label'), 'Landscape, 1:00');
  window.scrollY = 350;
  document.querySelector('.video-row').click();
  document.querySelector('video').currentTime = 12.5;
  const thumbnail = [...document.querySelectorAll('button')].find(button => button.textContent === 'Set as thumbnail');
  assert.ok(thumbnail); thumbnail.click(); await flush();
  assert.equal(posterTime, 12.5);
  assert.match(document.querySelector('#main').textContent, /Thumbnail updated\./);
  assert.match(images[0].src, /v=new-poster/);
  assert.doesNotMatch(images[1].src, /v=/);
  document.querySelector('video').currentTime = 20;
  document.body.dispatchEvent(new window.KeyboardEvent('keydown', {code: 'KeyT', bubbles: true}));
  await flush(); assert.equal(posterTime, 20);
  let resolve;
  pending = new Promise(r => {resolve = r;});
  document.querySelector('.back').click();
  assert.equal(window.scrollY, 350);
  assert.equal(document.querySelector('.videos img'), images[0]);
  items = [{...items[0], name: 'Changed'}, {id: 'c', name: 'New', duration: 20}];
  resolve(); await flush();
  assert.equal(document.querySelector('.videos img'), images[0]);
  assert.equal(document.querySelectorAll('.videos img').length, 2);
  assert.equal(images[1].isConnected, false);
  assert.equal(document.querySelector('.video-row').title, 'Changed');
  document.querySelector('#settings-tab').click(); await flush();
  assert.ok(document.querySelector('.storage'));
  document.querySelector('#library-tab').click();
  assert.equal(document.querySelector('.videos img'), images[0]);
});

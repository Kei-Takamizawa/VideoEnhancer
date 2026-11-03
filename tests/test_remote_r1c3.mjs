import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from '../gui/node_modules/jsdom/lib/api.js';
import {mountPlayer} from '../src/videoenhancer/remote/web/player.mjs';
import * as platform from '../src/videoenhancer/remote/web/platform.mjs';

function player(t, touch = false, userAgent = 'Macintosh') {
  t.mock.timers.enable({apis: ['setTimeout']});
  const dom = new JSDOM('<body></body>', {url: 'https://synthetic.test/'});
  const {document} = dom.window;
  for (const [name, value] of Object.entries({document, navigator: {userAgent, maxTouchPoints: touch ? 5 : 0}, fetch: async () => ({ok: false})})) { const old = Object.getOwnPropertyDescriptor(globalThis, name); Object.defineProperty(globalThis, name, {configurable: true, value}); t.after(() => {if (old) Object.defineProperty(globalThis, name, old); else delete globalThis[name];}); }
  const element = (tag, text, cls) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; };
  const button = (text, fn) => { const el = element('button', text); el.onclick = fn; return el; };
  const video = element('video'); let paused = true; let position = 60;
  Object.defineProperties(video, {paused: {get: () => paused}, duration: {get: () => 600}, readyState: {get: () => 1}, currentTime: {get: () => position, set: v => {position = v;}}});
  video.play = async () => {paused = false; video.dispatchEvent(new dom.window.Event('play'));};
  video.pause = () => {paused = true; video.dispatchEvent(new dom.window.Event('pause'));};
  let returns = 0;
  const root = mountPlayer(video, {id: 'synthetic', name: 'Synthetic landscape', duration: 600}, {element, button, backToLibrary: () => returns++});
  document.body.append(root);
  let full = false;
  root.requestFullscreen = async () => {full = true;};
  Object.defineProperty(document, 'fullscreenElement', {get: () => full ? root : null});
  document.exitFullscreen = async () => {full = false;};
  const key = (code, options = {}, target = document.body) => {const event = new dom.window.KeyboardEvent('keydown', {code, bubbles: true, cancelable: true, ...options}); target.dispatchEvent(event); return event.defaultPrevented;};
  const pointer = (type, pointerType = 'mouse', target = video) => {const event = new dom.window.Event(type, {bubbles: true}); Object.defineProperty(event, 'pointerType', {value: pointerType}); target.dispatchEvent(event);};
  t.after(() => {root.dispose?.(); dom.window.close();});
  return {dom, document, root, video, key, pointer, full: () => full, returns: () => returns};
}

test('document shortcuts work before focus and prevent browser defaults', async t => {
  const {key, video, root, full} = player(t);
  assert.equal(key('Space'), true); assert.equal(video.paused, false);
  assert.equal(key('KeyK'), true); assert.equal(video.paused, true);
  for (const [code, shiftKey, want] of [['ArrowRight', false, 65], ['ArrowLeft', false, 60], ['ArrowRight', true, 90], ['ArrowLeft', true, 60]]) {assert.equal(key(code, {shiftKey}), true); assert.equal(video.currentTime, want);}
  video.volume = .5;
  assert.equal(key('ArrowUp'), true); assert.equal(video.volume, .6);
  assert.equal(key('ArrowDown'), true); assert.equal(video.volume, .5);
  assert.equal(key('KeyM'), true); assert.equal(video.muted, true);
  assert.equal(key('KeyF'), true); assert.equal(full(), true);
  assert.equal(key('Escape'), true); assert.equal(full(), false);
  const seek = root.querySelector('[aria-label=Seek]'); assert.equal(key('ArrowRight', {}, seek), true); assert.equal(video.currentTime, 65);
  root.dispose(); assert.equal(key('Space'), false); assert.equal(video.paused, true);
});

test('editing and modified keys are left to the browser', t => {
  const {document, key, video} = player(t);
  for (const tag of ['input', 'textarea', 'select', 'div']) {
    const el = document.createElement(tag); if (tag === 'div') el.setAttribute('contenteditable', 'true'); document.body.append(el);
    assert.equal(key('Space', {}, el), false);
  }
  for (const modifier of ['metaKey', 'ctrlKey', 'altKey']) assert.equal(key('Space', {[modifier]: true}), false);
  assert.equal(video.paused, true);
});

test('single mouse click waits; double click only changes fullscreen', t => {
  const {video, full, pointer, dom} = player(t);
  pointer('pointerup'); assert.equal(video.paused, true);
  t.mock.timers.tick(251); assert.equal(video.paused, false);
  pointer('pointerup'); pointer('pointerup'); video.dispatchEvent(new dom.window.Event('dblclick', {bubbles: true}));
  t.mock.timers.tick(300); assert.equal(full(), true); assert.equal(video.paused, false);
});

test('idle hides bars and cursor, movement and pause reveal, bars and drag pin', t => {
  const {video, root, pointer, key} = player(t);
  const hidden = () => root.classList.contains('controls-hidden');
  t.mock.timers.tick(3000); assert.equal(hidden(), false);
  key('Space'); t.mock.timers.tick(2501); assert.equal(hidden(), true);
  pointer('pointermove'); assert.equal(hidden(), false);
  pointer('pointerenter', 'mouse', root.querySelector('.player-controls'));
  t.mock.timers.tick(3000); assert.equal(hidden(), false);
  pointer('pointerleave', 'mouse', root.querySelector('.player-controls'));
  t.mock.timers.tick(2501); assert.equal(hidden(), true);
  key('KeyM'); assert.equal(hidden(), false);
  const seek = root.querySelector('[aria-label=Seek]'); seek.setPointerCapture = () => {};
  pointer('pointerdown', 'touch', seek); t.mock.timers.tick(3000); assert.equal(hidden(), false);
  pointer('pointercancel', 'touch', seek); t.mock.timers.tick(2501); assert.equal(hidden(), true);
  video.pause(); assert.equal(hidden(), false);
});

test('touch reveals hidden controls, visible tap toggles playback, double tap enters native fullscreen', t => {
  const {root, video, pointer} = player(t, true);
  let fullscreen = 0; video.webkitEnterFullscreen = () => fullscreen++;
  assert.equal(root.querySelector('.player-remaining').textContent, '-9:00');
  root.classList.add('controls-hidden');
  pointer('pointerup', 'touch'); t.mock.timers.tick(300);
  assert.equal(root.classList.contains('controls-hidden'), false);
  assert.equal(video.paused, true);
  pointer('pointerup', 'touch'); t.mock.timers.tick(300);
  assert.equal(video.paused, false);
  pointer('pointerup', 'touch'); pointer('pointerup', 'touch');
  assert.equal(fullscreen, 1);
  t.mock.timers.tick(300); assert.equal(video.paused, false);
});

test('push failure preserves browser error and selects Brave guidance', async () => {
  assert.equal(typeof platform.pushFailure, 'function');
  const error = new Error('Registration failed - push service error');
  assert.match(await platform.pushFailure(error, {brave: {isBrave: async () => true}}), /Registration failed - push service error.*brave:\/\/settings\/privacy.*Use Google services for push messaging/);
  assert.doesNotMatch(await platform.pushFailure(error, {}), /Brave/);
  assert.match(await platform.pushFailure(error, {brave: {isBrave: async () => {throw Error();}}}), /Registration failed/);
});


test('minimal overlay has only time, seek and preview, with no title or buttons', t => {
  const {root, video, key} = player(t);
  assert.equal(root.querySelectorAll('.player-controls button, .volume, .player-title').length, 0);
  assert.equal(root.querySelectorAll('.player-controls > *').length, 3);
  video.currentTime = 595; key('ArrowRight'); assert.equal(video.currentTime, 600);
  assert.equal(root.querySelector('.player-remaining').textContent, '-0:00');
  video.currentTime = 2; key('ArrowLeft'); assert.equal(video.currentTime, 0);
});

test('Mac Esc and Backspace return only outside fullscreen and editable fields', t => {
  const {key, returns} = player(t);
  key('KeyF'); key('Backspace'); assert.equal(returns(), 0);
  key('Escape'); assert.equal(returns(), 0);
  assert.equal(key('Escape'), true); assert.equal(returns(), 1);
  assert.equal(key('Backspace'), true); assert.equal(returns(), 2);
});

test('hover leaves playback thumb fixed, drag seeks, and released mouse resumes hover', t => {
  const {root, video, dom} = player(t);
  const seek = root.querySelector('[aria-label=Seek]');
  seek.getBoundingClientRect = () => ({left: 0, width: 600});
  seek.setPointerCapture = () => {};
  const move = (type, x, buttons) => {
    const event = new dom.window.MouseEvent(type, {clientX: x, buttons, bubbles: true, cancelable: true});
    Object.defineProperty(event, 'pointerType', {value: 'mouse'});
    seek.dispatchEvent(event);
  };
  move('pointermove', 200, 0);
  assert.equal(Number(seek.value), 60); assert.equal(video.currentTime, 60);
  assert.equal(root.querySelector('.seek-preview').hidden, false);
  move('pointerdown', 200, 1);
  move('pointermove', 300, 1);
  assert.equal(Number(seek.value), 300); assert.equal(video.currentTime, 300);
  move('pointermove', 400, 0);
  assert.equal(Number(seek.value), 300); assert.equal(video.currentTime, 300);
});

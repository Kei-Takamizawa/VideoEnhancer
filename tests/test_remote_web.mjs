import './test_remote_r1c.mjs';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {runInNewContext} from 'node:vm';
import {
  downloadProgress, formatDuration, formatSize, pairingScreen, pairingStatus,
  shareFile, storageSegments, storageText, loadFile, needsSafari, safariURL, safariInstructions,
} from '../src/videoenhancer/remote/web/logic.mjs';

test('pairing countdown, expiry and claim states', () => {
  const original = [{id: 'first', label: 'iPad'}];
  const state = {pairing_open: true, closes_at: new Date(120000).toISOString(), devices: original};
  assert.equal(pairingStatus(state, original, 0), 'Pairing is open for 2:00.');
  assert.equal(pairingStatus(state, original, 61000), 'Pairing is open for 0:59.');
  assert.equal(pairingStatus(state, original, 120000), 'Pairing closed.');
  assert.equal(pairingStatus({...state, pairing_open: false}, original, 0), 'Pairing closed.');
  assert.equal(pairingStatus({...state, pairing_open: false, devices: [...original, {id: 'new', label: 'Mac, Safari 26'}]}, original, 0), 'New device added: Mac, Safari 26.');
});

test('storage segments distinguish library, other used, and free space', () => {
  assert.deepEqual(storageSegments({total: 1000, free: 400, library_bytes: 200}), [20, 40, 40]);
  assert.deepEqual(storageSegments({total: 0, free: 0, library_bytes: 0}), [0, 0, 100]);
  assert.deepEqual(storageSegments({total: 100, free: 200, library_bytes: 300}), [0, 0, 100]);
});

test('storage text uses decimal gigabytes and one decimal place', () => {
  assert.equal(storageText({total: 1000200000000, free: 456700000000, library_bytes: 12300000000, drive_label: 'D:'}),
    'Library 12.3 GB · Free 456.7 GB of 1,000.2 GB (D:)');
});

test('size and duration formatting handle missing metadata and long videos', () => {
  assert.equal(formatSize(1250000), '1.3 MB');
  assert.equal(formatSize(2500000000), '2.5 GB');
  assert.equal(formatDuration(65.9), '1:05');
  assert.equal(formatDuration(3661), '1:01:01');
  assert.equal(formatDuration(null), 'Unknown duration');
  assert.equal(formatDuration(NaN), 'Unknown duration');
});

test('download progress uses decimal MB with grouping', () => {
  assert.equal(downloadProgress(312000000, 1024000000), 'Loading 312 of 1,024 MB');
  assert.equal(downloadProgress(312000000, 0), 'Loading 312 MB');
});

test('pairing decisions never expose app while unpaired', () => {
  assert.equal(pairingScreen({paired: true}, false), 'app');
  assert.equal(pairingScreen({paired: false, pairing_open: true}, true), 'claim');
  assert.equal(pairingScreen({paired: false, pairing_open: true}, false), 'install');
  assert.equal(pairingScreen({paired: false, pairing_open: false}, true), 'closed');
});

test('share cancellation is successful and unrelated failures propagate', async () => {
  const file = new Blob(['video'], {type: 'video/mp4'});
  let shared;
  assert.equal(await shareFile(file, {share: async payload => { shared = payload; }}), 'shared');
  assert.deepEqual(shared, {files: [file]});
  assert.equal(await shareFile(file, {share: async () => { throw new DOMException('Cancelled', 'AbortError'); }}), 'cancelled');
  await assert.rejects(shareFile(file, {}), /File sharing is unavailable/);
  await assert.rejects(shareFile(file, {share: async () => { throw new Error('Failed'); }}), /Failed/);
});

test('service worker caches only fixed shell requests', async () => {
  const worker = await readFile(new URL('../src/videoenhancer/remote/web/sw.js', import.meta.url), 'utf8');
  const listeners = new Map();
  let cached;
  runInNewContext(worker, {
    self: {location: {origin: 'https://pc.local:8443'}, addEventListener: (name, handler) => listeners.set(name, handler)},
    URL, Response,
    fetch: async () => { throw new TypeError('Offline'); },
    caches: {match: async path => { cached = path; return new Response('shell'); }},
  });
  for (const [method, path] of [['GET', '/api/session'], ['GET', '/api/library/id/video'], ['POST', '/'], ['GET', '/?secret=value'], ['GET', 'https://other.local/']]) {
    let intercepted = false;
    listeners.get('fetch')({request: {method, url: new URL(path, 'https://pc.local:8443').href}, respondWith: () => { intercepted = true; }});
    assert.equal(intercepted, false, `${method} ${path} must bypass shell caching`);
  }
  let result;
  listeners.get('fetch')({request: {method: 'GET', url: 'https://pc.local:8443/style.css'}, respondWith: promise => { result = promise; }});
  assert.equal(await (await result).text(), 'shell');
  assert.equal(cached, '/style.css');
});

test('load builds File from the single response Blob while counting bytes', async () => {
  const blob = new Blob(['synthetic'], {type: 'video/mp4'});
  const progress = [];
  const response = new Response(blob);
  let calls = 0;
  response.blob = async () => { calls++; return blob; };
  const file = await loadFile(response, 'sample.mp4', loaded => progress.push(loaded));
  assert.equal(calls, 1);
  assert.equal(file.name, 'sample.mp4');
  assert.equal(file.type, 'video/mp4');
  assert.equal(await file.text(), 'synthetic');
  assert.equal(progress.at(-1), 9);
});

test('threshold bypasses sharing only above the configured limit', () => {
  assert.equal(needsSafari(900000000), false);
  assert.equal(needsSafari(900000001), true);
  assert.equal(needsSafari(101, 100), true);
});

test('Safari link retains same host port and token and gives manual fallback', () => {
  assert.equal(safariURL('https://pc.local:8443/dl/abc'), 'x-safari-https://pc.local:8443/dl/abc');
  assert.throws(() => safariURL('http://pc.local/dl/abc'));
  assert.equal(safariInstructions, 'Paste this link into Safari to save the video to Files.');
});

test('canShare refusal propagates for the Safari fallback and records result before share', async () => {
  const checks = [];
  let invoked = false;
  await assert.rejects(shareFile(new Blob(['x']), {canShare: () => false,
    share: async () => { invoked = true; }}, result => checks.push(result)), /File sharing is unavailable/);
  assert.equal(invoked, false);
  assert.deepEqual(checks, [false]);
});

// R1b add flow: pure decisions and bounded upload/crypto helpers.
const add = await import('../src/videoenhancer/remote/web/add.mjs');
const {createHash} = await import('node:crypto');

test('finish time shows known local time and never guesses unknown estimates', () => {
  assert.equal(add.finishText({finish: null}), 'Finish time unknown until the download starts');
  assert.equal(add.finishText({finish: 'bad', seconds: 20}), 'Finish time unknown until the download starts');
  assert.match(add.finishText({finish: '2026-11-02T18:00:00Z', seconds: 120}), /^Ready about .+ \(2 minutes from now\)$/);
});

test('playlist selection defaults eligible entries on and keeps refused entries off', () => {
  const rows = [{key: 'one'}, {key: 'two', error: 'Too large'}, {key: 'three'}];
  assert.deepEqual(add.selectedEntries(rows), ['one', 'three']);
  assert.deepEqual(add.selectedEntries(rows, new Set(['three', 'two'])), ['three']);
});

test('upload wording distinguishes transfer, resume and open app requirement', () => {
  assert.match(add.uploadText(4000000, 8000000, 2000000), /4.*8.*2.*MB\/s/);
  assert.match(add.resumeText({offset: 4000000, size: 8000000}), /Resume.*4.*8/);
  assert.equal(add.keepOpenText, 'Keep this app open while the video uploads.');
});

test('incremental SHA256 matches crypto across block, padding and chunk boundaries', async () => {
  for (const size of [0, 1, 55, 56, 63, 64, 65, 127, 128, 10001, 4194305]) {
    const bytes = Uint8Array.from({length: size}, (_, i) => (i * 17) % 256);
    const hash = new add.Sha256();
    for (let offset = 0; offset < size; offset += 71) hash.update(bytes.subarray(offset, offset + 71));
    assert.equal(hash.hex(), createHash('sha256').update(bytes).digest('hex'), `length ${size}`);
    assert.equal(await add.hashBlob(new Blob([bytes])), createHash('sha256').update(bytes).digest('hex'));
  }
});

test('resumed transfer trusts server offset and sends bounded chunks then whole-file digest', async () => {
  const file = new Blob([new Uint8Array(9000000)]);
  const calls = [];
  const request = async (path, options) => {
    calls.push([path, options]);
    if (!options) return {id: 'up', offset: 2000000, size: file.size};
    if (options.method === 'PUT') {
      assert.ok(options.body.size <= 4194304);
      return {offset: Number(new URL(path, 'https://pc').searchParams.get('offset')) + options.body.size};
    }
    return {id: 'up', offset: file.size, ready: true};
  };
  assert.equal((await add.transferUpload(file, 'up', request, () => {})).ready, true);
  assert.equal(calls[1][0], '/api/uploads/up/chunk?offset=2000000');
  assert.equal(JSON.parse(calls.at(-1)[1].body).sha256, createHash('sha256').update(new Uint8Array(9000000)).digest('hex'));
});

test('interrupted upload retries from current server offset without creating another upload', async () => {
  const file = new Blob(['abcdefgh']);
  let offset = 0;
  let fail = true;
  const request = async (path, options) => {
    if (!options) return {offset, size: file.size};
    if (options.method === 'PUT') {
      offset += options.body.size;
      if (fail) { fail = false; throw new Error('Connection dropped'); }
      return {offset};
    }
    assert.equal(JSON.parse(options.body).sha256, createHash('sha256').update('abcdefgh').digest('hex'));
    return {ready: true};
  };
  await assert.rejects(add.transferUpload(file, 'resume', request, () => {}), /Connection dropped/);
  assert.equal((await add.transferUpload(file, 'resume', request, () => {})).ready, true);
});

test('worker displays encrypted notification content and opens only same-origin item routes', async () => {
  const worker = await readFile(new URL('../src/videoenhancer/remote/web/sw.js', import.meta.url), 'utf8');
  const listeners = new Map();
  const notifications = [];
  const opened = [];
  const navigated = [];
  let windows = [];
  runInNewContext(worker, {
    self: {location: {origin: 'https://pc.local:8443'},
      addEventListener: (name, handler) => listeners.set(name, handler),
      registration: {showNotification: async (...args) => notifications.push(args)},
      clients: {matchAll: async () => windows, openWindow: async url => opened.push(url)}},
    URL, Response,
  });
  let pending;
  listeners.get('push')({data: {json: () => ({title: 'Ready', body: 'Sample is in your library.', url: '/#item=abc'})}, waitUntil: promise => { pending = promise; }});
  await pending;
  assert.equal(notifications[0][0], 'Ready');
  assert.equal(notifications[0][1].body, 'Sample is in your library.');
  assert.equal(notifications[0][1].data.url, '/#item=abc');
  const click = async path => {
    let closed = false;
    listeners.get('notificationclick')({notification: {data: {url: path}, close: () => { closed = true; }}, waitUntil: promise => { pending = promise; }});
    await pending; assert.equal(closed, true);
  };
  await click('/#item=abc');
  assert.deepEqual(opened, ['https://pc.local:8443/#item=abc']);
  let focused = false;
  windows = [{url: 'https://pc.local:8443/', navigate: async url => navigated.push(url), focus: async () => { focused = true; }}];
  await click('/#item=next');
  assert.equal(focused, true);
  assert.deepEqual(navigated, ['https://pc.local:8443/#item=next']);
  await click('https://evil.test/');
  assert.equal(navigated.at(-1), 'https://pc.local:8443/');
});

import './test_remote_r1e.mjs';

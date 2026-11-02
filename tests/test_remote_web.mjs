import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {runInNewContext} from 'node:vm';
import {
  downloadProgress, formatDuration, formatSize, pairingScreen,
  shareFile, storageSegments, storageText,
} from '../src/videoenhancer/remote/web/logic.mjs';

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

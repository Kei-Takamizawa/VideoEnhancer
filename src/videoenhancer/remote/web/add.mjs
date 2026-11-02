/** Add-flow decisions and bounded-memory SHA-256/upload helpers. */
import {formatDuration} from './logic.mjs';

export const keepOpenText = 'Keep this app open while the video uploads.';
export function finishText(estimate) {
  const date = new Date(estimate?.finish);
  if (!estimate?.finish || !Number.isFinite(date.getTime())) return 'Finish time unknown until the download starts';
  const seconds = estimate.seconds;
  const duration = Number.isFinite(seconds) && seconds >= 0
    ? (seconds < 60 ? 'less than a minute' : `${Math.ceil(seconds / 60)} minutes`) : null;
  return `Ready about ${date.toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})}${duration ? ` (${duration} from now)` : ''}`;
}
export function selectedEntries(entries, selected = null) {
  return entries.filter(row => !row.error && (!selected || selected.has(row.key))).map(row => row.key);
}
export function uploadText(offset, size, speed = 0) {
  return `${(offset / 1e6).toFixed(1)} of ${(size / 1e6).toFixed(1)} MB · ${(speed / 1e6).toFixed(1)} MB/s`;
}
export function resumeText(status) {
  return `Resume upload (${(status.offset / 1e6).toFixed(1)} of ${(status.size / 1e6).toFixed(1)} MB)`;
}

// SHA-256 (FIPS 180-4). Only one 64-byte block and its schedule are retained.
const K = new Uint32Array([
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2,
]);
const rotate = (x, n) => (x >>> n) | (x << (32 - n));
export class Sha256 {
  constructor() {
    this.state = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
    this.block = new Uint8Array(64);
    this.words = new Uint32Array(64);
    this.used = 0;
    this.length = 0;
  }
  compress() {
    const w = this.words;
    const view = new DataView(this.block.buffer);
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(i * 4);
    for (let i = 16; i < 64; i++) {
      const x = w[i - 15], y = w[i - 2];
      w[i] = (w[i - 16] + (rotate(x,7) ^ rotate(x,18) ^ (x >>> 3)) + w[i - 7] + (rotate(y,17) ^ rotate(y,19) ^ (y >>> 10))) >>> 0;
    }
    let [a,b,c,d,e,f,g,h] = this.state;
    for (let i = 0; i < 64; i++) {
      const t1 = (h + (rotate(e,6) ^ rotate(e,11) ^ rotate(e,25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0;
      const t2 = ((rotate(a,2) ^ rotate(a,13) ^ rotate(a,22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      h=g; g=f; f=e; e=(d+t1)>>>0; d=c; c=b; b=a; a=(t1+t2)>>>0;
    }
    [a,b,c,d,e,f,g,h].forEach((value, i) => { this.state[i] = (this.state[i] + value) >>> 0; });
  }
  update(bytes) {
    if (this.done) throw new Error('Hash is already complete.');
    this.length += bytes.length;
    let offset = 0;
    while (offset < bytes.length) {
      const count = Math.min(64 - this.used, bytes.length - offset);
      this.block.set(bytes.subarray(offset, offset + count), this.used);
      this.used += count; offset += count;
      if (this.used === 64) { this.compress(); this.used = 0; }
    }
    return this;
  }
  hex() {
    if (!this.done) {
      const bits = this.length * 8;
      this.block[this.used++] = 0x80;
      if (this.used > 56) { this.block.fill(0, this.used); this.compress(); this.used = 0; }
      this.block.fill(0, this.used, 56);
      const view = new DataView(this.block.buffer);
      view.setUint32(56, Math.floor(bits / 0x100000000));
      view.setUint32(60, bits >>> 0);
      this.compress(); this.done = true;
    }
    return Array.from(this.state, x => x.toString(16).padStart(8, '0')).join('');
  }
}
export async function hashBlob(file, progress = () => {}) {
  const hash = new Sha256();
  for (let offset = 0; offset < file.size; offset += 4194304) {
    hash.update(new Uint8Array(await file.slice(offset, offset + 4194304).arrayBuffer()));
    progress(Math.min(offset + 4194304, file.size));
  }
  return hash.hex();
}
const transfers = new Map();
export function transferUpload(file, id, request, progress) {
  const running = transfers.get(id);
  if (running) { running.progress = progress; return running.promise; }
  const state = {progress};
  state.promise = transfer(file, id, request, (...args) => state.progress(...args)).finally(() => transfers.delete(id));
  transfers.set(id, state);
  return state.promise;
}
async function transfer(file, id, request, progress) {
  const path = `/api/uploads/${encodeURIComponent(id)}`;
  let status = await request(path);
  if (status.ready) return status;
  if (!Number.isSafeInteger(status.offset) || status.offset < 0 || status.offset > file.size) throw new Error('The upload could not be resumed. Select the video again.');
  while (status.offset < file.size) {
    const start = status.offset;
    const chunk = file.slice(start, start + 4194304);
    const began = performance.now();
    status = await request(`${path}/chunk?offset=${start}`, {method: 'PUT', headers: {'Content-Type': 'application/octet-stream'}, body: chunk});
    if (status.offset !== start + chunk.size) throw new Error('The upload was interrupted. Tap Resume upload to continue.');
    progress(status.offset, file.size, chunk.size / Math.max((performance.now() - began) / 1000, .001));
  }
  progress(file.size, file.size, 0, 'Verifying the upload…');
  const sha256 = await hashBlob(file);
  return request(`${path}/finish`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sha256})});
}

// IndexedDB keeps the browser's Blob on disk instead of serializing a video in memory.
export async function uploadRecord(action, value) {
  const db = await new Promise((resolve, reject) => {
    const open = indexedDB.open('ve-upload-r1b', 1);
    open.onupgradeneeded = () => open.result.createObjectStore('uploads');
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(new Error('This iPad could not save the upload for resuming.'));
  });
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction('uploads', action === 'get' ? 'readonly' : 'readwrite');
      const store = tx.objectStore('uploads');
      const request = action === 'get' ? store.get('current') : action === 'put' ? store.put(value, 'current') : store.delete('current');
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = tx.onabort = () => reject(new Error('This iPad could not save the upload for resuming.'));
    });
  } finally { db.close(); }
}

export function entryDescription(entry) {
  return [formatDuration(entry.duration), entry.width && entry.height ? `${entry.width} × ${entry.height}` : '', finishText(entry.estimate)].filter(Boolean).join(' · ');
}

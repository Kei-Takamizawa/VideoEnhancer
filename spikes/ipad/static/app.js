const $ = selector => document.querySelector(selector);
const status = $('#status');
let config, registration, selectedUpload, shareFile, shareSize, eventSource, sleepStart, recoveryStart;
shareSize = localStorage.getItem('shareSize') || '50MB';
let downloadRun = JSON.parse(localStorage.getItem('downloadRun') || 'null');
let downloadFile;
const interruptedDownload = downloadRun && downloadRun.variant === 'B' && downloadRun.phase === 'loading';
const pending = JSON.parse(localStorage.getItem('pendingResults') || '[]');
let flushing;
const displayMode = () => (window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true) ? 'standalone' : 'browser';
function unpaired() {
  document.querySelectorAll('main > section, main > pre, main > h2').forEach(e => { e.hidden = true; });
  $('#pairing').hidden = false;
  status.textContent = 'This app is not paired. Ask the operator to open pairing, then tap Pair this app.';
}
async function request(path, options = {}) {
  const response = await fetch(path, {credentials:'same-origin', ...options,
    headers:{...options.headers, 'X-Display-Mode':displayMode()}});
  if (response.status === 401) unpaired();
  return response;
}
async function api(path, options = {}) {
  const response = await request(path, options);
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json();
}
async function post(path, data) {
  return api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
}
async function record(test, result) {
  const item = {test, automated:navigator.webdriver === true, ...result, display_mode:displayMode()};
  if (test === 'T3') Object.assign(item, {notification_permission:window.Notification?.permission ?? 'unavailable', push_manager:'PushManager' in window});
  $('#results').textContent = JSON.stringify(item, null, 2) + '\n' + $('#results').textContent;
  pending.push(item);
  localStorage.setItem('pendingResults', JSON.stringify(pending));
  await flush();
}
function flush() {
  if (flushing) return flushing;
  flushing = (async () => {
    while (pending.length) {
      try { await post('/api/results', pending[0]); } catch { if ($('#pairing').hidden) status.textContent = 'Result queued. Reconnect to home Wi-Fi.'; return; }
      pending.shift(); localStorage.setItem('pendingResults', JSON.stringify(pending));
    }
  })().finally(() => { flushing = undefined; });
  return flushing;
}
function action(selector, fn) {
  document.querySelectorAll(selector).forEach(element => element.addEventListener('click', async () => {
    element.disabled = true;
    try { await fn(element); } catch (error) { status.textContent = error.message; }
    finally { element.disabled = false; }
  }));
}
action('#pair-app', async () => { await post('/pair/claim', {}); await init(); });

action('[data-result]', b => record(b.dataset.result, {pass:b.dataset.pass === 'true',phase:'owner_observation'}));
action('#standalone', () => record('T2', {pass:matchMedia('(display-mode: standalone)').matches || navigator.standalone === true}));
action('#push', async () => {
  try {
    if (!('Notification' in window) || !('PushManager' in window)) throw new Error('Web Push unavailable. Open from the Home Screen.');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error(`Notification permission: ${permission}`);
    registration = await navigator.serviceWorker.ready;
    const encoded = config.vapid.replace(/-/g,'+').replace(/_/g,'/');
    const key = Uint8Array.from(atob(encoded + '='.repeat((4-encoded.length%4)%4)), c => c.charCodeAt(0));
    const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:key});
    const scheduled = await post('/api/push', {subscription:subscription.toJSON(),notification_permission:Notification.permission,push_manager:'PushManager' in window});
    await record('T3', {phase:'subscribed',pass:true,...scheduled,push_endpoint_host:new URL(subscription.endpoint).host});
    status.textContent = 'Close the app now. Reopen after 75 seconds.';
  } catch (error) { await record('T3', {phase:'subscribe',pass:false,error:error.message}); }
});

async function upload(file, source) {
  const started = performance.now();
  let aborted = false, abortObserved = false, resumedBytes = 0;
  try {
    $('#upload-status').textContent = 'Computing SHA-256 locally…';
    // shortcut: WebCrypto needs one contiguous buffer; record failure on large iPad files.
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer())), b => b.toString(16).padStart(2,'0')).join('');
    const path = `/api/upload/${digest}`;
    let offset = (await api(path)).offset;
    const initialOffset = offset;
    while (offset < file.size) {
      // Windows WebKit's fetch(Blob slice) sent offset-zero bytes in the spike.
      // Materialize only one chunk so every browser sends the requested range.
      const part = await file.slice(offset, offset + config.chunk_bytes).arrayBuffer();
      if (!aborted && offset > initialOffset) {
        const controller = new AbortController();
        const transfer = request(path + `?offset=${offset}`, {method:'PUT',body:part,signal:controller.signal});
        setTimeout(() => controller.abort(), 1);
        try { await transfer; } catch (error) { if (error.name !== 'AbortError') throw error;abortObserved = true; }
        aborted = true;
        offset = (await api(path)).offset;
        continue;
      }
      const response = await api(path + `?offset=${offset}`, {method:'PUT',body:part});
      if (abortObserved) resumedBytes += response.offset - offset;
      offset = response.offset;
      $('#upload-status').textContent = `${Math.round(offset / 1e6)} / ${Math.round(file.size / 1e6)} MB`;
    }
    const result = await post(path + '/finish', {size:file.size});
    const seconds = (performance.now() - started) / 1000;
    await record('T4', {source,pass:result.sha256 === digest,hash_matches:result.sha256 === digest,
      bytes:file.size,seconds,MB_s:(file.size-initialOffset)/1e6/seconds,chunk_bytes:config.chunk_bytes,
      forced_abort_attempted:aborted,abort_observed:abortObserved,resume_ok:abortObserved && resumedBytes > 0,
      transferred_bytes:file.size-initialOffset,resumed_bytes:resumedBytes,resume_offset:initialOffset});
  } catch (error) {
    await record('T4', {source,pass:false,error:error.message,forced_abort_attempted:aborted});
    $('#upload-status').textContent = 'Upload stopped. Restore Wi-Fi and tap Retry selected upload.';
  }
}
for (const source of ['photos','files']) {
  $('#' + source).addEventListener('change', async event => {
    const file = event.target.files[0];
    if (file) { selectedUpload = {file,source}; await upload(file,source); }
  });
}
action('#retry', async () => { if (selectedUpload) await upload(selectedUpload.file, selectedUpload.source); });

function waitEvent(element, type, timeout=20000) {
  return new Promise((resolve,reject) => {
    const timer = setTimeout(() => done(new Error(`Timeout: ${type}`)), timeout);
    const ok = () => done();
    const fail = () => done(new Error(`Media error ${element.error?.code}: ${element.error?.message || ''}`));
    function done(error) { clearTimeout(timer);element.removeEventListener(type,ok);element.removeEventListener('error',fail);error ? reject(error) : resolve(); }
    element.addEventListener(type,ok,{once:true});element.addEventListener('error',fail,{once:true});
  });
}
let playingTest = false;
async function playback(codec) {
  if (playingTest) return;
  playingTest = true;
  const video = $('#video'), start = performance.now(), result = {codec};
  try {
    const ready = waitEvent(video,'canplay');
    video.src = `/media/${codec}.mp4`;
    video.load();
    const play = video.play();
    play.catch(() => {});
    await ready; result.canplay_ms = performance.now() - start;
    await play;
    if ('requestVideoFrameCallback' in video) {
      await new Promise((resolve,reject) => {
        const timer = setTimeout(() => reject(new Error('First frame timeout')),20000);
        video.requestVideoFrameCallback(() => {clearTimeout(timer);resolve();});
      });
    } else await waitEvent(video,'timeupdate');
    result.first_frame_ms = performance.now() - start;
    for (const fraction of [.5,.9]) {
      const seekStart = performance.now(), seeked = waitEvent(video,'seeked');
      video.currentTime = video.duration * fraction; await seeked;
      result[`seek_${fraction*100}_ms`] = performance.now() - seekStart;
    }
    await record('T5', {...result,pass:true,errors:[]});
  } catch (error) { await record('T5', {...result,pass:false,errors:[error.message]}); }
  finally { video.pause(); playingTest = false; }
}
action('[data-codec]', b => playback(b.dataset.codec));

function saveDownload() { localStorage.setItem('downloadRun',JSON.stringify(downloadRun)); }
function downloadResult(phase, extra={}) {
  return record('T6', {...downloadRun,phase,observation_elapsed_s:(Date.now()-downloadRun.started_ms)/1000,...extra});
}
function startDownload(variant, size) {
  downloadFile = null; $('#download-share').disabled = true;
  downloadRun = {run:crypto.randomUUID(),variant,size,started_ms:Date.now(),phase:'started',hidden_ms:null,background_intervals:[]};
  saveDownload();
  return downloadResult('started');
}
document.querySelectorAll('[data-download]').forEach(b => b.addEventListener('click', event => {
  if (downloadRun?.phase === 'loading') { event.preventDefault(); status.textContent = 'Wait for the current Blob load to finish.'; return; }
  const size = $('#download-size').value;
  startDownload(b.dataset.download,size);
  b.href = `/media/${size}.mp4?download=1&run=${downloadRun.run}`;
  status.textContent = 'Check the file, return here and record whether the app returned normally.';
}));
async function loadDownloadBlob() {
  downloadRun.phase = 'loading'; saveDownload();
  try {
    const response = await request(`/media/${downloadRun.size}.mp4?download=1&run=${downloadRun.run}`);
    if (!response.ok) throw new Error(`File load ${response.status}`);
    downloadFile = new File([await response.blob()], `${downloadRun.size}.mp4`, {type:'video/mp4'});
    const canShare = !!navigator.canShare?.({files:[downloadFile]});
    downloadRun.phase = 'loaded'; saveDownload();
    await downloadResult('loaded', {bytes:downloadFile.size,can_share:canShare,pass:canShare});
    $('#download-share').disabled = !canShare;
    status.textContent = 'Loaded. Tap B: Share loaded download, then choose Save to Files or Save Video.';
  } catch (error) {
    downloadRun.phase = 'load_error'; saveDownload();
    await downloadResult('load_error',{pass:false,error:error.message,memory_failure:error.name === 'RangeError'});
  }
}
async function shareDownload() {
  if (!downloadFile) throw new Error('Load variant B first');
  try {
    await navigator.share({files:[downloadFile]});
    await downloadResult('finished',{share_returned:true,saved_file_unverified:true});
  } catch (error) { await downloadResult('share_error',{pass:false,error:error.name}); }
}
async function downloadReturned(returned) {
  if (!downloadRun) throw new Error('Start a download first');
  downloadRun.phase = 'owner_return'; saveDownload();
  await downloadResult('owner_return',{returned_without_relaunch:returned,usable:returned});
}
action('#download-blob', async () => { await startDownload('B',$('#download-size').value); await loadDownloadBlob(); });
action('#download-share', shareDownload);
action('#download-returned', () => downloadReturned(true));
action('#download-relaunch', () => downloadReturned(false));
action('#download-ok', () => downloadResult('owner_file',{pass:true}));
action('#download-fail', () => downloadResult('owner_file',{pass:false}));

action('[data-share-size]', async b => {
  shareSize = b.dataset.shareSize; shareFile = null; $('#share').disabled = true;
  localStorage.setItem('shareSize',shareSize);
  await record('T7',{phase:'load_started',size:shareSize});
  try {
    const start = performance.now(), response = await request(`/media/${shareSize}.mp4`);
    if (!response.ok) throw new Error(`File load ${response.status}`);
    shareFile = new File([await response.blob()], `${shareSize}.mp4`, {type:'video/mp4'});
    const canShare = !!navigator.canShare?.({files:[shareFile]});
    await record('T7', {phase:'loaded',size:shareSize,bytes:shareFile.size,load_ms:performance.now()-start,can_share:canShare,pass:canShare});
    $('#share').disabled = !canShare; status.textContent = 'File loaded. Tap Share loaded video.';
  } catch (error) { await record('T7',{size:shareSize,phase:'load',pass:false,error:error.message}); }
});
action('#share', async () => {
  try { await navigator.share({files:[shareFile],title:'VideoEnhancer spike'});await record('T7',{size:shareSize,phase:'share_sheet_returned',pass:true}); }
  catch(error) { await record('T7',{size:shareSize,phase:'share_sheet',pass:false,error:error.name + ': ' + error.message}); }
});
action('#photos-ok', () => record('T7',{size:shareSize,phase:'saved_to_photos',pass:true}));
action('#photos-fail', () => record('T7',{size:shareSize,phase:'saved_to_photos',pass:false}));
action('#paste', async () => {
  try { $('#url').value = await navigator.clipboard.readText();await record('T8',{phase:'clipboard_api',pass:validURL($('#url').value)}); }
  catch(error) { await record('T8',{phase:'clipboard_api',pass:false,error:error.name}); }
});
function validURL(text) { try { return ['http:','https:'].includes(new URL(text).protocol); } catch { return false; } }
action('#paste-check', () => record('T8',{phase:'manual_paste',pass:validURL($('#url').value)}));
action('#target-missing', () => record('T8',{phase:'share_target',pass:false,reason:'Not offered by iPadOS share sheet'}));
action('#sse', async () => {
  eventSource?.close();sleepStart = undefined;recoveryStart = undefined;
  eventSource = new EventSource('/api/events');
  eventSource.onmessage = async () => {
    if (recoveryStart !== undefined) {
      const ms = performance.now() - recoveryStart;recoveryStart = undefined;
      await record('T9',{pass:true,reconnect_ms:ms,sleep_s:(Date.now()-sleepStart)/1000});
    }
    status.textContent = 'Status connected. Lock for one minute.';
  };
  eventSource.onerror = () => { status.textContent = 'Status disconnected; reconnecting…'; };
  await record('T9',{phase:'started'});
});
document.addEventListener('visibilitychange', () => {
  if (downloadRun) {
    if (document.hidden) downloadRun.hidden_ms = Date.now();
    else if (downloadRun.hidden_ms) {
      downloadRun.background_intervals.push({start_ms:downloadRun.hidden_ms,end_ms:Date.now()});downloadRun.hidden_ms=null;
    }
    saveDownload();
  }
  if (!eventSource) return;
  if (document.hidden) sleepStart = Date.now();
  else if (sleepStart) {
    recoveryStart = performance.now();
    setTimeout(() => { if (recoveryStart !== undefined) { recoveryStart=undefined;record('T9',{pass:false,error:'No SSE event within 20 seconds after resume'}); } },20000);
  }
});
window.addEventListener('online', flush);
navigator.serviceWorker?.addEventListener('message', event => {
  if (event.data.type === 'display-mode') event.ports[0].postMessage(displayMode());
  if (event.data.type === 'unpaired') unpaired();
});
async function init() {
  try {
    if (location.pathname === '/pair/finish') {
      const secret = location.hash.slice(1); history.replaceState(null,'','/pair/finish');
      await post('/api/pair/finish',{secret}); location.replace('/'); return;
    }
    config = await api('/api/config');
    document.querySelectorAll('main > section, main > pre, main > h2').forEach(e => { e.hidden = false; });
    $('#pairing').hidden = true;
    registration = await navigator.serviceWorker.register('/sw.js');
    await flush(); status.textContent = 'Paired. Ready to test.';
    if (interruptedDownload) {
      downloadRun.phase = 'interrupted'; saveDownload();
      await downloadResult('interrupted',{pass:false,memory_failure:'possible',page_reloaded:true,reason:'Page reloaded during Blob load; memory termination cannot be confirmed by JavaScript'});
      status.textContent = 'Variant B was interrupted during loading (possible memory failure). Record whether relaunch was needed.';
    }
    const query = new URLSearchParams(location.search);
    if (['shared_url','shared_text','shared_title'].some(k => query.has(k))) {
      $('#url').value = query.get('shared_url') || query.get('shared_text') || '';
      history.replaceState(null,'','/');
      await record('T8',{phase:'share_target',pass:validURL($('#url').value)});
    }
  } catch(error) { if ($('#pairing').hidden) status.textContent = `Setup: ${error.message}`; }
}
init();

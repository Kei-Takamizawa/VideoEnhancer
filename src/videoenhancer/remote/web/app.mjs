import {
  downloadProgress, formatDuration, formatSize, pairingScreen,
  shareFile, storageSegments, storageText,
} from './logic.mjs';

const main = document.querySelector('#main');
const tabs = document.querySelector('#tabs');
const sheet = document.querySelector('#delete-sheet');
const offlineMessage = "Can't reach the PC. Check that it is on and on the same Wi-Fi.";
let session;
let activeTab = 'library';
let releaseDownload = () => {};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function button(text, action, className) {
  const node = element('button', text, className);
  node.type = 'button';
  node.onclick = action;
  return node;
}

function clearView() {
  releaseDownload();
  releaseDownload = () => {};
  const video = main.querySelector('video');
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
  main.replaceChildren();
  main.setAttribute('aria-busy', 'false');
}

async function response(path, options = {}) {
  let result;
  try {
    result = await fetch(path, {credentials: 'same-origin', cache: 'no-store', ...options});
  } catch {
    throw new Error(offlineMessage);
  }
  if (!result.ok) {
    let message = 'The request could not be completed. Try again.';
    try {
      const body = await result.json();
      message = body.error || body.message || message;
    } catch { /* A disconnected PC can return an incomplete response. */ }
    const error = new Error(message);
    error.status = result.status;
    throw error;
  }
  return result;
}

async function api(path, options) {
  return (await response(path, options)).json();
}

function showFailure(error, retry, container = main) {
  const section = element('div');
  const sentence = element('p', error.message || offlineMessage, 'error');
  sentence.setAttribute('role', 'alert');
  section.append(sentence, button('Retry', retry));
  container.append(section);
}

function pairingView() {
  clearView();
  tabs.hidden = true;
  const standalone = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
  const state = pairingScreen(session, standalone);
  const panel = element('section', undefined, 'pairing');
  panel.append(element('h1', 'Pair your iPad'));
  const steps = element('ol');
  for (const text of [
    "On the PC, run ‘VideoEnhancer - Redo pairing’, then open the setup address in Safari.",
    'Install the VideoEnhancer CA profile. In Settings, open General → VPN & Device Management → Downloaded Profile → Install.',
    'In Settings, open General → About → Certificate Trust Settings and enable full trust for VideoEnhancer Local CA.',
    'Open the HTTPS app address in Safari. Tap Share → Add to Home Screen, keep “Open as Web App” on, then tap Add.',
    'Open VideoEnhancer from the Home Screen and tap Pair this iPad.',
  ]) steps.append(element('li', text));
  panel.append(steps);
  if (state === 'claim') {
    const claim = button('Pair this iPad', async () => {
      claim.disabled = true;
      panel.querySelector('.error')?.remove();
      try {
        await api('/api/pair/claim', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
        await boot();
      } catch (error) {
        panel.append(element('p', error.message, 'error'));
        claim.disabled = false;
      }
    }, 'primary');
    panel.append(claim);
  } else {
    panel.append(element('p', state === 'closed'
      ? "Run ‘VideoEnhancer - Redo pairing’ on the PC to open a two-minute pairing window."
      : 'Open this app from the Home Screen to pair this iPad.', 'muted'));
    panel.append(button('Retry', boot));
  }
  main.append(panel);
}

function setTab(name) {
  activeTab = name;
  for (const tab of tabs.querySelectorAll('.tab')) {
    const active = tab.id === `${name}-tab`;
    tab.classList.toggle('active', active);
    if (active) tab.setAttribute('aria-current', 'page');
    else tab.removeAttribute('aria-current');
  }
}

function renderStorage(data) {
  const section = element('section', undefined, 'storage');
  const bar = element('div', undefined, 'storage-bar');
  bar.setAttribute('role', 'img');
  bar.setAttribute('aria-label', storageText(data));
  storageSegments(data).forEach((width, index) => {
    const segment = element('span', undefined, ['storage-library', 'storage-other', 'storage-free'][index]);
    segment.style.width = `${width}%`;
    bar.append(segment);
  });
  section.append(bar, element('p', storageText(data), 'storage-label'));
  return section;
}

function itemMetadata(item) {
  return [formatDuration(item.duration), item.width && item.height ? `${item.width} × ${item.height}` : '',
    item.codec ? item.codec.toUpperCase() : '', formatSize(item.size)].filter(Boolean).join(' · ');
}

async function libraryView() {
  clearView();
  setTab('library');
  main.append(element('h1', 'Library'));
  const content = element('div');
  main.append(content);
  main.setAttribute('aria-busy', 'true');
  try {
    const [library, storage] = await Promise.all([api('/api/library'), api('/api/storage')]);
    if (activeTab !== 'library' || !content.isConnected) return;
    content.append(renderStorage(storage));
    if (!library.items.length) content.append(element('p', 'Your library is empty.', 'muted'));
    const list = element('ul', undefined, 'videos');
    for (const item of library.items) {
      const row = button('', () => itemView(item), 'video-row');
      const label = element('span');
      label.append(element('span', item.name, 'video-name'), element('span', itemMetadata(item), 'metadata'));
      if (item.error) label.append(element('span', "Can't read this video", 'metadata error'));
      const chevron = element('span', '›', 'chevron');
      chevron.setAttribute('aria-hidden', 'true');
      row.append(label, chevron);
      const li = element('li');
      li.append(row);
      list.append(li);
    }
    content.append(list);
  } catch (error) {
    if (content.isConnected) {
      if (error.status === 401) { await boot(); return; }
      showFailure(error, libraryView, content);
    }
  } finally {
    if (content.isConnected) main.setAttribute('aria-busy', 'false');
  }
}

function itemView(item) {
  clearView();
  main.append(button('‹ Library', libraryView, 'back'), element('h1', item.name, 'item-title'),
    element('p', itemMetadata(item), 'muted item-meta'));
  const itemError = element('p', item.error ? "Can't read this video" : '', 'error');
  itemError.setAttribute('role', 'alert');
  const video = element('video');
  video.controls = true;
  video.playsInline = true;
  video.preload = 'metadata';
  video.src = `/api/library/${encodeURIComponent(item.id)}/video`;
  video.addEventListener('error', () => { itemError.textContent = "Can't play this video."; });
  main.append(video, itemError);
  const actions = element('div', undefined, 'actions');
  const progress = element('p', '', 'muted');
  progress.setAttribute('aria-live', 'polite');
  const download = button('Download', () => downloadVideo(item, download, progress), 'primary');
  const deletion = button('Delete', () => confirmDelete(item), 'danger');
  actions.append(download, deletion);
  main.append(actions, progress);
  if (sessionStorage.getItem('ve-loading-video')) {
    sessionStorage.removeItem('ve-loading-video');
    progress.textContent = 'The download was interrupted. This iPad may not have enough memory for this video.';
  }
}

async function downloadVideo(item, download, progress) {
  if (typeof navigator.share !== 'function') {
    progress.textContent = 'File sharing is unavailable on this iPad.';
    return;
  }
  const abort = new AbortController();
  let file;
  let reader;
  releaseDownload = () => {
    abort.abort();
    file = undefined;
    reader?.cancel().catch(() => {});
    sessionStorage.removeItem('ve-loading-video');
  };
  download.disabled = true;
  progress.textContent = downloadProgress(0, item.size);
  sessionStorage.setItem('ve-loading-video', '1');
  try {
    const result = await response(`/api/library/${encodeURIComponent(item.id)}/video`, {signal: abort.signal});
    const type = result.headers.get('Content-Type') || 'video/mp4';
    const total = Number(result.headers.get('Content-Length')) || item.size;
    reader = result.body.getReader();
    let chunks = [];
    let loaded = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      chunks.push(value);
      loaded += value.byteLength;
      progress.textContent = downloadProgress(loaded, total);
    }
    const extension = type.split(';')[0] === 'video/quicktime' ? '.mov' : '.mp4';
    file = new File(chunks, item.filename || `${item.name}${extension}`, {type});
    chunks = [];
    sessionStorage.removeItem('ve-loading-video');
    // iPadOS requires a fresh tap after a long fetch to activate the share sheet.
    download.textContent = 'Save video';
    download.disabled = false;
    download.onclick = async () => {
      if (!file) return;
      download.disabled = true;
      try {
        const outcome = await shareFile(file);
        progress.textContent = outcome === 'cancelled' ? '' : 'Video shared.';
      } catch (error) {
        progress.textContent = error.name === 'RangeError'
          ? 'This iPad does not have enough memory to share this video.'
          : 'This video could not be shared. Try again.';
      } finally {
        file = undefined;
        download.remove();
        const retry = button('Download', () => downloadVideo(item, retry, progress), 'primary');
        main.querySelector('.actions')?.prepend(retry);
      }
    };
    progress.textContent = 'Ready. Tap Save video, then choose Save Video or Save to Files.';
  } catch (error) {
    if (abort.signal.aborted) return;
    file = undefined;
    progress.textContent = error.name === 'RangeError'
      ? 'This iPad does not have enough memory to download this video.' : error.message || offlineMessage;
    download.disabled = false;
    sessionStorage.removeItem('ve-loading-video');
  }
}

function confirmDelete(item) {
  document.querySelector('#delete-description').textContent = `${item.name} · ${formatSize(item.size)}`;
  document.querySelector('#delete-error').textContent = '';
  document.querySelector('#confirm-delete').disabled = false;
  sheet.showModal();
  document.querySelector('#cancel-delete').focus();
  document.querySelector('#confirm-delete').onclick = async event => {
    event.preventDefault();
    const confirm = event.currentTarget;
    confirm.disabled = true;
    try {
      await api(`/api/library/${encodeURIComponent(item.id)}`, {method: 'DELETE'});
      sheet.close();
      await libraryView();
    } catch (error) {
      document.querySelector('#delete-error').textContent = error.message;
      confirm.disabled = false;
    }
  };
}

function settingsView() {
  clearView();
  setTab('settings');
  main.append(element('h1', 'Settings'));
  const details = element('dl');
  const date = value => value ? new Date(value).toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric'}) : 'Unknown';
  for (const [name, value] of [
    ['PC name', session.pc_name], ['PC address', (session.addresses || []).join('\n')],
    ['Certificate expires', date(session.cert_expires)],
    ['Pairing', `This iPad is paired since ${date(session.paired_at)}`],
    ['App version', session.version || '0.1.0'],
  ]) {
    const row = element('div');
    row.append(element('dt', name), element('dd', value));
    details.append(row);
  }
  main.append(details);
}

async function boot() {
  clearView();
  main.setAttribute('aria-busy', 'true');
  try {
    session = await api('/api/session');
    if (!session.paired) pairingView();
    else {
      tabs.hidden = false;
      document.querySelector('#connection').textContent = session.pc_name || '';
      await libraryView();
    }
  } catch (error) {
    tabs.hidden = true;
    showFailure(error, boot);
  } finally {
    main.setAttribute('aria-busy', 'false');
  }
}

document.querySelector('#library-tab').addEventListener('click', libraryView);
document.querySelector('#settings-tab').addEventListener('click', settingsView);
window.addEventListener('pagehide', () => releaseDownload());
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
boot();

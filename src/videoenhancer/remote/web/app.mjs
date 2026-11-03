import {platform, downloadMode, pushFailure} from './platform.mjs';
import {mountPlayer} from './player.mjs';
import {mountAdd} from './add-ui.mjs';
import {mountPairing} from './pairing-ui.mjs';
import {
  downloadProgress, formatDuration, formatSize, pairingScreen,
  shareFile, storageSegments, storageText, loadFile, safariURL, safariInstructions,
} from './logic.mjs';

const main = document.querySelector('#main');
const tabs = document.querySelector('#tabs');
const sheet = document.querySelector('#delete-sheet');
const offlineMessage = "Can't reach the PC. Check that it is on and on the same Wi-Fi.";
let session;
let activeTab = 'library';
let releaseDownload = () => {};
let addedBanner = false;
let libraryPanel, libraryScroll = 0, libraryRequest = 0;
let storageData;

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
  main.querySelector('.player')?.dispose();
  const video = main.querySelector('video');
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
  if (libraryPanel?.parentElement === main) libraryScroll = window.scrollY;
  main.replaceChildren();
  main.setAttribute('aria-busy', 'false');
}

async function response(path, options = {}) {
  let result;
  try {
    result = await fetch(path, {credentials: 'same-origin', cache: 'no-store', ...options});
  } catch (cause) {
    const error = new Error(offlineMessage);
    error.name = cause.name || 'Error';
    throw error;
  }
  if (!result.ok) {
    let message = 'The request could not be completed. Try again.';
    try {
      const body = await result.json();
      message = body.error?.message || body.error || body.message || message;
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

function clientEvent(kind, error, item, phase, canShare = null) {
  // Never transmit browser messages containing a video name or a URL.
  const safe = new Set(['', 'Failed to fetch', 'Load failed', 'The operation is not allowed.',
    'File sharing is unavailable on this device.']);
  const message = safe.has(error?.message || '') ? error?.message || '' : 'Browser operation failed.';
  void api('/api/client-event', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({kind, error_name: error?.name || '', error_message: message,
      size_bytes: item.size, can_share: canShare, phase})}).catch(() => {});
}

function errorDetail(error, progress) {
  progress.parentElement?.querySelector('.error-name')?.remove();
  const name = element('small', error.name || 'Error', 'muted error-name');
  progress.after(name);
}

function safariOption(item, progress) {
  const actions = main.querySelector('.actions');
  if (!actions || actions.querySelector('.safari-save')) return;
  const save = button('Save to Files with Safari', async () => {
    save.disabled = true;
    try {
      const {url} = await api(`/api/library/${encodeURIComponent(item.id)}/download-link`, {method: 'POST'});
      if (!progress.isConnected) return;
      main.querySelector('.safari-link')?.remove();
      const manual = element('div', undefined, 'safari-link');
      const link = element('a', url);
      link.href = safariURL(url);
      const copy = button('Copy link', async () => {
        try {
          await navigator.clipboard.writeText(url);
          copy.textContent = 'Copied';
        } catch {
          progress.textContent = 'Select and copy the link below.';
        }
      });
      manual.append(element('p', safariInstructions), link, copy);
      progress.after(manual);
      // This scheme asks iPadOS to open Safari. Keep manual copying available regardless.
      window.location.href = safariURL(url);
    } catch (error) {
      clientEvent('load_failure', error, item, 'load');
      progress.textContent = error.message;
      errorDetail(error, progress);
    } finally {
      save.disabled = false;
    }
  }, 'primary safari-save');
  actions.prepend(save);
}

function pairingView() {
  clearView();
  tabs.hidden = true;
  const standalone = navigator.standalone === true || matchMedia('(display-mode: standalone)').matches;
  const state = pairingScreen(session, standalone || platform() === 'mac');
  const panel = element('section', undefined, 'pairing');
  panel.append(element('h1', 'Pair your device'));
  if (platform() === 'mac') panel.append(element('p', 'Install the CA profile from the setup page, then open HTTPS in Safari or Chrome. Open pairing from a paired device or the PC. Optional in Safari: File > Add to Dock.'));
  const steps = element('ol');
  for (const text of (platform() === 'mac' ? [] : [
    "Open Settings > Add a new device on a paired device, or run ‘VideoEnhancer - Redo pairing’ on the PC, then open the setup address in Safari.",
    'Install the VideoEnhancer CA profile. In Settings, open General → VPN & Device Management → Downloaded Profile → Install.',
    'In Settings, open General → About → Certificate Trust Settings and enable full trust for VideoEnhancer Local CA.',
    'Open the HTTPS app address in Safari. Tap Share → Add to Home Screen, keep “Open as Web App” on, then tap Add.',
    'Open VideoEnhancer from the Home Screen and tap Pair this device.',
  ])) steps.append(element('li', text));
  panel.append(steps);
  panel.append(element('p', "When you are ready to pair, select Settings > Add a new device on a paired device, or click 'VideoEnhancer - Redo pairing' on the PC, then tap Pair this device within 2 minutes.", 'muted'));
  if (state === 'claim') {
    const claim = button('Pair this device', async () => {
      claim.disabled = true;
      panel.querySelector('.error')?.remove();
      try {
        await api('/api/pair/claim', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({platform: platform()})});
        await boot();
      } catch (error) {
        panel.append(element('p', error.message, 'error'));
        claim.disabled = false;
      }
    }, 'primary');
    panel.append(claim);
  } else {
    if (state !== 'closed') panel.append(element('p', 'Open this app from the Home Screen to pair this device.', 'muted'));
  }
  panel.append(button('Try again', boot));
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
  const request = ++libraryRequest;
  const returning = !!libraryPanel;
  clearView();
  setTab('library');
  if (!libraryPanel) {
    libraryPanel = element('section');
    libraryPanel.append(element('h1', 'Library'));
    libraryPanel.append(element('div', undefined, 'running-jobs'), element('ul', undefined, 'videos'));
  }
  main.append(libraryPanel);
  if (returning) window.scrollTo(0, libraryScroll);
  main.setAttribute('aria-busy', String(!returning));
  try {
    const library = await api('/api/library');
    if (request !== libraryRequest || activeTab !== 'library' || !libraryPanel.isConnected) return;
    libraryPanel.querySelector('.library-error')?.remove();
    if (addedBanner) {
      const banner = element('p', "Added. You'll get a notification when it's ready.");
      banner.setAttribute('role', 'status'); libraryPanel.prepend(banner); addedBanner = false;
    }
    if (!session.notifications_on && !libraryPanel.querySelector('.notification-card')) libraryPanel.prepend(notificationCard());
    void activeJobs(libraryPanel.querySelector('.running-jobs'));
    const requested = /^#item=([A-Za-z0-9_-]{1,128})$/.exec(location.hash);
    const list = libraryPanel.querySelector('.videos');
    const existing = new Map([...list.children].map(node => [node.dataset.id, node]));
    const ids = new Set(library.items.map(item => item.id));
    for (const node of [...list.children]) if (!ids.has(node.dataset.id)) node.remove();
    library.items.forEach((item, position) => {
      let li = existing.get(item.id);
      if (!li) {
        li = element('li'); li.dataset.id = item.id;
        const row = button('', () => {}, 'video-row');
        const poster = element('img', undefined, 'poster'); poster.alt = ''; poster.loading = 'lazy';
        poster.src = `/api/library/${encodeURIComponent(item.id)}/poster.jpg`;
        poster.onerror = () => { poster.style.visibility = 'hidden'; };
        const box = element('div', undefined, 'poster-box'); box.append(poster); row.append(box); li.append(row);
      }
      if (JSON.stringify(li.libraryItem) !== JSON.stringify(item)) {
        li.libraryItem = item;
        const row = li.firstElementChild;
        row.onclick = () => itemView(item);
        row.setAttribute('aria-label', `${item.name}, ${formatDuration(item.duration)}`);
        row.title = platform() === 'mac' ? item.name : '';
      }
      if (list.children[position] !== li) list.insertBefore(li, list.children[position] || null);
    });
    libraryPanel.querySelector('.empty-library')?.remove();
    if (!library.items.length) libraryPanel.append(element('p', 'Your library is empty.', 'muted empty-library'));
    if (requested) {
      const item = library.items.find(value => value.id === requested[1]);
      if (item) itemView(item);
    }
  } catch (error) {
    if (request === libraryRequest && libraryPanel.isConnected) {
      if (error.status === 401) { libraryPanel = undefined; await boot(); return; }
      libraryPanel.querySelector('.library-error')?.remove();
      const failure = element('div', undefined, 'library-error'); libraryPanel.append(failure);
      showFailure(error, libraryView, failure);
    }
  } finally {
    if (request === libraryRequest && libraryPanel?.isConnected) main.setAttribute('aria-busy', 'false');
  }
}

function openLibrary() {
  if (location.hash) history.pushState(null, '', '/');
  void libraryView();
}

function itemView(item) {
  libraryRequest++;
  if (location.hash !== `#item=${item.id}`) history.pushState(null, '', `#item=${item.id}`);
  clearView();
  main.append(button('‹ Library', openLibrary, 'back'), element('h1', item.name, 'item-title'),
    element('p', itemMetadata(item), 'muted item-meta'));
  const itemError = element('p', item.error ? "Can't read this video" : '', 'error');
  itemError.setAttribute('role', 'alert');
  const video = element('video');
  video.controls = true;
  video.playsInline = true;
  video.preload = 'metadata';
  video.src = `/api/library/${encodeURIComponent(item.id)}/video`;
  video.addEventListener('error', () => {
    itemError.textContent = "Can't play this video.";
    const error = {name: 'MediaError', message: video.error?.message || ''};
    clientEvent('load_failure', error, item, 'playback');
    errorDetail(error, itemError);
  });
  main.append(mountPlayer(video, item, {element, backToLibrary: openLibrary}), itemError);
  const actions = element('div', undefined, 'actions');
  const progress = element('p', '', 'muted');
  progress.setAttribute('aria-live', 'polite');
  const download = button('Download', () => downloadVideo(item, download, progress), 'primary');
  const deletion = button('Delete', () => confirmDelete(item), 'danger');
  if (downloadMode(platform(), item.size, session.share_limit_bytes) !== 'safari') actions.append(download);
  actions.append(deletion);
  main.append(actions, progress);
  if (downloadMode(platform(), item.size, session.share_limit_bytes) === 'safari') safariOption(item, progress);
  if (sessionStorage.getItem('ve-loading-video')) {
    sessionStorage.removeItem('ve-loading-video');
    progress.textContent = 'The download was interrupted. This device may not have enough memory for this video.';
  }
}

async function downloadVideo(item, download, progress) {
  if (platform() === 'mac') {
    download.disabled = true;
    try {
      const {url} = await api(`/api/library/${encodeURIComponent(item.id)}/download-link`, {method: 'POST'});
      const link = element('a'); link.href = url; link.download = item.filename || ''; main.append(link); link.click(); link.remove();
    } catch (error) { progress.textContent = error.message; }
    finally { download.disabled = false; }
    return;
  }
  if (typeof navigator.share !== 'function') {
    progress.textContent = 'File sharing is unavailable on this device.';
    const error = new Error(progress.textContent);
    clientEvent('share_failure', error, item, 'share', false);
    errorDetail(error, progress);
    safariOption(item, progress);
    return;
  }
  const abort = new AbortController();
  let file;
  releaseDownload = () => {
    abort.abort();
    file = undefined;
    sessionStorage.removeItem('ve-loading-video');
  };
  download.disabled = true;
  progress.textContent = downloadProgress(0, item.size);
  sessionStorage.setItem('ve-loading-video', '1');
  try {
    const result = await response(`/api/library/${encodeURIComponent(item.id)}/video`, {signal: abort.signal});
    const type = result.headers.get('Content-Type') || 'video/mp4';
    const total = Number(result.headers.get('Content-Length')) || item.size;
    const extension = type.split(';')[0] === 'video/quicktime' ? '.mov' : '.mp4';
    file = await loadFile(result, item.filename || `${item.name}${extension}`,
      loaded => { progress.textContent = downloadProgress(loaded, total); });
    if (abort.signal.aborted) { file = undefined; return; }
    sessionStorage.removeItem('ve-loading-video');
    // iPadOS requires a fresh tap after a long fetch to activate the share sheet.
    download.textContent = 'Save video';
    download.disabled = false;
    download.onclick = async () => {
      if (!file) return;
      download.disabled = true;
      let canShare = null;
      try {
        const outcome = await shareFile(file, navigator, result => {
          canShare = result;
          clientEvent('share_check', null, item, 'share', result);
        });
        progress.textContent = outcome === 'cancelled' ? '' : 'Video shared.';
      } catch (error) {
        clientEvent('share_failure', error, item, 'share', canShare);
        progress.textContent = 'This video is too large to share directly.';
        errorDetail(error, progress);
        safariOption(item, progress);
      } finally {
        file = undefined;
        download.remove();
        const retry = button('Download', () => downloadVideo(item, retry, progress), 'primary');
        if (progress.isConnected) main.querySelector('.actions')?.prepend(retry);
      }
    };
    progress.textContent = 'Ready. Tap Save video, then choose Save Video or Save to Files.';
  } catch (error) {
    if (abort.signal.aborted) return;
    clientEvent('load_failure', error, item, 'load');
    file = undefined;
    progress.textContent = error.name === 'RangeError'
      ? 'This device does not have enough memory to download this video.' : error.message || offlineMessage;
    download.disabled = false;
    sessionStorage.removeItem('ve-loading-video');
    errorDetail(error, progress);
    safariOption(item, progress);
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
  const storage = element('div'); main.append(storage);
  if (storageData) storage.append(renderStorage(storageData));
  void api('/api/storage').then(data => { storageData = data; storage.replaceChildren(renderStorage(data)); }).catch(error => showFailure(error, settingsView, storage));
  const details = element('dl');
  const date = value => value ? new Date(value).toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric'}) : 'Unknown';
  for (const [name, value] of [
    ['PC name', session.pc_name], ['PC address', (session.addresses || []).join('\n')],
    ['Certificate expires', date(session.cert_expires)],
    ['Pairing', `This device is paired since ${date(session.paired_at)}`],
    ['App version', session.version || '0.1.0'],
  ]) {
    const row = element('div');
    row.append(element('dt', name), element('dd', value));
    details.append(row);
  }
  main.append(details);
  const devices = element('section'); devices.append(element('h2', 'Paired devices'));
  const refreshDevices = () => {
    devices.replaceChildren(element('h2', 'Paired devices'));
    for (const device of session.devices || []) devices.append(element('p', `${device.label} · Paired ${date(device.created)}`));
  };
  refreshDevices();
  main.append(devices);
  mountPairing({container: main, element, button, api, session, update: next => { session = next; refreshDevices(); }});
  const notifications = element('section', undefined, 'add-card');
  notifications.append(element('h2', 'Notifications'), element('p', session.notifications_on ? 'Notifications are on for this device.' : 'Notifications are off for this device.'));
  if (session.notifications_on) {
    const status = element('p', '', 'muted'); status.setAttribute('role', 'status');
    const send = button('Send a test notification', async () => {
      send.disabled = true;
      try {
        const result = await api('/api/push/test', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
        status.textContent = result.ok ? 'Test notification sent.' : 'The notification could not be sent. Turn notifications on again from the Library tab.';
        if ([404, 410].includes(result.status)) session.notifications_on = false;
      } catch (error) { status.textContent = error.message; }
      finally { send.disabled = false; }
    });
    notifications.append(send, status);
  } else notifications.append(notificationCard());
  main.append(notifications);
}


function notificationCard() {
  const card = element('section', undefined, 'notification-card');
  card.append(element('p', 'Get a notification when a video is ready.'));
  const status = element('p', '', 'muted'); status.setAttribute('role', 'status');
  const enable = button('Turn on notifications', async () => {
    enable.disabled = true;
    try {
      if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) throw new Error(platform() === 'mac' ? 'Notifications are unavailable in this browser.' : 'Open this app from the Home Screen to turn on notifications.');
      // This call must happen during the tap, before waiting for the service worker.
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Notifications are off. Allow notifications in browser or device settings, then try again.');
      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        const value = session.push_key;
        const key = Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)), c => c.charCodeAt(0));
        subscription = await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: key});
      }
      await api('/api/push/subscribe', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(subscription.toJSON())});
      session.notifications_on = true; card.remove();
      if (activeTab === 'settings') settingsView();
    } catch (error) { status.textContent = await pushFailure(error); enable.disabled = false; }
  }, 'primary');
  card.append(enable, status); return card;
}

async function activeJobs(container) {
  clearTimeout(container.pollTimer);
  try {
    const {jobs} = await api('/api/jobs/active');
    if (!container.isConnected) return;
    container.replaceChildren();
    if (jobs?.length) {
      container.append(element('p', `${jobs.length} ${jobs.length === 1 ? 'video' : 'videos'} in progress`, 'muted'));
    }
  } catch (error) { if (container.isConnected) container.replaceChildren(element('p', error.message, 'error')); }
  if (container.isConnected) container.pollTimer = setTimeout(() => { if (container.isConnected) void activeJobs(container); }, 15000);
}

function addView() {
  clearView(); setTab('add'); main.append(element('h1', 'Add'));
  mountAdd({main, element, button, api, added: async () => { addedBanner = true; await libraryView(); }});
}

async function boot() {
  clearView();
  main.setAttribute('aria-busy', 'true');
  try {
    session = await api('/api/session');
    if (!session.paired) pairingView();
    else {
      tabs.hidden = false;
      await libraryView();
    }
  } catch (error) {
    tabs.hidden = true;
    showFailure(error, boot);
  } finally {
    main.setAttribute('aria-busy', 'false');
  }
}

document.querySelector('#library-tab').addEventListener('click', openLibrary);
document.querySelector('#settings-tab').addEventListener('click', settingsView);
document.querySelector('#add-tab').addEventListener('click', addView);
window.addEventListener('hashchange', () => { if (session?.paired) void libraryView(); });
window.addEventListener('pagehide', () => releaseDownload());
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
boot();

import {mountAdd} from './add-ui.mjs';
import {finishText} from './add.mjs';
import {
  downloadProgress, formatDuration, formatSize, pairingScreen,
  shareFile, storageSegments, storageText, loadFile, needsSafari, safariURL, safariInstructions,
} from './logic.mjs';

const main = document.querySelector('#main');
const tabs = document.querySelector('#tabs');
const sheet = document.querySelector('#delete-sheet');
const offlineMessage = "Can't reach the PC. Check that it is on and on the same Wi-Fi.";
let session;
let activeTab = 'library';
let releaseDownload = () => {};
let addedBanner = false;

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
    'File sharing is unavailable on this iPad.']);
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
  panel.append(element('p', "When you are ready to pair, click 'VideoEnhancer - Redo pairing' on the PC, then tap Pair this iPad within 2 minutes.", 'muted'));
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
    if (state !== 'closed') panel.append(element('p', 'Open this app from the Home Screen to pair this iPad.', 'muted'));
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
    if (addedBanner) {
      const banner = element('p', "Added. You'll get a notification when it's ready.");
      banner.setAttribute('role', 'status'); content.append(banner); addedBanner = false;
    }
    if (!session.notifications_on) content.append(notificationCard());
    const running = element('div', undefined, 'running-jobs'); content.append(running);
    void activeJobs(running);
    const requested = /^#item=([A-Za-z0-9_-]{1,128})$/.exec(location.hash);
    if (requested) {
      const item = library.items.find(value => value.id === requested[1]);
      history.replaceState(null, '', '/');
      if (item) { itemView(item); return; }
    }
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
  video.addEventListener('error', () => {
    itemError.textContent = "Can't play this video.";
    const error = {name: 'MediaError', message: video.error?.message || ''};
    clientEvent('load_failure', error, item, 'playback');
    errorDetail(error, itemError);
  });
  main.append(video, itemError);
  const actions = element('div', undefined, 'actions');
  const progress = element('p', '', 'muted');
  progress.setAttribute('aria-live', 'polite');
  const download = button('Download', () => downloadVideo(item, download, progress), 'primary');
  const deletion = button('Delete', () => confirmDelete(item), 'danger');
  if (!needsSafari(item.size, session.share_limit_bytes)) actions.append(download);
  actions.append(deletion);
  main.append(actions, progress);
  if (needsSafari(item.size, session.share_limit_bytes)) safariOption(item, progress);
  if (sessionStorage.getItem('ve-loading-video')) {
    sessionStorage.removeItem('ve-loading-video');
    progress.textContent = 'The download was interrupted. This iPad may not have enough memory for this video.';
  }
}

async function downloadVideo(item, download, progress) {
  if (typeof navigator.share !== 'function') {
    progress.textContent = 'File sharing is unavailable on this iPad.';
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
      ? 'This iPad does not have enough memory to download this video.' : error.message || offlineMessage;
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
  const notifications = element('section', undefined, 'add-card');
  notifications.append(element('h2', 'Notifications'), element('p', session.notifications_on ? 'Notifications are on for this iPad.' : 'Notifications are off for this iPad.'));
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
      if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) throw new Error('Open this app from the Home Screen to turn on notifications.');
      // This call must happen during the tap, before waiting for the service worker.
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Notifications are off. Allow notifications in iPad Settings, then try again.');
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
    } catch (error) { status.textContent = error.message; enable.disabled = false; }
  }, 'primary');
  card.append(enable, status); return card;
}

async function activeJobs(container) {
  try {
    const {jobs} = await api('/api/jobs/active');
    if (!container.isConnected) return;
    container.replaceChildren();
    if (jobs?.length) {
      container.append(element('p', `${jobs.length} ${jobs.length === 1 ? 'video' : 'videos'} in progress`, 'muted'));
      for (const job of jobs) {
        const row = element('div', undefined, 'running-row');
        row.append(element('small', `${job.title} ? ${finishText({finish: job.finish, seconds: job.seconds})}`, 'muted'));
        row.append(button('Cancel', async () => {
          if (!window.confirm('Cancel this video? Its source and unfinished files will be deleted.')) return;
          try {
            await api(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
            await libraryView();
          } catch (error) { row.append(element('p', error.message, 'error')); }
        }));
        container.append(row);
      }
    }
  } catch (error) { if (container.isConnected) container.replaceChildren(element('p', error.message, 'error')); }
  if (container.isConnected) setTimeout(() => { if (container.isConnected) void activeJobs(container); }, 15000);
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
document.querySelector('#add-tab').addEventListener('click', addView);
window.addEventListener('hashchange', () => { if (session?.paired && location.hash.startsWith('#item=')) void libraryView(); });
window.addEventListener('pagehide', () => releaseDownload());
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
boot();

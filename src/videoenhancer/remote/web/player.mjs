import {platform, previewTile, previewLeft} from './platform.mjs';
import {formatDuration} from './logic.mjs';

export function mountPlayer(video, item, {element, backToLibrary = () => {}}) {
  const document = video.ownerDocument;
  const mac = platform() === 'mac';
  const container = element('div', undefined, 'player');
  container.setAttribute('aria-label', 'Video player');
  video.controls = false;
  const controls = element('div', undefined, 'player-controls');
  const status = element('span', '', 'player-time'); status.setAttribute('aria-live', 'off');
  const remaining = element('span', '', 'player-time player-remaining');
  const feedback = element('div', undefined, 'player-feedback'); feedback.setAttribute('aria-hidden', 'true');
  let idleTimer, clickTimer, feedbackTimer;
  let lastTouch = false;
  let overBar = false;
  let disposed = false;
  let mouseGesture = false;
  function scheduleHide() {
    clearTimeout(idleTimer);
    if (!video.paused && !overBar && !dragging) idleTimer = setTimeout(() => container.classList.add('controls-hidden'), 2500);
  }
  function reveal() { container.classList.remove('controls-hidden'); scheduleHide(); }
  function icon(node, name) {
    // Original geometric icons; no third-party artwork.
    const shapes = {
      Play: '<path d="M8 5L20 12L8 19Z" fill="currentColor"/>',
      Pause: '<path d="M8 5V19M16 5V19" stroke-width="4"/>',
    };
    node.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">${shapes[name]}</svg>`;
    node.setAttribute('aria-label', name); node.title = name;
  }
  function flash() {
    icon(feedback, video.paused ? 'Pause' : 'Play');
    feedback.classList.add('shown'); clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(() => feedback.classList.remove('shown'), 500);
  }
  const toggle = async () => {
    if (!video.paused) { video.pause(); flash(); return; }
    try { await video.play(); flash(); } catch { status.textContent = "Can't play this video."; }
  };
  const skip = seconds => { if (video.readyState > 0) video.currentTime = Math.max(0, Math.min(duration(), video.currentTime + seconds)); };
  const bar = element('div', undefined, 'seek-wrap');
  const seek = element('input'); seek.type = 'range'; seek.min = 0; seek.max = item.duration || 0; seek.step = .1; seek.value = 0;
  seek.setAttribute('aria-label', 'Seek');
  const preview = element('div', undefined, 'seek-preview'); preview.hidden = true;
  const image = element('div', undefined, 'preview-image'); image.hidden = true;
  const time = element('span'); preview.append(image, time); bar.append(seek, preview);
  let index;
  let dragging = false;
  let hover = false;
  const base = `/api/library/${encodeURIComponent(item.id)}`;
  video.poster = `${base}/poster.jpg`;
  void fetch(`${base}/storyboard.json`, {credentials: 'same-origin'}).then(result => result.ok ? result.json() : null).then(value => {
    if (value && value.interval > 0 && value.width > 0 && value.height > 0 && value.frames > 0) index = value;
  }).catch(() => {});
  const duration = () => Number.isFinite(video.duration) ? video.duration : item.duration || 0;
  function show(seconds, clientX) {
    const rect = container.getBoundingClientRect();
    preview.hidden = false;
    time.textContent = formatDuration(seconds);
    if (index) {
      const tile = previewTile(seconds, index);
      image.hidden = false; image.style.width = `${index.width}px`; image.style.height = `${index.height}px`;
      image.style.backgroundImage = `url("${base}/storyboard/${tile.sheet}.jpg")`;
      image.style.backgroundPosition = `-${tile.x}px -${tile.y}px`;
    }
    const own = bar.getBoundingClientRect();
    preview.style.left = `${previewLeft(clientX - rect.left, rect.width, preview.offsetWidth) - (own.left - rect.left)}px`;
  }
  const at = event => {
    const rect = seek.getBoundingClientRect();
    return Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)) * duration();
  };
  function scrub(event) {
    const seconds = at(event);
    if (dragging) {
      seek.value = seconds;
      if (video.readyState > 0) video.currentTime = seconds;
    }
    show(seconds, event.clientX);
  }
  seek.onpointerdown = event => { dragging = true; reveal(); seek.setPointerCapture(event.pointerId); scrub(event); };
  seek.onpointermove = event => { hover = event.pointerType === 'mouse'; if (dragging || hover) scrub(event); };
  seek.onpointerup = event => { if (dragging) scrub(event); dragging = false; preview.hidden = !hover; reveal(); };
  seek.onpointercancel = () => { dragging = false; preview.hidden = true; reveal(); };
  seek.onpointerleave = () => { hover = false; if (!dragging) preview.hidden = true; };
  seek.oninput = () => { if (video.readyState > 0) video.currentTime = Number(seek.value); };
  function update() {
    seek.max = duration();
    if (!dragging) seek.value = video.currentTime;
    seek.style.setProperty('--played', `${duration() ? video.currentTime / duration() * 100 : 0}%`);
    status.textContent = formatDuration(video.currentTime);
    remaining.textContent = `-${formatDuration(Math.max(0, duration() - video.currentTime))}`;
  }
  for (const name of ['loadedmetadata', 'durationchange', 'timeupdate', 'play', 'pause', 'ended']) video.addEventListener(name, update);
  controls.append(status, bar, remaining);
  const fullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (mac && container.requestFullscreen) await container.requestFullscreen();
      else if (video.webkitDisplayingFullscreen && video.webkitExitFullscreen) video.webkitExitFullscreen();
      else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
      else if (container.requestFullscreen) await container.requestFullscreen();
    } catch { status.textContent = 'Full screen is unavailable.'; }
  };
  container.append(video, controls, feedback); update();
  const playback = () => {reveal(); update();};
  video.addEventListener('play', playback); video.addEventListener('pause', playback);
  container.addEventListener('pointermove', reveal);
  for (const panel of [controls]) {
    panel.addEventListener('pointerenter', () => {overBar = true; reveal();});
    panel.addEventListener('pointerleave', () => {overBar = false; reveal();});
    panel.addEventListener('pointerup', event => event.stopPropagation());
    panel.addEventListener('dblclick', event => event.stopPropagation());
    panel.addEventListener('focusin', reveal);
  }
  container.addEventListener('pointerup', event => {
    if (event.button > 0 || event.target !== video && event.target !== container) return;
    mouseGesture = event.pointerType === 'mouse';
    if (!mouseGesture) {
      const wasHidden = container.classList.contains('controls-hidden');
      reveal();
      if (clickTimer && lastTouch) {
        clearTimeout(clickTimer); clickTimer = undefined; lastTouch = false;
        void fullscreen();
      } else {
        lastTouch = true;
        clickTimer = setTimeout(() => {
          clickTimer = undefined; lastTouch = false;
          if (!wasHidden) void toggle();
        }, 250);
      }
    } else {
      reveal();
      if (clickTimer) {clearTimeout(clickTimer); clickTimer = undefined;}
      else clickTimer = setTimeout(() => {clickTimer = undefined; void toggle();}, 250);
    }
  });
  container.addEventListener('dblclick', event => {
    if (!mouseGesture || event.target !== video && event.target !== container) return;
    clearTimeout(clickTimer); clickTimer = undefined; void fullscreen(); reveal();
  });
  function keydown(event) {
    if (disposed || !container.isConnected || document.querySelector('dialog[open]')) return;
    reveal();
    if (event.altKey || event.ctrlKey || event.metaKey || event.isComposing) return;
    if (event.target.closest?.('input:not([type=range]), textarea, select, [contenteditable]:not([contenteditable="false"])')) return;
    let handled = true;
    switch (event.code) {
      case 'Space': case 'KeyK': void toggle(); break;
      case 'ArrowLeft': skip(event.shiftKey ? -30 : -5); break;
      case 'ArrowRight': skip(event.shiftKey ? 30 : 5); break;
      case 'ArrowUp': case 'ArrowDown':
        if (!mac) {handled = false; break;}
        video.volume = Math.max(0, Math.min(1, video.volume + (event.code === 'ArrowUp' ? .1 : -.1)));
        break;
      case 'KeyM': video.muted = !video.muted; break;
      case 'KeyF': void fullscreen(); break;
      case 'Escape':
        if (document.fullscreenElement) void document.exitFullscreen();
        else if (video.webkitDisplayingFullscreen && video.webkitExitFullscreen) video.webkitExitFullscreen();
        else if (mac) backToLibrary();
        else handled = false;
        break;
      case 'Backspace':
        if (mac && !document.fullscreenElement && !video.webkitDisplayingFullscreen) backToLibrary();
        else handled = false;
        break;
      default: handled = false;
    }
    if (handled) {event.preventDefault(); update();}
  }
  document.addEventListener('keydown', keydown);
  container.dispose = () => {
    disposed = true;
    document.removeEventListener('keydown', keydown);
    clearTimeout(idleTimer); clearTimeout(clickTimer); clearTimeout(feedbackTimer);
    video.removeEventListener('play', playback); video.removeEventListener('pause', playback);
    for (const name of ['loadedmetadata', 'durationchange', 'timeupdate', 'play', 'pause', 'ended']) video.removeEventListener(name, update);
  };
  return container;
}

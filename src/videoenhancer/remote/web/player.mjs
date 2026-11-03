import {platform, previewTile, previewLeft} from './platform.mjs';
import {formatDuration} from './logic.mjs';

export function mountPlayer(video, item, {element, button}) {
  const mac = platform() === 'mac';
  const container = element('div', undefined, 'player'); container.tabIndex = 0;
  container.setAttribute('aria-label', 'Video player');
  video.controls = false;
  const controls = element('div', undefined, 'player-controls');
  const status = element('span', '', 'player-time'); status.setAttribute('aria-live', 'off');
  const toggle = async () => {
    if (!video.paused) { video.pause(); return; }
    try { await video.play(); } catch { status.textContent = "Can't play this video."; }
  };
  const play = button('Play', toggle);
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
  seek.onpointerdown = event => { dragging = true; seek.setPointerCapture(event.pointerId); scrub(event); };
  seek.onpointermove = event => { hover = event.pointerType === 'mouse'; if (dragging || hover) scrub(event); };
  seek.onpointerup = event => { if (dragging) scrub(event); dragging = false; preview.hidden = !hover; };
  seek.onpointercancel = () => { dragging = false; preview.hidden = true; };
  seek.onpointerleave = () => { hover = false; if (!dragging) preview.hidden = true; };
  seek.oninput = () => { if (video.readyState > 0) video.currentTime = Number(seek.value); };
  function update() {
    seek.max = duration();
    if (!dragging) seek.value = video.currentTime;
    play.textContent = video.paused ? 'Play' : 'Pause';
    status.textContent = `${formatDuration(video.currentTime)} / ${formatDuration(duration())}`;
  }
  for (const name of ['loadedmetadata', 'durationchange', 'timeupdate', 'play', 'pause', 'ended']) video.addEventListener(name, update);
  controls.append(play, status, bar);
  if (mac) {
    const volume = element('input'); volume.type = 'range'; volume.min = 0; volume.max = 1; volume.step = .05; volume.value = video.volume;
    volume.className = 'volume'; volume.setAttribute('aria-label', 'Volume');
    volume.oninput = () => { video.volume = Number(volume.value); };
    controls.append(volume);
  }
  const fullscreen = button('Full screen', async () => {
    try {
      if (mac && container.requestFullscreen) {
        if (document.fullscreenElement) await document.exitFullscreen(); else await container.requestFullscreen();
      } else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
      else if (container.requestFullscreen) await container.requestFullscreen();
    } catch { status.textContent = 'Full screen is unavailable.'; }
  });
  controls.append(fullscreen); container.append(video, controls); update();
  container.addEventListener('keydown', event => {
    if (!mac || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.code === 'Space' && event.target.tagName === 'BUTTON') return;
    if (['ArrowLeft', 'ArrowRight'].includes(event.code) && event.target.classList.contains('volume')) return;
    if (event.code === 'Space') { event.preventDefault(); void toggle(); }
    else if (['ArrowLeft', 'ArrowRight'].includes(event.code)) {
      event.preventDefault();
      if (video.readyState > 0) video.currentTime = Math.max(0, Math.min(duration(), video.currentTime + (event.code === 'ArrowLeft' ? -5 : 5)));
    }
  });
  return container;
}

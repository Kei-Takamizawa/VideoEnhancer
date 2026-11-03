export function platform(nav = navigator) {
  if (/iPad/.test(nav.userAgent) || /Macintosh/.test(nav.userAgent) && nav.maxTouchPoints > 1) return 'ipad';
  return /Macintosh|Mac OS X/.test(nav.userAgent) ? 'mac' : 'other';
}

export function previewTile(time, index) {
  const frame = Math.max(0, Math.min(index.frames - 1, Math.floor(time / index.interval)));
  return {sheet: Math.floor(frame / 100), x: frame % 10 * index.width, y: Math.floor(frame % 100 / 10) * index.height};
}

export function previewLeft(pointer, width, previewWidth) {
  return Math.max(0, Math.min(Math.max(0, width - previewWidth), pointer - previewWidth / 2));
}

export function droppedVideo(files) {
  if (files.length !== 1 || !(files[0].type.startsWith('video/') || /\.(mp4|m4v|mov|webm|mkv)$/i.test(files[0].name))) throw new Error('Drop one video file.');
  return files[0];
}

export function downloadMode(kind, size, limit) {
  return kind === 'mac' ? 'attachment' : size > limit ? 'safari' : 'share';
}

export async function pushFailure(error, nav = navigator) {
  let brave = false;
  try { brave = await nav.brave?.isBrave() === true; } catch { /* Detection may be unavailable. */ }
  const hint = brave
    ? 'In Brave, open brave://settings/privacy, turn on Use Google services for push messaging, restart Brave, and try again.'
    : 'Check notification settings in your browser, then try again.';
  return `${error.message || 'Could not turn on notifications.'} ${hint}`;
}

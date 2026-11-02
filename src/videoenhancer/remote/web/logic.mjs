const number = new Intl.NumberFormat('en-US', {maximumFractionDigits: 0});
const decimal = new Intl.NumberFormat('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1});

export function storageSegments({total, free, library_bytes: library}) {
  if (!(total > 0)) return [0, 0, 100];
  const available = Math.min(total, Math.max(0, free));
  const own = Math.min(total - available, Math.max(0, library));
  return [100 * own / total, 100 * (total - available - own) / total, 100 * available / total];
}

export function storageText({total, free, library_bytes: library, drive_label: drive}) {
  return `Library ${decimal.format(library / 1e9)} GB · Free ${decimal.format(free / 1e9)} GB of ${decimal.format(total / 1e9)} GB (${drive})`;
}

export function formatSize(bytes) {
  return bytes >= 1e9 ? `${decimal.format(bytes / 1e9)} GB` : `${decimal.format(bytes / 1e6)} MB`;
}

export function formatDuration(seconds) {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return 'Unknown duration';
  const value = Math.floor(seconds);
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor(value / 60) % 60;
  const rest = String(value % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

export function downloadProgress(loaded, total) {
  const progress = number.format(Math.floor(loaded / 1e6));
  return total > 0 ? `Loading ${progress} of ${number.format(Math.round(total / 1e6))} MB` : `Loading ${progress} MB`;
}

export function pairingScreen(session, standalone) {
  if (session.paired) return 'app';
  if (!session.pairing_open) return 'closed';
  return standalone ? 'claim' : 'install';
}

export const safariInstructions = 'Paste this link into Safari to save the video to Files.';

export function needsSafari(size, limit = 900000000) {
  return size > limit;
}

export function safariURL(url) {
  const target = new URL(url);
  if (target.protocol !== 'https:') throw new Error('An HTTPS download link is required.');
  return `x-safari-https://${target.host}${target.pathname}`;
}

export async function loadFile(response, name, onProgress) {
  // Count a clone without retaining chunks; the final File has exactly one Blob part.
  const reader = response.clone().body?.getReader();
  const counter = (async () => {
    let loaded = 0;
    if (!reader) return;
    try {
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        loaded += value.byteLength;
        onProgress(loaded);
      }
    } finally {
      reader.releaseLock();
    }
  })();
  // Attach rejection handlers immediately: either branch can fail before the other.
  const [blob] = await Promise.all([response.blob(), counter]);
  return new File([blob], name, {type: response.headers.get('Content-Type') || blob.type || 'video/mp4'});
}

export async function shareFile(file, sharing = navigator, onCheck = () => {}) {
  const canShare = typeof sharing.canShare === 'function' ? sharing.canShare({files: [file]}) : null;
  onCheck(canShare);
  if (typeof sharing.share !== 'function' || canShare === false) {
    throw new Error('File sharing is unavailable on this iPad.');
  }
  try {
    await sharing.share({files: [file]});
    return 'shared';
  } catch (error) {
    if (error.name === 'AbortError') return 'cancelled';
    throw error;
  }
}

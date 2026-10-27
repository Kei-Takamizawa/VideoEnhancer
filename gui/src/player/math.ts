export type Transform = { scale: number; x: number; y: number };
export const clamp = (n: number, low: number, high: number) => Math.max(low, Math.min(high, n));
export function zoomAt(current: Transform, factor: number, x: number, y: number): Transform {
  const scale = clamp(current.scale * factor, 1, 8);
  if (scale === 1) return { scale, x: 0, y: 0 };
  const ratio = scale / current.scale;
  const limit = (scale - 1) / 2;
  return { scale, x: clamp(x - (x - current.x) * ratio, -limit, limit), y: clamp(y - (y - current.y) * ratio, -limit, limit) };
}
export function previewLeft(fraction: number, width: number, pictureWidth = 192) {
  return clamp(fraction * width - pictureWidth / 2, 0, Math.max(0, width - pictureWidth));
}
export function timecode(seconds: number) {
  const n = Math.max(0, Math.floor(seconds));
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
}

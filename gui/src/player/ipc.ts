type Event = { version: number; event?: string; reply?: number; error?: string; result?: unknown; [key: string]: unknown };
type WebView = { postMessage(message: string): void; addEventListener(type: "message", handler: (event: MessageEvent<Event>) => void): void };
declare global { interface Window { chrome?: { webview?: WebView } } }
let next = 0;
const pending = new Map<number, { resolve(value: unknown): void; reject(error: Error): void; timer: ReturnType<typeof setTimeout> }>();
const listeners = new Set<(event: Event) => void>();
let installed = false;
export function onPlayerEvent(listener: (event: Event) => void) {
  if (!installed) {
    window.chrome?.webview?.addEventListener("message", ({ data }) => {
      if (data.version !== 1) return;
      if (data.reply !== undefined) {
        const request = pending.get(data.reply);
        if (!request) return;
        pending.delete(data.reply); clearTimeout(request.timer);
        if (data.error) request.reject(new Error(data.error)); else request.resolve(data.result);
      } else listeners.forEach(callback => callback(data));
    });
    installed = true;
  }
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function send(command: { type: string; [key: string]: unknown }): Promise<unknown> {
  const id = ++next;
  return new Promise((resolve, reject) => {
    if (!window.chrome?.webview) { reject(new Error("The player is unavailable.")); return; }
    const timer = setTimeout(() => { pending.delete(id); reject(new Error("The player did not respond. Close it and try again.")); }, 15000);
    pending.set(id, { resolve, reject, timer });
    window.chrome.webview.postMessage(JSON.stringify({ version: 1, id, command }));
  });
}

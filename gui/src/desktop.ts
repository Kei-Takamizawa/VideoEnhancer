import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { Connection, Desktop } from "./types";

const call = <T>(operation: string, args: unknown = null): Promise<T> => invoke<T>("desktop_command", { operation, args }).catch(error => {
  throw error instanceof Error ? error : new Error(String(error));
});
function subscribe<T>(name: string, callback: (value: T) => void): () => void {
  let disposed = false;
  const listener = listen<T>(name, event => callback(event.payload));
  void listener.then(unlisten => { if (disposed) unlisten(); });
  return () => { disposed = true; void listener.then(unlisten => unlisten()); };
}
export const HEVC_STORE = "ms-windows-store://pdp/?ProductId=9NMZLZ57R3T7";
const probeHevc = () => document.createElement("video").canPlayType('video/mp4; codecs="hev1.2.4.L120.90"') !== "";
let startupHevc: boolean | undefined;
export const hevcPlaybackSupported = () => startupHevc ?? probeHevc();
export function installDesktop() {
  if (!isTauri()) return;
  startupHevc = probeHevc();
  const desktop: Desktop = {
    connection: async () => { const value = await call<Connection & {zoom_percent:number}>("connection"); zoom = value.zoom_percent; return value; }, reload: () => call("reload"), restartEngine: () => call("restartEngine"),
    storageStatus: verify => call("storageStatus", !!verify), moveStorage: folder => call("moveStorage", folder), removeOldStorage: () => call("removeOldStorage"),
    logRendererError: details => call("logRendererError", details), files: kind => call("files", kind),
    openFolder: folder => call("openFolder", folder), play: file => call("play", file), reveal: file => call("reveal", file),
    copy: text => call("copy", text), startupStatus: () => call("startupStatus"), hide: () => call("hide"), zoom: percent => call("zoom", percent), theme: theme => call("theme", theme),
    onZoom: callback => subscribe("zoom-changed", callback), onTrayExplanation: callback => subscribe("tray-explanation", callback),
    openExternal: url => call("openExternal", url), sourceLink: id => call("sourceLink", id), onFileDrop: callback => subscribe("native-file-drop", callback),
  };
  window.desktop = desktop;
  let playerOpen: boolean | undefined;
  const updateMemoryTarget = () => {
    const open = !!document.querySelector("video,.compare");
    if (open === playerOpen) return;
    playerOpen = open;
    // Unsupported older runtimes retain their normal memory target.
    void call("memoryTarget", !open).catch(() => {});
  };
  new MutationObserver(updateMemoryTarget).observe(document.documentElement, { childList: true, subtree: true });
  updateMemoryTarget();
  let zoom = 100;
  desktop.onZoom(value => { zoom = value; });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => { /* The browser may already be leaving fullscreen. */ });
      void call("fullscreen", false);
    }
    if (!event.ctrlKey || event.altKey || event.metaKey) return;
    const plus = ["+", "="].includes(event.key) || event.code === "NumpadAdd";
    const minus = event.key === "-" || event.code === "NumpadSubtract";
    const reset = event.key === "0" || event.code === "Numpad0";
    if (!plus && !minus && !reset) return;
    event.preventDefault(); const levels = [80, 90, 100, 110, 125, 150];
    void desktop.zoom(reset ? 100 : levels[Math.max(0, Math.min(5, levels.indexOf(zoom) + (plus ? 1 : -1)))]);
  }, true);
  document.addEventListener("fullscreenchange", () => { void call("fullscreen", !!document.fullscreenElement); });
  document.addEventListener("contextmenu", event => {
    if (!(event.target instanceof Element && event.target.closest("input,textarea,[contenteditable=true]"))) event.preventDefault();
  });
  document.addEventListener("click", event => {
    const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
    if (link && /^(https:|ms-windows-store:)/.test(link.href)) { event.preventDefault(); void desktop.openExternal!(link.href); }
  });
  subscribe<string>("desktop-error", message => { window.dispatchEvent(new CustomEvent("desktop-error", { detail: message })); });
  subscribe<string>("startup-status", message => { window.dispatchEvent(new CustomEvent("startup-status", { detail: message })); });
  requestAnimationFrame(() => requestAnimationFrame(() => { void call("ready"); }));
}

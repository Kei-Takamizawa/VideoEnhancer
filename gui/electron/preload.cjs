const { contextBridge, ipcRenderer, webUtils } = require("electron");
contextBridge.exposeInMainWorld("desktop", {
  connection: () => ipcRenderer.invoke("connection"),
  reload: () => ipcRenderer.invoke("reload"),
  restartEngine: () => ipcRenderer.invoke("restart-engine"),
  logRendererError: (details) => ipcRenderer.invoke("renderer-error", details),
  files: (kind) => ipcRenderer.invoke("files", kind),
  openFolder: (folder) => ipcRenderer.invoke("folder", folder),
  play: (file) => ipcRenderer.invoke("play", file),
  reveal: (file) => ipcRenderer.invoke("reveal", file),
  hide: () => ipcRenderer.invoke("hide"),
  onTrayExplanation: (callback) => {
    const listener = () => callback();
    ipcRenderer.on("tray-explanation", listener);
    return () => ipcRenderer.removeListener("tray-explanation", listener);
  },
  copy: (text) => ipcRenderer.invoke("copy", text),
  filePath: (file) => webUtils.getPathForFile(file),
  zoom: (percent) => ipcRenderer.invoke("zoom", percent),
  theme: (theme) => ipcRenderer.invoke("theme", theme),
  onZoom: (callback) => {
    const listener = (_event, percent) => callback(percent);
    ipcRenderer.on("zoom-changed", listener);
    return () => ipcRenderer.removeListener("zoom-changed", listener);
  },
});

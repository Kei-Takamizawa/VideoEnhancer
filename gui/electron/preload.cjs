const { contextBridge, ipcRenderer, webUtils } = require("electron");
contextBridge.exposeInMainWorld("desktop", {
  connection: () => ipcRenderer.invoke("connection"),
  files: (kind) => ipcRenderer.invoke("files", kind),
  openFolder: (folder) => ipcRenderer.invoke("folder", folder),
  play: (file) => ipcRenderer.invoke("play", file),
  copy: (text) => ipcRenderer.invoke("copy", text),
  filePath: (file) => webUtils.getPathForFile(file),
});

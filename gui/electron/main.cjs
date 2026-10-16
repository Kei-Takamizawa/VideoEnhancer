const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  ipcMain,
  dialog,
  shell,
  clipboard,
  protocol,
  net,
  nativeImage,
  nativeTheme,
} = require("electron");
const fs = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { pathToFileURL } = require("node:url");
const { servicePython } = require("./python.cjs");
const { permissionAllowed } = require("./permissions.cjs");

protocol.registerSchemesAsPrivileged([
  {
    scheme: "app",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
    },
  },
]);
let window,
  tray,
  connection,
  quitting = false,
  preferenceTimer;
const storage = require("./storage.cjs");
let storageProgress = { phase: "Idle" };
let storageBusy = false;
const locationFile = () => path.join(app.getPath("userData"), "storage-location.json");
let home =
  process.env.VE_HOME ||
  path.join(app.getPath("appData"), "..", "Local", "VideoEnhancer");
let child;
let starting;
let zoomPercent = 100;
let trayExplained = false;
const publisherURLs = new Set();
let zoomSave = Promise.resolve();
const zoomLevels = [80, 90, 100, 110, 125, 150];
function updateOverlay() {
  const dark = nativeTheme.shouldUseDarkColors;
  window?.setTitleBarOverlay({
    color: dark ? "#1C1814" : "#F5EFE6",
    symbolColor: dark ? "#DCCFBD" : "#574A3F",
    height: 32,
  });
}
function applyAppearance(theme) {
  nativeTheme.themeSource = ["system", "dark", "light"].includes(theme) ? theme : "system";
  updateOverlay();
}
nativeTheme.on("updated", updateOverlay);
async function setZoom(percent) {
  if (!zoomLevels.includes(percent)) throw new Error("Choose a supported zoom level.");
  zoomPercent = percent;
  zoomSave = zoomSave.catch(() => {}).then(() => request("settings", "PUT", { zoom: percent }));
  await zoomSave;
  window.webContents.setZoomFactor(percent / 100);
  window.webContents.send("zoom-changed", percent);
  return percent;
}
app.setName("VideoEnhancer");
async function request(route, method = "GET", body) {
  if (!connection) throw new Error("The engine is not connected.");
  const result = await fetch(`${connection.base_url}/${route}`, {
    method,
    headers: {
      Authorization: `Bearer ${connection.token}`,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(route === "shutdown" ? 20000 : 5000),
  });
  if (!result.ok)
    throw new Error((await result.json()).error || "Engine request failed.");
  return result.json();
}
async function ensureService() {
  if (storageBusy) throw new Error("App data is moving. Wait for it to finish.");
  if (!starting)
    starting = startService().finally(() => {
      starting = undefined;
    });
  return starting;
}
async function engineLocation() {
  if (process.env.VE_ENGINE_ROOT) return process.env.VE_ENGINE_ROOT;
  if (!app.isPackaged) return path.resolve(__dirname, "../..");
  return JSON.parse(await fs.readFile(path.join(process.resourcesPath, "engine-location.json"), "utf8")).root;
}
async function stopService() {

        await request("shutdown", "POST", {});
        const deadline = Date.now() + 20000;
        while (Date.now() < deadline) {
          try {
            const current = JSON.parse(await fs.readFile(path.join(home, "serve.json"), "utf8"));
            process.kill(current.pid, 0);
          } catch (error) {
            if (error.code !== "ENOENT" && error.code !== "ESRCH") throw error;
            connection = undefined;
            return;
          }
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        throw new Error("The engine could not stop safely. File removal may still be running. Try again when it finishes.");

}
async function loadStorageLocation() {
  let choice = await storage.startupLocation(locationFile(), home, process.env.VE_HOME);
  while (choice.missing) {
    const result = await dialog.showMessageBox({ type: "error", message: "The app data folder was not found",
      detail: choice.home, buttons: ["Choose…", "Use the previous folder", "Quit"], cancelId: 2 });
    if (result.response === 2) { app.exit(0); return false; }
    let selected;
    if (result.response === 0) {
      const pick = await dialog.showOpenDialog({ properties: ["openDirectory"] });
      if (!pick.canceled) selected = pick.filePaths[0];
    } else selected = choice.previous;
    if (selected && await fs.stat(selected).then(stat => stat.isDirectory()).catch(() => false)) {
      await storage.writeLocation(locationFile(), { active: selected, previous: choice.home });
      choice = await storage.startupLocation(locationFile(), home);
    }
  }
  home = choice.home;
  return true;
}

async function startService() {
  try {
    const candidate = JSON.parse(
      await fs.readFile(path.join(home, "serve.json"), "utf8"),
    );
    if (
      !Number.isInteger(candidate.port) ||
      candidate.port < 1 ||
      candidate.port > 65535 ||
      typeof candidate.token !== "string"
    )
      throw new Error("Invalid engine connection.");
    connection = {
      ...candidate,
      base_url: `http://127.0.0.1:${candidate.port}/v1`,
    };
    await request("health");
    return connection;
  } catch {
    connection = undefined;
  }
  let engineRoot =
    process.env.VE_ENGINE_ROOT || path.resolve(__dirname, "../..");
  if (app.isPackaged && !process.env.VE_ENGINE_ROOT) {
    const location = JSON.parse(
      await fs.readFile(
        path.join(process.resourcesPath, "engine-location.json"),
        "utf8",
      ),
    );
    engineRoot = location.root;
  }
  const configuredPython =
    process.env.VE_PYTHON ||
    path.join(engineRoot, ".venv", "Scripts", "python.exe");
  await fs.mkdir(home, { recursive: true });
  const log = await fs.open(path.join(home, "service-start.log"), "a");
  const python = await servicePython(configuredPython);
  await log.write(`Service executable: ${python.executable}\n`);
  if (python.fallback)
    await log.write("pythonw.exe is missing; falling back to python.exe with windowsHide.\n");
  child = spawn(python.executable, ["-m", "videoenhancer.cli", "serve"], {
    cwd: engineRoot,
    env: { ...process.env, VE_HOME: home, VE_STORAGE_MOVE_HOLD: storageBusy ? "1" : "0" },
    windowsHide: true,
    detached: true,
    stdio: ["ignore", log.fd, log.fd],
  });
  let spawnError;
  child.once("error", (error) => {
    spawnError = error;
  });
  child.unref();
  await log.close();
  for (let attempt = 0; attempt < 150; attempt++) {
    if (spawnError)
      throw new Error(
        `The engine could not start: ${spawnError.message}. Check VE_PYTHON and the Python environment.`,
      );
    await new Promise((resolve) => setTimeout(resolve, 200));
    try {
      const data = JSON.parse(
        await fs.readFile(path.join(home, "serve.json"), "utf8"),
      );
      connection = { ...data, base_url: `http://127.0.0.1:${data.port}/v1` };
      await request("health");
      return connection;
    } catch {
      connection = undefined;
    }
  }
  throw new Error(
    "The engine did not become reachable. Check service-start.log, then Retry.",
  );
}
function trusted(event) {
  const url = event.senderFrame?.url || "";
  return (
    event.sender === window?.webContents &&
    (url.startsWith("app://videoenhancer/") ||
      url.startsWith("http://127.0.0.1:5173/"))
  );
}
function handle(name, fn) {
  ipcMain.handle(name, (event, ...args) => {
    if (!trusted(event)) throw new Error("Untrusted renderer.");
    return fn(...args);
  });
}
async function syncPreferences() {
  try {
    const settings = await request("settings");
      trayExplained = settings.tray_explained === true;
      if (!publisherURLs.size) {
        const models = await request("models");
        for (const model of models) if (model.builtin && model.publisher_url) publisherURLs.add(new URL(model.publisher_url).href);
      }
    applyAppearance(settings.theme);
    zoomPercent = zoomLevels.includes(settings.zoom) ? settings.zoom : 100;
    window?.webContents.setZoomFactor(zoomPercent / 100);
    const login = {
      path: process.execPath,
      args: [
        ...(app.isPackaged ? [] : [path.resolve(__dirname, "..")]),
        "--hidden",
      ],
    };
    const current = app.getLoginItemSettings(login).openAtLogin;
    if (current !== settings.start_with_windows)
      app.setLoginItemSettings({
        ...login,
        openAtLogin: settings.start_with_windows,
      });
    const health = await request("health");
    tray?.setContextMenu(
      Menu.buildFromTemplate([
        {
          label: "Open VideoEnhancer",
          click: () => {
            window.show();
            window.focus();
          },
        },
        {
          label:
            health.paused_all
              ? "Resume processing"
              : "Pause processing",
          click: () =>
            request("processing", "POST", {
              paused: !health.paused_all,
            }).catch(showError),
        },
        { type: "separator" },
        { label: "Quit", click: gracefulQuit },
      ]),
    );
  } catch {
    /* The renderer shows connection errors and retains its last snapshot. */
  }
}
function showError(error) {
  dialog.showErrorBox("VideoEnhancer", String(error.message || error));
}
async function gracefulQuit() {
  if (quitting) return;
  try {
    if (starting) await starting.catch(() => {});
    if (!connection) {
      try {
        const candidate = JSON.parse(
          await fs.readFile(path.join(home, "serve.json"), "utf8"),
        );
        connection = {
          ...candidate,
          base_url: `http://127.0.0.1:${candidate.port}/v1`,
        };
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }
    if (connection) {
      try {
        await request("shutdown", "POST", {});
      } catch (error) {
        let alive = false;
        try {
          const current = JSON.parse(
            await fs.readFile(path.join(home, "serve.json"), "utf8"),
          );
          process.kill(current.pid, 0);
          alive = true;
        } catch (lookup) {
          if (lookup.code !== "ENOENT" && lookup.code !== "ESRCH") throw lookup;
        }
        if (alive) throw error;
      }
    }
    quitting = true;
    clearInterval(preferenceTimer);
    tray?.destroy();
    app.quit();
  } catch (error) {
    window?.show();
    showError(
      new Error(
        `The engine could not stop cleanly. Retry Quit. ${error.message}`,
      ),
    );
  }
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    if (window) {
      window.show();
      window.focus();
    }
  });
  app.on("window-all-closed", () => {});
  app.on("before-quit", (event) => {
    if (!quitting) {
      event.preventDefault();
      void gracefulQuit();
    }
  });
  app
    .whenReady()
    .then(async () => {
      if (!(await loadStorageLocation())) return;
      if (process.platform !== "win32") {
        quitting = true;
        dialog.showErrorBox(
          "VideoEnhancer",
          "The desktop app requires Windows 11.",
        );
        app.quit();
        return;
      }
      protocol.handle("app", async (request) => {
        const url = new URL(request.url);
        if (url.hostname !== "videoenhancer")
          return new Response("Forbidden", { status: 403 });
        const media = /^\/media\/([^/]+)$/.exec(url.pathname);
        if (media) {
          if (!["GET", "HEAD"].includes(request.method)) return new Response("Forbidden", { status: 403 });
          if (!connection) await ensureService();
          const headers = { Authorization: `Bearer ${connection.token}` };
          const range = request.headers.get("Range");
          if (range) headers.Range = range;
          return net.fetch(`${connection.base_url}/queue/${encodeURIComponent(decodeURIComponent(media[1]))}/video`,
            { method: request.method, headers, signal: request.signal });
        }
        const root = path.resolve(__dirname, "../dist");
        const target = path.resolve(
          root,
          `.${decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname)}`,
        );
        if (!target.startsWith(root + path.sep))
          return new Response("Forbidden", { status: 403 });
        return net.fetch(pathToFileURL(target).toString());
      });
      let initialSettings = {};
      try {
        initialSettings = JSON.parse(await fs.readFile(path.join(home, "settings.json"), "utf8"));
      } catch { /* Defaults apply on a new isolated home. */ }
      nativeTheme.themeSource = ["system", "dark", "light"].includes(initialSettings.theme)
        ? initialSettings.theme : "system";
      zoomPercent = zoomLevels.includes(initialSettings.zoom) ? initialSettings.zoom : 100;
      trayExplained = initialSettings.tray_explained === true;
      Menu.setApplicationMenu(null);
      window = new BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 1100,
        minHeight: 700,
        show: false,
        title: "VideoEnhancer",
        backgroundColor: nativeTheme.shouldUseDarkColors ? "#1C1814" : "#F5EFE6",
        titleBarStyle: "hidden",
        titleBarOverlay: {
          color: nativeTheme.shouldUseDarkColors ? "#1C1814" : "#F5EFE6",
          symbolColor: nativeTheme.shouldUseDarkColors ? "#DCCFBD" : "#574A3F",
          height: 32,
        },
        autoHideMenuBar: true,
        webPreferences: {
          preload: path.join(__dirname, "preload.cjs"),
          contextIsolation: true,
          nodeIntegration: false,
          sandbox: true,
          webSecurity: true,
          zoomFactor: zoomPercent / 100,
        },
      });
      window.webContents.on("before-input-event", (event, input) => {
        if (input.type !== "keyDown" || !input.control || input.alt || input.meta) return;
        const plus = ["+", "="].includes(input.key) || input.code === "NumpadAdd";
        const minus = input.key === "-" || input.code === "NumpadSubtract";
        const reset = input.key === "0" || input.code === "Numpad0";
        if (!plus && !minus && !reset) return;
        event.preventDefault();
        const index = zoomLevels.indexOf(zoomPercent);
        const target = reset ? 100 : zoomLevels[Math.max(0, Math.min(zoomLevels.length - 1, index + (plus ? 1 : -1)))];
        void setZoom(target).catch(showError);
      });
      window.on("close", (event) => {
        if (!quitting) {
          event.preventDefault();
          if (trayExplained) window.hide();
          else window.webContents.send("tray-explanation");
        }
      });
      window.webContents.setWindowOpenHandler(({ url }) => {
        if (
          /^https:\/\/github\.com\/Kei-Takamizawa\/VideoEnhancer\/(blob\/main\/docs\/|pull\/)/.test(
            url,
            ) || publisherURLs.has(url)
        )
          void shell.openExternal(url);
        return { action: "deny" };
      });
      window.webContents.on("will-navigate", (event) => event.preventDefault());
      window.webContents.session.setPermissionRequestHandler(
        (contents, permission, callback, details) => callback(permissionAllowed(window, contents, permission, details.requestingUrl)),
      );
      window.webContents.session.setPermissionCheckHandler((contents, permission, origin) =>
        permissionAllowed(window, contents, permission, origin));
      window.webContents.session.webRequest.onHeadersReceived(
        (details, callback) => {
          const dev = process.env.VE_GUI_DEV === "1";
          callback({
            responseHeaders: {
              ...details.responseHeaders,
              "Content-Security-Policy": [
                `default-src 'none'; script-src 'self'; style-src 'self'${dev ? " 'unsafe-inline'" : ""}; style-src-attr 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; font-src 'self'; connect-src http://127.0.0.1:*${dev ? " ws://127.0.0.1:5173" : ""}; object-src 'none'; base-uri 'none'; frame-src 'none'; form-action 'none'`,
              ],
            },
          });
        },
      );
      handle("connection", ensureService);
      handle("reload", () => { window.webContents.reload(); });
      handle("restart-engine", async () => {
        await ensureService(); await stopService(); return ensureService();
      });
      handle("storage-status", async () => ({ ...storageProgress,
        ...(await storage.readLocation(locationFile())), folder: home }));
      handle("storage-remove-old", () => storage.removePrevious(locationFile(), home));
      handle("storage-move", async (target) => {
        if (storageBusy) throw new Error("App data is already moving.");
        if (typeof target !== "string" || !path.isAbsolute(target)) throw new Error("Choose an absolute folder.");
        // Reject bad targets before stopping the current service.
        const candidate = await fs.lstat(target).catch(error => { if (error.code === "ENOENT") return undefined; throw error; });
        if (candidate && (!candidate.isDirectory() || candidate.isSymbolicLink() || (await fs.readdir(target)).length))
          throw new Error("The target must be a new or empty folder.");
        await request("storage/prepare", "POST", {});
        storageBusy = true;
        storageProgress = { phase: "Stopping the service" };
        const source = home;
        const priorLocation = await storage.readLocation(locationFile());
        let switched = false;
        try {
          await stopService();
          const info = await fs.stat(source, { bigint: true });
          storageProgress = { phase: "Copying and verifying", copied_bytes: 0 };
          const engineRoot = await engineLocation();
          await new Promise((resolve, reject) => {
            const copy = spawn(process.env.VE_PYTHON || path.join(engineRoot, ".venv", "Scripts", "python.exe"),
              ["-m", "videoenhancer.service.storage", source, target],
              { cwd: engineRoot, env: { ...process.env, VE_HOME: source }, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
            let buffer = "", errors = "";
            copy.stdout.on("data", chunk => {
              buffer += chunk.toString(); let boundary;
              while ((boundary = buffer.indexOf("\n")) >= 0) {
                const line = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 1);
                try { storageProgress = JSON.parse(line); } catch { /* Ignore incomplete diagnostics. */ }
              }
            });
            copy.stderr.on("data", chunk => { errors = (errors + chunk.toString()).slice(-8000); });
            copy.on("error", reject);
            copy.on("exit", code => code === 0 ? resolve() : reject(new Error(errors || "App data copy failed.")));
          });
          storageProgress = { ...storageProgress, phase: "Starting the service" };
          home = target; connection = undefined;
          await startService();
          // Publish the new location only after its service is reachable.
          await storage.writeLocation(locationFile(), { active: home, previous: source,
            previousIdentity: { dev: String(info.dev), ino: String(info.ino) } });
          switched = true;
          storageProgress = { ...storageProgress, phase: "Move completed", source, target };
          return { moved: true, folder: home };
        } catch (error) {
          if (home !== source) { await stopService().catch(() => {}); home = source; connection = undefined; }
          if (!switched) await storage.writeLocation(locationFile(), priorLocation);
          await startService();
          storageProgress = { phase: "Move failed; the previous folder is still in use", error: error.message };
          throw error;
        } finally { storageBusy = false; }
      });
      handle("renderer-error", async (details) => {
        if (typeof details !== "string") throw new Error("Invalid renderer error.");
        await fs.mkdir(home, { recursive: true });
        await fs.appendFile(path.join(home, "renderer-errors.log"),
          `${new Date().toISOString()}\n${details.slice(0, 64000)}\n`, "utf8");
      });
      handle("zoom", setZoom);
      handle("theme", (theme) => {
        if (!["light", "dark", "system"].includes(theme)) throw new Error("Invalid theme.");
        applyAppearance(theme);
      });
      handle("hide", async () => {
        await request("settings", "PUT", { tray_explained: true });
        trayExplained = true;
        window.hide();
      });
      handle("reveal", async (file) => {
        if (typeof file !== "string" || !path.isAbsolute(file) || file.includes("\0")) throw new Error("Choose an absolute local video file.");
        if (!(await fs.stat(file)).isFile()) throw new Error("The video does not exist.");
        shell.showItemInFolder(file);
      });
      handle("files", async (kind) => {
        if (kind !== "videos" && kind !== "folder")
          throw new Error("Invalid dialog kind.");
        const result = await dialog.showOpenDialog(window, {
          properties:
            kind === "folder"
              ? ["openDirectory"]
              : ["openFile", "multiSelections"],
          filters:
            kind === "videos"
              ? [
                  {
                    name: "Videos",
                    extensions: ["mp4", "mkv", "mov", "avi", "webm", "m4v"],
                  },
                ]
              : [],
        });
        return result.canceled ? [] : result.filePaths;
      });
      handle("folder", async (folder) => {
        if (
          typeof folder !== "string" ||
          !path.isAbsolute(folder) ||
          folder.includes("\0")
        )
          throw new Error("Choose an absolute local folder.");
        const stat = await fs.stat(folder);
        if (!stat.isDirectory()) throw new Error("The folder does not exist.");
        const error = await shell.openPath(folder);
        if (error) throw new Error(error);
      });
      handle("copy", (text) => {
        if (typeof text !== "string" || text.length > 100000)
          throw new Error("Details are too large.");
        clipboard.writeText(text);
      });
      handle("play", async (file) => {
        if (typeof file !== "string" || !path.isAbsolute(file) || file.includes("\0"))
          throw new Error("Choose an absolute local video file.");
        if (!(await fs.stat(file)).isFile()) throw new Error("The video does not exist.");
        const error = await shell.openPath(file);
        if (error) throw new Error(error);
      });
      tray = new Tray(
        nativeImage.createFromPath(path.join(__dirname, "icon.png")),
      );
      tray.setToolTip("VideoEnhancer");
      tray.on("double-click", () => {
        window.show();
        window.focus();
      });
      tray.setContextMenu(
        Menu.buildFromTemplate([
          { label: "Open VideoEnhancer", click: () => window.show() },
          { label: "Quit", click: gracefulQuit },
        ]),
      );
      await window.loadURL(
        process.env.VE_GUI_DEV === "1"
          ? "http://127.0.0.1:5173"
          : "app://videoenhancer/",
      );
      if (!process.argv.includes("--hidden")) window.show();
      preferenceTimer = setInterval(syncPreferences, 3000);
      await syncPreferences();
    })
    .catch((error) => {
      showError(error);
      quitting = true;
      app.quit();
    });
}

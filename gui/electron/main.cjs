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
} = require("electron");
const fs = require("node:fs/promises");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { pathToFileURL } = require("node:url");

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
const home =
  process.env.VE_HOME ||
  path.join(app.getPath("appData"), "..", "Local", "VideoEnhancer");
let child;
let starting;
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
  if (!starting)
    starting = startService().finally(() => {
      starting = undefined;
    });
  return starting;
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
  const python =
    process.env.VE_PYTHON ||
    path.join(engineRoot, ".venv", "Scripts", "python.exe");
  await fs.mkdir(home, { recursive: true });
  const log = await fs.open(path.join(home, "service-start.log"), "a");
  child = spawn(python, ["-m", "videoenhancer.cli", "serve"], {
    cwd: engineRoot,
    env: { ...process.env, VE_HOME: home },
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
            health.engine_state === "Paused"
              ? "Resume processing"
              : "Pause processing",
          click: () =>
            request("processing", "POST", {
              paused: health.engine_state !== "Paused",
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
      if (process.platform !== "win32") {
        quitting = true;
        dialog.showErrorBox(
          "VideoEnhancer",
          "The desktop app requires Windows 11.",
        );
        app.quit();
        return;
      }
      protocol.handle("app", (request) => {
        const url = new URL(request.url);
        if (url.hostname !== "videoenhancer")
          return new Response("Forbidden", { status: 403 });
        const root = path.resolve(__dirname, "../dist");
        const target = path.resolve(
          root,
          `.${decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname)}`,
        );
        if (!target.startsWith(root + path.sep))
          return new Response("Forbidden", { status: 403 });
        return net.fetch(pathToFileURL(target).toString());
      });
      window = new BrowserWindow({
        width: 1280,
        height: 840,
        minWidth: 1100,
        minHeight: 700,
        show: false,
        title: "VideoEnhancer",
        backgroundColor: "#14181f",
        autoHideMenuBar: true,
        webPreferences: {
          preload: path.join(__dirname, "preload.cjs"),
          contextIsolation: true,
          nodeIntegration: false,
          sandbox: true,
          webSecurity: true,
        },
      });
      window.on("close", (event) => {
        if (!quitting) {
          event.preventDefault();
          window.hide();
        }
      });
      window.webContents.setWindowOpenHandler(({ url }) => {
        if (
          /^https:\/\/github\.com\/Kei-Takamizawa\/VideoEnhancer\/(blob\/main\/docs\/|pull\/)/.test(
            url,
          )
        )
          void shell.openExternal(url);
        return { action: "deny" };
      });
      window.webContents.on("will-navigate", (event) => event.preventDefault());
      window.webContents.session.setPermissionRequestHandler(
        (_contents, _permission, callback) => callback(false),
      );
      window.webContents.session.webRequest.onHeadersReceived(
        (details, callback) => {
          const dev = process.env.VE_GUI_DEV === "1";
          callback({
            responseHeaders: {
              ...details.responseHeaders,
              "Content-Security-Policy": [
                `default-src 'none'; script-src 'self'; style-src 'self'${dev ? " 'unsafe-inline'" : ""}; style-src-attr 'unsafe-inline'; img-src 'self' blob: data:; media-src blob:; font-src 'self'; connect-src http://127.0.0.1:*${dev ? " ws://127.0.0.1:5173" : ""}; object-src 'none'; base-uri 'none'; frame-src 'none'; form-action 'none'`,
              ],
            },
          });
        },
      );
      handle("connection", ensureService);
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

function permissionAllowed(window, contents, permission, origin) {
  try {
  if (!window || contents !== window.webContents || permission !== "fullscreen") return false;
  const page = new URL(contents.getURL());
  if (!(page.protocol === "app:" && page.hostname === "videoenhancer") &&
      !(process.env.VE_GUI_DEV === "1" && page.protocol === "http:" && page.hostname === "127.0.0.1")) return false;
  if (!origin) return true;
  const requested = new URL(origin);
  return requested.protocol === page.protocol && requested.host === page.host;
  } catch { return false; }
}
module.exports = { permissionAllowed };

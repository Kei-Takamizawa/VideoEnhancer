import { createRequire } from "node:module";
import { expect, it } from "vitest";
const { permissionAllowed } = createRequire(import.meta.url)("../electron/permissions.cjs");

it("allows fullscreen for the own app window and denies every other permission and origin", () => {
  const contents = { getURL: () => "app://videoenhancer/index.html" };
  const window = { webContents: contents };
  expect(permissionAllowed(window, contents, "fullscreen", "app://videoenhancer")).toBe(true);
  expect(permissionAllowed(window, contents, "fullscreen", "https://example.com")).toBe(false);
  expect(permissionAllowed(window, { ...contents }, "fullscreen", "app://videoenhancer")).toBe(false);
  for (const permission of ["camera", "microphone", "notifications", "clipboard-read", "geolocation", "unknown"])
    expect(permissionAllowed(window, contents, permission, "app://videoenhancer")).toBe(false);
});

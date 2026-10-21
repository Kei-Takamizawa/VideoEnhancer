import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

test("unsigned owner folder finds the external engine and enforces renderer isolation", async () => {
  test.skip(
    !process.env.VE_TAURI_RELEASE_EXE,
    "Opt-in generated Windows package smoke check.",
  );
  const env: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(process.env).filter(
        (entry): entry is [string, string] => typeof entry[1] === "string",
      ),
    ),
    VE_HOME: path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `packaged-${Date.now()}`),
  };
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.VE_ENGINE_ROOT;
  mkdirSync(env.VE_HOME, { recursive: true });
  writeFileSync(path.join(env.VE_HOME, "settings.json"), JSON.stringify({ start_with_windows: false, tour_completed: true }));
  const app = await desktop.launch({
    executablePath: process.env.VE_TAURI_RELEASE_EXE!,
    args: [`--user-data-dir=${path.join(env.VE_HOME, "desktop")}`],
    env,
  });
  try {
    const page = await app.firstWindow();
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
      timeout: 40000,
    });
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME, "serve.json")), { timeout: 40000 })
      .toBe(true);
    expect(page.url()).toBe("http://tauri.localhost/");
    await expect(app.command("state")).rejects.toThrow(/desktop_test.*not found|not allowed|denied/i);
    expect(
      await page.evaluate(
        () => typeof (window as unknown as { require?: unknown }).require,
      ),
    ).toBe("undefined");
    await page.evaluate(async () => {
      const c = await window.desktop.connection();
      await fetch(`${c.base_url}/shutdown`, { method: "POST", headers: { Authorization: `Bearer ${c.token}`, "Content-Type": "application/json" }, body: "{}" });
    });
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME, "serve.json")), {
        timeout: 25000,
      })
      .toBe(false);
  } finally {
    await app.close().catch(() => {});
  }
});

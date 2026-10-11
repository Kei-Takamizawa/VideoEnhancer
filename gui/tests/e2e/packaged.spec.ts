import { _electron, expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import path from "node:path";

test("unsigned owner folder finds the external engine and enforces renderer isolation", async () => {
  test.skip(
    !process.env.VE_GUI_PACKAGE_EXE,
    "Opt-in generated Windows package smoke check.",
  );
  const env: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(process.env).filter(
        (entry): entry is [string, string] => typeof entry[1] === "string",
      ),
    ),
    VE_HOME: path.resolve("test-results", `packaged-${Date.now()}`),
  };
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.VE_ENGINE_ROOT;
  const app = await _electron.launch({
    executablePath: process.env.VE_GUI_PACKAGE_EXE!,
    args: [`--user-data-dir=${path.join(env.VE_HOME, "desktop")}`],
    env,
  });
  try {
    const page = await app.firstWindow();
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
      timeout: 40000,
    });
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME, "serve.json")))
      .toBe(true);
    const preferences = await app.evaluate(({ BrowserWindow }) => {
      const contents = BrowserWindow.getAllWindows()[0]
        .webContents as unknown as {
        getLastWebPreferences(): {
          contextIsolation: boolean;
          nodeIntegration: boolean;
          sandbox: boolean;
        };
      };
      return contents.getLastWebPreferences();
    });
    expect(preferences.contextIsolation).toBe(true);
    expect(preferences.nodeIntegration).toBe(false);
    expect(preferences.sandbox).toBe(true);
    expect(page.url()).toBe("app://videoenhancer/");
    expect(
      await page.evaluate(
        () => typeof (window as unknown as { require?: unknown }).require,
      ),
    ).toBe("undefined");
    await app.evaluate(({ app }) => app.quit());
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME, "serve.json")), {
        timeout: 25000,
      })
      .toBe(false);
  } finally {
    await app.close().catch(() => {});
  }
});

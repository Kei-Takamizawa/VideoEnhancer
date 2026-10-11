import { _electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
const electron: string = createRequire(import.meta.url)("electron");

test("owner GPU: Standard job survives close, second launch focuses, Quit checkpoints, next start resumes", async () => {
  test.skip(
    !process.env.VE_GUI_OWNER_CLIP || !process.env.VE_GUI_RESUME_HOME,
    "Opt-in owner sample and isolated verified-model home required.",
  );
  test.setTimeout(240000);
  const root = path.resolve("..");
  const env: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(process.env).filter(
        (entry): entry is [string, string] => typeof entry[1] === "string",
      ),
    ),
    VE_HOME: process.env.VE_GUI_RESUME_HOME!,
    VE_ENGINE_ROOT: root,
  };
  delete env.ELECTRON_RUN_AS_NODE;
  const discovery = path.join(env.VE_HOME, "serve.json");
  let app = await _electron.launch({
    executablePath: electron,
    args: ["."],
    env,
  });
  let child = app.process();
  try {
    const page = await app.firstWindow();
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
      timeout: 40000,
    });
    await app.evaluate(({ dialog }, file) => {
      dialog.showOpenDialog = async () => ({
        canceled: false,
        filePaths: [file],
      });
    }, process.env.VE_GUI_OWNER_CLIP!);
    await page.getByRole("button", { name: "+ Add videos" }).click();
    await page.getByText("More options", { exact: true }).click();
    await page
      .getByRole("textbox", { name: /Output folder/ })
      .fill(path.join(env.VE_HOME, "outputs"));
    await expect(
      page.getByRole("button", { name: "Add to queue" }),
    ).toBeEnabled({ timeout: 30000 });
    await page.getByRole("button", { name: "Add to queue" }).click();
    await expect(page.getByText("Now processing", { exact: true })).toBeVisible(
      {
        timeout: 30000,
      },
    );
    await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0].close(),
    );
    await expect
      .poll(() =>
        app.evaluate(({ BrowserWindow }) =>
          BrowserWindow.getAllWindows()[0].isVisible(),
        ),
      )
      .toBe(false);
    const connection = JSON.parse(readFileSync(discovery, "utf8"));
    const health = await fetch(
      `http://127.0.0.1:${connection.port}/v1/health`,
      { headers: { Authorization: `Bearer ${connection.token}` } },
    );
    expect(health.ok).toBe(true);
    const second = spawn(electron, ["."], {
      env,
      windowsHide: true,
      stdio: "ignore",
    });
    await expect
      .poll(
        () =>
          app.evaluate(({ BrowserWindow }) =>
            BrowserWindow.getAllWindows()[0].isVisible(),
          ),
        { timeout: 10000 },
      )
      .toBe(true);
    await expect.poll(() => second.exitCode, { timeout: 10000 }).toBe(0);
    await app.evaluate(({ app }) => app.quit());
    await expect
      .poll(() => existsSync(discovery), { timeout: 25000 })
      .toBe(false);
    await expect.poll(() => child.exitCode, { timeout: 15000 }).not.toBeNull();
    const jobs = path.join(env.VE_HOME, "jobs");
    const fs = await import("node:fs");
    const directories = fs
      .readdirSync(jobs, { withFileTypes: true })
      .filter((entry) => entry.isDirectory());
    const checkpoint = JSON.parse(
      readFileSync(
        path.join(jobs, directories[0].name, "manifest.json"),
        "utf8",
      ),
    );
    expect(checkpoint.state).toBe("queued");
    expect(
      checkpoint.segments.every(
        (s: { state: string }) => s.state !== "running",
      ),
    ).toBe(true);
    app = await _electron.launch({
      executablePath: electron,
      args: ["."],
      env,
    });
    child = app.process();
    const reopened = await app.firstWindow();
    await reopened
      .getByRole("button", { name: "History", exact: true })
      .click();
    await expect(reopened.getByText("Finished", { exact: true })).toBeVisible({
      timeout: 150000,
    });
    console.log(
      JSON.stringify({
        checkpoint_state: checkpoint.state,
        segments: checkpoint.segments.length,
        resumed: "done",
      }),
    );
    await app.evaluate(({ app }) => app.quit());
    await expect
      .poll(() => existsSync(discovery), { timeout: 25000 })
      .toBe(false);
  } finally {
    await app.evaluate(({ app }) => app.quit()).catch(() => {});
    await Promise.race([
      app.close().catch(() => {}),
      new Promise((resolve) => setTimeout(resolve, 10000)),
    ]);
    if (child.exitCode === null) child.kill();
  }
});

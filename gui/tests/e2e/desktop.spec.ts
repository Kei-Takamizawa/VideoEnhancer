import { _electron, expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const electron: string = createRequire(import.meta.url)("electron");

test("desktop starts real CPU service, adds synthetic footage, streams completion and survives window close", async () => {
  const root = path.resolve("..");
  const evidence =
    process.env.VE_GUI_EVIDENCE || path.resolve("test-results/evidence");
  mkdirSync(evidence, { recursive: true });
  const run = path.resolve("test-results", `engine-${Date.now()}`);
  mkdirSync(run, { recursive: true });
  const source = path.join(run, "synthetic.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", [
    "-v",
    "error",
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=320x180:rate=30",
    "-frames:v",
    "60",
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-threads",
    "2",
    source,
  ]);
  const env: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(process.env).filter(
        (e): e is [string, string] => typeof e[1] === "string",
      ),
    ),
    VE_HOME: path.join(run, "home"),
    VE_ENGINE_ROOT: root,
    VE_PYTHON:
      process.env.VE_PYTHON || path.join(root, ".venv/Scripts/python.exe"),
  };
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await _electron.launch({
    executablePath: electron,
    args: ["."],
    env,
  });
  const page = await app.firstWindow();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await expect(page.getByText("Your queue is empty.")).toBeVisible({
      timeout: 40000,
    });
    await app.evaluate(({ dialog }, file) => {
      dialog.showOpenDialog = async () => ({
        canceled: false,
        filePaths: [file],
      });
    }, source);
    // Restoration weights are deliberately absent in CI. Exercise the existing CPU fixture preset.
    await page.route(/\/v1\/(queue|estimate)$/, async (route) => {
      const request = route.request();
      if (request.method() !== "POST") return route.continue();
      const body = request.postDataJSON();
      body.settings = {
        ...body.settings,
        backend: "cpu",
        short_side: "keep",
        fps: "off",
        codec: "h264",
        ...(request.url().endsWith("/queue") ? { preset: "passthrough" } : {}),
      };
      await route.continue({ postData: JSON.stringify(body) });
    });
    await page.getByRole("button", { name: "+ Add videos" }).click();
    await page.getByRole("combobox", { name: /Preset/ }).selectOption("fast");
    await expect(page.getByText("Reading live estimates…")).not.toBeVisible();
    await expect(
      page.getByRole("button", { name: "Add to queue" }),
    ).toBeEnabled({ timeout: 30000 });
    await page.screenshot({ path: path.join(evidence, "add-synthetic.png") });
    await page.getByRole("button", { name: "Add to queue" }).click();
    await expect(page.locator(".state")).toHaveText("Done", { timeout: 40000 });
    await expect(page.getByText("100.0%")).toBeVisible();
    await page.screenshot({ path: path.join(evidence, "queue-synthetic.png") });
    for (const name of ["Plan", "Schedule", "Models", "Settings"]) {
      await page
        .getByRole("navigation")
        .getByRole("button", { name, exact: true })
        .click();
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
      await page.screenshot({
        path: path.join(evidence, `${name.toLowerCase()}-synthetic.png`),
      });
    }
    const discovery = JSON.parse(
      readFileSync(path.join(env.VE_HOME!, "serve.json"), "utf8"),
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
    const response = await fetch(
      `http://127.0.0.1:${discovery.port}/v1/health`,
      { headers: { Authorization: `Bearer ${discovery.token}` } },
    );
    expect(response.ok).toBe(true);
    await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0].show(),
    );
    await page
      .getByRole("navigation")
      .getByRole("button", { name: "Queue", exact: true })
      .click();
    await expect(page.locator(".state")).toHaveText("Done");
    await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0].setSize(1100, 700),
    );
    for (const zoom of [1.25, 1.5]) {
      await app.evaluate(
        ({ BrowserWindow }, factor) =>
          BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(factor),
        zoom,
      );
      for (const name of ["Queue", "Plan", "Schedule", "Models", "Settings"]) {
        await page
          .getByRole("navigation")
          .getByRole("button", { name, exact: true })
          .click();
        const bounds = await page.locator("footer").boundingBox();
        const height = await page.evaluate(() => innerHeight);
        expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(height + 1);
      }
      const png = await app.evaluate(async ({ BrowserWindow }) =>
        (await BrowserWindow.getAllWindows()[0].capturePage())
          .toPNG()
          .toString("base64"),
      );
      writeFileSync(
        path.join(evidence, `settings-${zoom * 100}-percent.png`),
        Buffer.from(png, "base64"),
      );
    }
    expect(errors).toEqual([]);
    await app.evaluate(({ app }) => app.quit());
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME!, "serve.json")))
      .toBe(false);
  } finally {
    await app.close().catch(() => {});
  }
});

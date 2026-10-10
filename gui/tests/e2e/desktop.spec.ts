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
  await app.evaluate(({ BrowserWindow }) => {
    const window = BrowserWindow.getAllWindows()[0];
    window.webContents.setZoomFactor(1);
    window.setContentSize(1280, 800);
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
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
    await page.getByRole("button", { name: /^Fast/ }).click();
    await expect(
      page.getByRole("button", { name: "Add to queue" }),
    ).toBeEnabled({ timeout: 30000 });
    await page.screenshot({ path: path.join(evidence, "add-synthetic.png") });
    await page.getByRole("button", { name: "Add to queue" }).click();
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect(page.getByText("Finished", { exact: true })).toBeVisible({
      timeout: 40000,
    });
    await page.screenshot({
      path: path.join(evidence, "history-synthetic.png"),
    });
    for (const name of ["Home", "History", "Schedule", "Models", "Settings"]) {
      await page.getByRole("button", { name, exact: true }).click();
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
      await page.screenshot({
        path: path.join(evidence, `${name.toLowerCase()}-synthetic.png`),
      });
    }
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByLabel("Theme").selectOption("dark");
    await page
      .getByRole("button", { name: "Save settings", exact: true })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    for (const size of [
      { width: 1280, height: 800 },
      { width: 1100, height: 700 },
    ]) {
      await app.evaluate(
        ({ BrowserWindow }, dimensions) =>
          BrowserWindow.getAllWindows()[0].setContentSize(
            dimensions.width,
            dimensions.height,
          ),
        size,
      );
      for (const theme of ["dark", "light"]) {
        await page
          .getByRole("button", { name: "Settings", exact: true })
          .click();
        await page.getByLabel("Theme").selectOption(theme);
        await page
          .getByRole("button", { name: "Save settings", exact: true })
          .click();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        for (const name of [
          "Home",
          "History",
          "Schedule",
          "Models",
          "Settings",
        ]) {
          await page.getByRole("button", { name, exact: true }).click();
          await expect(
            page.getByRole("heading", { name, exact: true }),
          ).toBeVisible();
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth > innerWidth,
            ),
          ).toBe(false);
          await page.screenshot({
            path: path.join(
              evidence,
              `${name.toLowerCase()}-${theme}-${size.width}x${size.height}.png`,
            ),
          });
        }
        await page.getByRole("button", { name: "Home", exact: true }).click();
        await page.getByRole("button", { name: "+ Add videos" }).click();
        await page.screenshot({
          path: path.join(
            evidence,
            `add-${theme}-${size.width}x${size.height}.png`,
          ),
        });
        await page.getByRole("button", { name: "Close", exact: true }).click();
      }
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
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect(page.getByText("Finished", { exact: true })).toBeVisible();
    await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0].setSize(1100, 700),
    );
    for (const zoom of [1.25, 1.5]) {
      await app.evaluate(
        ({ BrowserWindow }, factor) =>
          BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(factor),
        zoom,
      );
      for (const name of [
        "Home",
        "History",
        "Schedule",
        "Models",
        "Settings",
      ]) {
        await page.getByRole("button", { name, exact: true }).click();
        await expect(
          page.getByRole("heading", { name, exact: true }),
        ).toBeVisible();
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        );
        expect(overflow).toBe(false);
      }
      // Electron page zoom changes CDP screenshot clipping. Capture the physical
      // window only after the renderer has committed two animation frames.
      await page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
          ),
      );
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

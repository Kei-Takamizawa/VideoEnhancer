import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { assertPanelFits } from "./clipping";
const electron: string = (process.env.VE_TAURI_EXE || "");

test("desktop starts real CPU service, adds synthetic footage, streams completion and survives window close", async () => {
  test.setTimeout(150000);
  const root = path.resolve("..");
  const evidence =
    process.env.VE_GUI_EVIDENCE || path.resolve("test-results/evidence");
  mkdirSync(evidence, { recursive: true });
  const run = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `engine-${Date.now()}`);
  mkdirSync(run, { recursive: true });
  mkdirSync(path.join(run, "home"), { recursive: true });
  const source = path.join(run, "home", "synthetic.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", [
    "-v",
    "error",
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=640x360:rate=30",
    "-frames:v",
    "900",
    "-vf",
    `${existsSync("C:/Windows/Fonts/arial.ttf") ? "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':" : "drawtext="}text='Frame %{n}':x=20:y=20:fontsize=32:fontcolor=white:box=1:boxcolor=black`,
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
  const fixture = path.join(env.VE_HOME, "previews", "sync-fixture");
  mkdirSync(fixture, { recursive: true });
  const names = ["original", "fixture-0", "fixture-1", "fixture-2"];
  names.forEach((name) =>
    copyFileSync(source, path.join(fixture, `${name}-preview.mp4`)),
  );
  writeFileSync(
    path.join(fixture, "state.json"),
    JSON.stringify({
      id: "sync-fixture",
      kind: "compare",
      state: "done",
      phase: "Complete",
      request: { file: source },
      result: {
        original: "/v1/operations/sync-fixture/files/original",
        items: names.slice(1).map((id) => ({
          id,
          preview: `/v1/operations/sync-fixture/files/${id}`,
          fps: 30,
          projected_whole_file_seconds: 30,
        })),
      },
    }),
  );
  mkdirSync(env.VE_HOME, { recursive: true });
  writeFileSync(path.join(env.VE_HOME, "settings.json"), JSON.stringify({ tour_completed: true }));
  const app = await desktop.launch({
    executablePath: electron,
    args: [".", `--user-data-dir=${path.join(run, "desktop")}`],
    env,
  });
  const page = await app.firstWindow();
  await (async () => {
    const window = app;
    (await window.setZoomFactor(1));
    (await window.setContentSize(1280, 800));
  })();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
      timeout: 40000,
    });
    await app.files((file => [file])(source));
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
    await page.getByRole("button", { name: "Add videos" }).click();
    await page.locator(".mode-cards").getByRole("button", { name: /^Fast/ }).click();
    await expect(
      page.getByRole("button", { name: "Add to queue" }),
    ).toBeEnabled({ timeout: 30000 });
    await page.screenshot({ path: path.join(evidence, "add-synthetic.png") });
    await page.getByRole("button", { name: "Add to queue" }).click();
    await expect(page.getByText("Now processing", { exact: true })).toBeVisible(
      { timeout: 30000 },
    );
    await page.screenshot({
      path: path.join(evidence, "now-processing-synthetic.png"),
    });
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect(page.locator(".history-image").first()).toBeVisible({
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
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    for (const size of [
      { width: 1280, height: 800 },
      { width: 1100, height: 700 },
    ]) {
      await (async (dimensions) => app.setContentSize(
            dimensions.width,
            dimensions.height,
          ))(size);
      for (const theme of ["dark", "light"]) {
        await page
          .getByRole("button", { name: "Settings", exact: true })
          .click();
        await page.getByLabel("Theme").selectOption(theme);
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
          const clipping = await page.evaluate(() => {
            const main = document.querySelector<HTMLElement>(".app main")!;
            const issues: string[] = [];
            if (document.documentElement.scrollHeight > innerHeight || main.scrollHeight > main.clientHeight + 1) issues.push("page scrolls");
            const dock = document.querySelector<HTMLElement>("aside")!.getBoundingClientRect();
            for (const element of main.querySelectorAll<HTMLElement>("button,label")) {
              const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
              let top = rect.top, bottom = rect.bottom, left = rect.left, right = rect.right;
              for (let parent = element.parentElement; parent; parent = parent.parentElement) {
                const clip = parent.getBoundingClientRect(), parentStyle = getComputedStyle(parent);
                if (/hidden|auto|scroll|clip/.test(parentStyle.overflowY)) { top = Math.max(top, clip.top); bottom = Math.min(bottom, clip.bottom); }
                if (/hidden|auto|scroll|clip/.test(parentStyle.overflowX)) { left = Math.max(left, clip.left); right = Math.min(right, clip.right); }
              }
              if (bottom <= top || right <= left) continue;
              if (!rect.width || !rect.height || rect.bottom < main.getBoundingClientRect().top || rect.top >= dock.top) continue;
              if (element.scrollWidth > element.clientWidth + 1 && style.textOverflow !== "ellipsis") issues.push(`clipped: ${element.textContent?.trim()}`);
              if (top < dock.bottom && bottom > dock.top && left < dock.right && right > dock.left) issues.push(`behind dock: ${element.textContent?.trim()}`);
            }
            return issues;
          });
          expect(clipping).toEqual([]);
          for (const button of await page.locator("aside button").all()) {
            await button.hover();
            const rect = await button.locator('[role="tooltip"]').boundingBox();
            expect(rect).not.toBeNull();
            expect(rect!.x).toBeGreaterThanOrEqual(0);
            expect(rect!.y).toBeGreaterThanOrEqual(0);
            expect(rect!.x + rect!.width).toBeLessThanOrEqual(size.width);
            expect(rect!.y + rect!.height).toBeLessThanOrEqual(size.height);
          }
          await page.screenshot({
            path: path.join(
              evidence,
              `${name.toLowerCase()}-${theme}-${size.width}x${size.height}.png`,
            ),
          });
        }
        await page.getByRole("button", { name: "Home", exact: true }).click();
        await page.getByRole("button", { name: "Add videos" }).click();
        for (const zoom of [1, 1.1]) {
          await (async (factor) => app.setZoomFactor(factor))(zoom);
          await assertPanelFits(page);
        }
        await (async () => app.setZoomFactor(1))();
        await page.screenshot({
          path: path.join(
            evidence,
            `add-${theme}-${size.width}x${size.height}.png`,
          ),
        });
        await page.getByRole("button", { name: "Try models first" }).click();
        await expect(page.locator("canvas")).toHaveAttribute(
          "data-frame",
          /\d+/,
        );
        await expect(page.locator(".thumbnails img")).toHaveCount(8, {
          timeout: 30000,
        });
        for (const zoom of [1, 1.1]) {
          await (async (factor) => app.setZoomFactor(factor))(zoom);
          await assertPanelFits(page);
        }
        await (async () => app.setZoomFactor(1))();
        await page.screenshot({
          path: path.join(
            evidence,
            `compare-${theme}-${size.width}x${size.height}.png`,
          ),
        });
        await page.getByRole("button", { name: "Back", exact: true }).click();
        await page.getByRole("button", { name: "Close", exact: true }).click();
        await page.getByRole("button", { name: "History", exact: true }).click();
        for (const zoom of [1, 1.1]) {
          await (async (factor) => app.setZoomFactor(factor))(zoom);
          await page.locator(".history-image").first().click();
          await expect(page.getByRole("dialog", { name: "Video details" })).toBeVisible();
          await assertPanelFits(page);
          await page.getByRole("button", { name: "Delete video files…" }).click();
          await assertPanelFits(page);
          await page.getByRole("dialog", { name: "Remove records or video files?" }).getByRole("button", { name: "Cancel", exact: true }).click();
          await expect(page.getByRole("dialog")).toHaveCount(0);
        }
        await (async () => app.setZoomFactor(1))();
      }
    }
    await page.getByRole("button", { name: "Models", exact: true }).click();
    await page.getByRole("button", { name: "Compare on my video" }).click();
    const canvas = page.locator("canvas");
    await expect(canvas).toHaveAttribute("data-frame", /\d+/);
    let random = 112358;
    for (let i = 0; i < 100; i++) {
      random = (random * 1664525 + 1013904223) >>> 0;
      const frame = random % 900;
      await page.getByLabel("Seek frame", { exact: true }).fill(String(frame));
      await expect(canvas).toHaveAttribute("data-frame", String(frame));
      expect(JSON.parse((await canvas.getAttribute("data-frames"))!)).toEqual([
        frame,
        frame,
        frame,
        frame,
      ]);
    }
    await page.getByLabel("Seek frame", { exact: true }).fill("0");
    await expect(canvas).toHaveAttribute("data-frame", "0");
    await page.getByRole("button", { name: "Play preview" }).click();
    const played = await page.evaluate(
      () =>
        new Promise<{ frames: number; mismatches: number }>((resolve) => {
          const canvas = document.querySelector("canvas")!;
          let frames = 0,
            mismatches = 0,
            previous = "";
          const observe = () => {
            const current = canvas.dataset.frame!;
            if (current !== previous) {
              previous = current;
              frames++;
              const indices = JSON.parse(canvas.dataset.frames!) as number[];
              if (
                indices.length !== 4 ||
                indices.some((n) => n !== Number(current))
              )
                mismatches++;
            }
            if (frames >= 300) resolve({ frames, mismatches });
            else requestAnimationFrame(observe);
          };
          requestAnimationFrame(observe);
        }),
    );
    expect(played).toEqual({ frames: 300, mismatches: 0 });
    writeFileSync(
      path.join(evidence, "four-stream-sync.json"),
      JSON.stringify(
        {
          randomSeeks: 100,
          playedFrames: played.frames,
          mismatches: played.mismatches,
          evidence:
            "Four synthetic H.264 clips with frame numbers; decoded timestamps share an integer frame clock.",
        },
        null,
        2,
      ),
    );
    await page.getByRole("button", { name: "Back", exact: true }).click();
    const discovery = JSON.parse(
      readFileSync(path.join(env.VE_HOME!, "serve.json"), "utf8"),
    );
    await (async () => app.closeWindow())();
    await expect(page.getByRole("heading", { name: "VideoEnhancer keeps working in the tray" })).toBeVisible();
    await page.getByRole("button", { name: "Got it" }).click();
    await expect
      .poll(() =>
        (async () => app.isVisible())(),
      )
      .toBe(false);
    const response = await fetch(
      `http://127.0.0.1:${discovery.port}/v1/health`,
      { headers: { Authorization: `Bearer ${discovery.token}` } },
    );
    expect(response.ok).toBe(true);
    await (async () => app.show())();
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect(page.locator(".history-image").first()).toBeVisible();
    await (async () => app.setContentSize(1100, 700))();
    for (const zoom of [1.25, 1.5]) {
      await (async (factor) => app.setZoomFactor(factor))(zoom);
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
      const png = (await app.capturePage()).toString("base64");
      writeFileSync(
        path.join(evidence, `settings-${zoom * 100}-percent.png`),
        Buffer.from(png, "base64"),
      );
    }
    expect(errors).toEqual([]);
    await (async () => app.quit())();
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME!, "serve.json")))
      .toBe(false);
  } finally {
    await app.close().catch(() => {});
  }
});

test("Schedule bar tooltips stay inside both window sizes and zoom levels", async () => {
  const { fakeEngine } = createRequire(import.meta.url)("../perf/fake-engine.cjs");
  const home = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `tooltip-${Date.now()}`);
  const fixture = await fakeEngine(home);
  fixture.plan.timezone = "UTC";
  fixture.plan.days = [{ date: "2026-10-12", windows: [], run_hours: 1, jobs: [] }];
  fixture.plan.timeline = [{ job_id: "synthetic-0", start: "2026-10-12T23:00:00Z", end: "2026-10-13T00:00:00Z", overrun_seconds: 45 }];
  const app = await desktop.launch({ executablePath: electron, args: [".", `--user-data-dir=${path.join(home, "desktop")}`], env: { ...process.env, VE_HOME: home } });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Schedule", exact: true }).click();
    for (const size of [[1280, 800], [1100, 700]]) for (const factor of [1, 1.1]) {
      await (async (value) => { const window = app; (await window.setContentSize(value[0], value[1])); (await window.setZoomFactor(value[2])); })([...size, factor]);
      await page.locator(".planned-block").first().hover();
      await expect(page.locator(".timeline-tooltip").first()).toBeVisible();
      await assertPanelFits(page);
    }
  } finally { await app.close(); await fixture.close(); }
});

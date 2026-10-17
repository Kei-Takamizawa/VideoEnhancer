import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";

const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

test("History H.264 player and video fullscreen in both sizes and themes", async () => {
  test.skip(!process.env.VE_PLAYER_VISUAL_EVIDENCE, "Opt-in synthetic player screenshots.");
  test.setTimeout(180000);
  const evidence = process.env.VE_PLAYER_VISUAL_EVIDENCE!;
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `player-${Date.now()}`);
  mkdirSync(root, { recursive: true });
  mkdirSync(evidence, { recursive: true });
  const source = path.join(root, "synthetic-h264.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "2", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p", source], { windowsHide: true });
  const fixture = await fakeEngine(path.join(root, "home"));
  fixture.queue.jobs = fixture.queue.jobs.filter((job: { state: string }) => job.state === "done").slice(0, 1);
  const job = fixture.queue.jobs[0];
  job.settings = { ...job.settings, codec: "h264" };
  job.media = { ...job.media, display_width: 1280, display_height: 720, duration: 2, frame_count: 60 };
  fixture.routes[`queue/${job.id}/video`] = { fixtureVideoPath: source };
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  const records = [];
  try {
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    for (const [width, height] of [[1280, 800], [1100, 700]]) {
      await app.setContentSize(width, height);
      for (const theme of ["dark", "light"]) {
        await page.getByRole("button", { name: "Settings", exact: true }).click();
        await page.getByLabel("Theme").selectOption(theme);
        await page.getByRole("button", { name: "History", exact: true }).click();
        await page.locator(".history-image").first().click();
        const video = page.locator("video");
        await video.evaluate(async (element: HTMLVideoElement) => {
          element.muted = true;
          element.loop = true;
          const painted = new Promise<void>(resolve => element.requestVideoFrameCallback(() => resolve()));
          await element.play();
          await painted;
        });
        await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(2);
        await video.evaluate((element: HTMLVideoElement) => element.pause());
        writeFileSync(path.join(evidence, `player-${width}x${height}-${theme}.png`), await app.capturePage());
        const before = await app.command<{ width: number; height: number; x: number; y: number }>("state");
        await video.evaluate((element: HTMLVideoElement) => element.requestFullscreen());
        await expect.poll(() => app.isFullScreen()).toBe(true);
        await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
        writeFileSync(path.join(evidence, `player-fullscreen-${width}x${height}-${theme}.png`), await app.capturePage());
        await page.keyboard.press("Escape");
        await expect.poll(() => app.isFullScreen()).toBe(false);
        await expect.poll(async () => {
          const state = await app.command<typeof before>("state");
          return [state.width, state.height, state.x, state.y];
        }).toEqual([before.width, before.height, before.x, before.y]);
        records.push({ width, height, theme, restored_bounds: before });
        await expect(page.getByRole("dialog", { name: "Video details" })).toBeHidden();
      }
    }
  } finally {
    writeFileSync(path.join(evidence, "inventory.json"), JSON.stringify(records, null, 2));
    await app.close();
    await fixture.close();
  }
});

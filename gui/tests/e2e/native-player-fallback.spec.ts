import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { copyFileSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

for (const failure of ["missing-helper", "missing-dll", "invalid-dll", "device-failure"]) test(`History uses HTML5 and retains default-player escape after ${failure}`, async () => {
  test.skip(failure !== "missing-helper" && !process.env.VE_PLAYER_FAULT_TEST_EXE, "Requires the CPU-test helper built with test-faults.");
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/p1e3c2-e2e", `native-fallback-${Date.now()}`);
  const bin = path.join(root, "bin"); mkdirSync(bin, { recursive: true });
  const executable = path.join(bin, "VideoEnhancer.exe");
  copyFileSync(process.env.VE_TAURI_EXE!, executable);
  if (failure !== "missing-helper") copyFileSync(process.env.VE_PLAYER_FAULT_TEST_EXE!, path.join(bin, "VideoEnhancer-Player.exe"));
  if (["invalid-dll", "device-failure"].includes(failure)) for (const name of ["libmpv-2.dll", "libspirv-cross-c-shared.dll", "libwinpthread-1.dll"]) writeFileSync(path.join(bin, name), "Deliberately invalid synthetic DLL fixture");
  writeFileSync(path.join(bin, "engine-location.json"), JSON.stringify({ root: path.resolve("..") }));
  const video = path.join(root, "synthetic.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-hide_banner", "-loglevel", "error", "-nostdin", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=2", "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p", video], { windowsHide: true });
  const fixture = await fakeEngine(path.join(root, "home"));
  fixture.queue.jobs = fixture.queue.jobs.filter((job: { state: string }) => job.state === "done").slice(0, 1);
  const job = fixture.queue.jobs[0]; job.settings.codec = "h264";
  job.input = video; job.output = video;
  job.settings.short_side = "keep";
  job.media = { ...job.media, display_width: 320, display_height: 180, cfr_fps: "30", duration: 2 };
  fixture.routes[`queue/${job.id}/video`] = { fixtureVideoPath: video };
  const app = await desktop.launch({ executablePath: executable, env: { ...process.env, VE_HOME: path.join(root, "home"), VE_PLAYER_TEST_FAIL_D3D: failure === "device-failure" ? "1" : "0" } });
  try {
    const page = await app.firstWindow();
    await page.getByRole("button", { name: "History", exact: true }).click();
    await page.locator(".history-image").first().click();
    const player = page.locator("video");
    await expect(player).toBeVisible();
    await expect(page.getByText("Playing with the basic player.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in default player", exact: true })).toHaveCount(0);
    await player.evaluate(async (element: HTMLVideoElement) => { element.muted = true; await element.play(); });
    await expect.poll(() => player.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0);
    await player.dispatchEvent("error");
    await expect(page.getByText("This video can't be played here.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open in default player", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.locator(".history-image").first()).toBeFocused();
  } finally {
    await app.close(); await fixture.close();
    // The helper was absent; this media has no native owner after app close.
    rmSync(video);
  }
});

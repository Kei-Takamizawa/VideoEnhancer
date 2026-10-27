import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

test("section 10 real History cold and prewarmed clicks", async () => {
  test.skip(!process.env.VE_REVIEW_PLAYER_TEST, "Requires the review synthetic fixtures and native payload.");
  test.setTimeout(180000);
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT!, `startup-${Date.now()}`);
  const fixture = await fakeEngine(path.join(root, "home"));
  fixture.queue.jobs = fixture.queue.jobs.filter((job: { state: string }) => job.state === "done").slice(0, 1);
  const job = fixture.queue.jobs[0];
  job.input = path.resolve("../../scratch/p1e3c2-native/review-original-720.mp4");
  job.output = path.resolve("../../scratch/p1e3c2-native/review-output-1080.mp4");
  job.original_state = job.output_state = "present";
  job.settings = { ...job.settings, codec: "h264", short_side: 1080, fps: "2x" };
  job.media = { ...job.media, display_width: 1280, display_height: 720, cfr_fps: "30", duration: 65 };
  fixture.routes[`queue/${job.id}/thumbnail`] = { fixtureVideoPath: path.resolve("../../scratch/p1e3c2-native/review-poster.jpg") };
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const rows: unknown[] = [];
  const sample = (pid: number) => JSON.parse(execFileSync(path.resolve("../.venv/Scripts/python.exe"), [path.resolve("scripts/player-memory.py"), String(pid)], { encoding: "utf8", windowsHide: true }));
  try {
    const page = await app.firstWindow();
    await page.getByRole("button", { name: "History", exact: true }).click();
    await page.evaluate(() => {
      const state = window as unknown as { reviewEvents: unknown[] };
      state.reviewEvents = [];
      window.desktop.onPlayerMetric?.(event => state.reviewEvents.push({ at: performance.now(), ...event }));
    });
    for (const warm of [false, true]) for (let index = 0; index < 5; index++) {
      const button = page.locator(".history-image").first();
      let idle: unknown;
      if (warm) {
        await button.hover();
        await page.waitForTimeout(1300);
        const main = sample(app.process().pid!) as { helper_pids: number[] };
        expect(main.helper_pids).toHaveLength(1);
        if (index === 0) idle = sample(main.helper_pids[0]);
      }
      const began = await button.evaluate(element => { const began = performance.now(); (element as HTMLElement).click(); return began; });
      await expect(page.getByText("Opening player...", { exact: true })).toBeHidden({ timeout: 20000 });
      await expect(page.locator("video")).toHaveCount(0);
      await page.waitForTimeout(800);
      const events = await page.evaluate(began => (window as unknown as { reviewEvents: { at: number; event: Record<string, unknown> }[] }).reviewEvents.filter(row => row.at >= began), began);
      const loaded = events.find(row => row.event.event === "loaded");
      const poster = events.find(row => row.event.event === "poster");
      expect(loaded).toBeDefined();
      rows.push({ warm, index, first_frame_ms: loaded!.at - began, poster_ms: poster ? poster.at - began : null, events, idle });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.waitForTimeout(300);
    }
    await page.locator(".history-image").first().hover();
    await page.waitForTimeout(31000);
    const after = sample(app.process().pid!) as { helper_pids: number[] };
    expect(after.helper_pids).toHaveLength(0);
    rows.push({ unused_prewarm_after_31_seconds: after });
  } finally {
    const evidence = path.resolve(process.env.VE_GUI_EVIDENCE!); mkdirSync(evidence, { recursive: true });
    writeFileSync(path.join(evidence, "history-startup.json"), JSON.stringify(rows, null, 2));
    await app.close(); await fixture.close();
  }
});

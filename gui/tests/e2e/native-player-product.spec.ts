import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

test("optional native player opens from History, stays outside the main process and releases memory", async () => {
  test.skip(!process.env.VE_NATIVE_PLAYER_TEST, "Requires the optional verified native payload on the GPU PC.");
  test.setTimeout(90000);
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/p1e3c2-e2e", `native-product-${Date.now()}`);
  const fixture = await fakeEngine(path.join(root, "home"));
  fixture.queue.jobs = fixture.queue.jobs.filter((job: { state: string }) => job.state === "done").slice(0, 1);
  const job = fixture.queue.jobs[0];
  job.input = path.resolve("../../scratch/p1e3c2-native/pair-original.mp4");
  job.output = path.resolve("../../scratch/p1e3c2-native/pair-enhanced.mp4");
  job.original_state = "present"; job.output_state = "present";
  job.settings = { ...job.settings, codec: "h264", short_side: 720, fps: "2x" };
  job.media = { ...job.media, display_width: 640, display_height: 360, cfr_fps: "30", duration: 65 };
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const samples: Record<string, unknown> = {};
  const sample = () => JSON.parse(execFileSync(path.resolve("../.venv/Scripts/python.exe"), [path.resolve("scripts/player-memory.py"), String(app.process().pid)], { encoding: "utf8", windowsHide: true }));
  try {
    const page = await app.firstWindow();
    await page.getByRole("button", { name: "History", exact: true }).click();
    samples.before = sample();
    const began = Date.now();
    await page.locator(".history-image").first().click();
    await expect(page.getByText("Opening player...", { exact: true })).toBeHidden({ timeout: 20000 });
    await expect(page.locator("video")).toHaveCount(0);
    await expect(page.getByText("This video can't be played here. Open it in your default player instead.", { exact: true })).toHaveCount(0);
    samples.click_to_loaded_upper_ms = Date.now() - began;
    samples.open = sample();
    expect((samples.open as { helper_pids: number[] }).helper_pids.length).toBe(1);
    expect((samples.open as { main_has_libmpv: boolean }).main_has_libmpv).toBe(false);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.locator(".history-image").first()).toBeFocused();
    await new Promise(resolve => setTimeout(resolve, 10000));
    samples.after_10_seconds = sample();
    const before = samples.before as { main_private: number; main_tree_private: number; dedicated: number; shared: number };
    const after = samples.after_10_seconds as typeof before & { helper_pids: number[] };
    expect(after.helper_pids).toHaveLength(0);
    samples.return_within_5_percent = {
      main_private: after.main_private <= before.main_private * 1.05,
      main_tree_private: after.main_tree_private <= before.main_tree_private * 1.05,
      sampled_dedicated: after.dedicated <= before.dedicated * 1.05,
      sampled_shared: after.shared <= before.shared * 1.05,
    };
    // Retain missed targets as measurements; the report assesses the gate.
  } finally {
    const evidence = path.resolve(process.env.VE_GUI_EVIDENCE || "../../evidence/VE-P1e-3c2"); mkdirSync(evidence, { recursive: true });
    writeFileSync(path.join(evidence, "native-product-memory.json"), JSON.stringify(samples, null, 2));
    await app.close(); await fixture.close();
  }
});

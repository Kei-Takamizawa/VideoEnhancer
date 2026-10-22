import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";

test("A7 repeats unreadable-record Copy details fifty times with fresh clipboard contents", async () => {
  test.setTimeout(180000);
  const root = path.resolve("..");
  const run = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1f-3/gui", `copy-${Date.now()}`);
  const evidence = process.env.VE_GUI_EVIDENCE || path.resolve("../../evidence/VE-P1f-3/gui");
  mkdirSync(evidence, { recursive: true });
  execFileSync(path.join(root, ".venv/Scripts/python.exe"), ["tests/p1f2_gui_seed.py", run], { cwd: root, timeout: 60000, windowsHide: true });
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: path.join(run, "home"), VE_ENGINE_ROOT: root } });
  const timings: { iteration: number; milliseconds: number; result: string }[] = [];
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole("button", { name: "Add videos", exact: true })).toBeVisible({ timeout: 40000 });
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect(page.getByRole("button", { name: "damaged-record.mkv", exact: true })).toBeVisible({ timeout: 40000 });
    writeFileSync(path.join(run, "home", "jobs", "c".repeat(32), "manifest.json"), "{syntactically broken record", "utf8");
    await expect(page.getByRole("button", { name: "c".repeat(32), exact: true })).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "c".repeat(32), exact: true }).click();
    await expect(page.getByText(/This job's record can't be shown:/)).toBeVisible();
    for (let iteration = 0; iteration < 50; iteration++) {
      await page.evaluate(index => window.desktop.copy(`synthetic clipboard sentinel ${index}`), iteration);
      const start = performance.now();
      try {
        await page.getByRole("dialog", { name: "Video details" }).getByRole("button", { name: "Copy details", exact: true }).click();
        await expect(page.getByText("Copied", { exact: true })).toBeVisible();
        await expect.poll(() => app.clipboardText()).toContain("Parse error:");
        timings.push({ iteration, milliseconds: performance.now() - start, result: "PASS" });
      } catch (error) {
        timings.push({ iteration, milliseconds: performance.now() - start, result: String(error) });
        throw error;
      }
    }
  } finally {
    writeFileSync(path.join(evidence, "copy-stress.json"), JSON.stringify(timings, null, 2));
    await app.close();
  }
});

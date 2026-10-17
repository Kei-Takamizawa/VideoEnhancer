import { test, expect } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

for (const folder of ["VideoEnhancer", "videoenhancer-desktop"]) test(`U3 pointer in ${folder} wins over stale default History`, async () => {
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `pointer-${folder}-${Date.now()}`);
  const active = path.join(root, "active"), roaming = path.join(root, "roaming"), local = path.join(root, "local");
  const fixture = await fakeEngine(active), stale = await fakeEngine(path.join(local, "VideoEnhancer"));
  fixture.queue.jobs = fixture.queue.jobs.slice(11, 14);
  stale.queue.jobs = stale.queue.jobs.slice(11, 12);
  const source = path.join(roaming, folder, "storage-location.json");
  mkdirSync(path.dirname(source), { recursive: true });
  writeFileSync(source, JSON.stringify({ active }));
  const app = await desktop.launch({ args: [`--user-data-dir=${path.join(root, "desktop")}`], env: { ...process.env, VE_HOME: undefined, VE_TEST_EXPECTED_HOME: active, VE_TEST_APPDATA: roaming, VE_TEST_LOCALAPPDATA: local, VE_KEEP_TEST_ENGINE: "1" } });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect(page.locator(".history-card")).toHaveCount(3);
    const c = await page.evaluate(() => window.desktop.connection());
    const response = await fetch(`${c.base_url}/health`, { headers: { Authorization: `Bearer ${c.token}` } });
    expect((await response.json()).home).toBe(active);
    expect(JSON.parse(readFileSync(path.join(roaming, "VideoEnhancer/storage-location.json"), "utf8")).active).toBe(active);
  } finally { await app.close(); await fixture.close(); await stale.close(); }
});

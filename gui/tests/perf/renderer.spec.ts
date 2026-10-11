import { _electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("./fake-engine.cjs");

test("P1d renderer budgets with 1000 History records and live Standard progress", async () => {
  test.setTimeout(120000);
  const root = path.resolve("test-results", `perf-${Date.now()}`);
  const fixture = await fakeEngine(path.join(root, "home"));
  const app = await _electron.launch({ executablePath: require("electron"), args: [".", `--user-data-dir=${path.join(root, "desktop")}`], env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  const numbers: Record<string, unknown> = {};
  try {
    await app.evaluate(({ BrowserWindow }) => { BrowserWindow.getAllWindows()[0].setContentSize(1280, 800); });
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await page.evaluate(() => {
      const state = window as unknown as { timings: { event: string; start: number; processing: number; duration: number }[]; keyPaint: number[] };
      state.timings = []; state.keyPaint = [];
      const observedSince = performance.now();
      new PerformanceObserver(list => { for (const value of list.getEntries()) { const e = value as PerformanceEventTiming; if (e.startTime >= observedSince && ["keydown", "keyup", "pointerdown", "pointerup", "click"].includes(e.name)) state.timings.push({ event: e.name, start: e.startTime, processing: e.processingStart - e.startTime, duration: e.duration }); } }).observe({ type: "event", durationThreshold: 16 } as PerformanceObserverInit & { durationThreshold: number });
      document.addEventListener("click", () => performance.mark("last-click"), true);
      document.addEventListener("keydown", () => { const began = performance.now(); performance.mark("last-key"); requestAnimationFrame(() => requestAnimationFrame(() => state.keyPaint.push(performance.now() - began))); }, true);
    });
    const screens: Record<string, number> = {};
    for (const name of ["History", "Schedule", "Models", "Settings", "Home"]) {
      await page.getByRole("button", { name, exact: true }).click();
      await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
      screens[name] = await page.evaluate(async () => { await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))); const last = performance.getEntriesByName("last-click").at(-1)!; performance.mark("screen-painted"); return performance.measure("screen-switch", { start: last.startTime, end: performance.now() }).duration; });
    }
    numbers.screen_switch_ms = screens;
    numbers.history_open_ms = screens.History;
    await page.getByRole("button", { name: "History", exact: true }).click();
    numbers.history_dom_cards = await page.locator(".history-card").count();
    await page.getByRole("button", { name: "Schedule", exact: true }).click();
    const field = page.getByLabel("Hours 1 start");
    await field.focus();
    for (let i = 0; i < 5; i++) { await field.press("ArrowUp"); await page.waitForTimeout(80); }
    numbers.keystroke_paint_ms = await page.evaluate(() => (window as unknown as { keyPaint: number[] }).keyPaint);
    await page.waitForTimeout(600);
    numbers.event_timings = await page.evaluate(() => (window as unknown as { timings: unknown[] }).timings);
    // Event timestamps and the response/paint mark use the same renderer clock.
    numbers.preview_after_key_ms = await page.evaluate(() => {
      const key = performance.getEntriesByName("last-key").at(-1)!.startTime;
      return performance.getEntriesByName("schedule-preview-painted").filter(entry => entry.startTime >= key).at(0)?.startTime ? performance.getEntriesByName("schedule-preview-painted").filter(entry => entry.startTime >= key)[0].startTime - key : null;
    });
    await page.getByRole("button", { name: "Home", exact: true }).click();
    await page.evaluate(() => {
      const state = window as unknown as { progressChanges: number[] };
      state.progressChanges = [];
      const node = document.querySelector(".now-percent");
      if (!node) throw new Error("Progress text is missing");
      let previous = node.textContent;
      new MutationObserver(() => { if (node.textContent !== previous) { previous = node.textContent; state.progressChanges.push(performance.now()); } }).observe(node, { characterData: true, childList: true, subtree: true });
    });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Performance.enable");
    const before = await cdp.send("Performance.getMetrics");
    const begin = Date.now();
    await page.waitForTimeout(30000);
    const after = await cdp.send("Performance.getMetrics");
    const task = (value: { metrics: { name: string; value: number }[] }) => value.metrics.find(metric => metric.name === "TaskDuration")!.value;
    numbers.idle_renderer_one_core_percent = (task(after) - task(before)) / ((Date.now() - begin) / 1000) * 100;
    numbers.progress_changes = await page.evaluate(() => (window as unknown as { progressChanges: number[] }).progressChanges);
    const changes = numbers.progress_changes as number[];
    numbers.minimum_progress_gap_ms = Math.min(...changes.slice(1).map((value, index) => value - changes[index]));
    numbers.progress_updates_per_second = (numbers.progress_changes as number[]).length / ((Date.now() - begin) / 1000);
    const evidence = process.env.VE_GUI_EVIDENCE || path.resolve("test-results/perf-evidence");
    mkdirSync(evidence, { recursive: true });
    writeFileSync(path.join(evidence, "renderer-perf.json"), JSON.stringify(numbers, null, 2));
    console.log(JSON.stringify(numbers));
    expect(numbers.history_dom_cards as number).toBeLessThan(30);
    expect(numbers.history_open_ms as number).toBeLessThanOrEqual(300);
    expect(Math.max(...Object.values(screens))).toBeLessThanOrEqual(100);
    expect(Math.max(...numbers.keystroke_paint_ms as number[])).toBeLessThanOrEqual(50);
    expect(Math.max(0, ...(numbers.event_timings as { processing: number }[]).map(event => event.processing))).toBeLessThanOrEqual(50);
    expect(numbers.preview_after_key_ms).not.toBeNull();
    expect(numbers.preview_after_key_ms as number).toBeLessThanOrEqual(500);
    expect(numbers.idle_renderer_one_core_percent as number).toBeLessThanOrEqual(2);
    expect(numbers.progress_updates_per_second as number).toBeGreaterThan(0);
    expect(numbers.progress_updates_per_second as number).toBeLessThanOrEqual(1);
    expect(numbers.minimum_progress_gap_ms as number).toBeGreaterThanOrEqual(1000);
  } finally { await app.close(); await fixture.close(); }
});

import { _electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("./fake-engine.cjs");

test("P1d-3 renderer median budgets across ten independent cold launches", async () => {
  test.setTimeout(900000);
  const samples: Record<string, unknown>[] = [];
  const evidence = process.env.VE_GUI_EVIDENCE || path.resolve("test-results/perf-evidence");
  mkdirSync(evidence, { recursive: true });
  for (let repeat = 0; repeat < 10; repeat++) {
  const root = path.resolve("test-results", `perf-${Date.now()}`);
  const fixture = await fakeEngine(path.join(root, "home"));
  const app = await _electron.launch({ executablePath: require("electron"), args: [".", `--user-data-dir=${path.join(root, "desktop")}`], env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  const numbers: Record<string, unknown> = {};
  try {
    await app.evaluate(({ BrowserWindow }) => { BrowserWindow.getAllWindows()[0].setContentSize(1280, 800); });
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await page.evaluate(() => {
      const state = window as unknown as { timings: { event: string; start: number; processing: number; duration: number; interaction: number; target: string }[]; keyPaint: number[] };
      state.timings = []; state.keyPaint = [];
      const contexts: { event: string; time: number; target: string }[] = [];
      for (const name of ["pointerdown", "pointerup", "click", "keydown", "keyup"]) document.addEventListener(name, event => { const element = (event.target as HTMLElement | null)?.closest("button,input"); contexts.push({ event: name, time: event.timeStamp, target: element?.getAttribute("aria-label") || element?.textContent?.trim().slice(0, 80) || (element as HTMLInputElement | null)?.type || "unknown" }); }, true);
      const observedSince = performance.now();
      new PerformanceObserver(list => { for (const value of list.getEntries()) { const e = value as PerformanceEventTiming; if (e.startTime >= observedSince && ["keydown", "keyup", "pointerdown", "pointerup", "click"].includes(e.name)) state.timings.push({ event: e.name, start: e.startTime, processing: e.processingStart - e.startTime, duration: e.duration, interaction: e.interactionId, target: contexts.findLast(context => context.event === e.name && Math.abs(context.time - e.startTime) < 8)?.target || "unknown" }); } }).observe({ type: "event", durationThreshold: 16 } as PerformanceObserverInit & { durationThreshold: number });
      document.addEventListener("click", () => performance.mark("last-click"), true);
      document.addEventListener("keydown", () => { const began = performance.now(); performance.mark("last-key"); requestAnimationFrame(() => requestAnimationFrame(() => state.keyPaint.push(performance.now() - began))); }, true);
    });
    const visit = async (name: string) => {
      await page.getByRole("button", { name, exact: true }).click();
      await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
      return page.evaluate(async () => { await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))); return performance.now() - performance.getEntriesByName("last-click").at(-1)!.startTime; });
    };
    numbers.cold_history_open_ms = await visit("History");
    for (const name of ["Schedule", "Models", "Settings", "Home"]) await visit(name);
    const screens: Record<string, number> = {};
    for (const name of ["History", "Schedule", "Models", "Settings", "Home"]) screens[name] = await visit(name);
    numbers.screen_switch_ms = screens;
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
    samples.push(numbers);
    writeFileSync(path.join(evidence, "renderer-perf.json"), JSON.stringify({ samples }, null, 2));
    console.log(JSON.stringify({ repeat: repeat + 1, cold_history_open_ms: numbers.cold_history_open_ms, screens, minimum_progress_gap_ms: numbers.minimum_progress_gap_ms }));
  } finally { await app.close(); await fixture.close(); }
  }
  const quantile = (values: number[], percentile: number) => { const sorted = values.toSorted((a, b) => a - b); const position = (sorted.length - 1) * percentile; const lower = Math.floor(position); return sorted[lower] + (sorted[Math.ceil(position)] - sorted[lower]) * (position - lower); };
  const summary: Record<string, { samples: number[]; median: number; p90: number }> = {};
  const add = (name: string, values: number[]) => summary[name] = { samples: values, median: quantile(values, .5), p90: quantile(values, .9) };
  for (const name of ["History", "Schedule", "Models", "Settings", "Home"]) add(`warm_${name}_ms`, samples.map(sample => (sample.screen_switch_ms as Record<string, number>)[name]));
  for (const key of ["cold_history_open_ms", "preview_after_key_ms", "idle_renderer_one_core_percent", "progress_updates_per_second", "minimum_progress_gap_ms"]) add(key, samples.map(sample => Number(sample[key])));
  add("keystroke_paint_max_ms", samples.map(sample => Math.max(...sample.keystroke_paint_ms as number[])));
  const timings = samples.flatMap(sample => sample.event_timings as { processing: number; duration: number; interaction: number; event: string; target: string }[]);
  const interactions = samples.flatMap((sample, repeat) => { const grouped = new Map<number, { repeat: number; duration: number; event: string; target: string }>(); for (const timing of sample.event_timings as typeof timings) { if (!timing.interaction) continue; const previous = grouped.get(timing.interaction); if (!previous || previous.duration < timing.duration) grouped.set(timing.interaction, { repeat: repeat + 1, duration: timing.duration, event: timing.event, target: timing.target }); } return [...grouped.values()]; });
  const interactionP98 = quantile(interactions.map(value => value.duration), .98);
  const maximumInteraction = interactions.toSorted((a, b) => b.duration - a.duration)[0];
  writeFileSync(path.join(evidence, "renderer-perf.json"), JSON.stringify({ samples, summary, interaction_p98_ms: interactionP98, maximum_interaction: maximumInteraction, input_delay_max_ms: Math.max(...timings.map(value => value.processing)), method: "Linear-interpolated quantiles; each repeat starts a fresh renderer; interactionId deduplicates DOM events within each repeat." }, null, 2));
  for (const name of ["History", "Schedule", "Models", "Settings", "Home"]) expect(summary[`warm_${name}_ms`].median).toBeLessThanOrEqual(100);
  expect(summary.cold_history_open_ms.median).toBeLessThanOrEqual(300);
  expect(Math.max(...timings.map(value => value.processing))).toBeLessThanOrEqual(50);
  expect(interactionP98).toBeLessThanOrEqual(200);
  expect(summary.preview_after_key_ms.median).toBeLessThanOrEqual(500);
  expect(summary.keystroke_paint_max_ms.median).toBeLessThanOrEqual(50);
  expect(summary.idle_renderer_one_core_percent.median).toBeLessThanOrEqual(2);
  expect(summary.progress_updates_per_second.median).toBeGreaterThan(0);
  expect(summary.progress_updates_per_second.median).toBeLessThanOrEqual(1);
  expect(Math.min(...summary.minimum_progress_gap_ms.samples)).toBeGreaterThanOrEqual(900);
});

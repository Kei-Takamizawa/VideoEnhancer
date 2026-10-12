import { _electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);

test("real CUDA engine progress reaches the renderer at the specified cadence", async () => {
  test.skip(!process.env.VE_REAL_ENGINE_HOME, "Requires an isolated live CUDA fixture.");
  test.setTimeout(90000);
  const home = process.env.VE_REAL_ENGINE_HOME!;
  const connection = JSON.parse(readFileSync(path.join(home, "serve.json"), "utf8"));
  const app = await _electron.launch({ executablePath: require("electron"), args: [".", `--user-data-dir=${path.join(home, "desktop-progress")}`], env: { ...process.env, VE_HOME: home } });
  const page = await app.firstWindow();
  try {
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await expect(page.locator(".now-percent")).toBeVisible({ timeout: 40000 });
    const numbers = await page.evaluate(async ({ port, token }) => {
      const paints: number[] = [], events: number[] = [];
      const node = document.querySelector(".now-percent");
      if (!node) throw new Error("The real running job has no progress display.");
      let previous = node.textContent;
      const observer = new MutationObserver(() => { if (node.textContent !== previous) { previous = node.textContent; paints.push(performance.now()); } });
      observer.observe(node, { characterData: true, childList: true, subtree: true });
      const abort = new AbortController();
      const began = performance.now();
      const timer = setTimeout(() => abort.abort(), 30000);
      try {
        const response = await fetch(`http://127.0.0.1:${port}/v1/events`, { headers: { Authorization: `Bearer ${token}` }, signal: abort.signal });
        const reader = response.body!.getReader(); const decoder = new TextDecoder(); let pending = "";
        while (true) {
          const chunk = await reader.read(); if (chunk.done) break; pending += decoder.decode(chunk.value, { stream: true }); let boundary;
          while ((boundary = pending.indexOf("\n\n")) >= 0) { const message = pending.slice(0, boundary); pending = pending.slice(boundary + 2); if (message.startsWith("event: progress")) events.push(performance.now()); }
        }
      } catch (error) { if (!abort.signal.aborted) throw error; }
      finally { clearTimeout(timer); observer.disconnect(); }
      const gaps = events.slice(1).map((value, index) => (value - events[index]) / 1000);
      const paintGaps = paints.slice(1).map((value, index) => value - paints[index]);
      return { event_times_ms: events, event_gaps_seconds: gaps, good_gap_fraction: gaps.filter(value => value >= .9 && value <= 2.1).length / gaps.length, progress_paints_ms: paints, minimum_paint_gap_ms: Math.min(...paintGaps), average_paint_hz: paints.length / ((performance.now() - began) / 1000), observed_seconds: (performance.now() - began) / 1000 };
    }, connection);
    const evidence = process.env.VE_GUI_EVIDENCE!; mkdirSync(evidence, { recursive: true });
    writeFileSync(path.join(evidence, "real-progress.json"), JSON.stringify(numbers, null, 2));
    expect(numbers.event_gaps_seconds.length).toBeGreaterThan(10);
    expect(numbers.good_gap_fraction).toBeGreaterThanOrEqual(.95);
    expect(numbers.average_paint_hz).toBeGreaterThan(0);
    expect(numbers.average_paint_hz).toBeLessThanOrEqual(1);
    expect(numbers.minimum_paint_gap_ms).toBeGreaterThanOrEqual(900);
  } finally {
    // The fixture owns the service lifetime; exit this isolated desktop only.
    await app.evaluate(({ app }) => app.exit(0)).catch(() => {});
    await app.close().catch(() => {});
  }
});

import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");
import { assertPanelFits } from "./clipping";

test("P1e changed screens in both window sizes and themes", async () => {
  test.skip(!process.env.VE_P1E_VISUAL_EVIDENCE, "Opt-in external synthetic visual inventory.");
  test.setTimeout(600000);
  const evidence = process.env.VE_P1E_VISUAL_EVIDENCE!;
  mkdirSync(evidence, { recursive: true });
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `visual-fixture-${Date.now()}`), fixture = await fakeEngine(path.join(root, "home"));
  const modelIds = ["basicvsrpp-ntire21-decompress", "scunet-real-psnr", "drunet-deblock"];
  for (const id of modelIds) fixture.models.push({ ...JSON.parse(readFileSync(path.resolve("../src/videoenhancer/models/manifests", `${id}.json`), "utf8")), builtin: true, weights_verified: true });
  const media: Record<string, Buffer> = {};
  const thumbnail: Record<string, Buffer> = {};
  for (const aspect of ["portrait", "landscape"]) {
    const source = path.join(root, "home", `${aspect}.mp4`);
    execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-f", "lavfi", "-i", `testsrc2=size=${aspect === "portrait" ? "720x1280" : "1280x720"}:rate=30`, "-t", "1", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", source]);
    media[aspect] = readFileSync(source);
    const png = path.join(root, "home", `${aspect}.png`);
    execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-i", source, "-frames:v", "1", "-vf", "scale=266:266:force_original_aspect_ratio=decrease", png]);
    thumbnail[aspect] = readFileSync(png);
  }
  let aspect = "portrait", paneModels = 1, sequence = 0;
  for (const [index, job] of fixture.queue.jobs.entries()) {
    const shape = index % 2 ? "landscape" : "portrait";
    job.media = { ...job.media, display_width: shape === "portrait" ? 720 : 1280, display_height: shape === "portrait" ? 1280 : 720 };
    fixture.routes[`queue/${job.id}/thumbnail`] = thumbnail[shape]; fixture.routes[`media/${job.id}`] = media[shape];
  }
  fixture.queue.jobs[0].preview_ready = true;
  fixture.routes["queue/synthetic-0/preview"] = () => {
    const id = `visual-${++sequence}`, ids = modelIds.slice(0, paneModels);
    for (const name of ["original", ...ids]) fixture.routes[`operations/${id}/files/${name}`] = media[aspect];
    const operation = { id, kind: "compare", state: "done", phase: "Complete", result: { original: `/v1/operations/${id}/files/original`, items: ids.map(model => ({ id: model, name: fixture.models.find((entry: { id: string }) => entry.id === model).catalog.title, preview: `/v1/operations/${id}/files/${model}`, fps: 2.5, projected_whole_file_seconds: 600 })) } };
    fixture.queue.operations = [operation]; fixture.snapshot(); return operation;
  };
  const estimate = { seconds: 600, low: 500, high: 700, calibrated: true, finish: "2026-10-12T18:00:00Z" };
  fixture.routes.estimate = (data: { files: string[] }) => ({ presets: { standard: estimate, fast: estimate }, files: Object.fromEntries(data.files.map(file => [file, file.includes("broken") ? { error: "This video cannot be read.", presets: {}, warnings: [] } : { media: fixture.queue.jobs[0].media, presets: { standard: estimate, fast: estimate }, warnings: [], output: `${file}.output.mp4` }])) });
  fixture.plan.days = [{ date: "2026-10-12", windows: [{ start: "2026-10-12T16:00:00Z", end: "2026-10-13T01:00:00Z" }], run_hours: 9, jobs: [] }];
  fixture.plan.timeline = [{ job_id: "synthetic-0", start: "2026-10-12T16:00:00Z", end: "2026-10-12T19:00:00Z" }];
  const app = await desktop.launch({ executablePath: (process.env.VE_TAURI_EXE || ""), args: ["--force-device-scale-factor=1", ".", `--user-data-dir=${path.join(root, "desktop")}`], env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  const records: object[] = [];
  const visit = (name: string) => page.getByRole("button", { name, exact: true }).click();
  try {
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await app.files(["C:\\synthetic\\portrait.mp4", "C:\\synthetic\\landscape.mp4"]);
    for (const [width, height] of [[1280, 800], [1100, 700]]) {
      await (async (size) => app.setContentSize(size[0], size[1]))([width, height]);
      for (const theme of ["dark", "light"]) {
        await visit("Settings"); await page.getByLabel("Theme").selectOption(theme);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        const shot = async (name: string) => {
          await page.waitForTimeout(100); await assertPanelFits(page);
          const file = path.join(evidence, `${name}-${width}x${height}-${theme}.png`);
          const raw = await (async () => (await app.capturePage()).toString("base64"))();
          writeFileSync(file, Buffer.from(raw, "base64"));
          records.push({ name, width, height, theme, path: file }); writeFileSync(path.join(evidence, "inventory.json"), JSON.stringify(records, null, 2));
        };
        await visit("Home"); await shot("home");
        await page.getByRole("button", { name: "Add videos" }).click(); await expect(page.getByRole("button", { name: "Add to queue" })).toBeEnabled(); await shot("add"); await page.getByRole("button", { name: "Close", exact: true }).click();
        await app.files(["C:\\synthetic\\broken.mp4", "C:\\synthetic\\portrait.mp4"]);
        await page.getByRole("button", { name: "Add videos" }).click(); await expect(page.getByText("This video cannot be read.")).toBeVisible(); await page.getByText("This video cannot be read.").scrollIntoViewIfNeeded(); await shot("add-error"); await page.getByRole("button", { name: "Close", exact: true }).click();
        await app.files(["C:\\synthetic\\portrait.mp4", "C:\\synthetic\\landscape.mp4"]);
        await visit("History"); await shot("history"); await page.getByRole("button", { name: "Select", exact: true }).click(); await page.locator(".history-image").first().click(); await shot("history-select"); await page.getByRole("button", { name: "Cancel", exact: true }).click();
        await page.locator(".history-image").first().click(); await shot("history-popup"); await page.getByRole("button", { name: "Close", exact: true }).click();
        await page.getByRole("button", { name: "Select", exact: true }).click(); await page.locator(".history-image").first().click(); await page.getByRole("button", { name: "Remove from history", exact: true }).click(); await shot("history-removal"); await page.getByRole("dialog", { name: "Remove records or video files?" }).getByRole("button", { name: "Cancel", exact: true }).click(); await page.getByRole("button", { name: "Cancel", exact: true }).click();
        await visit("Models"); if (width === 1280) expect(await page.locator(".model-card").evaluateAll(nodes => Math.max(...nodes.map(node => node.getBoundingClientRect().height)))).toBeLessThanOrEqual(120); await shot("models"); await page.getByRole("button", { name: `Details for ${fixture.models[0].catalog.title}` }).click(); await shot("models-popup"); await page.getByRole("button", { name: "Close", exact: true }).click();
        fixture.queue.operations = [{ id: "download", kind: "download", state: "running", phase: "Downloading", percent: 42, remaining_seconds: 60, request: { model_id: modelIds[1] } }]; fixture.snapshot(); await shot("models-downloading"); fixture.queue.operations = []; fixture.snapshot();
        await visit("Schedule"); await page.getByRole("switch", { name: "Work only during these hours" }).check(); await shot("schedule-on"); await page.getByRole("switch", { name: "Work only during these hours" }).uncheck(); await shot("schedule-off");
        await visit("Settings"); fixture.queue.operations = [{ id: "calibration", kind: "calibrate", state: "running", phase: "Installed models", percent: 48, remaining_seconds: 180 }]; fixture.snapshot(); await shot("settings-calibration");
        await page.getByRole("button", { name: "Tutorial" }).click(); await shot("tour"); await page.getByRole("button", { name: "Skip", exact: true }).click();
        await visit("Home");
        for (const shape of ["portrait", "landscape"]) for (const models of [1, 3]) {
          aspect = shape; paneModels = models; await page.getByRole("button", { name: "Preview result" }).click();
          await expect(page.getByLabel("Original and enhanced synchronized preview")).toHaveAttribute("data-frame", "0");
          const canvas = page.getByLabel("Original and enhanced synchronized preview");
          const labels = page.locator(".compare-labels");
          await expect(labels).toBeVisible();
          await expect(labels.locator("strong")).toHaveCount(models + 1);
          expect(await labels.evaluate(element => element.getBoundingClientRect().bottom)).toBeLessThanOrEqual(await canvas.evaluate(element => element.getBoundingClientRect().top));
          const dimensions = await canvas.evaluate(element => { const box = element.getBoundingClientRect(); return { tile_width: box.width / Number(element.dataset.columns), tile_height: box.height / Number(element.dataset.rows), columns: element.dataset.columns, rows: element.dataset.rows }; });
          records.push({ name: `compare-${shape}-${models}-dimensions`, width, height, theme, ...dimensions });
          await shot(`compare-${shape}-${models}`);
          if (models === 1) {
            if (shape === "portrait") expect(dimensions.tile_height).toBeGreaterThanOrEqual(height === 800 ? 560 : 480);
            else if (width === 1280) expect(dimensions.tile_width).toBeGreaterThanOrEqual(590);
          }
          await page.getByRole("button", { name: "Full window", exact: true }).click();
          await expect(labels).toBeVisible();
          expect(await labels.evaluate(element => element.getBoundingClientRect().top)).toBeGreaterThanOrEqual(0);
          expect(await labels.evaluate(element => element.getBoundingClientRect().bottom)).toBeLessThanOrEqual(await canvas.evaluate(element => element.getBoundingClientRect().top));
          await shot(`compare-${shape}-${models}-full`); await page.locator(".compare").press("Escape");
          await page.getByRole("button", { name: "Close", exact: true }).click();
        }
        await visit("Models"); fixture.models.push(null); fixture.queue.operations = [{ id: `error-${width}-${theme}`, kind: "verify", state: "done", phase: "Complete" }]; fixture.snapshot();
        await expect(page.getByRole("heading", { name: "Something went wrong on this screen" })).toBeVisible(); await shot("screen-error");
        fixture.models.pop(); fixture.queue.operations = []; fixture.snapshot(); await page.getByRole("button", { name: "Reload", exact: true }).click({ noWaitAfter: true }); await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible({ timeout: 30000 });
      }
    }
  } finally { await app.close(); await fixture.close(); }
});

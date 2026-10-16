import { _electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

test("packaged design board inventory with isolated synthetic API data", async () => {
  test.skip(!process.env.VE_GUI_PACKAGE_EXE, "Opt-in packaged visual inventory.");
  test.setTimeout(600000);
  const root = path.resolve("test-results", `boards-${Date.now()}`);
  const evidence = path.join(process.env.VE_GUI_EVIDENCE!, "boards");
  mkdirSync(root, { recursive: true }); mkdirSync(evidence, { recursive: true });
  const source = path.join(root, "synthetic-one.mp4"), second = path.join(root, "synthetic-two.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "10", "-c:v", "libx264", "-threads", "2", source]); copyFileSync(source, second);
  const fixture = await fakeEngine(path.join(root, "home"));
  const initialJobs = JSON.parse(JSON.stringify(fixture.queue.jobs.slice(0, 15)));
  for (const job of initialJobs.slice(1, 11)) job.segment = 0;
  const initialSettings = { ...fixture.settings }, initialHealth = { ...fixture.health };
  const modelIds = ["basicvsrpp-ntire21-decompress", "scunet-real-psnr", "rife-4.25"];
  const catalog = modelIds.map(id => ({ ...JSON.parse(readFileSync(path.resolve("../src/videoenhancer/models/manifests", `${id}.json`), "utf8")), builtin: true, weights_verified: true }));
  fixture.models.push(...catalog);
  const presets = { standard: { seconds: 500, low: 375, high: 625, calibrated: false }, fast: { seconds: 60, low: 45, high: 75, calibrated: false } };
  let estimating = false;
  let warnings: string[] = [], compareFailure = false, delayed = false, queueCalls = 0, partial = false;
  fixture.routes.estimate = async (data: { files: string[] }) => { if (estimating) await new Promise(resolve => setTimeout(resolve, 10000)); return ({ presets, files: Object.fromEntries(data.files.map(file => [file, { media: initialJobs[0].media, presets, warnings, output: `${file}.output.mp4` }])) }); };
  const thumbnailPath = path.join(root, "synthetic-thumbnail.png");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-i", source, "-frames:v", "1", "-vf", "scale=120:68", thumbnailPath]);
  const thumbnail = readFileSync(thumbnailPath);
  fixture.routes["trial/thumbnails"] = { duration: 10, thumbnails: Array(8).fill(`data:image/png;base64,${thumbnail.toString("base64")}`) };
  for (const job of initialJobs) fixture.routes[`queue/${job.id}/thumbnail`] = thumbnail;
  fixture.plan.days = Array.from({ length: 7 }, (_, index) => ({ date: `2026-10-${12 + index}`, windows: index < 5 ? [{ start: `2026-10-${12 + index}T16:00:00Z`, end: `2026-10-${13 + index}T01:00:00Z` }] : [], run_hours: index < 5 ? 9 : 0, jobs: [] }));
  fixture.plan.timeline = [{ job_id: "synthetic-0", start: "2026-10-12T16:00:00Z", end: "2026-10-12T19:00:00Z" }];
  fixture.routes["compare/range"] = { start: 2 };
  const video = readFileSync(source);
  for (const name of ["original", "enhanced", modelIds[0]]) fixture.routes[`operations/visual/files/${name}`] = video;
  const comparison = () => ({ id: "visual", kind: "compare", state: compareFailure ? "failed" : "done", error: compareFailure ? "Synthetic preview failed. Try again." : undefined, request: { file: source }, phase: "Complete", result: { original: "/v1/operations/visual/files/original", items: compareFailure ? [] : [{ id: modelIds[0], name: "Gentle cleanup", preview: `/v1/operations/visual/files/${modelIds[0]}`, fps: 2.47, projected_whole_file_seconds: 500 }] } });
  fixture.routes.compare = () => { const operation = comparison(); fixture.queue.operations = [operation]; return operation; };
  fixture.routes["queue/synthetic-0/preview"] = () => { const operation = { id: "visual", kind: "result-preview", state: "done", result: { preview: { original: "/v1/operations/visual/files/original", enhanced: "/v1/operations/visual/files/enhanced" } } }; fixture.queue.operations = [operation]; return operation; };
  fixture.routes.queue = async (_: unknown, method: string) => {
    if (method === "GET") return fixture.queue;
    if (delayed) await new Promise(resolve => setTimeout(resolve, 5000));
    queueCalls++; return partial && queueCalls > 1 ? { statusCode: 400, error: "Synthetic second file could not be added." } : { id: "added" };
  };
  fixture.routes["queue/synthetic-0/details"] = { text: "Synthetic job log. No owner footage was used." };
  fixture.routes["history/remove"] = (data: { ids: string[] }) => {
    fixture.queue.jobs = fixture.queue.jobs.filter((job: { id: string }) => !data.ids.includes(job.id));
    return { ids: data.ids, files: { moved: 0, not_found: 0, kept: 0 }, kept: [] };
  };
  const app = await _electron.launch({ executablePath: process.env.VE_GUI_PACKAGE_EXE!, args: ["--force-device-scale-factor=1", `--user-data-dir=${path.join(root, "desktop")}`], env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  page.setDefaultTimeout(7000);
  await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible({ timeout: 40000 });
  await app.evaluate(({ dialog }, files) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: files }); }, [source, second]);
  const inventory = readFileSync(path.resolve("../design/p1d/README.md"), "utf8").split("\n").filter(line => /^\| \d+ \|/.test(line)).map(line => { const parts = line.split("|").map(part => part.trim()); return { number: Number(parts[1]), name: parts[2], component: parts[3], variant: parts[4], theme: parts[5] }; });
  const filter = process.env.VE_GUI_BOARD_IDS?.split(",").map(Number);
  const results: { number: number; name: string; paths?: string[]; error?: string }[] = filter ? JSON.parse(readFileSync(path.join(evidence, "inventory.json"), "utf8")).filter((row: { number: number }) => !filter.includes(row.number)) : [];
  const click = (name: string) => page.getByRole("button", { name, exact: true }).click();
  try {
    for (const board of inventory.filter(board => !filter || filter.includes(board.number))) {
      try {
        Object.assign(fixture.settings, initialSettings, { theme: board.theme, tray_explained: board.variant !== "tray" });
        delete fixture.routes.models;
        delete fixture.routes["queue/synthetic-0/pause"];
        Object.assign(fixture.health, initialHealth); fixture.control.events = true;
        fixture.queue.jobs = JSON.parse(JSON.stringify(initialJobs)); fixture.queue.operations = [];
        fixture.models.splice(0, fixture.models.length, ...JSON.parse(JSON.stringify(catalog)));
        estimating = board.variant === "one";
        warnings = []; delayed = false; partial = false; queueCalls = 0; compareFailure = board.variant === "failed" && board.component === "Compare";
        if (board.variant === "empty") fixture.queue.jobs = [];
        if (board.variant === "long") fixture.queue.jobs = JSON.parse(JSON.stringify(initialJobs.concat(initialJobs.slice(1, 11).map((job: { id: string }) => ({ ...job, id: `${job.id}-long` })))));
        if (board.variant === "waiting") { fixture.queue.jobs[0].state = "queued"; fixture.health.engine_state = "Waiting for your hours"; }
        if (board.variant === "finishing") { fixture.queue.jobs[0].phase = "finalizing"; fixture.queue.jobs[0].step = "validating"; fixture.queue.jobs[0].step_percent = 45; }
        if (board.variant === "problem" || board.variant === "failed" && board.component === "History") { fixture.queue.jobs[11].state = "failed"; fixture.queue.jobs[11].error = "Synthetic file was locked. Close the player and retry."; }
        if (board.variant === "notFound") { fixture.queue.jobs[11].output_state = "missing"; fixture.queue.jobs[11].original_state = "recycled"; }
        if (board.variant === "sac") fixture.health.smart_app_control = { blocked: true, message: "Synthetic Smart App Control block", status: "enforced" };
        if (board.variant === "fast") fixture.settings.preset = "fast";
        if (board.variant === "connecting") fixture.control.events = false;
        if (board.variant === "licence") fixture.models[0].weights_verified = false;
        fixture.schedule.enabled = board.variant !== "off";
        fixture.schedule.override_until = board.variant === "override" ? new Date(Date.now() + 3600000).toISOString() : null;
        fixture.health.av1_supported = board.variant != "optionsNoAv1";
        await app.evaluate(({ dialog }, files) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: files }); }, board.variant === "one" ? [source] : [source, second]);
        await app.evaluate(({ BrowserWindow }) => { const window = BrowserWindow.getAllWindows()[0]; window.show(); window.webContents.setZoomFactor(1); });
        await app.evaluate(async ({ BrowserWindow }) => { await BrowserWindow.getAllWindows()[0].loadURL("app://videoenhancer/"); });
        await page.waitForTimeout(250);
        if (board.variant === "connecting") await expect(page.getByRole("heading", { name: "Connecting to the engine…" })).toBeVisible();
        else await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
        if (board.component === "AddVideos") {
          if (board.variant === "warnings") warnings = ["Output too small for cleanup", "Output too small for AV1", "Insufficient space", "HDR is not supported", "Windows Smart App Control is blocking"];
          await click("Add videos");
          if (["options", "optionsNoAv1"].includes(board.variant)) await page.getByText("More options", { exact: true }).click();
          if (["busy", "partial"].includes(board.variant)) { delayed = board.variant === "busy"; partial = board.variant === "partial"; await expect(page.getByRole("button", { name: "Add to queue" })).toBeEnabled(); await click("Add to queue"); if (partial) await expect(page.getByRole("alert")).toBeVisible(); }
        } else if (board.component === "History") {
          await click("History");
          if (board.variant === "noMatch") await page.getByLabel("Search by file name").fill("no synthetic match");
          if (board.variant === "select") { await click("Select"); await page.locator('.history-image').first().click(); }
          if (board.variant === "deleteFiles") { await page.locator('.history-image').first().click(); await click("Delete video files…"); }
          if (board.variant === "clear") { await click("Select"); await click("Select all"); await click("Remove from history"); }
          if (board.variant === "toast") { await page.locator('.history-image').first().click(); await click("Remove from history"); await page.getByRole("dialog").getByRole("button", { name: "Remove selected items", exact: true }).click(); await expect(page.getByRole("button", { name: "Undo", exact: true })).toBeVisible(); }
        } else if (board.component === "Schedule") {
          await click("Schedule");
          if (board.variant === "addDay") await click("Add a day");
          if (board.variant === "runUntil") await page.getByLabel("Run now until a time…").fill("2026-10-12T18:00");
        } else if (board.component === "Models") {
          await click("Models");
          if (board.variant === "licence") await page.getByRole("button", { name: "Install", exact: true }).first().click();
          if (board.variant === "details") await page.getByRole("button", { name: "Details for Gentle cleanup", exact: true }).click();
          if (board.variant === "remove") await page.getByRole("button", { name: `Details for ${catalog[1].catalog.title}`, exact: true }).getByRole("button", { name: "Uninstall", exact: true }).click();
        } else if (board.component === "Settings") { await click("Settings"); if (board.variant === "advanced") await page.getByText("Advanced", { exact: true }).click();
        } else if (board.component === "Compare") {
          await click("Models"); await click("Compare on my video"); await expect(page.getByRole("heading", { name: /Compare models/ })).toBeVisible();
          if (board.variant !== "fast") await expect(page.locator('canvas')).toHaveAttribute('data-frame', /\d+/);
          if (board.variant === "swipe") await page.getByLabel("Side by side").uncheck();
        } else if (board.component === "Main") {
          if (["menu", "confirmCancel", "confirmRemove", "log", "actionError"].includes(board.variant)) { await page.getByRole("button", { name: board.variant === "confirmRemove" ? "Actions for video-1.mp4" : "Actions for video-0.mp4", exact: true }).click(); if (board.variant === "confirmCancel") await click("Cancel"); if (board.variant === "confirmRemove") await click("Remove from queue"); if (board.variant === "log") await click("Show log"); if (board.variant === "actionError") { fixture.routes['queue/synthetic-0/pause'] = { statusCode: 400, error: "Synthetic action failed." }; await page.locator(".row-menu").getByRole("button", { name: "Pause", exact: true }).click(); } }
          if (board.variant === "drop") await page.locator('.app').evaluate(element => { const dataTransfer = new DataTransfer(); dataTransfer.items.add(new File(['synthetic'], 'synthetic.mp4')); element.dispatchEvent(new DragEvent('dragenter', { bubbles: true, dataTransfer })); });
          if (board.variant === "zoom") await page.keyboard.press("Control+=");
          if (board.variant === "preview") { fixture.queue.jobs[0].preview_ready = true; fixture.snapshot(); await expect(page.getByRole("button", { name: "Preview result" })).toBeEnabled(); await click("Preview result"); }
          if (board.variant === "tray") { await page.waitForTimeout(3200); await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].close()); await expect(page.getByRole("heading", { name: "VideoEnhancer keeps working in the tray" })).toBeVisible(); }
          if (board.variant === "reconnecting") { fixture.control.events = false; fixture.disconnect(); await expect(page.locator(".connection.card").filter({ hasText: "Reconnecting" })).toBeVisible(); }
          if (board.variant === "unreachable") { fixture.control.events = false; fixture.routes.models = { statusCode: 503, error: "Synthetic engine is unreachable." }; await page.evaluate(() => window.dispatchEvent(new Event("focus"))); await expect(page.getByRole('heading', { name: "Can’t reach the engine" })).toBeVisible(); }
        }
        const paths: string[] = [];
        for (const [width, height] of [[1280, 800], [1100, 700]]) {
          await app.evaluate(({ BrowserWindow }, size) => BrowserWindow.getAllWindows()[0].setContentSize(size[0], size[1]), [width, height]);
          await page.waitForTimeout(150);
          const file = path.join(evidence, `${String(board.number).padStart(2, "0")}-${board.component}-${board.variant}-${board.theme}-${width}x${height}.png`);
          const png = await app.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].capturePage()).toPNG().toString("base64"));
          writeFileSync(file, Buffer.from(png, "base64")); paths.push(file);
        }
        results.push({ number: board.number, name: board.name, paths });
      } catch (error) { results.push({ number: board.number, name: board.name, error: (error as Error).message }); }
      writeFileSync(path.join(evidence, "inventory.json"), JSON.stringify(results, null, 2));
    }
    expect(results.filter(board => board.error)).toEqual([]);
    delete fixture.routes.models;
    fixture.control.events = true;
    fixture.models[0].weights_verified = false;
    fixture.queue.operations = [{ id: "download", kind: "download", state: "running", phase: "12 MB of 40 MB", percent: 30, request: { model_id: modelIds[0] } }];
    fixture.snapshot();
    await app.evaluate(async ({ BrowserWindow }) => { const window = BrowserWindow.getAllWindows()[0]; window.show(); await window.loadURL("app://videoenhancer/"); });
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await click("Models");
    await expect(page.getByRole("button", { name: "Installing Gentle cleanup", exact: true })).toBeVisible();
    await expect(page.getByRole("progressbar", { name: "Downloading Gentle cleanup", exact: true })).toHaveAttribute("value", "30");
    for (const [width, height] of [[1280, 800], [1100, 700]]) {
      await app.evaluate(({ BrowserWindow }, size) => BrowserWindow.getAllWindows()[0].setContentSize(size[0], size[1]), [width, height]);
      const png = await app.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].capturePage()).toPNG().toString("base64"));
      writeFileSync(path.join(evidence, `derived-Models-downloading-dark-${width}x${height}.png`), Buffer.from(png, "base64"));
    }

  } finally { await app.close(); await fixture.close(); }
});

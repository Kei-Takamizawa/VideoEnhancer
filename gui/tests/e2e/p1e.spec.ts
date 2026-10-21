import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync, spawn } from "node:child_process";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

async function launch(hidden = false) {
  const root = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1t/e2e", `p1e-${Date.now()}`);
  const fixture = await fakeEngine(path.join(root, "home"));
  const estimate = { seconds: 120, low: 100, high: 150, calibrated: true };
  let estimateCalls = 0;
  fixture.routes.estimate = (data: { files: string[] }) => {
    estimateCalls++;
    return { files: Object.fromEntries(data.files.map(file => [file, { media: fixture.queue.jobs[0].media, presets: { standard: estimate, fast: estimate }, warnings: [], output: `${file}.output.mp4` }])), presets: { standard: estimate, fast: estimate } };
  };
  const app = await desktop.launch({ executablePath: (process.env.VE_TAURI_EXE || ""), cwd: path.resolve(import.meta.dirname, "../.."), args: [".", `--user-data-dir=${path.join(root, "desktop")}`, ...(hidden ? ["--hidden"] : [])], env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  await (async () => app.setContentSize(1280, 800))();
  await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
  return { root, fixture, app, page, estimateCalls: () => estimateCalls, close: async () => { await app.close(); await fixture.close(); } };
}

test("P1t hidden startup stays hidden until explicitly opened", async () => {
  const state = await launch(true);
  try {
    await state.page.waitForTimeout(300);
    expect(await state.app.isVisible()).toBe(false);
    await state.app.show();
    await expect.poll(() => state.app.isVisible()).toBe(true);
  } finally { await state.close(); }
});

test("P1t queue reorders through pointer capture and Alt+Arrow", async () => {
  const state = await launch();
  const { page, fixture } = state;
  const moves: { id: string; position: number }[] = [];
  fixture.routes["queue/synthetic-1/move"] = (data: { position: number }) => {
    moves.push({ id: "synthetic-1", position: data.position });
    const moved = fixture.queue.jobs.find((job: { id: string }) => job.id === "synthetic-1");
    fixture.queue.jobs = fixture.queue.jobs.filter((job: { id: string }) => job.id !== moved.id);
    fixture.queue.jobs.splice(data.position - 1, 0, moved);
    fixture.queue.jobs.forEach((job: { position: number }, index: number) => { job.position = index + 1; });
    fixture.snapshot();
    return {};
  };
  try {
    const rows = page.locator(".next-row");
    await rows.nth(1).scrollIntoViewIfNeeded();
    const first = await rows.nth(0).boundingBox(), second = await rows.nth(1).boundingBox();
    if (!first || !second) throw new Error("Queue rows missing");
    await page.mouse.move(first.x + 8, first.y + first.height / 2);
    await page.mouse.down();
    await page.mouse.move(second.x + 8, second.y + second.height / 2, { steps: 12 });
    await page.mouse.up();
    await expect.poll(() => moves).toEqual([{ id: "synthetic-1", position: 3 }]);
    await expect(rows.nth(0)).toHaveAttribute("data-job-id", "synthetic-2");
    await expect(rows.nth(1)).toHaveAttribute("data-job-id", "synthetic-1");
    await page.locator('.next-row[data-job-id="synthetic-1"]').focus();
    await page.keyboard.press("Alt+ArrowUp");
    await expect.poll(() => moves.length).toBe(2);
    expect(moves[1]).toEqual({ id: "synthetic-1", position: 2 });
    await expect(rows.nth(0)).toHaveAttribute("data-job-id", "synthetic-1");
  } finally { await state.close(); }
});

test("P1t single instance, zoom shortcuts, fullscreen restoration and command limits", async () => {
  const state = await launch();
  const { page, app, fixture, root } = state;
  try {
    await app.hide();
    await expect.poll(() => app.isVisible()).toBe(false);
    const second = spawn(app.process().spawnfile, [], { windowsHide: true, stdio: "ignore", env: { ...process.env, VE_HOME: path.join(root, "home"), APPDATA: path.join(root, "desktop/roaming"), LOCALAPPDATA: path.join(root, "desktop/local"), WEBVIEW2_USER_DATA_FOLDER: path.join(root, "desktop") } });
    await expect.poll(() => second.exitCode, { timeout: 10000 }).toBe(0);
    await expect.poll(() => app.isVisible()).toBe(true);
    await page.keyboard.press("Control+Equal");
    await expect.poll(() => fixture.settings.zoom).toBe(110);
    await page.keyboard.press("Control+Numpad0");
    await expect.poll(() => fixture.settings.zoom).toBe(100);
    const before = await page.evaluate(() => devicePixelRatio);
    await page.keyboard.down("Control"); await page.mouse.wheel(0, -300); await page.keyboard.up("Control");
    await page.waitForTimeout(300);
    expect(await page.evaluate(() => devicePixelRatio)).toBe(before);
    await expect(page.evaluate(() => window.desktop.zoom(77))).rejects.toThrow();
    await expect(page.evaluate(() => window.desktop.openExternal!("https://evil.invalid/"))).rejects.toThrow();
    await expect(page.evaluate(() => window.desktop.play("relative.mp4"))).rejects.toThrow();
    await expect(page.evaluate(() => window.desktop.copy("x".repeat(100001)))).rejects.toThrow();
    await page.evaluate(() => window.desktop.copy("P1t synthetic clipboard"));
    expect(await app.clipboardText()).toBe("P1t synthetic clipboard");
    await page.evaluate(() => window.desktop.logRendererError!("x".repeat(64010)));
    expect(readFileSync(path.join(root, "home/renderer-errors.log"), "utf8").trimEnd()).toHaveLength(64000);
    const bounds = await app.command<{ width: number; height: number; x: number; y: number }>("state");
    await page.evaluate(() => document.documentElement.requestFullscreen());
    await expect.poll(() => app.isFullScreen()).toBe(true);
    await page.keyboard.press("Escape");
    await expect.poll(() => app.isFullScreen()).toBe(false);
    const restored = await app.command<typeof bounds>("state");
    for (const key of ["width", "height", "x", "y"] as const) expect(restored[key]).toBe(bounds[key]);
  } finally { await state.close(); }
});

test("P1t refused shutdown restores the window and shows Retry Quit", async () => {
  const state = await launch();
  const { page, app, fixture } = state;
  try {
    fixture.routes.shutdown = { statusCode: 409, error: "Synthetic shutdown refusal." };
    await app.hide();
    await expect.poll(() => app.isVisible()).toBe(false);
    await app.quit();
    await expect.poll(() => app.isVisible()).toBe(true);
    await expect(page.getByText(/The engine could not stop cleanly\. Retry Quit\./)).toBeVisible();
    expect(app.process().exitCode).toBeNull();
  } finally { await state.close(); }
});

test("P1e modal drop, independent Add fields and paused queue order", async () => {
  const state = await launch(); const { page, app, fixture } = state;
  try {
    await app.files(["C:\\synthetic\\one.mp4"]);
    await page.getByRole("button", { name: "Add videos" }).click();
    await expect(page.getByText("Checking…")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add to queue" })).toBeEnabled();
    const before = state.estimateCalls();
    await page.getByRole("checkbox", { name: "Delete the original when it is done" }).check();
    await page.waitForTimeout(600);
    expect(state.estimateCalls()).toBe(before);
    await app.command("drop", {type:"drop",paths:["C:\\synthetic\\drop.mp4"]});
    await expect(page.getByText("Close the dialog first to add videos.")).toBeVisible();
    expect(await page.getByRole("dialog").count()).toBe(1);
    await page.getByRole("button", { name: "Close", exact: true }).click();
    const current = await page.locator(".now-card h2").textContent();
    fixture.routes.processing = (data: { paused: boolean }) => { fixture.health.paused_all = data.paused; fixture.health.engine_state = data.paused ? "Paused" : "Working"; fixture.snapshot(); return { paused: data.paused }; };
    await page.getByRole("button", { name: "Pause all", exact: true }).click();
    await expect(page.getByRole("button", { name: "Resume all", exact: true })).toBeVisible();
    expect(await page.locator(".now-card h2").textContent()).toBe(current);
    await expect(page.getByText(/Finished parts are kept/)).toBeVisible();
  } finally { await state.close(); }
});

test("P1e History select, guarded remove choices, Select all and Undo", async () => {
  const state = await launch(); const { page, fixture } = state;
  let hidden: unknown[] = [], deletion: unknown;
  const remove = (data: { ids?: string[]; output?: boolean; original?: boolean }, clear = false) => {
    const ids = clear ? fixture.queue.jobs.filter((job: { state: string }) => job.state === "done").map((job: { id: string }) => job.id) : data.ids;
    hidden = fixture.queue.jobs.filter((job: { id: string }) => ids.includes(job.id));
    fixture.queue.jobs = fixture.queue.jobs.filter((job: { id: string }) => !ids.includes(job.id)); fixture.queue.history_revision = String(Date.now()); fixture.snapshot(); deletion = data;
    return { ids, files: { moved: data.output ? ids.length : 0, not_found: 0, kept: 0 }, kept: [] };
  };
  fixture.routes["history/remove"] = (data: { ids: string[] }) => remove(data);
  fixture.routes["history/clear"] = (data: object) => remove(data, true);
  fixture.routes["history/undo"] = () => { fixture.queue.jobs.push(...hidden); hidden = []; fixture.queue.history_revision = String(Date.now()); fixture.snapshot(); return {}; };
  try {
    await page.getByRole("button", { name: "History", exact: true }).click();
    expect(await page.locator(".history-card input[type=checkbox]").count()).toBe(0);
    await page.getByRole("button", { name: "Select", exact: true }).click();
    await page.locator(".history-image").first().click();
    await expect(page.getByText("1 selected", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Remove from history", exact: true }).click();
    const option = page.getByRole("checkbox", { name: "Move the finished videos to the Recycle Bin" });
    await expect(option).not.toBeChecked(); await option.check();
    await page.getByRole("dialog").getByRole("button", { name: "Remove selected items", exact: true }).click();
    await expect(page.getByText(/Files are in the Recycle Bin/)).toBeVisible();
    expect(deletion).toMatchObject({ output: true, original: false });
    await page.locator(".undo-toast").hover(); const width = await page.locator(".undo-tint").evaluate(node => node.getBoundingClientRect().width);
    await page.waitForTimeout(300); expect(await page.locator(".undo-tint").evaluate(node => node.getBoundingClientRect().width)).toBe(width);
    await page.locator(".undo-toast").getByRole("button", { name: "Undo" }).click();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(page.getByRole("button", { name: "Clear history…" })).toHaveCount(0);
    await page.getByRole("button", { name: "Select", exact: true }).click();
    await page.getByRole("button", { name: "Select all", exact: true }).click();
    await page.getByRole("button", { name: "Remove from history", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Remove selected items", exact: true }).click();
    await expect(page.getByText("No history yet.")).toBeVisible();
    await page.locator(".undo-toast").getByRole("button", { name: "Undo" }).click();
    await expect(page.locator(".history-image").first()).toBeVisible();
  } finally { await state.close(); }
});

test("P1e hours remain editable and Models card opens its details", async () => {
  const state = await launch(); const { page, fixture } = state;
  fixture.plan.days = [{ date: "2026-10-12", windows: [{ start: "2026-10-12T16:00:00Z", end: "2026-10-13T01:00:00Z" }], run_hours: 9, jobs: [] }];
  fixture.models.push({ id: "fixture-model", display_name: "Fixture model", architecture: "spandrel", task: "restore", builtin: true, licence: "MIT", weights_verified: false, weights: { sha256: "a".repeat(64), url: "https://example.invalid/fixture" }, catalog: { category: "cleanup", title: "Fixture model", summary: "Synthetic model for UI tests", look_change: "very_little", invents_detail: "low", flicker: "possible" } });
  fixture.queue.operations.push({ id: "model-refresh", kind: "verify", state: "done", phase: "Complete" }); fixture.snapshot();
  try {
    await page.getByRole("button", { name: "Schedule", exact: true }).click();
    await expect.poll(() => page.locator(".hours-block").first().evaluate(node => node.getBoundingClientRect().height)).toBeGreaterThan(0);
    await page.getByRole("switch", { name: "Work only during these hours" }).uncheck();
    await expect(page.getByLabel("Hours 1 start", { exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Models", exact: true }).click();
    await page.getByRole("button", { name: "Details for Fixture model" }).click();
    await expect(page.getByRole("dialog", { name: "Model details" })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.getByRole("button", { name: "Install", exact: true })).toBeVisible();
    fixture.models[0].weights_verified = true; fixture.queue.operations.push({ id: "model-installed", kind: "download", state: "done", phase: "Complete" }); fixture.snapshot();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByRole("button", { name: "Models", exact: true }).click();
    await expect(page.getByRole("button", { name: "Uninstall", exact: true })).toBeVisible();
  } finally { await state.close(); }
});

test("P1e Compare wheel gestures, full window and steady counters", async () => {
  const state = await launch(); const { page, fixture, root } = state;
  try {
    const videoPath = path.join(root, "home", "synthetic.mp4"); mkdirSync(root, { recursive: true });
    execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30", "-t", "3", "-c:v", "libx264", "-threads", "2", videoPath]);
    const video = readFileSync(videoPath);
    for (const name of ["original", "enhanced"]) fixture.routes[`operations/wheel/files/${name}`] = video;
    const operation = { id: "wheel", kind: "result-preview", state: "done", phase: "Complete", result: { preview: { original: "/v1/operations/wheel/files/original", enhanced: "/v1/operations/wheel/files/enhanced" } } };
    fixture.queue.jobs[0].preview_ready = true; fixture.snapshot();
    fixture.routes["queue/synthetic-0/preview"] = () => { fixture.queue.operations = [operation]; fixture.snapshot(); return operation; };
    await page.getByRole("button", { name: "Preview result" }).click();
    const canvas = page.getByLabel("Original and enhanced synchronized preview");
    await expect(canvas).toHaveAttribute("data-frame", "0");
    const bounds = (await page.locator(".canvas-viewport").boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Input.synthesizePinchGesture", { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2, scaleFactor: 1.5, gestureSourceType: "mouse" });
    const nativePinchStyle = await canvas.getAttribute("style");
    writeFileSync(path.join(root, "webview2-pinch-probe.json"), JSON.stringify({nativePinchStyle, note:"CDP synthesized pinch is not physical touchpad evidence."}));
    await cdp.send("Input.dispatchMouseEvent", {type:"mouseWheel", x:bounds.x+bounds.width/2,y:bounds.y+bounds.height/2,deltaX:0,deltaY:-40,modifiers:2});
    await cdp.detach();
    await expect(page.getByRole("button", {name:"Reset zoom",exact:true})).not.toHaveText("100%");
    const before = await canvas.getAttribute("style");
    await page.locator(".canvas-viewport").dispatchEvent("wheel", { deltaX: 40, deltaY: 20 });
    await expect.poll(() => canvas.getAttribute("style")).not.toBe(before);
    await page.getByRole("checkbox", { name: "Side by side" }).uncheck();
    await page.getByRole("button", { name: "Reset zoom", exact: true }).click();
    const split = await page.getByRole("slider", { name: "Comparison split" }).inputValue();
    await page.locator(".canvas-viewport").dispatchEvent("wheel", { deltaX: 50, deltaY: 0 });
    await expect.poll(() => page.getByRole("slider", { name: "Comparison split" }).inputValue()).not.toBe(split);
    await page.getByRole("button", { name: "Full window", exact: true }).click();
    await expect(page.locator(".compare")).toHaveClass(/is-full-window/);
    await page.locator(".compare").press("Escape");
    await expect(page.locator(".compare")).not.toHaveClass(/is-full-window/);
    const sibling = page.getByRole("checkbox", { name: "Side by side" });
    const x = (await sibling.boundingBox())!.x;
    await page.getByRole("button", { name: "Play preview" }).click(); await page.waitForTimeout(1200);
    expect((await sibling.boundingBox())!.x).toBe(x);
    writeFileSync(path.join(root, "counter-measurement.json"), JSON.stringify({ sibling_movement_px: 0 }));
  } finally { await state.close(); }
});

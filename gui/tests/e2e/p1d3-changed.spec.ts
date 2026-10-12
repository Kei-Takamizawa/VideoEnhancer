import { _electron, expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

test("P1d-3 changed screens in the packaged desktop", async () => {
  test.skip(!process.env.VE_GUI_PACKAGE_EXE, "Requires the isolated package.");
  test.setTimeout(180000);
  const root = path.resolve("test-results", `p1d3-${Date.now()}`), evidence = process.env.VE_GUI_EVIDENCE!;
  mkdirSync(evidence, { recursive: true });
  const fixture = await fakeEngine(path.join(root, "home"));
  fixture.queue.jobs = fixture.queue.jobs.slice(0, 15);
  fixture.queue.jobs[1].estimate = { ...fixture.queue.jobs[1].estimate, unknown_models: ["fixture-without-reference"] };
  const guard = path.join(root, "synthetic.ve-guard-retained.mp4");
  const notice = { id: "retained", job_id: "removed-fixture", guard, path: path.join(root, "synthetic.mp4"), result: `Kept: original path is occupied. Original bytes retained at ${guard}` };
  fixture.health.deletion_notices = [notice];
  fixture.queue.jobs[11].deletion_notices = [{ ...notice, id: "matched", job_id: fixture.queue.jobs[11].id }];
  fixture.health.speed_profile = { source: "builtin", calibration_minutes: 2 };
  const media = fixture.queue.jobs[0].media;
  const known = { seconds: 100, low: 100, high: 100, calibrated: true, profile_source: "builtin" };
  const unknown = { ...known, unknown_models: ["fixture-without-reference"] };
  const source = path.join(root, "synthetic-hdr.mp4"), normal = path.join(root, "synthetic-normal.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "10", "-c:v", "libx264", "-threads", "2", normal]);
  const model = "basicvsrpp-ntire21-decompress";
  fixture.models.push({ ...JSON.parse(readFileSync(path.resolve("../src/videoenhancer/models/manifests", `${model}.json`), "utf8")), builtin: true, weights_verified: true });
  fixture.routes["trial/thumbnails"] = { duration: 10, thumbnails: [] };
  fixture.routes["compare/range"] = { start: 2 };
  for (const name of ["original", model]) fixture.routes[`operations/unknown/files/${name}`] = readFileSync(normal);
  fixture.routes.compare = () => {
    const operation = { id: "unknown", kind: "compare", state: "done", request: { file: normal }, result: { output_fps: 30, original: "/v1/operations/unknown/files/original", items: [{ id: model, name: "Gentle cleanup", preview: `/v1/operations/unknown/files/${model}`, fps: 2.5, projected_whole_file_seconds: null }] } };
    fixture.queue.operations = [operation]; fixture.snapshot(); return operation;
  };
  fixture.routes.estimate = { presets: { standard: unknown, fast: known }, files: { [source]: { media, warnings: ["HDR is not supported"], output: `${source}.output.mp4`, presets: { standard: known, fast: known } }, [normal]: { media, warnings: [], output: `${normal}.output.mp4`, presets: { standard: unknown, fast: known } } } };
  const app = await _electron.launch({ executablePath: process.env.VE_GUI_PACKAGE_EXE!, args: ["--force-device-scale-factor=1", `--user-data-dir=${path.join(root, "desktop")}`], env: { ...process.env, VE_HOME: path.join(root, "home") } });
  const page = await app.firstWindow();
  const captures: string[] = [];
  const capture = async (name: string) => {
    for (const [width, height] of [[1280, 800], [1100, 700]]) {
      await app.evaluate(({ BrowserWindow }, size) => BrowserWindow.getAllWindows()[0].setContentSize(size[0], size[1]), [width, height]);
      if (name.startsWith("Compare")) await page.getByText(/Speed unknown for this video/).scrollIntoViewIfNeeded();
      await page.waitForTimeout(200);
      const file = path.join(evidence, `${name}-${width}x${height}.png`);
      const png = await app.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].capturePage()).toPNG().toString("base64"));
      writeFileSync(file, Buffer.from(png, "base64")); captures.push(file);
      if (name === "Settings-builtin") {
        const icon = path.join(evidence, `Settings-gear-${width}x${height}.png`);
        await page.getByRole("button", { name: "Settings", exact: true }).screenshot({ path: icon });
        captures.push(icon);
      }
    }
  };
  const open = async (name: string) => page.getByRole("button", { name, exact: true }).click();
  const reload = async () => { await app.evaluate(async ({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].loadURL("app://videoenhancer/")); await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible(); };
  try {
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    await expect(page.getByText(guard, { exact: true })).toBeVisible();
    await capture("Home-progress-retained-guard");
    await open("Settings"); await expect(page.getByText("Using the built-in speed profile.")).toBeVisible(); await capture("Settings-builtin");
    fixture.health.speed_profile = { source: "measured", driver_note: "Speed measured with driver 617.42. This PC now has driver fixture-new.", calibration_minutes: 8 };
    fixture.queue.operations = [{ id: "calibration", kind: "calibrate", state: "running", phase: "Measuring synthetic reference", request: {} }];
    await reload(); await open("Settings"); await expect(page.getByRole("button", { name: "Cancel", exact: true })).toBeVisible(); await capture("Settings-driver-note-cancel");
    fixture.queue.operations = [];
    await reload(); await open("History"); await page.locator('.history-name').first().click(); await expect(page.getByText(notice.result)).toBeVisible(); await capture("History-retained-guard");
    await open("Close"); await open("Home");
    await app.evaluate(({ dialog }, files) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: files }); }, [source, normal]);
    await open("+ Add videos"); await expect(page.getByText("HDR is not supported")).toBeVisible(); await expect(page.getByText("Speed unknown for fixture-without-reference. Run speed calibration.")).toBeVisible(); await capture("Add-HDR-and-unknown-speed");
    await open("Close");
    await app.evaluate(({ dialog }, file) => { dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [file] }); }, normal);
    await open("Models"); await open("Compare on my video");
    await expect(page.getByText(/Speed unknown for this video/)).toBeVisible();
    await expect(page.locator("canvas")).toHaveAttribute("data-frame", /\d+/);
    await capture("Compare-unknown-whole-video-speed");
    writeFileSync(path.join(evidence, "screenshots.json"), JSON.stringify({ fixture: "Isolated synthetic API states; real PQ/HLG behavior separately covered by API integration tests.", paths: captures }, null, 2));
  } finally { await app.close(); await fixture.close(); }
});

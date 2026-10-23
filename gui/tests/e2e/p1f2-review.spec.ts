import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";

test("P1f-2 unknown and damaged records, reuse and nested lists fit both themes", async () => {
  test.setTimeout(180000);
  const root = path.resolve(".."), run = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1f-2/gui", `records-${Date.now()}`);
  const home = path.join(run, "home"), evidence = process.env.VE_GUI_EVIDENCE || path.resolve("../../evidence/P1f-2/gui");
  mkdirSync(evidence, { recursive: true });
  execFileSync(path.join(root, ".venv/Scripts/python.exe"), ["tests/p1f2_gui_seed.py", run], { cwd: root, timeout: 60000 });
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: home, VE_ENGINE_ROOT: root, VE_STORAGE_MOVE_HOLD: "1" } });
  try {
    const page = await app.firstWindow();
    await app.setContentSize(1280, 800);
    await expect(page.getByRole("button", { name: "Add videos", exact: true })).toBeVisible({ timeout: 40000 });
    let checked = { id: "d".repeat(32), state: "done", result: { entries: [{ key: "0", title: "Synthetic reusable video", selected: "v", formats: [{ id: "v", width: 320, height: 180, fps: 30, codec: "h264" }], reuse: { job_id: "a".repeat(32), date: "2026-10-19", media: { display_width: 320, display_height: 180, cfr_fps: "30" } } }] } };
    let nested = false, sequence = 0;
    await page.route(/\/v1\/link-tools$/, route => route.fulfill({ json: { available: true } }));
    await page.route(/\/v1\/links\/check$/, route => { nested = route.request().postDataJSON().url.includes("nested"); checked = { ...checked, id: (++sequence).toString(16).padStart(32, "0") }; return route.fulfill({ json: checked }); });
    await page.route(/\/v1\/operations\/[0-9a-f]{32}$/, route => route.fulfill({ json: nested ? { ...checked, result: { entries: [{ key: "0", title: "Synthetic nested list", error: "This link is a list of lists. Paste the link of one list, for example a channel's Videos tab." }] } } : checked }));
    await page.route(/\/v1\/links\/estimate$/, route => route.fulfill({ json: { estimate: null } }));
    for (const theme of ["dark", "light"]) {
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByRole("combobox", { name: "Theme", exact: true }).selectOption(theme);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await page.getByRole("button", { name: "Home", exact: true }).click();
      await page.screenshot({ path: path.join(evidence, `review-home-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "History", exact: true }).click();
      await expect(page.getByText("Earlier in December 1969", { exact: true })).toHaveCount(0);
      await page.getByRole("button", { name: "unknown-fps.mkv", exact: true }).click();
      await expect(page.getByRole("definition").filter({ hasText: "Synthetic download failed" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(evidence, `review-failed-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.getByRole("button", { name: "damaged-record.mkv", exact: true }).click();
      await expect(page.getByText(/This job's record can't be shown:/)).toBeVisible();
      await expect(page.getByRole("button", { name: "Remove", exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(evidence, `review-record-error-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.getByRole("button", { name: "Home", exact: true }).click();
      await app.files([]);
      await page.getByRole("button", { name: "Add videos", exact: true }).click();
      await page.getByLabel("Paste a video link").fill("http://localhost/video");
      await page.getByRole("button", { name: "Check", exact: true }).click();
      await expect(page.getByRole("checkbox", { name: /Use the file downloaded/ })).toBeChecked();
      await page.screenshot({ path: path.join(evidence, `review-reuse-${theme}.png`), scale: "css" });
      await page.getByLabel("Paste a video link").fill("http://localhost/nested");
      await page.getByRole("button", { name: "Check", exact: true }).click();
      await expect(page.getByText(/This link is a list of lists/)).toBeVisible();
      await page.screenshot({ path: path.join(evidence, `review-nested-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "Close", exact: true }).click();
    }
    await page.getByRole("button", { name: "History", exact: true }).click();
    await page.getByRole("button", { name: "damaged-record.mkv", exact: true }).click();
    await page.getByRole("button", { name: "Remove", exact: true }).click();
    await expect(page.getByRole("checkbox", { name: "Remove from History", exact: true })).toBeChecked();
    await page.getByRole("button", { name: "Remove selected items", exact: true }).click();
    await expect(page.getByRole("button", { name: "damaged-record.mkv", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(page.getByRole("button", { name: "damaged-record.mkv", exact: true })).toBeVisible();
    const record = path.join(home, "jobs", "c".repeat(32), "manifest.json");
    writeFileSync(record, "{syntactically broken record");
    await expect(page.getByRole("button", { name: "c".repeat(32), exact: true })).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "c".repeat(32), exact: true }).click();
    await page.getByRole("dialog", { name: "Video details" }).getByRole("button", { name: "Copy details", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Video details" }).getByText("Copied", { exact: true })).toBeVisible();
    await expect.poll(() => app.clipboardText()).toContain("Parse error:");
    expect(await app.clipboardText()).toContain(record);
    await page.getByRole("button", { name: "Remove", exact: true }).click();
    await expect(page.getByText("This record can't be read, so its videos stay where they are.", { exact: true })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: /Move the/ })).toHaveCount(0);
    await page.getByRole("button", { name: "Remove selected items", exact: true }).click();
    await expect(page.getByRole("button", { name: "c".repeat(32), exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(page.getByRole("button", { name: "c".repeat(32), exact: true })).toBeVisible();
    expect(readFileSync(record, "utf8")).toBe("{syntactically broken record");
  } finally { await app.close(); }
});

test("P1f-2 video and tray Quit remain usable during real storage verification and removal", async () => {
  test.setTimeout(240000);
  const root = path.resolve(".."), run = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1f-2/gui", `storage-live-${Date.now()}`);
  execFileSync(path.join(root, ".venv/Scripts/python.exe"), ["tests/p1f2_gui_seed.py", run, "large"], { cwd: root, timeout: 120000 });
  const home = path.join(run, "home"), roaming = path.join(run, "roaming");
  mkdirSync(path.join(roaming, "VideoEnhancer"), { recursive: true });
  copyFileSync(path.join(run, "pointer.json"), path.join(roaming, "VideoEnhancer/storage-location.json"));
  for (const operation of ["refresh", "remove"]) {
    const settingsFile = path.join(home, "settings.json");
    writeFileSync(settingsFile, JSON.stringify({ ...JSON.parse(readFileSync(settingsFile, "utf8")), theme: operation === "refresh" ? "dark" : "light" }));
    const app = await desktop.launch({ env: { ...process.env, VE_HOME: undefined, VE_TEST_EXPECTED_HOME: home, VE_TEST_APPDATA: roaming, VE_TEST_LOCALAPPDATA: path.join(run, "local"), VE_ENGINE_ROOT: root, VE_STORAGE_MOVE_HOLD: "1" } });
    try {
      const page = await app.firstWindow();
      await expect(page.getByRole("button", { name: "Settings", exact: true })).toBeVisible({ timeout: 40000 });
      await page.evaluate(async () => {
        const video = document.createElement("video"); video.id = "storage-test-player"; video.muted = true; video.loop = true; video.style.cssText = "position:fixed;bottom:20px;right:20px;width:320px;z-index:999";
        document.body.append(video); video.src = `http://ve-media.localhost/${"a".repeat(32)}`; await video.play();
      });
      await app.setContentSize(1280, 800);
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      if (operation === "remove") {
        const remove = page.getByRole("button", { name: "Remove the old folder", exact: true });
        try { await expect(remove).toBeEnabled({ timeout: 30000 }); }
        catch (error) {
          const evidence = process.env.VE_GUI_EVIDENCE || path.resolve("../../evidence/P1f-2/gui");
          mkdirSync(evidence, { recursive: true });
          writeFileSync(path.join(evidence, "storage-remove-disabled.json"), JSON.stringify(await page.evaluate(() => window.desktop.storageStatus!(false)), null, 2));
          throw error;
        }
        await app.command("remove-confirmation", true);
        await remove.click();
      }
      await expect.poll(async () => (await app.command<{ storage_busy: boolean }>("state")).storage_busy).toBe(true);
      await page.evaluate(async () => {
        const video = document.querySelector<HTMLVideoElement>("#storage-test-player")!;
        const sought = new Promise<void>((resolve, reject) => { const timer = setTimeout(() => reject(new Error("seek timeout")), 10000); video.addEventListener("seeked", () => { clearTimeout(timer); resolve(); }, { once: true }); });
        video.currentTime = 1.5; await sought; await video.play();
      });
      expect((await app.command<{ storage_moving: boolean }>("state")).storage_moving).toBe(false);
      const evidence = process.env.VE_GUI_EVIDENCE || path.resolve("../../evidence/P1f-2/gui");
      mkdirSync(evidence, { recursive: true });
      await page.screenshot({ path: path.join(evidence, `review-storage-${operation}.png`), scale: "css" });
      await app.quit();
      await expect.poll(() => app.process().exitCode, { timeout: 30000 }).not.toBeNull();
    } finally { await app.close(); }
  }
});

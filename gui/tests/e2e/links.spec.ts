import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";
import { assertPanelFits } from "./clipping";

test("link cards, playlist, download Home and settings fit both sizes and themes", async () => {
  test.setTimeout(180000);
  const root = path.resolve(".."), run = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1f/e2e", `links-${Date.now()}`);
  const home = path.join(run, "home"), evidence = process.env.VE_GUI_EVIDENCE || path.resolve("../../evidence/P1f/gui");
  mkdirSync(home, { recursive: true }); mkdirSync(evidence, { recursive: true });
  writeFileSync(path.join(home, "settings.json"), JSON.stringify({ tour_completed: true, tray_explained: true }));
  execFileSync(path.join(root, ".venv/Scripts/python.exe"), ["-c", `from pathlib import Path
from videoenhancer.jobs.store import JobStore
home=Path(${JSON.stringify(home)})
JobStore(home).save(dict(schema_version=1,id='a'*32,state='downloading',input={'path':str(home/'download.mkv')},output=str(home/'output.mp4'),settings=dict(preset='fast',backend='cpu',short_side=1080,fps='off',codec='hevc'),media=dict(width=320,height=180,display_width=320,display_height=180,cfr_fps='30',frame_count=60,duration=2),segments=[],source=dict(url='http://localhost/video.mp4',title='Synthetic download',id='synthetic',extractor='generic',format='video'),download=dict(phase='Downloading',percent=42,bytes=420000,total_bytes=1000000,bytes_per_second=100000,remaining_seconds=6),created_at='2026-10-18T00:00:00+00:00'))`], { cwd: root, windowsHide: true });
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: home, VE_ENGINE_ROOT: root, VE_STORAGE_MOVE_HOLD: "1" } });
  try {
    const page = await app.firstWindow();
    await expect(page.getByRole("button", { name: "Add videos", exact: true })).toBeVisible({ timeout: 40000 });
    await page.evaluate(async () => { const c = await window.desktop.connection(); await fetch(`${c.base_url}/processing`, { method: "POST", headers: { Authorization: `Bearer ${c.token}`, "Content-Type": "application/json" }, body: JSON.stringify({ paused: true }) }); });
    const entries = [0, 1, 2].map(index => ({ key: String(index), title: `Synthetic playlist video ${index + 1}`, site: "Local fixture", uploader: "Acceptance fixture", duration: 2, selected: "sdr", formats: [
      { id: "sdr", width: 320, height: 180, fps: 30, codec: "h264", dynamic_range: "SDR", bytes: 1000000, estimate: { seconds: 60, low: 45, high: 75, calibrated: false } },
      { id: "hdr", width: 320, height: 180, fps: 30, codec: "h264", dynamic_range: "HDR", disabled: "HDR is not supported yet" },
    ] }));
    await page.route(/\/v1\/link-tools$/, route => route.fulfill({ json: { installed: {}, available: true } }));
    let checked = { id: "b".repeat(32), state: "done", result: { entries } };
    let checkNumber = 0;
    await page.route(/\/v1\/links\/check$/, route => {
      checked = { id: (++checkNumber).toString(16).padStart(32, "0"), state: "done", result: { entries: route.request().postDataJSON().url.includes("playlist") ? entries : entries.slice(0, 1) } };
      return route.fulfill({ json: checked });
    });
    await page.route(/\/v1\/operations\/[0-9a-f]{32}$/, route => route.fulfill({ json: checked }));
    await page.route(/\/v1\/links\/estimate$/, route => route.fulfill({ json: { estimate: { seconds: 60, low: 45, high: 75, calibrated: false } } }));
    for (const theme of ["dark", "light"]) {
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByRole("combobox", { name: "Theme", exact: true }).selectOption(theme);
      await expect(page.getByText("Saved", { exact: true })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await page.getByRole("button", { name: "Home", exact: true }).click();
      for (const [width, height] of [[1280, 800], [1100, 700]]) {
        await app.setContentSize(width, height);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await expect(page.getByRole("progressbar", { name: "Download progress" })).toHaveAttribute("value", "42");
        await page.screenshot({ scale: "css", path: path.join(evidence, `links-home-${theme}-${width}.png`) });
        await app.files([]);
        await page.getByRole("button", { name: "Add videos", exact: true }).click();
        await page.getByLabel("Paste a video link").fill("http://localhost/video.mp4");
        await page.getByRole("button", { name: "Check", exact: true }).click();
        await expect(page.getByRole("combobox", { name: "Quality", exact: true })).toHaveCount(1);
        await page.getByRole("combobox", { name: "Quality", exact: true }).focus();
        await assertPanelFits(page);
        await page.screenshot({ scale: "css", path: path.join(evidence, `links-quality-${theme}-${width}.png`) });
        await page.getByLabel("Paste a video link").fill("http://localhost/playlist.html");
        await page.getByRole("button", { name: "Check", exact: true }).click();
        await expect(page.getByText("Synthetic playlist video 3", { exact: true })).toBeVisible();
        await assertPanelFits(page);
        await page.screenshot({ scale: "css", path: path.join(evidence, `links-playlist-${theme}-${width}.png`) });
        await page.getByRole("button", { name: "Close", exact: true }).click();
        await page.getByRole("button", { name: "Settings", exact: true }).click();
        await page.getByRole("heading", { name: "Video links", exact: true }).scrollIntoViewIfNeeded();
        await expect(page.getByLabel("Simultaneous downloads")).toHaveValue("2");
        await page.getByLabel("Simultaneous downloads").scrollIntoViewIfNeeded();
        await page.screenshot({ scale: "css", path: path.join(evidence, `links-settings-${theme}-${width}.png`) });
        await page.getByRole("button", { name: "Home", exact: true }).click();
      }
    }
  } finally { await app.close(); }
});

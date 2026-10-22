import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { desktop } from "../desktop";

for (const state of ["fresh", "failed", "driver"]) test(`P1f-3 ${state} calibration and copyable notices in both themes`, async () => {
  test.setTimeout(180000);
  const root = path.resolve("..");
  const run = path.resolve(process.env.VE_GUI_TEST_ROOT || "../../scratch/P1f-3/gui", `${state}-${Date.now()}`);
  const evidence = process.env.VE_GUI_EVIDENCE || path.resolve("../../evidence/VE-P1f-3/gui");
  mkdirSync(evidence, { recursive: true });
  const fixture = JSON.parse(execFileSync(path.join(root, ".venv/Scripts/python.exe"), ["tests/p1f3_gui_seed.py", run, state], { cwd: root, encoding: "utf8", timeout: 60000, windowsHide: true })) as { source: string; refusal: string };
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: path.join(run, "home"), VE_ENGINE_ROOT: root, VE_TEST_STARTUP_ERROR: "Synthetic registry write denied" } });
  try {
    const page = await app.firstWindow();
    await app.setContentSize(1280, 800);
    await expect(page.getByRole("button", { name: "Add videos", exact: true })).toBeVisible({ timeout: 40000 });
    for (const theme of ["dark", "light"]) {
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByRole("combobox", { name: "Theme", exact: true }).selectOption(theme);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      if (state === "failed") {
        await expect(page.getByText(/The last calibration on .* failed: Synthetic old failure/)).toBeVisible();
        await expect(page.getByRole("button", { name: /^Run again/ })).toBeVisible();
      } else if (state === "driver") {
        await expect(page.getByText(/Speed measured with driver synthetic-old-driver/)).toBeVisible({ timeout: 20000 });
      } else {
        await expect(page.getByText("Using the built-in speed profile.")).toBeVisible({ timeout: 20000 });
      }
      const startup = page.getByRole("alert").filter({ hasText: "Windows didn't accept the startup entry:" });
      await expect(startup).toBeVisible({ timeout: 10000 });
      await startup.getByRole("button", { name: "Copy message", exact: true }).click();
      await expect(page.getByText("Copied", { exact: true })).toBeVisible();
      expect(await app.clipboardText()).toContain("Synthetic registry write denied");
      await page.screenshot({ path: path.join(evidence, `calibration-${state}-${theme}.png`), scale: "css" });
      if (state !== "fresh") continue;
      await page.route(/\/v1\/settings$/, route => route.request().method() === "PUT" ? route.fulfill({ status: 400, json: { error: "Synthetic save failed: code 90" } }) : route.continue());
      await page.getByLabel("Delete the original after a verified output").click();
      const error = page.getByRole("alert").filter({ hasText: "Synthetic save failed: code 90" });
      await expect(error).toBeVisible();
      await error.getByRole("button", { name: "Copy message", exact: true }).click();
      await expect(error.getByText("Copied", { exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(evidence, `action-copy-${theme}.png`), scale: "css" });
      await page.getByRole("heading", { name: "Settings", exact: true }).click();
      await page.mouse.move(0, 0);
      await expect(error).toHaveClass(/notice-fading/, { timeout: 10000 });
      await page.screenshot({ path: path.join(evidence, `action-fade-${theme}.png`), scale: "css" });
      await expect(error).toBeHidden();
      await page.unroute(/\/v1\/settings$/);
      await page.getByRole("button", { name: "Home", exact: true }).click();
      await page.screenshot({ path: path.join(evidence, `japanese-home-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "History", exact: true }).click();
      await expect(page.getByRole("button", { name: "サンプル「夏」の動画.mp4", exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(evidence, `japanese-history-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "サンプル「夏」の動画.mp4", exact: true }).click();
      await expect.poll(() => page.locator("video").evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThan(1);
      await page.getByRole("button", { name: "Copy details", exact: true }).click();
      await expect(page.getByText("Copied", { exact: true })).toBeVisible();
      await page.screenshot({ path: path.join(evidence, `japanese-details-${theme}.png`), scale: "css" });
      await page.getByRole("button", { name: "Close", exact: true }).click();
      await page.getByRole("button", { name: "Home", exact: true }).click();
      for (const [kind, file] of [["add", fixture.source], ["condition", fixture.refusal]]) {
        await app.files([file]);
        await page.getByRole("button", { name: "Add videos", exact: true }).click();
        await expect(page.getByRole("dialog")).toBeVisible();
        if (kind === "condition") await expect(page.getByText(/This video is larger than 1080p/)).toBeVisible();
        await page.screenshot({ path: path.join(evidence, `japanese-${kind}-${theme}.png`), scale: "css" });
        await page.getByRole("dialog").getByRole("button", { name: "Close", exact: true }).click();
      }
    }
    const lines = readFileSync(path.join(run, "home", "startup-errors.log"), "utf8").trim().split(/\r?\n/);
    expect(lines).toEqual(["Windows didn't accept the startup entry: Synthetic registry write denied"]);
  } finally { await app.close(); }
});

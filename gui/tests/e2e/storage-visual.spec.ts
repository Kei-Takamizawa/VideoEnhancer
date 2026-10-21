import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../perf/fake-engine.cjs");

test("Storage UI inventory in both sizes and themes with progress and completion", async () => {
  test.skip(!process.env.VE_STORAGE_VISUAL, "Opt-in external Storage screenshots.");
  const evidence = process.env.VE_STORAGE_VISUAL!, root = path.join(process.env.VE_STORAGE_SCRATCH!,"visual");
  mkdirSync(evidence,{recursive:true});
  const fixture = await fakeEngine(path.join(root,"home"));
  fixture.routes.storage = { folder: path.join(root,"home"), total_bytes: 2200000000,
    models_bytes: 1800000000, working_bytes: 350000000, history_bytes:50000000,
    free_bytes: 800000000000, cleanup:[{id:"synthetic-failed",name:"synthetic-failed.mp4",date:"2026-10-12T12:00:00Z",state:"failed",bytes:350000000}] };
  const app = await desktop.launch({ executablePath: (process.env.VE_TAURI_EXE || ""), args:[".",`--user-data-dir=${path.join(root,"desktop")}`],env:{...process.env,VE_HOME:path.join(root,"home")} });
  const page = await app.firstWindow();
  async function capture(name: string) {
    const png = await (async () => (await app.capturePage()).toString("base64"))();
    writeFileSync(path.join(evidence,name+".png"),Buffer.from(png,"base64"));
  }
  try {
    await page.getByRole("button",{name:"Settings",exact:true}).click();
    await expect(page.getByText("App data folder:",{exact:false})).toBeVisible();
    for (const size of [[1280,800],[1100,700]]) {
      await (async (s) => app.setContentSize(s[0],s[1]))(size);
      for (const theme of ["dark","light"]) {
        await page.getByLabel("Theme").selectOption(theme);
        const card = page.locator(".storage-card"); await card.scrollIntoViewIfNeeded();
        await expect(card.getByText("1.80 GB",{exact:true})).toBeVisible();
        const cleanup = card.locator('li[title="synthetic-failed"]');
        await expect(cleanup).toContainText("synthetic-failed.mp4");
        await expect(cleanup).toContainText("failed");
        await expect(cleanup).toContainText("2026");
        await expect(cleanup).toContainText("0.35 GB");
        await expect(cleanup).not.toContainText("Date unavailable");
        await capture(`${size[0]}-${theme}-sizes`);
        await app.command("storage-fixture", {phase:"Copying and verifying",copied_bytes:1100000000,total_bytes:2200000000});
        // The test moves through actual UI states using a synthetic IPC fixture; no owner data is used.
        await app.files((folder => [folder])(path.join(root,"destination")));
        await card.getByRole("button",{name:"Move…",exact:true}).click();
        await expect(card.getByText("Copying and verifying",{exact:false})).toBeVisible();
        await capture(`${size[0]}-${theme}-moving`);
        await expect(page.locator(".storage-card")).toBeVisible();
        await page.waitForTimeout(1500);
        await page.getByRole("button",{name:"Settings",exact:true}).click();
        await app.command("storage-fixture", {phase:"Move completed",previous:path.join(root,"old-copy"),can_remove:true});
        await page.locator(".storage-card").scrollIntoViewIfNeeded();
        await expect(page.getByRole("button",{name:"Remove the old folder",exact:true})).toBeVisible();
        await capture(`${size[0]}-${theme}-result`);
      }
    }
  } finally { await app.close(); await fixture.close(); }
});


import { _electron, expect, test } from "@playwright/test";
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
    free_bytes: 800000000000, cleanup:[{id:"synthetic-failed",state:"failed",bytes:350000000}] };
  const app = await _electron.launch({ executablePath: require("electron"), args:[".",`--user-data-dir=${path.join(root,"desktop")}`],env:{...process.env,VE_HOME:path.join(root,"home")} });
  const page = await app.firstWindow();
  async function capture(name: string) {
    const png = await app.evaluate(async ({BrowserWindow}) => (await BrowserWindow.getAllWindows()[0].webContents.capturePage()).toPNG().toString("base64"));
    writeFileSync(path.join(evidence,name+".png"),Buffer.from(png,"base64"));
  }
  try {
    await page.getByRole("button",{name:"Settings",exact:true}).click();
    await expect(page.getByText("App data folder:",{exact:false})).toBeVisible();
    for (const size of [[1280,800],[1100,700]]) {
      await app.evaluate(({BrowserWindow},s)=>BrowserWindow.getAllWindows()[0].setContentSize(s[0],s[1]),size);
      for (const theme of ["dark","light"]) {
        await page.getByLabel("Theme").selectOption(theme);
        const card = page.locator(".storage-card"); await card.scrollIntoViewIfNeeded();
        await expect(card.getByText("1.80 GB",{exact:true})).toBeVisible();
        await capture(`${size[0]}-${theme}-sizes`);
        await app.evaluate(({ipcMain})=>{
          ipcMain.removeHandler("storage-status");
          ipcMain.handle("storage-status",()=>({phase:"Copying and verifying",copied_bytes:1100000000,total_bytes:2200000000}));
          ipcMain.removeHandler("storage-move");
          ipcMain.handle("storage-move",()=>new Promise(resolve=>setTimeout(()=>resolve({moved:true}),1200)));
        });
        // The test moves through actual UI states using a synthetic IPC fixture; no owner data is used.
        await app.evaluate(({dialog},folder)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[folder]});},path.join(root,"destination"));
        await card.getByRole("button",{name:"Move…",exact:true}).click();
        await expect(card.getByText("Copying and verifying",{exact:false})).toBeVisible();
        await capture(`${size[0]}-${theme}-moving`);
        await expect(page.locator(".storage-card")).toBeVisible();
        await page.waitForTimeout(1500);
        await page.getByRole("button",{name:"Settings",exact:true}).click();
        await app.evaluate(({ipcMain},folder)=>{
          ipcMain.removeHandler("storage-status");ipcMain.handle("storage-status",()=>({phase:"Move completed",previous:folder}));
        },path.join(root,"old-copy"));
        await page.locator(".storage-card").scrollIntoViewIfNeeded();
        await expect(page.getByRole("button",{name:"Remove the old folder",exact:true})).toBeVisible();
        await capture(`${size[0]}-${theme}-result`);
      }
    }
  } finally { await app.close(); await fixture.close(); }
});


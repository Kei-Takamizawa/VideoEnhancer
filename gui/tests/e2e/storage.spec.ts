import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

test("isolated real C-D-C app-data move retains finished and paused jobs and installed weights", async () => {
  test.skip(!process.env.VE_STORAGE_C_FIXTURE, "Opt-in isolated C drive fixture required.");
  test.setTimeout(180000);
  const root = path.resolve(".."), scratch = process.env.VE_STORAGE_SCRATCH!;
  const croot = process.env.VE_STORAGE_C_FIXTURE!, old = path.join(croot, "home");
  const target = path.join(scratch, "moved"), back = path.join(croot, "returned");
  mkdirSync(scratch, { recursive: true });
  execFileSync(path.join(root, ".venv/Scripts/python.exe"), ["tests/storage_seed.py", croot, process.env.VE_GPU_TEST_MODEL_HOME!], { cwd: root, env: process.env, timeout: 60000 });
  const env: Record<string, string> = { ...Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => typeof entry[1] === "string")), VE_TEST_EXPECTED_HOME: old, VE_ENGINE_ROOT: root,
    VE_TEST_APPDATA:path.join(scratch,"roaming"),VE_TEST_LOCALAPPDATA:path.join(scratch,"local") };
  delete env.VE_HOME;
  mkdirSync(path.join(env.VE_TEST_APPDATA,"VideoEnhancer"),{recursive:true});
  writeFileSync(path.join(env.VE_TEST_APPDATA,"VideoEnhancer","storage-location.json"),JSON.stringify({active:old}));
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await desktop.launch({ executablePath: process.env.VE_GUI_PACKAGE_EXE || (process.env.VE_TAURI_EXE || ""),
    args: [...(process.env.VE_GUI_PACKAGE_EXE ? [] : ["."]), `--user-data-dir=${path.join(scratch,"desktop")}`], env });
  const page = await app.firstWindow();
  try {
    await expect(page.getByRole("button", { name: "Settings", exact: true })).toBeVisible({ timeout: 40000 });
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByText(`App data folder: ${old}`, { exact: true })).toBeVisible();
    for (const destination of [target, back]) {
      await app.files((folder => [folder])(destination));
      await page.getByRole("button", { name: "Move…", exact: true }).click();
      await expect(page.getByText(`App data folder: ${destination}`, { exact: true })).toBeVisible({ timeout: 60000 });
      expect(JSON.parse(readFileSync(path.join(destination,"jobs/finished/manifest.json"),"utf8")).state).toBe("done");
      expect(JSON.parse(readFileSync(path.join(destination,"jobs/paused/manifest.json"),"utf8")).state).toBe("paused");
      expect(existsSync(path.join(destination,"models/rife-4.25/flownet.pkl"))).toBe(true);
    }
    const result = await page.evaluate(async () => {
      const c = await window.desktop.connection();
      const call = async (route: string, body: object) => fetch(`${c.base_url}/${route}`, {method:"POST",headers:{Authorization:`Bearer ${c.token}`,"Content-Type":"application/json"},body:JSON.stringify(body)}).then(r=>r.json());
      await call("queue/paused/resume", {}); await call("processing", {paused:false});
      return c;
    });
    await expect.poll(() => JSON.parse(readFileSync(path.join(back,"jobs/paused/manifest.json"),"utf8")).state, {timeout:60000}).toBe("done");
    expect(existsSync(path.join(croot,"finished.mp4"))).toBe(true);
    expect(existsSync(path.join(croot,"resumed.mp4"))).toBe(true);
    writeFileSync(path.join(process.env.VE_GUI_EVIDENCE!,"cross-volume.json"),JSON.stringify({old,target,back,finished:"done",resumed:"done",model:"rife-4.25",service:result.base_url},null,2));
    await (async () => app.quit())();
  } finally { await app.close().catch(()=>{}); }
});


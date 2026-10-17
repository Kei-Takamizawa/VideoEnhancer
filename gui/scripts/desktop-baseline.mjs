/* global requestAnimationFrame */
import { chromium } from "@playwright/test";
import { execFileSync, spawn } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import path from "node:path";
import net from "node:net";
const require = createRequire(import.meta.url);
const { fakeEngine } = require("../tests/perf/fake-engine.cjs");
const root = path.resolve(process.env.VE_BASELINE_SCRATCH || "");
const output = process.env.VE_BASELINE_OUTPUT;
const executable = process.env.VE_BASELINE_EXE;
const kind = process.env.VE_BASELINE_KIND;
if (!root.toLowerCase().includes(`${path.sep}scratch${path.sep}`) || !output || !executable || !["tauri", "electron"].includes(kind)) throw new Error("Set isolated baseline paths and kind.");
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const result = { kind, method: "Same authenticated 1000-History fixture; process launch to Home data and two animation frames, five independent profiles; fifth remains five minutes. CDP for both shells.", cold_start_ms: [] };
mkdirSync(path.dirname(output), { recursive: true });
for (let repeat = 0; repeat < 5; repeat++) {
  const run = path.join(root, String(repeat)), home = path.join(run, "home"), profile = path.join(run, "desktop");
  mkdirSync(profile, { recursive: true });
  const fixture = await fakeEngine(home);
  const port = await new Promise(resolve => { const s = net.createServer(); s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => resolve(p)); }); });
  const began = performance.now();
  const child = spawn(executable, kind === "electron" ? [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`] : [], { windowsHide: true, stdio: "ignore", env: { ...process.env, VE_HOME: home, APPDATA: path.join(run, "roaming"), LOCALAPPDATA: path.join(run, "local"), WEBVIEW2_USER_DATA_FOLDER: profile, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port}` } });
  let browser;
  try {
    for (let i = 0; i < 300; i++) { try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`); break; } catch { await sleep(20); } }
    if (!browser) throw new Error("Baseline CDP attachment failed");
    const page = browser.contexts()[0].pages()[0];
    await page.getByRole("heading", { name: "Home", exact: true }).waitFor();
    await page.locator(".now-percent").waitFor();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    result.cold_start_ms.push(performance.now() - began);
    writeFileSync(output, JSON.stringify(result, null, 2));
    console.log(kind, repeat + 1, result.cold_start_ms.at(-1));
    if (repeat === 4) {
      await sleep(300000);
      result.idle_processes = JSON.parse(execFileSync(process.env.VE_PYTHON || path.resolve("../.venv/Scripts/python.exe"), ["-c", "import psutil,json,sys; r=psutil.Process(int(sys.argv[1])); print(json.dumps([{'pid':p.pid,'name':p.name(),'private_working_set_bytes':p.memory_full_info().uss,'private_bytes':p.memory_info().private} for p in [r,*r.children(recursive=True)] if p.is_running()]))", String(child.pid)], { encoding: "utf8", windowsHide: true }));
      result.idle_private_working_set_bytes = result.idle_processes.reduce((sum, p) => sum + p.private_working_set_bytes, 0);
      result.idle_private_bytes = result.idle_processes.reduce((sum, p) => sum + p.private_bytes, 0);
      result.python_engine = "NOT RUN in this fixture: the isolated authenticated engine fixture is an external Node process, not Python.";
    }
  } finally {
    const owned = JSON.parse(execFileSync(process.env.VE_PYTHON || path.resolve("../.venv/Scripts/python.exe"), ["-c", "import psutil,json,sys; a=[]\ntry:\n r=psutil.Process(int(sys.argv[1])); a=[{'pid':p.pid,'created':p.create_time()} for p in [r,*r.children(recursive=True)]]\nexcept psutil.NoSuchProcess: pass\nprint(json.dumps(a))", String(child.pid)], { encoding: "utf8", windowsHide: true }));
    if (browser) await browser.close().catch(() => {});
    if (child.exitCode === null) execFileSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
    execFileSync(process.env.VE_PYTHON || path.resolve("../.venv/Scripts/python.exe"), ["-c", "import psutil,json,sys,time; a=json.loads(sys.argv[1]); end=time.monotonic()+10\ndef alive(p):\n try:return psutil.Process(p['pid']).create_time()==p['created']\n except psutil.NoSuchProcess:return False\nwhile any(alive(p) for p in a) and time.monotonic()<end:time.sleep(.1)\nassert not any(alive(p) for p in a),'App descendants remained alive between cold launches'", JSON.stringify(owned)], { encoding: "utf8", windowsHide: true });
    result.all_recorded_processes_exited_between_launches = true;
    await fixture.close();
  }
}
result.cold_start_median_ms = result.cold_start_ms.toSorted((a, b) => a - b)[2];
writeFileSync(output, JSON.stringify(result, null, 2));
console.log(JSON.stringify(result));

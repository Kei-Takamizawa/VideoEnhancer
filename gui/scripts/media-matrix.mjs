/* global document, window, performance, requestAnimationFrame, Element, HTMLVideoElement, HTMLMediaElement */
import { chromium } from "@playwright/test";
import { execFileSync, spawn } from "node:child_process";
import { createWriteStream, mkdirSync, readFileSync, writeFileSync, existsSync, statSync } from "node:fs";
import path from "node:path";
import net from "node:net";

const scratch = path.resolve(process.env.VE_M2_SCRATCH || "");
const evidence = path.resolve(process.env.VE_M2_EVIDENCE || "");
const media = path.resolve(process.env.VE_M2_MEDIA || "");
const python = path.resolve(process.env.VE_PYTHON || "../.venv/Scripts/python.exe");
const snapshot = process.env.VE_M2_ENGINE_SNAPSHOT;
const followup = process.env.VE_M2_FOLLOWUP === "1";
const m3 = process.env.VE_DEV_M3_MEDIA === "1";
const lowMemory = process.env.VE_M2_LOW_MEMORY === "1";
const serviceScript = process.env.VE_M2_SERVICE_SCRIPT || (snapshot ? path.join(snapshot, "gui/scripts/media-service.py") : path.resolve("scripts/media-service.py"));
const sampleScript = snapshot ? path.join(snapshot, "gui/scripts/private-bytes.py") : path.resolve("scripts/private-bytes.py");
if (!scratch.toLowerCase().includes(`${path.sep}scratch${path.sep}`)) throw new Error("An isolated scratch folder is required.");
mkdirSync(evidence, { recursive: true });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const mean = values => values.reduce((sum, value) => sum + value, 0) / values.length;
const median = values => { const sorted = values.toSorted((a, b) => a - b); return (sorted[Math.floor((sorted.length - 1) / 2)] + sorted[Math.ceil((sorted.length - 1) / 2)]) / 2; };
const positions = [];
let seed = 0x51eecafe;
for (let i = 0; i < 20; i++) { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; positions.push(.05 + (seed >>> 0) / 4294967296 * .85); }
const recipe = { version: 2, engine: "Production Python Engine/LocalServer and unchanged Range handler; process-local legacy Origin override only for isolated Electron comparison", method: "Windows Private Bytes, all descendants, 1 s samples, 10 s pre-Play baseline with actual History player open", positions, chunks_mib: [8, 2, 1], codecs: ["h264", "av1"], repeats: 3, order: "Electron, Tauri alternately for every scenario/repeat", P: "120 s, 20 seeks at 3+6*i s", R: "20 seeks 100 ms apart, then 30 s play", steady: "600 s, one seek every 30 s", close: "Actual History dialog Close, sample after 30 s", build: "Release optimization; Tauri e2e feature permits chunk selection and fetch counters only" };
writeFileSync(path.join(evidence, "recipe.json"), JSON.stringify(recipe, null, 2));
if (followup) writeFileSync(path.join(evidence, "followup-recipe.json"), JSON.stringify({ repeats: "10 cycles, 30 s play, seeks at 5/15/25 s, 30 s closed, same instance", repeat_gate: "cycle 10 total <= cycle 1 + 50 MB", av1_idle: "300 s after final close", decoder: "CDP Media.playerPropertiesChanged; decoder/codec properties only", m3, lowMemory, positions }, null, 2));
const progress = message => { console.log(new Date().toISOString(), message); writeFileSync(path.join(evidence, "progress.json"), JSON.stringify({ time: new Date().toISOString(), message })); };

async function productionEngine(home, codec, kind) {
  mkdirSync(home, { recursive: true });
  const log = createWriteStream(path.join(home, "fixture-service.log"));
  const service = spawn(python, [serviceScript, home, media, process.env.VE_M2_TEMPLATE || "", codec], { windowsHide: true, stdio: ["ignore", "pipe", "pipe"], env: { ...process.env, PYTHONPATH: snapshot ? path.join(snapshot, "src") : process.env.PYTHONPATH, VE_HOME: home, APPDATA: path.join(home, "fixture-roaming"), LOCALAPPDATA: path.join(home, "fixture-local"), VE_TEST_ALLOW_LEGACY_ORIGIN: kind === "electron" ? "1" : "0" } });
  service.stderr.pipe(log);
  const control = { media_peak: 0, media_total: 0, ready: false };
  let pending = "";
  service.stdout.on("data", data => {
    pending += data.toString(); let boundary;
    while ((boundary = pending.indexOf("\n")) >= 0) {
      const line = pending.slice(0, boundary); pending = pending.slice(boundary + 1);
      try { Object.assign(control, JSON.parse(line)); } catch { log.write(line + "\n"); }
    }
  });
  for (let i = 0; i < 300 && !control.ready; i++) {
    if (service.exitCode !== null) throw new Error(`Production media service failed: ${readFileSync(path.join(home, "fixture-service.log"), "utf8").slice(-3000)}`);
    await sleep(100);
  }
  if (!control.ready) { service.kill(); throw new Error("Production media service did not become ready"); }
  return { control,
    memory: () => JSON.parse(execFileSync(python, ["-c", "import psutil,json,sys; r=psutil.Process(int(sys.argv[1])); print(json.dumps([{'pid':p.pid,'name':p.name(),'private_bytes':p.memory_info().private,'private_working_set_bytes':p.memory_full_info().uss} for p in [r,*r.children(recursive=True)] if p.is_running()]))", String(service.pid)], { encoding: "utf8", windowsHide: true })),
    close: async () => {
      const c = JSON.parse(readFileSync(path.join(home, "serve.json"), "utf8"));
      await fetch(`http://127.0.0.1:${c.port}/v1/shutdown`, { method: "POST", headers: { Authorization: `Bearer ${c.token}`, "Content-Type": "application/json" }, body: "{}", signal: AbortSignal.timeout(20000) }).catch(() => {});
      for (let i = 0; i < 100 && service.exitCode === null; i++) await sleep(100);
      if (service.exitCode === null) execFileSync("taskkill.exe", ["/PID", String(service.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
      log.end();
    } };
}

async function run(kind, chunk, codec, scenario, repeat) {
  const key = `${m3 ? "M3-" : lowMemory ? "Low-" : ""}${chunk}MiB-${codec}-${scenario}-${repeat}-${kind}`;
  const output = path.join(evidence, `${key}.json`);
  if (existsSync(output) && JSON.parse(readFileSync(output, "utf8")).completed) { progress(`Resume: ${key} already complete`); return; }
  const runRoot = path.join(scratch, key), home = path.join(runRoot, "home"), profile = path.join(runRoot, "desktop");
  mkdirSync(profile, { recursive: true });
  const file = path.join(media, `${codec}-1440-large.mp4`);
  if (statSync(file).size < 2_000_000_000) throw new Error("M2 requires at least 2 GB per file.");
  const fixture = await productionEngine(home, codec, kind);
  const port = await new Promise((resolve, reject) => { const s = net.createServer(); s.once("error", reject); s.listen(0, "127.0.0.1", () => { const port = s.address().port; s.close(() => resolve(port)); }); });
  const executable = kind === "tauri" ? process.env.VE_M2_TAURI_EXE : process.env.VE_M2_ELECTRON_EXE;
  if (!executable) throw new Error("Both isolated desktop executable paths are required.");
  progress(`START ${key}`);
  const child = spawn(executable, kind === "electron" ? [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--autoplay-policy=no-user-gesture-required"] : [], { windowsHide: true, stdio: "ignore", env: { ...process.env, VE_HOME: home, APPDATA: path.join(runRoot, "roaming"), LOCALAPPDATA: path.join(runRoot, "local"), WEBVIEW2_USER_DATA_FOLDER: profile, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port} --autoplay-policy=no-user-gesture-required`, VE_TEST_MEDIA_CHUNK_MIB: String(chunk) } });
  let browser, sampler;
  const samplesFile = path.join(evidence, `${key}.jsonl`);
  const result = { key, kind, chunk_mib: m3 ? null : chunk, media_path: m3 ? "Developer-only direct HTTP Range, no response chunk cap" : "M1 custom protocol", codec, scenario, repeat, file_bytes: statSync(file).size, seed: "0x51eecafe", completed: false };
  try {
    for (let i = 0; i < 200; i++) { try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`); break; } catch { if (child.exitCode !== null) throw new Error("Desktop exited before CDP attached"); await sleep(100); } }
    if (!browser) throw new Error("Desktop CDP startup timed out");
    const page = browser.contexts()[0].pages()[0];
    const cdp = await page.context().newCDPSession(page);
    const decoderProperties = [];
    cdp.on("Media.playerPropertiesChanged", event => {
      for (const property of event.properties) if (/decoder|platformvideo|videotrack|codec/i.test(property.name)) decoderProperties.push({ player_id: event.playerId, ...property });
    });
    await cdp.send("Media.enable");
    await page.getByRole("heading", { name: "Home", exact: true }).waitFor();
    await page.getByRole("button", { name: "History", exact: true }).click();
    const openPlayer = async () => {
      if (lowMemory) await page.evaluate(() => window.__TAURI_INTERNALS__.invoke("desktop_test", { operation: "memory-target", args: false }));
      if (m3) {
        const connection = JSON.parse(readFileSync(path.join(home, "serve.json"), "utf8"));
        const response = await fetch(`http://127.0.0.1:${connection.port}/v1/fixture-url`, { method: "POST", headers: { Authorization: `Bearer ${connection.token}`, "Content-Type": "application/json" }, body: "{}" });
        if (!response.ok) throw new Error(`M3 token issuance failed: ${response.status}`);
        const { url } = await response.json();
        await page.evaluate(url => {
          window.__m3FixtureUrl = url;
          if (window.__m3FixtureInstalled) return;
          window.__m3FixtureInstalled = true;
          const setAttribute = Element.prototype.setAttribute;
          Element.prototype.setAttribute = function(name, value) { return setAttribute.call(this, name, this instanceof HTMLVideoElement && name === "src" && String(value).startsWith("http://ve-media.localhost/") ? window.__m3FixtureUrl : value); };
          const src = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, "src");
          Object.defineProperty(HTMLMediaElement.prototype, "src", { ...src, set(value) { src.set.call(this, this instanceof HTMLVideoElement && String(value).startsWith("http://ve-media.localhost/") ? window.__m3FixtureUrl : value); } });
        }, url);
      }
      await page.locator(".history-card button").first().click();
      await page.locator("video").waitFor();
      await page.waitForFunction(() => document.querySelector("video")?.readyState >= 2);
      result.duration_seconds = await page.locator("video").evaluate(v => { v.pause(); v.muted = true; v.loop = true; return v.duration; });
      if (m3 && !await page.locator("video").evaluate(v => v.src.includes("/v1/fixture-playback/"))) throw new Error("M3 did not replace the media source before playback");
    };
    const closePlayer = async () => {
      await page.getByRole("dialog", { name: "Video details" }).getByRole("button", { name: "Close", exact: true }).click();
      if (lowMemory) await page.evaluate(() => window.__TAURI_INTERNALS__.invoke("desktop_test", { operation: "memory-target", args: true }));
    };
    await openPlayer();
    if (scenario === "repeat") {
      sampler = spawn(python, [sampleScript, String(child.pid), samplesFile], { windowsHide: true, stdio: "ignore" });
      await sleep(10500);
      result.cycles = [];
      result.play_time_ms = Date.now();
      for (let cycle = 1; cycle <= 10; cycle++) {
        if (cycle > 1) await openPlayer();
        const began = Date.now();
        await page.evaluate(async fractions => {
          const v = document.querySelector("video"), began = performance.now();
          await v.play();
          for (let i = 0; i < 3; i++) {
            const left = 5000 + i * 10000 - (performance.now() - began);
            if (left > 0) await new Promise(resolve => setTimeout(resolve, left));
            v.currentTime = fractions[i] * v.duration;
          }
          const left = 30000 - (performance.now() - began);
          if (left > 0) await new Promise(resolve => setTimeout(resolve, left));
        }, positions.slice((cycle - 1) % 18, (cycle - 1) % 18 + 3));
        await closePlayer();
        const closed = Date.now();
        await sleep(30500);
        result.cycles.push({ cycle, play_time_ms: began, closed_ms: closed });
        progress(`REPEAT ${key} cycle ${cycle}/10 closed for 30 s`);
      }
      if (codec === "av1") { progress(`IDLE ${key} for remaining 270 s`); for (let i = 0; i < 9; i++) { await sleep(30000); progress(`IDLE ${key} ${60 + i * 30} s after close`); } }
      sampler.kill(); await sleep(100);
      const samples = readFileSync(samplesFile, "utf8").trim().split("\n").map(JSON.parse);
      if (samples.some(row => row.access_errors.length)) throw new Error("Private Bytes sampling was incomplete");
      const nearest = target => samples.reduce((a, b) => Math.abs(a.time_ms - target) < Math.abs(b.time_ms - target) ? a : b);
      const roles = row => Object.fromEntries([...new Set(row.processes.map(p => p.role))].map(role => [role, row.processes.filter(p => p.role === role).reduce((sum, p) => sum + p.private_bytes, 0)]));
      for (const cycle of result.cycles) { const row = nearest(cycle.closed_ms + 30000); Object.assign(cycle, { sample_time_ms: row.time_ms, total_private_bytes: row.total_private_bytes, roles: roles(row), processes: row.processes }); }
      result.repeat_growth_private_bytes = result.cycles[9].total_private_bytes - result.cycles[0].total_private_bytes;
      result.repeat_passed = result.repeat_growth_private_bytes <= 50_000_000;
      const baseline = samples.filter(row => row.time_ms >= result.play_time_ms - 10000 && row.time_ms < result.play_time_ms);
      result.baseline_mean_private_bytes = mean(baseline.map(row => row.total_private_bytes));
      if (codec === "av1") { const row = nearest(result.cycles[9].closed_ms + 300000); result.idle_5_minutes = { ...row, roles: roles(row), growth_private_bytes: row.total_private_bytes - result.baseline_mean_private_bytes }; }
    } else if (scenario === "timing") {
      const timings = await page.evaluate(async fractions => {
        const v = document.querySelector("video"), src = v.src, starts = [], seeks = [];
        for (let i = 0; i < 10; i++) {
          v.pause(); v.removeAttribute("src"); v.load();
          const start = performance.now(), frame = new Promise(resolve => v.requestVideoFrameCallback(resolve));
          v.src = `${src}?repeat=${i}`; await v.play(); await frame; starts.push(performance.now() - start); v.pause();
          const began = performance.now(), sought = new Promise(resolve => v.addEventListener("seeked", resolve, { once: true }));
          v.currentTime = fractions[i] * v.duration; await sought; await new Promise(resolve => requestAnimationFrame(resolve)); seeks.push(performance.now() - began);
        }
        return { starts_ms: starts, seeks_ms: seeks };
      }, positions);
      Object.assign(result, timings, { start_median_ms: median(timings.starts_ms), seek_median_ms: median(timings.seeks_ms) });
    } else {
      sampler = spawn(python, [sampleScript, String(child.pid), samplesFile], { windowsHide: true, stdio: "ignore" });
      await sleep(10500);
      result.play_time_ms = Date.now();
      const heartbeat = setInterval(() => progress(`RUNNING ${key}, ${Math.round((Date.now() - result.play_time_ms) / 1000)} s`), 30000);
      try {
        await page.evaluate(async ({ scenario, fractions }) => {
          const v = document.querySelector("video"), began = performance.now();
          const until = async ms => { const left = ms - (performance.now() - began); if (left > 0) await new Promise(resolve => setTimeout(resolve, left)); };
          v.loop = true; await v.play();
          if (scenario === "P") {
            for (let i = 0; i < 20; i++) { await until(3000 + i * 6000); v.currentTime = fractions[i] * v.duration; }
            await until(120000);
          } else if (scenario === "R") {
            for (let i = 0; i < 20; i++) { await until(i * 100); v.currentTime = fractions[i] * v.duration; }
            await until(32000);
          } else {
            for (let i = 0; i < 19; i++) { await until((i + 1) * 30000); v.currentTime = fractions[i] * v.duration; }
            await until(600000);
          }
        }, { scenario, fractions: positions });
      } finally { clearInterval(heartbeat); }
      result.play_end_ms = Date.now();
      await closePlayer();
      result.closed_ms = Date.now();
      await sleep(30500);
      result.residual_time_ms = Date.now();
      sampler.kill(); await sleep(100);
      const samples = readFileSync(samplesFile, "utf8").trim().split("\n").map(line => JSON.parse(line));
      if (samples.some(row => row.access_errors.length)) throw new Error("Private Bytes sampling was incomplete");
      const baseline = samples.filter(row => row.time_ms >= result.play_time_ms - 10000 && row.time_ms < result.play_time_ms);
      if (baseline.length < 9) throw new Error("Insufficient 10-second baseline samples");
      result.baseline_mean_private_bytes = mean(baseline.map(row => row.total_private_bytes));
      const playback = samples.filter(row => row.time_ms >= result.play_time_ms && row.time_ms <= result.play_end_ms);
      const peak = playback.reduce((a, b) => a.total_private_bytes > b.total_private_bytes ? a : b);
      result.peak_total_private_bytes = peak.total_private_bytes;
      result.growth_private_bytes = peak.total_private_bytes - result.baseline_mean_private_bytes;
      result.processes_at_total_peak = peak.processes;
      result.per_process = [...new Set(samples.flatMap(row => row.processes.map(p => p.pid)))].map(pid => {
        const observations = samples.flatMap(row => row.processes.filter(p => p.pid === pid));
        const before = baseline.map(row => row.processes.find(p => p.pid === pid)?.private_bytes || 0);
        const playing = playback.flatMap(row => row.processes.filter(p => p.pid === pid));
        return { pid, name: observations[0].name, role: observations[0].role, baseline_mean_private_bytes: mean(before), peak_private_bytes: Math.max(0, ...playing.map(p => p.private_bytes)), growth_private_bytes: Math.max(0, ...playing.map(p => p.private_bytes)) - mean(before) };
      });
      result.shell_peak_private_bytes = result.per_process.find(p => p.pid === child.pid)?.peak_private_bytes;
      const nearest = target => samples.reduce((a, b) => Math.abs(a.time_ms - target) < Math.abs(b.time_ms - target) ? a : b);
      const residual = nearest(result.closed_ms + 30000);
      result.residual_total_private_bytes = residual.total_private_bytes;
      result.residual_growth_private_bytes = residual.total_private_bytes - result.baseline_mean_private_bytes;
      result.residual_offset_ms = residual.time_ms - result.closed_ms;
      result.residual_processes = residual.processes;
      if (scenario === "steady") {
        const nearestPlaying = target => playback.reduce((a, b) => Math.abs(a.time_ms - target) < Math.abs(b.time_ms - target) ? a : b);
        result.at_2_minutes = nearestPlaying(result.play_time_ms + 120000);
        result.at_10_minutes = nearestPlaying(result.play_time_ms + 600000);
        result.steady_growth_private_bytes = result.at_10_minutes.total_private_bytes - result.at_2_minutes.total_private_bytes;
      }
    }
    result.engine_fetch_peak = fixture.control.media_peak;
    result.decoder_properties = decoderProperties;
    result.engine_fetch_total = fixture.control.media_total;
    result.python_engine_processes_separate = fixture.memory();
    if (kind === "tauri") result.shell_fetch_counters = await page.evaluate(() => window.__TAURI_INTERNALS__.invoke("desktop_test", { operation: "state", args: null }));
    if (m3 && result.shell_fetch_counters.media_total !== 0) throw new Error("M3 comparison unexpectedly used the M1 custom protocol");
    result.completed = true;
    progress(`DONE ${key} growth=${result.growth_private_bytes ?? "timing"}, residual=${result.residual_growth_private_bytes ?? "n/a"}`);
  } catch (error) { result.error = String(error.stack || error); progress(`ERROR ${key}: ${error.message}`); throw error; }
  finally {
    writeFileSync(output, JSON.stringify(result, null, 2));
    if (sampler) sampler.kill();
    if (browser) await browser.close().catch(() => {});
    child.kill();
    await sleep(1500);
    await fixture.close();
  }
}

if (followup) {
  if (process.env.VE_M2_FINAL_LIFECYCLE === "1") {
    await run("tauri", 1, "av1", "timing", 1);
    await run("tauri", 1, "av1", "repeat", 1);
  } else if (lowMemory) {
    await run("tauri", 1, "av1", "timing", 1);
    await run("tauri", 1, "av1", "P", 1);
  } else if (m3) {
    for (let repeat = 1; repeat <= 3; repeat++) await run("tauri", 1, "av1", "P", repeat);
    await run("tauri", 1, "av1", "repeat", 1);
  } else {
    for (const [kind, codec] of [["tauri", "av1"], ["electron", "av1"], ["tauri", "h264"]]) await run(kind, 1, codec, "repeat", 1);
    await run("electron", 1, "h264", "timing", 1);
  }
} else {
for (const chunk of [8, 2, 1]) for (const codec of ["h264", "av1"]) {
  for (const kind of ["electron", "tauri"]) await run(kind, chunk, codec, "timing", 1);
  for (const scenario of ["P", "R"]) for (let repeat = 1; repeat <= 3; repeat++) for (const kind of ["electron", "tauri"]) await run(kind, chunk, codec, scenario, repeat);
  for (const kind of ["electron", "tauri"]) await run(kind, chunk, codec, "steady", 1);
}
}
progress("MATRIX COMPLETE; compare medians and every residual/steady sample before selecting a chunk.");

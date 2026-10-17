import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
const root = path.resolve(process.env.VE_M2_EVIDENCE || "");
const median = values => { const s = values.toSorted((a, b) => a - b); return (s[Math.floor((s.length - 1) / 2)] + s[Math.ceil((s.length - 1) / 2)]) / 2; };
const load = (chunk, codec, scenario, repeat, kind) => {
  const file = path.join(root, `${chunk}MiB-${codec}-${scenario}-${repeat}-${kind}.json`);
  if (!existsSync(file)) return null;
  const value = JSON.parse(readFileSync(file, "utf8"));
  if (!value.completed) return null;
  if (scenario === "steady") {
    const samples = readFileSync(file.replace(/\.json$/, ".jsonl"), "utf8").trim().split("\n").map(line => JSON.parse(line));
    const playing = samples.filter(row => row.time_ms >= value.play_time_ms && row.time_ms <= value.play_end_ms);
    const nearest = target => playing.reduce((a, b) => Math.abs(a.time_ms - target) < Math.abs(b.time_ms - target) ? a : b);
    value.raw_summary_used_post_close_sample = value.at_10_minutes.time_ms > value.play_end_ms;
    value.at_2_minutes = nearest(value.play_time_ms + 120000);
    value.at_10_minutes = nearest(value.play_time_ms + 600000);
    value.steady_growth_private_bytes = value.at_10_minutes.total_private_bytes - value.at_2_minutes.total_private_bytes;
    value.sample_offsets_ms = [value.at_2_minutes.time_ms - value.play_time_ms - 120000, value.at_10_minutes.time_ms - value.play_time_ms - 600000];
  }
  return value;
};
const rows = [], processes = [], missing = [];
for (const chunk of [8, 2, 1]) for (const codec of ["h264", "av1"]) {
  const row = { chunk_mib: chunk, codec, apps: {} };
  let complete = true;
  for (const kind of ["electron", "tauri"]) {
    const timing = load(chunk, codec, "timing", 1, kind);
    const steady = load(chunk, codec, "steady", 1, kind);
    const P = [1, 2, 3].map(i => load(chunk, codec, "P", i, kind));
    const R = [1, 2, 3].map(i => load(chunk, codec, "R", i, kind));
    if (!timing || !steady || [...P, ...R].some(value => !value)) { missing.push(`${chunk}MiB-${codec}-${kind}`); complete = false; continue; }
    const metrics = values => ({ growth_median_private_bytes: median(values.map(v => v.growth_private_bytes)), residual_median_private_bytes: median(values.map(v => v.residual_growth_private_bytes)), shell_peak_median_private_bytes: median(values.map(v => v.shell_peak_private_bytes)), shell_peak_max_private_bytes: Math.max(...values.map(v => v.shell_peak_private_bytes)), engine_fetch_peak: Math.max(...values.map(v => v.engine_fetch_peak)), client_fetch_peak: Math.max(...values.map(v => v.shell_fetch_counters?.media_peak || 0)), runs: values.map(v => ({ key: v.key, growth_private_bytes: v.growth_private_bytes, residual_private_bytes: v.residual_growth_private_bytes })) });
    row.apps[kind] = { timing: { play_start_median_ms: timing.start_median_ms, seek_median_ms: timing.seek_median_ms }, P: metrics(P), R: metrics(R), steady_growth_private_bytes: steady.steady_growth_private_bytes, steady_residual_growth_private_bytes: steady.residual_growth_private_bytes, steady_sample_offsets_ms: steady.sample_offsets_ms, corrected_post_close_sample: steady.raw_summary_used_post_close_sample };
    for (const run of [...P, ...R, steady]) for (const process of run.per_process) processes.push({ chunk_mib: chunk, codec, app: kind, scenario: run.scenario, repeat: run.repeat, ...process });
  }
  if (complete) {
    const e = row.apps.electron, t = row.apps.tauri;
    row.gates = { timing: t.timing.play_start_median_ms <= 500 && t.timing.seek_median_ms <= 300, P_growth: t.P.growth_median_private_bytes <= e.P.growth_median_private_bytes + 100_000_000, R_growth: t.R.growth_median_private_bytes <= e.R.growth_median_private_bytes + 100_000_000, P_residual: t.P.residual_median_private_bytes <= Math.max(50_000_000, e.P.residual_median_private_bytes), R_residual: t.R.residual_median_private_bytes <= Math.max(50_000_000, e.R.residual_median_private_bytes), steady: t.steady_growth_private_bytes <= 50_000_000 };
    row.passed = Object.values(row.gates).every(Boolean);
  }
  rows.push(row);
}
const selected = [8, 2, 1].find(chunk => rows.filter(row => row.chunk_mib === chunk).every(row => row.passed)) || null;
const result = { method: "Timing medians of ten; P/R medians of three; 1 s Windows Private Bytes samples. Steady samples are constrained to the active play interval, never after player close. Per-process peaks need not coincide and must not be summed as the total peak.", complete: missing.length === 0, selected_chunk_mib: selected, rows, missing, processes };
writeFileSync(path.join(root, "summary.json"), JSON.stringify(result, null, 2));
const headers = ["chunk_mib", "codec", "app", "scenario", "repeat", "pid", "name", "role", "baseline_mean_private_bytes", "peak_private_bytes", "growth_private_bytes"];
writeFileSync(path.join(root, "per-process.csv"), [headers.join(","), ...processes.map(p => headers.map(key => p[key]).join(","))].join("\n") + "\n");
console.log(JSON.stringify({ complete: result.complete, selected_chunk_mib: selected, missing, rows: rows.map(({ chunk_mib, codec, gates, passed }) => ({ chunk_mib, codec, gates, passed })) }, null, 2));
if (process.argv.includes("--require-complete") && !result.complete) process.exitCode = 1;

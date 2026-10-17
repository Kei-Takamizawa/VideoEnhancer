import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = path.resolve(process.env.VE_M2_FOLLOWUP_EVIDENCE || "../../evidence/P1t");
const load = (folder, name) => {
  const file = path.join(root, folder, name + ".json");
  if (!existsSync(file)) return null;
  const result = JSON.parse(readFileSync(file, "utf8"));
  if (!result.completed) return null;
  if (result.scenario === "repeat") {
    const samples = readFileSync(file.replace(/\.json$/, ".jsonl"), "utf8").trim().split("\n").map(JSON.parse);
    const baseline = samples.filter(s => s.time_ms >= result.play_time_ms - 10000 && s.time_ms < result.play_time_ms);
    if (baseline.length < 9 || samples.some(s => s.access_errors.length)) throw new Error(`Incomplete sampling: ${name}`);
    const roles = [...new Set(baseline.flatMap(s => s.processes.map(p => p.role)))];
    result.baseline_samples = baseline.length;
    result.baseline_roles_mean_private_bytes = Object.fromEntries(roles.map(role => [role, baseline.reduce((sum, s) => sum + s.processes.filter(p => p.role === role).reduce((sum, p) => sum + p.private_bytes, 0), 0) / baseline.length]));
    result.cycle10_minus_cycle1_roles_private_bytes = Object.fromEntries([...new Set([...Object.keys(result.cycles[0].roles), ...Object.keys(result.cycles[9].roles)])].map(role => [role, (result.cycles[9].roles[role] || 0) - (result.cycles[0].roles[role] || 0)]));
  }
  return result;
};
const repeats = [
  ["M1 Tauri AV1", "m2-followup-m1", "1MiB-av1-repeat-1-tauri"],
  ["Electron AV1", "m2-followup-m1", "1MiB-av1-repeat-1-electron"],
  ["M1 Tauri H264", "m2-followup-m1", "1MiB-h264-repeat-1-tauri"],
  ["M3 Tauri AV1", "m2-followup-m3", "M3-1MiB-av1-repeat-1-tauri"],
].map(([name, folder, key]) => ({ name, result: load(folder, key) }));
const P = [1, 2, 3].map(i => load("m2-followup-m3", `M3-1MiB-av1-P-${i}-tauri`));
const low = { timing: load("m2-followup-low", "Low-1MiB-av1-timing-1-tauri"), P: load("m2-followup-low", "Low-1MiB-av1-P-1-tauri") };
const electronH264 = load("m2-followup-m1", "1MiB-h264-timing-1-electron");
const complete = repeats.every(row => row.result) && P.every(Boolean) && !!electronH264;
const result = { complete, method: "Same 2 GB synthetic files, fixed seek seed, 1 s app-descendant Private Bytes samples; repeat gate cycle 10 minus cycle 1 <= 50 MB. M3 requires explicit local developer flag and a separate CSP build; it is not shipped.", repeats, M3_P: P, low_memory_attempt: low, electron_h264_decoder: electronH264?.decoder_properties };
writeFileSync(path.join(root, "media-followup-summary.json"), JSON.stringify(result, null, 2));
const csv = ["app,cycle,total_private_bytes,role,role_private_bytes"];
for (const { name, result } of repeats) for (const cycle of result?.cycles || []) for (const [role, bytes] of Object.entries(cycle.roles)) csv.push(`${name},${cycle.cycle},${cycle.total_private_bytes},${role},${bytes}`);
writeFileSync(path.join(root, "media-followup-roles.csv"), csv.join("\n") + "\n");
console.log(JSON.stringify({ complete, repeats: repeats.map(({ name, result }) => ({ name, growth_MB: result?.repeat_growth_private_bytes / 1e6, passed: result?.repeat_passed, idle_5min_MB: result?.idle_5_minutes?.total_private_bytes / 1e6, decoder: result?.decoder_properties?.filter(p => /decoder/i.test(p.name)) })), M3_P: P.map(p => p && ({ growth_MB: p.growth_private_bytes / 1e6, residual_MB: p.residual_growth_private_bytes / 1e6 })), low: low.P && { residual_MB: low.P.residual_growth_private_bytes / 1e6, play_ms: low.timing?.start_median_ms, seek_ms: low.timing?.seek_median_ms } }, null, 2));
if (process.argv.includes("--require-complete") && !complete) process.exitCode = 1;

import type { Job } from "./types";

export function historyWarning(job: Job): string {
  const reasons: string[] = [];
  if (job.state === "failed") reasons.push(job.failure_reason || "Processing did not finish.");
  if (job.state === "cancelled" && job.output_state !== "present") reasons.push("Cancelled before the output was ready.");
  if (job.output_state === "missing") reasons.push("The finished output is missing.");
  if (job.output_changed) reasons.push("The finished output changed after this job completed.");
  if (job.interpolation_fallback_parts) reasons.push(`Frame doubling used a simpler method for ${job.interpolation_fallback_parts} parts`);
  reasons.push(...job.file_removal_warnings || []);
  return reasons.join(" ");
}

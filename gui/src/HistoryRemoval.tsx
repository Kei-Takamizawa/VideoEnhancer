import { useState } from "react";
import { ActionButton } from "./ActionButton";
import type { Job } from "./types";

export function HistoryRemoval({ jobs, clear = false, action, close }: {
  jobs: Job[]; clear?: boolean; action(job: Job, name: string, data?: unknown): void; close(): void;
}) {
  const [output, setOutput] = useState(false), [original, setOriginal] = useState(false);
  return <div className="modal-shade"><div className="dialog" role="dialog" aria-modal="true" aria-label={clear ? "Clear history?" : "Remove from history?"}>
    <h2>{clear ? "Clear history?" : "Remove from history?"}</h2>
    <p>Remove {jobs.length} records. You can undo the record removal for 10 seconds. Files moved to the Recycle Bin stay there when you undo.</p>
    <label className="check"><input type="checkbox" checked={output} onChange={event => setOutput(event.target.checked)} />Also move the finished videos to the Recycle Bin</label>
    <label className="check"><input type="checkbox" checked={original} onChange={event => setOriginal(event.target.checked)} />Also move the original videos to the Recycle Bin</label>
    <div className="dialog-actions"><ActionButton onClick={close}>Keep history</ActionButton>
      <ActionButton className="danger" disabled={!jobs.length} onClick={() => { action(jobs[0], clear ? "clear-history" : "remove", { ids: jobs.map(job => job.id), output, original }); close(); }}>{clear ? "Clear history" : "Remove from history"}</ActionButton></div>
  </div></div>;
}

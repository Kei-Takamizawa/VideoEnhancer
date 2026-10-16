import { ErrorBoundary } from "./ErrorBoundary";
import { useState } from "react";
import { ActionButton } from "./ActionButton";
import type { Job } from "./types";

function HistoryRemovalContent({ jobs, clear = false, filesOnly = false, action, close }: {
  jobs: Job[]; clear?: boolean; filesOnly?: boolean; action(job: Job, name: string, data?: unknown): void; close(): void;
}) {
  const [history, setHistory] = useState(!filesOnly);
  const [output, setOutput] = useState(filesOnly), [original, setOriginal] = useState(false);
  return <div className="modal-shade"><div className="dialog" role="dialog" aria-modal="true" aria-label="Remove records or video files?">
    <h2>Remove records or video files?</h2>
    <p>Choose what to remove for {jobs.length} records. You can undo History removal for 10 seconds. Files moved to the Recycle Bin stay there when you undo.</p>
    <label className="check"><input type="checkbox" checked={history} onChange={event => setHistory(event.target.checked)} />Remove from History</label>
    <label className="check"><input type="checkbox" checked={output} onChange={event => setOutput(event.target.checked)} />Move the finished videos to the Recycle Bin</label>
    <label className="check"><input type="checkbox" checked={original} onChange={event => setOriginal(event.target.checked)} />Move the originals to the Recycle Bin</label>
    <div className="dialog-actions"><ActionButton onClick={close}>Cancel</ActionButton>
      <ActionButton className="danger" disabled={!jobs.length || (!history && !output && !original)} onClick={() => { action(jobs[0], clear ? "clear-history" : "remove", { ids: jobs.map(job => job.id), history, output, original }); close(); }}>Remove selected items</ActionButton></div>
  </div></div>;
}

export function HistoryRemoval(props: Parameters<typeof HistoryRemovalContent>[0]) {
  return <ErrorBoundary scope="Remove videos"><HistoryRemovalContent {...props} /></ErrorBoundary>;
}

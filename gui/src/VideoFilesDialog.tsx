import { useState } from "react";
import { ActionButton } from "./ActionButton";
import type { Api } from "./api";
import type { Job } from "./types";

export function VideoFilesDialog({ jobs, api, close }: { jobs: Job[]; api: Api; close(): void }) {
  const [output, setOutput] = useState(true), [original, setOriginal] = useState(false);
  const [busy, setBusy] = useState(false), [result, setResult] = useState("");
  return <div className="modal-shade"><div className="dialog" role="dialog" aria-modal="true" aria-label="Delete video files?">
    <h2>Delete video files?</h2><p>Move selected files from {jobs.length} records to the Recycle Bin. Safety checks keep files that cannot be recycled.</p>
    <label className="check"><input type="checkbox" checked={output} onChange={event => setOutput(event.target.checked)} disabled={busy} />Finished output</label>
    <label className="check"><input type="checkbox" checked={original} onChange={event => setOriginal(event.target.checked)} disabled={busy} />Original video</label>
    <div className="dialog-actions"><ActionButton disabled={busy} onClick={close}>Close</ActionButton><ActionButton className="danger" disabled={busy || (!output && !original)} onClick={async () => {
      setBusy(true);
      try {
        const response = await api.call<{ results: { result: string }[] }>("history/delete-files", "POST", { ids: jobs.map(job => job.id), output, original });
        const moved = response.results.filter(row => row.result === "Moved to the Recycle Bin").length;
        const missing = response.results.filter(row => row.result === "File not found").length;
        setResult(`${moved} moved, ${missing} not found, ${response.results.length - moved - missing} kept. ${response.results.filter(row => row.result.startsWith("Kept:")).map(row => row.result).join(" ")}`);
      } catch (error) { setResult((error as Error).message); } finally { setBusy(false); }
    }}>{busy ? "Checking files…" : "Move to Recycle Bin"}</ActionButton></div><p role="status">{result}</p>
  </div></div>;
}

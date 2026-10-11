import { useState } from "react";
import type { Api } from "./api";
import { duration, filename } from "./api";
import type { Job } from "./types";

export function HistoryDetail({ job, api, close, action, compare }: {
  job: Job; api?: Api; close(): void;
  action(job: Job, name: string, data?: unknown): void;
  compare(job: Job): void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [output, setOutput] = useState(true), [original, setOriginal] = useState(false);
  const [busy, setBusy] = useState(false), [results, setResults] = useState<string[]>([]);
  const gone = job.original_state === "missing" || job.original_state === "recycled";
  const fileState = (state?: string) => state === "recycled" ? "Moved to the Recycle Bin" : state === "missing" ? "File not found" : "Present";
  return <div className="modal-shade"><div className="dialog history-detail" role="dialog" aria-modal="true" aria-label={deleting ? "Delete video files?" : "Video details"}>
    <h2>{deleting ? "Delete video files?" : filename(job.input)}</h2>
    {deleting ? <>
      <p>Move the selected files to the Recycle Bin. A safety check keeps files that cannot be recycled. Removing history is a separate action.</p>
      <label className="check"><input type="checkbox" checked={output} disabled={busy} onChange={event => setOutput(event.target.checked)} />Finished output</label>
      <label className="check"><input type="checkbox" checked={original} disabled={busy} onChange={event => setOriginal(event.target.checked)} />Original video</label>
      <p className="muted">Compare again needs the original video.</p>
      <div className="dialog-actions"><button disabled={busy} onClick={() => setDeleting(false)}>Keep files</button><button className="danger" disabled={busy || !api || (!output && !original)} onClick={async () => {
        setBusy(true);
        try {
          const response = await api!.call<{ results: { file: string; result: string }[] }>("history/delete-files", "POST", { ids: [job.id], output, original });
          setResults(response.results.map(item => `${item.file === "output" ? "Output" : "Original"}: ${item.result}`));
          setDeleting(false);
        } catch (error) { setResults([(error as Error).message]); } finally { setBusy(false); }
      }}>{busy ? "Checking files…" : "Move to Recycle Bin"}</button></div>
    </> : <>
      <dl><dt>Mode</dt><dd>{job.mode || job.settings.preset}</dd><dt>Time taken</dt><dd>{duration(job.took_seconds || 0)}</dd><dt>Output size</dt><dd>{job.output_bytes === undefined ? "Not available" : `${(job.output_bytes / 1e6).toFixed(1)} MB`}</dd><dt>Original size</dt><dd>{job.original_bytes === undefined ? "Not available" : `${(job.original_bytes / 1e6).toFixed(1)} MB`}</dd><dt>Output folder</dt><dd title={job.output_folder || job.output}>{job.output_folder || job.output}</dd><dt>Output file</dt><dd>{fileState(job.output_state)}</dd><dt>Original file</dt><dd>{fileState(job.original_state)}</dd>{job.failure_reason && <><dt>Problem</dt><dd>{job.failure_reason}</dd></>}</dl>
      {job.original_delete_result && <p role="status">{job.original_delete_result}</p>}
      <div className="actions"><button disabled={job.state !== "done" || job.output_state === "missing" || job.output_state === "recycled"} onClick={() => action(job, "play")}>Play</button><button onClick={() => action(job, "folder")}>Show in folder</button><button disabled={gone} title={gone ? "Compare again needs the original video." : ""} onClick={() => compare(job)}>Compare again</button><button onClick={() => action(job, "copy")}>Copy details</button><button onClick={() => { action(job, "remove"); close(); }}>Remove from history</button><button onClick={() => setDeleting(true)}>Delete video files…</button></div>
      <div className="dialog-actions"><button onClick={close}>Close</button></div>
    </>}
    {results.map((result, index) => <p key={index} role="status">{result}</p>)}
  </div></div>;
}

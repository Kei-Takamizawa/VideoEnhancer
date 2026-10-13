import { ActionButton } from "./ActionButton";
import { useEffect, useRef, useState } from "react";
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
  const [url, setUrl] = useState<string>();
  const [unsupported, setUnsupported] = useState(false);
  const player = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    let alive = true, object: string | undefined;
    void api?.blob?.(`queue/${job.id}/video`).then(blob => {
      if (alive) { object = URL.createObjectURL(blob); setUrl(object); }
    }).catch(() => { if (alive) setUnsupported(true); });
    return () => { alive = false; if (object) URL.revokeObjectURL(object); };
  }, [api, job.id]);
  const gone = job.original_state === "missing" || job.original_state === "recycled";
  const fileState = (state?: string) => state === "recycled" ? "Moved to the Recycle Bin" : state === "missing" ? "File not found" : "Present";
  return <div className="modal-shade"><div className="dialog history-detail" role="dialog" aria-modal="true" aria-label={deleting ? "Delete video files?" : "Video details"}>
    <h2>{deleting ? "Delete video files?" : filename(job.input)}</h2>
    {deleting ? <>
      <p>Move the selected files to the Recycle Bin. A safety check keeps files that cannot be recycled. Removing history is a separate action.</p>
      <label className="check"><input type="checkbox" checked={output} disabled={busy} onChange={event => setOutput(event.target.checked)} />Finished output</label>
      <label className="check"><input type="checkbox" checked={original} disabled={busy} onChange={event => setOriginal(event.target.checked)} />Original video</label>
      <p className="muted">Compare again needs the original video.</p>
      <div className="dialog-actions"><ActionButton disabled={busy} onClick={() => setDeleting(false)}>Keep files</ActionButton><ActionButton className="danger" disabled={busy || !api || (!output && !original)} onClick={async () => {
        setBusy(true);
        try {
          const response = await api!.call<{ results: { file: string; result: string }[] }>("history/delete-files", "POST", { ids: [job.id], output, original });
          setResults(response.results.map(item => `${item.file === "output" ? "Output" : "Original"}: ${item.result}`));
          setDeleting(false);
        } catch (error) { setResults([(error as Error).message]); } finally { setBusy(false); }
      }}>{busy ? "Checking files…" : "Move to Recycle Bin"}</ActionButton></div>
    </> : <>
      {!unsupported && <video ref={player} className="history-player" src={url} controls onError={() => setUnsupported(true)} />}
      {unsupported && <ActionButton onClick={() => window.desktop.play(job.output_state === "present" ? job.output : job.input)}>Open in your player</ActionButton>}
      <dl><dt>Mode</dt><dd>{job.mode || job.settings.preset}</dd><dt>Time taken</dt><dd>{duration(job.took_seconds || 0)}</dd><dt>Output size</dt><dd>{job.output_bytes === undefined ? "Not available" : `${(job.output_bytes / 1e6).toFixed(1)} MB`}</dd><dt>Original size</dt><dd>{job.original_bytes === undefined ? "Not available" : `${(job.original_bytes / 1e6).toFixed(1)} MB`}</dd><dt>Output folder</dt><dd title={job.output_folder || job.output}>{job.output_folder || job.output}</dd><dt>Output file</dt><dd>{fileState(job.output_state)}</dd><dt>Original file</dt><dd>{fileState(job.original_state)}</dd>{(job.failure_reason || job.error) && <><dt>Problem</dt><dd>{job.failure_reason || job.error}</dd></>}</dl>
      {job.original_delete_result && <p role="status">{job.original_delete_result}</p>}
      {job.deletion_notices?.map(notice => <p role="status" key={notice.id}>{notice.result}<ActionButton onClick={() => window.desktop.reveal(notice.guard)}>Show in folder</ActionButton></p>)}
      <div className="actions">{job.state === "failed" && <ActionButton onClick={() => action(job, "retry")}>Retry</ActionButton>}<ActionButton disabled={!url || unsupported} onClick={() => { if (player.current?.paused) void player.current.play(); else player.current?.pause(); }}>Play or Pause</ActionButton><ActionButton onClick={() => action(job, "folder")}>Show in folder</ActionButton><ActionButton disabled={gone} title={gone ? "Compare again needs the original video." : ""} onClick={() => compare(job)}>Compare again</ActionButton><ActionButton onClick={() => action(job, "copy")}>Copy details</ActionButton><ActionButton onClick={() => { action(job, "remove"); close(); }}>Remove from history</ActionButton><ActionButton onClick={() => setDeleting(true)}>Delete video files…</ActionButton></div>
      <div className="dialog-actions"><ActionButton onClick={close}>Close</ActionButton></div>
    </>}
    {results.map((result, index) => <p key={index} role="status">{result}</p>)}
  </div></div>;
}

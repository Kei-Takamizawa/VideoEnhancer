import { ErrorBoundary } from "./ErrorBoundary";
import { historyWarning } from "./history";
import { ActionButton } from "./ActionButton";
import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { duration, filename } from "./api";
import type { Job } from "./types";
import { HEVC_STORE, hevcPlaybackSupported } from "./desktop";

function HistoryDetailContent({ job, close, action, compare }: {
  job: Job; api?: Api; close(): void;
  action(job: Job, name: string, data?: unknown): void;
  compare(job: Job): void;
}) {
  const url = `http://ve-media.localhost/${encodeURIComponent(job.id)}`;
  const hevcMissing = job.settings.codec === "hevc" && !hevcPlaybackSupported();
  const [unsupported, setUnsupported] = useState(false);
  const player = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    setUnsupported(false);
  }, [job.id]);
  const gone = job.original_state === "missing" || job.original_state === "recycled";
  const fileState = (state?: string) => state === "recycled" ? "Moved to the Recycle Bin" : state === "missing" ? "File not found" : "Present";
  return <div className="modal-shade"><div className="dialog history-detail" role="dialog" aria-modal="true" aria-label="Video details">
    <h2>{filename(job.input)}</h2>
      {job.source && <p>{job.source.url} <ActionButton onClick={() => window.desktop.sourceLink?.(job.id)}>Source link</ActionButton></p>}
      {hevcMissing && <div role="status"><p>This PC can't play HEVC videos inside the app. Install HEVC Video Extensions from the Microsoft Store, or open the video in your default player.</p><ActionButton onClick={() => window.desktop.openExternal?.(HEVC_STORE)}>Open Microsoft Store</ActionButton><ActionButton onClick={() => window.desktop.play(job.output_state === "present" ? job.output : job.input)}>Open in default player</ActionButton></div>}
      {!unsupported && !hevcMissing && <video ref={player} className="history-player" src={url} controls onError={() => setUnsupported(true)} />}
      {unsupported && <ActionButton onClick={() => window.desktop.play(job.output_state === "present" ? job.output : job.input)}>Open in your player</ActionButton>}
      <dl><dt>Mode</dt><dd>{job.mode || job.settings.preset}</dd><dt>Time taken</dt><dd>{duration(job.took_seconds || 0)}</dd><dt>Output size</dt><dd>{job.output_bytes === undefined ? "Not available" : `${(job.output_bytes / 1e6).toFixed(1)} MB`}</dd><dt>Original size</dt><dd>{job.original_bytes === undefined ? "Not available" : `${(job.original_bytes / 1e6).toFixed(1)} MB`}</dd><dt>Output folder</dt><dd title={job.output_folder || job.output}>{job.output_folder || job.output}</dd><dt>Output file</dt><dd>{job.output_changed ? "Changed since this job completed" : fileState(job.output_state)}</dd><dt>Original file</dt><dd>{fileState(job.original_state)}</dd>{(job.failure_reason || job.error) && <><dt>Problem</dt><dd>{job.failure_reason || job.error}</dd></>}</dl>
      {job.original_delete_result && <p role="status">{job.original_delete_result}</p>}
      {historyWarning(job) && <p className="warning-text" role="status">{historyWarning(job)}</p>}
      {job.deletion_notices?.map(notice => <p role="status" key={notice.id}>{notice.result}<ActionButton onClick={() => window.desktop.reveal(notice.guard)}>Show in folder</ActionButton></p>)}
      <div className="actions">{job.state === "failed" && <ActionButton onClick={() => action(job, "retry")}>Retry</ActionButton>}<ActionButton disabled={!url || unsupported || hevcMissing} onClick={() => { if (player.current?.paused) void player.current.play(); else player.current?.pause(); }}>Play or Pause</ActionButton><ActionButton onClick={() => action(job, "folder")}>Show in folder</ActionButton><ActionButton disabled={gone} title={gone ? "Compare again needs the original video." : ""} onClick={() => compare(job)}>Compare again</ActionButton><ActionButton onClick={() => action(job, "copy")}>Copy details</ActionButton><ActionButton onClick={() => { action(job, "remove"); close(); }}>Remove from history</ActionButton><ActionButton onClick={() => { action(job, "delete-files"); close(); }}>Delete video files…</ActionButton></div>
      <div className="dialog-actions"><ActionButton onClick={close}>Close</ActionButton></div>

  </div></div>;
}

export function HistoryDetail(props: Parameters<typeof HistoryDetailContent>[0]) {
  return <ErrorBoundary scope="Video details"><HistoryDetailContent {...props} /></ErrorBoundary>;
}

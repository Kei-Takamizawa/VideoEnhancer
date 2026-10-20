import { Check, GripVertical } from "lucide-react";
import { historyWarning } from "./history";
import { ActionButton } from "./ActionButton";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Api } from "./api";
import { duration, filename, when } from "./api";
import type { Health, Job, Plan, Queue } from "./types";
import { HistoryDetail } from "./HistoryDetail";

export function historyWhen(value?: string, now = new Date()) {
  if (!value) return "Not available";
  const ended = new Date(value),
    yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const clock = ended.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  if (ended.toDateString() === now.toDateString()) return `Today ${clock}`;
  if (ended.toDateString() === yesterday.toDateString())
    return `Yesterday ${clock}`;
  return `${ended.toLocaleDateString("en-US", { weekday: "short" })} ${String(ended.getMonth() + 1).padStart(2, "0")}/${String(ended.getDate()).padStart(2, "0")} ${clock}`;
}
export function problemWhen(value: string) {
  const date = new Date(value);
  return `${date.toLocaleDateString("en-US", { weekday: "short" })} ${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}, ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Home: "M3 10 12 3l9 7v11h-6v-7H9v7H3Z",
    History: "M3 12a9 9 0 1 0 3-7M3 3v6h6M12 7v5l3 2",
    Schedule: "M4 5h16v16H4ZM8 3v4M16 3v4M4 10h16",
    Models: "m12 3 9 5-9 5-9-5Zm-9 9 9 5 9-5m-18 5 9 5 9-5",
    Settings:
      "M8.94 4.61L10.61 4.12L10.09 1.17L13.91 1.17L13.39 4.12L15.06 4.61L16.59 5.45L18.31 2.99L21.01 5.69L18.55 7.41L19.39 8.94L19.88 10.61L22.83 10.09L22.83 13.91L19.88 13.39L19.39 15.06L18.55 16.59L21.01 18.31L18.31 21.01L16.59 18.55L15.06 19.39L13.39 19.88L13.91 22.83L10.09 22.83L10.61 19.88L8.94 19.39L7.41 18.55L5.69 21.01L2.99 18.31L5.45 16.59L4.61 15.06L4.12 13.39L1.17 13.91L1.17 10.09L4.12 10.61L4.61 8.94L5.45 7.41L2.99 5.69L5.69 2.99L7.41 5.45ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  };
  return (
    <svg
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}

export function Thumbnail({
  job,
  api,
  small = false,
}: {
  job: Job;
  api?: Api;
  small?: boolean;
}) {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    let alive = true,
      object: string | undefined;
    if (api && job.state !== "downloading" && !job.link_unanalysed)
      void api
        .blob(`queue/${job.id}/thumbnail`)
        .then((blob) => {
          if (!blob.type.startsWith("image/")) return;
          if (alive) {
            object = URL.createObjectURL(blob);
            setUrl(object);
          }
        })
        .catch(() => {});
    return () => {
      alive = false;
      if (object) URL.revokeObjectURL(object);
    };
  }, [api, job.id, job.state]);
  return (
    <div
      className={`thumbnail ${small ? "small" : ""} ${job.media.display_height > job.media.display_width ? "portrait" : "landscape"}`}
    >
      {url && <img src={url} alt="" />}
    </div>
  );
}

type Actions = {
  action(job: Job, name: string, data?: unknown): void;
  trial(job: Job): void;
};
function DownloadCard({ job, cancel }: { job: Job; cancel(): void }) {
  const download = job.download;
  return <article className="now-card"><div className="now-details">
    <p className="muted">{download?.phase || "Downloading"}</p>
    <h2>{job.source?.title || filename(job.input)}</h2>
    <div className="now-percent">{download?.percent == null ? "Downloading" : `${download.percent.toFixed(0)}%`}</div>
    <progress aria-label="Download progress" max="100" value={download?.percent ?? undefined} />
    <p>{download?.bytes_per_second ? `${(download.bytes_per_second / 1e6).toFixed(1)} MB/s` : "Waiting for download speed"} · {download?.remaining_seconds != null ? `${duration(download.remaining_seconds)} left` : "Time left after download starts"}</p>
    <p>Processing: {job.estimate_after_download ? "after download" : `${duration(job.estimate.seconds)} · Done ${when(job.eta)}`}</p>
    <ActionButton onClick={cancel}>Cancel download</ActionButton>
  </div></article>;
}
export function JobMenu({
  job,
  action,
  trial,
  position = 0,
}: Actions & { job: Job; position?: number }) {
  const [open, setOpen] = useState(false);
  const [changingMode, setChangingMode] = useState(false);
  const menu = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  if (job.record_error) return <ActionButton onClick={() => action(job, "remove")}>Remove</ActionButton>;
  if (job.unsupported_reason) return <ActionButton onClick={() => action(job, "cancel")}>Remove</ActionButton>;
  if (job.state === "downloading") return <ActionButton onClick={() => action(job, "cancel")}>Cancel download</ActionButton>;
  return (
    <div className="job-menu" ref={menu}>
      <ActionButton
        aria-label={`Actions for ${filename(job.input)}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        ⋯
      </ActionButton>
      {open && (
        <div className="row-menu">
          {!["done", "failed", "cancelled"].includes(job.state) && (
            <>
              <ActionButton onClick={() => action(job, "move", { position: 1 })}>
                Move to top
              </ActionButton>
              <ActionButton
                disabled={position < 2}
                onClick={() => action(job, "move", { position: position - 1 })}
              >
                Move up
              </ActionButton>
              <ActionButton
                onClick={() => action(job, "move", { position: position + 1 })}
              >
                Move down
              </ActionButton>
              <ActionButton
                onClick={() =>
                  action(job, job.state === "paused" ? "resume" : "pause")
                }
              >
                {job.state === "paused" ? "Resume" : "Pause"}
              </ActionButton>
              <ActionButton onClick={() => action(job, "cancel")}>Cancel</ActionButton>
              {!job.started_at &&
                job.segment === 0 &&
                job.state !== "running" && (
                  <>
                    <ActionButton disabled={job.state === "preparing"} onClick={() => action(job, "remove-unstarted")}>
                      Remove from queue
                    </ActionButton>
                    <ActionButton
                      disabled={job.state === "preparing"}
                      title={
                        job.state === "preparing"
                          ? "Wait for preparation"
                          : undefined
                      }
                      onClick={() => setChangingMode(!changingMode)}
                    >
                      Change mode
                    </ActionButton>
                    {changingMode &&
                      ["standard", "fast"].map((preset) => (
                        <ActionButton
                          key={preset}
                          aria-pressed={job.settings.preset === preset}
                          onClick={() => {
                            action(job, "mode", { preset });
                            setChangingMode(false);
                            setOpen(false);
                          }}
                        >
                          {preset === "standard" ? "Standard" : "Fast"}
                        </ActionButton>
                      ))}
                  </>
                )}
            </>
          )}
          <ActionButton
            disabled={job.original_state === "missing" || job.original_state === "recycled"}
            title={job.original_state === "missing" || job.original_state === "recycled" ? "Compare again needs the original video." : undefined}
            onClick={() => {
              trial(job);
              setOpen(false);
            }}
          >
            {["done", "failed", "cancelled"].includes(job.state)
              ? "Compare again"
              : "Try models on this video"}
          </ActionButton>
          <ActionButton onClick={() => action(job, "folder")}>
            Open output folder
          </ActionButton>
          <ActionButton onClick={() => action(job, "log")}>Show log</ActionButton>
          <ActionButton onClick={() => action(job, "copy")}>Copy details</ActionButton>
          {["done", "failed", "cancelled"].includes(job.state) && (
            <ActionButton onClick={() => action(job, "remove")}>
              Remove from history
            </ActionButton>
          )}
        </div>
      )}
    </div>
  );
}

export function HomePage({
  queue,
  health,
  plan,
  api,
  reconnecting,
  add,
  action,
  trial,
  preview,
  pauseAll,
  navigate,
  seenFailures = [],
  seen,
}: Actions & {
  queue: Queue;
  health?: Health;
  plan?: Plan;
  api?: Api;
  reconnecting: boolean;
  add(files?: string[]): void;
  preview(job: Job): void;
  pauseAll(): void;
  navigate(page: string): void;
  seenFailures?: string[];
  seen?(ids: string[]): void;
}) {
  const [problem, setProblem] = useState(false);
  const pointerJob = useRef<string | null>(null);
  const active = queue.jobs.filter(
    (j) => !["done", "failed", "cancelled"].includes(j.state),
  );
  const current =
    active.find((j) => !j.unsupported_reason && j.state === "running") ||
    active.find((j) => !j.unsupported_reason && ["queued", "paused"].includes(j.state)) ||
    active.find((j) => !j.unsupported_reason);
  const next = active.filter((j) => j !== current);
  const failures = queue.jobs.filter(
    (j) => j.state === "failed" && !seenFailures.includes(j.id),
  );
  const recent = queue.jobs
    .filter((j) => j.state === "done")
    .sort((a, b) =>
      (b.finished_at || b.eta || "").localeCompare(
        a.finished_at || a.eta || "",
      ),
    )
    .slice(0, 3);
  const chip = reconnecting
    ? "Reconnecting…"
    : health?.last_error
      ? `Problem · ${problemWhen(health.last_error.time)}`
      : health?.engine_state === "Paused"
        ? "Paused"
        : current?.step === "Paused for a preview"
          ? "Paused for a preview"
          : current?.phase === "finalizing"
            ? `Finishing ${filename(current.input)}`
            : current?.state === "running"
              ? `Working · ${current.fps?.toFixed(1) || "—"} fps${health?.next_change ? ` · pauses at ${when(health.next_change)}` : ""}`
              : current?.state === "preparing"
                ? "Preparing…"
                : current?.state === "downloading" ? "Downloading"
                : current
                  ? `Waiting for your hours${health?.next_change ? ` · starts ${when(health.next_change)}` : ""}`
                  : "Idle · nothing to do";
  return (
    <section aria-label="Home">
      <div className="page-heading">
        <div>
          <h1>Home</h1>
          <ActionButton
            className="status-chip"
            onClick={() => {
              if (health?.last_error) setProblem(true);
            }}
            title={health?.last_error?.message}
          >
            <span
              className={health?.last_error ? "warning-dot" : "status-dot"}
            />
            {chip}
          </ActionButton>
        </div>
        <div className="actions">
          <ActionButton onClick={pauseAll} disabled={!health?.paused_all && !active.some(job => !job.unsupported_reason && (job.state === "downloading" || job.state === "running" || (job.state === "queued" && health?.engine_state !== "Waiting for your hours")))} title="Pause jobs running or ready to run now">
            {health?.paused_all ? "Resume all" : "Pause all"}
          </ActionButton>
          <ActionButton className="primary" onClick={() => add()}>
            Add videos
          </ActionButton>
        </div>
      </div>
      {!!failures.length && (
        <div className="attention" role="status">
          {failures.length}{" "}
          {failures.length === 1 ? "video needs" : "videos need"} attention ·{" "}
          <ActionButton onClick={() => navigate("History")}>Open History</ActionButton>
          <ActionButton onClick={() => seen?.(failures.map((j) => j.id))}>
            Dismiss
          </ActionButton>
        </div>
      )}
      {problem && health?.last_error && (
        <div className="modal-shade">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Problem details"
            className="dialog"
          >
            <h2>Problem</h2>
            <p>{health.last_error.message}</p>
            <p>{when(health.last_error.time)}</p>
            <p>
              {queue.jobs.find((j) => j.id === health.last_error?.job_id)
                ?.input ||
                health.last_error.job_id ||
                "App"}
            </p>
            <div className="actions">
              <ActionButton
                onClick={() =>
                  window.desktop.copy(
                    JSON.stringify(health.last_error, null, 2),
                  )
                }
              >
                Copy details
              </ActionButton>
              <ActionButton onClick={() => setProblem(false)}>Close</ActionButton>
            </div>
          </div>
        </div>
      )}
      {health?.deletion_notices?.filter(notice => !queue.jobs.some(job => job.id === notice.job_id)).map(notice => <div className="alert" role="status" key={notice.id}><p>{notice.result}</p><p>{notice.guard}</p><ActionButton onClick={() => window.desktop.reveal(notice.guard)}>Show in folder</ActionButton></div>)}
      <div className="home-columns">
        <div>
          {current && (current.state === "downloading" || current.link_unanalysed) ? <DownloadCard job={current} cancel={() => action(current, "cancel")} /> : current ? (
            <article className="now-card">
              <Thumbnail job={current} api={api} />
              <div className="now-details">
                <p className="muted">
                  {health?.paused_all || current.state === "paused" ? "Paused" : current.state === "running"
                    ? "Now processing"
                    : current.state === "preparing"
                      ? "Preparing…"
                      : "Up next"}
                </p>
                <h2>{filename(current.input)}</h2>
                <p className="muted">
                  {current.media.display_width} × {current.media.display_height}{" "}
                  · {current.media.cfr_fps} fps ·{" "}
                  {duration(current.media.duration)} ·{" "}
                  {current.settings.preset === "standard" ? "Standard" : "Fast"}
                </p>
                <div className="now-percent">
                  {current.progress_percent.toFixed(0)}%{" "}
                  <span>
                    Segment {current.segment} of {current.segments}
                  </span>
                </div>
                <progress
                  aria-label="Current video progress"
                  max="100"
                  value={current.progress_percent}
                />
                {current.phase === "finalizing" && (
                  <p>
                    Finishing:{" "}
                    {current.step === "validating" ? "checking the file" : current.step}
                  </p>
                )}
                <div className="finish-row">
                  {(health?.paused_all || current.state === "paused") && <p>Paused. Finished parts are kept; the current part restarts (about {duration(current.part_seconds || 0)} of work).</p>}
                  <strong>
                    {current.state === "queued"
                      ? `Starts ${when(current.starts)}`
                      : current.estimate.unknown_models?.length ? "Speed unknown" : `Finishes ${when(current.eta)}`}
                  </strong>
                  <span>
                    Work left
                    <br />
                    {current.estimate.unknown_models?.length ? "Speed unknown" : duration(current.estimate.seconds)}
                  </span>
                </div>
                {!!current.overrun_seconds && (
                  <p>
                    Finishing one step after your hours, about{" "}
                    {Math.ceil(current.overrun_seconds / 60)} min
                  </p>
                )}
                <div className="actions">
                  <ActionButton
                    title="Pause this video. The next one starts instead."
                    onClick={() =>
                      action(
                        current,
                        current.state === "paused" ? "resume" : "pause",
                      )
                    }
                  >
                    {current.state === "paused" ? "Resume" : "Pause"}
                  </ActionButton>
                  <ActionButton
                    disabled={!current.preview_ready}
                    onClick={() => preview(current)}
                  >
                    Preview result
                  </ActionButton>
                  <JobMenu
                    job={current}
                    action={action}
                    trial={trial}
                    position={current.position || 1}
                  />
                </div>
              </div>
            </article>
          ) : (
            <div className="empty">
              <h2>Nothing in the queue.</h2>
              <p>Add a video to see when it will be ready.</p>
              <ActionButton onClick={() => add()}>
                Add your first video
              </ActionButton>
            </div>
          )}
          {!!next.length && (
            <>
              <div className="section-heading">
                <h2>Up next</h2>
                <span>
                  {next.length} videos · all done {when(queue.completion)}
                </span>
              </div>
              <div className="next-list">
                {next.map((job) => (
                  <article
                    key={job.id}
                    className="next-row"
                    data-job-id={job.id}
                    onPointerDown={e => {
                      if (e.button !== 0 || (e.target as Element).closest("button,input,select,a")) return;
                      pointerJob.current = job.id;
                      e.currentTarget.setPointerCapture(e.pointerId);
                    }}
                    onPointerCancel={() => { pointerJob.current = null; }}
                    onPointerUp={e => {
                      const moved = queue.jobs.find(j => j.id === pointerJob.current);
                      pointerJob.current = null;
                      if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
                      const targetId = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>(".next-row")?.dataset.jobId;
                      const target = queue.jobs.find(j => j.id === targetId);
                      if (moved && target && moved.id !== target.id) action(moved, "move", { position: target.position || 1 });
                    }}
                    onKeyDown={(e) => {
                      if (
                        e.altKey &&
                        ["ArrowUp", "ArrowDown"].includes(e.key)
                      ) {
                        e.preventDefault();
                        const n =
                          (job.position || 1) +
                          (e.key === "ArrowUp" ? -1 : 1);
                        if (n >= 1 && n <= queue.jobs.length)
                          action(job, "move", { position: n });
                      }
                    }}
                    tabIndex={0}
                  >
                    <GripVertical size={16} aria-hidden="true" />
                    <Thumbnail job={job} api={api} small />
                    <div className="next-name">
                      <h2>{filename(job.input)}</h2>
                      <p>
                        {duration(job.media.duration)} ·{" "}
                        {job.settings.preset === "standard"
                          ? "Standard"
                          : "Fast"}
                      </p>
                    </div>
                    <div>
                      {(job.state === "downloading" || job.link_unanalysed) ? <><p>{job.download?.phase} · {job.download?.percent == null ? "" : `${job.download.percent.toFixed(0)}%`}</p><progress aria-label="Download progress" max="100" value={job.download?.percent ?? undefined} /><p>Processing: {job.estimate_after_download ? "after download" : duration(job.estimate.seconds)}</p></> : job.unsupported_reason ? `No longer supported: ${job.unsupported_reason}` : job.cancel_cleanup ? ("Cancelling…") : job.state === "preparing" ? (
                        "Preparing…"
                      ) : job.state === "paused" ? (
                        "Waits until you resume it"
                      ) : job.estimate.unknown_models?.length ? (
                        "Speed unknown"
                      ) : (
                        <>
                          Starts {when(job.starts)}
                          <br />
                          Done {when(job.eta)}
                        </>
                      )}
                    </div>
                    <JobMenu
                      job={job}
                      action={action}
                      trial={trial}
                      position={job.position || 1}
                    />
                  </article>
                ))}
              </div>
            </>
          )}
          <ActionButton className="drop-zone" onClick={() => add()}>
            + Drop videos anywhere in this window, or click to add
          </ActionButton>
        </div>
        <div className="home-sidebar">
          <article className="card">
            <div className="section-heading">
              <h2>Your hours this week</h2>
              <ActionButton onClick={() => navigate("Schedule")}>Edit hours</ActionButton>
            </div>
            {plan?.days.slice(0, 5).map((day) => (
              <div className="week-row" key={day.date}>
                <span>
                  {new Date(`${day.date}T12:00:00`).toLocaleDateString(
                    "en-US",
                    { weekday: "short" },
                  )}
                </span>
                <progress max="24" value={day.run_hours} />
                <span>
                  {day.run_hours
                    ? `${day.run_hours.toFixed(1)} h`
                    : day.windows.length
                      ? "free"
                      : "off"}
                </span>
              </div>
            ))}
            <p>Everything finishes {when(queue.completion)}</p>
          </article>
          <article className="card">
            <div className="section-heading">
              <h2>Recently finished</h2>
              <ActionButton onClick={() => navigate("History")}>All history</ActionButton>
            </div>
            {recent.map((job) => (
              <div className="recent-row" key={job.id}>
                <Thumbnail job={job} api={api} small />
                <span>{filename(job.input)}</span>
                <ActionButton onClick={() => action(job, "play")}>Open</ActionButton>
              </div>
            ))}
          </article>
        </div>
      </div>
    </section>
  );
}

function historyAspect(job: Job) {
  const width = job.media.display_width, height = job.media.display_height;
  return width > 0 && height > 0 && Number.isFinite(width / height) ? width / height : 16 / 9;
}

export function HistoryPage({
  queue,
  api,
  action,
  trial,
  seen,
}: Actions & { queue: Queue; api?: Api; seen?(ids: string[]): void }) {
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState<string[]>([]);
  const [selectMode, setSelectMode] = useState(false);
  const [galleryWidth, setGalleryWidth] = useState(1000);
  const [detail, setDetail] = useState<string>();
  const viewport = useRef<HTMLDivElement>(null);
  const [scroll, setScroll] = useState(0);
  const [columns, setColumns] = useState(3);
  useEffect(() => {
    if (!viewport.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(entries => { setGalleryWidth(entries[0].contentRect.width); setColumns(Math.max(1, Math.floor((entries[0].contentRect.width + 16) / 256))); });
    observer.observe(viewport.current);
    return () => observer.disconnect();
  }, []);
  const terminal = useMemo(() => queue.jobs
    .filter((j) => ["done", "failed", "cancelled"].includes(j.state))
    .sort((a, b) =>
      (b.finished_at || b.eta || "").localeCompare(
        a.finished_at || a.eta || "",
      ),
    ), [queue.history_revision || queue.jobs]);
  const matches = (job: Job, name: string) =>
    name === "All" ||
    (name === "Needs attention"
      ? job.state === "failed"
      : job.settings.preset === name.toLowerCase());
  const visible = useMemo(() => terminal.filter(
    (j) =>
      matches(j, filter) &&
      filename(j.input).toLowerCase().includes(search.toLowerCase()),
  ), [terminal, filter, search]);
  const visibleIds = visible.map((j) => j.id).join(",");
  const calendarDay = new Date().toDateString();
  const groups = useMemo(() => {
    const groups = new Map<string, Job[]>();
  const now = new Date(), yesterday = new Date(now);
  const monthYear = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" });
  yesterday.setDate(yesterday.getDate() - 1);
  const todayLabel = now.toDateString(), yesterdayLabel = yesterday.toDateString();
  for (const job of visible) {
    const date = new Date(job.finished_at || job.eta || 0);
    const label = date.toDateString() === todayLabel ? "Today"
      : date.toDateString() === yesterdayLabel ? "Yesterday"
      : now.getTime() - date.getTime() < 7 * 86400000 ? "Last 7 days"
      : `Earlier in ${monthYear.format(date)}`;
    const group = groups.get(label);
    if (group) group.push(job);
    else groups.set(label, [job]);
  }
    return groups;
  }, [visible, calendarDay]);
  const rows: { label?: string; jobs: Job[]; top: number; height: number }[] = [];
  let height = 0;
  for (const [label, jobs] of groups) {
    rows.push({ label, jobs: [], top: height, height: 32 }); height += 32;
    let pending: Job[] = [], aspectSum = 0;
    const flush = () => {
      if (!pending.length) return;
      const rowHeight = Math.min(200, (galleryWidth - (pending.length - 1) * 12) / aspectSum);
      rows.push({ jobs: pending, top: height, height: rowHeight + 12 });
      height += rowHeight + 12; pending = []; aspectSum = 0;
    };
    for (const job of jobs) {
      const aspect = historyAspect(job);
      pending.push(job); aspectSum += aspect;
      if (aspectSum * 200 + (pending.length - 1) * 12 >= galleryWidth) flush();
    }
    flush();
  }
  const windowRows = rows.filter(row => row.top + row.height >= scroll - 300 && row.top < scroll + (viewport.current?.clientHeight || 450) + 300);
  useEffect(() => {
    if (!seen) return;
    const cards = document.querySelectorAll<HTMLElement>(
      '[aria-label="History"] .history-card[data-failed="true"]',
    );
    if (typeof IntersectionObserver === "undefined") {
      seen(Array.from(cards, (c) => c.dataset.jobId!));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) =>
        seen(
          entries
            .filter((e) => e.isIntersecting)
            .map((e) => (e.target as HTMLElement).dataset.jobId!),
        ),
      { threshold: 0.1 },
    );
    cards.forEach((card) => observer.observe(card));
    return () => observer.disconnect();
  }, [visibleIds, seen, scroll, columns]);
  return (
    <section aria-label="History">
      <div className="page-heading">
        <h1>History</h1>
        <input
          aria-label="Search by file name"
          placeholder="Search by file name"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {!selectMode && <ActionButton className="small history-select-button" onClick={() => setSelectMode(true)}>Select</ActionButton>}
      </div>
      {selectMode && <div className="toolbar">
        <span>{selected.length} selected</span>
        <ActionButton onClick={() => setSelected(visible.map(job => job.id))}>Select all</ActionButton>
        <ActionButton disabled={!selected.length} onClick={() => action(terminal.find(job => job.id === selected[0])!, "remove", { ids: selected })}>Remove from history</ActionButton>
        <ActionButton disabled={!selected.length} onClick={() => action(terminal.find(job => job.id === selected[0])!, "delete-files", { ids: selected })}>Delete video files…</ActionButton>
        <ActionButton onClick={() => { setSelected([]); setSelectMode(false); }}>Cancel</ActionButton>
      </div>}
      <div className="filters">
        {["All", "Standard", "Fast", "Needs attention"].map((name) => (
          <ActionButton
            key={name}
            aria-pressed={filter === name}
            onClick={() => setFilter(name)}
          >
            {name} ({terminal.filter((j) => matches(j, name)).length})
          </ActionButton>
        ))}
      </div>
      <div className="history-viewport" ref={viewport} onScroll={event => setScroll(event.currentTarget.scrollTop)}>
        {!visible.length && <p className="empty">{terminal.length ? "No videos match your search." : "No history yet."}</p>}
        <div style={{ height, position: "relative" }}>
        {windowRows.map(row => row.label ? <h2 key={row.top} className="history-group" style={{ top: row.top }}>{row.label}</h2> : <div key={row.top} className="history-grid virtual-row" style={{ top: row.top, height: row.height - 12, display: "flex", gap: 12 }}>{row.jobs.map((job) => (
            <article
              className="card history-card"
              key={job.id}
              data-job-id={job.id}
              data-failed={job.state === "failed"}
            >
              <button className="history-image" aria-label={selectMode ? `Select ${filename(job.input)}` : filename(job.input)}
                style={{ width: (row.height - 12) * historyAspect(job), height: row.height - 12 }}
                onClick={() => selectMode ? setSelected(old => old.includes(job.id) ? old.filter(id => id !== job.id) : [...old, job.id]) : setDetail(job.id)}>
                <Thumbnail job={job} api={api} small />
                {selectMode && <span className="history-select" aria-hidden="true">{selected.includes(job.id) && <Check size={16} strokeWidth={1.8} />}</span>}
                <span className="history-scrim"><span className="history-filename" title={filename(job.input)}>{filename(job.input)}</span>
                  {historyWarning(job) && <span className="badge warning" role="img"
                    aria-label={historyWarning(job)} title={historyWarning(job)}>⚠</span>}
                </span>
              </button>
            </article>
          ))}</div>)}
        </div>
      </div>
      {detail && queue.jobs.find(job => job.id === detail) && <HistoryDetail job={queue.jobs.find(job => job.id === detail)!} api={api} action={action} compare={trial} close={() => setDetail(undefined)} />}
      <p className="muted">
        Finished and failed jobs move here automatically. Removing an item from
        History keeps files unless you explicitly choose to move them to the Recycle Bin.
      </p>
    </section>
  );
}

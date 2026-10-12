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
    if (api)
      void api
        .blob(`queue/${job.id}/thumbnail`)
        .then((blob) => {
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
  return (
    <div className="job-menu" ref={menu}>
      <button
        aria-label={`Actions for ${filename(job.input)}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        ⋯
      </button>
      {open && (
        <div className="row-menu">
          {!["done", "failed", "cancelled"].includes(job.state) && (
            <>
              <button onClick={() => action(job, "move", { position: 1 })}>
                Move to top
              </button>
              <button
                disabled={position < 2}
                onClick={() => action(job, "move", { position: position - 1 })}
              >
                Move up
              </button>
              <button
                onClick={() => action(job, "move", { position: position + 1 })}
              >
                Move down
              </button>
              <button
                onClick={() =>
                  action(job, job.state === "paused" ? "resume" : "pause")
                }
              >
                {job.state === "paused" ? "Resume" : "Pause"}
              </button>
              <button onClick={() => action(job, "cancel")}>Cancel</button>
              {!job.started_at &&
                job.segment === 0 &&
                job.state !== "running" && (
                  <>
                    <button disabled={job.state === "preparing"} onClick={() => action(job, "remove-unstarted")}>
                      Remove from queue
                    </button>
                    <button
                      disabled={job.state === "preparing"}
                      title={
                        job.state === "preparing"
                          ? "Wait for preparation"
                          : undefined
                      }
                      onClick={() => setChangingMode(!changingMode)}
                    >
                      Change mode
                    </button>
                    {changingMode &&
                      ["standard", "fast"].map((preset) => (
                        <button
                          key={preset}
                          aria-pressed={job.settings.preset === preset}
                          onClick={() => {
                            action(job, "mode", { preset });
                            setChangingMode(false);
                            setOpen(false);
                          }}
                        >
                          {preset === "standard" ? "Standard" : "Fast"}
                        </button>
                      ))}
                  </>
                )}
            </>
          )}
          <button
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
          </button>
          <button onClick={() => action(job, "folder")}>
            Open output folder
          </button>
          <button onClick={() => action(job, "log")}>Show log</button>
          <button onClick={() => action(job, "copy")}>Copy details</button>
          {["done", "failed", "cancelled"].includes(job.state) && (
            <button onClick={() => action(job, "remove")}>
              Remove from history
            </button>
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
  const active = queue.jobs.filter(
    (j) => !["done", "failed", "cancelled"].includes(j.state),
  );
  const current =
    active.find((j) => j.state === "running") ||
    active.find((j) => j.state === "queued") ||
    active[0];
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
                : current
                  ? `Waiting for your hours${health?.next_change ? ` · starts ${when(health.next_change)}` : ""}`
                  : "Idle · nothing to do";
  return (
    <section aria-label="Home">
      <div className="page-heading">
        <div>
          <h1>Home</h1>
          <button
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
          </button>
        </div>
        <div className="actions">
          <button onClick={pauseAll}>
            {health?.paused_all ? "Resume all" : "Pause all"}
          </button>
          <button className="primary" onClick={() => add()}>
            + Add videos
          </button>
        </div>
      </div>
      {!!failures.length && (
        <div className="attention" role="status">
          {failures.length}{" "}
          {failures.length === 1 ? "video needs" : "videos need"} attention ·{" "}
          <button onClick={() => navigate("History")}>Open History</button>
          <button onClick={() => seen?.(failures.map((j) => j.id))}>
            Dismiss
          </button>
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
              <button
                onClick={() =>
                  window.desktop.copy(
                    JSON.stringify(health.last_error, null, 2),
                  )
                }
              >
                Copy details
              </button>
              <button onClick={() => setProblem(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
      {health?.deletion_notices?.filter(notice => !queue.jobs.some(job => job.id === notice.job_id)).map(notice => <div className="alert" role="status" key={notice.id}><p>{notice.result}</p><p>{notice.guard}</p><button onClick={() => window.desktop.reveal(notice.guard)}>Show in folder</button></div>)}
      <div className="home-columns">
        <div>
          {current ? (
            <article className="now-card">
              <Thumbnail job={current} api={api} />
              <div className="now-details">
                <p className="muted">
                  {current.state === "running"
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
                  <button
                    title="Pause this video. The next one starts instead."
                    onClick={() =>
                      action(
                        current,
                        current.state === "paused" ? "resume" : "pause",
                      )
                    }
                  >
                    {current.state === "paused" ? "Resume" : "Pause"}
                  </button>
                  <button
                    disabled={!current.preview_ready}
                    onClick={() => preview(current)}
                  >
                    Preview result
                  </button>
                  <JobMenu
                    job={current}
                    action={action}
                    trial={trial}
                    position={queue.jobs.indexOf(current) + 1}
                  />
                </div>
              </div>
            </article>
          ) : (
            <div className="empty">
              <h2>Nothing in the queue.</h2>
              <p>Add a video to see when it will be ready.</p>
              <button className="primary" onClick={() => add()}>
                Add videos
              </button>
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
                    draggable
                    onDragStart={(e) =>
                      e.dataTransfer.setData("text/plain", job.id)
                    }
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const moved = queue.jobs.find(
                        (j) => j.id === e.dataTransfer.getData("text/plain"),
                      );
                      if (moved)
                        action(moved, "move", {
                          position: queue.jobs.indexOf(job) + 1,
                        });
                    }}
                    onKeyDown={(e) => {
                      if (
                        e.altKey &&
                        ["ArrowUp", "ArrowDown"].includes(e.key)
                      ) {
                        e.preventDefault();
                        const n =
                          queue.jobs.indexOf(job) +
                          (e.key === "ArrowUp" ? 0 : 2);
                        if (n >= 1 && n <= queue.jobs.length)
                          action(job, "move", { position: n });
                      }
                    }}
                    tabIndex={0}
                  >
                    <span aria-hidden="true">⋮⋮</span>
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
                      {job.cancel_cleanup ? ("Cancelling…") : job.state === "preparing" ? (
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
                      position={queue.jobs.indexOf(job) + 1}
                    />
                  </article>
                ))}
              </div>
            </>
          )}
          <button className="drop-zone" onClick={() => add()}>
            + Drop videos anywhere in this window, or click to add
          </button>
        </div>
        <div className="home-sidebar">
          <article className="card">
            <div className="section-heading">
              <h2>Your hours this week</h2>
              <button onClick={() => navigate("Schedule")}>Edit hours</button>
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
              <button onClick={() => navigate("History")}>All history</button>
            </div>
            {recent.map((job) => (
              <div className="recent-row" key={job.id}>
                <Thumbnail job={job} api={api} small />
                <span>{filename(job.input)}</span>
                <button onClick={() => action(job, "play")}>Open</button>
              </div>
            ))}
          </article>
        </div>
      </div>
    </section>
  );
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
  const [clear, setClear] = useState(false);
  const [detail, setDetail] = useState<string>();
  const viewport = useRef<HTMLDivElement>(null);
  const [scroll, setScroll] = useState(0);
  const [columns, setColumns] = useState(3);
  useEffect(() => {
    if (!viewport.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(entries => setColumns(Math.max(1, Math.floor((entries[0].contentRect.width + 16) / 256))));
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
    for (let index = 0; index < jobs.length; index += columns) {
      rows.push({ jobs: jobs.slice(index, index + columns), top: height, height: 300 }); height += 300;
    }
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
        <button disabled={!terminal.length} onClick={() => setClear(true)}>Clear history…</button>
        <input
          aria-label="Search by file name"
          placeholder="Search by file name"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {!!selected.length && <div className="toolbar">
        <span>{selected.length} selected</span>
        <button onClick={() => setSelected(visible.map(job => job.id))}>Select all</button>
        <button onClick={() => { action(terminal.find(job => job.id === selected[0])!, "remove", { ids: selected }); setSelected([]); }}>Remove from history</button>
        <button onClick={() => setSelected([])}>Done</button>
      </div>}
      <div className="filters">
        {["All", "Standard", "Fast", "Needs attention"].map((name) => (
          <button
            key={name}
            aria-pressed={filter === name}
            onClick={() => setFilter(name)}
          >
            {name} ({terminal.filter((j) => matches(j, name)).length})
          </button>
        ))}
      </div>
      <div className="history-viewport" ref={viewport} onScroll={event => setScroll(event.currentTarget.scrollTop)}>
        {!visible.length && <p className="empty">{terminal.length ? "No videos match your search." : "No history yet."}</p>}
        <div style={{ height, position: "relative" }}>
        {windowRows.map(row => row.label ? <h2 key={row.top} className="history-group" style={{ top: row.top }}>{row.label}</h2> : <div key={row.top} className="history-grid virtual-row" style={{ top: row.top, gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>{row.jobs.map((job) => (
            <article
              className="card history-card"
              key={job.id}
              data-job-id={job.id}
              data-failed={job.state === "failed"}
            >
              <label className="check history-select"><input type="checkbox" aria-label={`Select ${filename(job.input)}`} checked={selected.includes(job.id)} onChange={event => setSelected(old => event.target.checked ? [...old, job.id] : old.filter(id => id !== job.id))} /></label>
              <Thumbnail job={job} api={api} small />
              <h2 title={filename(job.input)}><button className="history-name" onClick={() => setDetail(job.id)}>{filename(job.input)}</button></h2>
              <p>{historyWhen(job.finished_at || job.eta)}</p>
              <p>
                {job.settings.preset === "standard" ? "Standard" : "Fast"}
                {job.took_seconds !== undefined
                  ? ` · took ${duration(job.took_seconds)}`
                  : ""}
                {job.output_bytes !== undefined
                  ? ` · ${(job.output_bytes / 1_000_000).toFixed(0)} MB`
                  : ""}
              </p>
              <p
                className={
                  job.state === "done"
                    ? "success"
                    : job.state === "failed"
                      ? "warning-text"
                      : "muted"
                }
              >
                {job.state === "done"
                  ? "Finished"
                  : job.state === "failed"
                    ? job.error?.startsWith("Needs attention:")
                      ? job.error
                      : `Needs attention: ${job.error || "processing could not finish"}`
                    : job.cancel_cleanup ? "Cancelling…" : "Cancelled"}
              </p>
              {(job.output_state === "missing" || job.output_state === "recycled") && <p className="muted">Output: {job.output_state === "recycled" ? "Moved to the Recycle Bin" : "File not found"}</p>}
              {(job.original_state === "missing" || job.original_state === "recycled") && <p className="muted">Original: {job.original_state === "recycled" ? "Moved to the Recycle Bin" : "File not found"}</p>}
              {job.original_delete_result?.startsWith("Original kept:") && <p title={job.original_delete_result}>{job.original_delete_result}</p>}
              <div className="actions">
                {job.state === "done" ? (
                  <>
                    <button onClick={() => action(job, "play")}>Play</button>
                    <button onClick={() => action(job, "folder")}>
                      Show in folder
                    </button>
                  </>
                ) : job.state === "failed" ? (
                  <>
                    <button onClick={() => action(job, "retry")}>Retry</button>
                    <button onClick={() => action(job, "copy")}>
                      Copy details
                    </button>
                  </>
                ) : null}
                <JobMenu job={job} action={action} trial={trial} />
              </div>
            </article>
          ))}</div>)}
        </div>
      </div>
      {clear && <div className="modal-shade"><div className="dialog" role="dialog" aria-modal="true">
        <h2>Clear history?</h2><p>Remove all finished, failed and cancelled records. Your video files stay as they are. This cannot be undone.</p>
        <div className="dialog-actions"><button onClick={() => setClear(false)}>Keep history</button><button className="danger" onClick={() => { action(terminal[0], "clear-history"); setClear(false); }}>Clear history</button></div>
      </div></div>}
      {detail && queue.jobs.find(job => job.id === detail) && <HistoryDetail job={queue.jobs.find(job => job.id === detail)!} api={api} action={action} compare={trial} close={() => setDetail(undefined)} />}
      <p className="muted">
        Finished and failed jobs move here automatically. Removing an item from
        History never deletes the video file.
      </p>
    </section>
  );
}

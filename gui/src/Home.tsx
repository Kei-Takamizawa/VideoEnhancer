import { useEffect, useState } from "react";
import type { Api } from "./api";
import { duration, filename, when } from "./api";
import type { Health, Job, Plan, Queue } from "./types";

export function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    Home: "M3 10 12 3l9 7v11h-6v-7H9v7H3Z",
    History: "M3 12a9 9 0 1 0 3-7M3 3v6h6M12 7v5l3 2",
    Schedule: "M4 5h16v16H4ZM8 3v4M16 3v4M4 10h16",
    Models: "m12 3 9 5-9 5-9-5Zm-9 9 9 5 9-5m-18 5 9 5 9-5",
    Settings:
      "M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
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
  return (
    <div className="job-menu">
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
            </>
          )}
          <button
            onClick={() => {
              trial(job);
              setOpen(false);
            }}
          >
            Try models on this video
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
}) {
  const active = queue.jobs.filter(
    (j) => !["done", "failed", "cancelled"].includes(j.state),
  );
  const current =
    active.find((j) => j.state === "running") ||
    active.find((j) => j.state === "queued") ||
    active[0];
  const next = active.filter((j) => j !== current);
  const failures = queue.jobs.filter((j) => j.state === "failed");
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
      ? "Problem · details"
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
              if (health?.last_error)
                void window.desktop.copy(
                  JSON.stringify(health.last_error, null, 2),
                );
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
            {health?.engine_state === "Paused" ? "Resume all" : "Pause all"}
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
        </div>
      )}
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
                    {current.step === "validating" ? "checking" : current.step}
                  </p>
                )}
                <div className="finish-row">
                  <strong>
                    {current.state === "queued"
                      ? `Starts ${when(current.starts)}`
                      : `Finishes ${when(current.eta)}`}
                  </strong>
                  <span>
                    Work left
                    <br />
                    {duration(current.estimate.seconds)}
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
                      {job.state === "preparing" ? (
                        "Preparing…"
                      ) : job.state === "paused" ? (
                        "Paused"
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
              <h2>This week</h2>
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
}: Actions & { queue: Queue; api?: Api }) {
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("All");
  const terminal = queue.jobs
    .filter((j) => ["done", "failed", "cancelled"].includes(j.state))
    .sort((a, b) =>
      (b.finished_at || b.eta || "").localeCompare(
        a.finished_at || a.eta || "",
      ),
    );
  const matches = (job: Job, name: string) =>
    name === "All" ||
    (name === "Needs attention"
      ? job.state === "failed"
      : job.settings.preset === name.toLowerCase());
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
      </div>
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
      <div className="history-grid">
        {terminal
          .filter(
            (j) =>
              matches(j, filter) &&
              filename(j.input).toLowerCase().includes(search.toLowerCase()),
          )
          .map((job) => (
            <article className="card history-card" key={job.id}>
              <Thumbnail job={job} api={api} small />
              <h2>{filename(job.input)}</h2>
              <p>{when(job.finished_at || job.eta)}</p>
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
                    : "Cancelled"}
              </p>
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
          ))}
      </div>
      <p className="muted">
        Finished and failed jobs move here automatically. Removing an item from
        History never deletes the video file.
      </p>
    </section>
  );
}

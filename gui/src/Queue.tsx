import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { duration, filename, folder, when } from "./api";
import type { Job, Model, Queue, Settings, Estimate, Media } from "./types";

export function QueuePage({
  queue,
  add,
  action,
  trial,
}: {
  queue: Queue;
  add(files?: string[]): void;
  action(job: Job, name: string, data?: unknown): void;
  trial(job: Job): void;
}) {
  const [menu, setMenu] = useState<string>();
  const [drag, setDrag] = useState<string>();
  return (
    <section
      aria-label="Queue"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        if (e.dataTransfer.files.length)
          add(
            Array.from(e.dataTransfer.files).map((f) =>
              window.desktop.filePath(f),
            ),
          );
      }}
    >
      <div className="page-heading">
        <div>
          <h1>Queue</h1>
          <p>Restore your videos. Keep track of when they will finish.</p>
        </div>
        <button className="primary" onClick={() => add()}>
          + Add videos
        </button>
      </div>
      <div className="drop-zone">Drop videos here, or choose Add videos.</div>
      {!queue.jobs.length && (
        <div className="empty">
          Your queue is empty. Add a video to get started.
        </div>
      )}
      <div className="jobs">
        {queue.jobs.map((job, index) => (
          <article
            key={job.id}
            className="job"
            draggable
            onDragStart={(e) => {
              setDrag(job.id);
              e.dataTransfer.setData("text/plain", job.id);
            }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.stopPropagation();
              if (drag) {
                const moved = queue.jobs.find((j) => j.id === drag);
                if (moved) action(moved, "move", { position: index + 1 });
                setDrag(undefined);
              }
            }}
          >
            <div className="job-top">
              <span className="ordinal">{index + 1}</span>
              <div className="job-title">
                <h2>{filename(job.input)}</h2>
                <p>
                  {job.media.display_width} × {job.media.display_height} ·{" "}
                  {job.media.cfr_fps} fps · {duration(job.media.duration)}
                </p>
              </div>
              <span className="badge">
                {job.settings.preset === "standard" ? "Standard" : "Fast"}
              </span>
              <strong className="state">
                {job.phase === "finalizing" && job.state !== "done"
                  ? `Finalizing: ${job.step}`
                  : job.state === "queued"
                    ? "Waiting"
                    : job.state === "preparing"
                      ? "Preparing…"
                      : job.state.charAt(0).toUpperCase() + job.state.slice(1)}
              </strong>
              <button
                aria-label={`Actions for ${filename(job.input)}`}
                onClick={() => setMenu(menu === job.id ? undefined : job.id)}
              >
                •••
              </button>
            </div>
            <div className="progress-line">
              <progress max="100" value={job.progress_percent} />
              <strong>{job.progress_percent.toFixed(1)}%</strong>
            </div>
            <div className="job-bottom">
              <div>
                <strong>
                  {job.state === "done" ? "Finished" : "Finish"}:{" "}
                  {when(job.eta)}
                </strong>
                <p>
                  {duration(job.estimate.seconds)} GPU ·{" "}
                  {duration(job.estimate.low)}–{duration(job.estimate.high)}
                  {!job.estimate.calibrated && (
                    <span className="badge warning">uncalibrated</span>
                  )}
                </p>
              </div>
              <span>
                Segment {job.segment}/{job.segments}
                {job.phase === "finalizing" &&
                  job.state !== "done" &&
                  ` · ${job.step_percent.toFixed(0)}% of step`}
              </span>
              <button
                disabled={["done", "cancelled"].includes(job.state)}
                onClick={() =>
                  action(
                    job,
                    job.state === "paused" || job.state === "failed"
                      ? "resume"
                      : "pause",
                  )
                }
              >
                {job.state === "paused" || job.state === "failed"
                  ? "Resume"
                  : "Pause"}
              </button>
            </div>
            {job.error && (
              <div className="error" role="alert">
                <strong>
                  {filename(job.input)} — segment {job.segment}
                </strong>
                <p>{job.error}</p>
                <p>
                  Review the details, correct the reported problem, then Resume.
                </p>
                <button onClick={() => action(job, "copy")}>
                  Copy details
                </button>
              </div>
            )}
            {menu === job.id && (
              <div className="row-menu">
                {[
                  "Move to top",
                  "Move up",
                  "Move down",
                  "Pause",
                  "Resume",
                  "Cancel",
                  "Remove",
                  "Open output folder",
                  "Show log",
                  "Copy details",
                  "Trial",
                ].map((label) => (
                  <button
                    key={label}
                    disabled={
                      (["Pause", "Resume", "Cancel"].includes(label) &&
                        ["done", "cancelled"].includes(job.state)) ||
                      (label === "Remove" &&
                        !["done", "cancelled", "failed"].includes(job.state)) ||
                      (label === "Move up" && index === 0) ||
                      (label === "Move down" && index === queue.jobs.length - 1)
                    }
                    onClick={() => {
                      setMenu(undefined);
                      if (label === "Trial") trial(job);
                      else if (label.startsWith("Move"))
                        action(job, "move", {
                          position:
                            label === "Move to top"
                              ? 1
                              : index + (label === "Move up" ? 0 : 2),
                        });
                      else
                        action(
                          job,
                          (
                            {
                              "Open output folder": "folder",
                              "Show log": "log",
                              "Copy details": "copy",
                            } as Record<string, string>
                          )[label] || label.toLowerCase(),
                        );
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
      <p className="summary">
        {queue.completion
          ? `All jobs ${queue.jobs.every((j) => ["done", "cancelled", "failed"].includes(j.state)) ? "finished" : "finish"} ${when(queue.completion)}`
          : queue.jobs.length
            ? "Paused or unscheduled jobs have no finish time."
            : "Your videos stay on your computer."}
      </p>
    </section>
  );
}

type Preview = {
  media: Media;
  presets: Record<string, Estimate>;
  warnings: string[];
  output: string;
};
export function AddDialog({
  api,
  files,
  defaults,
  models,
  av1 = false,
  close,
  saved,
  trial,
}: {
  api: Api;
  files: string[];
  defaults: Settings;
  models: Model[];
  av1?: boolean;
  close(): void;
  saved(): void;
  trial(file: string, settings: Settings, media?: Media): void;
}) {
  const [settings, setSettings] = useState({ ...defaults });
  const added = useRef(new Set<string>());
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    setLoading(true);
    const timer = setTimeout(
      () =>
        Promise.all(
          files.map(
            async (file) =>
              [
                file,
                await api.call<Preview>("estimate", "POST", {
                  file,
                  settings,
                  output_folder: settings.output_folder,
                }),
              ] as const,
          ),
        )
          .then((results) => {
            if (current) {
              setPreviews(Object.fromEntries(results));
              setError("");
              setLoading(false);
            }
          })
          .catch((e) => {
            if (current) {
              setError(e.message);
              setLoading(false);
            }
          }),
      200,
    );
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [api, files, settings]);
  const field = (key: keyof Settings, value: string | number) =>
    setSettings((old) => ({ ...old, [key]: value }));
  return (
    <div className="modal-shade">
      <div
        className="dialog wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-title"
      >
        <h2 id="add-title">
          Add {files.length === 1 ? "video" : `${files.length} videos`}
        </h2>
        <div className="form-grid">
          <label>
            Preset
            <select
              value={settings.preset}
              onChange={(e) => field("preset", e.target.value)}
            >
              <option value="standard">
                Standard — restore compression damage
              </option>
              <option value="fast">Fast — resize and smooth motion</option>
            </select>
          </label>
          <label>
            Output short side
            <select
              value={settings.short_side}
              onChange={(e) =>
                field(
                  "short_side",
                  e.target.value === "keep" ? "keep" : Number(e.target.value),
                )
              }
            >
              <option value="keep">Keep</option>
              {[1080, 1440, 2160].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label>
            Frame rate
            <select
              value={settings.fps}
              onChange={(e) => field("fps", e.target.value)}
            >
              <option value="off">Keep</option>
              <option value="2x">2×</option>
            </select>
          </label>
          <label>
            Codec
            <select
              value={settings.codec}
              onChange={(e) => field("codec", e.target.value)}
            >
              <option value="hevc">HEVC</option>
              <option value="h264">H.264</option>
              {av1 && <option value="av1">AV1</option>}
            </select>
          </label>
          <label className="span-two">
            Output folder
            <div className="input-button">
              <input
                placeholder="Source folder / enhanced"
                value={settings.output_folder}
                onChange={(e) => field("output_folder", e.target.value)}
              />
              <button
                onClick={async () => {
                  const selected = await window.desktop.files("folder");
                  if (selected[0]) field("output_folder", selected[0]);
                }}
              >
                Browse…
              </button>
            </div>
          </label>
        </div>
        <details>
          <summary>Advanced</summary>
          <label>
            Restoration model
            <select
              value={settings.restore_model || ""}
              onChange={(e) => field("restore_model", e.target.value)}
            >
              <option value="">Preset default</option>
              {models
                .filter((m) => m.task === "restore")
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.display_name}
                    {m.commercial_use_allowed ? "" : " (Non-commercial)"}
                  </option>
                ))}
            </select>
          </label>
        </details>
        <div className="estimate-list">
          {loading && <p role="status">Reading live estimates…</p>}
          {files.map((file) => (
            <div className="estimate-file" key={file}>
              <strong>{filename(file)}</strong>
              {previews[file] && (
                <>
                  <div className="preset-estimates">
                    {["standard", "fast"].map((preset) => {
                      const e = previews[file].presets[preset];
                      return (
                        <div key={preset}>
                          <strong>
                            {preset === "standard" ? "Standard" : "Fast"}
                          </strong>
                          <p>
                            {duration(e.seconds)} GPU ({duration(e.low)}–
                            {duration(e.high)})
                          </p>
                          <p>Finish: {when(e.finish)}</p>
                          {!e.calibrated && (
                            <span className="badge warning">uncalibrated</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {previews[file].warnings.map((w) => (
                    <p className="warning-text" key={w}>
                      {w}
                    </p>
                  ))}
                </>
              )}
            </div>
          ))}
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button disabled={busy} onClick={close}>
            Close
          </button>
          <button
            disabled={busy || !previews[files[0]]}
            onClick={() => trial(files[0], settings, previews[files[0]]?.media)}
          >
            Trial…
          </button>
          <button
            className="primary"
            disabled={
              busy ||
              loading ||
              !!error ||
              files.some((f) =>
                previews[f]?.warnings.some(
                  (w) =>
                    w.includes("HDR") ||
                    w.includes("Insufficient") ||
                    w.includes("Output too small"),
                ),
              )
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                for (const file of files) {
                  if (added.current.has(file)) continue;
                  await api.call("queue", "POST", {
                    file,
                    settings: {
                      ...settings,
                      restore_model: settings.restore_model || undefined,
                    },
                    output_folder: settings.output_folder,
                  });
                  added.current.add(file);
                }
                saved();
              } catch (e) {
                setError(
                  `${(e as Error).message} ${added.current.size ? `${added.current.size} video(s) already added; Retry will add only the remaining videos.` : ""}`,
                );
                setBusy(false);
              }
            }}
          >
            {busy ? "Analyzing and adding…" : "Add to queue"}
          </button>
        </div>
      </div>
    </div>
  );
}
export async function localAction(job: Job, name: string) {
  if (name === "copy") await window.desktop.copy(JSON.stringify(job, null, 2));
  if (name === "folder") await window.desktop.openFolder(folder(job.output));
}

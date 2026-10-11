import { useEffect, useState } from "react";
import type { Api } from "./api";
import { completion, filename, when } from "./api";
import type { Health, Job, Model, Operation, Plan, Settings } from "./types";

const colors = [
  "#78b9ff",
  "#d6a7ff",
  "#6cd8bd",
  "#ffbc75",
  "#ff9ec0",
  "#b7d779",
];
export function timelineHour(value: string, date: string, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(value));
  const part = (name: string) => parts.find((p) => p.type === name)!.value;
  const day = `${part("year")}-${part("month")}-${part("day")}`;
  return day < date
    ? 0
    : day > date
      ? 24
      : Number(part("hour")) + Number(part("minute")) / 60;
}
export function PlanPage({
  title = "Plan",
  plan,
  jobs,
  scenario,
  change,
  calibrate,
  operation,
}: {
  title?: string;
  plan?: Plan;
  jobs: Job[];
  scenario: string;
  change(value: string): void;
  calibrate(): void;
  operation?: Operation;
}) {
  const ids = jobs.map((j) => j.id);
  const color = (id: string) =>
    colors[Math.max(0, ids.indexOf(id)) % colors.length];
  return (
    <section>
      <div className="page-heading">
        <div>
          <h1>{title}</h1>
          <p>All jobs finish {when(completion(plan))}</p>
        </div>
        <label>
          Estimate
          <select value={scenario} onChange={(e) => change(e.target.value)}>
            <option value="best">Best</option>
            <option value="expected">Expected</option>
            <option value="worst">Worst</option>
          </select>
        </label>
      </div>
      {jobs.some((j) => !j.estimate.calibrated) && (
        <div className="preview-panel">
          <span className="badge warning">uncalibrated</span> Measure this
          computer for a more useful estimate.{" "}
          <button
            disabled={
              operation?.state === "waiting" || operation?.state === "running"
            }
            onClick={calibrate}
          >
            Calibrate
          </button>
        </div>
      )}
      {operation && <OperationStatus operation={operation} />}
      <div className="plan-table">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Operating windows</th>
              <th>Run time</th>
              <th>Job progress</th>
              <th>00:00 — 24:00</th>
            </tr>
          </thead>
          <tbody>
            {plan?.days
              .filter((day, i) => day.jobs.length || i < 7)
              .map((day) => {
                const hour = (value: string) =>
                  timelineHour(value, day.date, plan.timezone);
                const title = new Date(
                  `${day.date}T12:00:00`,
                ).toLocaleDateString("en-US", {
                  weekday: "short",
                  month: "2-digit",
                  day: "2-digit",
                });
                return (
                  <tr key={day.date}>
                    <th>{title}</th>
                    <td>
                      {day.windows
                        .map(
                          (w) =>
                            `${new Date(w.start).toLocaleTimeString("en-US", { timeZone: plan.timezone, hour: "2-digit", minute: "2-digit", hour12: false })}–${new Date(w.end).toLocaleTimeString("en-US", { timeZone: plan.timezone, hour: "2-digit", minute: "2-digit", hour12: false })}`,
                        )
                        .join(", ") || "Off"}
                    </td>
                    <td>{day.run_hours.toFixed(1)} h</td>
                    <td>
                      {day.jobs.map((j) => (
                        <p key={j.job_id}>
                          <span
                            className="job-dot"
                            style={{ backgroundColor: color(j.job_id) }}
                          />
                          {filename(
                            jobs.find((row) => row.id === j.job_id)?.input ||
                              j.job_id,
                          )}{" "}
                          {j.start_percent.toFixed(0)}% →{" "}
                          {j.end_percent.toFixed(0)}%
                          {j.completion &&
                            ` · done ~${new Date(j.completion).toLocaleTimeString("en-US", { timeZone: plan.timezone, hour: "2-digit", minute: "2-digit", hour12: false })}`}
                        </p>
                      ))}
                    </td>
                    <td>
                      <svg
                        className="timeline"
                        viewBox="0 0 240 24"
                        role="img"
                        aria-label={`${title}: ${day.run_hours.toFixed(1)} planned hours`}
                      >
                        <rect
                          x="0"
                          y="0"
                          width="240"
                          height="24"
                          fill="var(--surface)"
                        />
                        {day.windows.map((w, i) => (
                          <rect
                            key={i}
                            x={hour(w.start) * 10}
                            width={(hour(w.end) - hour(w.start)) * 10}
                            y="4"
                            height="16"
                            fill="var(--window)"
                          />
                        ))}
                        {plan?.timeline
                          .filter((t) => hour(t.end) > hour(t.start))
                          .map((t, i) => (
                            <rect
                              key={i}
                              x={hour(t.start) * 10}
                              width={Math.max(
                                1,
                                (hour(t.end) - hour(t.start)) * 10,
                              )}
                              y="7"
                              height="10"
                              fill={color(t.job_id)}
                            >
                              <title>
                                {t.overrun_seconds
                                  ? `Finishing one step after your hours, about ${Math.ceil(t.overrun_seconds / 60)} min`
                                  : `${filename(jobs.find((j) => j.id === t.job_id)?.input || t.job_id)} · ${when(t.end)}`}
                              </title>
                            </rect>
                          ))}
                        {[0, 6, 12, 18, 24].map((h) => (
                          <line
                            key={h}
                            x1={h * 10}
                            x2={h * 10}
                            y1="0"
                            y2="24"
                            stroke="var(--border)"
                          />
                        ))}
                      </svg>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
      {!jobs.length && (
        <p className="empty">Add a video to see your day-by-day plan.</p>
      )}
    </section>
  );
}

export function OperationStatus({
  operation,
  cancel,
}: {
  operation: Operation;
  cancel?(): void;
}) {
  return (
    <div
      className={operation.state === "failed" ? "error" : "operation"}
      role="status"
    >
      <strong>
        {operation.kind.charAt(0).toUpperCase() + operation.kind.slice(1)}:{" "}
        {operation.state}
      </strong>
      <p>{operation.error || operation.phase}</p>
      {operation.percent !== undefined && operation.state === "running" && (
        <progress
          aria-label="Operation progress"
          max="100"
          value={operation.percent}
        />
      )}
      {["waiting", "running"].includes(operation.state) && (
        <>
          <progress aria-label={`${operation.kind} in progress`} />
          {cancel && <button onClick={cancel}>Cancel</button>}
        </>
      )}
      {operation.result?.weights_verified && (
        <p>
          SHA-256 verified · {operation.result.bytes?.toLocaleString()} bytes
          <br />
          <code>{operation.result.sha256}</code>
        </p>
      )}
    </div>
  );
}

export function ModelsPage({
  api,
  models,
  refresh,
  operate,
  operations,
  settings,
  compare,
}: {
  api: Api;
  models: Model[];
  refresh(): void;
  operate(route: string, data?: unknown): void;
  operations: Operation[];
  settings?: Settings;
  compare?(): void;
}) {
  const [consent, setConsent] = useState<Model>();
  const [removal, setRemoval] = useState<Model>();
  const [error, setError] = useState("");
  const [category, setCategory] = useState("cleanup");
  const [menu, setMenu] = useState<string>();
  const [details, setDetails] = useState<Model>();
  const group = (model: Model) =>
    model.catalog?.category ||
    (model.task === "restore" ? "cleanup" : "motion");
  return (
    <section>
      <div className="page-heading">
        <div>
          <h1>Models</h1>
          <p>Choose verified models and review their licences.</p>
        </div>
        <button
          onClick={async () => {
            try {
              const folder = (await window.desktop.files("folder"))[0];
              if (folder) {
                await api.call("models", "POST", { folder });
                refresh();
                setError("");
              }
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Add my own model…
        </button>
        <button disabled={!compare} onClick={compare}>
          Compare on my video
        </button>
      </div>
      <p>
        <a
          href="https://github.com/Kei-Takamizawa/VideoEnhancer/blob/main/docs/ADDING_MODELS.md"
          target="_blank"
          rel="noreferrer"
        >
          How to add a compatible model
        </a>
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="filter-pills" aria-label="Model category">
        {[
          ["cleanup", "Cleanup"],
          ["motion", "Smoother motion"],
          ["size", "Bigger picture"],
        ].map(([key, label]) => (
          <button
            key={key}
            aria-pressed={category === key}
            onClick={() => {
              setCategory(key);
              setMenu(undefined);
            }}
          >
            {label} ·{" "}
            {key === "size" ? 1 : models.filter((m) => group(m) === key).length}
          </button>
        ))}
        <button disabled>Faces · coming later</button>
      </div>
      <div className="model-grid">
        {category === "size" && (
          <article className="card model-card">
            <h2>
              Standard resize <span className="badge">Default</span>
            </h2>
            <p className="muted">Non-learned resize</p>
            <p>Makes the picture bigger without AI. Never changes the look.</p>
            <dl className="model-facts">
              <div>
                <dt>Speed</dt>
                <dd>Not measured here</dd>
              </div>
              <div>
                <dt>Changes the look</dt>
                <dd>Very little</dd>
              </div>
              <div>
                <dt>Licence</dt>
                <dd>No model weights</dd>
              </div>
            </dl>
            <p>No download</p>
            <button disabled>Installed</button>
          </article>
        )}
        {models
          .filter((m) => group(m) === category)
          .map((m) => {
            const c = m.catalog;
            const key = m.task === "restore" ? "restore_model" : "interp_model";
            const defaultId =
              settings?.[key] ||
              (m.task === "restore"
                ? "basicvsrpp-ntire21-decompress"
                : "rife-4.25");
            const speed = c?.reference_speed;
            const label = speed
              ? speed.fps >= 30
                ? "Fast"
                : speed.fps >= 10
                  ? "Medium"
                  : speed.fps >= 2
                    ? "Slow"
                    : "Very slow"
              : "Not measured here";
            const operation = [...operations]
              .reverse()
              .find(
                (o) =>
                  o.request &&
                  "model_id" in o.request &&
                  o.request.model_id === m.id,
              );
            return (
              <article className="card model-card" key={m.id}>
                <div className="model-title">
                  <h2>{c?.title || m.display_name}</h2>
                  <button
                    aria-label={`Actions for ${c?.title || m.display_name}`}
                    aria-expanded={menu === m.id}
                    onClick={() => setMenu(menu === m.id ? undefined : m.id)}
                  >
                    ⋯
                  </button>
                </div>
                <p className="muted">
                  {m.display_name} · {m.architecture}
                </p>
                {defaultId === m.id && <span className="badge">Default</span>}
                <p>
                  {c?.description ||
                    "A model you added. Review its details before use."}
                </p>
                <dl className="model-facts">
                  <div>
                    <dt>Speed</dt>
                    <dd
                      title={
                        speed
                          ? `About ${(30 / speed.fps).toFixed(1)} h per hour of 30 fps video · ${speed.gpu}`
                          : "No qualifying measurement on this computer yet"
                      }
                    >
                      {label}
                    </dd>
                  </div>
                  <div>
                    <dt>Changes the look</dt>
                    <dd>
                      {c?.look_change.replaceAll("_", " ") || "Not specified"}
                    </dd>
                  </div>
                  <div>
                    <dt>Licence</dt>
                    <dd>{c?.licence_plain || m.licence}</dd>
                  </div>
                </dl>
                <p>
                  {m.size_bytes
                    ? `${(m.size_bytes / 1e6).toFixed(1)} MB`
                    : "Not downloaded"}{" "}
                  ·{" "}
                  {m.weights_verified
                    ? "SHA-256 verified"
                    : "Weights not verified"}
                </p>
                {m.weights_verified ? (
                  <button disabled>Installed</button>
                ) : m.builtin ? (
                  <button className="primary" onClick={() => setConsent(m)}>
                    Install
                  </button>
                ) : (
                  <button onClick={() => operate(`models/${m.id}/verify`)}>
                    Verify again
                  </button>
                )}
                {operation && <OperationStatus operation={operation} />}
                {menu === m.id && (
                  <div className="model-menu" role="menu">
                    <button
                      role="menuitem"
                      disabled={!m.weights_verified}
                      onClick={async () => {
                        try {
                          await api.call("settings", "PUT", { [key]: m.id });
                          refresh();
                          setMenu(undefined);
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      Make it my default
                    </button>
                    <button
                      role="menuitem"
                      onClick={() => {
                        operate(`models/${m.id}/verify`);
                        setMenu(undefined);
                      }}
                    >
                      Verify again
                    </button>
                    <button
                      role="menuitem"
                      onClick={() => {
                        setDetails(m);
                        setMenu(undefined);
                      }}
                    >
                      Details
                    </button>
                    <button
                      role="menuitem"
                      onClick={() => {
                        setRemoval(m);
                        setMenu(undefined);
                      }}
                    >
                      Remove…
                    </button>
                  </div>
                )}
              </article>
            );
          })}
      </div>
      {details && (
        <div className="modal-shade">
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Model details"
          >
            <h2>{details.catalog?.title || details.display_name}</h2>
            <p>Licence: {details.licence}</p>
            <p className="break">
              Source: {details.weights.url || "Added from a local folder"}
            </p>
            <p className="break">SHA-256: {details.weights.sha256}</p>
            <p>
              {details.catalog?.reference_speed
                ? `${details.catalog.reference_speed.fps.toFixed(2)} fps · peak ${details.catalog.reference_speed.peak_memory_gb.toFixed(2)} GB · ${details.catalog.reference_speed.gpu}`
                : "Speed and peak memory have not been measured for this catalog entry."}
            </p>
            <p>
              Invents detail:{" "}
              {details.catalog?.invents_detail || "Not specified"} · Flicker:{" "}
              {details.catalog?.flicker || "Not specified"}
            </p>
            <button onClick={() => setDetails(undefined)}>Close</button>
          </div>
        </div>
      )}
      {operations
        .filter((o) => o.kind === "download" || o.kind === "verify")
        .map((o) => (
          <OperationStatus key={o.id} operation={o} />
        ))}
      {consent && (
        <div className="modal-shade">
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="consent-title"
          >
            <h2 id="consent-title">Download {consent.display_name}?</h2>
            <p>Licence: {consent.licence}</p>
            {!consent.commercial_use_allowed && (
              <p className="warning-text">Non-commercial use only.</p>
            )}
            <p>
              Source: <span className="break">{consent.weights.url}</span>
            </p>
            <p>
              Confirm that you accept this licence for your intended use. Your
              consent is recorded on this computer.
            </p>
            <div className="dialog-actions">
              <button onClick={() => setConsent(undefined)}>Cancel</button>
              <button
                className="primary"
                onClick={() => {
                  operate(`models/${consent.id}/download`, {
                    agree: true,
                    licence: consent.licence,
                  });
                  setConsent(undefined);
                }}
              >
                Accept licence and download
              </button>
            </div>
          </div>
        </div>
      )}
      {removal && (
        <div className="modal-shade">
          <div className="dialog" role="dialog" aria-modal="true">
            <h2>Remove {removal.display_name}?</h2>
            <p>
              This removes the model weights from this computer. Videos already
              finished remain unchanged. Models used in the queue cannot be
              removed.
            </p>
            <div className="dialog-actions">
              <button onClick={() => setRemoval(undefined)}>Keep model</button>
              <button
                className="danger"
                onClick={async () => {
                  try {
                    await api.call(`models/${removal.id}`, "DELETE");
                    setRemoval(undefined);
                    refresh();
                  } catch (e) {
                    setError((e as Error).message);
                    setRemoval(undefined);
                  }
                }}
              >
                Remove model
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function SettingsPage({
  api,
  value,
  health,
  saved,
  calibrate,
  operation,
}: {
  api: Api;
  value: Settings;
  health?: Health;
  saved(): void;
  calibrate(): void;
  operation?: Operation;
}) {
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => setDraft(value), [value]);
  const change = (key: keyof Settings, value: string | boolean | number) =>
    setDraft((old) => ({ ...old, [key]: value }));
  return (
    <section>
      <div className="page-heading">
        <div>
          <h1>Settings</h1>
          <p>Defaults apply to newly added videos.</p>
        </div>
        <button
          className="primary"
          onClick={async () => {
            try {
              const editable = { ...draft };
              delete editable.seen_failures;
              await api.call("settings", "PUT", editable);
              saved();
              setMessage("Settings saved.");
              setError("");
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Save settings
        </button>
      </div>
      <h2>Defaults</h2>
      <div className="form-grid">
        <label className="span-two">
          Default output folder
          <div className="input-button">
            <input
              value={draft.output_folder}
              placeholder="Source folder / enhanced"
              onChange={(e) => change("output_folder", e.target.value)}
            />
            <button
              onClick={async () => {
                const folder = (await window.desktop.files("folder"))[0];
                if (folder) change("output_folder", folder);
              }}
            >
              Browse…
            </button>
          </div>
        </label>
        <label>
          Default preset
          <select
            value={draft.preset}
            onChange={(e) => change("preset", e.target.value)}
          >
            <option value="standard">Standard</option>
            <option value="fast">Fast</option>
          </select>
        </label>
        <label>
          Default codec
          <select
            value={draft.codec}
            onChange={(e) => change("codec", e.target.value)}
          >
            <option value="hevc">HEVC</option>
            <option value="h264">H.264</option>
            <option value="av1">AV1</option>
          </select>
        </label>
        <label>
          Default short side
          <select
            value={draft.short_side}
            onChange={(e) =>
              change(
                "short_side",
                e.target.value === "keep" ? "keep" : Number(e.target.value),
              )
            }
          >
            <option value="keep">Keep</option>
            {[1080, 1440, 2160].map((n) => (
              <option value={n} key={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Default frame rate
          <select
            value={draft.fps}
            onChange={(e) => change("fps", e.target.value)}
          >
            <option value="off">Keep</option>
            <option value="2x">2×</option>
          </select>
        </label>
      </div>
      <h2>App</h2>
      <div className="form-grid">
        <label>
          Theme
          <select
            value={draft.theme}
            onChange={(e) => change("theme", e.target.value)}
          >
            <option value="system">System</option>
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.start_with_windows}
            onChange={(e) => change("start_with_windows", e.target.checked)}
          />
          Start with Windows (hidden in tray)
        </label>
      </div>
      <details>
        <summary>Advanced</summary>
        <p>
          These options apply to new jobs. Keep defaults unless you need a
          specific adjustment.
        </p>
        <div className="form-grid">
          {[
            ["clip_length", "Clip length", 15],
            ["clip_overlap", "Clip overlap", 2],
            [
              "interpolation_safety_threshold",
              "Interpolation safety threshold",
              0.2,
            ],
          ].map(([key, label, fallback]) => (
            <label key={key}>
              {label}
              <input
                type="number"
                step={key === "interpolation_safety_threshold" ? "0.01" : "1"}
                value={draft.advanced[key] ?? fallback}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    advanced: {
                      ...draft.advanced,
                      [key]: Number(e.target.value),
                    },
                  })
                }
              />
            </label>
          ))}
        </div>
      </details>
      <h2>Diagnostics</h2>
      <label className="span-two">
        Log folder
        <div className="input-button">
          <input
            value={draft.log_folder}
            placeholder={health?.home || "Engine home"}
            onChange={(e) => change("log_folder", e.target.value)}
          />
          <button
            onClick={() =>
              window.desktop
                .openFolder(draft.log_folder || health?.home || "")
                .catch((e) => setError(e.message))
            }
          >
            Open
          </button>
        </div>
      </label>
      <div className="toolbar">
        <button
          onClick={calibrate}
          disabled={
            operation?.state === "running" || operation?.state === "waiting"
          }
        >
          Run speed calibration
        </button>
        <button
          onClick={() =>
            window.desktop
              .copy(JSON.stringify({ health, settings: draft }, null, 2))
              .then(() => setMessage("Diagnostics copied."))
          }
        >
          Copy diagnostics
        </button>
      </div>
      {operation && <OperationStatus operation={operation} />}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <div className="about">
        <h2>About</h2>
        <p>Version {health?.version || "0.1.0"} · Windows 11 · MIT licence</p>
        <p>
          Your videos stay on this computer. No telemetry or automatic updates.
        </p>
        <p>
          Models have separate licences; some are non-commercial. Review the
          Models page before using them.
        </p>
        <p>
          {health?.gpu || "GPU detection in progress"} · Driver{" "}
          {health?.driver || "unknown"} ·{" "}
          {health?.vram_bytes
            ? `${(health.vram_bytes / 1e9).toFixed(1)} GB VRAM`
            : "VRAM unknown"}
        </p>
      </div>
    </section>
  );
}

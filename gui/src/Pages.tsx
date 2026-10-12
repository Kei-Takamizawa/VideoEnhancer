import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import type { Health, Model, Operation, Settings } from "./types";

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
  health,
}: {
  api: Api;
  models: Model[];
  refresh(): void;
  operate(route: string, data?: unknown): void;
  operations: Operation[];
  settings?: Settings;
  compare?(): void;
  health?: Health;
}) {
  const [consent, setConsent] = useState<Model>();
  const [accepted, setAccepted] = useState(false);
  useEffect(() => setAccepted(false), [consent]);
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
            {(key === "size" ? 1 : 0) +
              models.filter((m) => group(m) === key).length}
          </button>
        ))}
        <button disabled>Faces · coming later</button>
      </div>
      <div className="model-grid">
        {category === "size" && (
          <article className="card model-card">
            <h2>
              Standard resize{" "}
              {!settings?.size_model && <span className="badge">Default</span>}
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
            {settings?.size_model && (
              <button
                onClick={async () => {
                  await api.call("settings", "PUT", { size_model: "" });
                  refresh();
                }}
              >
                Make it my default
              </button>
            )}
          </article>
        )}
        {models
          .filter((m) => group(m) === category)
          .map((m) => {
            const c = m.catalog;
            const key =
              m.task === "restore"
                ? "restore_model"
                : m.task === "size"
                  ? "size_model"
                  : "interp_model";
            const defaultId =
              settings?.[key] ||
              (m.task === "restore"
                ? "basicvsrpp-ntire21-decompress"
                : m.task === "size"
                  ? ""
                  : "rife-4.25");
            const reference = c?.reference_speed;
            const speed =
              m.architecture === "drunet"
                ? reference?.variants?.[settings?.restore_strength || "medium"] || reference
                : reference;
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
            const downloading = operation?.kind === "download" && ["running", "waiting"].includes(operation.state);
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
                  {c?.summary || c?.description ||
                    "A model you added. Review its details before use."}
                </p>
                {m.architecture === "drunet" && (
                  <label>
                    Strength
                    <select
                      value={settings?.restore_strength || "medium"}
                      onChange={async (e) => {
                        await api.call("settings", "PUT", {
                          restore_strength: e.target.value,
                        });
                        refresh();
                      }}
                    >
                      <option value="light">Light</option>
                      <option value="medium">Medium</option>
                      <option value="strong">Strong</option>
                    </select>
                  </label>
                )}
                <dl className="model-facts">
                  <div>
                    <dt>Speed</dt>
                    <dd
                      title={
                        speed
                          ? `About ${(30 / speed.fps).toFixed(1)} h per hour of 30 fps video · ${reference?.gpu}`
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
                {downloading ? (
                  <div className="download-progress">
                    <span>{operation.percent === undefined ? "Downloading…" : `Downloading ${Math.floor(operation.percent)}%`}</span>
                    <span className="muted">{operation.phase}</span>
                    <progress aria-label={`Downloading ${c?.title || m.display_name}`} max={100} value={operation.percent} />
                    <button onClick={() => operate(`operations/${operation.id}/cancel`)}>Cancel</button>
                  </div>
                ) : m.weights_verified ? (
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
                {operation && !downloading && <OperationStatus operation={operation} cancel={operation.state === "running" || operation.state === "waiting" ? () => operate(`operations/${operation.id}/cancel`) : undefined} />}
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
                        setError("");
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
            <p>{details.display_name}</p>
            <p>Licence: {details.licence}</p>
            <p>{details.catalog?.licence_plain}</p>
            <p className="break">
              Source: {details.weights.url ? new URL(details.weights.url).hostname : "Added from a local folder"}
            </p>
            <p>SHA-256: {details.weights.sha256.slice(0, 12)}… <button onClick={() => window.desktop.copy(details.weights.sha256)}>Copy</button></p>
            <p>
              {details.catalog?.reference_speed
                ? `${details.catalog.reference_speed.fps.toFixed(2)} fps · sampled process peak ${details.catalog.reference_speed.peak_memory_gb.toFixed(2)} GB · ${details.catalog.reference_speed.gpu} · ${details.catalog.reference_speed.mode || "standard"} · tile ${details.catalog.reference_speed.tile_size || "none"}, overlap ${details.catalog.reference_speed.tile_overlap || 0}`
                : "Speed and peak memory have not been measured for this catalog entry."}
            </p>
            <p>Peak GPU memory {details.catalog?.reference_speed?.peak_memory_gb.toFixed(2) || "not measured"} GB of {health?.vram_bytes ? (health.vram_bytes / 1e9).toFixed(1) : "unknown"} GB</p>
            {[settings?.restore_model || "basicvsrpp-ntire21-decompress", settings?.interp_model || "rife-4.25", settings?.size_model].includes(details.id) && <p>Default for Standard</p>}
            <p>
              Invents detail:{" "}
              {details.catalog?.invents_detail || "Not specified"} · Flicker:{" "}
              {details.catalog?.flicker || "Not specified"}
            </p>
            <button onClick={() => setDetails(undefined)}>Close</button>
          </div>
        </div>
      )}
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
            <p>{consent.catalog?.licence_plain}</p>
            {consent.publisher_url && <a href={consent.publisher_url} target="_blank" rel="noreferrer">Model publisher’s page</a>}
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
              <label className="check"><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} />I accept this licence</label>
              <button onClick={() => setConsent(undefined)}>Cancel</button>
              <button
                className="primary"
                disabled={!accepted}
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
            <h2>{error ? "This model is needed" : `Remove ${removal.catalog?.title || removal.display_name}?`}</h2>
            {error && <p role="alert">{error}</p>}
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
  const dirty = useRef(false);
  const currentDraft = useRef(draft);
  const savedCallback = useRef(saved);
  currentDraft.current = draft;
  savedCallback.current = saved;
  useEffect(() => { if (!dirty.current) setDraft(value); }, [value]);
  useEffect(() => {
    if (!dirty.current) return;
    setMessage("Saving…");
    const timer = setTimeout(async () => {
      try {
        const editable = { ...draft };
        delete editable.seen_failures;
        delete editable.tray_explained;
        await api.call("settings", "PUT", editable);
        if (currentDraft.current === draft) {
          dirty.current = false;
          setMessage("Saved");
          setError("");
          savedCallback.current();
        }
      } catch (error) { setError((error as Error).message); setMessage(""); }
    }, 400);
    return () => clearTimeout(timer);
  }, [api, draft]);
  const change = (key: keyof Settings, value: string | boolean | number) => {
    dirty.current = true;
    setDraft(old => ({ ...old, [key]: value }));
  };
  return (
    <section className="settings-page">
      <div className="page-heading"><h1>Settings</h1><span role="status">{message}</span></div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="settings-columns">
        <div>
          <article className="card">
            <h2>Defaults for new videos</h2>
            <label>Save to<div className="input-button"><input aria-label="Default output folder" value={draft.output_folder} placeholder="Next to the original, in enhanced" onChange={event => change("output_folder", event.target.value)} /><button onClick={async () => { const folder = (await window.desktop.files("folder"))[0]; if (folder) change("output_folder", folder); }}>Choose…</button></div></label>
            <div className="form-grid">
              <label>Default mode<select value={draft.preset} onChange={event => change("preset", event.target.value)}><option value="standard">Standard</option><option value="fast">Fast</option></select></label>
              <label>Default size<select value={draft.short_side} onChange={event => change("short_side", event.target.value === "keep" ? "keep" : Number(event.target.value))}><option value="keep">Keep</option>{[1080,1440,2160].map(size => <option key={size} value={size}>{size}p</option>)}</select></label>
              <label>Default frame rate<select value={draft.fps} onChange={event => change("fps", event.target.value)}><option value="off">Keep</option><option value="2x">2×</option></select></label>
              <label>Default codec<select value={draft.codec} onChange={event => change("codec", event.target.value)}><option value="h264">H.264</option><option value="hevc">HEVC</option><option value="av1" disabled={health?.av1_supported !== true}>AV1</option></select></label>
            </div>
            {health?.av1_supported === false && <p className="muted">{health.av1_unavailable_reason || "AV1 hardware encoding is unavailable."}</p>}
          </article>
          <article className="card"><h2>After processing</h2><label className="check"><input type="checkbox" checked={!!draft.delete_original_after} onChange={event => change("delete_original_after", event.target.checked)} />Delete the original after a verified output</label><p className="muted">Off by default. Files are moved to the Recycle Bin only after the output passes all checks.</p></article>
          <article className="card"><details><summary>Advanced</summary><p className="muted">Apply to new videos. Keep defaults unless you need a specific adjustment.</p><div className="form-grid">{[["clip_length","Clip length",15],["clip_overlap","Clip overlap",2],["interpolation_safety_threshold","Interpolation safety threshold",0.2]].map(([key,label,fallback]) => <label key={key}>{label}<input type="number" step={key === "interpolation_safety_threshold" ? "0.01" : "1"} value={draft.advanced[key] ?? fallback} onChange={event => { dirty.current = true; setDraft(old => ({ ...old, advanced: { ...old.advanced, [key]: Number(event.target.value) } })); }} /></label>)}</div></details></article>
        </div>
        <div>
          <article className="card">
            <h2>App</h2><div className="form-grid">
              <label>Theme<select value={draft.theme} onChange={event => change("theme", event.target.value)}><option value="system">System</option><option value="dark">Dark</option><option value="light">Light</option></select></label>
              <label>Zoom<select value={draft.zoom || 100} onChange={event => { const zoom = Number(event.target.value); change("zoom", zoom); void window.desktop.zoom(zoom).catch(error => setError(error.message)); }}>{[80,90,100,110,125,150].map(zoom => <option key={zoom} value={zoom}>{zoom}%</option>)}</select></label>
            </div><p className="muted">Above 100%, small windows can scroll.</p>
            <label className="check"><input type="checkbox" checked={draft.start_with_windows} onChange={event => change("start_with_windows", event.target.checked)} />Start with Windows (hidden in tray)</label>
          </article>
          <article className="card"><h2>Diagnostics</h2><label>Log folder<div className="input-button"><input value={draft.log_folder} placeholder={health?.home || "Engine home"} onChange={event => change("log_folder", event.target.value)} /><button onClick={() => window.desktop.openFolder(draft.log_folder || health?.home || "").catch(error => setError(error.message))}>Open</button></div></label><div className="toolbar"><button onClick={calibrate} disabled={operation?.state === "running" || operation?.state === "waiting"}>Run speed calibration{health?.speed_profile?.calibration_minutes ? ` (about ${health.speed_profile.calibration_minutes} min)` : ""}</button><button onClick={() => window.desktop.copy(JSON.stringify({ health, settings: draft }, null, 2)).then(() => setMessage("Diagnostics copied."))}>Copy diagnostics</button></div>{health?.speed_profile && <p>{health.speed_profile.source === "builtin" ? "Using the built-in speed profile." : health.speed_profile.source === "measured" ? "Using this PC’s measured speed profile." : "No speed profile for this GPU. Estimates are uncalibrated."}</p>}{health?.speed_profile?.driver_note && <p>{health.speed_profile.driver_note}</p>}{operation && <OperationStatus operation={operation} cancel={["running", "waiting"].includes(operation.state) ? () => api.call(`operations/${operation.id}/cancel`, "POST").catch(error => setError(error.message)) : undefined} />}</article>
          <article className="card"><h2>About</h2><p>VideoEnhancer {health?.version || "0.1.0"} · Windows 11 · MIT licence</p><p>{health?.gpu || "Detecting GPU…"} · Driver {health?.driver || "unknown"}{health?.vram_bytes ? ` · ${(health.vram_bytes / 1e9).toFixed(1)} GB VRAM` : ""}</p><p className="muted">Your videos stay on this computer. No telemetry or automatic updates. Models have their own licences.</p></article>
        </div>
      </div>
    </section>
  );
}

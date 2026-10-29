import { StorageCard } from "./Storage";
import { Licences } from "./Licences";
import { VideoLinksCard } from "./VideoLinks";
import { CopyMessage, Notice } from "./Notice";
import { Check } from "lucide-react";
import { ActionButton } from "./ActionButton";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { duration } from "./api";
import type { Health, Model, Operation, Settings } from "./types";

const sessionStarted = Date.now();

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
  const remaining = operation.remaining_seconds;
  const percent = operation.percent;
  return (
    <Notice autoDismiss={operation.state === "failed"} role={operation.state === "failed" ? "alert" : "status"} dismissible={operation.state === "failed"} className={operation.state === "failed" ? "error" : "operation"} identity={operation.id + operation.state + operation.error}>
      <strong>
        {operation.kind.charAt(0).toUpperCase() + operation.kind.slice(1)}:{" "}
        {operation.state}
      </strong>
      <p>{operation.error || operation.phase}</p>
      {operation.kind === "history-removal" && <>
        <p>{operation.completed_files || 0} of {operation.total_files || 0} files checked</p>
        {operation.current_file && <p>{operation.current_file.kind}: {operation.current_file.outcome}</p>}
      </>}
      {remaining != null && ["waiting", "running"].includes(operation.state) && <p className="time-left">{duration(remaining)} left</p>}
      {percent !== undefined && ["waiting", "running"].includes(operation.state) && (
        <progress
          aria-label="Operation progress"
          max="100"
          value={percent}
        />
      )}
      {["waiting", "running"].includes(operation.state) && (
        <>
          {cancel && <ActionButton onClick={cancel}>Cancel</ActionButton>}
        </>
      )}
      {operation.result?.weights_verified && (
        <p>
          SHA-256 verified · {operation.result.bytes?.toLocaleString()} bytes
          <br />
          <code>{operation.result.sha256}</code>
        </p>
      )}
    </Notice>
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
  const modelRemovalBlocked = error.startsWith("The default for Standard.") || error.startsWith("Used by ") || /^\d+ videos in the queue use it/.test(error);
  const [category, setCategory] = useState("cleanup");
  const [details, setDetails] = useState<Model>();
  const [resizeDetails, setResizeDetails] = useState(false);
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
        <ActionButton
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
        </ActionButton>
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
        <Notice autoDismiss={!modelRemovalBlocked} identity={error} dismiss={() => setError("")}>{error}</Notice>
      )}
      <div className="filter-pills" aria-label="Model category">
        {[
          ["cleanup", "Cleanup"],
          ["motion", "Smoother motion"],
          ["size", "Bigger picture"],
        ].map(([key, label]) => (
          <ActionButton
            key={key}
            aria-pressed={category === key}
            onClick={() => {
              setCategory(key);
            }}
          >
            {label} ·{" "}
            {(key === "size" ? 1 : 0) +
              models.filter((m) => group(m) === key).length}
          </ActionButton>
        ))}
        <ActionButton disabled>Faces · coming later</ActionButton>
        <ActionButton className="model-compare" disabled={!compare} onClick={compare}>
          Compare on my video
        </ActionButton>

      </div>
      {resizeDetails && <div className="modal"><div className="dialog" role="dialog" aria-modal="true" aria-label="Standard resize details">
        <h2>Standard resize</h2><p>Makes the picture bigger without AI. Never changes the look.</p>
        <p>Changes the look: Very little · Licence: No model weights · No download</p>
        <ActionButton onClick={async () => { await api.call("settings", "PUT", { size_model: "" }); refresh(); }}>Make it my default</ActionButton>
        <ActionButton onClick={() => setResizeDetails(false)}>Close</ActionButton>
      </div></div>}
      <div className="model-grid">
        {category === "size" && (
          <article className="card model-card">
            <h2>
              Standard resize{" "}
              {!settings?.size_model && <span className="badge">Default</span>}
            </h2>
            <p>Makes the picture bigger without AI. Never changes the look.</p>
            <span className="badge">Built in</span>
            <ActionButton onClick={() => setResizeDetails(true)}>Details</ActionButton>
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
              <article className="card model-card" key={m.id} role="button" tabIndex={0} aria-label={`Details for ${c?.title || m.display_name}`}
                onClick={() => setDetails(m)} onKeyDown={event => { if (event.target === event.currentTarget && ["Enter", " "].includes(event.key)) { event.preventDefault(); setDetails(m); } }}>
                <h2>{c?.title || m.display_name}</h2>
                <p className="muted">{c?.summary || c?.description || "A model you added. Review its details before use."}</p>
                {m.weights_verified && !downloading && <span className="installed-check"><Check size={14} aria-hidden="true" /> Installed</span>}
                <div onClick={event => event.stopPropagation()}>
                  {downloading ? <div className="download-progress"><ActionButton className="install-progress" disabled style={{ background: `linear-gradient(to right, var(--install-fill) ${operation.percent || 0}%, var(--install-empty) ${operation.percent || 0}%)` }} aria-label={`Installing ${c?.title || m.display_name}`}>
                    {operation.phase} {Math.floor(operation.percent || 0)}% · {operation.remaining_seconds != null ? `${duration(operation.remaining_seconds)} left` : "Starting…"}
                  </ActionButton><progress className="sr-only" aria-label={`Downloading ${c?.title || m.display_name}`} max={100} value={operation.percent || 0} /><ActionButton onClick={() => operate(`operations/${operation.id}/cancel`)}>Cancel</ActionButton></div>
                  : m.weights_verified ? <ActionButton className="danger" disabled={!!m.uninstall_reason || defaultId === m.id} title={m.uninstall_reason || (defaultId === m.id ? "Choose another default before uninstalling this model." : "Uninstall this model")} onClick={() => { setRemoval(m); setError(""); }}>Uninstall</ActionButton>
                  : <ActionButton className="primary" onClick={() => setConsent(m)}>Install</ActionButton>}
                </div>
                {operation?.state === "failed" && <Notice autoDismiss identity={(operation.created_at || operation.id) + operation.error}>{operation.error || "Install failed. Open details for the full log."}</Notice>}
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
            <p>SHA-256: {details.weights.sha256.slice(0, 12)}… <ActionButton onClick={() => window.desktop.copy(details.weights.sha256)}>Copy</ActionButton></p>
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
            {details.architecture === "drunet" && <label>Strength<select value={settings?.restore_strength || "medium"} onChange={async event => { await api.call("settings", "PUT", { restore_strength: event.target.value }); refresh(); }}><option value="light">Light</option><option value="medium">Medium</option><option value="strong">Strong</option></select></label>}
            <div className="actions"><ActionButton disabled={!details.weights_verified} onClick={async () => { const key = details.task === "restore" ? "restore_model" : details.task === "size" ? "size_model" : "interp_model"; await api.call("settings", "PUT", { [key]: details.id }); refresh(); }}>Make it my default</ActionButton>
            <ActionButton onClick={() => operate(`models/${details.id}/verify`)}>Verify again</ActionButton></div>
            {operations.filter(operation => operation.request?.model_id === details.id && operation.state === "failed").map(operation => <OperationStatus key={operation.id} operation={operation} />)}
            <ActionButton onClick={() => setDetails(undefined)}>Close</ActionButton>
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
              <p className="warning-text">Non-commercial use only.<CopyMessage text="Non-commercial use only." /></p>
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
              <ActionButton onClick={() => setConsent(undefined)}>Cancel</ActionButton>
              <ActionButton
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
              </ActionButton>
            </div>
          </div>
        </div>
      )}
      {removal && (
        <div className="modal-shade">
          <div className="dialog" role="dialog" aria-modal="true">
            <h2>{error ? "This model is needed" : `Uninstall ${removal.catalog?.title || removal.display_name}?`}</h2>
            {error && <Notice autoDismiss={!modelRemovalBlocked} identity={error} dismiss={() => setError("")}>{error}</Notice>}
            <p>
              This removes the model weights from this computer. Videos already
              finished remain unchanged. Models used in the queue cannot be
              removed.
            </p>
            <div className="dialog-actions">
              <ActionButton onClick={() => setRemoval(undefined)}>Keep model</ActionButton>
              <ActionButton
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
              </ActionButton>
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
  tour,
  appearance,
}: {
  api: Api;
  value: Settings;
  health?: Health;
  saved(): void;
  calibrate(): void;
  operation?: Operation;
  tour?(): void;
  appearance?(theme: string): void;
}) {
  const pastCalibration = operation?.kind === "calibrate" && operation.state === "failed"
    && (!operation.created_at || Date.parse(operation.created_at) < sessionStarted);
  const speedProfileMessage = health?.speed_profile?.source === "builtin" ? "Using the built-in speed profile." : health?.speed_profile?.source === "measured" ? "Using this PC's measured speed profile." : "No speed profile for this GPU. Estimates are uncalibrated. Run speed calibration to measure this PC.";
  const previousCalibration = pastCalibration
    ? `The last calibration on ${operation?.created_at ? new Date(operation.created_at).toLocaleString() : "an earlier date"} failed: ${operation?.error || "No reason was recorded."}` : "";
  const [draft, setDraft] = useState(value);
  const [licencesOpen, setLicencesOpen] = useState(false);
  const licencesButton = useRef<HTMLButtonElement>(null);
  const restoreLicencesFocus = useRef(false);
  const closeLicences = useCallback(() => { restoreLicencesFocus.current = true; setLicencesOpen(false); }, []);
  useEffect(() => {
    if (!licencesOpen && restoreLicencesFocus.current) {
      licencesButton.current?.focus();
      restoreLicencesFocus.current = false;
    }
  }, [licencesOpen]);
  const [startupError, setStartupError] = useState("");
  useEffect(() => {
    let active = true;
    let revision = 0;
    const update = (event: Event) => { revision++; setStartupError((event as CustomEvent<string>).detail); };
    window.addEventListener("startup-status", update);
    void window.desktop.startupStatus?.().then(value => { if (active && revision === 0) setStartupError(value); }).catch(error => { if (active && revision === 0) setStartupError(String(error)); });
    return () => { active = false; window.removeEventListener("startup-status", update); };
  }, []);
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
        delete editable.tour_completed;
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
    if (key === "theme") {
      const theme = String(value);
      appearance?.(theme);
      document.documentElement.dataset.theme = theme === "system"
        ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme;
      void window.desktop.theme?.(theme);
    }
    dirty.current = true;
    setDraft(old => ({ ...old, [key]: value }));
  };
  return (
    <>
    {licencesOpen && <Licences close={closeLicences} />}
    <section className="settings-page" hidden={licencesOpen}>
      <div className="page-heading"><h1>Settings</h1><ActionButton onClick={tour} className="tutorial">Tutorial</ActionButton><span role="status">{message}</span></div>
      {error && <Notice autoDismiss identity={error} dismiss={() => setError("")}>{error}</Notice>}
      <div className="settings-columns">
        <div>
          <article className="card">
            <h2>Defaults for new videos</h2>
            <label>Save to<div className="input-button"><input aria-label="Default output folder" value={draft.output_folder} placeholder="Next to the original, in enhanced" onChange={event => change("output_folder", event.target.value)} /><ActionButton onClick={async () => { const folder = (await window.desktop.files("folder"))[0]; if (folder) change("output_folder", folder); }}>Choose…</ActionButton></div></label>
            <div className="form-grid">
              <label>Default mode<select value={draft.preset} onChange={event => change("preset", event.target.value)}><option value="standard">Standard</option><option value="fast">Fast</option></select></label>
              <label>Default size<select value={draft.short_side} onChange={event => change("short_side", event.target.value === "keep" ? "keep" : Number(event.target.value))}><option value="keep">Keep</option>{[1080,1440].map(size => <option key={size} value={size}>{size}p</option>)}</select></label>
              <label>Default frame rate<select value={draft.fps} onChange={event => change("fps", event.target.value)}><option value="off">Keep</option><option value="2x">2×</option></select></label>
              <label>Default codec<select value={draft.codec} onChange={event => change("codec", event.target.value)}><option value="h264">H.264</option><option value="hevc">HEVC</option><option value="av1" disabled={health?.av1_supported !== true}>AV1</option></select></label>
            </div>
            {health?.av1_supported === false && <p className="muted">{health.av1_unavailable_reason || "AV1 hardware encoding is unavailable."}<CopyMessage text={health.av1_unavailable_reason || "AV1 hardware encoding is unavailable."} /></p>}
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
            {startupError && <p role="alert">{startupError}<CopyMessage text={startupError} /></p>}
          </article>
          <article className="card"><h2>Diagnostics</h2><label>Log folder<div className="input-button"><input value={draft.log_folder} placeholder={health?.home || "Engine home"} onChange={event => change("log_folder", event.target.value)} /><ActionButton aria-label="Open log folder" onClick={() => window.desktop.openFolder(draft.log_folder || health?.home || "").catch(error => setError(error.message))}>Open</ActionButton></div></label><div className="toolbar"><ActionButton onClick={calibrate} disabled={operation?.state === "running" || operation?.state === "waiting"}>{pastCalibration ? "Run again" : "Run speed calibration"}{health?.speed_profile?.calibration_minutes ? ` (about ${health.speed_profile.calibration_minutes} min)` : ""}</ActionButton><ActionButton onClick={() => window.desktop.copy(JSON.stringify({ health, settings: draft }, null, 2))}>Copy diagnostics</ActionButton></div>{health?.speed_profile && <p>{speedProfileMessage}<CopyMessage text={speedProfileMessage} /></p>}{health?.speed_profile?.driver_note && <p>{health.speed_profile.driver_note}<CopyMessage text={health.speed_profile.driver_note} /></p>}{pastCalibration ? <p>{previousCalibration}<CopyMessage text={previousCalibration} /></p> : operation && <OperationStatus operation={operation} cancel={["running", "waiting"].includes(operation.state) ? () => api.call(`operations/${operation.id}/cancel`, "POST").catch(error => setError(error.message)) : undefined} />}</article>
          <StorageCard api={api} automatic={draft.cleanup_working_files !== false} change={value => change("cleanup_working_files", value)} />
          <VideoLinksCard api={api} />
          <article className="card"><h2>About</h2><p>VideoEnhancer {health?.version || "0.1.0"} · Windows 11 · MIT licence</p><p>{health?.gpu || "Detecting GPU…"} · Driver {health?.driver || "unknown"}{health?.vram_bytes ? ` · ${(health.vram_bytes / 1e9).toFixed(1)} GB VRAM` : ""}</p>
            {health?.software_decoders && <p>FFmpeg software decoding: VP9 {health.software_decoders.vp9 ? "available" : "unavailable"}, AV1 {health.software_decoders.av1 ? "available" : "unavailable"}</p>}
            <ActionButton ref={licencesButton} onClick={() => setLicencesOpen(true)}>Open-source licences</ActionButton><p className="muted">Your videos stay on this computer. No telemetry or automatic updates. Models have their own licences.</p></article>
        </div>
      </div>
    </section>
    </>
  );
}

import { ActionButton } from "./ActionButton";
import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { duration, filename, folder, when } from "./api";
import type { Job, Model, Settings, Estimate, Media } from "./types";

type Preview = {
  media: Media;
  presets: Record<string, Estimate>;
  warnings: string[];
  output: string;
  error?: string;
};
export function AddDialog({
  api,
  files,
  defaults,
  models,
  av1 = false,
  av1Reason,
  close,
  saved,
  trial,
}: {
  api: Api;
  files: string[];
  defaults: Settings;
  models: Model[];
  av1?: boolean;
  av1Reason?: string | null;
  close(): void;
  saved(): void;
  trial(
    file: string,
    settings: Settings,
    media?: Media,
    apply?: (key: "restore_model" | "interp_model" | "size_model" | "preset", id: string) => void,
  ): void;
}) {
  const [items, setItems] = useState(files);
  const [settings, setSettings] = useState({ ...defaults });
  const added = useRef(new Set<string>());
  const [totals, setTotals] = useState<Record<string, Estimate>>({});
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const [refresh, setRefresh] = useState(0);
  const timeKey = JSON.stringify([items, settings.preset, settings.short_side, settings.fps,
    settings.restore_model, settings.interp_model, settings.size_model, settings.restore_strength, settings.size_strength]);
  useEffect(() => {
    const timer = setInterval(() => setRefresh(old => old + 1), 30000);
    const focus = () => setRefresh(old => old + 1);
    window.addEventListener("focus", focus);
    return () => { clearInterval(timer); window.removeEventListener("focus", focus); };
  }, []);
  useEffect(() => {
    let current = true;
    setLoading(true);
    const request = new AbortController();
    const timer = setTimeout(async () => {
      if (!items.length) { setLoading(false); return; }
      try {
        const chosen = settingsRef.current;
        const result = await api.call<{ files: Record<string, Preview>; presets: Record<string, Estimate> }>("estimate", "POST", { files: items, settings: chosen, output_folder: chosen.output_folder }, request.signal);
        if (current) { setPreviews(result.files); setTotals(result.presets); setError(""); }
      } catch (error) { if (current) setError((error as Error).message); }
      finally { if (current) setLoading(false); }
    }, 200);
    return () => {
      current = false;
      request.abort();
      clearTimeout(timer);
    };
  }, [api, items, timeKey, refresh]);
  useEffect(() => {
    const request = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const result = await api.call<{ files: Record<string, { warnings: string[]; output: string }> }>("estimate/space", "POST", { files: items, settings: settingsRef.current }, request.signal);
        setPreviews(old => Object.fromEntries(Object.entries(old).map(([file, preview]) => [file,
          result.files[file] ? { ...preview, output: result.files[file].output, warnings: [...new Set([...preview.warnings.filter(w => !w.includes("Insufficient") && !w.includes("Output too small")), ...result.files[file].warnings])] } : preview])));
      } catch (error) { if (!request.signal.aborted) setError((error as Error).message); }
    }, 200);
    return () => { clearTimeout(timer); request.abort(); };
  }, [api, items, settings.output_folder, settings.codec, settings.short_side, settings.fps]);
  const addable = items.filter(file => previews[file] && !previews[file].error && !previews[file].warnings.some(w =>
    ["HDR", "Smart App Control", "Insufficient", "Output too small"].some(reason => w.includes(reason))));
  const field = (key: keyof Settings, value: string | number | boolean) =>
    setSettings((old) => ({ ...old, [key]: value }));
  return (
    <div className="modal-shade">
      <div
        className="dialog wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-title"
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.target instanceof HTMLInputElement) {
            e.preventDefault();
            e.currentTarget
              .querySelector<HTMLButtonElement>(".add-submit")
              ?.click();
          }
        }}
      >
        <h2 id="add-title">
          Add {items.length === 1 ? "video" : `${items.length} videos`}
        </h2>
        <div className="mode-cards">
          {["standard", "fast"].map((mode) => (
            <ActionButton
              key={mode}
              aria-pressed={settings.preset === mode}
              onClick={() => field("preset", mode)}
            >
              <strong>{mode === "standard" ? "Standard" : "Fast"}</strong>
              <p>
                {mode === "standard"
                  ? "Cleans up blockiness and noise, then makes motion smoother. Keeps the original look."
                  : "Only makes motion smoother and resizes. No cleanup."}
              </p>
              <p>
                {totals[mode]
                  ? totals[mode].unknown_models?.length ? "Speed unknown" : `${duration(totals[mode].seconds)} of work`
                  : "Preparing…"}
              </p>
              <p className="mode-finish">
                {totals[mode]
                  ? totals[mode].unknown_models?.length ? "Run speed calibration." : `Done ${when(totals[mode].finish)}`
                  : ""}
              </p>
            </ActionButton>
          ))}
        </div>
        <details>
          <summary className="output-summary">
            <span>
              Output:{" "}
              {settings.short_side === "keep"
                ? "Original size"
                : `${settings.short_side}p`}{" "}
              ·{" "}
              {previews[items[0]]
                ? (() => {
                    const [n, d = "1"] =
                      previews[items[0]].media.cfr_fps.split("/");
                    return `${((Number(n) / Number(d)) * (settings.fps === "2x" ? 2 : 1)).toFixed(0)} fps`;
                  })()
                : settings.fps === "2x"
                  ? "Double frame rate"
                  : "Original frame rate"}{" "}
              · {settings.codec.toUpperCase()} ·{" "}
              {settings.output_folder
                ? `Saved in ${settings.output_folder}`
                : 'Saved next to the original, in "enhanced"'}
            </span>
            <span>More options</span>
          </summary>
          <div className="form-grid">
            <label>
              Mode
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
              File format
              <select
                value={settings.codec}
                onChange={(e) => field("codec", e.target.value)}
              >
                <option value="hevc">HEVC</option>
                <option value="h264">H.264</option>
                <option value="av1" disabled={!av1}>
                  AV1
                </option>
              </select>
            </label>
            {!av1 && (
              <p className="span-two">
                {av1Reason || "Checking AV1 hardware encoding…"}
              </p>
            )}
            <label className="span-two">
              Output folder
              <div className="input-button">
                <input
                  placeholder="Source folder / enhanced"
                  value={settings.output_folder}
                  onChange={(e) => field("output_folder", e.target.value)}
                />
                <ActionButton
                  onClick={async () => {
                    const selected = await window.desktop.files("folder");
                    if (selected[0]) field("output_folder", selected[0]);
                  }}
                >
                  Browse…
                </ActionButton>
              </div>
            </label>
          </div>
          <label>
            Cleanup model
            <select
              value={settings.restore_model || ""}
              onChange={(e) => field("restore_model", e.target.value)}
            >
              <option value="">Preset default</option>
              {models
                .filter((m) => m.task === "restore" && m.weights_verified)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.display_name}
                    {m.commercial_use_allowed ? "" : " (Non-commercial)"}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Smoother motion
            <select
              value={settings.interp_model || ""}
              onChange={(e) => field("interp_model", e.target.value)}
            >
              <option value="">Preset default</option>
              {models
                .filter((m) => m.task === "interpolate" && m.weights_verified)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.catalog?.title || m.display_name}
                  </option>
                ))}
            </select>
          </label>
          {models.find((m) => m.id === settings.restore_model)?.architecture ===
            "drunet" && (
            <label>
              Cleanup strength
              <select
                value={settings.restore_strength || "medium"}
                onChange={(e) => field("restore_strength", e.target.value)}
              >
                <option value="light">Light</option>
                <option value="medium">Medium</option>
                <option value="strong">Strong</option>
              </select>
            </label>
          )}
          <label>
            Bigger picture
            <select
              value={settings.size_model || ""}
              disabled={!models.some(model => model.task === "size" && model.weights_verified)}
              onChange={(e) => field("size_model", e.target.value)}
            >
              <option value="">Standard resize</option>
              {models
                .filter((m) => m.task === "size" && m.weights_verified)
                .map((m) => (
                  <option value={m.id} key={m.id}>
                    {m.catalog?.title || m.display_name}
                  </option>
                ))}
            </select>
          </label>
        </details>
        <label className="check"><input type="checkbox" checked={!!settings.delete_original_after} onChange={event => field("delete_original_after", event.target.checked)} />Delete the original when it is done</label>
        {!models.some(model => model.task === "size" && model.weights_verified) && <p className="muted">More choices come later.</p>}
        <div className="estimate-list">
          {items.map((file) => (
            <div className="estimate-file" key={file}>
              <strong>{filename(file)}</strong>
              <ActionButton disabled={busy} onClick={() => setItems(old => old.filter(item => item !== file))}>Remove it</ActionButton>
              {loading && !previews[file] && <p role="status">Checking…</p>}
              {previews[file]?.error && <p className="error" role="alert">{previews[file].error}</p>}
              {previews[file] && !previews[file].error && (
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
                            {e.unknown_models?.length ? "Speed unknown" : `${duration(e.seconds)} of work (${duration(e.low)}–${duration(e.high)})`}
                          </p>
                          <p>Finish: {e.unknown_models?.length ? "Speed unknown" : when(e.finish)}</p>
                          {e.unknown_models?.map(model => <p className="warning-text" key={model}>Speed unknown for {model}. Run speed calibration.</p>)}
                          {!e.calibrated && !e.unknown_models?.length && (
                            <span className="badge warning">uncalibrated</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {previews[file].warnings.map((w) => (
                    <div className="warning-text" key={w}>
                      {w}
                      {w.includes("Insufficient") && <ActionButton onClick={async () => { const folder = (await window.desktop.files("folder"))[0]; if (folder) field("output_folder", folder); }}>Choose a folder…</ActionButton>}
                      {w.includes("too small for cleanup") && <ActionButton onClick={() => field("short_side", 1080)}>Use 1080</ActionButton>}
                      {w.includes("too small for AV1") && <ActionButton onClick={() => field("codec", "hevc")}>Use HEVC</ActionButton>}
                      {w.includes("smaller than the source") && <ActionButton onClick={() => field("short_side", "keep")}>Use Keep</ActionButton>}
                      {w.includes("HDR") && <ActionButton onClick={() => setItems(old => old.filter(item => item !== file))}>Remove it</ActionButton>}
                      {w.includes("Smart App Control") && <a href="https://github.com/Kei-Takamizawa/VideoEnhancer/blob/main/docs/TROUBLESHOOTING.md" target="_blank" rel="noreferrer">Read instructions</a>}
                    </div>
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
          <ActionButton disabled={busy} onClick={close}>
            Close
          </ActionButton>
          <ActionButton
            disabled={busy || !previews[items[0]]}
            onClick={() =>
              trial(items[0], settings, previews[items[0]]?.media, field)
            }
          >
            Try models first
          </ActionButton>
          <ActionButton
            className="primary add-submit"
            disabled={
              busy ||
              !addable.length ||
              !!error
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                for (const file of addable) {
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
          </ActionButton>
        </div>
      </div>
    </div>
  );
}
export async function localAction(job: Job, name: string) {
  if (name === "copy") await window.desktop.copy(JSON.stringify(job, null, 2));
  if (name === "folder") {
    if (job.output_state === "present") await window.desktop.reveal(job.output);
    else await window.desktop.openFolder(folder(job.output));
  }
}

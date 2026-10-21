import { Notice } from "./Notice";
import { hevcPlaybackSupported } from "./desktop";
import { ActionButton } from "./ActionButton";
import { LinkPanel } from "./LinkPanel";
import type { LinkSelection } from "./LinkPanel";
import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { duration, filename, folder, when } from "./api";
import type { Job, Model, Settings, Estimate, Media } from "./types";

type ValidPreview = {
  media: Media;
  presets: Record<string, Estimate>;
  warnings: string[];
  output: string;
  error?: never;
};
type Preview = ValidPreview | { error: string; media?: never; presets?: never; warnings?: never; output?: never };
export function AddDialog({
  api,
  files,
  initialUrl,
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
  initialUrl?: string;
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
  const [links, setLinks] = useState<LinkSelection[]>([]);
  const [settings, setSettings] = useState({ ...defaults });
  const [fileSettings, setFileSettings] = useState<Record<string, Partial<Settings>>>({});
  const [selectedSeconds, setSelectedSeconds] = useState<number>();
  const [selectedFinish, setSelectedFinish] = useState<string>();
  const fileSettingsRef = useRef(fileSettings); fileSettingsRef.current = fileSettings;
  const forFile = (file: string) => ({ ...settings, ...fileSettings[file] });
  const fileField = (file: string, key: keyof Settings, value: string | number | boolean) => setFileSettings(old => ({ ...old, [file]: { ...old[file], [key]: value } }));
  const added = useRef(new Set<string>());
  const [totals, setTotals] = useState<Record<string, Estimate>>({});
  const [previews, setPreviews] = useState<Record<string, Preview>>({});
  const validPreviews = Object.fromEntries(Object.entries(previews).filter(
    (entry): entry is [string, ValidPreview] => !!entry[1].media && !entry[1].error,
  ));
  const firstValid = items.find(file => validPreviews[file]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const [refresh, setRefresh] = useState(0);
  const timeKey = JSON.stringify([items, settings.preset, settings.short_side, settings.fps,
    settings.restore_model, settings.interp_model, settings.size_model, settings.restore_strength, settings.size_strength,
    Object.fromEntries(Object.entries(fileSettings).map(([file, value]) => [file,
      Object.fromEntries(Object.entries(value).filter(([key]) => !["codec", "output_folder", "delete_original_after"].includes(key)))]).filter(([, value]) => Object.keys(value).length))]);
  const spaceKey = JSON.stringify(fileSettings);
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
        const result = await api.call<{ files: Record<string, Preview>; presets: Record<string, Estimate>; selected_seconds?: number; selected_finish?: string }>("estimate", "POST", { files: items, settings: chosen, file_settings: fileSettingsRef.current, output_folder: chosen.output_folder }, request.signal);
        if (current) { setPreviews(result.files); setTotals(result.presets); setSelectedSeconds(result.selected_seconds); setSelectedFinish(result.selected_finish); setError(""); }
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
        const result = await api.call<{ files: Record<string, { warnings: string[]; output: string }> }>("estimate/space", "POST", { files: items, settings: settingsRef.current, file_settings: fileSettingsRef.current }, request.signal);
        setPreviews(old => Object.fromEntries(Object.entries(old).map(([file, preview]) => [file,
          result.files[file] && preview.media ? { ...preview, output: result.files[file].output, warnings: [...new Set([...preview.warnings.filter(w => !w.includes("Insufficient") && !w.includes("Output too small")), ...result.files[file].warnings])] } : preview])));
      } catch (error) { if (!request.signal.aborted) setError((error as Error).message); }
    }, 200);
    return () => { clearTimeout(timer); request.abort(); };
  }, [api, items, settings.output_folder, settings.codec, settings.short_side, settings.fps, spaceKey]);
  const addable = items.filter(file => validPreviews[file] && !validPreviews[file].warnings.some(w =>
    ["HDR", "Smart App Control", "Insufficient", "Output too small", "cannot read", "larger than 1080p"].some(reason => w.includes(reason))));
  const field = (key: keyof Settings, value: string | number | boolean) => {
    setSettings((old) => ({ ...old, [key]: value }));
    setFileSettings(old => Object.fromEntries(Object.entries(old).map(([file, item]) => [file, { ...item, [key]: value }])));
  };
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
          Add {items.length + links.length === 1 ? "video" : items.length + links.length ? `${items.length + links.length} videos` : "videos"}
        </h2>
        <LinkPanel api={api} settings={settings} initialUrl={initialUrl} changed={setLinks} />
        <ActionButton onClick={async () => { const paths = await window.desktop.files("videos"); setItems(old => [...new Set([...old, ...paths])]); }}>Choose video files…</ActionButton>
        <p className="muted">Apply to all</p>
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
                  ? "Cleans up compression and doubles the frame rate. Best quality, takes longer."
                  : "Doubles the frame rate without cleanup. Much quicker."}
              </p>
              <p>
                {totals[mode]
                  ? totals[mode].unknown_models?.length ? "Speed unknown" : `${duration(totals[mode].seconds)} of work`
                  : items.length ? "Preparing…" : ""}
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
              {firstValid
                ? (() => {
                    const [n, d = "1"] =
                      validPreviews[firstValid].media.cfr_fps.split("/");
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
                {[1080, 1440].map((n) => (
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
                <option value="hevc">{hevcPlaybackSupported() ? "HEVC" : "HEVC - Needs HEVC Video Extensions to play inside the app"}</option>
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
        {selectedSeconds !== undefined && <p>Total selected work: {duration(selectedSeconds)} · Done {when(selectedFinish)}</p>}
        <div className="estimate-list">
          {items.map((file) => (
            <div className="estimate-file" key={file}>
              <strong>{filename(file)}</strong>
              <div className="file-mode" aria-label={`Mode for ${filename(file)}`}>
                {["standard", "fast"].map(mode => <ActionButton key={mode} aria-pressed={forFile(file).preset === mode} onClick={() => fileField(file, "preset", mode)}>{mode === "standard" ? "Standard" : "Fast"}</ActionButton>)}
              </div>
              <details><summary>Settings</summary><div className="form-grid">
                <label>Output short side<select value={forFile(file).short_side} onChange={event => fileField(file, "short_side", event.target.value === "keep" ? "keep" : Number(event.target.value))}><option value="keep">Keep</option>{[1080,1440].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
                <label>Frame rate<select value={forFile(file).fps} onChange={event => fileField(file, "fps", event.target.value)}><option value="off">Keep</option><option value="2x">2×</option></select></label>
                <label>File format<select value={forFile(file).codec} onChange={event => fileField(file, "codec", event.target.value)}><option value="hevc">{hevcPlaybackSupported() ? "HEVC" : "HEVC - Needs HEVC Video Extensions to play inside the app"}</option><option value="h264">H.264</option><option value="av1" disabled={!av1}>AV1</option></select></label>
                {(["restore_model", "interp_model", "size_model"] as const).map((key, index) => <label key={key}>{["Cleanup", "Smoother motion", "Bigger picture"][index]}<select value={forFile(file)[key] || ""} onChange={event => fileField(file, key, event.target.value)}><option value="">Preset default</option>{models.filter(model => model.weights_verified && model.task === ["restore", "interpolate", "size"][index]).map(model => <option key={model.id} value={model.id}>{model.catalog?.title || model.display_name}</option>)}</select></label>)}
                {models.find(model => model.id === forFile(file).restore_model)?.architecture === "drunet" && <label>Cleanup strength<select value={forFile(file).restore_strength || "medium"} onChange={event => fileField(file, "restore_strength", event.target.value)}>{["light", "medium", "strong"].map(strength => <option key={strength} value={strength}>{strength}</option>)}</select></label>}
                <label className="check"><input type="checkbox" checked={!!forFile(file).delete_original_after} onChange={event => fileField(file, "delete_original_after", event.target.checked)} />Delete this original when it is done</label>
                <label>Output folder<input value={forFile(file).output_folder} onChange={event => fileField(file, "output_folder", event.target.value)} /></label>
              </div></details>

              <ActionButton disabled={busy} onClick={() => setItems(old => old.filter(item => item !== file))}>Remove it</ActionButton>
              {loading && !previews[file] && <p role="status">Checking…</p>}
              {previews[file]?.error && <Notice identity={previews[file].error!}>{previews[file].error}</Notice>}
              {validPreviews[file] && (
                <>
                  <div className="preset-estimates">
                    {["standard", "fast"].map((preset) => {
                      const e = validPreviews[file].presets[preset];
                      return (
                        <div key={preset} aria-current={forFile(file).preset === preset ? "true" : undefined}>
                          <strong>
                            {preset === "standard" ? "Standard" : "Fast"}
                          </strong>
                          <p>
                            {e.unknown_models?.length ? "Speed unknown" : `${duration(e.seconds)} of work (${duration(e.low)}–${duration(e.high)})`}
                          </p>
                          <p>Finish: {e.unknown_models?.length ? "Speed unknown" : when(e.finish)}</p>
                          {e.unknown_models?.map(model => <Notice className="warning-text" key={model} identity={model + timeKey}>Speed unknown for {model}. Run speed calibration.</Notice>)}
                          {!e.calibrated && !e.unknown_models?.length && (
                            <span className="badge warning">uncalibrated</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {validPreviews[file].warnings.some(w => w.includes("Insufficient")) && <ActionButton onClick={() => window.dispatchEvent(new Event("open-storage"))}>Open Storage settings</ActionButton>}
                  {validPreviews[file].warnings.map((w) => (
                    <Notice className="warning-text" key={w} identity={w + timeKey}>
                      {w}
                      {w.includes("Insufficient") && <ActionButton onClick={async () => { const folder = (await window.desktop.files("folder"))[0]; if (folder) fileField(file, "output_folder", folder); }}>Choose a folder…</ActionButton>}
                      {w.includes("too small for cleanup") && <ActionButton onClick={() => fileField(file, "short_side", 1080)}>Use 1080</ActionButton>}
                      {w.includes("too small for AV1") && <ActionButton onClick={() => fileField(file, "codec", "hevc")}>Use HEVC</ActionButton>}
                      {w.includes("HDR") && <ActionButton onClick={() => setItems(old => old.filter(item => item !== file))}>Remove it</ActionButton>}
                      {w.includes("Smart App Control") && <a href="https://github.com/Kei-Takamizawa/VideoEnhancer/blob/main/docs/TROUBLESHOOTING.md" target="_blank" rel="noreferrer">Read instructions</a>}
                    </Notice>
                  ))}
                </>
              )}
            </div>
          ))}
        </div>
        {error && (
          <Notice identity={error} dismiss={() => setError("")}>
            {error}
          </Notice>
        )}
        <div className="dialog-actions">
          <ActionButton disabled={busy} onClick={close}>
            Close
          </ActionButton>
          <ActionButton
            disabled={busy || !firstValid}
            onClick={() =>
              firstValid && trial(firstValid, forFile(firstValid), validPreviews[firstValid].media, (key, value) => fileField(firstValid, key, value))
            }
          >
            Try models first
          </ActionButton>
          <ActionButton
            className="primary add-submit"
            disabled={
              busy ||
              (!addable.length && !links.length) ||
              !!error
            }
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                if (links.some(link => !link.reuse_job_id)) {
                  const preferences = await api.call<Settings>("settings");
                  if (!preferences.video_download_folder) {
                    const folder = (await window.desktop.files("folder"))[0];
                    if (!folder) { setBusy(false); return; }
                    await api.call("settings", "PUT", { video_download_folder: folder });
                  }
                }
                for (const link of links) {
                  const key = `link:${link.check_id}:${link.entry_key}`;
                  if (added.current.has(key)) continue;
                  await api.call("links/queue", "POST", { ...link, settings, output_folder: settings.output_folder });
                  added.current.add(key);
                }
                for (const file of addable) {
                  if (added.current.has(file)) continue;
                  await api.call("queue", "POST", {
                    file,
                    settings: {
                      ...forFile(file),
                      restore_model: forFile(file).restore_model || undefined,
                    },
                    output_folder: forFile(file).output_folder,
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

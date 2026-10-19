import { useEffect, useState } from "react";
import type { Api } from "./api";
import { duration } from "./api";
import type { Estimate, Settings } from "./types";
import { ActionButton } from "./ActionButton";
import { Notice } from "./Notice";
import { VideoLinksCard } from "./VideoLinks";

type Format = { id: string; width?: number; height?: number; fps?: number; codec: string; dynamic_range: string; bytes?: number; disabled?: string; unknown_size?: boolean; estimate?: Estimate };
type Entry = { key: string; title: string; site?: string; uploader?: string; duration?: number; thumbnail?: boolean; selected?: string; formats?: Format[]; error?: string; reuse?: { job_id: string; date: string; media?: { display_width?: number; display_height?: number; width?: number; height?: number; cfr_fps?: string } } };
type Checked = { entries: Entry[]; truncated?: boolean };
type CheckOperation = { id: string; state: string; phase: string; error?: string; result?: Checked };
export type LinkSelection = { check_id: string; entry_key: string; format_id: string; reuse_job_id?: string };
const unknown = "VideoEnhancer can't read this video's size before downloading. It is checked after the download. If it is larger than 1080p or HDR, the job stops and the downloaded file is kept.";

function frameRate(value?: string) {
  const [n, d = "1"] = (value || "").split("/");
  const rate = Number(n) / Number(d);
  return rate > 0 ? Number(rate.toFixed(3)).toString() : "?";
}

function LinkThumbnail({ api, path }: { api: Api; path: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let active = true, object = "";
    void api.blob(path).then(blob => { object = URL.createObjectURL(blob); if (active) setUrl(object); else URL.revokeObjectURL(object); }).catch(() => {});
    return () => { active = false; if (object) URL.revokeObjectURL(object); };
  }, [api, path]);
  return url ? <img className="thumbnail" src={url} alt="" /> : null;
}

export function LinkPanel({ api, settings, initialUrl = "", changed }: { api: Api; settings: Settings; initialUrl?: string; changed(value: LinkSelection[]): void }) {
  const [url, setUrl] = useState(initialUrl);
  const [available, setAvailable] = useState<boolean>();
  const [operation, setOperation] = useState<CheckOperation>();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [formats, setFormats] = useState<Record<string, string>>({});
  const [reuse, setReuse] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [estimates, setEstimates] = useState<Record<string, Record<string, Estimate | null>>>({});
  useEffect(() => { let active = true; void api.call<{ available: boolean }>("link-tools").then(value => { if (active) setAvailable(value.available); }).catch(error => { if (active) setError(error.message); }); return () => { active = false; }; }, [api]);
  useEffect(() => {
    changed(entries.filter(entry => selected[entry.key] && !entry.error && formats[entry.key]).map(entry => ({ check_id: operation!.id, entry_key: entry.key, format_id: formats[entry.key], reuse_job_id: reuse[entry.key] ? entry.reuse?.job_id : undefined })));
  }, [entries, selected, formats, reuse, operation?.id, changed]);
  useEffect(() => {
    if (!operation) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const value = await api.call<CheckOperation>(`operations/${operation.id}`);
        if (!active) return;
        setOperation(value);
        if (value.state === "running") timer = setTimeout(poll, 500);
        else {
          setBusy(false);
          if (value.state === "done" && value.result) {
            setEntries(value.result.entries);
            setSelected(Object.fromEntries(value.result.entries.map(entry => [entry.key, !entry.error])));
            setFormats(Object.fromEntries(value.result.entries.map(entry => [entry.key, entry.selected || ""])));
          } else if (value.error) setError(value.error);
        }
      } catch (error) { if (active) { setError((error as Error).message); setBusy(false); } }
    };
    timer = setTimeout(poll, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [api, operation?.id]);
  useEffect(() => {
    if (!entries.length || !operation) return;
    let active = true;
    const timer = setTimeout(() => {
      void Promise.all(entries.filter(entry => formats[entry.key]).map(async entry => {
        const value = await api.call<{ estimate: Estimate | null; formats?: Record<string, Estimate | null> }>("links/estimate", "POST", { check_id: operation.id, entry_key: entry.key, format_id: formats[entry.key], settings, all_formats: true });
        return [entry.key, value.formats || { [formats[entry.key]]: value.estimate }] as const;
      })).then(values => { if (active) setEstimates(Object.fromEntries(values)); }).catch(error => { if (active) setError(error.message); });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [api, entries, formats, settings, operation?.id]);
  return <section aria-label="Video link">
    <label>Paste a video link<input type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" /></label>
    {available === false ? <VideoLinksCard api={api} compact installed={() => setAvailable(true)} /> : <ActionButton disabled={!available || busy || !url.trim()} onClick={async () => {
      setBusy(true); setError(""); setEntries([]); setSelected({}); setReuse({});
      try { setOperation(await api.call<CheckOperation>("links/check", "POST", { url: url.trim(), settings })); }
      catch (error) { setError((error as Error).message); setBusy(false); }
    }}>Check</ActionButton>}
    {busy && <p role="status">{operation?.phase || "Checking link"} <ActionButton disabled={!operation || operation.state !== "running"} onClick={() => api.call(`operations/${operation!.id}/cancel`, "POST")}>Cancel</ActionButton></p>}
    {error && <Notice identity={error} dismiss={() => setError("")}>{error}</Notice>}
    {operation?.result?.truncated && <p>The first 200 videos are shown.</p>}
    {entries.length > 1 && <div className="toolbar"><ActionButton onClick={() => setSelected(Object.fromEntries(entries.map(entry => [entry.key, !entry.error])))}>Select all</ActionButton><ActionButton onClick={() => setSelected({})}>Select none</ActionButton></div>}
    {entries.map(entry => {
      const format = entry.formats?.find(format => format.id === formats[entry.key]);
      const estimate = estimates[entry.key]?.[format?.id || ""] ?? format?.estimate;
      return <article className="card" key={entry.key}>
        {entry.thumbnail && operation && <LinkThumbnail api={api} path={`links/${operation.id}/thumbnail/${entry.key}`} />}
        <label className="check"><input type="checkbox" disabled={!!entry.error} checked={!!selected[entry.key]} onChange={event => setSelected(old => ({ ...old, [entry.key]: event.target.checked }))} />{entry.title}</label>
        <p>{entry.site} · {entry.uploader} {entry.duration ? `· ${duration(entry.duration)}` : ""}</p>
        {entry.error ? <p role="status">{entry.error}</p> : <>
          <label>Quality<select value={formats[entry.key] || ""} onChange={event => setFormats(old => ({ ...old, [entry.key]: event.target.value }))}>{entry.formats?.map(format => <option key={format.id} value={format.id} disabled={!!format.disabled}>{format.width && format.height ? `${format.width} × ${format.height}` : "Size checked after download"} · {format.fps || "?"} fps · {format.codec} · {format.dynamic_range}{format.bytes ? ` · ${(format.bytes / 1e6).toFixed(1)} MB` : " · Size unknown"} · {(estimates[entry.key]?.[format.id] || format.estimate) ? duration((estimates[entry.key]?.[format.id] || format.estimate)!.seconds) : "after download"}{format.disabled ? ` — ${format.disabled}` : ""}</option>)}</select></label>
          {format?.unknown_size && <p>{unknown}</p>}
          <p>{format?.bytes ? `Download about ${(format.bytes / 1e6).toFixed(1)} MB` : "Download size reported during transfer"}</p>
          <p>{estimate ? `Processing about ${duration(estimate.seconds)}${estimate.unknown_models?.length ? " · Speed unknown" : ""}` : "Processing: after download"}</p>
          {entry.reuse && <><label className="check"><input type="checkbox" checked={!!reuse[entry.key]} onChange={event => setReuse(old => ({ ...old, [entry.key]: event.target.checked }))} />Use the file downloaded on {entry.reuse.date?.slice(0, 10)} ({entry.reuse.media?.display_width || entry.reuse.media?.width}x{entry.reuse.media?.display_height || entry.reuse.media?.height}, {frameRate(entry.reuse.media?.cfr_fps)} fps)</label><ActionButton onClick={() => setReuse(old => ({ ...old, [entry.key]: false }))}>Download again</ActionButton></>}
        </>}
      </article>;
    })}
  </section>;
}

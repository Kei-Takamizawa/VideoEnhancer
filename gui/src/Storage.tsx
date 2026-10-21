import { useCallback, useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { ActionButton } from "./ActionButton";
import { Notice } from "./Notice";

type Storage = { folder: string; total_bytes: number; models_bytes: number; working_bytes: number;
  history_bytes: number; free_bytes: number; cleanup: { id: string; name?: string; date?: string; state: string; bytes: number }[] };
type Move = { phase?: string; previous?: string; copied_bytes?: number; total_bytes?: number; disabled?: boolean; can_remove?: boolean; busy?: boolean; remove_reason?: string; damaged?: Record<string,number> };
const gb = (bytes: number) => `${(bytes / 1e9).toFixed(2)} GB`;
export function StorageCard({ api, automatic, change }: { api: Api; automatic: boolean; change(value: boolean): void }) {
  const [data, setData] = useState<Storage>();
  const [move, setMove] = useState<Move>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  async function refresh() { const value = await api.call<Storage>("storage"); if (!value.folder || !Array.isArray(value.cleanup)) throw new Error("Storage information is unavailable. Retry shortly."); setData(value); }
  useEffect(() => { let mounted = true; void api.call<Storage>("storage").then(value => { if (!value.folder || !Array.isArray(value.cleanup)) throw new Error("Storage information is unavailable. Retry shortly."); if (mounted) setData(value); }).catch(e => { if (mounted) setError(e.message); });
    return () => { mounted = false; }; }, [api]);
  const pending = useRef<Promise<unknown>>(Promise.resolve());
  const readMove = useCallback((verify = false): Promise<Move> => {
    const next = pending.current.catch(() => {}).then(() => window.desktop.storageStatus!(verify));
    pending.current = next;
    return next;
  }, []);
  useEffect(() => {
    if (!window.desktop.storageStatus) return;
    let mounted = true, first = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const verify = first; first = false;
      try { const value = await readMove(verify); if (mounted) setMove(value); }
      catch (e) { if (mounted) setError((e as Error).message); }
      finally { if (mounted) timer = setTimeout(() => { void poll(); }, 500); }
    };
    void poll();
    return () => { mounted = false; clearTimeout(timer); };
  }, [api, readMove]);
  async function relocate() {
    setBusy(true); setError(""); setResult("");
    try {
      const folder = (await window.desktop.files("folder"))[0]; if (!folder) return;
      await window.desktop.moveStorage!(folder);
      setResult("Move completed. The app is using the new folder.");
      // Recreate the API client and event stream with the restarted service's token.
      window.dispatchEvent(new Event("storage-moved"));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <article className="card storage-card" id="storage">
    <h2>Storage</h2>
    {error && <Notice identity={error} dismiss={() => setError("")}>{error}</Notice>}
    {data && <><p className="break">App data folder: {data.folder}</p>
      <dl><dt>Models</dt><dd>{gb(data.models_bytes)}</dd><dt>Working files of unfinished jobs</dt><dd>{gb(data.working_bytes)}</dd><dt>History and logs</dt><dd>{gb(data.history_bytes)}</dd></dl>
      <p>{gb(data.total_bytes)} in use · {gb(data.free_bytes)} free on the app data drive</p></>}
    <div role="status" className="break">{result || (busy ? move.phase || "Starting move…" : move.phase === "Move completed" ? "Move completed. The app is using the new folder." : "")}
      {busy && move.total_bytes ? <><progress max={move.total_bytes} value={move.copied_bytes || 0} />{gb(move.copied_bytes || 0)} / {gb(move.total_bytes)}</> : null}</div>
    {move.damaged && Object.keys(move.damaged).length>0 && <p>{Object.values(move.damaged).reduce((sum,n)=>sum+n,0)} damaged records copied unchanged: {Object.entries(move.damaged).map(([file,n])=>`${file} (${n})`).join(", ")}</p>}
    {move.disabled && <p>App data is set by VE_HOME. Unset it to use Move.</p>}
    <ActionButton disabled={busy || move.busy || move.disabled || !window.desktop.moveStorage} onClick={relocate}>Move…</ActionButton>
    {move.previous && move.remove_reason && <p>{move.remove_reason}</p>}
    {move.previous && <><p className="break">Old folder kept: {move.previous}</p><ActionButton className="danger" disabled={busy || move.busy || move.disabled || !move.can_remove} onClick={async () => { setBusy(true); setError(""); setResult(""); try { const value = await window.desktop.removeOldStorage!() as {cancelled?: boolean; message?: string}; if (!value.cancelled) setResult(value.message || "Old-folder removal finished."); setMove(await readMove()); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }}>Remove the old folder</ActionButton></>}
    <h3>Clean up working files</h3>
    <p>Failed and cancelled jobs stay in History. Retry starts from the beginning after cleanup.</p>
    <label className="check"><input type="checkbox" checked={automatic} onChange={event => change(event.target.checked)} />Automatically clean up 7 days after failure or cancellation</label>
    {data?.cleanup.length ? <ul>{data.cleanup.map(job => <li key={job.id} title={job.id}>{job.name || "Video"} · {job.state} · {job.date ? new Date(job.date).toLocaleDateString() : "Date unavailable"} · {gb(job.bytes)} <ActionButton disabled={busy} onClick={async () => { try { await api.call("storage/cleanup", "POST", { ids: [job.id] }); await refresh(); } catch (e) { setError((e as Error).message); } }}>Clean up</ActionButton></li>)}</ul> : <p>No failed or cancelled working files to clean up.</p>}
  </article>;
}

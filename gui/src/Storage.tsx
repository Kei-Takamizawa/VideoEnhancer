import { useEffect, useState } from "react";
import type { Api } from "./api";
import { ActionButton } from "./ActionButton";
import { Notice } from "./Notice";

type Storage = { folder: string; total_bytes: number; models_bytes: number; working_bytes: number;
  history_bytes: number; free_bytes: number; cleanup: { id: string; state: string; bytes: number }[] };
type Move = { phase?: string; previous?: string; copied_bytes?: number; total_bytes?: number };
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
  useEffect(() => {
    if (!window.desktop.storageStatus) return;
    const poll = () => { void window.desktop.storageStatus!().then(setMove).catch(e => setError(e.message)); };
    poll(); const timer = setInterval(poll, 500); return () => clearInterval(timer);
  }, []);
  async function relocate() {
    try {
      const folder = (await window.desktop.files("folder"))[0]; if (!folder) return;
      setBusy(true); setError(""); setResult("");
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
    <div role="status">{result || (busy ? move.phase || "Starting move…" : move.phase === "Move completed" ? "Move completed. The app is using the new folder." : "")}
      {busy && move.total_bytes ? <><progress max={move.total_bytes} value={move.copied_bytes || 0} />{gb(move.copied_bytes || 0)} / {gb(move.total_bytes)}</> : null}</div>
    <ActionButton disabled={busy || !window.desktop.moveStorage} onClick={relocate}>Move…</ActionButton>
    {move.previous && <><p className="break">Old folder kept: {move.previous}</p><ActionButton className="danger" disabled={busy} onClick={async () => { try { await window.desktop.removeOldStorage!(); setMove(old => ({ ...old, previous: undefined })); setResult("The old folder was permanently removed."); } catch (e) { setError((e as Error).message); } }}>Remove the old folder</ActionButton></>}
    <h3>Clean up working files</h3>
    <p>Failed and cancelled jobs stay in History. Retry starts from the beginning after cleanup.</p>
    <label className="check"><input type="checkbox" checked={automatic} onChange={event => change(event.target.checked)} />Automatically clean up 7 days after failure or cancellation</label>
    {data?.cleanup.length ? <ul>{data.cleanup.map(job => <li key={job.id}>{job.id} · {job.state} · {gb(job.bytes)} <ActionButton disabled={busy} onClick={async () => { try { await api.call("storage/cleanup", "POST", { ids: [job.id] }); await refresh(); } catch (e) { setError((e as Error).message); } }}>Clean up</ActionButton></li>)}</ul> : <p>No failed or cancelled working files to clean up.</p>}
  </article>;
}

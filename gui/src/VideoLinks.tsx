import { useEffect, useState } from "react";
import type { Api } from "./api";
import type { Operation } from "./types";
import { ActionButton } from "./ActionButton";
import { Notice } from "./Notice";
import { OperationStatus } from "./Pages";

type Tool = { tool: string; version: string; released: string; bytes: number; licence: string; present?: boolean };
type Plan = { id: string; channel: string; tools: Tool[]; notice: string };
type Status = { installed: Record<string, Tool>; available: boolean; notice: string };
type ToolsOperation = Omit<Operation, "result"> & { result?: Plan | Status };

export function VideoLinksCard({ api, compact = false, installed }: { api: Api; compact?: boolean; installed?(): void }) {
  const [status, setStatus] = useState<Status>();
  const [channel, setChannel] = useState("stable");
  const [plan, setPlan] = useState<Plan>();
  const [operation, setOperation] = useState<ToolsOperation>();
  const [consent, setConsent] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [folder, setFolder] = useState("");
  const [limit, setLimit] = useState(2);
  useEffect(() => {
    if (compact) return;
    let active = true;
    void api.call<{ video_download_folder?: string; video_download_limit?: number }>("settings").then(value => { if (active) { setFolder(value.video_download_folder || ""); setLimit(value.video_download_limit || 2); } }).catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [api, compact]);
  useEffect(() => {
    let active = true;
    void api.call<Status>("link-tools").then(value => { if (active) setStatus(value); }).catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [api]);
  useEffect(() => {
    if (!operation) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api.call<ToolsOperation>(`operations/${operation.id}`);
        if (!active) return;
        setOperation(next);
        if (next.state === "running") timer = setTimeout(poll, 500);
        else {
          setBusy(false);
          if (next.state === "done" && next.result && "tools" in next.result) { setPlan(next.result); setDialog(true); setConsent(false); }
          if (next.state === "done" && next.result && "installed" in next.result) { setStatus(next.result); setPlan(undefined); setDialog(false); if (next.result.available) installed?.(); }
          if (next.state === "failed") setError(next.error || "Link-tool operation failed.");
          if (["failed", "cancelled"].includes(next.state)) {
            const current = await api.call<Status>("link-tools");
            if (active) setStatus(current);
          }
        }
      } catch (error) { if (active) { setError((error as Error).message); setBusy(false); } }
    };
    timer = setTimeout(poll, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [api, operation?.id]);
  const start = async (action: string) => {
    setBusy(true); setError("");
    if (action === "install") setDialog(false);
    try { setOperation(await api.call<ToolsOperation>(`link-tools/${action}`, "POST", { channel, plan_id: plan?.id, consent })); }
    catch (error) { setError((error as Error).message); setBusy(false); }
  };
  const changed = plan?.tools.some(tool => !status?.installed[tool.tool]?.present || status.installed[tool.tool].version !== tool.version);
  return <article className="card">
    {!compact && <h2>Video links</h2>}
    <p>Optional tools download videos from links. Checks and updates run only when you request them.</p>
    {Object.values(status?.installed || {}).map(tool => <p key={tool.tool}>{tool.tool} {tool.version} · Released {tool.released.slice(0, 10)}{!tool.present && " · Reinstall needed"}</p>)}
    {!compact && <><label>Download folder<input value={folder} onChange={event => setFolder(event.target.value)} onBlur={() => { void api.call("settings", "PUT", { video_download_folder: folder }).catch(error => setError(error.message)); }} /></label><ActionButton onClick={async () => { const chosen = (await window.desktop.files("folder"))[0]; if (chosen) { await api.call("settings", "PUT", { video_download_folder: chosen }); setFolder(chosen); } }}>Choose download folder…</ActionButton><label>Simultaneous downloads<select value={limit} onChange={event => { const value = Number(event.target.value); setLimit(value); void api.call("settings", "PUT", { video_download_limit: value }).catch(error => setError(error.message)); }}>{[1, 2, 3].map(value => <option key={value}>{value}</option>)}</select></label></>}
    {!compact && <label>Update channel<select disabled={busy} value={channel} onChange={event => { setChannel(event.target.value); setPlan(undefined); }}><option value="stable">Stable</option><option value="nightly">Nightly</option></select></label>}
    <div className="toolbar">
      <ActionButton disabled={busy || !status} onClick={() => void start("check")}>{status?.available ? "Check for updates" : "Install link tools"}</ActionButton>
      {!compact && Object.keys(status?.installed || {}).length > 0 && <ActionButton disabled={busy} onClick={() => void start("uninstall")}>Uninstall link tools</ActionButton>}
    </div>
    {error && <Notice role="alert" identity={error} dismiss={() => setError("")}>{error}</Notice>}
    {operation && <OperationStatus operation={operation as Operation} cancel={operation.state === "running" ? () => { void api.call(`operations/${operation.id}/cancel`, "POST").catch(error => setError(error.message)); } : undefined} />}
    {dialog && plan && <div className="modal-shade"><section className="dialog" role="dialog" aria-modal="true" aria-label="Install link tools">
      <h2>{status?.available ? "Update link tools" : "Install link tools"}</h2>
      {plan.tools.map(tool => <p key={tool.tool}>{tool.tool} {tool.version} · {(tool.bytes / 1e6).toFixed(1)} MB · {tool.licence}</p>)}
      <p>{plan.notice}</p>
      {!changed && <p>Link tools are up to date.</p>}
      <label className="check"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />I have read the licences and download notice</label>
      <div className="toolbar"><ActionButton disabled={busy} onClick={() => setDialog(false)}>Cancel</ActionButton><ActionButton disabled={busy || !consent || !changed} onClick={() => void start("install")}>{status?.available ? "Update" : "Install"}</ActionButton></div>
    </section></div>}
  </article>;
}

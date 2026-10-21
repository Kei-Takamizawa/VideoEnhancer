import { Notice } from "./Notice";
import { ErrorBoundary } from "./ErrorBoundary";
import { Tour } from "./Tour";
import { UndoToast } from "./UndoToast";
import { HistoryRemoval } from "./HistoryRemoval";
import { ActionButton } from "./ActionButton";
import { useCallback, useEffect, useRef, useState } from "react";
import { client, events, filename } from "./api";
import type { Api } from "./api";
import type {
  Health,
  Job,
  Media,
  Model,
  Operation,
  Plan,
  Queue,
  Progress,
  Schedule,
  Settings,
} from "./types";
import { AddDialog, localAction } from "./Queue";
import { HomePage, HistoryPage, Icon, problemWhen } from "./Home";
import { ScheduleView } from "./ScheduleView";
import { ModelsPage, OperationStatus, SettingsPage } from "./Pages";
import { Compare, TrialDialog } from "./Trial";
import { useDialogFocus } from "./focus";

const empty: Queue = { jobs: [], operations: [], completion: null };
export function ConnectionBanner({
  error,
  retry,
}: {
  error: string;
  retry(): void;
}) {
  return error ? (
    <Notice className="error connection" identity={error}>
      <h2>Can’t reach the engine</h2><p>{error}</p> <ActionButton onClick={retry}>Retry</ActionButton>
      <ActionButton onClick={() => window.desktop.copy(error)}>Copy details</ActionButton><p>Your last known data remains visible.</p>
    </Notice>
  ) : null;
}
export function ControlWarning({
  health,
  retry,
}: {
  health?: Health;
  retry(): void;
}) {
  return health?.smart_app_control.blocked ? (
    <Notice identity={health.smart_app_control.message || "Windows blocked video processing"}>
      <h2>Windows is blocking a required video component</h2>
      <p>
        Smart App Control prevented the engine from running. Processing cannot
        continue until the component is permitted.
      </p>
      <p>{health.smart_app_control.message}</p>
      <a
        target="_blank"
        rel="noreferrer"
        href="https://github.com/Kei-Takamizawa/VideoEnhancer/blob/main/docs/TROUBLESHOOTING.md"
      >
        Read troubleshooting instructions
      </a>{" "}
      <ActionButton onClick={retry}>Retry</ActionButton>
    </Notice>
  ) : null;
}
export default function App() {
  useDialogFocus();
  const [page, setPage] = useState(sessionStorage.getItem("storage-return") ? "Settings" : "Home");
  useEffect(() => {
    const storage = () => { setFiles(undefined); setPage("Settings"); };
    const moved = () => { sessionStorage.setItem("storage-return", "1"); void window.desktop.reload?.(); };
    window.addEventListener("open-storage", storage);
    window.addEventListener("storage-moved", moved);
    return () => { window.removeEventListener("open-storage", storage); window.removeEventListener("storage-moved", moved); };
  }, []);
  const [dropCount, setDropCount] = useState(0);
  const [dropNotice, setDropNotice] = useState("");
  useEffect(() => { if (!dropNotice) return; const timer = setTimeout(() => setDropNotice(""), 3000); return () => clearTimeout(timer); }, [dropNotice]);
  const [api, setApi] = useState<Api>();
  const [error, setError] = useState("");
  const [reconnecting, setReconnecting] = useState(false);
  const [engineStalled, setEngineStalled] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(Date.now());
  const [actionError, setActionError] = useState("");
  useEffect(() => {
    const error = (event: Event) => setActionError((event as CustomEvent<string>).detail);
    window.addEventListener("desktop-error", error);
    return () => window.removeEventListener("desktop-error", error);
  }, []);
  const [zoomToast, setZoomToast] = useState<number>();
  useEffect(() => window.desktop.onZoom((zoom) => {
    setZoomToast(zoom);
    setSettings((previous) => previous ? { ...previous, zoom } : previous);
  }), []);
  useEffect(() => {
    if (zoomToast === undefined) return;
    const timer = setTimeout(() => setZoomToast(undefined), 3000);
    return () => clearTimeout(timer);
  }, [zoomToast]);
  useEffect(() => {
    const switchScreen = (event: KeyboardEvent) => {
      if (!event.ctrlKey || event.altKey || event.metaKey) return;
      const screen = ["Home", "History", "Schedule", "Models", "Settings"][Number(event.key) - 1];
      if (screen) {
        event.preventDefault();
        setPage(screen);
      }
    };
    window.addEventListener("keydown", switchScreen);
    return () => window.removeEventListener("keydown", switchScreen);
  }, []);
  const [queue, setQueue] = useState(empty);
  const [health, setHealth] = useState<Health>();
  const [plan, setPlan] = useState<Plan>();
  const scenario = "expected";
  const [settings, setSettings] = useState<Settings>();
  const [tour, setTour] = useState(false);
  const tourChecked = useRef(false);
  useEffect(() => { if (settings && !tourChecked.current) { tourChecked.current = true; if (settings.tour_completed === false) setTour(true); } }, [settings]);
  const seenPending = useRef(new Set<string>());
  const markSeen = useCallback(
    (ids: string[]) => {
      if (
        !api ||
        !settings ||
        !ids.some(
          (id) =>
            !settings.seen_failures?.includes(id) &&
            !seenPending.current.has(id),
        )
      )
        return;
      ids.forEach((id) => seenPending.current.add(id));
      const seen = Array.from(
        new Set([...(settings.seen_failures || []), ...seenPending.current]),
      );
      void api
        .call("settings", "PUT", { seen_failures: seen })
        .then(() =>
          setSettings((previous) =>
            previous
              ? {
                  ...previous,
                  seen_failures: Array.from(
                    new Set([...(previous.seen_failures || []), ...seen]),
                  ),
                }
              : previous,
          ),
        )
        .catch((error) => {
          ids.forEach((id) => seenPending.current.delete(id));
          setActionError(error.message);
        });
    },
    [api, settings],
  );
  const [schedule, setSchedule] = useState<Schedule>();
  const [models, setModels] = useState<Model[]>([]);
  const [generation, setGeneration] = useState(0);
  const [files, setFiles] = useState<string[]>();
  const [linkUrl, setLinkUrl] = useState("");
  useEffect(() => {
    const paste = (event: ClipboardEvent) => {
      if (page !== "Home" || document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      if (event.target instanceof Element && event.target.closest("input,textarea,[contenteditable=true]")) return;
      const value = event.clipboardData?.getData("text/plain").trim() || "";
      if (!/^https?:\/\//i.test(value)) return;
      event.preventDefault(); setLinkUrl(value); setFiles([]);
    };
    document.addEventListener("paste", paste);
    return () => document.removeEventListener("paste", paste);
  }, [page]);
  const [trial, setTrial] = useState<{
    file: string;
    settings: Settings;
    media?: Media;
    job_id?: string;
    apply?: (key: "restore_model" | "interp_model" | "size_model" | "preset", id: string) => void;
  }>();
  const [confirm, setConfirm] = useState<{ job: Job; name: string }>();
  const [trayExplanation, setTrayExplanation] = useState(false);
  useEffect(() => window.desktop.onTrayExplanation(() => setTrayExplanation(true)), []);
  const [historyUndo, setHistoryUndo] = useState<string[]>();
  const [historyUndoRevision, setHistoryUndoRevision] = useState("");
  useEffect(() => {
    if (!api || !sessionStorage.getItem("storage-return")) return;
    sessionStorage.removeItem("storage-return");
    void api.call<{ storage_undo_ids?: string[] }>("health").then(value => {
      if (value.storage_undo_ids?.length) {
        setHistoryUndo(value.storage_undo_ids);
        void api.call("history/pause-undo", "POST", { ids: value.storage_undo_ids, paused: false });
      }
    });
  }, [api]);
  const historyRemovalSeen = useRef(new Map<string, string>());
  useEffect(() => {
    for (const op of queue.operations.filter(op => op.kind === "history-removal")) {
      const signature = JSON.stringify([op.state, op.result?.ids, op.result?.files]);
      if (historyRemovalSeen.current.get(op.id) === signature) continue;
      historyRemovalSeen.current.set(op.id, signature);
      const ids = op.result?.ids || [];
      const recent = op.state === "running" || Date.now() - Date.parse(op.completed_at || op.created_at || "") < 10000;
      if (ids.length && recent) {
        setHistoryUndo(ids);
        setHistoryUndoRevision(op.completed_at || op.id);
        setFilesMoved((op.result?.files?.moved || 0) > 0);
      }
      if (op.state === "failed") setActionError(op.error || "File removal failed.");
      else if (op.state === "done" && recent && op.result?.files) {
        const files = op.result.files;
        setActionError(`${files.moved} moved, ${files.not_found} not found, ${files.kept} kept. ${(op.result.kept || []).map(item => item.reason).join(" ")}`);
      }
    }
  }, [queue.operations]);
  const [historyRemoval, setHistoryRemoval] = useState<Job[]>();
  const [historyFiles, setHistoryFiles] = useState<Job[]>();
  const [filesMoved, setFilesMoved] = useState(false);
  const [log, setLog] = useState<string>();
  const [resultPreview, setResultPreview] = useState<string>();
  const resultOperation = queue.operations.find(
    (op) => op.id === resultPreview,
  );
  const showPreview = async (job: Job) => {
    try {
      const op = await api!.call<Operation>(
        `queue/${job.id}/preview`,
        "POST",
        {},
      );
      setResultPreview(op.id);
    } catch (error) {
      setActionError((error as Error).message);
    }
  };
  const modelVersion = queue.operations
    .filter((o) => ["download", "verify"].includes(o.kind))
    .map((o) => `${o.id}:${o.state}`)
    .join(",");
  useEffect(() => {
    if (api && modelVersion)
      void api
        .call<Model[]>("models")
        .then(setModels)
        .catch((e) => setActionError(e.message));
  }, [api, modelVersion]);
  const refresh = useCallback(
    async (connection = api) => {
      if (!connection) return;
      const [prefs, hours, registry] = await Promise.all([
        connection.call<Settings>("settings"),
        connection.call<Schedule>("schedule"),
        connection.call<Model[]>("models"),
      ]);
      setSettings(prefs);
      setSchedule(hours);
      setModels(registry);
    },
    [api],
  );
  useEffect(() => {
    const abort = new AbortController();
    let alive = true;
    let lastProgressPaint = -Infinity;
    let progressTimer: ReturnType<typeof setTimeout> | undefined;
    let pendingProgress: Progress[] = [];
    const flushProgress = () => {
      if (!alive) return;
      lastProgressPaint = performance.now();
      progressTimer = undefined;
      const packet = pendingProgress;
      pendingProgress = [];
      setQueue(previous => ({ ...previous, jobs: previous.jobs.map(job => {
        const update = packet.find(value => value.id === job.id);
        if (!update || job.state !== "running") return job;
        const low = job.estimate.seconds > 0 ? job.estimate.low / job.estimate.seconds : 0.75;
        const high = job.estimate.seconds > 0 ? job.estimate.high / job.estimate.seconds : 1.25;
        return { ...job, progress_percent: update.percent, eta: update.finish_time, fps: update.fps, phase: update.phase, step: update.step, estimate: { ...job.estimate, seconds: update.work_left, low: update.work_left * low, high: update.work_left * high } };
      }) }));
    };
    const receiveProgress = (packet: Progress[]) => {
      pendingProgress = packet;
      if (progressTimer !== undefined) return;
      const wait = Math.max(0, 1000 - (performance.now() - lastProgressPaint));
      if (wait === 0) flushProgress();
      else progressTimer = setTimeout(flushProgress, wait);
    };
    window.desktop
      .connection()
      .then(async (connection) => {
        if (!alive) return;
        let next = client(connection);
        setApi(next);
        await refresh(next);
        if (!alive) return;
        setError("");
        await events(
          connection,
          abort.signal,
          (raw) => {
            if ("progress" in (raw as Record<string, unknown>)) {
              setLastUpdate(Date.now());
              receiveProgress((raw as { progress: Progress[] }).progress);
              return;
            }
            const snapshot = raw as {
              queue: Queue;
              health: Health;
              plan: Plan;
            };
            setLastUpdate(Date.now());
            setQueue(previous => ({ ...snapshot.queue, jobs: snapshot.queue.jobs.map(job => {
              const old = previous.jobs.find(record => record.id === job.id);
              return job.state === "running" && old?.state === "running" ? { ...job, progress_percent: old.progress_percent, estimate: old.estimate, eta: old.eta, fps: old.fps } : job;
            }) }));
            receiveProgress(snapshot.queue.jobs.filter(job => job.state === "running").map(job => ({ id: job.id, percent: job.progress_percent, work_left: job.estimate.seconds, finish_time: job.eta || "", fps: job.fps, phase: job.phase, step: job.step })));
            setHealth(snapshot.health);
            if (scenario === "expected") setPlan(snapshot.plan);
            else
              void next
                .call<Plan>(`plan?scenario=${scenario}`)
                .then(setPlan)
                .catch((e) => setError(e.message));
          },
          setReconnecting,
          async () => {
            const restored = await window.desktop.connection();
            next = client(restored);
            if (alive) setApi(next);
            return restored;
          },
          setEngineStalled,
        );
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
      if (progressTimer !== undefined) clearTimeout(progressTimer);
      abort.abort();
    };
    // Reconnection has an explicit lifetime; preference reads are not stream dependencies.
  }, [generation, scenario]);
  useEffect(() => {
    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () =>
      (document.documentElement.dataset.theme =
        settings?.theme === "system"
          ? dark.matches
            ? "dark"
            : "light"
          : settings?.theme || "dark");
    apply();
    dark.addEventListener("change", apply);
    return () => dark.removeEventListener("change", apply);
  }, [settings?.theme]);
  useEffect(() => {
    const restore = () => {
      if (document.visibilityState === "visible") setGeneration((v) => v + 1);
    };
    document.addEventListener("visibilitychange", restore);
    window.addEventListener("focus", restore);
    return () => {
      document.removeEventListener("visibilitychange", restore);
      window.removeEventListener("focus", restore);
    };
  }, []);
  useEffect(() => {
    if (page === "History" && api) void api.call<Queue>("queue?refresh_files=true").then(setQueue).catch(error => setActionError(error.message));
  }, [page, api]);
  const compareJob = async (job: Job) => {
    try {
      const record = await api!.call<{ input: { path: string }; settings: Settings; media: Media }>(`queue/${job.id}/json`);
      setTrial({ file: record.input.path, settings: record.settings, media: record.media, job_id: job.id });
    } catch (error) { setActionError((error as Error).message); }
  };
  const retry = () => setGeneration((v) => v + 1);
  const operate = async (route: string, data?: unknown) => {
    try {
      await api?.call(route, "POST", data || {});
      setActionError("");
    } catch (e) {
      setActionError((e as Error).message);
    }
  };
  const perform = async (job: Job, name: string, data?: unknown) => {
    try {
      if (name === "copy") {
        const details = await api!.call<{ text: string }>(
          `queue/${job.id}/details`,
        );
        await window.desktop.copy(details.text);
      } else if (name === "folder") await localAction(job, name);
      else if (name === "play") await window.desktop.play(job.output);
      else if (name === "log")
          setLog(`${job.log}\n\n${(await api!.call<{ text: string }>(`queue/${job.id}/log`)).text}`);
      else if (name === "remove" || name === "clear-history") {
        const ids = (data as { ids?: string[] } | undefined)?.ids || [job.id];
        const result = await api!.call<Operation | { ids: string[]; files: { moved: number; not_found: number; kept: number }; kept: { reason: string }[] }>(name === "remove" ? "history/remove" : "history/clear", "POST", { ids, ...(data as object || {}) });
        if ("kind" in result) {
          setQueue(old => ({ ...old, operations: [...old.operations.filter(op => op.id !== result.id), result] }));
          return;
        }
        setQueue(old => ({ ...old, jobs: old.jobs.filter(record => !result.ids.includes(record.id)) }));
        setHistoryUndo(result.ids.length ? result.ids : undefined);
        setFilesMoved(result.files.moved > 0);
        if (result.files.moved || result.files.not_found || result.files.kept) setActionError(`${result.files.moved} moved, ${result.files.not_found} not found, ${result.files.kept} kept. ${result.kept.map(item => item.reason).join(" ")}`);
        return;
      }
      else await api!.call(`queue/${job.id}/${name}`, "POST", data || {});
      setActionError("");
    } catch (e) {
      setActionError((e as Error).message);
    }
  };
  const action = (job: Job, name: string, data?: unknown) => {
    if (name === "cancel" || name === "remove-unstarted") setConfirm({ job, name });
    else if (name === "delete-files") { const ids = (data as { ids?: string[] } | undefined)?.ids || [job.id]; setHistoryFiles(queue.jobs.filter(record => ids.includes(record.id))); }
    else if (name === "remove") { const ids = (data as { ids?: string[] } | undefined)?.ids || [job.id]; setHistoryRemoval(queue.jobs.filter(record => ids.includes(record.id))); }
    else void perform(job, name, data);
  };
  const add = useCallback(async (paths?: string[]) => {
    try {
      setLinkUrl("");
      setFiles(paths || await window.desktop.files("videos"));
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, []);
  const calibration = queue.operations.findLast((o) => o.kind === "calibrate");
  useEffect(() => window.desktop.onFileDrop?.(event => {
    setDropCount(event.type === "enter" ? event.paths.length : 0);
    if (event.type !== "drop") return;
    if (document.querySelector('[role="dialog"][aria-modal="true"]')) {
      setDropNotice("Close the dialog first to add videos."); return;
    }
    if (event.paths.length) void add(event.paths);
  }), [add]);
  return (
    <div
      className="app"
    >
      {dropNotice && <div className="zoom-toast" role="status">{dropNotice}</div>}
      {!!dropCount && (
        <div className="drop-overlay">Drop to add {dropCount} {dropCount === 1 ? "video" : "videos"}</div>
      )}
      {tour && <Tour navigate={setPage} close={() => { setTour(false); void api!.call("settings", "PUT", { tour_completed: true }).then(() => setSettings(old => old ? { ...old, tour_completed: true } : old)).catch(error => setActionError(error.message)); }} />}
      {historyUndo && <UndoToast key={`${historyUndo.join(",")}:${historyUndoRevision}`} moved={filesMoved} expire={() => setHistoryUndo(undefined)}
        pause={paused => { void api!.call("history/pause-undo", "POST", { ids: historyUndo, paused }).catch(error => setActionError(error.message)); }}
        undo={() => { void api!.call("history/undo", "POST", { ids: historyUndo }).then(() => setHistoryUndo(undefined)).catch(error => setActionError(error.message)); }} />}
      {historyFiles && api && <HistoryRemoval jobs={historyFiles} filesOnly action={(job, name, data) => { void perform(job, name, data); }} close={() => setHistoryFiles(undefined)} />}
      {historyRemoval && <HistoryRemoval jobs={historyRemoval} action={(job, name, data) => { void perform(job, name, data); }} close={() => setHistoryRemoval(undefined)} />}
      {zoomToast !== undefined && <div className="zoom-toast" role="status">
        <strong>{zoomToast}%</strong><span>Ctrl+0 resets to 100%</span>
      </div>}
      {error && <div className="connection-overlay"><ConnectionBanner error={error} retry={retry} /></div>}
      <fieldset className="engine-actions" disabled={reconnecting}>
      <aside>
        <div className="brand" aria-label="VideoEnhancer">
          VE
        </div>
        <nav aria-label="Main navigation">
          {["Home", "History", "Schedule", "Models"].map((name) => (
            <ActionButton
              key={name}
              aria-current={page === name ? "page" : undefined}
              aria-label={name}
              onClick={() => setPage(name)}
            >
              <Icon name={name} />
              <span className="dock-tooltip" role="tooltip">{name}</span>
              {name === "Home" && health?.waiting_count ? <span className="dock-count">{health.waiting_count}</span> : null}
              {name === "History" &&
                queue.jobs.some(
                  (j) =>
                    j.state === "failed" &&
                    !settings?.seen_failures?.includes(j.id),
                ) && <span className="warning-dot" />}
            </ActionButton>
          ))}
        </nav>
        <ActionButton
          className="settings-nav"
          aria-label="Settings"
          aria-current={page === "Settings" ? "page" : undefined}
          onClick={() => setPage("Settings")}
        >
          <Icon name="Settings" />
          <span className="dock-tooltip" role="tooltip">Settings</span>
        </ActionButton>
      </aside>
      <main>
        <ErrorBoundary key={page} scope={page}>
        {reconnecting && <div className="connection card" role="status">Reconnecting… <span>Last update {new Date(lastUpdate).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })}</span></div>}
        {engineStalled && <Notice className="error card" identity={String(lastUpdate)}>
          <p>The engine stopped responding</p>
          <ActionButton onClick={async () => {
            try { await window.desktop.restartEngine?.(); setEngineStalled(false); retry(); }
            catch (error) { setActionError((error as Error).message); }
          }}>Restart</ActionButton>
        </Notice>}
        <ControlWarning health={health} retry={retry} />
        {queue.operations.filter(op => op.kind === "history-removal" && op.state === "running")
          .map(op => <OperationStatus key={op.id} operation={op} />)}
        {health?.last_error && (
          <Notice identity={health.last_error.time + health.last_error.message} dismiss={() => { void api?.call("errors/dismiss", "POST").catch(error => setActionError(error.message)); }}>
            Problem · {problemWhen(health.last_error.time)} · {health.last_error.message}
            <ActionButton
              onClick={() =>
                window.desktop.copy(JSON.stringify(health.last_error, null, 2))
              }
            >
              Copy details
            </ActionButton>
          </Notice>
        )}
        {actionError && (
          <Notice identity={actionError} dismiss={() => setActionError("")}>
            {actionError}

          </Notice>
        )}
        {page === "Home" && (
          <HomePage
            queue={queue}
            health={health}
            plan={plan}
            api={api}
            reconnecting={reconnecting}
            navigate={setPage}
            seenFailures={settings?.seen_failures}
            seen={markSeen}
            pauseAll={() =>
              void operate("processing", {
                paused: !health?.paused_all,
              })
            }
            preview={(job) => void showPreview(job)}
            add={(paths) => void add(paths)}
            action={action}
            trial={(job) => void compareJob(job)}
          />
        )}
        {page === "History" && (
          <HistoryPage
            seen={markSeen}
            queue={queue}
            api={api}
            action={action}
            trial={(job) => void compareJob(job)}
          />
        )}
        {page === "Schedule" && api && schedule && (
          <ScheduleView
            api={api}
            value={schedule}
            applied={() => void refresh()}
            plan={plan}
            jobs={queue.jobs}
          />
        )}
        {page === "Models" && api && (
          <ModelsPage
            health={health}
            compare={async () => {
              const chosen = await window.desktop.files("videos");
              if (chosen[0] && settings)
                setTrial({ file: chosen[0], settings });
            }}
            settings={settings}
            api={api}
            models={models}
            refresh={() =>
              void refresh().catch((e) => setActionError(e.message))
            }
            operate={(route, data) => void operate(route, data)}
            operations={queue.operations}
          />
        )}
        {page === "Settings" && api && settings && (
          <SettingsPage tour={() => setTour(true)} appearance={theme => setSettings(old => old ? { ...old, theme } : old)}
            api={api}
            value={settings}
            health={health}
            saved={() => void refresh()}
            calibrate={() => void operate("calibrate")}
            operation={calibration}
          />
        )}
        {(!api || !settings || !health) && !error && <div className="connection card" role="status"><h2>Connecting to the engine…</h2><p>Getting your videos and settings ready.</p></div>}
        </ErrorBoundary>
      </main>
      {files && api && settings && (
        <ErrorBoundary key={files.join("|")} scope="Add videos">
        <AddDialog
          initialUrl={linkUrl}
          api={api}
          files={files}
          defaults={settings}
          models={models}
          av1={health?.av1_supported}
          av1Reason={health?.av1_unavailable_reason}
          close={() => setFiles(undefined)}
          saved={() => setFiles(undefined)}
          trial={(file, prefs, media, apply) =>
            setTrial({ file, settings: prefs, media, apply })
          }
        />
        </ErrorBoundary>
      )}
      {trial && api && (
        <ErrorBoundary key={trial.file} scope="Compare">
        <TrialDialog
          models={models}
          started={
            !!trial.job_id &&
            queue.jobs.some(
              (j) =>
                j.id === trial.job_id &&
                (!!j.started_at ||
                  j.segment > 0 ||
                  !["queued", "paused"].includes(j.state)),
            )
          }
          switchStandard={async () => {
            if (trial.apply) trial.apply("preset", "standard");
            else if (trial.job_id) await api.call(`queue/${trial.job_id}/mode`, "POST", { preset: "standard" });
            setTrial(old => old ? { ...old, settings: { ...old.settings, preset: "standard" } } : old);
            await refresh();
          }}
          useModel={async (key, id) => {
            if (trial.apply) trial.apply(key, id);
            else if (trial.job_id)
              await api.call(`queue/${trial.job_id}/model`, "POST", {
                [key]: id,
              });
            else await api.call("settings", "PUT", { [key]: id });
            await refresh();
          }}
          api={api}
          value={trial}
          operations={queue.operations}
          close={() => setTrial(undefined)}
        />
        </ErrorBoundary>
      )}
      {resultPreview && api && (
        <div className="modal-shade compare-full-window">
          <div
            className="dialog trial-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Preview result"
          >
            <h2>Preview result</h2>
            <p>This uses the completed result and leaves processing running.</p>
            {resultOperation && resultOperation.state !== "done" && <OperationStatus operation={resultOperation} />}
            {resultOperation?.state === "done" && (
              <Compare api={api} operation={resultOperation} />
            )}
            <ActionButton
              onClick={async () => {
                try {
                  await api.call(
                    `operations/${resultPreview}/cancel`,
                    "POST",
                    {},
                  );
                  setResultPreview(undefined);
                } catch (error) {
                  setActionError((error as Error).message);
                }
              }}
            >
              Close
            </ActionButton>
          </div>
        </div>
      )}
      {trayExplanation && <div className="modal-shade"><div className="dialog" role="dialog" aria-modal="true">
        <h2>VideoEnhancer keeps working in the tray</h2>
        <p>Closing the window doesn't stop it. It stays in the tray next to the clock and works during your hours. To stop it completely, choose Quit there.</p>
        <p>Right-click the icon in the tray to open VideoEnhancer, pause processing, or quit.</p>
        <div className="dialog-actions"><ActionButton className="primary" onClick={async () => {
          try { await window.desktop.hide(); setTrayExplanation(false); } catch (error) { setActionError((error as Error).message); }
        }}>Got it</ActionButton></div>
      </div></div>}
      {confirm && (
        <div className="modal-shade">
          <div role="dialog" aria-modal="true" className="dialog">
            <h2>
              {confirm.name === "remove-unstarted" ? "Remove" : "Cancel"}{" "}
              {filename(confirm.job.input)}{confirm.name === "remove-unstarted" ? " from the queue" : ""}?
            </h2>
            <p>
              {confirm.name === "remove-unstarted"
                ? "It hasn't started, so no work is lost. No files are changed."
                : (confirm.job.completed_segments ?? confirm.job.segment) === 0
                  ? "Remove this video from the queue. The original stays as it is."
                  : "The work so far will be lost. This video cannot be resumed. The original stays as it is."}
            </p>
            <div className="dialog-actions">
              <ActionButton onClick={() => setConfirm(undefined)}>{confirm.name === "remove-unstarted" ? "Keep it" : "Keep working"}</ActionButton>
              <ActionButton
                className="danger"
                onClick={() => {
                  void perform(confirm.job, confirm.name === "remove-unstarted" ? "cancel" : confirm.name);
                  setConfirm(undefined);
                }}
              >
                {confirm.name === "remove-unstarted" ? "Remove from queue" : "Cancel video"}
              </ActionButton>
            </div>
          </div>
        </div>
      )}
      {log !== undefined && (
        <div className="modal-shade">
          <div className="dialog wide" role="dialog" aria-modal="true">
            <h2>Job log</h2>
            <pre>{log}</pre>
            <div className="dialog-actions">
              <ActionButton onClick={() => window.desktop.copy(log)}>Copy log</ActionButton>
              <ActionButton onClick={() => setLog(undefined)}>Close</ActionButton>
            </div>
          </div>
        </div>
      )}
      </fieldset>
    </div>
  );
}

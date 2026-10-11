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
    <div className="error connection" role="alert">
      Engine unreachable: {error} <button onClick={retry}>Retry</button>
      <p>Your last known data remains visible.</p>
    </div>
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
    <div className="error" role="alert">
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
      <button onClick={retry}>Retry</button>
    </div>
  ) : null;
}
export default function App() {
  useDialogFocus();
  const [page, setPage] = useState("Home");
  const [dropCount, setDropCount] = useState(0);
  const [api, setApi] = useState<Api>();
  const [error, setError] = useState("");
  const [reconnecting, setReconnecting] = useState(false);
  const [actionError, setActionError] = useState("");
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
  useEffect(() => {
    if (!historyUndo) return;
    const timer = setTimeout(() => setHistoryUndo(undefined), 10000);
    return () => clearTimeout(timer);
  }, [historyUndo]);
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
            const snapshot = raw as {
              queue: Queue;
              health: Health;
              plan: Plan;
            };
            setQueue(snapshot.queue);
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
        );
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
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
      else if (name === "remove") {
        const ids = (data as { ids?: string[] } | undefined)?.ids || [job.id];
        await api!.call("history/remove", "POST", { ids });
        setQueue(old => ({ ...old, jobs: old.jobs.filter(record => !ids.includes(record.id)) }));
        setHistoryUndo(ids);
      }
      else if (name === "clear-history") { await api!.call("history/clear", "POST", {}); setQueue(old => ({ ...old, jobs: old.jobs.filter(record => !["done", "failed", "cancelled"].includes(record.state)) })); }
      else await api!.call(`queue/${job.id}/${name}`, "POST", data || {});
      setActionError("");
    } catch (e) {
      setActionError((e as Error).message);
    }
  };
  const action = (job: Job, name: string, data?: unknown) => {
    if (name === "cancel") setConfirm({ job, name });
    else void perform(job, name, data);
  };
  const add = async (paths?: string[]) => {
    try {
      const selected = paths || (await window.desktop.files("videos"));
      if (selected.length) setFiles(selected);
    } catch (e) {
      setActionError((e as Error).message);
    }
  };
  const calibration = queue.operations.findLast((o) => o.kind === "calibrate");
  return (
    <div
      className="app"
      onDragEnter={(e) => {
        if (Array.from(e.dataTransfer.types).includes("Files"))
          setDropCount(Math.max(1, e.dataTransfer.items.length));
      }}
      onDragOver={(e) => {
        if (Array.from(e.dataTransfer.types).includes("Files"))
          e.preventDefault();
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDropCount(0);
      }}
      onDrop={(e) => {
        setDropCount(0);
        if (e.dataTransfer.files.length) {
          e.preventDefault();
          void add(
            Array.from(e.dataTransfer.files).map((file) =>
              window.desktop.filePath(file),
            ),
          );
        }
      }}
    >
      {!!dropCount && (
        <div className="drop-overlay">Drop to add {dropCount} {dropCount === 1 ? "video" : "videos"}</div>
      )}
      <div className="title-bar"><span className="title-icon">VE</span>VideoEnhancer</div>
      {historyUndo && <div className="zoom-toast" role="status">
        Removed from history
        <button onClick={async () => {
          try {
            await api!.call("history/undo", "POST", { ids: historyUndo });
            setHistoryUndo(undefined);
          } catch (error) { setActionError((error as Error).message); }
        }}>Undo</button>
      </div>}
      {zoomToast !== undefined && <div className="zoom-toast" role="status">
        <strong>{zoomToast}%</strong><span>Ctrl+0 resets to 100%</span>
      </div>}
      <aside>
        <div className="brand" aria-label="VideoEnhancer">
          VE
        </div>
        <nav aria-label="Main navigation">
          {["Home", "History", "Schedule", "Models"].map((name) => (
            <button
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
            </button>
          ))}
        </nav>
        <button
          className="settings-nav"
          aria-label="Settings"
          aria-current={page === "Settings" ? "page" : undefined}
          onClick={() => setPage("Settings")}
        >
          <Icon name="Settings" />
          <span className="dock-tooltip" role="tooltip">Settings</span>
        </button>
      </aside>
      <main>
        {reconnecting && <div role="status">Reconnecting…</div>}
        <ConnectionBanner error={error} retry={retry} />
        <ControlWarning health={health} retry={retry} />
        {health?.last_error && (
          <div className="error" role="alert">
            Problem · {problemWhen(health.last_error.time)} · {health.last_error.message}
            <button
              onClick={() =>
                window.desktop.copy(JSON.stringify(health.last_error, null, 2))
              }
            >
              Copy details
            </button>
          </div>
        )}
        {actionError && (
          <div role="alert" className="error">
            {actionError}
            <button onClick={() => setActionError("")}>Dismiss</button>
          </div>
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
            trial={(job) =>
              setTrial({
                file: job.input,
                settings: job.settings,
                media: job.media,
                job_id: job.id,
              })
            }
          />
        )}
        {page === "History" && (
          <HistoryPage
            seen={markSeen}
            queue={queue}
            api={api}
            action={action}
            trial={(job) =>
              setTrial({
                file: job.input,
                settings: job.settings,
                media: job.media,
                job_id: job.id,
              })
            }
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
          <SettingsPage
            api={api}
            value={settings}
            health={health}
            saved={() => void refresh()}
            calibrate={() => void operate("calibrate")}
            operation={calibration}
          />
        )}
        {!api && !error && <p role="status">Connecting to the engine…</p>}
      </main>
      {files && api && settings && (
        <AddDialog
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
      )}
      {trial && api && (
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
      )}
      {resultPreview && api && (
        <div className="modal-shade">
          <div
            className="dialog wide"
            role="dialog"
            aria-modal="true"
            aria-label="Preview result"
          >
            <h2>Preview result</h2>
            <p>This uses the completed result and leaves processing running.</p>
            {resultOperation && <OperationStatus operation={resultOperation} />}
            {resultOperation?.state === "done" && (
              <Compare api={api} operation={resultOperation} />
            )}
            <button
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
            </button>
          </div>
        </div>
      )}
      {trayExplanation && <div className="modal-shade"><div className="dialog" role="dialog" aria-modal="true">
        <h2>VideoEnhancer keeps working in the tray</h2>
        <p>Closing the window doesn't stop it. It stays in the tray next to the clock and works during your hours. To stop it completely, choose Quit there.</p>
        <p>Right-click the icon in the tray to open VideoEnhancer, pause processing, or quit.</p>
        <div className="dialog-actions"><button className="primary" onClick={async () => {
          try { await window.desktop.hide(); setTrayExplanation(false); } catch (error) { setActionError((error as Error).message); }
        }}>Got it</button></div>
      </div></div>}
      {confirm && (
        <div className="modal-shade">
          <div role="dialog" aria-modal="true" className="dialog">
            <h2>
              {confirm.name === "remove" || (confirm.job.completed_segments ?? confirm.job.segment) === 0 ? "Remove" : "Cancel"}{" "}
              {filename(confirm.job.input)}{confirm.name === "cancel" && (confirm.job.completed_segments ?? confirm.job.segment) === 0 ? " from the queue" : ""}?
            </h2>
            <p>
              {confirm.name === "remove"
                ? "Remove this job and its trial previews. The finished output is kept."
                : (confirm.job.completed_segments ?? confirm.job.segment) === 0
                  ? "Remove this video from the queue. The original stays as it is."
                  : "The work so far will be lost. This video cannot be resumed. The original stays as it is."}
            </p>
            <div className="dialog-actions">
              <button onClick={() => setConfirm(undefined)}>Keep job</button>
              <button
                className="danger"
                onClick={() => {
                  void perform(confirm.job, confirm.name);
                  setConfirm(undefined);
                }}
              >
                {confirm.name === "remove" ? "Remove job" : "Cancel job"}
              </button>
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
              <button onClick={() => window.desktop.copy(log)}>Copy log</button>
              <button onClick={() => setLog(undefined)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

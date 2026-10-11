import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { completion, filename, when } from "./api";
import type { Job, Plan, Schedule, Window } from "./types";
import { cells, windows, SchedulePage } from "./Schedule";
import { timelineHour } from "./Pages";

const days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const time = (quarter: number) =>
  `${String(Math.floor(quarter / 4) % 24).padStart(2, "0")}:${String((quarter % 4) * 15).padStart(2, "0")}`;
const quarter = (value: string) =>
  Number(value.slice(0, 2)) * 4 + Number(value.slice(3)) / 15;
function ranges(row: boolean[]) {
  const result: { start: number; end: number }[] = [];
  for (let q = 0; q < 96;) {
    if (!row[q]) {
      q++;
      continue;
    }
    const start = q;
    while (q < 96 && row[q]) q++;
    result.push({ start, end: q });
  }
  return result;
}

export function ScheduleView({
  api,
  value,
  plan,
  jobs,
  applied,
}: {
  api: Api;
  value: Schedule;
  plan?: Plan;
  jobs: Job[];
  applied(): void;
}) {
  const [draft, setDraft] = useState(value),
    [preview, setPreview] = useState<Plan>(),
    [freePlan, setFreePlan] = useState<Plan>();
  const [bounds, setBounds] = useState<{ best?: Plan; worst?: Plan }>({});
  const [saveCount, setSaveCount] = useState(0);
  const [exceptionEditor, setExceptionEditor] = useState(false);
  const [blockMenu, setBlockMenu] = useState<{
    day: string;
    weekday: number;
    row: boolean[];
    start: number;
  }>();
  const [tooltip, setTooltip] = useState("");
  const [undo, setUndo] = useState<Schedule>(),
    [saved, setSaved] = useState(false),
    [error, setError] = useState("");
  const [custom, setCustom] = useState(false),
    [editing, setEditing] = useState<string>(),
    [date, setDate] = useState("");
  const [exceptionOff, setExceptionOff] = useState(true),
    [exceptionStart, setExceptionStart] = useState("09:00"),
    [exceptionEnd, setExceptionEnd] = useState("18:00"),
    [until, setUntil] = useState("");
  const [exceptionExtra, setExceptionExtra] = useState<Window[]>([]);
  const suppressClick = useRef(false);
  const drag = useRef<
    | {
        day: string;
        weekday: number;
        start: number;
        end: number;
        origin: number;
        edge: string;
        row: boolean[];
      }
    | undefined
  >(undefined);
  const lastApplied = useRef(value),
    appliedCallback = useRef(applied);
  useEffect(() => {
    appliedCallback.current = applied;
  }, [applied]);
  useEffect(() => {
    setDraft((previous) =>
      JSON.stringify(previous) === JSON.stringify(lastApplied.current)
        ? value
        : previous,
    );
    lastApplied.current = value;
  }, [value]);
  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      void api
        .call<{ plan: Plan; best?: Plan; worst?: Plan }>(
          "schedule/preview",
          "POST",
          draft,
        )
        .then((p) => {
          if (alive) {
            setPreview(p.plan);
            setBounds({ best: p.best, worst: p.worst });
            setError("");
          }
        })
        .catch((e) => {
          if (alive) setError(e.message);
        });
    }, 150);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [api, draft]);
  useEffect(() => {
    let alive = true;
    void api
      .call<{ plan: Plan }>("schedule/preview", "POST", {
        ...draft,
        enabled: false,
        override_until: null,
      })
      .then((p) => {
        if (alive) setFreePlan(p.plan);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [api, draft]);
  useEffect(() => {
    if (JSON.stringify(draft) === JSON.stringify(lastApplied.current) || error)
      return;
    let alive = true;
    const timer = setTimeout(() => {
      const previous = lastApplied.current;
      void api
        .call("schedule", "PUT", draft)
        .then(() => {
          lastApplied.current = draft;
          if (alive) {
            setUndo(previous);
            setSaved(true);
            setSaveCount((previous) => previous + 1);
            appliedCallback.current();
          }
        })
        .catch((e) => {
          if (alive) setError(e.message);
        });
    }, 600);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [api, draft, error]);
  useEffect(() => {
    if (!saved) return;
    const timer = setTimeout(() => setSaved(false), 8000);
    return () => clearTimeout(timer);
  }, [saved, saveCount]);
  const shown = preview || plan;
  const grid = cells(draft);
  const rowFor = (day: string, weekday: number) => {
    const exception = draft.exceptions.find((e) => e.date === day);
    if (!exception) return grid[(weekday + 6) % 7];
    const row = Array<boolean>(96).fill(false);
    if (exception.windows !== "off")
      for (const w of exception.windows) {
        const end = quarter(w.end) || 96;
        for (let q = quarter(w.start); q < end; q++) row[q] = true;
      }
    return row;
  };
  const writeRow = (
    day: string,
    weekday: number,
    row: boolean[],
    dateOnly = false,
  ) => {
    setEditing(day);
    const exception = dateOnly || draft.exceptions.some((e) => e.date === day);
    if (exception) {
      const values: Window[] = ranges(row).map((r) => ({
        start: time(r.start),
        end: time(r.end),
      }));
      setDraft({
        ...draft,
        exceptions: [
          ...draft.exceptions.filter((e) => e.date !== day),
          { date: day, windows: values.length ? values : "off" },
        ],
      });
    } else {
      const next = cells(draft);
      next[(weekday + 6) % 7] = row;
      setDraft({ ...draft, weekly: windows(next) });
    }
  };
  const moveRange = (
    day: string,
    weekday: number,
    row: boolean[],
    start: number,
    end: number,
    left: number,
    right: number,
  ) => {
    const next = row.slice();
    for (let q = start; q < end; q++) next[q] = false;
    for (let q = Math.max(0, left); q < Math.min(96, right); q++)
      next[q] = true;
    writeRow(day, weekday, next);
  };
  const override = async (target: string | null) => {
    try {
      await api.call("schedule/override", "POST", { until: target });
      applied();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <section aria-label="Schedule">
      <div className="page-heading">
        <div>
          <h1>Schedule</h1>
          <p>Everything finishes {when(completion(shown))}</p>
          {bounds.best && bounds.worst && (
            <p className="muted">
              could be {when(completion(bounds.best))} –{" "}
              {when(completion(bounds.worst))}
            </p>
          )}
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
          />
          Only work during my hours
        </label>
      </div>
      <div className="schedule-presets">
        {[
          "Weeknights 22:00–08:00 + weekends",
          "Every night 22:00–08:00",
          "While I'm at work 09:00–18:00",
        ].map((name, n) => (
          <button
            key={name}
            onClick={() => {
              setUndo(draft);
              setDraft({
                ...draft,
                weekly:
                  n === 0
                    ? [
                        {
                          days: ["mon", "tue", "wed", "thu", "fri"],
                          start: "22:00",
                          end: "08:00",
                        },
                        { days: ["sat", "sun"], start: "00:00", end: "00:00" },
                      ]
                    : [
                        {
                          days:
                            n === 1
                              ? days
                              : ["mon", "tue", "wed", "thu", "fri"],
                          start: n === 1 ? "22:00" : "09:00",
                          end: n === 1 ? "08:00" : "18:00",
                        },
                      ],
              });
            }}
          >
            {name}
          </button>
        ))}
        <button onClick={() => setCustom(true)}>Custom…</button>
      </div>
      {saved && (
        <div role="status" className="saved-toast">
          Saved ·{" "}
          <button
            disabled={!undo}
            onClick={() => {
              if (undo) {
                setDraft(undo);
                setSaved(false);
              }
            }}
          >
            Undo
          </button>
        </div>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {tooltip && (
        <div role="tooltip" id="work-tooltip" className="work-tooltip">
          {tooltip}
        </div>
      )}
      <div className="schedule-columns">
        <article className="card">
          <div className="track-heading">
            <span />
            <div>
              {["00", "06", "12", "18", "24"].map((t) => (
                <span key={t}>{t}</span>
              ))}
            </div>
            <span />
          </div>
          {shown?.days.slice(0, 7).map((day) => {
            const weekday = new Date(`${day.date}T12:00:00Z`).getUTCDay(),
              row = rowFor(day.date, weekday),
              blocks = ranges(
                draft.enabled ? row : Array<boolean>(96).fill(true),
              );
            return (
              <div className="schedule-track-row" key={day.date}>
                <strong>
                  {editing === day.date &&
                  !draft.exceptions.some((e) => e.date === day.date)
                    ? "Every "
                    : ""}
                  {new Date(`${day.date}T12:00:00Z`).toLocaleDateString(
                    "en-US",
                    { weekday: "short", timeZone: "UTC" },
                  )}
                  <small>{day.date.slice(5)}</small>
                </strong>
                <div
                  className="hours-track"
                  onClick={(e) => {
                    if (suppressClick.current) {
                      suppressClick.current = false;
                      return;
                    }
                    if (e.target !== e.currentTarget || !draft.enabled) return;
                    const rect = e.currentTarget.getBoundingClientRect();
                    const q = Math.min(
                      88,
                      Math.max(
                        0,
                        Math.floor(((e.clientX - rect.left) / rect.width) * 96),
                      ),
                    );
                    const next = row.slice();
                    for (let n = q; n < q + 8; n++) next[n] = true;
                    writeRow(day.date, weekday, next);
                  }}
                  onPointerMove={(e) => {
                    const state = drag.current;
                    if (!state) return;
                    const rect = e.currentTarget.getBoundingClientRect(),
                      q = Math.round(
                        ((e.clientX - rect.left) / rect.width) * 96,
                      ),
                      delta = q - state.origin;
                    const length = state.end - state.start;
                    const left =
                      state.edge === "end"
                        ? state.start
                        : state.edge === "start"
                          ? Math.max(
                              0,
                              Math.min(state.end - 1, state.start + delta),
                            )
                          : Math.max(
                              0,
                              Math.min(96 - length, state.start + delta),
                            );
                    const right =
                      state.edge === "start"
                        ? state.end
                        : state.edge === "end"
                          ? Math.min(
                              96,
                              Math.max(state.start + 1, state.end + delta),
                            )
                          : left + length;
                    moveRange(
                      state.day,
                      state.weekday,
                      state.row,
                      state.start,
                      state.end,
                      left,
                      right,
                    );
                  }}
                  onPointerUp={() => {
                    suppressClick.current = Boolean(drag.current);
                    drag.current = undefined;
                  }}
                >
                  {blocks.map((block) => (
                    <div
                      className="allowed-block"
                      key={`${block.start}-${block.end}`}
                      style={{
                        left: `${(block.start / 96) * 100}%`,
                        width: `${((block.end - block.start) / 96) * 100}%`,
                      }}
                      tabIndex={0}
                      role="group"
                      aria-label={`${day.date} ${time(block.start)}–${block.end === 96 ? "24:00" : time(block.end)}`}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        if (draft.enabled)
                          setBlockMenu({
                            day: day.date,
                            weekday,
                            row,
                            start: block.start,
                          });
                      }}
                      onKeyDown={(e) => {
                        if (!draft.enabled) return;
                        if (
                          e.key === "ContextMenu" ||
                          (e.shiftKey && e.key === "F10")
                        ) {
                          e.preventDefault();
                          setBlockMenu({
                            day: day.date,
                            weekday,
                            row,
                            start: block.start,
                          });
                        }
                        if (e.key === "Escape") setBlockMenu(undefined);
                        if (e.key === "Delete") {
                          e.preventDefault();
                          moveRange(
                            day.date,
                            weekday,
                            row,
                            block.start,
                            block.end,
                            0,
                            0,
                          );
                        }
                      }}
                      onPointerDown={(e) => {
                        if (!draft.enabled) return;
                        e.stopPropagation();
                        const track = e.currentTarget.parentElement!;
                        const rect = track.getBoundingClientRect();
                        drag.current = {
                          day: day.date,
                          weekday,
                          row,
                          start: block.start,
                          end: block.end,
                          origin: Math.round(
                            ((e.clientX - rect.left) / rect.width) * 96,
                          ),
                          edge:
                            (e.target as HTMLElement).dataset.edge || "move",
                        };
                        track.setPointerCapture(e.pointerId);
                      }}
                    >
                      {["start", "end"].map((edge) => (
                        <button
                          className={`block-edge ${edge}`}
                          key={edge}
                          data-edge={edge}
                          aria-label={`${day.date} ${edge} edge`}
                          disabled={!draft.enabled}
                          onKeyDown={(e) => {
                            if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
                              e.preventDefault();
                              const delta = e.key === "ArrowRight" ? 1 : -1;
                              moveRange(
                                day.date,
                                weekday,
                                row,
                                block.start,
                                block.end,
                                edge === "start"
                                  ? Math.max(
                                      0,
                                      Math.min(
                                        block.end - 1,
                                        block.start + delta,
                                      ),
                                    )
                                  : block.start,
                                edge === "end"
                                  ? Math.min(
                                      96,
                                      Math.max(
                                        block.start + 1,
                                        block.end + delta,
                                      ),
                                    )
                                  : block.end,
                              );
                            }
                          }}
                        />
                      ))}
                      <span>
                        {time(block.start)}–
                        {block.end === 96 ? "24:00" : time(block.end)}
                      </span>
                      <button
                        className="block-menu-trigger"
                        aria-label={`Options for ${day.date} ${time(block.start)}`}
                        disabled={!draft.enabled}
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => {
                          e.stopPropagation();
                          setBlockMenu({
                            day: day.date,
                            weekday,
                            row,
                            start: block.start,
                          });
                        }}
                      >
                        ⋯
                      </button>
                      {blockMenu?.day === day.date &&
                        blockMenu.start === block.start && (
                          <div
                            role="menu"
                            className="row-menu"
                            onPointerDown={(e) => e.stopPropagation()}
                          >
                            <button
                              role="menuitem"
                              onClick={(e) => {
                                e.stopPropagation();
                                writeRow(
                                  day.date,
                                  weekday,
                                  blockMenu.row,
                                  true,
                                );
                                setBlockMenu(undefined);
                              }}
                            >
                              Only on{" "}
                              {new Date(
                                `${day.date}T12:00:00Z`,
                              ).toLocaleDateString("en-US", {
                                weekday: "short",
                                timeZone: "UTC",
                              })}{" "}
                              {day.date.slice(5).replace("-", "/")}
                            </button>
                          </div>
                        )}
                      <button
                        className="remove-block"
                        aria-label={`Remove ${day.date} ${time(block.start)}`}
                        disabled={!draft.enabled}
                        onPointerDown={(e) => e.stopPropagation()}
                        onClick={(e) => {
                          e.stopPropagation();
                          moveRange(
                            day.date,
                            weekday,
                            row,
                            block.start,
                            block.end,
                            0,
                            0,
                          );
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {shown.timeline
                    .filter(
                      (t) =>
                        timelineHour(t.end, day.date, shown.timezone) >
                        timelineHour(t.start, day.date, shown.timezone),
                    )
                    .map((t, i) => (
                      <div
                        className="planned-block"
                        key={i}
                        tabIndex={0}
                        aria-describedby={tooltip ? "work-tooltip" : undefined}
                        onFocus={() =>
                          setTooltip(
                            `${filename(jobs.find((j) => j.id === t.job_id)?.input || t.job_id)} ${(t.start_percent || 0).toFixed(0)}% → ${(t.end_percent || 0).toFixed(0)}%, done ${when(t.end)}${t.overrun_seconds ? ` · Finishing one step after your hours, about ${Math.ceil(t.overrun_seconds / 60)} min` : ""}`,
                          )
                        }
                        onBlur={() => setTooltip("")}
                        onMouseEnter={() =>
                          setTooltip(
                            `${filename(jobs.find((j) => j.id === t.job_id)?.input || t.job_id)} ${(t.start_percent || 0).toFixed(0)}% → ${(t.end_percent || 0).toFixed(0)}%, done ${when(t.end)}${t.overrun_seconds ? ` · Finishing one step after your hours, about ${Math.ceil(t.overrun_seconds / 60)} min` : ""}`,
                          )
                        }
                        onMouseLeave={() => setTooltip("")}
                        style={{
                          left: `${(timelineHour(t.start, day.date, shown.timezone) / 24) * 100}%`,
                          width: `${((timelineHour(t.end, day.date, shown.timezone) - timelineHour(t.start, day.date, shown.timezone)) / 24) * 100}%`,
                        }}
                        title={`${filename(jobs.find((j) => j.id === t.job_id)?.input || t.job_id)} · done ${when(t.end)}${t.overrun_seconds ? ` · Finishing one step after your hours, about ${Math.ceil(t.overrun_seconds / 60)} min` : ""}`}
                      />
                    ))}
                  {day.date === shown.days[0].date && (
                    <div
                      className="now-line"
                      style={{
                        left: `${(timelineHour(new Date().toISOString(), day.date, shown.timezone) / 24) * 100}%`,
                      }}
                      title="Now"
                    />
                  )}
                </div>
                <span>
                  {!draft.enabled
                    ? "Working any time"
                    : day.run_hours
                      ? `${day.run_hours.toFixed(1)} h`
                      : blocks.length
                        ? "free"
                        : "off"}
                </span>
              </div>
            );
          })}
          <p className="muted">
            Allowed hours · Planned work · Now. Drag edges or press arrow keys
            to change times. Delete removes a focused block.
          </p>
        </article>
        <div className="home-sidebar">
          <article className="card">
            <h2>Exceptions</h2>
            {draft.exceptions.map((e) => (
              <div key={e.date}>
                <button
                  onClick={() => {
                    setDate(e.date);
                    setExceptionOff(e.windows === "off");
                    setExceptionExtra(
                      e.windows === "off" ? [] : e.windows.slice(1),
                    );
                    if (e.windows !== "off") {
                      setExceptionStart(e.windows[0]?.start || "09:00");
                      setExceptionEnd(e.windows[0]?.end || "18:00");
                    }
                    setExceptionEditor(true);
                  }}
                >
                  {e.date} ·{" "}
                  {e.windows === "off"
                    ? "Off all day"
                    : e.windows.map((w) => `${w.start}–${w.end}`).join(", ")}
                </button>
                <button
                  aria-label={`Delete exception ${e.date}`}
                  onClick={() =>
                    setDraft({
                      ...draft,
                      exceptions: draft.exceptions.filter(
                        (v) => v.date !== e.date,
                      ),
                    })
                  }
                >
                  ×
                </button>
              </div>
            ))}
            <button
              onClick={() => {
                setDate("");
                setExceptionOff(true);
                setExceptionExtra([]);
                setExceptionEditor(true);
              }}
            >
              Add a day
            </button>
            {exceptionEditor && (
              <div className="exception-editor">
                <label>
                  Exception date
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                  />
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={exceptionOff}
                    onChange={(e) => setExceptionOff(e.target.checked)}
                  />
                  Off all day
                </label>
                {!exceptionOff && (
                  <div className="actions">
                    <input
                      aria-label="Exception start"
                      type="time"
                      step="900"
                      value={exceptionStart}
                      onChange={(e) => setExceptionStart(e.target.value)}
                    />
                    <input
                      aria-label="Exception end"
                      type="time"
                      step="900"
                      value={exceptionEnd}
                      onChange={(e) => setExceptionEnd(e.target.value)}
                    />
                  </div>
                )}
                {!exceptionOff &&
                  exceptionExtra.map((window, index) => (
                    <div className="actions" key={index}>
                      <input
                        aria-label={`Exception start ${index + 2}`}
                        type="time"
                        step="900"
                        value={window.start}
                        onChange={(e) =>
                          setExceptionExtra((old) =>
                            old.map((w, i) =>
                              i === index ? { ...w, start: e.target.value } : w,
                            ),
                          )
                        }
                      />
                      <input
                        aria-label={`Exception end ${index + 2}`}
                        type="time"
                        step="900"
                        value={window.end}
                        onChange={(e) =>
                          setExceptionExtra((old) =>
                            old.map((w, i) =>
                              i === index ? { ...w, end: e.target.value } : w,
                            ),
                          )
                        }
                      />
                      <button
                        aria-label={`Remove hours ${index + 2}`}
                        onClick={() =>
                          setExceptionExtra((old) =>
                            old.filter((_, i) => i !== index),
                          )
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                <button
                  disabled={!date}
                  onClick={() => {
                    setDraft({
                      ...draft,
                      exceptions: [
                        ...draft.exceptions.filter((e) => e.date !== date),
                        {
                          date,
                          windows: exceptionOff
                            ? "off"
                            : [
                                { start: exceptionStart, end: exceptionEnd },
                                ...exceptionExtra,
                              ],
                        },
                      ],
                    });
                    setExceptionEditor(false);
                  }}
                >
                  Save day
                </button>
                <button onClick={() => setExceptionEditor(false)}>Close</button>
              </div>
            )}
          </article>
          <article className="card">
            <h2>Need it sooner?</h2>
            {draft.override_until ? (
              <>
                <p>
                  Working now until{" "}
                  {draft.override_until === "queue-complete"
                    ? "the queue is done"
                    : when(draft.override_until)}
                </p>
                <button onClick={() => void override(null)}>Stop</button>
              </>
            ) : (
              <>
                <p>
                  Ignore your hours and keep working. Everything would finish{" "}
                  {when(completion(freePlan))}.
                </p>
                <button onClick={() => void override("queue-complete")}>
                  Run now until the queue is done
                </button>
                <label>
                  Run now until a time…
                  <input
                    type="datetime-local"
                    value={until}
                    onChange={(e) => setUntil(e.target.value)}
                  />
                </label>
                <button disabled={!until} onClick={() => void override(until)}>
                  Run now until a time…
                </button>
              </>
            )}
          </article>
        </div>
      </div>
      {custom && (
        <div className="modal-shade">
          <div
            className="dialog wide"
            role="dialog"
            aria-modal="true"
            aria-label="Exact operating hours"
          >
            <SchedulePage
              api={api}
              value={draft}
              applied={() => {
                applied();
                setCustom(false);
              }}
              currentFinish={completion(shown)}
            />
            <button onClick={() => setCustom(false)}>Close</button>
          </div>
        </div>
      )}
    </section>
  );
}

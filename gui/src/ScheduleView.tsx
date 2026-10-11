import { useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { completion, filename, when } from "./api";
import type { Job, Plan, Schedule, Window } from "./types";
import { timelineHour } from "./Pages";

const days = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const shiftTime = (value: string, delta: number) => {
  const minutes = ((Number(value.slice(0, 2)) * 60 + Number(value.slice(3)) + delta) % 1440 + 1440) % 1440;
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
};

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
    [preview, setPreview] = useState<Plan>();
  const [saveCount, setSaveCount] = useState(0);
  const [exceptionEditor, setExceptionEditor] = useState(false);
  const [undo, setUndo] = useState<Schedule>(),
    [saved, setSaved] = useState(false),
    [error, setError] = useState("");
  const [date, setDate] = useState("");
  const [exceptionOff, setExceptionOff] = useState(true),
    [exceptionStart, setExceptionStart] = useState("09:00"),
    [exceptionEnd, setExceptionEnd] = useState("18:00"),
    [until, setUntil] = useState("");
  const [exceptionExtra, setExceptionExtra] = useState<Window[]>([]);
  const [overrideCheck, setOverrideCheck] = useState<{ finish: string | null }>();
  useEffect(() => {
    setOverrideCheck(undefined);
    if (!until || !Number.isFinite(new Date(until).getTime())) return;
    const abort = new AbortController();
    const timer = setTimeout(() => {
      void api.call<{ plan: Plan }>("schedule/preview", "POST", { ...draft, override_until: new Date(until).toISOString() }, abort.signal)
        .then(result => { if (!abort.signal.aborted) setOverrideCheck({ finish: completion(result.plan) || null }); })
        .catch(error => { if (!abort.signal.aborted) setError(error.message); });
    }, 400);
    return () => { clearTimeout(timer); abort.abort(); };
  }, [api, draft, until]);
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
    const request = new AbortController();
    const timer = setTimeout(() => {
      void api
        .call<{ plan: Plan }>(
          "schedule/preview",
          "POST",
          draft,
          request.signal,
        )
        .then((p) => {
          if (alive) {
            setPreview(p.plan);
            setError("");
          }
        })
        .catch((e) => {
          if (alive) setError(e.message);
        });
    }, 400);
    return () => {
      alive = false;
      request.abort();
      clearTimeout(timer);
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
  const row = (index: number, patch: Partial<Schedule["weekly"][number]>) =>
    setDraft(old => ({ ...old, weekly: old.weekly.map((value, i) => i === index ? { ...value, ...patch } : value) }));
  const oldFinish = completion(plan);
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
                enabled: true,
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
      <div className="schedule-columns">
        <div className="schedule-numeric-column">
          <article className="card">
            <h2>Your hours</h2>
            <div className="numeric-hours">
              {draft.weekly.map((window, index) => <div className="numeric-hour" role="group" aria-label={`Hours ${index + 1}`} key={index}>
                <div className="day-picks">{["mon", "tue", "wed", "thu", "fri", "sat", "sun"].map(day => <button key={day} disabled={!draft.enabled} aria-pressed={window.days.includes(day)} onClick={() => row(index, { days: window.days.includes(day) ? window.days.filter(d => d !== day) : [...window.days, day] })}>{day.slice(0, 1).toUpperCase()}</button>)}</div>
                {(["start", "end"] as const).map(key => <label key={key}>{key === "start" ? "From" : "To"}<input aria-label={`Hours ${index + 1} ${key}`} type="time" step="900" disabled={!draft.enabled} value={window[key]} onChange={event => row(index, { [key]: event.target.value })} onKeyDown={event => {
                  if (event.key === "ArrowUp" || event.key === "ArrowDown") { event.preventDefault(); row(index, { [key]: shiftTime(window[key], event.key === "ArrowUp" ? 15 : -15) }); }
                }} /></label>)}
                <button disabled={!draft.enabled} onClick={() => row(index, { start: "00:00", end: "00:00" })}>All day</button>
                <button aria-label={`Remove hours ${index + 1}`} disabled={!draft.enabled} onClick={() => setDraft({ ...draft, weekly: draft.weekly.filter((_, i) => i !== index) })}>×</button>
                {window.end < window.start && <small>next day</small>}
              </div>)}
              <button disabled={!draft.enabled} onClick={() => setDraft({ ...draft, weekly: [...draft.weekly, { days: ["mon", "tue", "wed", "thu", "fri"], start: "22:00", end: "08:00" }] })}>+ Add hours</button>
            </div>
            <p className="muted">Overlapping hours count once. From and To at 00:00 means all day.</p>
          </article>
          <article className="card">
            <h2>Coming up</h2>
            <p>Everything finishes {when(completion(shown))}{oldFinish && oldFinish !== completion(shown) ? ` · was ${when(oldFinish)}` : ""}</p>
            {shown?.days.slice(0, 7).map(day => <div className="schedule-track-row" key={day.date}>
              <strong>{new Date(`${day.date}T12:00:00Z`).toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })}<small>{day.date.slice(5)}</small></strong>
              <div className="hours-track" aria-label={`${day.date} planned work`}>
                {day.windows.map((window, i) => <div key={i} className="hours-block read-only" style={{ left: `${timelineHour(window.start, day.date, shown.timezone) / 24 * 100}%`, width: `${Math.max(0, timelineHour(window.end, day.date, shown.timezone) - timelineHour(window.start, day.date, shown.timezone)) / 24 * 100}%` }} />)}
                {shown.timeline.filter(item => timelineHour(item.end, day.date, shown.timezone) > timelineHour(item.start, day.date, shown.timezone)).map((item, i) => <div key={i} className="planned-block" tabIndex={0} aria-label={`${filename(jobs.find(job => job.id === item.job_id)?.input || item.job_id)} done ${when(item.end)}`} style={{ left: `${timelineHour(item.start, day.date, shown.timezone) / 24 * 100}%`, width: `${Math.max(0, timelineHour(item.end, day.date, shown.timezone) - timelineHour(item.start, day.date, shown.timezone)) / 24 * 100}%` }}>
                  <span role="tooltip" className="timeline-tooltip">{filename(jobs.find(job => job.id === item.job_id)?.input || item.job_id)} · done {when(item.end)}{item.overrun_seconds ? ` · Finishing one step after your hours, about ${Math.ceil(item.overrun_seconds / 60)} min` : ""}</span>
                </div>)}
              </div><span>{day.run_hours.toFixed(1)} h</span>
            </div>)}
            <p className="muted">Allowed hours · Planned work. Edit the numeric rows above to change times.</p>
          </article>
        </div>
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
                  Ignore your hours and keep working until the queue is done or a time you choose.
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
                {overrideCheck && <p>New finish: {when(overrideCheck.finish)}</p>}
                <button disabled={!until || !overrideCheck} onClick={() => void override(new Date(until).toISOString())}>
                  Run now until a time…
                </button>
              </>
            )}
          </article>
        </div>
      </div>
    </section>
  );
}

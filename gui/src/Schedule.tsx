import { useEffect, useState } from "react";
import type { Api } from "./api";
import { completion, duration, when } from "./api";
import type { Plan, Schedule, Window } from "./types";
const days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const minutes = (time: string) =>
  Number(time.slice(0, 2)) * 60 + Number(time.slice(3));
const clock = (quarter: number) =>
  `${String(Math.floor(quarter / 4) % 24).padStart(2, "0")}:${String((quarter % 4) * 15).padStart(2, "0")}`;
function cells(schedule: Schedule) {
  const grid = days.map(() => Array<boolean>(96).fill(false));
  for (const window of schedule.weekly)
    for (const day of window.days) {
      const index = days.indexOf(day);
      if (index < 0) continue;
      const start = minutes(window.start) / 15,
        end = minutes(window.end) / 15;
      const count = (end - start + 96) % 96 || 96;
      for (let n = 0; n < count; n++) {
        const slot = start + n;
        grid[(index + Math.floor(slot / 96)) % 7][slot % 96] = true;
      }
    }
  return grid;
}
function windows(grid: boolean[][]): Schedule["weekly"] {
  const result: Schedule["weekly"] = [];
  for (let day = 0; day < 7; day++) {
    let slot = 0;
    while (slot < 96) {
      if (!grid[day][slot]) {
        slot++;
        continue;
      }
      const start = slot;
      while (slot < 96 && grid[day][slot]) slot++;
      result.push({ days: [days[day]], start: clock(start), end: clock(slot) });
    }
  }
  return result;
}
export function SchedulePage({
  api,
  value,
  applied,
  currentFinish,
}: {
  api: Api;
  value: Schedule;
  applied(): void;
  currentFinish?: string | null;
}) {
  const [draft, setDraft] = useState(value);
  const [preview, setPreview] = useState<{
    plan: Plan;
    next_window: Window | null;
  }>();
  const [error, setError] = useState("");
  const [painting, setPainting] = useState<boolean | null>(null);
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [date, setDate] = useState("");
  const [custom, setCustom] = useState<Window>({
    start: "22:00",
    end: "08:00",
  });
  const [override, setOverride] = useState("job-complete");
  const grid = cells(draft);
  const dirty = JSON.stringify(value) !== JSON.stringify(draft);
  useEffect(() => {
    setDraft(value);
  }, [value]);
  useEffect(() => {
    let alive = true;
    const timer = setTimeout(
      () =>
        api
          .call<{ plan: Plan; next_window: Window | null }>(
            "schedule/preview",
            "POST",
            draft,
          )
          .then((p) => {
            if (alive) {
              setPreview(p);
              setError("");
            }
          })
          .catch((e) => {
            if (alive) setError(e.message);
          }),
      150,
    );
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [api, draft]);
  useEffect(() => {
    const up = () => setPainting(null);
    window.addEventListener("pointerup", up);
    return () => window.removeEventListener("pointerup", up);
  }, []);
  const paint = (day: number, slot: number, on: boolean) => {
    const next = cells(draft);
    next[day][slot] = on;
    setDraft({ ...draft, weekly: windows(next) });
  };
  const setException = (value: Window[] | "off") => {
    if (!date) return;
    setDraft({
      ...draft,
      exceptions: [
        ...draft.exceptions.filter((e) => e.date !== date),
        { date, windows: value },
      ].sort((a, b) => a.date.localeCompare(b.date)),
    });
  };
  const count = new Date(
    Number(month.slice(0, 4)),
    Number(month.slice(5)),
    0,
  ).getDate();
  return (
    <section>
      <div className="page-heading">
        <div>
          <h1>Schedule</h1>
          <p>Choose when VideoEnhancer may work.</p>
        </div>
        <button
          className="primary"
          disabled={!dirty || !!error}
          onClick={async () => {
            try {
              await api.call("schedule", "PUT", draft);
              applied();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Save schedule
        </button>
      </div>
      <label className="check">
        <input
          type="checkbox"
          checked={draft.enabled}
          onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
        />
        Only run during these hours
      </label>
      {dirty && <p className="warning-text">Unsaved changes</p>}
      <p>
        Paint or drag to select hours. Each cell is 15 minutes. You can also
        edit the list below.
      </p>
      <div className="weekly-grid" aria-label="Weekly operating hours">
        <div className="hour-labels">
          {Array.from({ length: 24 }, (_, n) => (
            <span key={n}>{String(n).padStart(2, "0")}:00</span>
          ))}
        </div>
        {days.map((day, d) => (
          <div className="day-column" key={day}>
            <strong>{day.charAt(0).toUpperCase() + day.slice(1)}</strong>
            <div>
              {grid[d].map((on, slot) => (
                <button
                  key={slot}
                  aria-label={`${day} ${clock(slot)}`}
                  aria-pressed={on}
                  className={on ? "slot allowed" : "slot"}
                  onPointerDown={(e) => {
                    e.preventDefault();
                    setPainting(!on);
                    paint(d, slot, !on);
                  }}
                  onPointerEnter={() => {
                    if (painting !== null) paint(d, slot, painting);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      paint(d, slot, !on);
                    }
                  }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      <h2>Weekly hours</h2>
      <div className="window-list">
        {draft.weekly.map((w, i) => (
          <div className="window-row" key={i}>
            <label>
              Days
              <input
                aria-label={`Days for window ${i + 1}`}
                value={w.days.join(",")}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    weekly: draft.weekly.map((v, n) =>
                      n === i
                        ? {
                            ...v,
                            days: e.target.value
                              .toLowerCase()
                              .split(",")
                              .map((d) => d.trim()),
                          }
                        : v,
                    ),
                  })
                }
              />
            </label>
            <label>
              Start
              <input
                type="time"
                step="900"
                value={w.start}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    weekly: draft.weekly.map((v, n) =>
                      n === i ? { ...v, start: e.target.value } : v,
                    ),
                  })
                }
              />
            </label>
            <label>
              End
              <input
                type="time"
                step="900"
                value={w.end}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    weekly: draft.weekly.map((v, n) =>
                      n === i ? { ...v, end: e.target.value } : v,
                    ),
                  })
                }
              />
            </label>
            <button
              aria-label={`Delete window ${i + 1}`}
              onClick={() =>
                setDraft({
                  ...draft,
                  weekly: draft.weekly.filter((_, n) => n !== i),
                })
              }
            >
              Delete
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={() =>
          setDraft({
            ...draft,
            weekly: [
              ...draft.weekly,
              { days: days.slice(0, 5), start: "22:00", end: "08:00" },
            ],
          })
        }
      >
        + Add window
      </button>
      <p className="muted">
        Windows can cross midnight. Overlapping hours are treated as one allowed
        interval.
      </p>
      <h2>Date exceptions</h2>
      <label>
        Month
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
        />
      </label>
      <div className="calendar" aria-label="Exception dates">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <span key={d}>{d}</span>
        ))}
        {Array.from(
          { length: (new Date(`${month}-01T12:00:00`).getDay() + 6) % 7 },
          (_, i) => (
            <span key={`pad-${i}`} />
          ),
        )}
        {Array.from({ length: count }, (_, i) => {
          const day = `${month}-${String(i + 1).padStart(2, "0")}`;
          const exception = draft.exceptions.find((e) => e.date === day);
          return (
            <button
              key={day}
              aria-pressed={date === day}
              className={exception ? "exception-day" : ""}
              onClick={() => setDate(day)}
            >
              {i + 1}
              {exception?.windows === "off" ? " Off" : exception ? " •" : ""}
            </button>
          );
        })}
      </div>
      {date && (
        <div className="exception-editor">
          <strong>{date}</strong>
          <button onClick={() => setException("off")}>Mark Off</button>
          <label>
            Start
            <input
              type="time"
              step="900"
              value={custom.start}
              onChange={(e) => setCustom({ ...custom, start: e.target.value })}
            />
          </label>
          <label>
            End
            <input
              type="time"
              step="900"
              value={custom.end}
              onChange={(e) => setCustom({ ...custom, end: e.target.value })}
            />
          </label>
          <button onClick={() => setException([custom])}>
            Set custom hours
          </button>
        </div>
      )}
      <ul>
        {draft.exceptions.map((e) => (
          <li key={e.date}>
            {e.date}:{" "}
            {e.windows === "off"
              ? "Off"
              : e.windows.map((w) => `${w.start} → ${w.end}`).join(", ")}{" "}
            <button
              aria-label={`Delete exception ${e.date}`}
              onClick={() =>
                setDraft({
                  ...draft,
                  exceptions: draft.exceptions.filter((v) => v.date !== e.date),
                })
              }
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <h2>Temporary override</h2>
      <div className="toolbar">
        <label>
          Run now, ignore schedule
          <select
            value={override === "job-complete" ? override : "time"}
            onChange={(e) =>
              setOverride(
                e.target.value === "job-complete"
                  ? "job-complete"
                  : new Date(
                      Date.now() +
                        3600000 -
                        new Date().getTimezoneOffset() * 60000,
                    )
                      .toISOString()
                      .slice(0, 16),
              )
            }
          >
            <option value="job-complete">
              Until the current job completes
            </option>
            <option value="time">Until a chosen time</option>
          </select>
        </label>
        {override !== "job-complete" && (
          <input
            aria-label="Override end"
            type="datetime-local"
            value={override}
            onChange={(e) => setOverride(e.target.value)}
          />
        )}
        <button
          onClick={async () => {
            try {
              await api.call("schedule/override", "POST", {
                until:
                  override === "job-complete"
                    ? override
                    : new Date(override).toISOString(),
              });
              applied();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Run now
        </button>
        <button
          onClick={async () => {
            await api.call("schedule/override", "POST", { until: null });
            applied();
          }}
        >
          Clear override
        </button>
      </div>
      <div className="preview-panel">
        {preview?.next_window && (
          <p>
            <strong>Next window:</strong> {when(preview.next_window.start)} –{" "}
            {when(preview.next_window.end)} (
            {duration(
              (new Date(preview.next_window.end).getTime() -
                new Date(preview.next_window.start).getTime()) /
                1000,
            )}
            )
          </p>
        )}
        <p>
          All jobs finish {when(completion(preview?.plan))}
          {currentFinish && ` (was ${when(currentFinish)})`}
        </p>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
export { cells, windows };

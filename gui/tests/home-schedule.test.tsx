import { describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { HomePage, HistoryPage, historyWhen } from "../src/Home";
import { ScheduleView } from "../src/ScheduleView";
import type { Api } from "../src/api";
import type { Job, Plan, Queue, Schedule } from "../src/types";

const running: Job = {
  id: "running",
  input: "C:\\synthetic.mp4",
  output: "C:\\enhanced.mp4",
  state: "running",
  settings: {
    preset: "fast",
    short_side: 1080,
    fps: "2x",
    codec: "hevc",
    output_folder: "",
    start_with_windows: false,
    theme: "system",
    log_folder: "",
    advanced: {},
  },
  media: {
    display_width: 640,
    display_height: 360,
    cfr_fps: "30",
    duration: 60,
    frame_count: 1800,
  },
  estimate: { seconds: 750, low: 600, high: 900, calibrated: false },
  progress_percent: 40,
  phase: "enhance",
  step: "enhancing",
  step_percent: 40,
  segment: 1,
  segments: 2,
  log: "",
  preview_ready: false,
};
const failed: Job = {
  ...running,
  id: "failed",
  input: "C:\\locked.mp4",
  state: "failed",
  error:
    "Needs attention: this video's work files are locked by another program. Close that program, then Retry.",
};
const queue: Queue = {
  jobs: [failed, running],
  operations: [],
  completion: null,
};
const schedule: Schedule = {
  schema_version: 1,
  timezone: "UTC",
  enabled: true,
  weekly: [{ days: ["mon"], start: "22:00", end: "08:00" }],
  exceptions: [],
};
const plan: Plan = {
  timezone: "UTC",
  days: Array.from({ length: 7 }, (_, n) => ({
    date: `2026-10-${String(12 + n).padStart(2, "0")}`,
    windows: [],
    run_hours: 0,
    jobs: [],
  })),
  timeline: [],
  jobs: [],
};

describe("Home and History", () => {
  it("opens Problem without copying, hides seen failures and dismisses unseen failures", () => {
    const seen = vi.fn();
    const copy = vi.mocked(window.desktop.copy);
    copy.mockClear();
    const props = {
      queue,
      reconnecting: false,
      add: vi.fn(),
      action: vi.fn(),
      trial: vi.fn(),
      preview: vi.fn(),
      pauseAll: vi.fn(),
      navigate: vi.fn(),
      seen,
    };
    const health = {
      last_error: {
        message: "Close the program locking this video.",
        time: "2026-10-10T12:00:00Z",
        job_id: failed.id,
      },
    } as import("../src/types").Health;
    const view = render(<HomePage {...props} health={health} />);
    fireEvent.click(screen.getByRole("button", { name: "Problem · details" }));
    expect(
      screen.getByRole("dialog", { name: "Problem details" }),
    ).toBeTruthy();
    expect(copy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    expect(copy).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(seen).toHaveBeenCalledWith([failed.id]);
    view.rerender(<HomePage {...props} seenFailures={[failed.id]} />);
    expect(screen.queryByRole("button", { name: "Open History" })).toBeNull();
  });
  it("changes only an unstarted job mode and reports a rendered failed History card as seen", () => {
    const action = vi.fn(),
      seen = vi.fn();
    const queued = {
      ...running,
      id: "next",
      input: "C:\\next.mp4",
      state: "queued",
      segment: 0,
      progress_percent: 0,
    };
    const view = render(
      <HomePage
        queue={{ ...queue, jobs: [running, queued] }}
        reconnecting={false}
        add={vi.fn()}
        action={action}
        trial={vi.fn()}
        preview={vi.fn()}
        pauseAll={vi.fn()}
        navigate={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Actions for next.mp4" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Change mode" }));
    fireEvent.click(screen.getByRole("button", { name: "Standard" }));
    expect(action).toHaveBeenCalledWith(queued, "mode", { preset: "standard" });
    fireEvent.click(
      screen.getByRole("button", { name: "Actions for synthetic.mp4" }),
    );
    expect(screen.queryByRole("button", { name: "Change mode" })).toBeNull();
    view.unmount();
    render(
      <HistoryPage queue={queue} action={action} trial={vi.fn()} seen={seen} />,
    );
    expect(seen).toHaveBeenCalledWith([failed.id]);
    fireEvent.click(
      screen.getByRole("button", { name: "Actions for locked.mp4" }),
    );
    expect(screen.getByRole("button", { name: "Compare again" })).toBeTruthy();
  });
  it("uses local calendar dates, including a daylight-saving boundary", () => {
    const now = new Date(2026, 9, 10, 12);
    expect(historyWhen(new Date(2026, 9, 10, 6, 42).toISOString(), now)).toBe(
      "Today 06:42",
    );
    expect(historyWhen(new Date(2026, 9, 9, 23, 18).toISOString(), now)).toBe(
      "Yesterday 23:18",
    );
    expect(historyWhen(new Date(2026, 9, 5, 4, 55).toISOString(), now)).toBe(
      "Mon 10/05 04:55",
    );
    expect(
      historyWhen(
        new Date(2026, 10, 1, 23, 18).toISOString(),
        new Date(2026, 10, 2, 12),
      ),
    ).toBe("Yesterday 23:18");
  });
  it("shows only active work on Home and enables existing-result preview when a segment is durable", () => {
    const preview = vi.fn(),
      navigate = vi.fn();
    const props = {
      queue,
      reconnecting: false,
      add: vi.fn(),
      action: vi.fn(),
      trial: vi.fn(),
      preview,
      pauseAll: vi.fn(),
      navigate,
    };
    const view = render(<HomePage {...props} />);
    expect(screen.getByText("Now processing")).toBeTruthy();
    expect(screen.queryByText("locked.mp4")).toBeNull();
    expect(
      (
        screen.getByRole("button", {
          name: "Preview result",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Open History" }));
    expect(navigate).toHaveBeenCalledWith("History");
    view.rerender(
      <HomePage
        {...props}
        queue={{ ...queue, jobs: [{ ...running, preview_ready: true }] }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Preview result" }));
    expect(preview).toHaveBeenCalledWith(
      expect.objectContaining({ id: "running" }),
    );
  });
  it("filters terminal jobs, preserves the quarantine message and retries the failed job", () => {
    const action = vi.fn();
    render(<HistoryPage queue={queue} action={action} trial={vi.fn()} />);
    expect(screen.queryByText("synthetic.mp4")).toBeNull();
    expect(screen.getByText(failed.error!)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(action).toHaveBeenCalledWith(failed, "retry");
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search by file name" }),
      { target: { value: "missing" } },
    );
    expect(screen.queryByText("locked.mp4")).toBeNull();
  });
});

describe("Schedule week", () => {
  it("adds and deletes a block, drags its edge and opens a date-only context menu", () => {
    vi.stubGlobal("PointerEvent", MouseEvent);
    const call = vi.fn(async () => ({ plan }));
    render(
      <ScheduleView
        api={{ call } as unknown as Api}
        value={schedule}
        plan={plan}
        jobs={[]}
        applied={vi.fn()}
      />,
    );
    const track = document.querySelector<HTMLElement>(".hours-track")!;
    track.setPointerCapture = vi.fn();
    vi.spyOn(track, "getBoundingClientRect").mockReturnValue({
      left: 0,
      width: 960,
    } as DOMRect);
    fireEvent.click(track, { clientX: 360 });
    const added = screen.getByRole("group", { name: "2026-10-12 09:00–11:00" });
    fireEvent.keyDown(added, { key: "Delete" });
    expect(
      screen.queryByRole("group", { name: "2026-10-12 09:00–11:00" }),
    ).toBeNull();
    fireEvent.pointerDown(
      screen.getByRole("button", { name: "2026-10-12 start edge" }),
      { clientX: 880, pointerId: 1 },
    );
    fireEvent.pointerMove(track, { clientX: 900, pointerId: 1 });
    fireEvent.pointerUp(track, { pointerId: 1 });
    const changed = screen.getByRole("group", {
      name: "2026-10-12 22:30–24:00",
    });
    fireEvent.contextMenu(changed);
    fireEvent.click(
      screen.getByRole("menuitem", { name: "Only on Mon 10/12" }),
    );
    expect(
      screen.getByRole("button", { name: /2026-10-12 · 22:30/ }),
    ).toBeTruthy();
    vi.unstubAllGlobals();
  });
  it("edits an exception in place and deletes it", async () => {
    const call = vi.fn(async () => ({ plan }));
    render(
      <ScheduleView
        api={{ call } as unknown as Api}
        value={{
          ...schedule,
          exceptions: [{ date: "2026-10-12", windows: "off" }],
        }}
        plan={plan}
        jobs={[]}
        applied={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "2026-10-12 · Off all day" }),
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Off all day" }));
    fireEvent.change(screen.getByLabelText("Exception start"), {
      target: { value: "13:00" },
    });
    fireEvent.change(screen.getByLabelText("Exception end"), {
      target: { value: "18:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save day" }));
    await waitFor(
      () =>
        expect(call).toHaveBeenCalledWith(
          "schedule",
          "PUT",
          expect.objectContaining({
            exceptions: [
              {
                date: "2026-10-12",
                windows: [{ start: "13:00", end: "18:00" }],
              },
            ],
          }),
        ),
      { timeout: 2000 },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Delete exception 2026-10-12" }),
    );
    expect(screen.queryByRole("button", { name: /2026-10-12 ·/ })).toBeNull();
  });
  it("restarts the saved timer and undoes the most recent saved schedule", async () => {
    vi.useFakeTimers();
    try {
      const call = vi.fn(async () => ({ plan }));
      render(
        <ScheduleView
          api={{ call } as unknown as Api}
          value={schedule}
          plan={plan}
          jobs={[]}
          applied={vi.fn()}
        />,
      );
      fireEvent.keyDown(
        screen.getByRole("button", { name: "2026-10-12 start edge" }),
        { key: "ArrowRight" },
      );
      await act(() => vi.advanceTimersByTimeAsync(750));
      await act(() => vi.advanceTimersByTimeAsync(6000));
      fireEvent.keyDown(
        screen.getByRole("button", { name: "2026-10-12 start edge" }),
        { key: "ArrowRight" },
      );
      await act(() => vi.advanceTimersByTimeAsync(750));
      await act(() => vi.advanceTimersByTimeAsync(2000));
      expect(screen.getByRole("button", { name: "Undo" })).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "Undo" }));
      expect(
        screen.getByRole("group", { name: "2026-10-12 22:15–24:00" }),
      ).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
  it("previews, automatically saves a keyboard edit, and restores it through Undo", async () => {
    const call = vi.fn(async () => ({ plan })),
      applied = vi.fn();
    render(
      <ScheduleView
        api={{ call } as unknown as Api}
        value={schedule}
        plan={plan}
        jobs={[]}
        applied={applied}
      />,
    );
    fireEvent.keyDown(
      screen.getByRole("button", { name: "2026-10-12 start edge" }),
      { key: "ArrowRight" },
    );
    await waitFor(
      () =>
        expect(call).toHaveBeenCalledWith(
          "schedule",
          "PUT",
          expect.objectContaining({
            weekly: expect.arrayContaining([
              expect.objectContaining({ start: "22:15" }),
            ]),
          }),
        ),
      { timeout: 2000 },
    );
    expect(applied).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    await waitFor(
      () => expect(call).toHaveBeenCalledWith("schedule", "PUT", schedule),
      { timeout: 2000 },
    );
    expect(call).toHaveBeenCalledWith(
      "schedule/preview",
      "POST",
      expect.any(Object),
    );
  });
  it("runs through queue completion using the explicit override API", async () => {
    const call = vi.fn(async () => ({ plan }));
    render(
      <ScheduleView
        api={{ call } as unknown as Api}
        value={schedule}
        plan={plan}
        jobs={[]}
        applied={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Run now until the queue is done" }),
    );
    await waitFor(() =>
      expect(call).toHaveBeenCalledWith("schedule/override", "POST", {
        until: "queue-complete",
      }),
    );
  });
});

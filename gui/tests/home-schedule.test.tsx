import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HomePage, HistoryPage } from "../src/Home";
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

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueuePage } from "../src/Queue";
import { SchedulePage, cells, windows } from "../src/Schedule";
import { ConnectionBanner, ControlWarning } from "../src/App";
import { ModelsPage, PlanPage, SettingsPage, timelineHour } from "../src/Pages";
import type { Api } from "../src/api";
import type { Health, Job, Model, Schedule, Settings } from "../src/types";

const settings: Settings = {
  preset: "standard",
  short_side: 1080,
  fps: "2x",
  codec: "hevc",
  output_folder: "",
  start_with_windows: false,
  theme: "system",
  log_folder: "",
  advanced: {},
};
const job: Job = {
  id: "one",
  input: "C:\\synthetic.mp4",
  output: "C:\\enhanced\\synthetic.mp4",
  state: "running",
  settings,
  media: {
    display_width: 640,
    display_height: 360,
    cfr_fps: "30",
    duration: 60,
    frame_count: 1800,
  },
  estimate: { seconds: 750, low: 600, high: 900, calibrated: false },
  eta: "2026-10-09T03:40:00Z",
  progress_percent: 99.9,
  phase: "finalizing",
  step: "validating",
  step_percent: 40,
  segment: 2,
  segments: 2,
  log: "",
};
const schedule: Schedule = {
  schema_version: 1,
  timezone: "UTC",
  enabled: true,
  weekly: [{ days: ["mon"], start: "22:00", end: "08:00" }],
  exceptions: [],
};
const api = {
  call: vi.fn(async () => ({ plan: { jobs: [] }, next_window: null })),
  blob: vi.fn(),
} as unknown as Api;
describe("Queue", () => {
  it("shows concrete ETA and engine finalization without prematurely showing 100%", () => {
    render(
      <QueuePage
        queue={{ jobs: [job], completion: job.eta!, operations: [] }}
        add={vi.fn()}
        action={vi.fn()}
        trial={vi.fn()}
      />,
    );
    expect(screen.getByText("99.9%")).toBeTruthy();
    expect(screen.getByText("Finalizing: validating")).toBeTruthy();
    expect(screen.getByText(/All jobs finish/)).toBeTruthy();
    expect(screen.getByText("uncalibrated")).toBeTruthy();
  });
  it("offers keyboard reorder and actionable error details", () => {
    const action = vi.fn();
    render(
      <QueuePage
        queue={{
          jobs: [
            { ...job, state: "failed", error: "The component is missing." },
          ],
          completion: null,
          operations: [],
        }}
        add={vi.fn()}
        action={action}
        trial={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Actions for synthetic.mp4" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Move to top" }));
    expect(action).toHaveBeenCalledWith(
      expect.objectContaining({ id: "one" }),
      "move",
      { position: 1 },
    );
    expect(screen.getByText("The component is missing.")).toBeTruthy();
  });
});
describe("Schedule", () => {
  it("preserves crossing midnight when converting between grid and list", () => {
    const grid = cells(schedule);
    expect(grid[0][88]).toBe(true);
    expect(grid[1][31]).toBe(true);
    expect(grid[1][32]).toBe(false);
    expect(cells({ ...schedule, weekly: windows(grid) })).toEqual(grid);
  });
  it("keeps edits unsaved until Save and updates the shared API schedule", async () => {
    const applied = vi.fn();
    render(<SchedulePage api={api} value={schedule} applied={applied} />);
    fireEvent.keyDown(screen.getByRole("button", { name: "mon 12:00" }), {
      key: "Enter",
    });
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: "mon 12:00" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Save schedule" }));
    await waitFor(() => expect(applied).toHaveBeenCalled());
    expect(api.call).toHaveBeenCalledWith(
      "schedule",
      "PUT",
      expect.objectContaining({ weekly: expect.any(Array) }),
    );
  });
  it("creates and deletes an Off exception", () => {
    render(<SchedulePage api={api} value={schedule} applied={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "15" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark Off" }));
    expect(screen.getByText(/: Off/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Delete exception/ }));
    expect(screen.queryByText(/: Off/)).toBeNull();
  });
});
describe("Recovery and settings", () => {
  it("places plan blocks in the engine timezone across the daylight-saving jump", () => {
    expect(
      timelineHour("2026-03-08T08:00:00Z", "2026-03-08", "America/Los_Angeles"),
    ).toBe(0);
    expect(
      timelineHour("2026-03-08T10:00:00Z", "2026-03-08", "America/Los_Angeles"),
    ).toBe(3);
    expect(
      timelineHour("2026-03-09T07:00:00Z", "2026-03-08", "America/Los_Angeles"),
    ).toBe(24);
  });
  it("shows unreachable Retry while keeping the existing queue visible", () => {
    const retry = vi.fn();
    render(
      <>
        <ConnectionBanner error="Connection closed" retry={retry} />
        <QueuePage
          queue={{ jobs: [job], operations: [], completion: null }}
          add={vi.fn()}
          action={vi.fn()}
          trial={vi.fn()}
        />
      </>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(screen.getByRole("heading", { name: "synthetic.mp4" })).toBeTruthy();
  });
  it("blocks processing with an explained Smart App Control message", () => {
    render(
      <ControlWarning
        health={
          {
            smart_app_control: {
              blocked: true,
              status: "enforced",
              message: "Smart App Control blocked FFmpeg",
            },
          } as Health
        }
        retry={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain(
      "Processing cannot continue",
    );
    expect(screen.getByRole("link").getAttribute("href")).toContain(
      "TROUBLESHOOTING",
    );
  });
  it("saves startup preference and copies diagnostics", async () => {
    const saved = vi.fn();
    render(
      <SettingsPage
        api={api}
        value={settings}
        saved={saved}
        calibrate={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("checkbox", { name: /Start with Windows/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => expect(saved).toHaveBeenCalled());
    expect(api.call).toHaveBeenCalledWith(
      "settings",
      "PUT",
      expect.objectContaining({ start_with_windows: true }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Copy diagnostics" }));
    expect(window.desktop.copy).toHaveBeenCalled();
  });
  it("renders plan progress and delegates scenario changes to the engine", () => {
    const change = vi.fn();
    render(
      <PlanPage
        jobs={[job]}
        scenario="expected"
        change={change}
        calibrate={vi.fn()}
        plan={{
          timezone: "UTC",
          jobs: [{ job_id: "one", completion: job.eta! }],
          timeline: [],
          days: [
            {
              date: "2026-10-09",
              windows: [],
              run_hours: 1.2,
              jobs: [{ job_id: "one", start_percent: 8, end_percent: 50 }],
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/8% → 50%/)).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "worst" },
    });
    expect(change).toHaveBeenCalledWith("worst");
  });
});

describe("Models", () => {
  const model: Model = {
    id: "fixture",
    display_name: "Fixture model",
    task: "restore",
    architecture: "basicvsrpp",
    licence: "Fixture non-commercial licence",
    commercial_use_allowed: false,
    builtin: true,
    weights_verified: false,
    size_bytes: 0,
    weights: { url: "https://example.invalid/fixture", sha256: "a".repeat(64) },
  };
  it("requires explicit acceptance with licence and source before requesting a download", () => {
    const operate = vi.fn();
    render(
      <ModelsPage
        api={api}
        models={[model]}
        refresh={vi.fn()}
        operate={operate}
        operations={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Download…" }));
    expect(operate).not.toHaveBeenCalled();
    expect(screen.getByText(`Licence: ${model.licence}`)).toBeTruthy();
    expect(screen.getByText(model.weights.url!)).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "Accept licence and download" }),
    );
    expect(operate).toHaveBeenCalledWith("models/fixture/download", {
      agree: true,
      licence: model.licence,
    });
  });
  it("shows folder-validation errors and confirms user-model removal", async () => {
    const call = vi
      .fn()
      .mockRejectedValueOnce(new Error("The weights do not match the SHA-256."))
      .mockResolvedValue({});
    vi.mocked(window.desktop.files).mockResolvedValueOnce(["C:\\FixtureModel"]);
    const refresh = vi.fn();
    render(
      <ModelsPage
        api={{ ...api, call } as Api}
        models={[{ ...model, builtin: false }]}
        refresh={refresh}
        operate={vi.fn()}
        operations={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Add model…" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("SHA-256"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove…" }));
    expect(call).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Remove model" }));
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    expect(call).toHaveBeenLastCalledWith("models/fixture", "DELETE");
  });
});

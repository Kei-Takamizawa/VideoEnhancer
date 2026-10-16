import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HomePage } from "../src/Home";
import { ConnectionBanner, ControlWarning } from "../src/App";
import { ModelsPage, SettingsPage, timelineHour } from "../src/Pages";
import type { Api } from "../src/api";
import type { Health, Job, Model, Settings } from "../src/types";

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
const api = {
  call: vi.fn(async () => ({ plan: { jobs: [] }, next_window: null })),
  blob: vi.fn(),
} as unknown as Api;
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
        <HomePage
          queue={{ jobs: [job], operations: [], completion: null }}
          add={vi.fn()}
          action={vi.fn()}
          trial={vi.fn()} preview={vi.fn()} pauseAll={vi.fn()} navigate={vi.fn()} reconnecting={false}
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
    await waitFor(() => expect(saved).toHaveBeenCalled());
    expect(api.call).toHaveBeenCalledWith(
      "settings",
      "PUT",
      expect.objectContaining({ start_with_windows: true }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Copy diagnostics" }));
    expect(window.desktop.copy).toHaveBeenCalled();
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
    publisher_url: "https://example.invalid/publisher",
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
    fireEvent.click(screen.getByRole("button", { name: "Install" }));
    expect(operate).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Model publisher’s page" }).getAttribute("href")).toBe(model.publisher_url);
    expect(screen.getByText(`Licence: ${model.licence}`)).toBeTruthy();
    expect(screen.getByText(model.weights.url!)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Accept licence and download" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "I accept this licence" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Accept licence and download" }),
    );
    expect(operate).toHaveBeenCalledWith("models/fixture/download", {
      agree: true,
      licence: model.licence,
    });
  });
  it("shows the active download instead of another Install button", () => {
    const operate = vi.fn();
    render(<ModelsPage api={api} models={[model]} refresh={vi.fn()} operate={operate} operations={[{ id: "download", kind: "download", state: "running", phase: "12 MB of 40 MB", percent: 30, request: { model_id: model.id } }]} />);
    expect(screen.queryByRole("button", { name: "Install" })).toBeNull();
    expect(screen.getByText(/30%/)).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Downloading Fixture model" }).getAttribute("value")).toBe("30");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(operate).toHaveBeenCalledWith("operations/download/cancel");
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
        models={[{ ...model, builtin: false, weights_verified: true }]}
        refresh={refresh}
        operate={vi.fn()}
        operations={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Add my own model…" }));
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("SHA-256"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Uninstall" }));
    expect(call).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Remove model" }));
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    expect(call).toHaveBeenLastCalledWith("models/fixture", "DELETE");
  });
});
it("shows finalization and moves queued videos with Alt arrows", () => {
  const action = vi.fn();
  const pending = { ...job, id: "next", position: 2, state: "queued", input: "C:\\next.mp4", segment: 0 };
  render(<HomePage queue={{ jobs: [job, pending, { ...pending, id: "third", input: "C:\\third.mp4" }], operations: [], completion: null }} reconnecting={false} add={vi.fn()} action={action} trial={vi.fn()} preview={vi.fn()} pauseAll={vi.fn()} navigate={vi.fn()} />);
  expect(screen.getByText("Finishing: checking the file")).toBeTruthy();
  const row = screen.getByRole("heading", { name: "next.mp4" }).closest("article")!;
  fireEvent.keyDown(row, { key: "ArrowUp", altKey: true });
  expect(action).toHaveBeenCalledWith(pending, "move", { position: 1 });
  fireEvent.keyDown(row, { key: "ArrowDown", altKey: true });
  expect(action).toHaveBeenLastCalledWith(pending, "move", { position: 3 });
  expect(action).toHaveBeenCalledTimes(2);
});

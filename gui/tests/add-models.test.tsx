import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AddDialog } from "../src/Queue";
import { ModelsPage, SettingsPage } from "../src/Pages";
import type { Api } from "../src/api";
import type { Health, Model, Settings } from "../src/types";

const settings: Settings = {
  preset: "standard",
  short_side: 1080,
  fps: "2x",
  codec: "hevc",
  output_folder: "",
  start_with_windows: false,
  theme: "dark",
  log_folder: "",
  advanced: {},
};
const model: Model = {
  id: "cleanup",
  display_name: "Fixture cleanup",
  architecture: "spandrel",
  task: "restore",
  licence: "MIT",
  commercial_use_allowed: true,
  builtin: false,
  size_bytes: 100,
  weights_verified: true,
  weights: { sha256: "a".repeat(64) },
  catalog: {
    category: "cleanup",
    title: "Gentle fixture",
    description: "Fixture only",
    look_change: "very_little",
    invents_detail: "low",
    flicker: "possible",
    licence_plain: "Free for any use",
  },
};

it("Add and Settings show the same unavailable AV1 reason", () => {
  const api = { call: vi.fn().mockResolvedValue({}) } as unknown as Api;
  const reason = "AV1 hardware encoding is unavailable: driver rejected encode";
  const add = render(
    <AddDialog
      api={api}
      files={[]}
      defaults={settings}
      models={[]}
      av1={false}
      av1Reason={reason}
      close={vi.fn()}
      saved={vi.fn()}
      trial={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByText("More options"));
  expect(
    screen.getByRole("option", { name: "AV1" }).hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByText(reason)).toBeTruthy();
  add.unmount();
  render(
    <SettingsPage
      api={api}
      value={settings}
      health={
        { av1_supported: false, av1_unavailable_reason: reason } as Health
      }
      saved={vi.fn()}
      calibrate={vi.fn()}
    />,
  );
  expect(
    screen.getByRole("option", { name: "AV1" }).hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByText(reason)).toBeTruthy();
});

it("adds while preparing, keeps mode and model choices when returning from Compare", async () => {
  const saved = vi.fn(),
    trial = vi.fn();
  const call = vi.fn().mockImplementation((route: string) =>
    Promise.resolve(
      route === "estimate"
        ? {
            files: { "C:\\fixture.mp4": { media: {
              cfr_fps: "30",
              duration: 60,
              display_width: 640,
              display_height: 360,
              frame_count: 1800,
            },
            presets: { standard: { seconds: 600 }, fast: { seconds: 60 } },
            warnings: [],
            output: "C:\\enhanced\\fixture.mp4",
            } }, presets: { standard: { seconds: 600 }, fast: { seconds: 60 } },
          }
        : { id: "queued" },
    ),
  );
  render(
    <AddDialog
      api={{ call } as unknown as Api}
      files={["C:\\fixture.mp4"]}
      defaults={settings}
      models={[model]}
      saved={saved}
      close={vi.fn()}
      trial={trial}
    />,
  );
  fireEvent.click(screen.getByText("More options"));
  fireEvent.change(screen.getByLabelText("Cleanup model"), {
    target: { value: "cleanup" },
  });
  await waitFor(() =>
    expect(
      screen
        .getByRole("button", { name: "Try models first" })
        .hasAttribute("disabled"),
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: "Try models first" }));
  expect(trial.mock.calls[0][1].restore_model).toBe("cleanup");
  fireEvent.click(screen.getByRole("button", { name: /^Fast/ }));
  fireEvent.click(screen.getByRole("button", { name: "Add to queue" }));
  await waitFor(() => expect(saved).toHaveBeenCalled());
  expect(call).toHaveBeenCalledWith(
    "queue",
    "POST",
    expect.objectContaining({
      settings: expect.objectContaining({
        preset: "fast",
        restore_model: "cleanup",
      }),
    }),
  );
  expect(screen.getByText(/Output: 1080p/)).toBeTruthy();
});

it("changes only the new-job default and exposes exact model details", async () => {
  const call = vi.fn(async () => ({})),
    refresh = vi.fn();
  render(
    <ModelsPage
      api={{ call } as unknown as Api}
      models={[model]}
      settings={settings}
      refresh={refresh}
      operate={vi.fn()}
      operations={[]}
    />,
  );
  expect(screen.getByText("Cleanup · 1")).toBeTruthy();
  expect(
    screen
      .getByRole("button", { name: "Faces · coming later" })
      .hasAttribute("disabled"),
  ).toBe(true);
  expect(screen.getByText("Not measured here")).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Actions for Gentle fixture" }),
  );
  fireEvent.click(screen.getByRole("menuitem", { name: "Make it my default" }));
  await waitFor(() => expect(refresh).toHaveBeenCalled());
  expect(call).toHaveBeenCalledWith("settings", "PUT", {
    restore_model: "cleanup",
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Actions for Gentle fixture" }),
  );
  fireEvent.click(screen.getByRole("menuitem", { name: "Details" }));
  expect(screen.getByText(/SHA-256: aaaaaaaaaaaa/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Copy" }));
  expect(window.desktop.copy).toHaveBeenCalledWith(model.weights.sha256);
});

it("keeps DRUNet on one card and persists its three strength choices", async () => {
  const call = vi.fn(async () => ({}));
  render(
    <ModelsPage
      api={{ call } as unknown as Api}
      models={[{ ...model, id: "drunet-deblock", architecture: "drunet" }]}
      settings={settings}
      refresh={vi.fn()}
      operate={vi.fn()}
      operations={[]}
    />,
  );
  expect(screen.getAllByText("Gentle fixture")).toHaveLength(1);
  const selector = screen.getByLabelText("Strength");
  expect(selector.querySelectorAll("option")).toHaveLength(3);
  fireEvent.change(selector, { target: { value: "strong" } });
  await waitFor(() =>
    expect(call).toHaveBeenCalledWith("settings", "PUT", {
      restore_strength: "strong",
    }),
  );
});
it.each([
  ["Output too small for cleanup", "Use 1080", true],
  ["Output too small for AV1", "Use HEVC", true],
  ["Insufficient space", "Choose a folder…", true],
  ["HDR is not supported", "Remove it", true],
  ["Windows Smart App Control is blocking", "Read instructions", true],
  ["The chosen size is smaller than the source", "Use Keep", false],
])("warning %s offers %s and blocks=%s", async (warning, fix, blocked) => {
  const estimate = { seconds: 100, low: 75, high: 125, calibrated: false };
  const call = vi.fn(async () => ({ files: { "C:\\fixture.mp4": { media: { display_width: 720, display_height: 1280, duration: 30, frame_count: 900, cfr_fps: "30" }, presets: { standard: estimate, fast: estimate }, warnings: [warning], output: "C:\\output.mp4" } }, presets: { standard: estimate, fast: estimate } }));
  render(<AddDialog api={{ call } as unknown as Api} files={["C:\\fixture.mp4"]} defaults={settings} models={[]} saved={vi.fn()} close={vi.fn()} trial={vi.fn()} />);
  await screen.findByText(warning);
  expect(screen.getAllByRole(fix === "Read instructions" ? "link" : "button", { name: fix }).length).toBeGreaterThan(0);
  expect((screen.getByRole("button", { name: "Add to queue" }) as HTMLButtonElement).disabled).toBe(blocked);
  if (fix === "Use 1080" || fix === "Use HEVC" || fix === "Use Keep") {
    fireEvent.click(screen.getByRole("button", { name: fix }));
    const update = fix === "Use 1080" ? { short_side: 1080 } : fix === "Use HEVC" ? { codec: "hevc" } : { short_side: "keep" };
    await waitFor(() => expect(call).toHaveBeenCalledWith("estimate", "POST", expect.objectContaining({ settings: expect.objectContaining(update) }), expect.any(AbortSignal)));
  }
});

it("Add distinguishes a chosen model with unknown speed from an uncalibrated GPU", async () => {
  const known = { seconds: 50, low: 40, high: 60, calibrated: true };
  const unknown = { ...known, calibrated: false, unknown_models: ["fixture-without-reference"], profile_source: "builtin" };
  const file = "C:\\synthetic\\unknown.mp4";
  const media = { display_width: 720, display_height: 1280, cfr_fps: "30", duration: 30, frame_count: 900 };
  const api = { call: vi.fn().mockResolvedValue({ files: { [file]: { media, warnings: [], output: "C:\\synthetic\\output.mp4", presets: { standard: unknown, fast: known } } }, presets: { standard: unknown, fast: known } }) } as unknown as Api;
  render(<AddDialog api={api} files={[file]} defaults={settings} models={[]} close={vi.fn()} saved={vi.fn()} trial={vi.fn()} />);
  await waitFor(() => expect(screen.getByText("Speed unknown for fixture-without-reference. Run speed calibration.")).toBeTruthy());
  expect(screen.queryByText("uncalibrated")).toBeNull();
  const standard = screen.getByRole("button", { name: /^Standard Cleans/ });
  expect(standard.textContent).toContain("Speed unknown");
  expect(standard.textContent).not.toContain("of work");
});

it("Settings shows the measured-driver note, calibration duration and Cancel", async () => {
  const call = vi.fn().mockResolvedValue({});
  render(<SettingsPage api={{ call } as unknown as Api} value={settings} health={{ speed_profile: { source: "measured", driver_note: "Speed measured with driver X. This PC now has driver Y.", calibration_minutes: 3 } } as Health} saved={vi.fn()} calibrate={vi.fn()} operation={{ id: "calibration", kind: "calibrate", state: "running", phase: "Measuring" }} />);
  expect(screen.getByText("Speed measured with driver X. This PC now has driver Y.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Run speed calibration (about 3 min)" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  await waitFor(() => expect(call).toHaveBeenCalledWith("operations/calibration/cancel", "POST"));
});

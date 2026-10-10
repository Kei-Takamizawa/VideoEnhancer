import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AddDialog } from "../src/Queue";
import { ModelsPage } from "../src/Pages";
import type { Api } from "../src/api";
import type { Model, Settings } from "../src/types";

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

it("adds while preparing, keeps mode and model choices when returning from Compare", async () => {
  const saved = vi.fn(),
    trial = vi.fn();
  const call = vi.fn().mockImplementation((route: string) =>
    Promise.resolve(
      route === "estimate"
        ? {
            media: {
              cfr_fps: "30",
              duration: 60,
              display_width: 640,
              display_height: 360,
              frame_count: 1800,
            },
            presets: { standard: { seconds: 600 }, fast: { seconds: 60 } },
            warnings: [],
            output: "C:\\enhanced\\fixture.mp4",
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
  expect(screen.getByText(`SHA-256: ${model.weights.sha256}`)).toBeTruthy();
});

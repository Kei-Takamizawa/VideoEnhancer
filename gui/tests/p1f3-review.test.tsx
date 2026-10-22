import { afterEach, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { Notice } from "../src/Notice";
import { ActionButton } from "../src/ActionButton";
import { SettingsPage } from "../src/Pages";
import type { Api } from "../src/api";
import type { Operation, Settings } from "../src/types";

afterEach(() => vi.useRealTimers());

it("A5 shows and copies a fake startup-entry failure beside the toggle", async () => {
  const original = window.desktop.startupStatus;
  const message = "Windows didn't accept the startup entry: Synthetic registry failure";
  window.desktop.startupStatus = vi.fn().mockResolvedValue(message);
  const settings: Settings = { preset: "standard", short_side: 1080, fps: "2x", codec: "hevc", output_folder: "", start_with_windows: false, theme: "dark", log_folder: "", advanced: {} };
  const api = { call: vi.fn().mockResolvedValue({ folder: "isolated", cleanup: [] }) } as unknown as Api;
  try {
    render(<SettingsPage api={api} value={settings} saved={vi.fn()} calibrate={vi.fn()} />);
    await act(async () => {});
    const error = screen.getByRole("alert");
    expect(error.textContent).toContain(message);
    fireEvent.click(error.querySelector<HTMLButtonElement>('button[aria-label="Copy message"]')!);
    await act(async () => {});
    expect(window.desktop.copy).toHaveBeenCalledWith(message);
  } finally { window.desktop.startupStatus = original; }
});

it("B1 keeps Copied for 1.5 seconds before fading out", async () => {
  vi.useFakeTimers();
  render(<ActionButton onClick={() => Promise.resolve()}>Copy diagnostics</ActionButton>);
  fireEvent.click(screen.getByRole("button", { name: "Copy diagnostics" }));
  await act(async () => {});
  act(() => vi.advanceTimersByTime(1500));
  expect(screen.getByRole("status").textContent).toBe("Copied");
  act(() => vi.advanceTimersByTime(200));
  expect(screen.queryByRole("status")).toBeNull();
});

it("B1 confirms only after copy resolves and reports a rejected copy", async () => {
  let resolve: () => void = () => {};
  const copied = new Promise<void>(done => { resolve = done; });
  const view = render(<ActionButton onClick={() => copied}>Copy details</ActionButton>);
  fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
  expect(screen.queryByRole("status")).toBeNull();
  await act(async () => resolve());
  expect(screen.getByRole("status").textContent).toBe("Copied");
  view.rerender(<ActionButton onClick={() => Promise.reject(new Error("Synthetic clipboard busy"))}>Copy details</ActionButton>);
  fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
  await act(async () => {});
  expect(screen.getByRole("alert").textContent).toBe("Couldn't copy: Synthetic clipboard busy");
  window.desktop.copy = vi.fn().mockResolvedValue(undefined);
  fireEvent.click(screen.getByRole("button", { name: "Copy message" }));
  await act(async () => {});
  expect(window.desktop.copy).toHaveBeenCalledWith("Couldn't copy: Synthetic clipboard busy");
  expect(screen.getByRole("status").textContent).toBe("Copied");
});

it("A4 labels a persisted calibration failure as the last attempt, with Run again", async () => {
  const settings: Settings = { preset: "standard", short_side: 1080, fps: "2x", codec: "hevc", output_folder: "", start_with_windows: false, theme: "dark", log_folder: "", advanced: {} };
  const api = { call: vi.fn().mockResolvedValue({ folder: "isolated", cleanup: [] }) } as unknown as Api;
  const operation = { id: "old", kind: "calibrate", state: "failed", created_at: "2020-01-01T00:00:00Z", error: "Synthetic old failure" } as Operation;
  render(<SettingsPage api={api} value={settings} saved={vi.fn()} calibrate={vi.fn()} operation={operation} />);
  await act(async () => {});
  expect(screen.getByText(/The last calibration on .* failed: Synthetic old failure/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Run again" })).toBeTruthy();
});

it("B1 copies the complete message and confirms next to its button", async () => {
  window.desktop.copy = vi.fn().mockResolvedValue(undefined);
  render(<Notice identity="failure">Failed: 日本語 / error 90</Notice>);
  fireEvent.click(screen.getByRole("button", { name: "Copy message" }));
  await act(async () => {});
  expect(window.desktop.copy).toHaveBeenCalledWith("Failed: 日本語 / error 90");
  expect(screen.getByRole("status").textContent).toBe("Copied");
});

it("B2 fades action errors after eight seconds, pauses on hover, and retains conditions", () => {
  vi.useFakeTimers();
  render(<Notice identity="save" {...{ autoDismiss: true }}>Save failed</Notice>);
  fireEvent.mouseEnter(screen.getByRole("alert"));
  act(() => vi.advanceTimersByTime(10000));
  expect(screen.getByRole("alert").textContent).toContain("Save failed");
  fireEvent.mouseLeave(screen.getByRole("alert"));
  act(() => vi.advanceTimersByTime(8000));
  expect(screen.getByRole("alert").className).toContain("notice-fading");
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.queryByRole("alert")).toBeNull();
  render(<Notice identity="engine">Engine unavailable</Notice>);
  act(() => vi.advanceTimersByTime(20000));
  expect(screen.getByRole("alert").textContent).toContain("Engine unavailable");
});

it("B2 holds an action error while its copy control has keyboard focus", () => {
  vi.useFakeTimers();
  render(<Notice identity="focused" autoDismiss>Focused action failure</Notice>);
  const copy = screen.getByRole("button", { name: "Copy message" });
  fireEvent.focus(copy);
  act(() => vi.advanceTimersByTime(20000));
  expect(screen.getByRole("alert").textContent).toContain("Focused action failure");
  fireEvent.blur(copy, { relatedTarget: document.body });
  act(() => vi.advanceTimersByTime(8000));
  expect(screen.getByRole("alert").className).toContain("notice-fading");
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.queryByRole("alert")).toBeNull();
});

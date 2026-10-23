import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { HistoryDetail } from "../src/HistoryDetail";
import type { Job } from "../src/types";

const job = { id: "a".repeat(32), input: "synthetic.mp4", output: "output.mp4", state: "done", settings: { preset: "fast", codec: "h264" } } as Job;
it("keeps the spill condition and its Copy control visible", async () => {
  const original = window.desktop;
  const copy = vi.fn(async () => {});
  window.desktop = { ...original, copy };
  vi.useFakeTimers();
  const view = render(<HistoryDetail job={{ ...job, gpu_memory_notice: true }} close={() => {}} action={() => {}} compare={() => {}} />);
  try {
    const notice = screen.getByText("Some parts ran slower because GPU memory was full.");
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(notice.isConnected).toBe(true);
    fireEvent.click(notice.querySelector("button")!);
    expect(copy).toHaveBeenCalledWith("Some parts ran slower because GPU memory was full.");
  } finally { view.unmount(); vi.useRealTimers(); window.desktop = original; }
});
it("uses the folder date in an unreadable detail title while retaining the Copy identity", () => {
  const action = vi.fn();
  render(<HistoryDetail job={{ ...job, input: job.id, record_error: true, unreadable_record: true, record_folder_date: "2026-10-22T12:00:00Z" }} close={() => {}} action={action} compare={() => {}} />);
  expect(screen.getByRole("heading").textContent).toBe(`Unreadable record · ${new Date("2026-10-22T12:00:00Z").toLocaleDateString()}`);
  fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
  expect(action).toHaveBeenCalledWith(expect.objectContaining({ id: job.id }), "copy");
});

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HistoryDetail } from "../src/HistoryDetail";
import type { Job } from "../src/types";

afterEach(() => { delete window.desktop.openPlayer; delete window.desktop.closePlayer; delete window.desktop.onPlayerError; });
it.each(["Missing helper", "Missing DLL", "DLL load failure", "D3D11 device failure"])("retains HTML5 and History actions after %s", async reason => {
  window.desktop.openPlayer = vi.fn(async () => { throw new Error(reason); });
  window.desktop.closePlayer = vi.fn(async () => {});
  const job = { id: "a".repeat(32), input: "synthetic.mp4", output: "synthetic-output.mp4", state: "done", settings: { codec: "h264", preset: "standard" }, media: { display_width: 320, display_height: 180 } } as Job;
  const { container } = render(<HistoryDetail job={job} close={() => {}} action={() => {}} compare={() => {}} />);
  await waitFor(() => expect(container.querySelector("video")?.src).toContain(job.id));
  expect(screen.getByRole("button", { name: "Show in folder" })).toBeTruthy();
  expect(screen.getByText("Playing with the basic player.")).toBeTruthy();
});

it("shows an error only when HTML5 also fails after native rejection and error event", async () => {
  let notify: Parameters<NonNullable<typeof window.desktop.onPlayerError>>[0] | undefined;
  window.desktop.onPlayerError = vi.fn(callback => { notify = callback; return () => {}; });
  window.desktop.openPlayer = vi.fn(async () => { throw new Error("Missing DLL"); });
  const job = { id: "b".repeat(32), input: "synthetic.mp4", state: "done", settings: { codec: "h264", preset: "standard" } } as Job;
  const { container } = render(<HistoryDetail job={job} close={() => {}} action={() => {}} compare={() => {}} />);
  await waitFor(() => expect(container.querySelector("video")).toBeTruthy());
  act(() => notify?.({ id: job.id, message: "Native DLL load failure" }));
  expect(screen.getByText("Playing with the basic player.")).toBeTruthy();
  expect(screen.queryByText(/can't be played/)).toBeNull();
  expect(screen.queryByText("Native DLL load failure")).toBeNull();
  expect(screen.queryByRole("button", { name: /Open in.*player/ })).toBeNull();
  fireEvent.error(container.querySelector("video")!);
  expect(screen.getByText("This video can't be played here.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Open in default player" })).toBeTruthy();
  expect(screen.queryByText("Playing with the basic player.")).toBeNull();
});

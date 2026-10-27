import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HistoryDetail } from "../src/HistoryDetail";
import type { Job } from "../src/types";

afterEach(() => { delete window.desktop.openPlayer; delete window.desktop.closePlayer; });
it.each(["Missing helper", "Missing DLL", "DLL load failure", "D3D11 device failure"])("retains HTML5 and History actions after %s", async reason => {
  window.desktop.openPlayer = vi.fn(async () => { throw new Error(reason); });
  window.desktop.closePlayer = vi.fn(async () => {});
  const job = { id: "a".repeat(32), input: "synthetic.mp4", output: "synthetic-output.mp4", state: "done", settings: { codec: "h264", preset: "standard" }, media: { display_width: 320, display_height: 180 } } as Job;
  const { container } = render(<HistoryDetail job={job} close={() => {}} action={() => {}} compare={() => {}} />);
  await waitFor(() => expect(container.querySelector("video")?.src).toContain(job.id));
  expect(screen.getByRole("button", { name: "Show in folder" })).toBeTruthy();
  expect(screen.getByText("This video can't be played here. Open it in your default player instead.")).toBeTruthy();
});

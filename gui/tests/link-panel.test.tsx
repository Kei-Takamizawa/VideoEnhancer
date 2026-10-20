import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LinkPanel } from "../src/LinkPanel";
import { AddDialog } from "../src/Queue";
import { HistoryDetail } from "../src/HistoryDetail";
import { HistoryPage } from "../src/Home";
import type { Api } from "../src/api";
import type { Job, Settings } from "../src/types";

it("keeps an unknown-size failed link visible in History with Retry", () => {
  const job = { id: "a".repeat(32), state: "failed", input: "D:/Synthetic/video.mkv", output: "D:/Synthetic/out.mp4", settings: { codec: "hevc", preset: "fast" }, media: { display_width: null, display_height: null }, estimate: { seconds: 0 }, error: "Synthetic download failed", source: { url: "http://localhost/video" } } as unknown as Job;
  render(<HistoryPage queue={{ jobs: [job], operations: [], completion: null }} action={vi.fn()} trial={vi.fn()} />);
  const card = screen.getByRole("button", { name: "video.mkv" });
  expect(Number.parseFloat(card.style.width)).toBeGreaterThan(0);
  fireEvent.click(card);
  expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
});

it("refreshes estimates only for the entry whose quality changed", async () => {
  const entries = ["0", "1", "2"].map(key => ({ key, title: `Video ${key}`, selected: "small", formats: [{ id: "small", codec: "h264" }, { id: "large", codec: "h264" }] }));
  const requests: string[] = [];
  const call = vi.fn(async (route: string, _method?: string, body?: { entry_key: string }) => {
    if (route === "link-tools") return { available: true };
    if (route === "links/estimate") { requests.push(body!.entry_key); return { estimate: null }; }
    return { id: "checked", state: "done", result: { entries } };
  });
  render(<LinkPanel api={{ call } as unknown as Api} settings={{ short_side: 1080 } as Settings} changed={vi.fn()} initialUrl="http://localhost/playlist" />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Check" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Check" }));
  await waitFor(() => expect(requests).toEqual(["0", "1", "2"]));
  requests.length = 0;
  fireEvent.change(screen.getAllByRole("combobox", { name: "Quality" })[1], { target: { value: "large" } });
  await waitFor(() => expect(requests).toEqual(["1"]));
});

it("shows the downloaded path and opens a stored source using only the job ID", async () => {
  const open = vi.fn(async () => {});
  const previous = window.desktop.sourceLink;
  window.desktop.sourceLink = open;
  const job = { id: "a".repeat(32), state: "done", input: "D:\\SyntheticDownloads\\video.mkv", output: "D:\\SyntheticDownloads\\enhanced\\video.mp4", settings: { codec: "h264", preset: "fast" }, source: { url: "https://example.test/video" }, original_state: "present", output_state: "present" } as Job;
  try {
    render(<HistoryDetail job={job} close={vi.fn()} action={vi.fn()} compare={vi.fn()} />);
    expect(screen.getByText(job.input)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Source link" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith(job.id));
  } finally { window.desktop.sourceLink = previous; }
});

it.each([true, false])("requires the first download folder and respects picker cancellation (%s)", async choose => {
  const settings: Settings = { preset: "fast", short_side: 1080, fps: "off", codec: "hevc", output_folder: "", start_with_windows: false, theme: "dark", log_folder: "", advanced: {} };
  const saved = vi.fn();
  const picker = vi.mocked(window.desktop.files).mockResolvedValue(choose ? ["D:\\SyntheticDownloads"] : []);
  const checked = { id: "checked", state: "done", result: { entries: [{ key: "0", title: "Synthetic", selected: "video", formats: [{ id: "video", codec: "h264", dynamic_range: "SDR", unknown_size: true }] }] } };
  const call = vi.fn(async (route: string) => {
    if (route === "link-tools") return { available: true };
    if (route === "estimate/space") return { files: {} };
    if (route === "settings") return {};
    if (route === "links/queue") return { id: "job" };
    if (route === "links/estimate") return { estimate: null };
    return checked;
  });
  render(<AddDialog api={{ call } as unknown as Api} files={[]} initialUrl="http://localhost/video.mp4" defaults={settings} models={[]} close={vi.fn()} saved={saved} trial={vi.fn()} />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Check" }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Check" }));
  const add = await screen.findByRole("button", { name: "Add to queue" });
  await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(add);
  await waitFor(() => expect(picker).toHaveBeenCalledWith("folder"));
  if (choose) {
    await waitFor(() => expect(saved).toHaveBeenCalled());
    expect(call).toHaveBeenCalledWith("settings", "PUT", { video_download_folder: "D:\\SyntheticDownloads" });
    expect(call.mock.calls.findIndex(args => args[0] === "links/queue")).toBeGreaterThan(call.mock.calls.findIndex(args => args[0] === "settings"));
  } else {
    await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(false));
    expect(call.mock.calls.some(args => args[0] === "links/queue")).toBe(false);
    expect(saved).not.toHaveBeenCalled();
  }
  picker.mockClear();
});

it("checks only on request, handles a completed check and disables HDR", async () => {
  const changed = vi.fn();
  const call = vi.fn(async (route: string) => {
    if (route === "link-tools") return { available: true };
    if (route === "links/estimate") return { estimate: null };
    return { id: "checked", state: "done", result: { entries: [
      { key: "0", title: "Local fixture", selected: "sdr", formats: [
        { id: "sdr", codec: "h264", dynamic_range: "SDR", unknown_size: true },
        { id: "hdr", codec: "h264", dynamic_range: "HDR", disabled: "HDR is not supported yet" },
      ], reuse: { job_id: "saved", date: "2026-10-18T00:00:00Z", media: { display_width: 320, display_height: 180, cfr_fps: "30000/1001" } } },
      { key: "1", title: "Live fixture", error: "Live streams are not supported." },
    ] } };
  });
  render(<LinkPanel api={{ call } as unknown as Api} settings={{ short_side: 1080 } as Settings} initialUrl="http://localhost/video.mp4" changed={changed} />);
  await waitFor(() => expect((screen.getByRole("button", { name: "Check" }) as HTMLButtonElement).disabled).toBe(false));
  expect(call.mock.calls.map(args => args[0])).toEqual(["link-tools"]);
  fireEvent.click(screen.getByRole("button", { name: "Check" }));
  await screen.findByText("VideoEnhancer can't read this video's size before downloading. It is checked after the download. If it is larger than 1080p or HDR, the job stops and the downloaded file is kept.");
  expect((screen.getByRole("option", { name: /HDR is not supported/ }) as HTMLOptionElement).disabled).toBe(true);
  expect((screen.getByRole("checkbox", { name: "Live fixture" }) as HTMLInputElement).disabled).toBe(true);
  await waitFor(() => expect(changed).toHaveBeenLastCalledWith([{ check_id: "checked", entry_key: "0", format_id: "sdr", reuse_job_id: "saved" }]));
  expect((screen.getByRole("checkbox", { name: "Use the file downloaded on 2026-10-18 (320x180, 29.97 fps)" }) as HTMLInputElement).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Download again" }));
  await waitFor(() => expect(changed).toHaveBeenLastCalledWith([{ check_id: "checked", entry_key: "0", format_id: "sdr", reuse_job_id: undefined }]));
  fireEvent.click(screen.getByRole("button", { name: "Select none" }));
  await waitFor(() => expect(changed).toHaveBeenLastCalledWith([]));
});

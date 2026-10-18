import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LinkPanel } from "../src/LinkPanel";
import { AddDialog } from "../src/Queue";
import type { Api } from "../src/api";
import type { Settings } from "../src/types";

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
      ] },
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
  await waitFor(() => expect(changed).toHaveBeenLastCalledWith([{ check_id: "checked", entry_key: "0", format_id: "sdr", reuse_job_id: undefined }]));
  fireEvent.click(screen.getByRole("button", { name: "Select none" }));
  await waitFor(() => expect(changed).toHaveBeenLastCalledWith([]));
});

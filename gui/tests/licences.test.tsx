import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SettingsPage } from "../src/Pages";
import type { Api } from "../src/api";
import type { Settings } from "../src/types";

const settings = { preset: "standard", short_side: 1080, fps: "off", codec: "h264", output_folder: "", theme: "system", log_folder: "", advanced: {} } as Settings;
const api = { call: vi.fn(async () => ({})) } as unknown as Api;
const notices = { text: "libmpv / FFmpeg / libplacebo\nWritten offer: sources.tar.zst", path: "D:\\fixture\\THIRD_PARTY_NOTICES.md" };

it("reads selectable notices in Settings and restores focus after Close and Escape", async () => {
  window.desktop.licences = vi.fn(async () => notices);
  render(<SettingsPage api={api} value={settings} saved={vi.fn()} calibrate={vi.fn()} />);
  const trigger = screen.getByRole("button", { name: "Open-source licences" });
  fireEvent.click(trigger);
  expect(await screen.findByRole("textbox", { name: "Licence notices" })).toHaveProperty("value", notices.text);
  expect(screen.queryByRole("heading", { name: "Settings" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Show file" }));
  expect(window.desktop.reveal).toHaveBeenCalledWith(notices.path);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.getByRole("heading", { name: "Settings" })).toBeTruthy();
  expect(document.activeElement).toBe(trigger);
  fireEvent.click(trigger);
  await screen.findByRole("textbox", { name: "Licence notices" });
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.getByRole("heading", { name: "Settings" })).toBeTruthy());
  expect(document.activeElement).toBe(trigger);
});

it("shows the specific read error inside the view", async () => {
  window.desktop.licences = vi.fn(async () => { throw new Error("Licence notices are not valid UTF-8."); });
  render(<SettingsPage api={api} value={settings} saved={vi.fn()} calibrate={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Open-source licences" }));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Licence notices are not valid UTF-8.");
});

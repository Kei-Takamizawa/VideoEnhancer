import { expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { installDesktop } from "../src/desktop";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async () => null),
  isTauri: () => true,
}));
vi.mock("@tauri-apps/api/event", () => ({ listen: vi.fn(async () => () => {}) }));

it("preserves native errors and applies memory targets as a player opens and closes", async () => {
  const original = window.desktop;
  const message = "Move stopped. A file the app needs at start is damaged: previews/test/state.json. Your data stays in the current folder.";
  vi.mocked(invoke).mockImplementation(async (_command, args) => {
    if ((args as { operation: string }).operation === "moveStorage") throw message;
    if ((args as { operation: string }).operation === "licences") return { text: "Full notices", path: "D:\\fixture\\THIRD_PARTY_NOTICES.md" };
    return null;
  });
  try {
    installDesktop();
    await expect(window.desktop.licences!()).resolves.toEqual({ text: "Full notices", path: "D:\\fixture\\THIRD_PARTY_NOTICES.md" });
    await expect(window.desktop.moveStorage!("D:\\scratch\\target")).rejects.toThrow(message);
    vi.mocked(invoke).mockClear();
    const video = document.createElement("video");
    document.body.append(video);
    await vi.waitFor(() => expect(invoke).toHaveBeenCalledWith("desktop_command", { operation: "memoryTarget", args: false }));
    vi.mocked(invoke).mockClear();
    video.remove();
    await vi.waitFor(() => expect(invoke).toHaveBeenCalledWith("desktop_command", { operation: "memoryTarget", args: true }));
  } finally {
    window.desktop = original;
  }
});

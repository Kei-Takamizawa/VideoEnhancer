import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StorageCard } from "../src/Storage";
import type { Api } from "../src/api";

const api = { call: vi.fn(async () => ({ folder: "D:\\scratch\\active", cleanup: [], total_bytes: 0, free_bytes: 0, models_bytes: 0, working_bytes: 0, history_bytes: 0 })) } as unknown as Api;
const location = { previous: "D:\\scratch\\old", can_remove: true };

it("does not overlap progress polls or repeat full verification", async () => {
  const original = window.desktop;
  let finish!: (value: typeof location) => void;
  const status = vi.fn().mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockResolvedValue(location);
  window.desktop = { ...original, storageStatus: status };
  vi.useFakeTimers();
  const view = render(<StorageCard api={api} automatic={false} change={() => {}} />);
  try {
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(status).toHaveBeenCalledTimes(1);
    expect(status).toHaveBeenLastCalledWith(true);
    await act(async () => { finish(location); await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    expect(status).toHaveBeenCalledTimes(2);
    expect(status).toHaveBeenLastCalledWith(false);
  } finally { view.unmount(); vi.useRealTimers(); window.desktop = original; }
});

it("disables Move and Remove throughout removal and preserves a retained old folder", async () => {
  const original = window.desktop;
  let finish!: (value: { message: string }) => void;
  window.desktop = { ...original, storageStatus: vi.fn(async () => location), moveStorage: vi.fn(), removeOldStorage: vi.fn(() => new Promise(resolve => { finish = resolve; })) };
  const view = render(<StorageCard api={api} automatic={false} change={() => {}} />);
  try {
    const remove = await screen.findByRole("button", { name: "Remove the old folder" }) as HTMLButtonElement;
    await waitFor(() => expect(remove.disabled).toBe(false));
    fireEvent.click(remove);
    expect(remove.disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Move…" }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => { finish({ message: "Removed 1 files. Kept 2 move-manifest files." }); });
    expect(screen.getByText(/Old folder kept:/).isConnected).toBe(true);
    await waitFor(() => expect(remove.disabled).toBe(false));
  } finally { view.unmount(); window.desktop = original; }
});

it("explains a legacy pointer without offering unsafe removal", async () => {
  const original = window.desktop;
  const message = "This folder was moved by an earlier version, so the app can't check it before removing it. Keeping it is safe.";
  window.desktop = { ...original, storageStatus: vi.fn(async () => ({ ...location, can_remove: false, remove_reason: message })) };
  const view = render(<StorageCard api={api} automatic={false} change={() => {}} />);
  try {
    expect((await screen.findByText(message)).isConnected).toBe(true);
    expect((screen.getByRole("button", { name: "Remove the old folder" }) as HTMLButtonElement).disabled).toBe(true);
  } finally { view.unmount(); window.desktop = original; }
});

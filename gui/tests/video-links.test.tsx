import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { VideoLinksCard } from "../src/VideoLinks";
import type { Api } from "../src/api";

const tools = [
  { tool: "yt-dlp", version: "2026.08.19", released: "2026-08-19T00:00:00Z", bytes: 18000000, licence: "Unlicense source; GPLv3+ executable", present: true },
  { tool: "deno", version: "2.9.7", released: "2026-09-17T00:00:00Z", bytes: 42000000, licence: "MIT", present: true },
];
const plan = { id: "reviewed-plan", channel: "stable", tools, notice: "Only download videos you have the right to use. Some sites' terms do not allow downloading." };

it("does no automatic release check and requires consent for the exact checked plan", async () => {
  const call = vi.fn(async (route: string) => {
    if (route === "settings") return {};
    if (route === "link-tools") return { installed: {}, available: false, notice: plan.notice };
    if (route === "link-tools/check" || route === "operations/check") return { id: "check", kind: "link tools", state: "done", result: plan };
    if (route === "link-tools/install" || route === "operations/install") return { id: "install", kind: "link tools", state: "done", result: { installed: Object.fromEntries(tools.map(tool => [tool.tool, tool])), available: true, notice: plan.notice } };
    throw new Error(route);
  });
  const view = render(<VideoLinksCard api={{ call } as unknown as Api} />);
  try {
    await waitFor(() => expect((screen.getByRole("button", { name: "Install link tools" }) as HTMLButtonElement).disabled).toBe(false));
    expect(call.mock.calls.map(args => args[0]).sort()).toEqual(["link-tools", "settings"]);
    fireEvent.click(screen.getByRole("button", { name: "Install link tools" }));
    await screen.findByRole("dialog", { name: "Install link tools" });
    const install = screen.getByRole("button", { name: /^Install$/ }) as HTMLButtonElement;
    expect(install.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "I have read the licences and download notice" }));
    fireEvent.click(install);
    await waitFor(() => expect(call).toHaveBeenCalledWith("link-tools/install", "POST", { channel: "stable", plan_id: "reviewed-plan", consent: true }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await screen.findByRole("button", { name: "Check for updates" });
  } finally { view.unmount(); }
});

it("does not offer an update when the checked versions are already installed", async () => {
  const call = vi.fn(async (route: string) => route === "link-tools"
    ? { installed: Object.fromEntries(tools.map(tool => [tool.tool, tool])), available: true, notice: plan.notice }
    : { id: "check", kind: "link tools", state: "done", result: plan });
  const view = render(<VideoLinksCard api={{ call } as unknown as Api} />);
  try {
    fireEvent.click(await screen.findByRole("button", { name: "Check for updates" }));
    await screen.findByText("Link tools are up to date.");
    fireEvent.click(screen.getByRole("checkbox"));
    expect((screen.getByRole("button", { name: /^Update$/ }) as HTMLButtonElement).disabled).toBe(true);
    expect(call.mock.calls.some(args => args[0] === "link-tools/install")).toBe(false);
  } finally { view.unmount(); }
});

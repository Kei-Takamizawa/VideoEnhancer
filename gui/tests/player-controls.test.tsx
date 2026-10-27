import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Controls } from "../src/player/Controls";
import { previewLeft, zoomAt } from "../src/player/math";
import { readFileSync } from "node:fs";
const css = readFileSync("src/player/player.css", "utf8");
const bridge = vi.hoisted(() => ({ send: vi.fn(async () => true), receive: (event: Record<string, unknown>) => { void event; } }));
vi.mock("../src/player/ipc", () => ({ send: bridge.send, onPlayerEvent: (listener: typeof bridge.receive) => { bridge.receive = listener; return () => {}; } }));
afterEach(() => { vi.useRealTimers(); bridge.send.mockClear(); });
function event(value: Record<string, unknown>) { act(() => bridge.receive({ version: 1, ...value })); }
describe("native player controls", () => {
  it("attaches prewarmed metadata without another open and retains the poster until video is ready", () => {
    render(<Controls />);
    expect(bridge.send).toHaveBeenCalledTimes(1);
    event({ event: "configured", title: "Synthetic", original: true });
    expect(bridge.send).toHaveBeenCalledTimes(1);
    expect((screen.getByRole("button", { name: "Before / After" }) as HTMLButtonElement).disabled).toBe(false);
    event({ event: "poster", image: "data:image/jpeg;base64,c3ludGhldGlj" });
    expect(screen.getByAltText("Video poster").getAttribute("src")).toContain("data:image/jpeg");
    event({ event: "loaded", title: "Synthetic", original: true });
    expect(screen.queryByAltText("Video poster")).toBeNull();
  });

  it("keeps ten-second skips clamped and uses the portrait preview dimensions", () => {
    render(<Controls />); event({ event: "configured", original: true, video_width: 540, video_height: 960 });
    event({ event: "state", position: 5, duration: 60, paused: true });
    fireEvent.click(screen.getByRole("button", { name: "Back 10 seconds" }));
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "seek", seconds: 0 });
    fireEvent.click(screen.getByRole("button", { name: "Forward 10 seconds" }));
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "seek", seconds: 15 });
    fireEvent.pointerMove(screen.getByRole("slider", { name: "Seek" }), { clientX: 50 });
    const image = screen.getByAltText("Seek preview") as HTMLImageElement;
    expect([image.width, image.height]).toEqual([90, 160]);
    for (const name of ["Back 10 seconds", "Forward 10 seconds", "Play", "Close player", "Details"])
      expect(screen.getByRole("button", { name }).querySelector("svg")).toBeTruthy();
  });
  it("shows a reset control for zoom and returns the native picture to 100 percent", () => {
    render(<Controls />);
    fireEvent.wheel(screen.getByRole("main"), { ctrlKey: true, deltaY: -100, clientX: 0, clientY: 0 });
    expect(screen.getByText(/Zoom 122/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reset zoom" }));
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "transform", scale: 1, x: 0, y: 0 });
    expect(screen.queryByRole("button", { name: "Reset zoom" })).toBeNull();
  });

  it("hides after two seconds, reveals on movement and stays visible while paused", () => {
    vi.useFakeTimers(); render(<Controls />);
    const player = screen.getByRole("main");
    act(() => vi.advanceTimersByTime(2100));
    expect(player.className).toContain("hidden-controls");
    fireEvent.pointerMove(player);
    expect(player.className).not.toContain("hidden-controls");
    event({ event: "state", paused: true });
    act(() => vi.advanceTimersByTime(3000));
    expect(player.className).not.toContain("hidden-controls");
  });
  it("routes exact seeks, paused frame steps and the approved shortcuts", () => {
    render(<Controls />); event({ event: "state", position: 10, duration: 60, paused: true });
    fireEvent.keyDown(document, { key: "ArrowRight", shiftKey: true });
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "seek", seconds: 11 });
    fireEvent.keyDown(document, { key: "," });
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "step", forward: false });
    fireEvent.keyDown(document, { key: "f" });
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "fullscreen", enabled: true });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "fullscreen", enabled: false });
    event({ event: "state", paused: false });
    expect((screen.getByRole("button", { name: "Next frame" }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("disables Before/After without the original and updates the native divider", () => {
    render(<Controls />);
    expect((screen.getByRole("button", { name: "Before / After" }) as HTMLButtonElement).disabled).toBe(true);
    event({ event: "loaded", original: true });
    fireEvent.click(screen.getByRole("button", { name: "Before / After" }));
    fireEvent.change(screen.getByRole("slider", { name: "Before / After divider" }), { target: { value: "0.75" } });
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "divider", fraction: 0.75 });
  });
  it("keeps preview above the bar, clamps its edges and gives every control a name", () => {
    render(<Controls />);
    expect(previewLeft(0, 800)).toBe(0); expect(previewLeft(1, 800)).toBe(608);
    expect(css).toMatch(/bottom:\s*calc\(100% \+ 12px\)/);
    for (const control of screen.getAllByRole("button")) expect(control.getAttribute("aria-label")).toBeTruthy();
    expect(screen.getByRole("slider", { name: "Seek" })).toBeTruthy();
    expect(screen.getByRole("slider", { name: "Volume" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Playback speed" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Playback speed" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "1.5×" }));
    expect(bridge.send).toHaveBeenLastCalledWith({ type: "speed", rate: 1.5 });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(css).toMatch(/\.speed-menu\s*\{[^}]*background:\s*transparent/);
  });
  it("zooms around the cursor and clamps 100-800 percent", () => {
    const start = { scale: 1, x: 0, y: 0 };
    const zoom = zoomAt(start, 2, 0.25, -0.25);
    expect(zoom).toEqual({ scale: 2, x: -0.25, y: 0.25 });
    expect((0.25 - zoom.x) / zoom.scale).toBe(0.25);
    expect(zoomAt(zoom, 100, 0, 0).scale).toBe(8);
    expect(zoomAt(zoom, 0.01, 0, 0)).toEqual(start);
  });
});

import { render, screen, fireEvent } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ErrorBoundary } from "../src/ErrorBoundary";

it("shows a fixed recovery screen and logs the component stack after a render failure", () => {
  const copy = vi.fn().mockResolvedValue(undefined);
  const logRendererError = vi.fn().mockResolvedValue(undefined);
  const reload = vi.fn().mockResolvedValue(undefined);
  const previous = window.desktop;
  window.desktop = { ...previous, copy, logRendererError, reload };
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
  function Broken(): never { throw new Error("synthetic render failure"); }
  try {
    render(<ErrorBoundary scope="Synthetic dialog"><Broken /></ErrorBoundary>);
    expect(screen.getByText("Something went wrong on this screen")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reload" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reload" }));
    expect(reload).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    expect(copy).toHaveBeenCalledWith(expect.stringContaining("synthetic render failure"));
    expect(logRendererError).toHaveBeenCalledWith(expect.stringContaining("Broken"));
  } finally {
    window.desktop = previous;
    consoleError.mockRestore();
  }
});

import { expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Notice } from "../src/Notice";

it("Dismiss hides one error and a new error is visible", () => {
  const dismiss = vi.fn();
  const view = render(<Notice identity="first" dismiss={dismiss}>First problem</Notice>);
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByRole("alert")).toBeNull();
  expect(dismiss).toHaveBeenCalledOnce();
  view.rerender(<Notice identity="first">First problem</Notice>);
  expect(screen.queryByRole("alert")).toBeNull();
  view.rerender(<Notice identity="second">Second problem</Notice>);
  expect(screen.getByRole("alert").textContent).toContain("Second problem");
});

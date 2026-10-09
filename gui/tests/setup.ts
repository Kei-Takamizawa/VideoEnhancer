import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
afterEach(cleanup);
Object.defineProperty(window, "matchMedia", {
  value: vi.fn(() => ({
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
});
window.desktop = {
  connection: vi.fn(),
  files: vi.fn(),
  openFolder: vi.fn(async () => {}),
  copy: vi.fn(async () => {}),
  filePath: vi.fn(),
};

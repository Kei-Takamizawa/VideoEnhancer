import { expect, it, vi } from "vitest";
import { compareMovie } from "../src/Trial";
it("reuses the original fetch/demux while new model tiles arrive, and retries failures", async () => {
  const cache = new Map<string, Promise<number>>();
  const load = vi.fn(async () => 7);
  const original = compareMovie(cache, "original", load);
  expect(compareMovie(cache, "original", load)).toBe(original);
  await expect(compareMovie(cache, "model-one", load)).resolves.toBe(7);
  await expect(compareMovie(cache, "original", load)).resolves.toBe(7);
  expect(load).toHaveBeenCalledTimes(2);
  const fail = vi.fn(async () => { throw new Error("Interrupted"); });
  await expect(compareMovie(cache, "model-two", fail)).rejects.toThrow("Interrupted");
  await expect(compareMovie(cache, "model-two", load)).resolves.toBe(7);
  expect(load).toHaveBeenCalledTimes(3);
  expect(cache.size).toBe(3);
});

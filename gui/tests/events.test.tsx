import { afterEach, describe, expect, it, vi } from "vitest";
import { events } from "../src/api";

const connection = { base_url: "http://127.0.0.1:1234/v1", token: "test" };
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("event recovery", () => {
  it("reconnects after 30 seconds of silence and keeps the last snapshot", async () => {
    vi.useFakeTimers();
    let controller: ReadableStreamDefaultController<Uint8Array>;
    const fetch = vi.fn(async (_url, options) => {
      const body = new ReadableStream<Uint8Array>({
        start(value) {
          controller = value;
          options.signal.addEventListener("abort", () => value.error(new Error("aborted")));
        },
      });
      return { ok: true, body };
    });
    vi.stubGlobal("fetch", fetch);
    const abort = new AbortController();
    const receive = vi.fn();
    const status = vi.fn();
    const reconnect = vi.fn(async () => ({ base_url: "http://127.0.0.1:5678/v1", token: "new" }));
    const running = events(connection, abort.signal, receive, status, reconnect);
    await vi.advanceTimersByTimeAsync(0);
    controller!.enqueue(new TextEncoder().encode('event: update\ndata: {"jobs":[]}\n\n'));
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(30000);
    expect(status).toHaveBeenLastCalledWith(true);
    expect(receive).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(reconnect).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[1][0]).toBe("http://127.0.0.1:5678/v1/events");
    abort.abort();
    await running;
  });

  it("heartbeats reset the silence deadline and error events are not snapshots", async () => {
    vi.useFakeTimers();
    let controller: ReadableStreamDefaultController<Uint8Array>;
    const fetch = vi.fn(async (_url, options) => ({
      ok: true,
      body: new ReadableStream<Uint8Array>({
        start(value) {
          controller = value;
          options.signal.addEventListener("abort", () => value.error(new Error("aborted")));
        },
      }),
    }));
    vi.stubGlobal("fetch", fetch);
    const abort = new AbortController();
    const receive = vi.fn();
    const running = events(connection, abort.signal, receive);
    await vi.advanceTimersByTimeAsync(0);
    for (let n = 0; n < 4; n++) {
      await vi.advanceTimersByTimeAsync(20000);
      controller!.enqueue(new TextEncoder().encode(": heartbeat\n\nevent: error\ndata: Try again.\n\n"));
      await vi.advanceTimersByTimeAsync(0);
    }
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(receive).not.toHaveBeenCalled();
    abort.abort();
    await running;
  });
});

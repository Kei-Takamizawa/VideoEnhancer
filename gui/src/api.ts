import type { Connection } from "./types";
export interface Api {
  call<T>(route: string, method?: string, data?: unknown): Promise<T>;
  blob(route: string): Promise<Blob>;
}
export function client(connection: Connection): Api {
  async function send(route: string, method = "GET", data?: unknown) {
    const response = await fetch(`${connection.base_url}/${route}`, {
      method,
      headers: {
        Authorization: `Bearer ${connection.token}`,
        "Content-Type": "application/json",
      },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal: AbortSignal.timeout(
        method === "POST" && route === "queue" ? 1200000 : 30000,
      ),
    });
    if (!response.ok)
      throw new Error(
        (await response.json()).error ||
          `Engine request failed (${response.status}).`,
      );
    return response;
  }
  return {
    call: async <T>(route: string, method?: string, data?: unknown) =>
      (await send(route, method, data)).json() as Promise<T>,
    blob: async (route) => (await send(route)).blob(),
  };
}
export async function events(
  connection: Connection,
  signal: AbortSignal,
  receive: (data: unknown) => void,
  status: (reconnecting: boolean) => void = () => {},
  reconnect?: () => Promise<Connection>,
) {
  let attempt = 0;
  while (!signal.aborted) {
    const stream = new AbortController();
    const cancel = () => stream.abort();
    signal.addEventListener("abort", cancel, { once: true });
    let silence = setTimeout(cancel, 30000);
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const response = await fetch(`${connection.base_url}/events`, {
        headers: { Authorization: `Bearer ${connection.token}` },
        signal: stream.signal,
      });
      if (!response.ok || !response.body)
        throw new Error("The engine event stream is unavailable.");
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!stream.signal.aborted) {
        const chunk = await reader.read();
        if (chunk.done) throw new Error("The engine connection closed.");
        buffer += decoder.decode(chunk.value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const message = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          clearTimeout(silence);
          silence = setTimeout(cancel, 30000);
          attempt = 0;
          status(false);
          if (message.startsWith("event: update")) {
            const line = message.split("\n").find((line) => line.startsWith("data: "));
            if (line) receive(JSON.parse(line.slice(6)));
          }
        }
      }
    } catch {
      if (!signal.aborted) status(true);
    } finally {
      clearTimeout(silence);
      stream.abort();
      signal.removeEventListener("abort", cancel);
      await reader?.cancel().catch(() => {});
    }
    if (signal.aborted) return;
    const delay = [1000, 2000, 5000, 10000][Math.min(attempt++, 3)];
    await new Promise<void>((resolve) => {
      const finish = () => { clearTimeout(timer); signal.removeEventListener("abort", finish); resolve(); };
      const timer = setTimeout(finish, delay);
      signal.addEventListener("abort", finish, { once: true });
    });
    if (!signal.aborted && reconnect) {
      try {
        connection = await reconnect();
      } catch {
        status(true);
      }
    }
  }
}
export function filename(value: string) {
  return value.split(/[\\/]/).at(-1) || value;
}
export function folder(value: string) {
  return value.replace(/[\\/][^\\/]*$/, "");
}
export function duration(seconds: number) {
  const minutes = Math.ceil(Math.max(0, seconds) / 60);
  return minutes >= 60
    ? `${Math.floor(minutes / 60)} h ${minutes % 60} m`
    : `${minutes} m`;
}
export function when(value?: string | null) {
  return value
    ? new Date(value).toLocaleString("en-US", {
        weekday: "short",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "Not scheduled";
}
export function completion(plan?: { jobs: { completion: string | null }[] }) {
  const times = plan?.jobs.map((j) => j.completion);
  return times?.length && times.every(Boolean) ? times.sort().at(-1) : null;
}

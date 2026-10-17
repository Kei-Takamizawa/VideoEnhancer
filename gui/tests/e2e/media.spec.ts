import { expect, test } from "@playwright/test";
import { desktop } from "../desktop";
import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

// Full P/R/steady Private Bytes qualification is in scripts/media-matrix.mjs.
for (const codec of ["h264", "av1"]) test(`M1 ${codec}: bounded 1440 media, 10 starts and seeks`, async () => {
  test.skip(!process.env.VE_MEDIA_HOME, "Requires isolated FFmpeg-only 1440 fixtures of at least 2 GB.");
  test.setTimeout(300000);
  const home = process.env.VE_MEDIA_HOME!;
  const m3 = process.env.VE_MEDIA_DESIGN === "m3-prototype";
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: home, VE_KEEP_TEST_ENGINE: m3 ? "1" : "0" } });
  const page = await app.firstWindow();
  const evidence = process.env.VE_GUI_EVIDENCE!; mkdirSync(evidence, { recursive: true });
  const result: Record<string, unknown> = { codec, memory_qualification: "Separate Private Bytes P/R/steady matrix; this test checks timing only", starts_ms: [] as number[], seeks_ms: [] as number[] };
  const messages: string[] = []; result.messages = messages;
  page.on("console", message => { if (message.type()==="error") messages.push(message.text().replace(/[0-9a-fA-F]{32,}/g,"<redacted>")); });
  page.on("response", response => { if (response.status()>=400) messages.push(`HTTP ${response.status()} ${new URL(response.url()).origin}`); });
  result.design = m3 ? "M3 throwaway prototype with test-only CSP permitting local engine media; not shipped" : "M1 bounded custom protocol";
  try {
    await expect(page.getByRole("heading", { name: "Home", exact: true })).toBeVisible();
    let directUrl = "";
    const c = JSON.parse(readFileSync(path.join(home,"serve.json"),"utf8"));
    if (m3) {
      const response = await fetch(`http://127.0.0.1:${c.port}/v1/fixture-url/${codec}-1440-large`, {method:"POST",headers:{Authorization:`Bearer ${c.token}`}});
      if (!response.ok) throw new Error("M3 fixture URL issuance failed");
      directUrl = (await response.json()).url;
    }
    const responses = await page.evaluate(async ({codec,directUrl}) => {
      const video = document.createElement("video"); video.crossOrigin="anonymous"; video.muted = true; video.style.cssText = "position:fixed;inset:0;width:960px;height:540px;z-index:999"; document.body.append(video);
      const starts: number[] = [], seeks: number[] = [];
      const event = (name: string) => new Promise<void>((resolve, reject) => { const timer = setTimeout(() => reject(new Error(`${name} timeout`)), 15000); video.addEventListener(name, () => { clearTimeout(timer); resolve(); }, { once: true }); });
      for (let i = 0; i < 10; i++) {
        video.pause(); video.removeAttribute("src"); video.load();
        const started = performance.now(); const painted = new Promise<void>(resolve => video.requestVideoFrameCallback(() => resolve()));
        const url = `${directUrl || `http://ve-media.localhost/${codec}-1440-large`}?repeat=${i}`;
        video.src = url; await video.play(); await painted; starts.push(performance.now() - started); video.pause();
        const began = performance.now(); const sought = event("seeked"); video.currentTime = 12 + i * 11.37; await sought; await new Promise(resolve => requestAnimationFrame(resolve)); seeks.push(performance.now() - began);
      }
      video.loop = true; await video.play();
      return { starts, seeks };
    }, {codec,directUrl});
    result.starts_ms = responses.starts; result.seeks_ms = responses.seeks; result.file_bytes = statSync(path.join(home,"../media",`${codec}-1440-large.mp4`)).size;
    result.fetches = await app.command("state");
    if (m3) result.engine_fetches = await fetch(`http://127.0.0.1:${c.port}/v1/fixture-fetches`,{headers:{Authorization:`Bearer ${c.token}`}}).then(r=>r.json());
    const median = (values: number[]) => { const sorted = values.toSorted((a, b) => a - b); return (sorted[4] + sorted[5]) / 2; };
    result.start_median_ms = median(responses.starts); result.seek_median_ms = median(responses.seeks);
    expect(result.file_bytes).toBeGreaterThanOrEqual(2_000_000_000);
    expect(result.start_median_ms).toBeLessThanOrEqual(500);
    expect(result.seek_median_ms).toBeLessThanOrEqual(300);
  } finally {
    writeFileSync(path.join(evidence, `media-${codec}.json`), JSON.stringify(result, null, 2));
    await app.close();
  }
});

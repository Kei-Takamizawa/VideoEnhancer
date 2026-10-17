/* eslint-disable @typescript-eslint/no-require-imports -- Node helper loaded by Playwright. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

async function fakeEngine(home) {
  fs.mkdirSync(home, { recursive: true });
  const settings = { preset: "standard", codec: "hevc", short_side: 1080, fps: "2x", output_folder: "", start_with_windows: false, theme: "dark", zoom: 100, tray_explained: true, tour_completed: true, delete_original_after: false, log_folder: "", advanced: {} };
  const schedule = { schema_version: 1, enabled: true, timezone: "America/Los_Angeles", weekly: [{ days: ["mon", "tue", "wed", "thu", "fri"], start: "09:00", end: "18:00" }], exceptions: [] };
  const plan = { timezone: schedule.timezone, days: [], timeline: [], jobs: [], completion: new Date(Date.now() + 3600000).toISOString() };
  const job = index => ({ id: `synthetic-${index}`, position: index + 1, state: index === 0 ? "running" : index < 11 ? "queued" : "done", input: `C:\\synthetic\\video-${index}.mp4`, output: `C:\\synthetic\\video-${index}-output.mp4`, settings, media: { display_width: 720, display_height: 1280, cfr_fps: "30", duration: 30, frame_count: 900 }, estimate: { seconds: 500, low: 375, high: 625, calibrated: false }, eta: plan.completion, progress_percent: 20, phase: "processing", step: "Processing", step_percent: 20, segment: 1, completed_segments: index < 11 ? 0 : 3, segments: 3, log: "C:\\synthetic\\job.jsonl", original_state: "present", output_state: "present", original_bytes: 1000000, output_bytes: 2000000, output_folder: "C:\\synthetic", took_seconds: 400, finished_at: new Date(Date.now() - index * 1000).toISOString() });
  const queue = { history_revision: "synthetic-history-v1", jobs: Array.from({ length: 1011 }, (_, index) => job(index)), operations: [], completion: plan.completion };
  const health = { version: "fixture", engine_state: "Working", waiting_count: 10, paused_all: false, gpu: "Synthetic RTX 4060 Ti", driver: "fixture", vram_bytes: 8589934592, home, av1_supported: true, av1_min_width: 130, av1_min_height: 66, smart_app_control: { blocked: false } };
  const token = crypto.randomBytes(32).toString("hex");
  const clients = new Set();
  const routes = { storage: { folder: home, total_bytes: 0, models_bytes: 0, working_bytes: 0, history_bytes: 0, free_bytes: 0, cleanup: [], core_records_load: true } };
  const models = [];
  const control = { events: true, media_active: 0, media_peak: 0, media_total: 0 };
  let previewSequence = 0;
  const server = http.createServer((req, res) => {
    const route = req.url.split("?")[0].replace(/^\/v1\//, "");
    res.setHeader("Access-Control-Allow-Origin", req.headers.origin === "http://tauri.localhost" ? "http://tauri.localhost" : "app://videoenhancer");
    res.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
    if (req.headers.authorization !== `Bearer ${token}`) { res.writeHead(401); res.end(); return; }
    const mediaFile = routes[route]?.fixtureVideoPath;
    if (mediaFile && ["GET", "HEAD"].includes(req.method)) {
      const size = fs.statSync(mediaFile).size;
      let start = 0, end = size - 1;
      if (req.headers.range) {
        const match = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range);
        if (!match || (!match[1] && !match[2])) { res.writeHead(416); res.end(); return; }
        start = match[1] ? Number(match[1]) : Math.max(0, size - Number(match[2]));
        end = match[1] && match[2] ? Math.min(size - 1, Number(match[2])) : size - 1;
        if (start >= size || end < start) { res.writeHead(416, { "Content-Range": `bytes */${size}` }); res.end(); return; }
      }
      control.media_active++; control.media_total++;
      control.media_peak = Math.max(control.media_peak, control.media_active);
      let ended = false;
      const finish = () => { if (!ended) { ended = true; control.media_active--; } };
      res.once("close", finish); res.once("finish", finish);
      res.setHeader("Content-Type", "video/mp4"); res.setHeader("Accept-Ranges", "bytes");
      res.setHeader("Content-Length", end - start + 1); res.setHeader("Cache-Control", "no-store");
      if (req.headers.range) { res.statusCode = 206; res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`); }
      if (req.method === "HEAD") { res.end(); return; }
      const stream = fs.createReadStream(mediaFile, { start, end });
      res.once("close", () => stream.destroy()); stream.on("error", () => res.destroy()); stream.pipe(res);
      return;
    }
    if (route === "events") {
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      clients.add(res); req.on("close", () => clients.delete(res));
      if (control.events) res.write(`event: update\ndata: ${JSON.stringify({ queue, health, plan })}\n\n`); return;
    }
    let raw = "";
    req.on("data", chunk => raw += chunk);
    req.on("end", () => {
      let data; try { data = raw ? JSON.parse(raw) : {}; } catch { data = {}; }
      if (route === "settings" && req.method === "PUT") Object.assign(settings, data);
      if (route === "schedule" && req.method === "PUT") Object.assign(schedule, data);
      if (route in routes) {
        const handler = routes[route];
        Promise.resolve(typeof handler === "function" ? handler(data, req.method) : handler).then(value => {
          if (Buffer.isBuffer(value)) { res.setHeader("Content-Type", value[0] === 0x89 ? "image/png" : "video/mp4"); res.end(value); return; }
          if (value?.statusCode) res.statusCode = value.statusCode;
          res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(value));
        }).catch(error => { res.statusCode = 500; res.end(JSON.stringify({ error: error.message })); });
        return;
      }
      res.setHeader("Content-Type", "application/json");
      if (route === "estimate/space") { res.end(JSON.stringify({ files: Object.fromEntries((data.files || []).map(file => [file, { output: `${file}.output.mp4`, warnings: [] }])) })); return; }
      if (route === "schedule/preview") {
        previewSequence++;
        setTimeout(() => res.end(JSON.stringify({ plan: { ...plan, jobs: [{ id: "synthetic-0", completion: new Date(Date.now() + previewSequence * 60000).toISOString() }] }, next_window: null })), 15); return;
      }
      let value = route === "health" ? health : route === "queue" ? queue : route === "settings" ? settings : route === "schedule" ? schedule : route === "plan" ? plan : route === "models" ? models : route.includes("/thumbnail") ? null : {};
      if (/^queue\/[^/]+\/json$/.test(route) && !routes[route]) { const record = queue.jobs.find(job => job.id === route.split("/")[1]); value = record ? { ...record, input: { path: record.input } } : {}; }
      if (route.includes("/thumbnail")) { res.writeHead(404); }
      res.end(JSON.stringify(value));
    });
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  fs.writeFileSync(path.join(home, "serve.json"), JSON.stringify({ port: server.address().port, token, pid: process.pid, protocol_version: 1 }));
  fs.writeFileSync(path.join(home, "settings.json"), JSON.stringify(settings));
  const timer = setInterval(() => {
    if (queue.jobs[0]?.state === "running") queue.jobs[0].progress_percent = (queue.jobs[0].progress_percent + 1) % 90;
    const running = queue.jobs.filter(job => job.state === "running").map(job => ({ id: job.id, percent: job.progress_percent, work_left: job.estimate.seconds, finish_time: job.eta, fps: job.fps, phase: job.phase, step: job.step }));
    const message = `event: progress\ndata: ${JSON.stringify({ progress: running })}\n\n`;
    if (control.events) for (const client of clients) client.write(message);
  }, 1000);
  return { queue, health, plan, settings, schedule, models, routes, control,
    snapshot: () => { if (control.events) for (const client of clients) client.write(`event: update\ndata: ${JSON.stringify({ queue, health, plan })}\n\n`); },
    disconnect: () => { for (const client of clients) client.end(); },
    error: message => { for (const client of clients) client.write(`event: error\ndata: ${message}\n\n`); },
    close: async () => { clearInterval(timer); for (const client of clients) client.end(); await new Promise(resolve => server.close(resolve)); } };
}
module.exports = { fakeEngine };

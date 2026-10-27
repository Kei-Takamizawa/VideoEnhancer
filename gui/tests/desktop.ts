import { chromium, test, type Browser, type Page } from "@playwright/test";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import net from "node:net";

const launches: { home: string; output(): string }[] = [];
test.beforeEach(() => { launches.length = 0; });
test.afterEach(async ({ browserName }, info) => {
  void browserName;
  if (info.status === info.expectedStatus) return;
  for (const [index, launch] of launches.entries()) {
    writeFileSync(info.outputPath(`app-${index}.log`), launch.output());
    try { writeFileSync(info.outputPath(`engine-${index}.log`), readFileSync(path.join(launch.home, "videoenhancer.jsonl")).subarray(-2_000_000)); }
    catch { writeFileSync(info.outputPath(`engine-${index}.log`), "No engine log was available."); }
    try { writeFileSync(info.outputPath(`engine-start-${index}.log`), readFileSync(path.join(launch.home, "service-start.log")).subarray(-2_000_000)); } catch { /* The engine may have failed before creating its start log. */ }
  }
});

export class DesktopApp {
  constructor(private child: ChildProcess, private browser: Browser, private page: Page, private home: string, private keepEngine = false) {}
  firstWindow() { return Promise.resolve(this.page); }
  process() { return this.child; }
  async command<T = unknown>(operation: string, args: unknown = null): Promise<T> {
    return this.page.evaluate(({ operation, args }) => {
      const internal = window as unknown as { __TAURI_INTERNALS__: { invoke<T>(command: string, args: unknown): Promise<T> } };
      return internal.__TAURI_INTERNALS__.invoke<T>("desktop_test", { operation, args });
    }, { operation, args });
  }
  files(paths: string[]) { return this.command("files", paths); }
  setContentSize(width: number, height: number) { return this.command("size", [width, height]); }
  async setZoomFactor(factor: number) { await this.page.evaluate(value => window.desktop.zoom(value), Math.round(factor * 100)); }
  async capturePage() { return this.page.screenshot({ scale: "css" }); }
  async show() { return this.command("show"); }
  async hide() { await this.page.evaluate(() => window.desktop.hide()); }
  async closeWindow() { return this.command("close"); }
  async isVisible() { return (await this.command<{ visible: boolean }>("state")).visible; }
  async isFullScreen() { return (await this.command<{ fullscreen: boolean }>("state")).fullscreen; }
  setFullScreen(value: boolean) { return this.command("fullscreen", value); }
  async reload() { await this.page.reload(); }
  async loadURL(url?: string) { if (url && !url.startsWith("app://videoenhancer/") && !url.startsWith("http://tauri.localhost/")) throw new Error("Only app reloads are allowed"); await this.page.reload(); }
  async startupEnabled() { return this.command<boolean>("startup"); }
  async themeSource() { return this.page.getByLabel("Theme").inputValue(); }
  clipboardText() { return this.command<string>("clipboard"); }
  async getNativeWindowHandle() { const buffer = Buffer.alloc(8); buffer.writeBigUInt64LE(BigInt(await this.command<number>("handle"))); return buffer; }
  async quit() { await this.command("quit").catch(() => {}); }
  async exit() { await this.command("exit").catch(() => {}); }
  async close() {
    try {
      const current = await this.page.evaluate(() => window.desktop.connection()).catch(() => null);
      let discovery: { pid?: number; port: number; token: string } | undefined;
      try { discovery = JSON.parse(readFileSync(path.join(this.home, "serve.json"), "utf8")); } catch { /* A completed move removes the old discovery file. */ }
      const c = current ? { ...current, port: new URL(current.base_url).port } : discovery;
      if (!this.keepEngine && discovery?.pid !== process.pid && c) await fetch(`http://127.0.0.1:${c.port}/v1/shutdown`, { method: "POST", headers: { Authorization: `Bearer ${c.token}`, "Content-Type": "application/json" }, body: "{}", signal: AbortSignal.timeout(20000) }).catch(() => {});
    } catch { /* No service was started by this isolated fixture. */ }
    await this.exit(); this.child.kill(); await this.browser.close().catch(() => {});
  }
}
export const desktop = {
  async launch(options: { executablePath?: string; args?: string[]; cwd?: string; env?: Record<string, string | undefined> }) {
    const env = { ...process.env, ...options.env };
    const home = env.VE_HOME || env.VE_TEST_EXPECTED_HOME;
    if (!home || !path.resolve(home).toLowerCase().includes(`${path.sep}scratch${path.sep}`)) throw new Error("Desktop tests require an isolated home under scratch.");
    const profile = options.args?.find(arg => arg.startsWith("--user-data-dir="))?.slice(16) || path.join(home, "desktop");
    mkdirSync(profile, { recursive: true });
    const port = await new Promise<number>((resolve, reject) => { const server = net.createServer(); server.once("error", reject); server.listen(0, "127.0.0.1", () => { const port = (server.address() as net.AddressInfo).port; server.close(() => resolve(port)); }); });
    const exe = options.executablePath || env.VE_TAURI_EXE || env.VE_TAURI_RELEASE_EXE || path.join(process.env.CARGO_TARGET_DIR || path.resolve("../../cache/tauri-target"), "debug/VideoEnhancer.exe");
    const child = spawn(exe, options.args?.filter(arg => arg === "--hidden") || [], { cwd: options.cwd || path.resolve(".."), windowsHide: true,
      env: { ...env, APPDATA: env.VE_TEST_APPDATA || path.join(profile, "roaming"), LOCALAPPDATA: env.VE_TEST_LOCALAPPDATA || path.join(profile, "local"), WEBVIEW2_USER_DATA_FOLDER: profile,
        WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port} --autoplay-policy=no-user-gesture-required` }, stdio: ["ignore", "pipe", "pipe"] });
    let failure: Error | undefined; child.once("error", error => { failure = error; });
    let output = "";
    const capture = (chunk: Buffer) => { output = (output + chunk.toString()).slice(-2_000_000); };
    launches.push({ home, output: () => output });
    child.on("exit", (code, signal) => capture(Buffer.from(`${Date.now()} process exit code=${code} signal=${signal}\n`)));
    child.stdout?.on("data", capture); child.stderr?.on("data", capture);
    let browser: Browser | undefined;
    for (let i = 0; i < 150; i++) { if (failure) throw failure; if (child.exitCode !== null) break; try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`); break; } catch { await new Promise(resolve => setTimeout(resolve, 200)); } }
    if (!browser) {
      let native: string;
      try { native = execFileSync(path.resolve(import.meta.dirname, "../../.venv/Scripts/python.exe"), [path.resolve(import.meta.dirname, "../../scripts/desktop_startup_diagnostics.py"), String(child.pid)], { encoding: "utf8", windowsHide: true, timeout: 10000 }); } catch (error) { native = String(error); }
      capture(Buffer.from(`\nStartup diagnostics:\n${native}\n`));
      child.kill(); throw new Error(`Tauri CDP attachment failed (${exe}, exit=${child.exitCode}): ${output}`);
    }
    try {
      const context = browser.contexts()[0];
      const page = context.pages()[0] || await context.waitForEvent("page", { timeout: 30000 });
      page.on("close", () => capture(Buffer.from(`${Date.now()} webview closed; origin unknown (see native lifecycle events)\n`)));
      page.on("crash", () => capture(Buffer.from(`${Date.now()} webview crashed\n`)));
      await page.waitForURL("http://tauri.localhost/**");
      return new DesktopApp(child, browser, page, home, env.VE_KEEP_TEST_ENGINE === "1");
    } catch (error) {
      child.kill();
      await browser.close().catch(() => {});
      throw error;
    }
  },
};

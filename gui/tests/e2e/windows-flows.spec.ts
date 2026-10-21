import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { execFileSync, spawn } from "node:child_process";
import {
  copyFileSync,
  createReadStream,
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { createServer } from "node:https";

test("owner Windows: packaged GPU flows create no extra visible console windows", async () => {
  test.skip(
    process.platform !== "win32" ||
      !process.env.VE_GUI_WINDOWS_FLOWS_HOME ||
      !process.env.VE_GUI_PACKAGE_EXE,
    "Opt-in fresh copied model home and packaged app.",
  );
  test.setTimeout(300000);
  const root = path.resolve("..");
  const home = process.env.VE_GUI_WINDOWS_FLOWS_HOME!;
  const evidence = path.join(
    process.env.VE_GUI_EVIDENCE!,
    `windows-flows-${Date.now()}`,
  );
  mkdirSync(evidence, { recursive: true });
  const monitor = spawn(
    path.join(root, ".venv/Scripts/pythonw.exe"),
    [path.join(root, "scripts/window_monitor.py"), evidence],
    { windowsHide: true },
  );
  await expect.poll(() => existsSync(path.join(evidence, "ready"))).toBe(true);
  const source = path.join(evidence, "synthetic.mp4");
  execFileSync(
    process.env.VE_FFMPEG || "ffmpeg",
    [
      "-v",
      "error",
      "-f",
      "lavfi",
      "-i",
      "testsrc2=size=512x288:rate=30",
      "-t",
      "3",
      "-c:v",
      "libx264",
      "-threads",
      "2",
      "-pix_fmt",
      "yuv420p",
      source,
    ],
    { windowsHide: true },
  );
  const env = { ...process.env, VE_HOME: home } as Record<string, string>;
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.VE_ENGINE_ROOT;
  const manifestPath = path.join(home, "models/basicvsrpp-ntire21-decompress/model.json");
  const model = JSON.parse(readFileSync(manifestPath, "utf8"));
  const downloadFixture = process.env.VE_GUI_DOWNLOAD_FIXTURE;
  if (downloadFixture && (!process.env.VE_GUI_DOWNLOAD_CERT || !process.env.VE_GUI_DOWNLOAD_KEY)) throw new Error("The local HTTPS publisher needs an isolated certificate and key.");
  if (downloadFixture) env.SSL_CERT_FILE = process.env.VE_GUI_DOWNLOAD_CERT!;
  const publisher = downloadFixture ? createServer({ cert: readFileSync(process.env.VE_GUI_DOWNLOAD_CERT!), key: readFileSync(process.env.VE_GUI_DOWNLOAD_KEY!) }, (_request, response) => {
    response.writeHead(200, { "Content-Length": statSync(downloadFixture).size });
    createReadStream(downloadFixture).pipe(response);
  }) : undefined;
  if (publisher) {
    expect(existsSync(path.join(path.dirname(manifestPath), model.weights.filename))).toBe(false);
    await new Promise<void>(resolve => publisher.listen(0, "127.0.0.1", resolve));
    const address = publisher.address();
    if (!address || typeof address === "string") throw new Error("Missing local fixture publisher");
    model.weights.url = `https://127.0.0.1:${address.port}/weights.pth`;
    writeFileSync(manifestPath, JSON.stringify(model));
  }
  const app = await desktop.launch({
    executablePath: process.env.VE_GUI_PACKAGE_EXE!,
    args: [`--user-data-dir=${path.join(home, "desktop")}`],
    env,
  }).catch(error => { publisher?.closeAllConnections(); publisher?.close(); monitor.kill(); throw error; });
  writeFileSync(path.join(evidence, "app.pid"), String(app.process().pid));
  writeFileSync(
    path.join(evidence, "own-windows.json"),
    JSON.stringify(
      await Promise.all([app.getNativeWindowHandle().then(handle => Number(handle.readBigUInt64LE()))]),
    ),
  );
  const flows: string[] = [];
  try {
    const page = await app.firstWindow();
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
      timeout: 40000,
    });
    flows.push("cold start");
    await expect
      .poll(() => existsSync(path.join(home, "serve.json")), { timeout: 40000 })
      .toBe(true);
    const discovery = JSON.parse(
      readFileSync(path.join(home, "serve.json"), "utf8"),
    );
    const call = async (route: string, method = "GET", body?: unknown) => {
      const response = await fetch(
        `http://127.0.0.1:${discovery.port}/v1/${route}`,
        {
          method,
          headers: {
            Authorization: `Bearer ${discovery.token}`,
            "Content-Type": "application/json",
          },
          body: body === undefined ? undefined : JSON.stringify(body),
        },
      );
      if (!response.ok) throw new Error(await response.text());
      return response.json();
    };
    await page.getByRole("button", { name: "Models", exact: true }).click();
    const card = page.getByRole("button", { name: `Details for ${model.catalog.title}`, exact: true });
    await card.getByRole("button", { name: "Install", exact: true }).click();
    await page.getByRole("checkbox", { name: "I accept this licence", exact: true }).check();
    await page
      .getByRole("button", { name: "Accept licence and download" })
      .click();
    await expect
      .poll(
        async () =>
          (await call("queue")).operations.find(
            (o: { kind: string }) => o.kind === "download",
          )?.state,
        { timeout: 30000 },
      )
      .toBe("done");
    await expect(
      card.getByText("Installed", { exact: true }),
    ).toBeVisible();
    flows.push("licence consent and verified built-in model install");
    await call("settings", "PUT", { short_side: "keep" });
    await app.files((file => [file])(source));
    await page.getByRole("button", { name: "Home", exact: true }).click();
    for (const mode of ["Standard", "Fast"]) {
      const input = path.join(evidence, `${mode.toLowerCase()}-synthetic.mp4`);
      copyFileSync(source, input);
      await app.files((file => [file])(input));
      await page.getByRole("button", { name: "Add videos" }).click();
      await page.locator(".mode-cards").getByRole("button", { name: new RegExp(`^${mode}`) }).click();
      await page.getByRole("button", { name: "Add to queue" }).click();
      await expect
        .poll(
          async () => {
            const jobs = (await call("queue")).jobs;
            if (jobs.some((j: { state: string }) => j.state === "failed"))
              throw new Error(JSON.stringify(jobs));
            return jobs.filter((j: { state: string }) => j.state === "done")
              .length;
          },
          { timeout: 90000 },
        )
        .toBe(mode === "Standard" ? 1 : 2);
      flows.push(`${mode} job completed`);
    }
    const trial = await call("trial", "POST", {
      file: source,
      seconds: 3,
      settings: { preset: "fast", short_side: "keep" },
    });
    await expect
      .poll(async () => (await call(`operations/${trial.id}`)).state, {
        timeout: 90000,
      })
      .toBe("done");
    flows.push("P1b trial completed");
    await page.getByRole("button", { name: "Models", exact: true }).click();
    await app.files([source]);
    await page.getByRole("button", { name: "Compare on my video" }).click();
    await expect(page.getByText("Compare: done")).toBeVisible({
      timeout: 90000,
    });
    await expect(page.locator("canvas")).toHaveAttribute("data-frame", "0", {
      timeout: 15000,
    });
    flows.push("GPU compare completed");
    await page.screenshot({ path: path.join(evidence, "gpu-compare.png") });
    await (async () => app.quit())();
    await expect
      .poll(() => existsSync(path.join(home, "serve.json")))
      .toBe(false);
    flows.push("Quit");
  } finally {
    await app.close().catch(() => {});
    writeFileSync(path.join(evidence, "stop"), "stop");
    await expect
      .poll(() => existsSync(path.join(evidence, "windows.json")))
      .toBe(true);
    monitor.kill();
    publisher?.closeAllConnections();
    if (publisher) await new Promise<void>(resolve => publisher.close(() => resolve()));
    writeFileSync(
      path.join(evidence, "flows.json"),
      JSON.stringify(flows, null, 2),
    );
  }
  const windows = JSON.parse(
    readFileSync(path.join(evidence, "windows.json"), "utf8"),
  );
  expect(windows.unexpected_windows).toEqual([]);
  expect(flows).toHaveLength(7);
});

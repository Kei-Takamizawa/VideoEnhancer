import { _electron, expect, test } from "@playwright/test";
import { execFileSync, spawn } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

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
  const app = await _electron.launch({
    executablePath: process.env.VE_GUI_PACKAGE_EXE!,
    args: [`--user-data-dir=${path.join(home, "desktop")}`],
    env,
  });
  writeFileSync(path.join(evidence, "app.pid"), String(app.process().pid));
  writeFileSync(
    path.join(evidence, "own-windows.json"),
    JSON.stringify(
      await app.evaluate(({ BrowserWindow }) =>
        BrowserWindow.getAllWindows().map((window) =>
          Number(window.getNativeWindowHandle().readBigUInt64LE()),
        ),
      ),
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
    await page.getByRole("button", { name: "Install", exact: true }).click();
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
      page.getByRole("button", { name: "Installed", exact: true }),
    ).toBeVisible();
    flows.push("licence consent and verified built-in model install");
    await call("settings", "PUT", { short_side: "keep" });
    await app.evaluate(({ dialog }, file) => {
      dialog.showOpenDialog = async () => ({
        canceled: false,
        filePaths: [file],
      });
    }, source);
    await page.getByRole("button", { name: "Home", exact: true }).click();
    for (const mode of ["Standard", "Fast"]) {
      const input = path.join(evidence, `${mode.toLowerCase()}-synthetic.mp4`);
      copyFileSync(source, input);
      await app.evaluate(({ dialog }, file) => {
        dialog.showOpenDialog = async () => ({
          canceled: false,
          filePaths: [file],
        });
      }, input);
      await page.getByRole("button", { name: "+ Add videos" }).click();
      await page.getByRole("button", { name: new RegExp(`^${mode}`) }).click();
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
    await page.getByRole("button", { name: "Compare on my video" }).click();
    await page.getByRole("button", { name: "Compare selected models" }).click();
    await expect(page.getByText("Compare: done")).toBeVisible({
      timeout: 90000,
    });
    await expect(page.locator("canvas")).toHaveAttribute("data-frame", "0", {
      timeout: 15000,
    });
    flows.push("GPU compare completed");
    await page.screenshot({ path: path.join(evidence, "gpu-compare.png") });
    await app.evaluate(({ app }) => app.quit());
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

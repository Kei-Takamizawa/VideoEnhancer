import { desktop } from "../desktop";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import type { Queue } from "../../src/types";
const executable: string = (process.env.VE_TAURI_EXE || "");

test("owner GPU: trial waits, cancels, updates estimate, paired frames stay synchronized, startup preference toggles", async () => {
  test.skip(
    !process.env.VE_GUI_GPU_HOME,
    "Opt-in owner GPU check with already verified model weights.",
  );
  test.setTimeout(300000);
  const root = path.resolve("..");
  const evidence = process.env.VE_GUI_EVIDENCE!;
  mkdirSync(evidence, { recursive: true });
  const source = path.join(evidence, "gpu-synthetic.mp4");
  execFileSync(process.env.VE_FFMPEG || "ffmpeg", [
    "-v",
    "error",
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=512x288:rate=30",
    "-t",
    "20",
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-threads",
    "2",
    "-y",
    source,
  ]);
  const env: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(process.env).filter(
        (e): e is [string, string] => typeof e[1] === "string",
      ),
    ),
    VE_HOME: process.env.VE_GUI_GPU_HOME!,
    VE_ENGINE_ROOT: root,
  };
  delete env.ELECTRON_RUN_AS_NODE;
  const app = await desktop.launch({
    executablePath: executable,
    args: [".", `--user-data-dir=${path.join(env.VE_HOME, "desktop")}`],
    env,
  });
  const page = await app.firstWindow();
  const testProcess = app.process();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let base = "";
  let token = "";
  const call = async (route: string, method = "GET", body?: unknown) => {
    const response = await fetch(`${base}/${route}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  };
  try {
    await expect(page.getByText("Nothing in the queue.")).toBeVisible({
      timeout: 40000,
    });
    await expect
      .poll(() => existsSync(path.join(env.VE_HOME, "serve.json")), {
        timeout: 40000,
      })
      .toBe(true);
    const connection = JSON.parse(
      readFileSync(path.join(env.VE_HOME, "serve.json"), "utf8"),
    );
    base = `http://127.0.0.1:${connection.port}/v1`;
    token = connection.token;
    console.log(
      "GPU service discovered; checking production pipeline and trial admission.",
    );
    await app.files((file => [file])(source));
    await page.getByRole("button", { name: "Add videos" }).click();
    await page.getByText("More options", { exact: true }).click();
    await page
      .getByRole("combobox", { name: /Output short side/ })
      .selectOption("keep");
    await expect(
      page.getByRole("button", { name: "Add to queue" }),
    ).toBeEnabled({ timeout: 30000 });
    await page.getByRole("button", { name: "Add to queue" }).click();
    await expect(page.getByText("Now processing", { exact: true })).toBeVisible(
      {
        timeout: 30000,
      },
    );
    const before = ((await call("queue")) as Queue).jobs[0];
    const openTrial = async () => {
      await page
        .getByRole("button", { name: "Actions for gpu-synthetic.mp4" })
        .click();
      await page
        .getByRole("button", { name: "Try models on this video", exact: true })
        .click();
      await expect(page.getByRole("dialog")).toBeVisible();
    };
    await openTrial();
    await expect(page.getByText("Compare: waiting", { exact: true })).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Cancel", exact: true })
      .click();
    await expect(page.getByText("Compare: cancelled")).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Back", exact: true })
      .click();
    await openTrial();
    await expect(page.getByText("Compare: waiting", { exact: true })).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Back", exact: true })
      .click();
    await page
      .locator(".now-card")
      .getByRole("button", { name: "Pause", exact: true })
      .click();
    await expect
      .poll(
        async () => {
          const operation = ((await call("queue")) as Queue).operations.at(-1);
          if (operation?.state === "failed") throw new Error(operation.error);
          return operation?.state;
        },
        { timeout: 150000 },
      )
      .toBe("done");
    const after = ((await call("queue")) as Queue).jobs[0];
    expect(after.state).toBe("paused");
    expect(after.estimate.seconds).toBeGreaterThan(0);
    await openTrial();
    const picture = page.locator("canvas");
    await expect(picture).toHaveAttribute("data-frame", "0", {
      timeout: 20000,
    });
    await page.getByRole("button", { name: "Play preview" }).click();
    const deltas = await picture.evaluate(async (element) => {
      const values: number[] = [];
      for (let i = 0; i < 20; i++) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        values.push(Number((element as HTMLCanvasElement).dataset.syncDelta));
      }
      return values;
    });
    expect(Math.max(...deltas)).toBeLessThanOrEqual(1e6 / 60);
    await page.getByRole("button", { name: "Pause preview" }).click();
    const last = Number(await picture.getAttribute("data-frame"));
    await page.getByRole("button", { name: "Next frame" }).click();
    await expect(picture).toHaveAttribute("data-frame", String(last + 1));
    for (let step = 0; step < 6; step++) await page.getByRole("button", { name: "Zoom in", exact: true }).click();
    await expect(picture).toHaveCSS("image-rendering", "pixelated");
    await page.getByRole("checkbox", { name: "Side by side" }).check();
    await page.screenshot({ path: path.join(evidence, "trial-synthetic.png") });
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Back", exact: true })
      .click();
    await page
      .locator(".now-card")
      .getByRole("button", { name: "Resume" })
      .click();
    await page.getByRole("button", { name: "History", exact: true }).click();
    await expect.poll(async () => {
      const job = ((await call("queue")) as Queue).jobs[0];
      if (job.state === "failed") throw new Error(JSON.stringify(job));
      return job.state;
    }, { timeout: 100000 }).toBe("done");
    await expect(page.locator(".history-card")).toHaveCount(1, {
      timeout: 100000,
    });
    for (const name of ["Home", "History", "Schedule", "Models", "Settings"]) {
      await page.getByRole("button", { name, exact: true }).click();
      await page.screenshot({
        path: path.join(evidence, `${name.toLowerCase()}-gpu-synthetic.png`),
      });
    }
    const startup = page.getByRole("checkbox", { name: /Start with Windows/ });
    await startup.check();
    await expect
      .poll(
        () =>
          app.startupEnabled(),
        { timeout: 8000 },
      )
      .toBe(true);
    await startup.uncheck();
    await expect
      .poll(
        () =>
          app.startupEnabled(),
        { timeout: 8000 },
      )
      .toBe(false);
    await page.getByRole("button", { name: "Copy diagnostics" }).click();
    expect(
      await app.clipboardText(),
    ).toContain("NVIDIA");
    expect(errors).toEqual([]);
    console.log(
      JSON.stringify({
        before_seconds: before.estimate.seconds,
        after_seconds: after.estimate.seconds,
        max_sync_delta_us: Math.max(...deltas),
      }),
    );
    await (async () => app.quit())();
  } finally {
    if (base)
      await call("settings", "PUT", { start_with_windows: false }).catch(
        () => {},
      );
    await (async () => app.quit())().catch(() => {});
    await Promise.race([
      app.close().catch(() => {}),
      new Promise((resolve) => setTimeout(resolve, 10000)),
    ]);
    if (testProcess.exitCode === null) testProcess.kill();
  }
});

test("owner GPU: legacy speed calibration includes 2160 processing", async () => {
  test.skip(true, "NOT RUN (designer decision): calibration processes 2160; P1f Part R will replace it.");
  const app = await desktop.launch({ env: { ...process.env, VE_HOME: process.env.VE_GUI_GPU_HOME } });
  try {
    const page = await app.firstWindow();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByRole("button", { name: "Run speed calibration" }).click();
    await expect(page.getByText("Calibrate: done")).toBeVisible({ timeout: 150000 });
  } finally { await app.close(); }
});

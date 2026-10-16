import { createRequire } from "node:module";
import { mkdtemp, mkdir, writeFile, readFile, rm, stat } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { expect, test } from "vitest";
const { startupLocation, writeLocation, removePrevious } = createRequire(import.meta.url)("../electron/storage.cjs");

test("a missing saved home stays missing and VE_HOME overrides the stored folder", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "ve-location-"));
  try {
    const file = path.join(root, "desktop/location.json"), old = path.join(root, "old"), target = path.join(root, "missing");
    await mkdir(old); await writeLocation(file, { active: target, previous: old });
    const result = await startupLocation(file, old);
    expect(result.home).toBe(target); expect(result.missing).toBe(true); expect(result.previous).toBe(old);
    expect((await startupLocation(file, old, old)).home).toBe(old);
    expect((await startupLocation(file, old, old)).missing).toBe(false);
    expect(JSON.parse(await readFile(file, "utf8")).active).toBe(target);
    // Choosing the retained copy is an explicit pointer switch.
    await writeLocation(file, { active: old, previous: target });
    expect((await startupLocation(file, target)).missing).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("removing an old folder refuses an unverified or active folder", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "ve-removal-"));
  try {
    const file = path.join(root, "location.json");
    await writeFile(file, JSON.stringify({ active: root, previous: root }));
    await expect(removePrevious(file, root)).rejects.toThrow("no verified old folder");
  } finally { await rm(root, { recursive: true, force: true }); }
});


test("old-folder removal needs a successful location record and preserves the active data", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "ve-old-folder-"));
  try {
    const old = path.join(root, "old"), active = path.join(root, "active"), file = path.join(root, "desktop/location.json");
    await mkdir(old); await mkdir(active);
    await writeFile(path.join(old, "settings.json"), "old");
    await writeFile(path.join(active, "settings.json"), "active");
    const identity = await stat(old, { bigint: true });
    await writeLocation(file, { active, previous: old, previousIdentity: { dev: String(identity.dev), ino: String(identity.ino) } });
    expect((await removePrevious(file, active)).removed).toBe(old);
    await expect(stat(old)).rejects.toMatchObject({ code: "ENOENT" });
    expect(await readFile(path.join(active, "settings.json"), "utf8")).toBe("active");
    expect(JSON.parse(await readFile(file, "utf8")).previous).toBeUndefined();
  } finally { await rm(root, { recursive: true, force: true }); }
});

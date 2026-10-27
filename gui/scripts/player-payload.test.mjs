import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { verifyPlayerPayload } from "./player-payload.mjs";

test("packaging authenticates every DLL, source, manifest and licence inventory", () => {
  const parent = path.resolve(tmpdir());
  const folder = path.resolve(parent, `ve-player-payload-${process.pid}-${Date.now()}`);
  assert.ok(folder.startsWith(parent + path.sep));
  mkdirSync(path.join(folder, "LICENSES/mpv"), { recursive: true, mode: 0o777 });
  const hash = value => createHash("sha256").update(value).digest("hex");
  const files = {
    "libmpv-2.dll": "synthetic mpv",
    "libspirv-cross-c-shared.dll": "synthetic spirv",
    "libwinpthread-1.dll": "synthetic threads",
    "sources.tar.zst": "synthetic source archive",
    "source-manifest.json": "{}",
    "LICENSES/mpv/LICENSE": "synthetic licence text",
    "DISTRIBUTION.md": "synthetic distribution terms",
  };
  for (const [name, value] of Object.entries(files)) writeFileSync(path.join(folder, name), value);
  const inventory = Object.entries(files).map(([name, value]) => `${hash(value)}  ${name}\n`).join("");
  writeFileSync(path.join(folder, "SHA256SUMS"), inventory);
  const record = file => ({ file, bytes: Buffer.byteLength(files[file]), sha256: hash(files[file]) });
  const lock = { dlls: Object.keys(files).filter(file => file.endsWith(".dll")).map(record), sources: record("sources.tar.zst"), artifact_manifest_sha256: hash("{}"), checksum_inventory_sha256: hash(inventory) };
  try {
    assert.doesNotThrow(() => verifyPlayerPayload(folder, lock));
    for (const name of ["libmpv-2.dll", "libspirv-cross-c-shared.dll", "libwinpthread-1.dll", "sources.tar.zst", "source-manifest.json", "LICENSES/mpv/LICENSE", "SHA256SUMS"]) {
      const original = readFileSync(path.join(folder, name));
      writeFileSync(path.join(folder, name), "modified");
      assert.throws(() => verifyPlayerPayload(folder, lock), /mismatch/i);
      writeFileSync(path.join(folder, name), original);
    }
    writeFileSync(path.join(folder, "LICENSES/mpv/extra.txt"), "unverified");
    assert.throws(() => verifyPlayerPayload(folder, lock), /Unverified licence/);
  } finally {
    // The resolved, test-created target is inside the session's TEMP folder.
    assert.ok(folder.startsWith(parent + path.sep));
    rmSync(folder, { recursive: true });
  }
});

import { createHash } from "node:crypto";
import { readFileSync, statSync, readdirSync, lstatSync } from "node:fs";
import path from "node:path";

export function verifyFile(folder, record) {
  const file = path.join(folder, record.file);
  const bytes = readFileSync(file);
  if (bytes.length !== record.bytes || createHash("sha256").update(bytes).digest("hex") !== record.sha256) throw new Error(`Native player payload mismatch: ${record.file}`);
}
export function verifyPlayerPayload(folder, lock) {
  for (const record of [...lock.dlls, lock.sources]) verifyFile(folder, record);
  const manifest = readFileSync(path.join(folder, "source-manifest.json"));
  if (createHash("sha256").update(manifest).digest("hex") !== lock.artifact_manifest_sha256) throw new Error("Native player manifest mismatch");
  if (!statSync(path.join(folder, "LICENSES")).isDirectory()) throw new Error("Missing licence texts");
  for (const name of ["DISTRIBUTION.md", "SHA256SUMS"]) if (!statSync(path.join(folder, name)).isFile()) throw new Error(`Missing ${name}`);
  // Authenticate every licence/build receipt against the accepted manifest's
  // checksum inventory. Reject path traversal and symlinks in the payload.
  const root = path.resolve(folder);
  if (createHash("sha256").update(readFileSync(path.join(folder, "SHA256SUMS"))).digest("hex") !== lock.checksum_inventory_sha256) throw new Error("Checksum inventory mismatch");
  const listed = new Set();
  for (const line of readFileSync(path.join(folder, "SHA256SUMS"), "utf8").trim().split(/\r?\n/)) {
    const match = /^([a-f0-9]{64})\s+\*?(.+)$/.exec(line);
    if (!match) throw new Error("Invalid checksum inventory");
    const file = path.resolve(root, match[2]);
    if (!file.startsWith(root + path.sep)) throw new Error("Unsafe checksum path");
    listed.add(file);
    let part = file;
    while (part !== root) { if (lstatSync(part).isSymbolicLink()) throw new Error("Symlink in native payload"); part = path.dirname(part); }
    const bytes = readFileSync(file);
    if (createHash("sha256").update(bytes).digest("hex") !== match[1]) throw new Error(`Payload checksum mismatch: ${match[2]}`);
  }
  const checkLicences = folder => {
    for (const entry of readdirSync(folder, { withFileTypes: true })) {
      const file = path.join(folder, entry.name);
      if (entry.isSymbolicLink()) throw new Error("Symlink in licence payload");
      if (entry.isDirectory()) checkLicences(file);
      else if (!listed.has(path.resolve(file))) throw new Error("Unverified licence file");
    }
  };
  checkLicences(path.join(folder, "LICENSES"));
  if (readdirSync(path.join(folder, "LICENSES")).length === 0) throw new Error("Empty licence directory");
}

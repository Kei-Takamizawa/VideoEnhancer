import { execFileSync } from "node:child_process";
import { copyFileSync, cpSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";

export function applicationLicences(destination) {
  const root = path.join(destination, "LICENSES", "VideoEnhancer");
  mkdirSync(root, { recursive: true });
  copyFileSync("../LICENSE", path.join(root, "VideoEnhancer-MIT.txt"));
  for (const name of ["react", "react-dom", "lucide-react", "mp4box", "@tauri-apps/api"]) {
    const folder = `node_modules/${name}`;
    const files = readdirSync(folder).filter(file => /^(license|licence|copying|copyright|notice)/i.test(file));
    if (!files.length) throw new Error(`Missing frontend licence material: ${name}`);
    for (const file of files) copyFileSync(path.join(folder, file), path.join(root, `${name.replaceAll("/", "_")}-${file}`));
  }
  const metadata = JSON.parse(execFileSync("cargo", ["metadata", "--offline", "--locked", "--manifest-path", "src-tauri/Cargo.toml", "--filter-platform", "x86_64-pc-windows-msvc", "--format-version", "1"], { encoding: "utf8", maxBuffer: 16 * 1024 * 1024 }));
  const used = new Set(metadata.resolve.nodes.map(node => node.id));
  const supplements = JSON.parse(readFileSync("licences/provenance.json", "utf8"));
  for (const crate of metadata.packages.filter(crate => used.has(crate.id) && crate.source)) {
    const folder = path.dirname(crate.manifest_path);
    const notices = readdirSync(folder, { withFileTypes: true }).filter(entry => /^(licen[cs]e|copying|copyright|notices?|unlicense)([._-]|$)/i.test(entry.name));
    const target = path.join(root, `${crate.name}-${crate.version}`);
    mkdirSync(target, { recursive: true });
    if (notices.length === 0) {
      const record = supplements.find(record => record.crate === crate.name && record.version === crate.version);
      if (!record) throw new Error(`Missing application licence material: ${crate.name} ${crate.version}`);
      const bytes = readFileSync(path.join("licences", record.file));
      if (bytes.length !== record.bytes || createHash("sha256").update(bytes).digest("hex") !== record.sha256) throw new Error("Supplemental licence checksum mismatch");
      copyFileSync(path.join("licences", record.file), path.join(target, "LICENSE"));
    }
    for (const entry of notices) {
      if (entry.isSymbolicLink()) throw new Error("Symlink in application licence material");
      cpSync(path.join(folder, entry.name), path.join(target, entry.name), { recursive: true });
    }
    if (crate.name === "selectors") cpSync(folder, path.join(target, "source"), { recursive: true });
  }
  copyFileSync("licences/provenance.json", path.join(root, "supplemental-licence-provenance.json"));
}

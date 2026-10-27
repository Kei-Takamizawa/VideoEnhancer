import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, writeFileSync, existsSync, readdirSync, readFileSync, cpSync } from "node:fs";
import path from "node:path";
import { verifyPlayerPayload } from "./player-payload.mjs";
import { applicationLicences } from "./application-licences.mjs";

const destination = process.env.VE_TAURI_PACKAGE_OUT;
if (!destination || !["../../package/VideoEnhancer", "../../package/VideoEnhancer-candidate"].some(folder => path.resolve(destination) === path.resolve(folder))) throw new Error("Set VE_TAURI_PACKAGE_OUT to work/package/VideoEnhancer or VideoEnhancer-candidate.");
const payload = process.env.VE_LIBMPV_DIR;
const lock = JSON.parse(readFileSync("src-tauri/libmpv.lock.json", "utf8"));
if (payload) verifyPlayerPayload(payload, lock);
const allowed = ["VideoEnhancer.exe", "engine-location.json", "THIRD_PARTY_NOTICES.md"];
if (existsSync(destination) && readdirSync(destination).some(name => !allowed.includes(name))) throw new Error("The candidate folder contains unexpected files; preserve them before packaging.");
execFileSync(process.platform === "win32" ? "npm.cmd" : "npm", ["run", "build:desktop"], { stdio: "inherit", shell: process.platform === "win32" });
if (payload) execFileSync("cargo", ["build", "--release", "--locked", "--manifest-path", "src-tauri/player/Cargo.toml"], { stdio: "inherit" });
mkdirSync(destination, { recursive: true });
copyFileSync(path.join(process.env.CARGO_TARGET_DIR || "src-tauri/target", "release/VideoEnhancer.exe"), path.join(destination, "VideoEnhancer.exe"));
writeFileSync(path.join(destination, "engine-location.json"), JSON.stringify({ root: path.resolve("..") }, null, 2));
copyFileSync("THIRD_PARTY_NOTICES.md", path.join(destination, "THIRD_PARTY_NOTICES.md"));
applicationLicences(destination);
if (payload) {
  copyFileSync(path.join(process.env.CARGO_TARGET_DIR || "src-tauri/player/target", "release/VideoEnhancer-Player.exe"), path.join(destination, "VideoEnhancer-Player.exe"));
  for (const { file } of lock.dlls) copyFileSync(path.join(payload, file), path.join(destination, file));
  cpSync(path.join(payload, "LICENSES"), path.join(destination, "LICENSES"), { recursive: true });
  copyFileSync(path.join(payload, "DISTRIBUTION.md"), path.join(destination, "DISTRIBUTION.md"));
  for (const name of ["sources.tar.zst", "SHA256SUMS", "source-manifest.json"]) copyFileSync(path.join(payload, name), path.join(path.dirname(destination), name));
}
console.log(`Unsigned portable candidate: ${path.resolve(destination)}`);

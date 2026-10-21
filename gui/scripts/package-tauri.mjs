import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";

const destination = process.env.VE_TAURI_PACKAGE_OUT;
if (!destination || path.resolve(destination) !== path.resolve("../../package/VideoEnhancer")) throw new Error("Set VE_TAURI_PACKAGE_OUT to work/package/VideoEnhancer.");
if (existsSync(destination) && readdirSync(destination).some(name => !["VideoEnhancer.exe", "engine-location.json"].includes(name))) throw new Error("The candidate folder contains unexpected files; preserve them before packaging.");
execFileSync(process.platform === "win32" ? "npm.cmd" : "npm", ["run", "build:desktop"], { stdio: "inherit", shell: process.platform === "win32" });
mkdirSync(destination, { recursive: true });
copyFileSync(path.join(process.env.CARGO_TARGET_DIR || "src-tauri/target", "release/VideoEnhancer.exe"), path.join(destination, "VideoEnhancer.exe"));
writeFileSync(path.join(destination, "engine-location.json"), JSON.stringify({ root: path.resolve("..") }, null, 2));
console.log(`Unsigned portable candidate: ${path.resolve(destination)}`);

import { packager } from "@electron/packager";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const folders = await packager({
  dir: ".",
  name: "VideoEnhancer",
  platform: "win32",
  arch: "x64",
  out: process.env.VE_GUI_PACKAGE_OUT || "release",
  overwrite: true,
  asar: true,
  ignore: [
    /^\/src($|\/)/,
    /^\/tests($|\/)/,
    /^\/test-results($|\/)/,
    /^\/playwright-report($|\/)/,
    /^\/release($|\/)/,
  ],
});
for (const folder of folders) {
  await mkdir(path.join(folder, "resources"), { recursive: true });
  await writeFile(
    path.join(folder, "resources", "engine-location.json"),
    JSON.stringify({ root: path.resolve("..") }, null, 2),
  );
}
console.log(`Unsigned development app: ${folders.join(", ")}`);

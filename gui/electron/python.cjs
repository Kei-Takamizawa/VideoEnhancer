const fs = require("node:fs/promises");
const path = require("node:path");

async function servicePython(configured, platform = process.platform) {
  if (
    platform !== "win32" ||
    path.basename(configured).toLowerCase() === "pythonw.exe"
  )
    return { executable: configured, fallback: false };
  const sibling = path.join(path.dirname(configured), "pythonw.exe");
  try {
    await fs.access(sibling);
    return { executable: sibling, fallback: false };
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    return { executable: configured, fallback: true };
  }
}

module.exports = { servicePython };

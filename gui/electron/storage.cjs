const fs = require('node:fs/promises');
const path = require('node:path');

async function readLocation(file) {
  try { return JSON.parse(await fs.readFile(file, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return {}; throw error; }
}
async function writeLocation(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  const handle = await fs.open(tmp, 'w');
  try { await handle.writeFile(JSON.stringify(value)); await handle.sync(); }
  finally { await handle.close(); }
  await fs.rename(tmp, file);
}
async function startupLocation(file, fallback, override) {
  const saved = await readLocation(file);
  const home = override || saved.active || fallback;
  return { ...saved, home, missing: !!(!override && saved.active && !(await exists(home))) };
}
async function exists(folder) {
  try { return (await fs.stat(folder)).isDirectory(); }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}
async function removePrevious(file, current) {
  const saved = await readLocation(file);
  if (saved.active !== current || !saved.previous || !saved.previousIdentity)
    throw new Error('There is no verified old folder to remove.');
  const old = path.resolve(saved.previous), active = path.resolve(current);
  if (old === active || active.startsWith(old + path.sep) || old === path.parse(old).root)
    throw new Error('The old folder is not safe to remove.');
  const info = await fs.lstat(old, { bigint: true });
  if (info.isSymbolicLink() || String(info.dev) !== saved.previousIdentity.dev || String(info.ino) !== saved.previousIdentity.ino)
    throw new Error('The old folder changed. It was kept.');
  async function check(folder) {
    for (const entry of await fs.readdir(folder, { withFileTypes: true })) {
      const p = path.join(folder, entry.name);
      if ((await fs.lstat(p)).isSymbolicLink()) throw new Error('The old folder contains a linked path. It was kept.');
      if (entry.isDirectory()) await check(p);
    }
  }
  await check(old);
  await fs.rm(old, { recursive: true });
  delete saved.previous; delete saved.previousIdentity;
  await writeLocation(file, saved);
  return { removed: old };
}
module.exports = { readLocation, writeLocation, startupLocation, removePrevious };

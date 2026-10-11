import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { expect, test } from "vitest";

const { servicePython } = createRequire(import.meta.url)(
  "../electron/python.cjs",
);

test("Windows service uses sibling pythonw and logs a missing-sibling fallback", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "ve-python-selection-"));
  try {
    const consolePython = path.join(directory, "python.exe");
    const windowlessPython = path.join(directory, "pythonw.exe");
    expect(await servicePython(consolePython, "win32")).toEqual({
      executable: consolePython,
      fallback: true,
    });
    await writeFile(windowlessPython, "fixture");
    expect(await servicePython(consolePython, "win32")).toEqual({
      executable: windowlessPython,
      fallback: false,
    });
    expect(await servicePython(windowlessPython, "win32")).toEqual({
      executable: windowlessPython,
      fallback: false,
    });
    expect(await servicePython(consolePython, "linux")).toEqual({
      executable: consolePython,
      fallback: false,
    });
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

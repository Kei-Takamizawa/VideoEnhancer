import { createServer } from "vite";
import { spawn } from "node:child_process";
import electron from "electron";
const server = await createServer({
  server: { host: "127.0.0.1", port: 5173, strictPort: true },
});
await server.listen();
const env = { ...process.env, VE_GUI_DEV: "1" };
delete env.ELECTRON_RUN_AS_NODE;
const app = spawn(electron, ["."], { stdio: "inherit", env });
app.on("exit", async (code) => {
  await server.close();
  process.exit(code || 0);
});

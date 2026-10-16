import { defineConfig } from "@playwright/test";
export default defineConfig({ testDir: "tests/perf", workers: 1, timeout: 120000, reporter: "list", use: { trace: "retain-on-failure" } });

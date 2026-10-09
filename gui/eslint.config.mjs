import js from "@eslint/js";
import tseslint from "typescript-eslint";
export default tseslint.config(
  {
    ignores: [
      "dist/**",
      "release/**",
      "node_modules/**",
      "test-results/**",
      "playwright-report/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.cjs", "**/*.mjs"],
    languageOptions: {
      globals: {
        require: "readonly",
        module: "readonly",
        process: "readonly",
        Buffer: "readonly",
        console: "readonly",
        fetch: "readonly",
        AbortSignal: "readonly",
        Response: "readonly",
        URL: "readonly",
        setTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        __dirname: "readonly",
      },
    },
  },
  {
    files: ["electron/*.cjs"],
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
);

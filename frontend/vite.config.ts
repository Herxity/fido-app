import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { host: "localhost", port: 5173, strictPort: true, proxy: { "/api": "http://localhost:8000" } },
  test: { environment: "jsdom", setupFiles: "./src/test/setup.ts", css: true, globals: true, exclude: ["e2e/**", "node_modules/**"] },
});

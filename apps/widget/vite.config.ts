import { defineConfig } from "vite";

export default defineConfig({
  build: {
    lib: {
      entry: "src/index.ts",
      formats: ["iife"],
      name: "AgentHubWidget",
      fileName: () => "widget/v1/loader.js",
    },
  },
});

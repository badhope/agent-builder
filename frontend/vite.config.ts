import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/v1": {
        target: process.env.VITE_API_BASE ?? "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      "/ws": {
        target: process.env.VITE_API_BASE ?? "http://localhost:8000",
        changeOrigin: true,
        secure: false,
        ws: true,
      },
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query"],
          chart: ["recharts"],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});

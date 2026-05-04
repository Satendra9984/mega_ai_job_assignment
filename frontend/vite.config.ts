import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite proxies /ws and /api to the FastAPI backend (localhost:8000).
// Prod: nginx on :3000 proxies the same paths; the browser uses the page origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/ws": { target: "http://127.0.0.1:8000", ws: true, changeOrigin: true },
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});

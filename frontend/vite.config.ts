import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, /api and /health are proxied to FastAPI so the browser sees one origin (no CORS setup needed).
// API_PROXY overrides the backend address, e.g. API_PROXY=http://localhost:8001 when port 8000 is busy.
const backend = process.env.API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/health": backend,
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend is the only origin the app talks to. In dev we proxy /api so the
// browser never needs CORS and the reality of "one local server" is preserved.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});

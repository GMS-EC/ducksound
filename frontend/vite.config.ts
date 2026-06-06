import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = "http://web:8604";

function spaBypass(req: any, _res: any, _options: any) {
  if (req.headers.accept?.includes("text/html")) {
    return "/index.html";
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
      "/login": { target: apiTarget, changeOrigin: true },
      "/logout": { target: apiTarget, changeOrigin: true },
      "/admin": { target: apiTarget, changeOrigin: true },
      "/audio": { target: apiTarget, changeOrigin: true },
      "/lyrics": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/album-art": { target: apiTarget, changeOrigin: true },
      "/daily-mix-cover": { target: apiTarget, changeOrigin: true },
      "/service-worker.js": { target: apiTarget, changeOrigin: true },
      "/dashboard": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/explore": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/favoritos": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/folders": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/colecciones": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/coleccion": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/daily-mixes": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/daily-mix": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/artists": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/artist": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/albums": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/album": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/profile": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
      "/stats": { target: apiTarget, changeOrigin: true, bypass: spaBypass },
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    // Allow requests forwarded by the Caddy reverse proxy from our public
    // hostnames. Vite blocks unknown Host headers by default ("Blocked
    // request...").
    allowedHosts: [
      "marketpulse1.me",
      "www.marketpulse1.me",
      "localhost",
    ],
    watch: {
      usePolling: true,
    },
    hmr: {
      overlay: false,
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));

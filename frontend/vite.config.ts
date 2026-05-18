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
    // request..."). The IP host is for direct fallback access via :8080.
    allowedHosts: [
      "marketpulse1.me",
      "www.marketpulse1.me",
      "46.101.174.12",
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

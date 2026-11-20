import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "chat-ui",
  base: "/chat/",
  plugins: [react()],
  server: {
    proxy: {
      "/v1": "http://127.0.0.1:8081",
    },
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O build sai dentro do pacote Python: quem instala via pip recebe o app
// pronto e não precisa de Node para nada.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "../fintips/web", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8420" },
  },
});

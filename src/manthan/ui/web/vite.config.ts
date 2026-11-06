import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// outDir resolves against this folder (the Vite root), so run the build from here.
export default defineConfig({
  base: "/",
  plugins: [react()],
  build: { outDir: "../static", emptyOutDir: true },
});

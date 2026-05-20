import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import fs from "fs";

const dataDir = path.resolve(__dirname, "../../data");
const quizVisual = path.join(dataDir, "quiz-visual");

/** Serve MinerU images + quiz-visual assets at /quiz-visual/... */
function serveDataPlugin() {
  return {
    name: "serve-ic3-data",
    configureServer(server: import("vite").ViteDevServer) {
      server.middlewares.use("/quiz-visual", (req, res, next) => {
        const url = (req.url || "/").split("?")[0];
        const rel = url.replace(/^\/+/, "");
        const candidates = [
          path.join(quizVisual, rel),
          path.join(dataDir, "mineru_out", "ic3_unlocked", "ocr", rel),
          path.join(dataDir, "mineru_out_full", "ic3_unlocked", "ocr", rel),
        ];
        for (const filePath of candidates) {
          if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
            const ext = path.extname(filePath).toLowerCase();
            const types: Record<string, string> = {
              ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg",
              ".png": "image/png",
              ".json": "application/json",
            };
            res.setHeader("Content-Type", types[ext] || "application/octet-stream");
            fs.createReadStream(filePath).pipe(res);
            return;
          }
        }
        next();
      });
    },
  };
}

function copyQuizVisualOnBuild() {
  return {
    name: "copy-quiz-visual",
    closeBundle() {
      const src = path.join(dataDir, "quiz-visual");
      const dest = path.join(__dirname, "dist", "quiz-visual");
      if (fs.existsSync(src)) {
        fs.cpSync(src, dest, { recursive: true });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), serveDataPlugin(), copyQuizVisualOnBuild()],
  resolve: {
    alias: {
      "@ic3-quiz/core": path.resolve(__dirname, "../../packages/ic3-quiz-core/src"),
    },
  },
  publicDir: path.resolve(__dirname, "../../data"),
  server: { port: 5173 },
});

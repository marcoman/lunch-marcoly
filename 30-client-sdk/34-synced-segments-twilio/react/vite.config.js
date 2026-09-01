/**
 * Vite + lab REST proxy. Flag evaluation stays in the React Web SDK.
 * Token and project keys stay in this process — not in the page.
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { apiConfig, applyFlagControl, listFlagControls } from "./flag-controls.js";

const PORT = Number.parseInt(process.env.PORT || "8341", 10);

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(payload);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function labApiPlugin() {
  return {
    name: "lab-api",
    configureServer(server) {
      const id = (process.env.LD_CLIENT_SIDE_ID || "").trim();
      console.log("34-synced-segments-twilio[react]");
      console.log(`Open http://127.0.0.1:${PORT}/`);
      if (!id) {
        console.warn("Warning: LD_CLIENT_SIDE_ID is unset — flags stay at code defaults.");
      }
      const cfg = apiConfig();
      if (!cfg.configured) {
        console.warn("Warning: lab Controls need " + cfg.missing.join(", ") + ".");
      }
      if (!(process.env.SEGMENT_WRITE_KEY || "").trim()) {
        console.warn("Warning: SEGMENT_WRITE_KEY is unset — Join inner circle cannot call Twilio Segment.");
      }

      server.middlewares.use(async (req, res, next) => {
        const pathname = (req.url || "").split("?")[0];
        if (!pathname.startsWith("/api/")) {
          next();
          return;
        }
        try {
          if (pathname === "/api/config" && req.method === "GET") {
            const segmentWriteKey = (process.env.SEGMENT_WRITE_KEY || "").trim();
            sendJson(res, 200, {
              clientSideId: id || null,
              segmentWriteKey: segmentWriteKey || null,
              controls: apiConfig(),
            });
            return;
          }
          if (pathname === "/api/flag-controls" && req.method === "GET") {
            sendJson(res, 200, await listFlagControls());
            return;
          }
          if (pathname === "/api/flag-controls" && req.method === "POST") {
            const body = await readBody(req);
            sendJson(
              res,
              200,
              await applyFlagControl(body.key, {
                on: body.on,
                fallthrough: body.fallthrough,
              })
            );
            return;
          }
          sendJson(res, 404, { error: "Not found" });
        } catch (err) {
          sendJson(res, err.status || 500, { error: String(err.message || err) });
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), labApiPlugin()],
  server: {
    host: "127.0.0.1",
    port: PORT,
    strictPort: true,
  },
});

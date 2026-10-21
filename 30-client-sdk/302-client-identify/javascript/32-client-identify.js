#!/usr/bin/env node
/**
 * Static host + config + REST Controls proxy.
 * The page evaluates flags with the JavaScript SDK. This process never
 * evaluates flags with LD_SDK_KEY.
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const { apiConfig, listFlagControls, applyFlagControl } = require("./flag-controls");

const PORT = Number.parseInt(process.env.PORT || "8320", 10);
const ROOT = __dirname;
const LD_BUNDLE = path.join(
  ROOT,
  "node_modules",
  "launchdarkly-js-client-sdk",
  "dist",
  "ldclient.min.js"
);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
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

function serveFile(res, filePath) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }
    const ext = path.extname(filePath);
    res.writeHead(200, {
      "Content-Type": MIME[ext] || "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
    });
    res.end(data);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);

  if (url.pathname === "/api/config" && req.method === "GET") {
    const clientSideId = (process.env.LD_CLIENT_SIDE_ID || "").trim();
    sendJson(res, 200, {
      clientSideId: clientSideId || null,
      controls: apiConfig(),
    });
    return;
  }

  if (url.pathname === "/api/flag-controls" && req.method === "GET") {
    try {
      sendJson(res, 200, await listFlagControls());
    } catch (err) {
      sendJson(res, err.status || 500, { error: String(err.message || err) });
    }
    return;
  }

  if (url.pathname === "/api/flag-controls" && req.method === "POST") {
    try {
      const body = await readBody(req);
      sendJson(
        res,
        200,
        await applyFlagControl(body.key, {
          on: body.on,
          fallthrough: body.fallthrough,
        })
      );
    } catch (err) {
      sendJson(res, err.status || 500, { error: String(err.message || err) });
    }
    return;
  }

  if (url.pathname === "/vendor/ldclient.min.js") {
    serveFile(res, LD_BUNDLE);
    return;
  }

  const rawPath = url.pathname === "/" ? "/index.html" : url.pathname;
  const relative = path.normalize(decodeURIComponent(rawPath)).replace(/^[/\\]+/, "");
  const filePath = path.join(ROOT, relative);
  if (!filePath.startsWith(ROOT + path.sep) && filePath !== ROOT) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }
  serveFile(res, filePath);
});

server.listen(PORT, "127.0.0.1", () => {
  const id = (process.env.LD_CLIENT_SIDE_ID || "").trim();
  console.log("32-client-identify[javascript]");
  console.log(`Open http://127.0.0.1:${PORT}/`);
  if (!id) {
    console.warn("Warning: LD_CLIENT_SIDE_ID is unset — flags stay at code defaults.");
  }
  const cfg = apiConfig();
  if (!cfg.configured) {
    console.warn("Warning: lab Controls need " + cfg.missing.join(", ") + ".");
  }
  console.log("Press Ctrl+C to stop.");
});

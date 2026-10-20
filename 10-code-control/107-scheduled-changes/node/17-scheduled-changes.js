#!/usr/bin/env node
/** Serve the scheduled-changes grid navigator and REST-backed lab. */

const fs = require("fs");
const http = require("http");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const {
  FLAG_KEY,
  apiConfig,
  evaluateHighlight,
  listScheduledChanges,
  normalizeUsername,
  startScheduledChange,
  stopScheduledChange,
} = require("../scheduled-change");

const PORT = Number(process.env.PORT || 8171);
const ROOT = __dirname;
let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = (process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    console.warn("Warning: LD_SDK_KEY not set — highlight defaults to none.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch {
    console.warn("Warning: LaunchDarkly SDK did not initialize.");
    ldClient.close();
    ldClient = null;
  }
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Cache-Control": "no-store",
  });
  res.end(payload);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.setEncoding("utf8");
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 1024 * 1024) {
        reject(new Error("Request body is too large"));
        req.destroy();
      }
    });
    req.on("end", () => {
      try {
        const value = JSON.parse(raw || "{}");
        if (!value || Array.isArray(value) || typeof value !== "object") {
          throw new Error("Request body must be a JSON object");
        }
        resolve(value);
      } catch (error) {
        reject(error instanceof SyntaxError ? new Error("Request body must be JSON") : error);
      }
    });
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  if (req.method === "GET" && url.pathname === "/api/flags") {
    try {
      const username = normalizeUsername(url.searchParams.get("username"));
      return sendJson(res, 200, await evaluateHighlight(ldClient, username));
    } catch (error) {
      return sendJson(res, 400, { error: error.message });
    }
  }
  if (req.method === "GET" && url.pathname === "/api/schedule") {
    try {
      return sendJson(res, 200, await listScheduledChanges());
    } catch (error) {
      return sendJson(res, 502, { error: error.message, ...apiConfig() });
    }
  }
  if (req.method === "GET" && url.pathname === "/api/bootstrap") {
    return sendJson(res, 200, {
      appBanner: "17-scheduled-changes[node]",
      flagKey: FLAG_KEY,
      controls: apiConfig(),
      port: PORT,
    });
  }
  if (req.method === "POST" && url.pathname === "/api/schedule") {
    try {
      const body = await readJson(req);
      return sendJson(res, 201, await startScheduledChange(Number(body.minutes)));
    } catch (error) {
      const status = /between 1 and 60|Request body/.test(error.message) ? 400 : 502;
      return sendJson(res, status, { ok: false, error: error.message });
    }
  }
  if (req.method === "DELETE" && url.pathname === "/api/schedule") {
    try {
      return sendJson(res, 200, await stopScheduledChange());
    } catch (error) {
      return sendJson(res, 502, { ok: false, error: error.message });
    }
  }

  const urlPath = url.pathname === "/" ? "/index.html" : url.pathname;
  const filePath = path.resolve(ROOT, `.${urlPath}`);
  if (!filePath.startsWith(`${ROOT}${path.sep}`)) {
    res.writeHead(403);
    return res.end("Forbidden");
  }
  fs.readFile(filePath, (error, data) => {
    if (error) {
      res.writeHead(404);
      return res.end("Not found");
    }
    res.writeHead(200, {
      "Content-Type": filePath.endsWith(".html") ? "text/html" : "text/plain",
    });
    res.end(data);
  });
});

initLaunchDarkly().then(() => {
  server.listen(PORT, "127.0.0.1", () => {
    console.log("17-scheduled-changes[node]");
    console.log(`Open http://127.0.0.1:${PORT}/`);
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

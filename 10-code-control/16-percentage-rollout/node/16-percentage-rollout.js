#!/usr/bin/env node
/** Serve the static percentage-rollout grid navigator. */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateRollout, normalizeUsername } = require("../rollout");

const PORT = Number(process.env.PORT || 8080);
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

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  if (req.method === "GET" && url.pathname === "/api/flags") {
    try {
      const username = normalizeUsername(url.searchParams.get("username"));
      return sendJson(res, 200, await evaluateRollout(ldClient, username));
    } catch (error) {
      return sendJson(res, 400, { error: error.message });
    }
  }
  if (req.method === "GET" && url.pathname === "/api/bootstrap") {
    return sendJson(res, 200, {
      appBanner: "16-percentage-rollout[node]",
      flagKey: "enable-grid-selection-highlight-pct",
      rollout: "30% green / 70% none",
      port: PORT,
    });
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
    console.log("16-percentage-rollout[node]");
    console.log(`Open http://127.0.0.1:${PORT}/`);
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

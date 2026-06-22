#!/usr/bin/env node
/** Serve the segments-by-name grid navigator web UI on a local HTTP server. */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateHighlight } = require("../segment-style");

// LaunchDarkly capability: String flag variation from segment targeting
// See: https://launchdarkly.com/docs/home/flags/segments

const PORT = 8080;
const ROOT = __dirname;

let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) return;
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (_) {
    ldClient = null;
  }
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

async function runServer() {
  await initLaunchDarkly();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

    if (url.pathname === "/api/highlight") {
      const username = (url.searchParams.get("username") || "").trim();
      if (!username) {
        sendJson(res, 400, { error: "username query parameter is required" });
        return;
      }
      const result = await evaluateHighlight(ldClient, username);
      sendJson(res, 200, result);
      return;
    }

    const urlPath = url.pathname === "/" ? "/index.html" : url.pathname;
    const filePath = path.join(ROOT, urlPath);

    if (!filePath.startsWith(ROOT)) {
      res.writeHead(403);
      res.end("Forbidden");
      return;
    }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }
      const ext = path.extname(filePath);
      const type = ext === ".html" ? "text/html" : "text/plain";
      res.writeHead(200, { "Content-Type": type });
      res.end(data);
    });
  });

  server.listen(PORT, "127.0.0.1", () => {
    console.log(`Grid navigator (segments by name) running at http://127.0.0.1:${PORT}/`);
    console.log("Press Ctrl+C to stop.");
  });
}

const args = process.argv.slice(2);
if (args.length >= 2 && args[0] === "--evaluate-once") {
  (async () => {
    await initLaunchDarkly();
    try {
      const result = await evaluateHighlight(ldClient, args[1]);
      console.log(JSON.stringify(result));
    } finally {
      if (ldClient) await ldClient.close();
    }
    process.exit(0);
  })();
} else {
  runServer().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

process.on("SIGINT", async () => {
  if (ldClient) await ldClient.close();
  process.exit(0);
});

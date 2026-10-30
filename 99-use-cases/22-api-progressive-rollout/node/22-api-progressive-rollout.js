#!/usr/bin/env node
/**
 * Serve the API progressive-rollout grid.
 *
 * Start progressive release POSTs the environment release.
 * /api/release reads it back for the drawer.
 *
 * LaunchDarkly: string variation, plus environment releases
 * https://launchdarkly.com/docs/api/environment-releases
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateHighlight } = require("./highlight-eval");
const releases = require("./release-status");

const PORT = Number(process.env.PORT || 8781);
const ROOT = __dirname;
let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) return;
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 10 });
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

function resultStatus(body) {
  return body && (body.error || body.configured === false) ? 400 : 200;
}

async function runServer() {
  await initLaunchDarkly();
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
    if (url.pathname === "/api/highlight" && req.method === "GET") {
      const username = (url.searchParams.get("username") || "").trim();
      if (!username) {
        sendJson(res, 400, { error: "username query parameter is required" });
        return;
      }
      sendJson(res, 200, await evaluateHighlight(ldClient, username));
      return;
    }
    if (url.pathname === "/api/release" && req.method === "GET") {
      sendJson(res, 200, await releases.latestProgressiveRelease());
      return;
    }
    if (url.pathname === "/api/bootstrap" && req.method === "GET") {
      sendJson(res, 200, {
        flagKey: "api-progressive-grid-highlight",
        targetingUrl: releases.targetingUrl(),
        schedule: releases.schedule(),
      });
      return;
    }
    if (req.method === "POST" && ["/api/release/start", "/api/release/stop", "/api/release/reset"].includes(url.pathname)) {
      const body =
        url.pathname === "/api/release/start"
          ? await releases.startProgressiveRelease()
          : url.pathname === "/api/release/stop"
            ? await releases.stopProgressiveRelease()
            : await releases.resetDemo();
      sendJson(res, resultStatus(body), body);
      return;
    }
    if (url.pathname === "/" || url.pathname === "/index.html") {
      fs.readFile(path.join(ROOT, "index.html"), (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end("Not found");
          return;
        }
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(data);
      });
      return;
    }
    res.writeHead(404);
    res.end("Not found");
  });
  server.listen(PORT, "127.0.0.1", () => {
    console.log(`Serving on http://127.0.0.1:${PORT}/`);
  });
}

const args = process.argv.slice(2);
if (args.length >= 2 && args[0] === "--evaluate-once") {
  initLaunchDarkly()
    .then(() => evaluateHighlight(ldClient, args[1]))
    .then((result) => {
      console.log(JSON.stringify(result));
      if (ldClient) ldClient.close();
    });
} else {
  runServer();
}

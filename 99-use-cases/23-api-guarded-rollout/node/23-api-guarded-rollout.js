#!/usr/bin/env node
/**
 * Serve the API guarded-rollout grid.
 *
 * This process evaluates the flag and sends the latency and movement events.
 * Start guarded release POSTs the environment release.
 *
 * LaunchDarkly: guarded rollout via environment releases
 * https://launchdarkly.com/docs/api/environment-releases
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { FLAG_HIGHLIGHT, evaluateHighlight } = require("./highlight-eval");
const { LATENCY_THRESHOLD_MS, metricViews, trackObserved } = require("./metrics");
const releases = require("./release-status");

const PORT = Number(process.env.PORT || 8785);
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

function readJson(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      if (!chunks.length) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch (_) {
        resolve({});
      }
    });
  });
}

async function trackLatency(username, latencyMs) {
  if (!ldClient) {
    return [503, { error: true, detail: "LD_SDK_KEY is missing or the SDK did not initialize." }];
  }
  const value = Number(latencyMs);
  if (!String(username || "").trim() || !(value >= 0 && value <= 500)) {
    return [400, { error: true, detail: "username and latencyMs (0–500) are required." }];
  }
  return [200, await trackObserved(ldClient, String(username).trim(), value)];
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
      sendJson(res, 200, await releases.latestGuardedRelease());
      return;
    }
    if (url.pathname === "/api/bootstrap" && req.method === "GET") {
      sendJson(res, 200, {
        flagKey: FLAG_HIGHLIGHT,
        targetingUrl: releases.targetingUrl(),
        schedule: releases.schedule(),
        thresholdMs: LATENCY_THRESHOLD_MS,
        metrics: metricViews(),
      });
      return;
    }
    if (url.pathname === "/api/track" && req.method === "POST") {
      const body = await readJson(req);
      const [status, result] = await trackLatency(body.username, body.latencyMs);
      sendJson(res, status, result);
      return;
    }
    if (req.method === "POST" && ["/api/release/start", "/api/release/stop", "/api/release/reset"].includes(url.pathname)) {
      const body = url.pathname === "/api/release/start"
        ? await releases.startGuardedRelease()
        : url.pathname === "/api/release/stop"
          ? await releases.stopGuardedRelease()
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

#!/usr/bin/env node
/** Serve the flag-enabled grid navigator web UI on a local HTTP server. */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const {
  FLAG_HIGHLIGHT,
  FLAG_CONTEXT,
  FLAG_COUNT,
  buildFlagResponse,
} = require("../highlight-style");
const { detectHostOs, HOST_OS_ATTR, FLAG_OS_EMOJI } = require("../host-os");

// LaunchDarkly capability: Boolean flag evaluation + private context attributes
// See: https://launchdarkly.com/docs/sdk/features/private-attributes

const PORT = 8080;
const ROOT = __dirname;
const HOST_OS = detectHostOs();

let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    console.warn("Warning: LD_SDK_KEY not set — flags default to off.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey, { privateAttributes: [HOST_OS_ATTR] });
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (err) {
    console.warn("Warning: LaunchDarkly SDK did not initialize — flags default to off.");
    ldClient = null;
  }
}

function buildContext(username) {
  return {
    kind: "user",
    key: username,
    hostOs: HOST_OS,
    privateAttributes: [HOST_OS_ATTR],
  };
}

async function evaluateFlags(username) {
  if (!ldClient) {
    return buildFlagResponse(username, false, false, false, false, HOST_OS);
  }
  const context = buildContext(username);
  const highlightEnabled = await ldClient.variation(FLAG_HIGHLIGHT, context, false);
  const contextHighlight = await ldClient.variation(FLAG_CONTEXT, context, false);
  const showMoveCount = await ldClient.variation(FLAG_COUNT, context, false);
  const showOsEmoji = await ldClient.variation(FLAG_OS_EMOJI, context, false);
  return buildFlagResponse(
    username,
    Boolean(highlightEnabled),
    Boolean(contextHighlight),
    Boolean(showMoveCount),
    Boolean(showOsEmoji),
    HOST_OS
  );
}

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (url.pathname === "/api/flags") {
    const username = (url.searchParams.get("username") || "").trim();
    if (!username) {
      sendJson(res, 400, { error: "username query parameter is required" });
      return;
    }
    sendJson(res, 200, await evaluateFlags(username));
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

initLaunchDarkly().then(() => {
  server.listen(PORT, "127.0.0.1", () => {
    console.log(`Grid navigator (flag enablement) running at http://127.0.0.1:${PORT}/`);
    console.log("Press Ctrl+C to stop.");
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

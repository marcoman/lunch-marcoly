#!/usr/bin/env node
/**
 * Serve the SDK-fallback lab through a real, controllable streaming proxy.
 *
 * LaunchDarkly: every refresh uses variationDetail(). The stream gate changes
 * data delivery, never application evaluation logic.
 * https://launchdarkly.com/docs/sdk/features/evaluating
 */
const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");

const PORT = Number(process.env.PORT || 8181);
const GATE_PORT = Number(process.env.LD_STREAM_GATE_PORT || 8182);
const START_WAIT = Number(process.env.LD_START_WAIT || 2);
const STREAM_ORIGIN = (process.env.LD_STREAM_ORIGIN || "https://stream.launchdarkly.com")
  .replace(/\/+$/, "");
const POLL_ORIGIN = (process.env.LD_POLL_ORIGIN || "https://sdk.launchdarkly.com")
  .replace(/\/+$/, "");
const INDEX = path.resolve(__dirname, "../python/index.html");
const FLAG_KEY = "enable-sdk-fallback-grid-highlight";
const FLAG_NAME = "Enable: SDK fallback grid highlight";
const CODE_DEFAULT = "none";
const LIVE_VALUE = "green";

let ldClient = null;
let mode = "starting";
let everInitialized = false;

class StreamGate {
  constructor() {
    this.allowed = true;
    this.active = new Set();
  }

  open() {
    this.allowed = true;
  }

  drop() {
    this.allowed = false;
    for (const stream of this.active) {
      stream.upstream.destroy();
      stream.downstream.destroy();
    }
    this.active.clear();
  }

  count() {
    return this.active.size;
  }
}

const gate = new StreamGate();

/**
 * Proxy the SDK's /all stream. Node supplies HTTP chunk framing automatically.
 * Authorization is forwarded but never logged.
 */
const gateServer = http.createServer((req, res) => {
  if (!gate.allowed) {
    res.writeHead(503, { "Content-Type": "text/plain", Connection: "close" });
    res.end("stream gate closed");
    return;
  }

  const origin = new URL(STREAM_ORIGIN);
  const transport = origin.protocol === "https:" ? https : http;
  const headers = {};
  for (const name of [
    "authorization",
    "accept",
    "user-agent",
    "x-launchdarkly-event-schema",
    "x-launchdarkly-wrapper",
  ]) {
    if (req.headers[name]) headers[name] = req.headers[name];
  }

  const upstream = transport.request({
    protocol: origin.protocol,
    hostname: origin.hostname,
    port: origin.port || undefined,
    method: "GET",
    path: `${origin.pathname.replace(/\/$/, "")}${req.url}`,
    headers,
  });
  const stream = { upstream, downstream: res };

  upstream.on("response", (response) => {
    if (!gate.allowed) {
      response.destroy();
      res.writeHead(503, { Connection: "close" });
      res.end();
      return;
    }
    if (response.statusCode >= 400) {
      res.writeHead(response.statusCode, { Connection: "close" });
      response.pipe(res);
      return;
    }

    gate.active.add(stream);
    res.writeHead(response.statusCode, {
      "Content-Type": response.headers["content-type"] || "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "close",
    });
    response.pipe(res);
    const cleanup = () => gate.active.delete(stream);
    response.on("close", cleanup);
    response.on("end", cleanup);
    res.on("close", () => {
      cleanup();
      response.destroy();
    });
  });
  upstream.on("error", () => {
    gate.active.delete(stream);
    if (!res.headersSent) res.writeHead(502, { Connection: "close" });
    res.end();
  });
  upstream.end();
});

function apiError(message, status = 500) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function configured() {
  return Boolean(String(process.env.LD_SDK_KEY || "").trim());
}

/**
 * Construct one server SDK client with a bounded initialization wait.
 * streamUri redirects transport only; SDK evaluation and storage stay native.
 */
async function makeClient() {
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) throw apiError("LD_SDK_KEY is required for this lab.", 503);
  const client = LaunchDarkly.init(sdkKey, {
    streamUri: `http://127.0.0.1:${GATE_PORT}`,
    baseUri: POLL_ORIGIN,
    sendEvents: false,
    diagnosticOptOut: true,
    streamInitialReconnectDelay: 0.5,
  });
  try {
    await client.waitForInitialization({ timeout: START_WAIT });
  } catch (_error) {
    // The uninitialized client is intentional in DEFAULT mode.
  }
  return client;
}

async function replaceClient(nextMode) {
  if (nextMode === "stream") gate.open();
  else if (nextMode === "default") gate.drop();
  else throw apiError(`Unknown mode: ${nextMode}`, 400);

  const previous = ldClient;
  ldClient = null;
  mode = nextMode;
  everInitialized = false;
  if (previous) await previous.close();
  const next = await makeClient();
  ldClient = next;
  everInitialized = next.initialized();
  return status();
}

function dropStream() {
  if (!ldClient || !ldClient.initialized()) {
    throw apiError("Connect and initialize the stream before dropping it.", 409);
  }
  everInitialized = true;
  mode = "last-known";
  gate.drop();
  return status();
}

function source() {
  if (mode === "last-known") return "LAST_KNOWN";
  if (mode === "stream" && ldClient?.initialized()) return "STREAM";
  return "DEFAULT";
}

function status() {
  const initialized = Boolean(ldClient?.initialized());
  if (initialized) everInitialized = true;
  return {
    mode,
    source: source(),
    initialized,
    everInitialized,
    gateOpen: gate.allowed,
    activeStreams: gate.count(),
    startWaitSeconds: START_WAIT,
    configured: configured(),
  };
}

/**
 * Evaluate in every mode with the same context, flag, and code default.
 */
async function evaluate(username) {
  if (!ldClient) {
    return {
      flagValue: CODE_DEFAULT,
      highlightColor: CODE_DEFAULT,
      reason: { kind: "ERROR", errorKind: "CLIENT_NOT_READY" },
      ...status(),
    };
  }
  const detail = await ldClient.variationDetail(
    FLAG_KEY,
    { kind: "user", key: username },
    CODE_DEFAULT
  );
  const value = [CODE_DEFAULT, LIVE_VALUE].includes(detail.value)
    ? detail.value
    : CODE_DEFAULT;
  return {
    flagValue: value,
    highlightColor: value,
    reason: detail.reason,
    ...status(),
  };
}

function sendJson(res, statusCode, body) {
  const payload = JSON.stringify(body);
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Cache-Control": "no-store",
  });
  res.end(payload);
}

async function handleApi(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/config") {
    sendJson(res, 200, {
      runtime: "18-sdk-fallbacks[node]",
      flag: { key: FLAG_KEY, name: FLAG_NAME },
      codeDefault: CODE_DEFAULT,
      ...status(),
    });
    return;
  }
  if (req.method === "GET" && url.pathname === "/api/status") {
    sendJson(res, 200, status());
    return;
  }
  if (req.method === "GET" && url.pathname === "/api/evaluate") {
    const username = (url.searchParams.get("username") || "").trim();
    if (!username) throw apiError("username query parameter is required", 400);
    sendJson(res, 200, await evaluate(username));
    return;
  }
  if (req.method === "POST" && url.pathname === "/api/connect") {
    sendJson(res, 200, await replaceClient("stream"));
    return;
  }
  if (req.method === "POST" && url.pathname === "/api/drop-stream") {
    sendJson(res, 200, dropStream());
    return;
  }
  if (req.method === "POST" && url.pathname === "/api/block-init") {
    sendJson(res, 200, await replaceClient("default"));
    return;
  }
  throw apiError("Not found", 404);
}

async function closeAll(appServer) {
  gate.drop();
  appServer?.close();
  gateServer.close();
  if (ldClient) {
    const closing = ldClient;
    ldClient = null;
    await closing.close();
  }
}

async function run() {
  await new Promise((resolve) => gateServer.listen(GATE_PORT, "127.0.0.1", resolve));
  if (configured()) {
    const initial = await replaceClient("stream");
    if (!initial.initialized) {
      console.warn("Warning: SDK did not initialize; use Connect stream to retry.");
    }
  } else {
    console.warn("Warning: LD_SDK_KEY is unset; evaluations use none.");
  }

  const appServer = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
    try {
      if (url.pathname.startsWith("/api/")) {
        await handleApi(req, res, url);
      } else if (url.pathname === "/" || url.pathname === "/index.html") {
        fs.readFile(INDEX, (error, data) => {
          if (error) {
            res.writeHead(404);
            res.end("Not found");
          } else {
            res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
            res.end(data);
          }
        });
      } else {
        res.writeHead(404);
        res.end("Not found");
      }
    } catch (error) {
      sendJson(res, error.status || 500, { error: String(error.message || error) });
    }
  });

  appServer.listen(PORT, "127.0.0.1", () => {
    console.log("18-sdk-fallbacks[node]");
    console.log(`Flag: ${FLAG_NAME} (${FLAG_KEY}); code default: ${CODE_DEFAULT}`);
    console.log(`Stream gate: http://127.0.0.1:${GATE_PORT} → ${STREAM_ORIGIN}`);
    console.log(`Open http://127.0.0.1:${PORT}/`);
  });

  let shuttingDown = false;
  const shutdown = async () => {
    if (shuttingDown) return;
    shuttingDown = true;
    await closeAll(appServer);
  };
  process.on("SIGINT", () => shutdown().then(() => process.exit(0)));
  process.on("SIGTERM", () => shutdown().then(() => process.exit(0)));
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});

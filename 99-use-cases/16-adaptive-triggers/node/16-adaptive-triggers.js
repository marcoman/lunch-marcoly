#!/usr/bin/env node
/**
 * Serve the adaptive-trigger grid and keep all privileged operations server-side.
 * LaunchDarkly: variation, numeric custom track, and REST targeting update.
 * https://launchdarkly.com/docs/home/flags/triggers
 * https://launchdarkly.com/docs/sdk/features/events
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const {
  FLAG_HIGHLIGHT,
  buildContext,
  evaluateHighlight,
} = require("../highlight-eval");

const PORT = Number(process.env.PORT || 8161);
const ROOT = __dirname;

const FLAG_NAME = "Enable: adaptive grid highlight";
const METRIC_KEY = "adaptive-grid-nav-latency-metric";
const EVENT_KEY = "adaptive-grid-nav-latency";
const THRESHOLD_MS = 200;
const LIVE_VALUE = "green";
const API_HOST = (process.env.LD_API_HOST || "https://app.launchdarkly.com").replace(/\/+$/, "");
const APP_HOST = (process.env.LD_APP_HOST || API_HOST).replace(/\/+$/, "");

let ldClient = null;
let cachedSdkEnvironmentKey = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    console.warn("Warning: LD_SDK_KEY is unset — evaluation stays at code fallback none.");
    return;
  }
  const client = LaunchDarkly.init(sdkKey);
  try {
    await client.waitForInitialization({ timeout: 10 });
    ldClient = client;
  } catch (err) {
    console.warn(`Warning: LaunchDarkly initialization failed: ${err.message || err}`);
    await client.close();
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
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      try {
        resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function apiConfig() {
  const missing = ["LD_API_ACCESS_TOKEN", "LD_PROJECT_KEY", "LD_ENVIRONMENT_KEY"]
    .filter((key) => !String(process.env[key] || "").trim());
  return {
    configured: missing.length === 0,
    missing,
    projectKey: process.env.LD_PROJECT_KEY || null,
    environmentKey: process.env.LD_ENVIRONMENT_KEY || null,
  };
}

/**
 * Dashboard deep links so flag analytics and the trigger stay one click away.
 * Adaptive triggers live on the flag Targeting tab; results appear on Monitoring.
 */
function dashboardLinks(projectKey, environmentKey) {
  if (!projectKey) return null;
  const envQuery = environmentKey
    ? `?env=${encodeURIComponent(environmentKey)}&selected-env=${encodeURIComponent(environmentKey)}`
    : "";
  const flagBase = `${APP_HOST}/projects/${encodeURIComponent(projectKey)}/flags/${FLAG_HIGHLIGHT}`;
  return {
    flagTargeting: `${flagBase}${envQuery}`,
    flagMonitoring: `${flagBase}/monitoring${envQuery}`,
    metric: `${APP_HOST}/projects/${encodeURIComponent(projectKey)}/metrics/${METRIC_KEY}`,
    environments: `${APP_HOST}/projects/${encodeURIComponent(projectKey)}/settings/environments`,
  };
}

async function ldApi(pathname, options = {}) {
  const config = apiConfig();
  if (!config.configured) {
    const err = new Error(`This control needs ${config.missing.join(", ")} on the Node host.`);
    err.status = 503;
    throw err;
  }
  const response = await fetch(`${API_HOST}/api/v2${pathname}`, {
    ...options,
    headers: {
      Authorization: process.env.LD_API_ACCESS_TOKEN,
      "LD-API-Version": "20240415",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(body.message || `LaunchDarkly API returned ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return body;
}

/**
 * Which environment does LD_SDK_KEY belong to? Metric events land in that
 * environment, and an adaptive trigger only sees its own environment. A
 * mismatch with LD_ENVIRONMENT_KEY silently prevents the trigger from firing.
 */
async function resolveSdkEnvironmentKey() {
  if (cachedSdkEnvironmentKey) return cachedSdkEnvironmentKey;
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  const config = apiConfig();
  if (!sdkKey || !config.configured) return null;
  const body = await ldApi(
    `/projects/${config.projectKey}/environments?limit=100`,
    { method: "GET" }
  );
  const match = (body.items || []).find((environment) => environment.apiKey === sdkKey);
  cachedSdkEnvironmentKey = match ? match.key : null;
  return cachedSdkEnvironmentKey;
}

/**
 * Most recent audit log entry for this flag, so the page can attribute a
 * default-rule change to the adaptive trigger rather than to a lab control.
 * https://launchdarkly.com/docs/api/audit-log/get-audit-log-entries
 */
async function fetchLastChange() {
  const config = apiConfig();
  const spec = `proj/${config.projectKey}:env/${config.environmentKey}:flag/${FLAG_HIGHLIGHT}`;
  const body = await ldApi(
    `/auditlog?spec=${encodeURIComponent(spec)}&limit=1`,
    { method: "GET" }
  );
  const entry = (body.items || [])[0];
  if (!entry) return null;
  const actor = entry.member?.email || entry.token?.name || null;
  return {
    date: entry.date || null,
    summary: String(entry.description || entry.titleVerb || "")
      .replace(/[*~`]/g, "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .join("; "),
    actor,
    byAutomation: !actor,
  };
}

async function getStatus() {
  const config = apiConfig();
  const links = dashboardLinks(config.projectKey, config.environmentKey);
  const sdk = { initialized: Boolean(ldClient), environmentKey: null, matchesRestEnvironment: null };

  if (!config.configured) {
    return { ...config, links, sdk, flag: null };
  }

  const flag = await ldApi(`/flags/${config.projectKey}/${FLAG_HIGHLIGHT}`, { method: "GET" });
  const targeting = flag.environments?.[config.environmentKey] || null;
  const fallthroughIndex = targeting?.fallthrough?.variation;

  let lastChange = null;
  try {
    sdk.environmentKey = await resolveSdkEnvironmentKey();
    if (sdk.environmentKey) {
      sdk.matchesRestEnvironment = sdk.environmentKey === config.environmentKey;
    }
    lastChange = await fetchLastChange();
  } catch (_err) {
    /* diagnostics are best effort — never block status */
  }

  return {
    ...config,
    links,
    sdk,
    lastChange,
    flag: {
      key: FLAG_HIGHLIGHT,
      name: flag.name || FLAG_NAME,
      on: targeting?.on ?? null,
      fallthrough: Number.isInteger(fallthroughIndex)
        ? flag.variations[fallthroughIndex]?.value
        : null,
    },
  };
}

/**
 * Start the risky/live behavior. The adaptive trigger later changes this same
 * default rule to the safe `none` variation; it does not invoke SDK fallback.
 */
async function startLive() {
  const config = apiConfig();
  const flag = await ldApi(`/flags/${config.projectKey}/${FLAG_HIGHLIGHT}`, { method: "GET" });
  const live = flag.variations.find((variation) => variation.value === LIVE_VALUE);
  if (!live) {
    const err = new Error(`Flag ${FLAG_HIGHLIGHT} has no ${LIVE_VALUE} variation.`);
    err.status = 409;
    throw err;
  }
  await ldApi(`/flags/${config.projectKey}/${FLAG_HIGHLIGHT}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json; domain-model=launchdarkly.semanticpatch",
    },
    body: JSON.stringify({
      environmentKey: config.environmentKey,
      comment: "16-adaptive-triggers: start live from lab control",
      instructions: [
        { kind: "turnFlagOn" },
        { kind: "updateFallthroughVariationOrRollout", variationId: live._id },
      ],
    }),
  });
  return getStatus();
}

/**
 * Return to the provisioned state: targeting off, off variation `none`.
 * Does not delete the adaptive trigger — that remains a dashboard step.
 */
async function stopLive() {
  const config = apiConfig();
  await ldApi(`/flags/${config.projectKey}/${FLAG_HIGHLIGHT}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json; domain-model=launchdarkly.semanticpatch",
    },
    body: JSON.stringify({
      environmentKey: config.environmentKey,
      comment: "16-adaptive-triggers: stop from lab control",
      instructions: [{ kind: "turnFlagOff" }],
    }),
  });
  return getStatus();
}

/**
 * Send the slider value as a numeric custom metric for the current user.
 * Numeric value is the fourth track argument; data identifies this lab.
 * These events — not flag evaluations — are what the adaptive trigger watches.
 */
async function trackLatency(username, latencyMs) {
  if (!ldClient) {
    const err = new Error("LD_SDK_KEY is missing or the SDK did not initialize.");
    err.status = 503;
    throw err;
  }
  const value = Number(latencyMs);
  if (!username || !Number.isFinite(value) || value < 0 || value > 500) {
    const err = new Error("username and latencyMs (0–500) are required.");
    err.status = 400;
    throw err;
  }
  ldClient.track(EVENT_KEY, buildContext(username), { source: "16-adaptive-triggers" }, value);
  await ldClient.flush();
  return {
    tracked: true,
    eventKey: EVENT_KEY,
    latencyMs: value,
    aboveThreshold: value > THRESHOLD_MS,
  };
}

async function handleApi(req, res, url) {
  if (url.pathname === "/api/config" && req.method === "GET") {
    const config = apiConfig();
    sendJson(res, 200, {
      controls: config,
      flag: { key: FLAG_HIGHLIGHT, name: FLAG_NAME },
      metricKey: METRIC_KEY,
      eventKey: EVENT_KEY,
      thresholdMs: THRESHOLD_MS,
      links: dashboardLinks(config.projectKey, config.environmentKey),
    });
    return true;
  }
  if (url.pathname === "/api/highlight" && req.method === "GET") {
    const username = (url.searchParams.get("username") || "").trim();
    if (!username) {
      sendJson(res, 400, { error: "username query parameter is required" });
      return true;
    }
    sendJson(res, 200, await evaluateHighlight(ldClient, username));
    return true;
  }
  if (url.pathname === "/api/status" && req.method === "GET") {
    sendJson(res, 200, await getStatus());
    return true;
  }
  if (url.pathname === "/api/start-live" && req.method === "POST") {
    sendJson(res, 200, await startLive());
    return true;
  }
  if (url.pathname === "/api/stop" && req.method === "POST") {
    sendJson(res, 200, await stopLive());
    return true;
  }
  if (url.pathname === "/api/track-latency" && req.method === "POST") {
    const body = await readJson(req);
    sendJson(res, 200, await trackLatency(String(body.username || "").trim(), body.latencyMs));
    return true;
  }
  return false;
}

async function runServer() {
  await initLaunchDarkly();
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
    if (url.pathname.startsWith("/api/")) {
      try {
        if (!(await handleApi(req, res, url))) {
          sendJson(res, 404, { error: "Not found" });
        }
      } catch (err) {
        sendJson(res, err.status || 500, { error: String(err.message || err) });
      }
      return;
    }

    const urlPath = url.pathname === "/" ? "/index.html" : url.pathname;
    const filePath = path.resolve(ROOT, `.${urlPath}`);
    if (!filePath.startsWith(`${ROOT}${path.sep}`)) {
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
      res.writeHead(200, {
        "Content-Type": path.extname(filePath) === ".html"
          ? "text/html; charset=utf-8"
          : "text/plain; charset=utf-8",
      });
      res.end(data);
    });
  });

  server.listen(PORT, "127.0.0.1", () => {
    console.log("16-adaptive-triggers[node]");
    console.log(`Flag: ${FLAG_NAME} (${FLAG_HIGHLIGHT})`);
    console.log(`Metric event key: ${EVENT_KEY} — threshold ${THRESHOLD_MS} ms`);
    console.log(`Open http://127.0.0.1:${PORT}/`);
  });
}

const args = process.argv.slice(2);
if (args.length >= 2 && args[0] === "--evaluate-once") {
  (async () => {
    await initLaunchDarkly();
    try {
      console.log(JSON.stringify(await evaluateHighlight(ldClient, args[1])));
    } finally {
      if (ldClient) await ldClient.close();
    }
  })().catch((err) => {
    console.error(err);
    process.exitCode = 1;
  });
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

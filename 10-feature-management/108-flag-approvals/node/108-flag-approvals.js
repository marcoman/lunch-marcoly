#!/usr/bin/env node
/** Serve the approval lab for the move-count flag.
 *
 * Approvals
 * https://launchdarkly.com/docs/home/releases/approvals
 */

const fs = require("fs");
const http = require("http");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { FLAG_KEY, apiConfig, approvalState, requestApproval, applyApproval, resetDemo } = require("./approvals");

const PORT = Number(process.env.PORT || 8181);
const ROOT = __dirname;
let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = (process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    console.warn("Warning: LD_SDK_KEY not set — the count stays hidden.");
    return;
  }
  // LaunchDarkly: server-side Node SDK · boolean variation
  // https://launchdarkly.com/docs/sdk/server-side/node-js
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch {
    console.warn("Warning: LaunchDarkly SDK did not initialize.");
    ldClient.close();
    ldClient = null;
  }
}

async function evaluateCount(username) {
  const name = String(username || "").trim();
  if (!name) throw new Error("Username is required");
  if (!ldClient) {
    return { username: name, flagKey: FLAG_KEY, showMoveCount: false, reason: "DEFAULT", sdk: false };
  }
  const context = { kind: "user", key: name, name };
  // LaunchDarkly: boolean variation · evaluation reasons
  // https://launchdarkly.com/docs/home/flags/boolean
  const detail = await ldClient.variationDetail(FLAG_KEY, context, false);
  return {
    username: name,
    flagKey: FLAG_KEY,
    showMoveCount: Boolean(detail.value),
    reason: detail.reason && detail.reason.kind ? detail.reason.kind : "UNKNOWN",
    sdk: true,
  };
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
  try {
    if (req.method === "GET" && url.pathname === "/api/flags") {
      return sendJson(res, 200, await evaluateCount(url.searchParams.get("username")));
    }
    if (req.method === "GET" && url.pathname === "/api/approval") {
      return sendJson(res, 200, await approvalState());
    }
    if (req.method === "POST" && url.pathname === "/api/approval") {
      await readJson(req);
      return sendJson(res, 200, await requestApproval());
    }
    if (req.method === "POST" && url.pathname === "/api/approval/apply") {
      const body = await readJson(req);
      return sendJson(res, 200, await applyApproval(body.id));
    }
    if (req.method === "POST" && url.pathname === "/api/approval/reset") {
      await readJson(req);
      return sendJson(res, 200, await resetDemo());
    }
  } catch (error) {
    const status = /Username is required|Approval id is required|Request body/.test(error.message) ? 400 : 502;
    const payload = { ok: false, error: error.message, request: null };
    if (error.steps) payload.steps = error.steps;
    if (url.pathname === "/api/approval" && req.method === "GET") Object.assign(payload, apiConfig());
    return sendJson(res, status, payload);
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
    res.writeHead(200, { "Content-Type": filePath.endsWith(".html") ? "text/html; charset=utf-8" : "text/plain" });
    res.end(data);
  });
});

initLaunchDarkly().then(() => {
  server.listen(PORT, "127.0.0.1", () => {
    console.log("108-flag-approvals[node]");
    console.log(`Open http://127.0.0.1:${PORT}/`);
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

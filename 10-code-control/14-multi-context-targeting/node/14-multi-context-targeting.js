#!/usr/bin/env node
/** Serve the multi-context grid navigator and LaunchDarkly lab. */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluatePartner, normalizeOrg, normalizeUsername } = require("../partner");
const { api_config, listFlagControls, applyFlagControl } = require("../ld-flag-controls");

// LaunchDarkly: evaluate show-partner-org-badge with a user+organization multi-context.
// https://launchdarkly.com/docs/home/flags/multi-contexts
const PORT = Number(process.env.PORT || 8080);
const ROOT = __dirname;
let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = (process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    console.warn("Warning: LD_SDK_KEY not set — partner badge stays false.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch {
    console.warn("Warning: LaunchDarkly SDK did not initialize — partner badge stays false.");
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
      const org = normalizeOrg(url.searchParams.get("org"));
      return sendJson(res, 200, await evaluatePartner(ldClient, username, org));
    } catch (error) {
      return sendJson(res, 400, { error: error.message });
    }
  }
  if (req.method === "GET" && url.pathname === "/api/bootstrap") {
    return sendJson(res, 200, {
      appBanner: "14-multi-context-targeting[node]",
      controls: api_config(),
    });
  }
  if (req.method === "GET" && url.pathname === "/api/flag-controls") {
    try {
      return sendJson(res, 200, await listFlagControls());
    } catch (error) {
      return sendJson(res, 502, { configured: true, flags: [], error: error.message });
    }
  }
  if (req.method === "POST" && url.pathname === "/api/flag-controls") {
    try {
      const body = await readJson(req);
      const key = String(body.key || "").trim();
      if (!key) throw new Error('"key" is required');
      const options = {};
      if (Object.prototype.hasOwnProperty.call(body, "on")) {
        if (typeof body.on !== "boolean") throw new Error('"on" must be a boolean');
        options.on = body.on;
      }
      if (Object.prototype.hasOwnProperty.call(body, "fallthrough")) {
        options.fallthrough = body.fallthrough;
      }
      return sendJson(res, 200, await applyFlagControl(key, options));
    } catch (error) {
      const status = /required|must be|not allowed|Provide|No variation/.test(error.message) ? 400 : 502;
      return sendJson(res, status, { ok: false, error: error.message });
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
    res.writeHead(200, { "Content-Type": filePath.endsWith(".html") ? "text/html" : "text/plain" });
    res.end(data);
  });
});

initLaunchDarkly().then(() => {
  server.listen(PORT, "127.0.0.1", () => {
    console.log("14-multi-context-targeting[node]");
    console.log(`Open http://127.0.0.1:${PORT}/`);
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

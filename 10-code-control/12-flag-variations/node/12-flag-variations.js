#!/usr/bin/env node
/** Serve the flag-variations grid navigator web UI on a local HTTP server. */

const http = require("http");
const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { evaluateFlags } = require("../flag-variations");
const { detectHostOs, HOST_OS_ATTR } = require("../host-os");
const {
  api_config,
  listFlagControls,
  applyFlagControl,
} = require("../ld-flag-controls");

// LaunchDarkly capability: Multivariate flag evaluation + anonymous contexts
// See: https://launchdarkly.com/docs/sdk/features/flag-types
// See: https://launchdarkly.com/docs/sdk/features/anonymous

const PORT = Number(process.env.PORT || 8080);
const ROOT = __dirname;
const HOST_OS = detectHostOs();

let ldClient = null;

async function initLaunchDarkly() {
  const sdkKey = process.env.LD_SDK_KEY;
  if (!sdkKey) {
    console.warn("Warning: LD_SDK_KEY not set — flags use defaults.");
    return;
  }
  ldClient = LaunchDarkly.init(sdkKey, { privateAttributes: [HOST_OS_ATTR] });
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (err) {
    console.warn("Warning: LaunchDarkly SDK did not initialize — flags use defaults.");
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
        const parsed = JSON.parse(raw || "{}");
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
          throw new Error("Request body must be a JSON object");
        }
        resolve(parsed);
      } catch (error) {
        reject(
          error instanceof SyntaxError
            ? new Error("Request body must be JSON")
            : error
        );
      }
    });
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (req.method === "GET" && url.pathname === "/api/flags") {
    const username = (url.searchParams.get("username") || "").trim();
    if (!username) {
      sendJson(res, 400, { error: "username query parameter is required" });
      return;
    }
    sendJson(res, 200, await evaluateFlags(ldClient, username, HOST_OS));
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/flag-controls") {
    sendJson(res, 200, await listFlagControls());
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/bootstrap") {
    sendJson(res, 200, {
      appBanner: "12-flag-variations[node]",
      hostOs: HOST_OS,
      controls: api_config(),
    });
    return;
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
      sendJson(res, 200, await applyFlagControl(key, options));
    } catch (error) {
      const status = /required|must be|not allowed|Provide|No variation/.test(error.message)
        ? 400
        : 502;
      sendJson(res, status, { ok: false, error: error.message || String(error) });
    }
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
    console.log(`Grid navigator (flag variations) running at http://127.0.0.1:${PORT}/`);
    console.log("Press Ctrl+C to stop.");
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

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
  interpretHighlightVariation,
  parseCohorts,
} = require("../highlight-style");
const { detectHostOs, HOST_OS_ATTR, FLAG_OS_EMOJI } = require("../host-os");
const { api_config, listFlagControls, applyFlagControl } = require("../ld-flag-controls");

// LaunchDarkly capability: Boolean flag evaluation + private context attributes
// See: https://launchdarkly.com/docs/sdk/features/private-attributes

const PORT = Number(process.env.PORT || 8080);
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

function withLdContext(response, username) {
  // LaunchDarkly: contexts — key + private hostOs, shown in the lab drawer.
  // https://launchdarkly.com/docs/home/flags/contexts
  const { isHuman, isRobot, isBeta } = parseCohorts(username);
  response.ldContext = {
    kind: "user",
    key: username,
    attributes: { [HOST_OS_ATTR]: HOST_OS },
    privateAttributes: [HOST_OS_ATTR],
    appDerived: {
      cohortWords: { human: isHuman, robot: isRobot, beta: isBeta },
      note:
        "Cohort words are parsed in app code from the username for the " +
        "context-highlight flag — they are not separate LD context attributes.",
    },
    note:
      `${HOST_OS_ATTR} is a private attribute: used for targeting, ` +
      "redacted from analytics events sent to LaunchDarkly.",
  };
  return response;
}

async function evaluateFlags(username) {
  if (!ldClient) {
    return withLdContext(
      buildFlagResponse(username, false, false, false, false, HOST_OS),
      username
    );
  }
  const context = buildContext(username);
  const highlightRaw = await ldClient.variation(FLAG_HIGHLIGHT, context, "none");
  const { enabled: highlightEnabled, servedColor } =
    interpretHighlightVariation(highlightRaw);
  const contextHighlight = await ldClient.variation(FLAG_CONTEXT, context, false);
  const showMoveCount = await ldClient.variation(FLAG_COUNT, context, false);
  const showOsEmoji = await ldClient.variation(FLAG_OS_EMOJI, context, false);
  return withLdContext(
    buildFlagResponse(
      username,
      highlightEnabled,
      Boolean(contextHighlight),
      Boolean(showMoveCount),
      Boolean(showOsEmoji),
      HOST_OS,
      servedColor
    ),
    username
  );
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
          error instanceof SyntaxError ? new Error("Request body must be JSON") : error
        );
      }
    });
    req.on("error", reject);
  });
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

  if (req.method === "GET" && url.pathname === "/api/flags") {
    const username = (url.searchParams.get("username") || "").trim();
    if (!username) {
      sendJson(res, 400, { error: "username query parameter is required" });
      return;
    }
    sendJson(res, 200, await evaluateFlags(username));
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/bootstrap") {
    sendJson(res, 200, {
      appBanner: "101-flag-enablement[node]",
      hostOs: HOST_OS,
      controls: api_config(),
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/flag-controls") {
    try {
      sendJson(res, 200, await listFlagControls());
    } catch (error) {
      sendJson(res, 502, { configured: true, flags: [], error: error.message });
    }
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
      const status = /required|must be|not allowed|Provide|No variation|JSON/.test(
        error.message
      )
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
    console.log(`Grid navigator (flag enablement) running at http://127.0.0.1:${PORT}/`);
    console.log("Press Ctrl+C to stop.");
  });
});

process.on("SIGINT", () => {
  if (ldClient) ldClient.close();
  process.exit(0);
});

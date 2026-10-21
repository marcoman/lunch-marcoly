#!/usr/bin/env node
/**
 * 26-flags-vs-agent-control.js — HTTP adapter for the three briefing sources.
 *
 * GET  /              → index.html
 * GET  /api/bootstrap → personas, tickers, cached stories
 * GET  /api/stories   → headlines for two tickers
 * POST /api/generate  → SSE. Body field source: original | flags | json
 *
 * LaunchDarkly work lives in agentCore.js.
 */

"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const {
  configKey,
  demoPersonas,
  generateStream,
  initLaunchDarkly,
  judgeKey,
  personaById,
} = require("./agentCore");
const {
  DEFAULT_TICKER_1,
  DEFAULT_TICKER_2,
  fetchStoriesForTickers,
  getLastPairCached,
} = require("./yahooNews");

const APP_BANNER = "26-flags-vs-agent-control[node]";
const PORT = Number(process.env.PORT || 8261);
const ROOT = __dirname;

function sendJson(res, status, body) {
  const raw = Buffer.from(JSON.stringify(body), "utf8");
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": raw.length,
    "Cache-Control": "no-store",
  });
  res.end(raw);
}

function sendFile(res, filePath, contentType) {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }
  const data = fs.readFileSync(filePath);
  res.writeHead(200, {
    "Content-Type": contentType,
    "Content-Length": data.length,
    "Cache-Control": "no-store",
  });
  res.end(data);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

async function handleGenerate(req, res) {
  let payload = {};
  try {
    const raw = await readBody(req);
    payload = JSON.parse(raw || "{}");
  } catch {
    sendJson(res, 400, { error: "Invalid JSON body." });
    return;
  }

  const demo = demoPersonas();
  const personaId = String(payload.personaId || demo[0].id);
  const persona = personaById(personaId) || demo[0];
  const stories = Array.isArray(payload.stories) ? payload.stories : [];
  let source = String(payload.source || "original");
  if (!["original", "flags", "json"].includes(source)) source = "original";

  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-store",
    Connection: "close",
  });
  try {
    for await (const event of generateStream(persona, stories, source)) {
      res.write(`data: ${JSON.stringify(event)}\n\n`);
    }
  } catch (exc) {
    if (!res.writableEnded) {
      res.write(
        `data: ${JSON.stringify({ type: "error", message: String(exc.message || exc) })}\n\n`
      );
    }
  } finally {
    if (!res.writableEnded) res.end();
  }
}

function bootstrapBody() {
  const cached = getLastPairCached();
  return {
    appBanner: APP_BANNER,
    personas: demoPersonas().map((p) => ({
      id: p.id,
      name: p.name,
      profile: p.profile,
      anonymous: false,
    })),
    defaultTickers: {
      ticker1: (cached && cached.ticker1) || DEFAULT_TICKER_1,
      ticker2: (cached && cached.ticker2) || DEFAULT_TICKER_2,
    },
    cachedStories: cached,
    mode: "launchdarkly",
    provider: "AgentControl",
    model: `config:${configKey()}`,
    configKey: configKey(),
    judgeKey: judgeKey(),
    source: "original",
    sources: [
      { id: "original", label: "AgentControl", enabled: true },
      { id: "flags", label: "Separate flags", enabled: true },
      { id: "json", label: "JSON flag", enabled: true },
    ],
  };
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://127.0.0.1:${PORT}`);
  try {
    if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) {
      sendFile(res, path.join(ROOT, "index.html"), "text/html; charset=utf-8");
      return;
    }
    if (req.method === "GET" && url.pathname === "/api/bootstrap") {
      sendJson(res, 200, bootstrapBody());
      return;
    }
    if (req.method === "GET" && url.pathname === "/api/stories") {
      const ticker1 = url.searchParams.get("ticker1") || DEFAULT_TICKER_1;
      const ticker2 = url.searchParams.get("ticker2") || DEFAULT_TICKER_2;
      sendJson(res, 200, await fetchStoriesForTickers(ticker1, ticker2, 2));
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/generate") {
      await handleGenerate(req, res);
      return;
    }
    res.writeHead(404);
    res.end("Not found");
  } catch (exc) {
    if (!res.headersSent) sendJson(res, 500, { error: String(exc.message || exc) });
    else res.end();
  }
});

initLaunchDarkly()
  .then(() => {
    server.listen(PORT, "127.0.0.1", () => {
      console.log(APP_BANNER);
      console.log(`Open http://127.0.0.1:${PORT}/`);
      console.log(`LD_AGENT_CONFIG_KEY=${configKey()}`);
      console.log(`LD_JUDGE_KEY=${judgeKey()}`);
      console.log("Press Ctrl+C to stop.");
    });
  })
  .catch((exc) => {
    console.error(exc.message || exc);
    process.exit(1);
  });

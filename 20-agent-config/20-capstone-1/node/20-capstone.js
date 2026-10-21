#!/usr/bin/env node
/**
 * 20-capstone Node web.
 *
 * GET  /              → index.html
 * GET  /api/bootstrap → personas, tools, graph keys
 * GET  /api/stories   → headlines
 * POST /api/generate  → SSE
 * POST /api/feedback  → thumbs on the specialist draft
 *
 * LaunchDarkly work lives in agentCore.js.
 */

"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const {
  PERSONAS,
  TOOL_ORDER,
  generateStream,
  graphKey,
  initLaunchDarkly,
  judgeKey,
  nodeKey,
  personaById,
  submitFeedback,
} = require("./agentCore");
const {
  DEFAULT_TICKER_1,
  DEFAULT_TICKER_2,
  fetchStoriesForTickers,
  getLastPairCached,
} = require("./yahooNews");

const APP_BANNER = "20-capstone[node]";
const PORT = Number(process.env.PORT || 8291);
const ROOT = __dirname;
const ROLES = ["assess", "report", "questions", "good", "finalize"];

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
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

async function handleGenerate(req, res) {
  let payload = {};
  try {
    payload = JSON.parse((await readBody(req)) || "{}");
  } catch {
    sendJson(res, 400, { error: "Invalid JSON body." });
    return;
  }
  const persona = personaById(String(payload.personaId || "")) || PERSONAS[1];
  const action = String(payload.action || "report");
  const locale = payload.locale === "es" ? "es" : "en";
  const tools = Array.isArray(payload.tools) ? payload.tools.map(String) : [];
  const stories = Array.isArray(payload.stories) ? payload.stories : [];
  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-store",
    Connection: "close",
  });
  try {
    for await (const event of generateStream(persona, action, stories, tools, locale)) {
      res.write(`data: ${JSON.stringify(event)}\n\n`);
    }
  } catch (exc) {
    res.write(`data: ${JSON.stringify({ type: "error", message: String(exc.message || exc) })}\n\n`);
  }
  res.end();
}

async function handleFeedback(req, res) {
  let payload = {};
  try {
    payload = JSON.parse((await readBody(req)) || "{}");
  } catch {
    sendJson(res, 400, { error: "Invalid JSON body." });
    return;
  }
  const persona = personaById(String(payload.personaId || "")) || PERSONAS[1];
  try {
    const body = await submitFeedback({
      persona,
      locale: payload.locale === "es" ? "es" : "en",
      resumptionToken: payload.resumptionToken,
      kind: payload.kind,
    });
    sendJson(res, 200, body);
  } catch (exc) {
    sendJson(res, 400, { ok: false, error: String(exc.message || exc) });
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
  try {
    if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) {
      sendFile(res, path.join(ROOT, "index.html"), "text/html; charset=utf-8");
      return;
    }
    if (req.method === "GET" && url.pathname === "/api/bootstrap") {
      const cached = getLastPairCached();
      sendJson(res, 200, {
        appBanner: APP_BANNER,
        personas: PERSONAS,
        tools: TOOL_ORDER,
        actions: [
          { id: "report", labelKey: "actionReport" },
          { id: "questions", labelKey: "actionQuestions" },
          { id: "good", labelKey: "actionGood" },
        ],
        graphKey: graphKey(),
        nodeKeys: Object.fromEntries(ROLES.map((role) => [role, nodeKey(role)])),
        judgeKeys: [judgeKey("fidelity"), judgeKey("discipline")],
        defaultTickers: {
          ticker1: (cached && cached.ticker1) || DEFAULT_TICKER_1,
          ticker2: (cached && cached.ticker2) || DEFAULT_TICKER_2,
        },
        persistedStories: cached
          ? {
              ticker1: cached.ticker1,
              ticker2: cached.ticker2,
              tickers: cached.tickers,
              savedAt: cached.updated_at,
              directory: "20-agent-config/stories",
            }
          : null,
      });
      return;
    }
    if (req.method === "GET" && url.pathname === "/api/stories") {
      const body = await fetchStoriesForTickers(
        url.searchParams.get("ticker1") || DEFAULT_TICKER_1,
        url.searchParams.get("ticker2") || DEFAULT_TICKER_2,
        2
      );
      sendJson(res, 200, body);
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/generate") {
      await handleGenerate(req, res);
      return;
    }
    if (req.method === "POST" && url.pathname === "/api/feedback") {
      await handleFeedback(req, res);
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
      console.log(`LD_GRAPH_KEY=${graphKey()}`);
    });
  })
  .catch((exc) => {
    console.error(exc.message || exc);
    process.exit(1);
  });

#!/usr/bin/env node
/**
 * 01-reference-agent.js — thin HTTP adapter for the reference agent UI.
 *
 * Request map
 * -----------
 *   GET /                 → index.html
 *   GET /api/bootstrap    → personas, default tickers, cached stories, provider/model
 *   GET /api/stories      → latest 2 headlines for ticker1 + ticker2
 *   POST /api/generate    → text/event-stream of generation events
 */

"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const {
  PERSONAS,
  generateStream,
  modelLabel,
  personaById,
  providerLabel,
  resolveMode,
} = require("./agentCore");
const {
  DEFAULT_TICKER_1,
  DEFAULT_TICKER_2,
  fetchStoriesForTickers,
  getLastPairCached,
} = require("./yahooNews");

const APP_BANNER = "01-reference-agent[node]";
const PORT = Number(process.env.PORT || 8090);
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

  const personaId = String(payload.personaId || PERSONAS[0].id);
  const persona = personaById(personaId) || PERSONAS[0];
  let stories = payload.stories;
  if (!Array.isArray(stories)) stories = [];

  res.writeHead(200, {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-store",
    Connection: "close",
  });

  try {
    for await (const event of generateStream(persona, stories)) {
      res.write(`data: ${JSON.stringify(event)}\n\n`);
    }
  } catch (exc) {
    if (exc.code !== "EPIPE" && exc.code !== "ECONNRESET") {
      console.error(exc);
    }
  }
  res.end();
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
  const pathname = url.pathname;

  try {
    if (req.method === "GET" && (pathname === "/" || pathname === "/index.html")) {
      sendFile(res, path.join(ROOT, "index.html"), "text/html; charset=utf-8");
      return;
    }

    if (req.method === "GET" && pathname === "/api/bootstrap") {
      const mode = resolveMode();
      const cached = getLastPairCached();
      sendJson(res, 200, {
        appBanner: APP_BANNER,
        personas: PERSONAS.map((p) => ({
          id: p.id,
          name: p.name,
          profile: p.profile,
        })),
        defaultTickers: {
          ticker1: (cached && cached.ticker1) || DEFAULT_TICKER_1,
          ticker2: (cached && cached.ticker2) || DEFAULT_TICKER_2,
        },
        cachedStories: cached,
        mode,
        provider: providerLabel(mode),
        model: modelLabel(mode),
      });
      return;
    }

    if (req.method === "GET" && pathname === "/api/stories") {
      const ticker1 = url.searchParams.get("ticker1") || DEFAULT_TICKER_1;
      const ticker2 = url.searchParams.get("ticker2") || DEFAULT_TICKER_2;
      const body = await fetchStoriesForTickers(ticker1, ticker2, 2);
      sendJson(res, 200, body);
      return;
    }

    if (req.method === "POST" && pathname === "/api/generate") {
      await handleGenerate(req, res);
      return;
    }

    res.writeHead(404);
    res.end("Not found");
  } catch (exc) {
    console.error(exc);
    if (!res.headersSent) {
      sendJson(res, 500, { error: String(exc.message || exc) });
    } else {
      res.end();
    }
  }
});

server.listen(PORT, "127.0.0.1", () => {
  const mode = resolveMode();
  console.log(APP_BANNER);
  console.log(`Open http://127.0.0.1:${PORT}/`);
  console.log(`AGENT_LLM_MODE=${mode} model=${modelLabel(mode)}`);
  console.log("Press Ctrl+C to stop.");
});

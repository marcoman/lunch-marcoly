/**
 * yahooNews.js — fetch recent Yahoo Finance news titles for tickers.
 *
 * Uses Yahoo's unofficial public search JSON endpoints (no API key).
 * Successful fetches are written to the shared example cache:
 *   ../stories/stories_cache.json
 */

"use strict";

const fs = require("fs");
const path = require("path");

const EXAMPLE_ROOT = path.resolve(__dirname, "..");
const STORIES_DIR = path.join(EXAMPLE_ROOT, "stories");
const CACHE_PATH = path.join(STORIES_DIR, "stories_cache.json");

const YAHOO_SEARCH_HOSTS = [
  "https://query1.finance.yahoo.com/v1/finance/search",
  "https://query2.finance.yahoo.com/v1/finance/search",
];

// Space Yahoo calls; stop walking hosts/variants on HTTP 429.
const REQUEST_GAP_MS = 1000;

const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

const DEFAULT_TICKER_1 = "NVDA";
const DEFAULT_TICKER_2 = "SPCX";

function normalizeTicker(raw) {
  return String(raw || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9.\-]/g, "");
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function unixToIso(value) {
  const ts = Number(value);
  if (!Number.isFinite(ts) || ts <= 0) return "";
  try {
    return new Date(ts * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
  } catch (_) {
    return "";
  }
}

function formatPublishedDisplay(published) {
  const text = String(published || "").trim();
  if (!text) return "";
  const dt = new Date(text);
  if (Number.isNaN(dt.getTime())) return text;
  return dt.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatStorySource(story) {
  if (!story) return "";
  const publisher = String(story.publisher || "").trim();
  const when = formatPublishedDisplay(story.published);
  if (publisher && when) return `${publisher} · ${when}`;
  return publisher || when;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function loadCache() {
  if (!fs.existsSync(CACHE_PATH)) {
    return { updated_at: null, tickers: {}, last_pair: null };
  }
  try {
    const data = JSON.parse(fs.readFileSync(CACHE_PATH, "utf8"));
    if (!data || typeof data !== "object") {
      return { updated_at: null, tickers: {}, last_pair: null };
    }
    data.tickers = data.tickers || {};
    data.last_pair = data.last_pair ?? null;
    data.updated_at = data.updated_at ?? null;
    return data;
  } catch {
    return { updated_at: null, tickers: {}, last_pair: null };
  }
}

function saveCache(cache) {
  const next = { ...cache, updated_at: nowIso() };
  fs.mkdirSync(STORIES_DIR, { recursive: true });
  fs.writeFileSync(CACHE_PATH, `${JSON.stringify(next, null, 2)}\n`, "utf8");
}

function getCachedTicker(ticker) {
  const symbol = normalizeTicker(ticker);
  if (!symbol) return null;
  const entry = (loadCache().tickers || {})[symbol];
  if (!entry || !(entry.stories || []).length) return null;
  return {
    ticker: symbol,
    name: entry.name || symbol,
    stories: (entry.stories || []).slice(0, 2),
    error: null,
    from_cache: true,
    cached_at: entry.cached_at,
  };
}

function getLastPairCached() {
  const cache = loadCache();
  const pair = cache.last_pair;
  if (!pair || typeof pair !== "object") return null;
  const t1 = normalizeTicker(String(pair.ticker1 || ""));
  const t2 = normalizeTicker(String(pair.ticker2 || ""));
  if (!t1 || !t2) return null;
  const blocks = [];
  for (const symbol of [t1, t2]) {
    const cached = getCachedTicker(symbol);
    if (!cached) return null;
    blocks.push(cached);
  }
  return {
    ticker1: t1,
    ticker2: t2,
    tickers: blocks,
    updated_at: cache.updated_at,
    from_cache: true,
  };
}

function rememberTicker(symbol, name, stories) {
  if (!stories || !stories.length) return;
  const cache = loadCache();
  const tickers = { ...(cache.tickers || {}) };
  tickers[symbol] = {
    name: name || symbol,
    stories: stories.slice(0, 2),
    cached_at: nowIso(),
  };
  cache.tickers = tickers;
  saveCache(cache);
}

function rememberPair(ticker1, ticker2, results) {
  if (!Array.isArray(results) || results.length !== 2) return;
  if (!results.every((r) => (r.stories || []).length)) return;
  const cache = loadCache();
  cache.last_pair = {
    ticker1: normalizeTicker(ticker1),
    ticker2: normalizeTicker(ticker2),
  };
  for (const block of results) {
    const stories = block.stories || [];
    if (stories.length && !block.from_cache) {
      const symbol = normalizeTicker(String(block.ticker || ""));
      if (symbol) {
        const tickers = { ...(cache.tickers || {}) };
        tickers[symbol] = {
          name: block.name || symbol,
          stories: stories.slice(0, 2),
          cached_at: nowIso(),
        };
        cache.tickers = tickers;
      }
    }
  }
  saveCache(cache);
}

async function yahooGetJson(url) {
  let lastErr = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await sleep(REQUEST_GAP_MS);
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: {
          "User-Agent": USER_AGENT,
          Accept: "application/json",
          "Accept-Language": "en-US,en;q=0.9",
        },
        signal: AbortSignal.timeout(20000),
      });
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`);
        err.status = res.status;
        // Rate-limited: do not retry — caller falls back to cache.
        if (res.status === 429) {
          throw err;
        }
        if (res.status === 503 && attempt < 2) {
          lastErr = err;
          await sleep(1500 * (attempt + 1));
          continue;
        }
        throw err;
      }
      return await res.json();
    } catch (exc) {
      lastErr = exc;
      if (exc.status === 429) {
        throw exc;
      }
      if (attempt < 2 && (exc.name === "TimeoutError" || exc.name === "AbortError")) {
        await sleep(1000);
        continue;
      }
      if (attempt < 2 && exc.status === 503) {
        await sleep(1500 * (attempt + 1));
        continue;
      }
      throw exc;
    }
  }
  throw lastErr || new Error("Yahoo request failed");
}

function parseSearchPayload(symbol, payload, count) {
  const quotes = payload.quotes || [];
  let name = "";
  if (quotes.length) {
    const q0 = quotes[0] || {};
    name = String(q0.shortname || q0.longname || "").trim();
  }
  const stories = [];
  for (const item of (payload.news || []).slice(0, count)) {
    const title = String(item.title || "").trim();
    if (!title) continue;
    stories.push({
      title,
      publisher: String(item.publisher || "").trim(),
      published: unixToIso(item.providerPublishTime),
      link: String(item.link || "").trim(),
      uuid: String(item.uuid || "").trim(),
    });
  }
  if (!stories.length) return null;
  return {
    ticker: symbol,
    name: name || symbol,
    stories,
    error: null,
    from_cache: false,
  };
}

async function fetchStoriesForTicker(ticker, count = 2) {
  const symbol = normalizeTicker(ticker);
  if (!symbol) {
    return {
      ticker: "",
      name: "",
      stories: [],
      error: "Ticker is empty.",
      from_cache: false,
    };
  }

  const queryVariants = [
    {
      q: symbol,
      quotesCount: "1",
      newsCount: String(Math.max(1, count)),
      enableFuzzyQuery: "false",
      newsQueryId: "news_cie_vespa",
      lang: "en-US",
      region: "US",
    },
    {
      q: symbol,
      quotesCount: "1",
      newsCount: String(Math.max(1, count)),
      lang: "en-US",
      region: "US",
    },
  ];

  let lastError = `No recent stories found for ${symbol}.`;
  outer: for (const host of YAHOO_SEARCH_HOSTS) {
    for (const params of queryVariants) {
      const url = `${host}?${new URLSearchParams(params)}`;
      try {
        const payload = await yahooGetJson(url);
        const parsed = parseSearchPayload(symbol, payload, count);
        if (!parsed) {
          lastError = `No recent stories found for ${symbol}.`;
          continue;
        }
        rememberTicker(symbol, parsed.name, parsed.stories);
        return parsed;
      } catch (exc) {
        if (exc.status) {
          lastError = `Yahoo Finance HTTP ${exc.status} for ${symbol}.`;
          if (exc.status === 429) {
            break outer;
          }
        } else {
          lastError = `Yahoo Finance request failed for ${symbol}: ${exc.message || exc}`;
        }
      }
    }
  }

  const cached = getCachedTicker(symbol);
  if (cached) {
    cached.error = `${lastError} Showing last saved headlines.`;
    return cached;
  }

  return {
    ticker: symbol,
    name: symbol,
    stories: [],
    error: lastError,
    from_cache: false,
  };
}

async function fetchStoriesForTickers(ticker1, ticker2, count = 2) {
  const t1 = normalizeTicker(ticker1) || DEFAULT_TICKER_1;
  const t2 = normalizeTicker(ticker2) || DEFAULT_TICKER_2;
  const first = await fetchStoriesForTicker(t1, count);
  await sleep(REQUEST_GAP_MS);
  const second = await fetchStoriesForTicker(t2, count);
  const results = [first, second];
  rememberPair(t1, t2, results);
  const errors = results.map((r) => r.error).filter(Boolean);
  return {
    tickers: results,
    ok: errors.length === 0,
    errors,
    ticker1: t1,
    ticker2: t2,
  };
}

function formatStoriesForPrompt(tickerResults) {
  const lines = [
    "Using only the recent Yahoo Finance headlines below, write a short " +
      "market briefing that compares the two tickers. Cite story titles " +
      "where helpful. Do not invent facts beyond what the headlines imply.",
    "",
  ];
  for (const block of tickerResults) {
    const ticker = block.ticker || "?";
    const name = block.name || ticker;
    lines.push(`## ${ticker} (${name})`);
    const stories = block.stories || [];
    if (!stories.length) {
      lines.push("- (no stories available)");
      if (block.error) lines.push(`- note: ${block.error}`);
    } else {
      stories.forEach((story, i) => {
        const title = story.title || "(untitled)";
        const source = formatStorySource(story) || "unknown";
        lines.push(`${i + 1}. ${title} — ${source}`);
      });
    }
    lines.push("");
  }
  return lines.join("\n").trim();
}

module.exports = {
  DEFAULT_TICKER_1,
  DEFAULT_TICKER_2,
  normalizeTicker,
  getLastPairCached,
  fetchStoriesForTickers,
  formatStoriesForPrompt,
  formatStorySource,
  formatPublishedDisplay,
};

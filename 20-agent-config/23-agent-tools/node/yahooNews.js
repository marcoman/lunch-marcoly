/**
 * yahooNews.js — fetch recent news titles for two tickers.
 *
 * Live waterfall (stop on the first source that returns headlines):
 *   1. Finnhub — if FINNHUB_API_KEY is set
 *   2. Massive — if MASSIVE_API_KEY is set
 *   3. Yahoo Finance search JSON — no API key
 *   4. Disk cache (../stories/stories_cache.json), then the on-screen error
 *
 * Every provider is mapped into the same story shape so the UI, cache, and
 * LLM prompt never see vendor-specific JSON.
 */

"use strict";

const fs = require("fs");
const path = require("path");

const EXAMPLE_ROOT = path.resolve(__dirname, "..");
const SERIES_ROOT = path.resolve(EXAMPLE_ROOT, ".."); // 20-agent-config/
const STORIES_DIR = path.join(SERIES_ROOT, "stories");
const CACHE_PATH = path.join(STORIES_DIR, "stories_cache.json");

const YAHOO_SEARCH_HOSTS = [
  "https://query1.finance.yahoo.com/v1/finance/search",
  "https://query2.finance.yahoo.com/v1/finance/search",
];
const FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news";
const MASSIVE_NEWS_URL = "https://api.massive.com/v2/reference/news";

// Space Yahoo calls; stop walking hosts/variants on HTTP 429.
const REQUEST_GAP_MS = 1000;

const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

const DEFAULT_TICKER_1 = "NVDA";
const DEFAULT_TICKER_2 = "SPCX";

function envKey(name) {
  return String(process.env[name] || "").trim();
}

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

function toIso(value) {
  if (value == null || value === "") return "";
  if (typeof value === "number" && Number.isFinite(value)) return unixToIso(value);
  const text = String(value).trim();
  if (!text) return "";
  if (/^\d+$/.test(text)) return unixToIso(text);
  const dt = new Date(text);
  if (Number.isNaN(dt.getTime())) return text;
  return dt.toISOString().replace(/\.\d{3}Z$/, "Z");
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

function commonStory({ title, publisher = "", published = "", link = "", uuid = "" }) {
  const t = String(title || "").trim();
  if (!t) return null;
  return {
    title: t,
    publisher: String(publisher || "").trim(),
    published: String(published || "").trim(),
    link: String(link || "").trim(),
    uuid: String(uuid || "").trim(),
  };
}

function tickerOk(symbol, name, stories, source) {
  return {
    ticker: symbol,
    name: name || symbol,
    stories,
    source,
    error: null,
    from_cache: false,
  };
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
    source: "cache",
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

async function getJson(url, extraHeaders = {}, { sleepBefore = 0 } = {}) {
  let lastErr = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (sleepBefore) await sleep(sleepBefore);
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: {
          "User-Agent": USER_AGENT,
          Accept: "application/json",
          "Accept-Language": "en-US,en;q=0.9",
          ...extraHeaders,
        },
        signal: AbortSignal.timeout(20000),
      });
      if (!res.ok) {
        const err = new Error(`HTTP ${res.status}`);
        err.status = res.status;
        if (res.status === 429) throw err;
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
      if (exc.status === 429) throw exc;
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
  throw lastErr || new Error("News request failed");
}

function httpFail(label, symbol, exc) {
  if (exc && exc.status) return `${label} HTTP ${exc.status} for ${symbol}.`;
  return `${label} request failed for ${symbol}: ${exc.message || exc}`;
}

async function fetchFinnhub(symbol, count) {
  const token = envKey("FINNHUB_API_KEY");
  if (!token) return { parsed: null, err: "" };
  const end = new Date();
  const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000);
  const isoDate = (d) => d.toISOString().slice(0, 10);
  const url = `${FINNHUB_NEWS_URL}?${new URLSearchParams({
    symbol,
    from: isoDate(start),
    to: isoDate(end),
    token,
  })}`;
  let payload;
  try {
    payload = await getJson(url);
  } catch (exc) {
    return { parsed: null, err: httpFail("Finnhub", symbol, exc) };
  }
  if (!Array.isArray(payload)) {
    return { parsed: null, err: `Finnhub returned no stories for ${symbol}.` };
  }
  const stories = [];
  for (const item of payload) {
    if (!item || typeof item !== "object") continue;
    const story = commonStory({
      title: item.headline || item.title || "",
      publisher: item.source || "",
      published: toIso(item.datetime),
      link: item.url || "",
      uuid: item.id == null ? "" : String(item.id),
    });
    if (story) stories.push(story);
    if (stories.length >= count) break;
  }
  if (!stories.length) {
    return { parsed: null, err: `No recent stories found for ${symbol}.` };
  }
  return { parsed: tickerOk(symbol, symbol, stories, "finnhub"), err: "" };
}

async function fetchMassive(symbol, count) {
  const token = envKey("MASSIVE_API_KEY");
  if (!token) return { parsed: null, err: "" };
  const url = `${MASSIVE_NEWS_URL}?${new URLSearchParams({
    ticker: symbol,
    limit: String(Math.max(1, count)),
    sort: "published_utc",
    order: "desc",
  })}`;
  let payload;
  try {
    payload = await getJson(url, { Authorization: `Bearer ${token}` });
  } catch (exc) {
    return { parsed: null, err: httpFail("Massive", symbol, exc) };
  }
  const results = payload && payload.results;
  if (!Array.isArray(results) || !results.length) {
    return { parsed: null, err: `No recent stories found for ${symbol}.` };
  }
  const stories = [];
  for (const item of results) {
    if (!item || typeof item !== "object") continue;
    const publisher = item.publisher && typeof item.publisher === "object"
      ? item.publisher.name || ""
      : item.publisher || "";
    const story = commonStory({
      title: item.title || item.headline || "",
      publisher,
      published: toIso(item.published_utc),
      link: item.article_url || item.url || "",
      uuid: item.id == null ? "" : String(item.id),
    });
    if (story) stories.push(story);
    if (stories.length >= count) break;
  }
  if (!stories.length) {
    return { parsed: null, err: `No recent stories found for ${symbol}.` };
  }
  return { parsed: tickerOk(symbol, symbol, stories, "massive"), err: "" };
}

function parseYahooPayload(symbol, payload, count) {
  const quotes = payload.quotes || [];
  let name = "";
  if (quotes.length) {
    const q0 = quotes[0] || {};
    name = String(q0.shortname || q0.longname || "").trim();
  }
  const stories = [];
  for (const item of (payload.news || []).slice(0, count)) {
    const story = commonStory({
      title: item.title || "",
      publisher: item.publisher || "",
      published: unixToIso(item.providerPublishTime),
      link: item.link || "",
      uuid: item.uuid || "",
    });
    if (story) stories.push(story);
  }
  if (!stories.length) return null;
  return tickerOk(symbol, name || symbol, stories, "yahoo");
}

async function fetchYahoo(symbol, count) {
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
  for (const host of YAHOO_SEARCH_HOSTS) {
    for (const params of queryVariants) {
      const url = `${host}?${new URLSearchParams(params)}`;
      try {
        const payload = await getJson(url, {}, { sleepBefore: REQUEST_GAP_MS });
        const parsed = parseYahooPayload(symbol, payload, count);
        if (!parsed) {
          lastError = `No recent stories found for ${symbol}.`;
          continue;
        }
        return { parsed, err: "" };
      } catch (exc) {
        if (exc.status) {
          lastError = `Yahoo Finance HTTP ${exc.status} for ${symbol}.`;
          if (exc.status === 429) return { parsed: null, err: lastError };
        } else {
          lastError = `Yahoo Finance request failed for ${symbol}: ${exc.message || exc}`;
        }
      }
    }
  }
  return { parsed: null, err: lastError };
}

async function fetchStoriesForTicker(ticker, count = 2) {
  const symbol = normalizeTicker(ticker);
  if (!symbol) {
    return {
      ticker: "",
      name: "",
      stories: [],
      source: "",
      error: "Ticker is empty.",
      from_cache: false,
    };
  }

  let lastError = `No recent stories found for ${symbol}.`;

  if (envKey("FINNHUB_API_KEY")) {
    const { parsed, err } = await fetchFinnhub(symbol, count);
    if (parsed) {
      rememberTicker(symbol, parsed.name, parsed.stories);
      return parsed;
    }
    if (err) lastError = err;
  }

  if (envKey("MASSIVE_API_KEY")) {
    const { parsed, err } = await fetchMassive(symbol, count);
    if (parsed) {
      rememberTicker(symbol, parsed.name, parsed.stories);
      return parsed;
    }
    if (err) lastError = err;
  }

  {
    const { parsed, err } = await fetchYahoo(symbol, count);
    if (parsed) {
      rememberTicker(symbol, parsed.name, parsed.stories);
      return parsed;
    }
    if (err) lastError = err;
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
    source: "",
    error: lastError,
    from_cache: false,
  };
}

async function fetchStoriesForTickers(ticker1, ticker2, count = 2) {
  const t1 = normalizeTicker(ticker1) || DEFAULT_TICKER_1;
  const t2 = normalizeTicker(ticker2) || DEFAULT_TICKER_2;
  const first = await fetchStoriesForTicker(t1, count);
  if (first.source === "yahoo" || !(first.stories || []).length) {
    await sleep(REQUEST_GAP_MS);
  }
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
    "Using only the recent headlines below, write a short " +
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

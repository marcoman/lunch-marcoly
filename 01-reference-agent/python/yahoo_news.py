"""
yahoo_news.py — fetch recent Yahoo Finance news titles for tickers.

Uses Yahoo's unofficial public search JSON endpoints (no API key). Several
host/query variants are tried because Yahoo rate-limits and occasionally
returns 404 for a given query shape.

Successful fetches are written to the shared example cache
(../stories/stories_cache.json) so all language apps can reuse the same
headlines:
  * a later 404/429 can fall back to the last good headlines
  * the UI can restore titles on application start

Returned shape (per ticker)
---------------------------
{
  "ticker": "NVDA",
  "name": "NVIDIA Corporation",
  "stories": [
    {"title": "...", "publisher": "...", "link": "...", "uuid": "..."},
    ...
  ],
  "error": null | "human-readable failure",
  "from_cache": false | true
}
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
STORIES_DIR = EXAMPLE_ROOT / "stories"
CACHE_PATH = STORIES_DIR / "stories_cache.json"

YAHOO_SEARCH_HOSTS = (
    "https://query1.finance.yahoo.com/v1/finance/search",
    "https://query2.finance.yahoo.com/v1/finance/search",
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Default demo tickers used when the UI fields are empty.
DEFAULT_TICKER_1 = "NVDA"
DEFAULT_TICKER_2 = "SPCX"


def normalize_ticker(raw: str) -> str:
    """Uppercase ticker; keep letters/digits/.- only."""
    cleaned = re.sub(r"[^A-Za-z0-9.\-]", "", (raw or "").strip().upper())
    return cleaned


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_cache() -> dict[str, Any]:
    """Load the on-disk story cache, or an empty structure."""
    if not CACHE_PATH.is_file():
        return {"updated_at": None, "tickers": {}, "last_pair": None}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"updated_at": None, "tickers": {}, "last_pair": None}
    if not isinstance(data, dict):
        return {"updated_at": None, "tickers": {}, "last_pair": None}
    data.setdefault("tickers", {})
    data.setdefault("last_pair", None)
    data.setdefault("updated_at", None)
    return data


def save_cache(cache: dict[str, Any]) -> None:
    """Persist the shared story cache under 01-reference-agent/stories/."""
    cache = dict(cache)
    cache["updated_at"] = _now_iso()
    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_cached_ticker(ticker: str) -> dict[str, Any] | None:
    """Return a cached ticker block (without error) or None."""
    symbol = normalize_ticker(ticker)
    if not symbol:
        return None
    entry = (load_cache().get("tickers") or {}).get(symbol)
    if not entry or not (entry.get("stories") or []):
        return None
    return {
        "ticker": symbol,
        "name": entry.get("name") or symbol,
        "stories": list(entry.get("stories") or [])[:2],
        "error": None,
        "from_cache": True,
        "cached_at": entry.get("cached_at"),
    }


def get_last_pair_cached() -> dict[str, Any] | None:
    """Return the last successfully saved two-ticker snapshot for UI boot."""
    cache = load_cache()
    pair = cache.get("last_pair")
    if not isinstance(pair, dict):
        return None
    t1 = normalize_ticker(str(pair.get("ticker1") or ""))
    t2 = normalize_ticker(str(pair.get("ticker2") or ""))
    if not t1 or not t2:
        return None
    blocks = []
    for symbol in (t1, t2):
        cached = get_cached_ticker(symbol)
        if cached is None:
            return None
        blocks.append(cached)
    return {
        "ticker1": t1,
        "ticker2": t2,
        "tickers": blocks,
        "updated_at": cache.get("updated_at"),
        "from_cache": True,
    }


def _remember_ticker(symbol: str, name: str, stories: list[dict[str, str]]) -> None:
    """Write one successful ticker result into the cache."""
    if not stories:
        return
    cache = load_cache()
    tickers = dict(cache.get("tickers") or {})
    tickers[symbol] = {
        "name": name or symbol,
        "stories": stories[:2],
        "cached_at": _now_iso(),
    }
    cache["tickers"] = tickers
    save_cache(cache)


def _remember_pair(ticker1: str, ticker2: str, results: list[dict[str, Any]]) -> None:
    """Remember the last pair when both sides have real stories."""
    if len(results) != 2:
        return
    if not all((r.get("stories") or []) and not r.get("from_cache") for r in results):
        # Still update last_pair if both have usable stories (live or mixed).
        if not all(r.get("stories") for r in results):
            return
    cache = load_cache()
    cache["last_pair"] = {
        "ticker1": normalize_ticker(ticker1),
        "ticker2": normalize_ticker(ticker2),
    }
    # Ensure each live success is stored under tickers{}.
    for block in results:
        stories = block.get("stories") or []
        if stories and not block.get("from_cache"):
            symbol = normalize_ticker(str(block.get("ticker") or ""))
            if symbol:
                tickers = dict(cache.get("tickers") or {})
                tickers[symbol] = {
                    "name": block.get("name") or symbol,
                    "stories": stories[:2],
                    "cached_at": _now_iso(),
                }
                cache["tickers"] = tickers
    save_cache(cache)


def _yahoo_get_json(url: str) -> dict[str, Any]:
    """GET JSON from Yahoo; retry once on HTTP 429."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in {429, 503} and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except TimeoutError as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(1.0)
                continue
            raise
    assert last_exc is not None
    raise last_exc


def _parse_search_payload(symbol: str, payload: dict[str, Any], count: int) -> dict[str, Any] | None:
    """Extract name + stories from a Yahoo search payload, or None if empty."""
    quotes = payload.get("quotes") or []
    name = ""
    if quotes:
        q0 = quotes[0] or {}
        name = (q0.get("shortname") or q0.get("longname") or "").strip()

    stories: list[dict[str, str]] = []
    for item in (payload.get("news") or [])[:count]:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        stories.append(
            {
                "title": title,
                "publisher": (item.get("publisher") or "").strip(),
                "link": (item.get("link") or "").strip(),
                "uuid": (item.get("uuid") or "").strip(),
            }
        )
    if not stories:
        return None
    return {
        "ticker": symbol,
        "name": name or symbol,
        "stories": stories,
        "error": None,
        "from_cache": False,
    }


def fetch_stories_for_ticker(ticker: str, count: int = 2) -> dict[str, Any]:
    """Fetch up to `count` recent news stories for one ticker.

    Tries multiple Yahoo URL variants. On hard failure, returns the last
    cached headlines for that ticker when available.
    """
    symbol = normalize_ticker(ticker)
    if not symbol:
        return {
            "ticker": "",
            "name": "",
            "stories": [],
            "error": "Ticker is empty.",
            "from_cache": False,
        }

    # Query variants: ticker-focused news first, then plain search.
    query_variants = (
        {
            "q": symbol,
            "quotesCount": "1",
            "newsCount": str(max(1, count)),
            "enableFuzzyQuery": "false",
            "newsQueryId": "news_cie_vespa",
            "lang": "en-US",
            "region": "US",
        },
        {
            "q": symbol,
            "quotesCount": "1",
            "newsCount": str(max(1, count)),
            "lang": "en-US",
            "region": "US",
        },
    )

    last_error = f"No recent stories found for {symbol}."
    for host in YAHOO_SEARCH_HOSTS:
        for params in query_variants:
            url = f"{host}?{urllib.parse.urlencode(params)}"
            try:
                payload = _yahoo_get_json(url)
            except urllib.error.HTTPError as exc:
                last_error = f"Yahoo Finance HTTP {exc.code} for {symbol}."
                # 404 on one variant is common; try the next shape/host.
                continue
            except urllib.error.URLError as exc:
                last_error = f"Yahoo Finance request failed for {symbol}: {exc.reason}"
                continue
            except (TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"Yahoo Finance response error for {symbol}: {exc}"
                continue

            parsed = _parse_search_payload(symbol, payload, count)
            if parsed is None:
                last_error = f"No recent stories found for {symbol}."
                continue

            _remember_ticker(symbol, parsed["name"], parsed["stories"])
            return parsed

    # Live fetch failed — serve last good headlines if we have them.
    cached = get_cached_ticker(symbol)
    if cached is not None:
        cached["error"] = f"{last_error} Showing last saved headlines."
        return cached

    return {
        "ticker": symbol,
        "name": symbol,
        "stories": [],
        "error": last_error,
        "from_cache": False,
    }


def fetch_stories_for_tickers(
    ticker1: str, ticker2: str, count: int = 2
) -> dict[str, Any]:
    """Fetch stories for two tickers (UI has exactly two inputs)."""
    t1 = normalize_ticker(ticker1) or DEFAULT_TICKER_1
    t2 = normalize_ticker(ticker2) or DEFAULT_TICKER_2
    first = fetch_stories_for_ticker(t1, count=count)
    # Small gap helps avoid Yahoo rate limits when fetching the pair.
    time.sleep(0.5)
    second = fetch_stories_for_ticker(t2, count=count)
    results = [first, second]
    _remember_pair(t1, t2, results)
    errors = [r["error"] for r in results if r.get("error")]
    return {
        "tickers": results,
        "ok": len(errors) == 0,
        "errors": errors,
        "ticker1": t1,
        "ticker2": t2,
    }


def format_stories_for_prompt(ticker_results: list[dict[str, Any]]) -> str:
    """Turn fetched stories into the user-message context for the LLM.

    The model should write report-style prose from these headlines.
    """
    lines = [
        "Using only the recent Yahoo Finance headlines below, write a short "
        "market briefing that compares the two tickers. Cite story titles "
        "where helpful. Do not invent facts beyond what the headlines imply.",
        "",
    ]
    for block in ticker_results:
        ticker = block.get("ticker") or "?"
        name = block.get("name") or ticker
        lines.append(f"## {ticker} ({name})")
        stories = block.get("stories") or []
        if not stories:
            lines.append("- (no stories available)")
            if block.get("error"):
                lines.append(f"- note: {block['error']}")
        else:
            for i, story in enumerate(stories, start=1):
                title = story.get("title") or "(untitled)"
                publisher = story.get("publisher") or "unknown"
                lines.append(f"{i}. {title} — {publisher}")
        lines.append("")
    return "\n".join(lines).strip()

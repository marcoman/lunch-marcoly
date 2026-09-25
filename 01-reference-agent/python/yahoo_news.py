"""
yahoo_news.py — fetch recent news titles for two tickers.

Live waterfall (stop on the first source that returns headlines):
  1. Finnhub — if FINNHUB_API_KEY is set
  2. Massive — if MASSIVE_API_KEY is set
  3. Yahoo Finance search JSON — no API key
  4. Disk cache (../stories/stories_cache.json), then the on-screen error

Every provider is mapped into the same story shape so the UI, cache, and
LLM prompt never see vendor-specific JSON.

Returned shape (per ticker)
---------------------------
{
  "ticker": "NVDA",
  "name": "NVIDIA Corporation",
  "stories": [
    {
      "title": "...",
      "publisher": "...",
      "published": "2026-08-04T15:25:00-04:00",
      "link": "...",
      "uuid": "...",
    },
    ...
  ],
  "source": "finnhub" | "massive" | "yahoo" | "cache" | "",
  "error": null | "human-readable failure",
  "from_cache": false | true
}
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
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
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
MASSIVE_NEWS_URL = "https://api.massive.com/v2/reference/news"
# Space Yahoo calls; stop walking hosts/variants on HTTP 429.
REQUEST_GAP_S = 1.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SOURCE_LABELS = {
    "finnhub": "Finnhub",
    "massive": "Massive",
    "yahoo": "Yahoo Finance",
    "cache": "cache",
}

# Default demo tickers used when the UI fields are empty.
DEFAULT_TICKER_1 = "NVDA"
DEFAULT_TICKER_2 = "SPCX"


def normalize_ticker(raw: str) -> str:
    """Uppercase ticker; keep letters/digits/.- only."""
    cleaned = re.sub(r"[^A-Za-z0-9.\-]", "", (raw or "").strip().upper())
    return cleaned


def source_label(source: str | None, from_cache: bool = False) -> str:
    """Human name for a ticker-block source field."""
    if from_cache or source == "cache":
        return SOURCE_LABELS["cache"]
    return SOURCE_LABELS.get((source or "").strip().lower(), "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _env_key(name: str) -> str:
    return (os.environ.get(name) or "").strip()


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
        "source": "cache",
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


def _common_story(
    *,
    title: str,
    publisher: str = "",
    published: str = "",
    link: str = "",
    uuid: str = "",
) -> dict[str, str] | None:
    """Normalize one headline into the shared story object, or None if empty."""
    title = (title or "").strip()
    if not title:
        return None
    return {
        "title": title,
        "publisher": (publisher or "").strip(),
        "published": (published or "").strip(),
        "link": (link or "").strip(),
        "uuid": (uuid or "").strip(),
    }


def _ticker_ok(
    symbol: str,
    name: str,
    stories: list[dict[str, str]],
    source: str,
) -> dict[str, Any]:
    return {
        "ticker": symbol,
        "name": name or symbol,
        "stories": stories,
        "source": source,
        "error": None,
        "from_cache": False,
    }


def _get_json(
    url: str,
    extra_headers: dict[str, str] | None = None,
    *,
    sleep_before: float = 0.0,
) -> Any:
    """GET JSON. Retries briefly on 503/timeouts. Raises HTTPError on 4xx/429."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers, method="GET")
    last_exc: Exception | None = None
    for attempt in range(3):
        if sleep_before:
            time.sleep(sleep_before)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429:
                raise
            if exc.code == 503 and attempt < 2:
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


def _unix_to_iso(value: Any) -> str:
    """Convert unix seconds to local ISO datetime."""
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return ""
    if ts <= 0:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(
            timespec="seconds"
        )
    except (OverflowError, OSError, ValueError):
        return ""


def _to_iso(value: Any) -> str:
    """Unix seconds or ISO/RFC3339 text → local ISO datetime string."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _unix_to_iso(value)
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit():
        return _unix_to_iso(text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return str(value).strip()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().isoformat(timespec="seconds")


def format_published_display(published: str | None) -> str:
    """Human date+time for UI: 'Aug 4, 2026 3:25 PM'."""
    text = (published or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return text
    hour = dt.strftime("%I").lstrip("0") or "12"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} {hour}:{dt.strftime('%M')} {dt.strftime('%p')}"


def format_story_source(story: dict[str, Any] | None) -> str:
    """Publisher followed by date/time, e.g. 'Simply Wall St. · Aug 4, 2026 3:25 PM'."""
    if not story:
        return ""
    publisher = (story.get("publisher") or "").strip()
    when = format_published_display(str(story.get("published") or ""))
    if publisher and when:
        return f"{publisher} · {when}"
    return publisher or when


def _http_fail(label: str, symbol: str, exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"{label} HTTP {exc.code} for {symbol}."
    if isinstance(exc, urllib.error.URLError):
        return f"{label} request failed for {symbol}: {exc.reason}"
    return f"{label} response error for {symbol}: {exc}"


def _fetch_finnhub(
    symbol: str, count: int
) -> tuple[dict[str, Any] | None, str]:
    """Finnhub company-news → common ticker block. company-news: token query param."""
    token = _env_key("FINNHUB_API_KEY")
    if not token:
        return None, ""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=7)
    url = (
        f"{FINNHUB_NEWS_URL}?"
        + urllib.parse.urlencode(
            {
                "symbol": symbol,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "token": token,
            }
        )
    )
    try:
        payload = _get_json(url)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, _http_fail("Finnhub", symbol, exc)

    if not isinstance(payload, list):
        return None, f"Finnhub returned no stories for {symbol}."

    stories: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        story = _common_story(
            title=str(item.get("headline") or item.get("title") or ""),
            publisher=str(item.get("source") or ""),
            published=_to_iso(item.get("datetime")),
            link=str(item.get("url") or ""),
            uuid=str(item.get("id") or ""),
        )
        if story:
            stories.append(story)
        if len(stories) >= count:
            break
    if not stories:
        return None, f"No recent stories found for {symbol}."
    return _ticker_ok(symbol, symbol, stories, "finnhub"), ""


def _fetch_massive(
    symbol: str, count: int
) -> tuple[dict[str, Any] | None, str]:
    """Massive ticker news — Bearer token. https://massive.com/docs/rest/stocks/news"""
    token = _env_key("MASSIVE_API_KEY")
    if not token:
        return None, ""
    url = (
        f"{MASSIVE_NEWS_URL}?"
        + urllib.parse.urlencode(
            {
                "ticker": symbol,
                "limit": str(max(1, count)),
                "sort": "published_utc",
                "order": "desc",
            }
        )
    )
    try:
        payload = _get_json(url, {"Authorization": f"Bearer {token}"})
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, _http_fail("Massive", symbol, exc)

    if not isinstance(payload, dict):
        return None, f"Massive returned no stories for {symbol}."
    results = payload.get("results") or []
    if not isinstance(results, list) or not results:
        return None, f"No recent stories found for {symbol}."

    stories: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        publisher = item.get("publisher") or {}
        pub_name = ""
        if isinstance(publisher, dict):
            pub_name = str(publisher.get("name") or "")
        elif publisher:
            pub_name = str(publisher)
        story = _common_story(
            title=str(item.get("title") or item.get("headline") or ""),
            publisher=pub_name,
            published=_to_iso(item.get("published_utc")),
            link=str(item.get("article_url") or item.get("url") or ""),
            uuid=str(item.get("id") or ""),
        )
        if story:
            stories.append(story)
        if len(stories) >= count:
            break
    if not stories:
        return None, f"No recent stories found for {symbol}."
    return _ticker_ok(symbol, symbol, stories, "massive"), ""


def _parse_yahoo_payload(symbol: str, payload: dict[str, Any], count: int) -> dict[str, Any] | None:
    """Extract name + stories from a Yahoo search payload, or None if empty."""
    quotes = payload.get("quotes") or []
    name = ""
    if quotes:
        q0 = quotes[0] or {}
        name = (q0.get("shortname") or q0.get("longname") or "").strip()

    stories: list[dict[str, str]] = []
    for item in (payload.get("news") or [])[:count]:
        if not isinstance(item, dict):
            continue
        story = _common_story(
            title=str(item.get("title") or ""),
            publisher=str(item.get("publisher") or ""),
            published=_unix_to_iso(item.get("providerPublishTime")),
            link=str(item.get("link") or ""),
            uuid=str(item.get("uuid") or ""),
        )
        if story:
            stories.append(story)
    if not stories:
        return None
    return _ticker_ok(symbol, name or symbol, stories, "yahoo")


def _fetch_yahoo(
    symbol: str, count: int
) -> tuple[dict[str, Any] | None, str]:
    """Yahoo unofficial search JSON (no API key)."""
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
                payload = _get_json(url, sleep_before=REQUEST_GAP_S)
            except urllib.error.HTTPError as exc:
                last_error = f"Yahoo Finance HTTP {exc.code} for {symbol}."
                if exc.code == 429:
                    return None, last_error
                continue
            except urllib.error.URLError as exc:
                last_error = f"Yahoo Finance request failed for {symbol}: {exc.reason}"
                continue
            except (TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"Yahoo Finance response error for {symbol}: {exc}"
                continue

            if not isinstance(payload, dict):
                last_error = f"No recent stories found for {symbol}."
                continue
            parsed = _parse_yahoo_payload(symbol, payload, count)
            if parsed is None:
                last_error = f"No recent stories found for {symbol}."
                continue
            return parsed, ""
    return None, last_error


def fetch_stories_for_ticker(ticker: str, count: int = 2) -> dict[str, Any]:
    """Fetch up to `count` recent news stories for one ticker.

    Tries Finnhub, then Massive, then Yahoo. Stops at the first live hit.
    On hard failure, returns the last cached headlines when available.
    """
    symbol = normalize_ticker(ticker)
    if not symbol:
        return {
            "ticker": "",
            "name": "",
            "stories": [],
            "source": "",
            "error": "Ticker is empty.",
            "from_cache": False,
        }

    last_error = f"No recent stories found for {symbol}."

    if _env_key("FINNHUB_API_KEY"):
        parsed, err = _fetch_finnhub(symbol, count)
        if parsed is not None:
            _remember_ticker(symbol, parsed["name"], parsed["stories"])
            return parsed
        if err:
            last_error = err

    if _env_key("MASSIVE_API_KEY"):
        parsed, err = _fetch_massive(symbol, count)
        if parsed is not None:
            _remember_ticker(symbol, parsed["name"], parsed["stories"])
            return parsed
        if err:
            last_error = err

    parsed, err = _fetch_yahoo(symbol, count)
    if parsed is not None:
        _remember_ticker(symbol, parsed["name"], parsed["stories"])
        return parsed
    if err:
        last_error = err

    cached = get_cached_ticker(symbol)
    if cached is not None:
        cached["error"] = f"{last_error} Showing last saved headlines."
        return cached

    return {
        "ticker": symbol,
        "name": symbol,
        "stories": [],
        "source": "",
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
    # Gap between tickers when Yahoo was used (each Yahoo GET also waits REQUEST_GAP_S).
    if first.get("source") == "yahoo" or not first.get("stories"):
        time.sleep(REQUEST_GAP_S)
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
        "Using only the recent headlines below, write a short "
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
                source = format_story_source(story) or "unknown"
                lines.append(f"{i}. {title} — {source}")
        lines.append("")
    return "\n".join(lines).strip()

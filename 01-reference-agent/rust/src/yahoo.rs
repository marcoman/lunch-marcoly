use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const DEFAULT_TICKER_1: &str = "NVDA";
pub const DEFAULT_TICKER_2: &str = "SPCX";

const USER_AGENT: &str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) \
    AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

const YAHOO_HOSTS: [&str; 2] = [
    "https://query1.finance.yahoo.com/v1/finance/search",
    "https://query2.finance.yahoo.com/v1/finance/search",
];

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Story {
    pub title: String,
    #[serde(default)]
    pub publisher: String,
    #[serde(default)]
    pub link: String,
    #[serde(default)]
    pub uuid: String,
}

#[derive(Clone, Debug)]
pub struct TickerBlock {
    pub ticker: String,
    pub name: String,
    pub stories: Vec<Story>,
    pub error: Option<String>,
    pub from_cache: bool,
}

#[derive(Clone, Debug)]
pub struct FetchPairResult {
    pub tickers: Vec<TickerBlock>,
    pub errors: Vec<String>,
    #[allow(dead_code)]
    pub ticker1: String,
    #[allow(dead_code)]
    pub ticker2: String,
}

#[derive(Clone, Serialize, Deserialize, Default)]
struct CacheTickerEntry {
    name: String,
    stories: Vec<Story>,
    cached_at: String,
}

#[derive(Serialize, Deserialize, Default)]
struct LastPair {
    ticker1: String,
    ticker2: String,
}

#[derive(Serialize, Deserialize, Default)]
struct StoriesCache {
    updated_at: Option<String>,
    #[serde(default)]
    tickers: std::collections::HashMap<String, CacheTickerEntry>,
    last_pair: Option<LastPair>,
}

pub fn example_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn cache_path() -> PathBuf {
    example_root().join("stories").join("stories_cache.json")
}

fn stories_dir() -> PathBuf {
    example_root().join("stories")
}

fn ticker_cleaner() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[^A-Z0-9.\-]").expect("ticker regex"))
}

pub fn normalize_ticker(raw: &str) -> String {
    let upper = raw.trim().to_uppercase();
    ticker_cleaner().replace_all(&upper, "").into_owned()
}

fn now_iso() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // Cache metadata only; shared readers do not parse this field strictly.
    format!("{secs}")
}

fn load_cache() -> StoriesCache {
    let path = cache_path();
    let Ok(raw) = fs::read_to_string(&path) else {
        return StoriesCache::default();
    };
    serde_json::from_str(&raw).unwrap_or_default()
}

fn save_cache(mut cache: StoriesCache) -> Result<(), String> {
    cache.updated_at = Some(now_iso());
    fs::create_dir_all(stories_dir()).map_err(|e| e.to_string())?;
    let raw = serde_json::to_string_pretty(&cache).map_err(|e| e.to_string())?;
    fs::write(cache_path(), format!("{raw}\n")).map_err(|e| e.to_string())
}

pub fn get_cached_ticker(ticker: &str) -> Option<TickerBlock> {
    let symbol = normalize_ticker(ticker);
    if symbol.is_empty() {
        return None;
    }
    let cache = load_cache();
    let entry = cache.tickers.get(&symbol)?.clone();
    if entry.stories.is_empty() {
        return None;
    }
    let mut stories = entry.stories;
    stories.truncate(2);
    let name = if entry.name.is_empty() {
        symbol.clone()
    } else {
        entry.name
    };
    Some(TickerBlock {
        ticker: symbol,
        name,
        stories,
        error: None,
        from_cache: true,
    })
}

pub fn get_last_pair_cached() -> Option<(String, String, Vec<TickerBlock>)> {
    let cache = load_cache();
    let pair = cache.last_pair?;
    let t1 = normalize_ticker(&pair.ticker1);
    let t2 = normalize_ticker(&pair.ticker2);
    if t1.is_empty() || t2.is_empty() {
        return None;
    }
    let mut blocks = Vec::new();
    for symbol in [&t1, &t2] {
        blocks.push(get_cached_ticker(symbol)?);
    }
    Some((t1, t2, blocks))
}

fn remember_ticker(symbol: &str, name: &str, stories: &[Story]) {
    if stories.is_empty() {
        return;
    }
    let mut cache = load_cache();
    let mut trimmed = stories.to_vec();
    trimmed.truncate(2);
    let name = if name.is_empty() { symbol } else { name };
    cache.tickers.insert(
        symbol.to_string(),
        CacheTickerEntry {
            name: name.to_string(),
            stories: trimmed,
            cached_at: now_iso(),
        },
    );
    let _ = save_cache(cache);
}

fn remember_pair(ticker1: &str, ticker2: &str, results: &[TickerBlock]) {
    if results.len() != 2 || results.iter().any(|r| r.stories.is_empty()) {
        return;
    }
    let mut cache = load_cache();
    cache.last_pair = Some(LastPair {
        ticker1: normalize_ticker(ticker1),
        ticker2: normalize_ticker(ticker2),
    });
    for block in results {
        if block.stories.is_empty() || block.from_cache {
            continue;
        }
        let symbol = normalize_ticker(&block.ticker);
        if symbol.is_empty() {
            continue;
        }
        let mut stories = block.stories.clone();
        stories.truncate(2);
        let name = if block.name.is_empty() {
            symbol.clone()
        } else {
            block.name.clone()
        };
        cache.tickers.insert(
            symbol,
            CacheTickerEntry {
                name,
                stories,
                cached_at: now_iso(),
            },
        );
    }
    let _ = save_cache(cache);
}

fn yahoo_get_json(url: &str) -> Result<Value, String> {
    let mut last_err = String::from("Yahoo request failed");
    for attempt in 0..3 {
        let resp = ureq::get(url)
            .set("User-Agent", USER_AGENT)
            .set("Accept", "application/json")
            .set("Accept-Language", "en-US,en;q=0.9")
            .timeout(Duration::from_secs(20))
            .call();
        match resp {
            Ok(r) => {
                let status = r.status();
                if status == 429 || status == 503 {
                    last_err = format!("HTTP {status}");
                    if attempt < 2 {
                        thread::sleep(Duration::from_millis(1500 * (attempt as u64 + 1)));
                        continue;
                    }
                    return Err(last_err);
                }
                if !(200..300).contains(&status) {
                    return Err(format!("HTTP {status}"));
                }
                return r.into_json().map_err(|e| e.to_string());
            }
            Err(e) => {
                last_err = e.to_string();
                if attempt < 2 {
                    thread::sleep(Duration::from_secs(1));
                    continue;
                }
            }
        }
    }
    Err(last_err)
}

fn parse_search_payload(symbol: &str, payload: &Value, count: usize) -> Option<TickerBlock> {
    let mut name = String::new();
    if let Some(quotes) = payload.get("quotes").and_then(|q| q.as_array()) {
        if let Some(q0) = quotes.first() {
            name = q0
                .get("shortname")
                .and_then(|v| v.as_str())
                .or_else(|| q0.get("longname").and_then(|v| v.as_str()))
                .unwrap_or("")
                .trim()
                .to_string();
        }
    }
    let mut stories = Vec::new();
    if let Some(news) = payload.get("news").and_then(|n| n.as_array()) {
        for item in news.iter().take(count) {
            let title = item
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .trim()
                .to_string();
            if title.is_empty() {
                continue;
            }
            stories.push(Story {
                title,
                publisher: item
                    .get("publisher")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
                link: item
                    .get("link")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
                uuid: item
                    .get("uuid")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .trim()
                    .to_string(),
            });
        }
    }
    if stories.is_empty() {
        return None;
    }
    if name.is_empty() {
        name = symbol.to_string();
    }
    Some(TickerBlock {
        ticker: symbol.to_string(),
        name,
        stories,
        error: None,
        from_cache: false,
    })
}

pub fn fetch_stories_for_ticker(ticker: &str, count: usize) -> TickerBlock {
    let symbol = normalize_ticker(ticker);
    if symbol.is_empty() {
        return TickerBlock {
            ticker: String::new(),
            name: String::new(),
            stories: vec![],
            error: Some("Ticker is empty.".into()),
            from_cache: false,
        };
    }
    let count = count.max(1);
    let variants = [
        format!(
            "q={symbol}&quotesCount=1&newsCount={count}&enableFuzzyQuery=false&newsQueryId=news_cie_vespa&lang=en-US&region=US"
        ),
        format!("q={symbol}&quotesCount=1&newsCount={count}&lang=en-US&region=US"),
    ];

    let mut last_error = format!("No recent stories found for {symbol}.");
    for host in YAHOO_HOSTS {
        for params in &variants {
            let url = format!("{host}?{params}");
            match yahoo_get_json(&url) {
                Ok(payload) => {
                    if let Some(parsed) = parse_search_payload(&symbol, &payload, count) {
                        remember_ticker(&symbol, &parsed.name, &parsed.stories);
                        return parsed;
                    }
                    last_error = format!("No recent stories found for {symbol}.");
                }
                Err(err) => {
                    last_error = if err.starts_with("HTTP ") {
                        format!("Yahoo Finance {err} for {symbol}.")
                    } else {
                        format!("Yahoo Finance request failed for {symbol}: {err}")
                    };
                }
            }
        }
    }

    if let Some(mut cached) = get_cached_ticker(&symbol) {
        cached.error = Some(format!("{last_error} Showing last saved headlines."));
        return cached;
    }
    TickerBlock {
        ticker: symbol.clone(),
        name: symbol,
        stories: vec![],
        error: Some(last_error),
        from_cache: false,
    }
}

pub fn fetch_stories_for_tickers(ticker1: &str, ticker2: &str, count: usize) -> FetchPairResult {
    let mut t1 = normalize_ticker(ticker1);
    if t1.is_empty() {
        t1 = DEFAULT_TICKER_1.to_string();
    }
    let mut t2 = normalize_ticker(ticker2);
    if t2.is_empty() {
        t2 = DEFAULT_TICKER_2.to_string();
    }
    let first = fetch_stories_for_ticker(&t1, count);
    thread::sleep(Duration::from_millis(500));
    let second = fetch_stories_for_ticker(&t2, count);
    let results = vec![first, second];
    remember_pair(&t1, &t2, &results);
    let errors: Vec<String> = results
        .iter()
        .filter_map(|r| r.error.clone())
        .collect();
    FetchPairResult {
        tickers: results,
        errors,
        ticker1: t1,
        ticker2: t2,
    }
}

pub fn format_stories_for_prompt(ticker_results: &[TickerBlock]) -> String {
    let mut lines = vec![
        "Using only the recent Yahoo Finance headlines below, write a short \
         market briefing that compares the two tickers. Cite story titles \
         where helpful. Do not invent facts beyond what the headlines imply."
            .to_string(),
        String::new(),
    ];
    for block in ticker_results {
        let ticker = if block.ticker.is_empty() {
            "?"
        } else {
            &block.ticker
        };
        let name = if block.name.is_empty() {
            ticker
        } else {
            &block.name
        };
        lines.push(format!("## {ticker} ({name})"));
        if block.stories.is_empty() {
            lines.push("- (no stories available)".into());
            if let Some(err) = &block.error {
                lines.push(format!("- note: {err}"));
            }
        } else {
            for (i, story) in block.stories.iter().enumerate() {
                let title = if story.title.is_empty() {
                    "(untitled)"
                } else {
                    &story.title
                };
                let publisher = if story.publisher.is_empty() {
                    "unknown"
                } else {
                    &story.publisher
                };
                lines.push(format!("{}. {title} — {publisher}", i + 1));
            }
        }
        lines.push(String::new());
    }
    lines.join("\n").trim().to_string()
}

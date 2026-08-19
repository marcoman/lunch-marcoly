using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace ConfigOutsideCode;

/// <summary>
/// Fetch recent Yahoo Finance news titles for tickers (no API key).
/// Successful fetches are written to the shared example cache:
///   20-agent-config/stories/stories_cache.json
///
/// Plain data-fetch helper — no LaunchDarkly here. See <see cref="AgentCore"/> for
/// the LD insertion point (this module only supplies the `{{ stories }}` variable).
/// </summary>
public static class YahooNews
{
    public const string DefaultTicker1 = "NVDA";
    public const string DefaultTicker2 = "SPCX";

    private static readonly string[] YahooSearchHosts =
    {
        "https://query1.finance.yahoo.com/v1/finance/search",
        "https://query2.finance.yahoo.com/v1/finance/search",
    };

    // Space Yahoo calls; stop walking hosts/variants on HTTP 429.
    private const int RequestGapMs = 1000;

    private const string UserAgent =
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(20) };
    private static string? _exampleRoot;

    private sealed class YahooHttpException(int statusCode) : Exception($"HTTP {statusCode}")
    {
        public int StatusCode { get; } = statusCode;
    }

    /// <summary>
    /// Locate the example root (22-config-outside-code/) by walking a few
    /// candidate directories relative to the current working directory until
    /// rest/messages/baseline-system.txt is found. Shared with AgentCore for
    /// the baseline (code-fallback) prompt files.
    /// </summary>
    public static string ExampleRoot()
    {
        if (_exampleRoot != null) return _exampleRoot;

        var cwd = Path.GetFullPath(Directory.GetCurrentDirectory());
        var parent = Directory.GetParent(cwd)?.FullName ?? cwd;
        var candidates = new[]
        {
            cwd,
            parent,
            Path.Combine(cwd, "22-config-outside-code"),
            Path.GetFullPath(Path.Combine(cwd, "..")),
            Path.GetFullPath(Path.Combine(cwd, "..", "..")),
        };

        foreach (var candidate in candidates)
        {
            if (File.Exists(Path.Combine(candidate, "rest", "messages", "baseline-system.txt")))
            {
                _exampleRoot = candidate;
                return candidate;
            }
        }

        _exampleRoot = Path.GetFullPath(Path.Combine(cwd, ".."));
        return _exampleRoot;
    }

    /// <summary>Series root (20-agent-config/) — shared stories cache for 21–24.</summary>
    public static string SeriesRoot()
    {
        var parent = Directory.GetParent(ExampleRoot());
        return parent?.FullName ?? ExampleRoot();
    }

    private static string CachePath() => Path.Combine(SeriesRoot(), "stories", "stories_cache.json");

    public static string NormalizeTicker(string? raw)
    {
        if (string.IsNullOrEmpty(raw)) return "";
        var upper = raw.Trim().ToUpperInvariant();
        return new string(upper.Where(c => (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c is '.' or '-').ToArray());
    }

    private static string NowIso() => DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);

    private static string UnixToIso(JsonNode? node)
    {
        if (node is null) return "";
        double ts;
        try
        {
            ts = node.GetValue<double>();
        }
        catch
        {
            return "";
        }
        if (ts <= 0) return "";
        try
        {
            return DateTimeOffset.FromUnixTimeSeconds((long)ts).UtcDateTime
                .ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);
        }
        catch
        {
            return "";
        }
    }

    /// <summary>Human date+time, e.g. "Aug 4, 2026 3:25 PM" (local time zone).</summary>
    public static string FormatPublishedDisplay(string? published)
    {
        if (string.IsNullOrWhiteSpace(published)) return "";
        var text = published.Trim();
        if (!DateTimeOffset.TryParse(text, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var dt))
        {
            return text;
        }
        return dt.ToLocalTime().ToString("MMM d, yyyy h:mm tt", CultureInfo.InvariantCulture);
    }

    /// <summary>Publisher followed by date/time, e.g. "Simply Wall St. · Aug 4, 2026 3:25 PM".</summary>
    public static string FormatStorySource(JsonNode? story)
    {
        if (story is null) return "";
        var publisher = (story["publisher"]?.GetValue<string>() ?? "").Trim();
        var when = FormatPublishedDisplay(story["published"]?.GetValue<string>());
        if (publisher.Length > 0 && when.Length > 0) return $"{publisher} · {when}";
        return publisher.Length > 0 ? publisher : when;
    }

    private static JsonObject LoadCache()
    {
        var path = CachePath();
        if (!File.Exists(path)) return EmptyCache();
        try
        {
            var node = JsonNode.Parse(File.ReadAllText(path));
            if (node is not JsonObject obj) return EmptyCache();
            obj["tickers"] ??= new JsonObject();
            if (!obj.ContainsKey("last_pair")) obj["last_pair"] = null;
            if (!obj.ContainsKey("updated_at")) obj["updated_at"] = null;
            return obj;
        }
        catch
        {
            return EmptyCache();
        }
    }

    private static void SaveCache(JsonObject cache)
    {
        cache["updated_at"] = NowIso();
        try
        {
            var path = CachePath();
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, cache.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n");
        }
        catch
        {
            // Cache is best-effort for demos.
        }
    }

    private static JsonObject EmptyCache() => new()
    {
        ["updated_at"] = null,
        ["tickers"] = new JsonObject(),
        ["last_pair"] = null,
    };

    private static JsonObject? GetCachedTicker(string ticker)
    {
        var symbol = NormalizeTicker(ticker);
        if (symbol.Length == 0) return null;
        var cache = LoadCache();
        if (cache["tickers"] is not JsonObject tickers) return null;
        if (tickers[symbol] is not JsonObject entry) return null;
        if (entry["stories"] is not JsonArray storiesArr || storiesArr.Count == 0) return null;

        var stories = new JsonArray();
        foreach (var s in storiesArr.Take(2)) stories.Add(s?.DeepClone());

        var name = entry["name"]?.GetValue<string>();
        var result = new JsonObject
        {
            ["ticker"] = symbol,
            ["name"] = string.IsNullOrEmpty(name) ? symbol : name,
            ["stories"] = stories,
            ["error"] = null,
            ["from_cache"] = true,
        };
        var cachedAt = entry["cached_at"]?.GetValue<string>();
        if (cachedAt != null) result["cached_at"] = cachedAt;
        return result;
    }

    public static JsonObject? GetLastPairCached()
    {
        var cache = LoadCache();
        if (cache["last_pair"] is not JsonObject pair) return null;
        var t1 = NormalizeTicker(pair["ticker1"]?.GetValue<string>());
        var t2 = NormalizeTicker(pair["ticker2"]?.GetValue<string>());
        if (t1.Length == 0 || t2.Length == 0) return null;

        var blocks = new JsonArray();
        foreach (var symbol in new[] { t1, t2 })
        {
            var cached = GetCachedTicker(symbol);
            if (cached is null) return null;
            blocks.Add(cached);
        }
        return new JsonObject
        {
            ["ticker1"] = t1,
            ["ticker2"] = t2,
            ["tickers"] = blocks,
            ["updated_at"] = cache["updated_at"]?.GetValue<string>(),
            ["from_cache"] = true,
        };
    }

    private static void RememberTicker(string symbol, string? name, JsonArray? stories)
    {
        if (stories is null || stories.Count == 0) return;
        var cache = LoadCache();
        var tickers = cache["tickers"] as JsonObject ?? new JsonObject();
        var take = new JsonArray();
        foreach (var s in stories.Take(2)) take.Add(s?.DeepClone());
        tickers[symbol] = new JsonObject
        {
            ["name"] = string.IsNullOrEmpty(name) ? symbol : name,
            ["stories"] = take,
            ["cached_at"] = NowIso(),
        };
        cache["tickers"] = tickers;
        SaveCache(cache);
    }

    private static void RememberPair(string ticker1, string ticker2, List<JsonObject> results)
    {
        if (results.Count != 2) return;
        if (!results.All(r => (r["stories"] as JsonArray)?.Count > 0)) return;

        var cache = LoadCache();
        cache["last_pair"] = new JsonObject
        {
            ["ticker1"] = NormalizeTicker(ticker1),
            ["ticker2"] = NormalizeTicker(ticker2),
        };

        var tickers = cache["tickers"] as JsonObject ?? new JsonObject();
        foreach (var block in results)
        {
            var fromCache = block["from_cache"]?.GetValue<bool>() ?? false;
            if (fromCache) continue;
            if (block["stories"] is not JsonArray stories || stories.Count == 0) continue;
            var symbol = NormalizeTicker(block["ticker"]?.GetValue<string>());
            if (symbol.Length == 0) continue;

            var take = new JsonArray();
            foreach (var s in stories.Take(2)) take.Add(s?.DeepClone());
            var name = block["name"]?.GetValue<string>();
            tickers[symbol] = new JsonObject
            {
                ["name"] = string.IsNullOrEmpty(name) ? symbol : name,
                ["stories"] = take,
                ["cached_at"] = NowIso(),
            };
        }
        cache["tickers"] = tickers;
        SaveCache(cache);
    }

    private static async Task<JsonObject> YahooGetJsonAsync(string url)
    {
        Exception? lastErr = null;
        for (var attempt = 0; attempt < 3; attempt++)
        {
            await Task.Delay(RequestGapMs);
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, url);
                request.Headers.Add("User-Agent", UserAgent);
                request.Headers.Add("Accept", "application/json");
                request.Headers.Add("Accept-Language", "en-US,en;q=0.9");
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(20));
                using var response = await Http.SendAsync(request, cts.Token);
                if (response.IsSuccessStatusCode)
                {
                    var body = await response.Content.ReadAsStringAsync();
                    return JsonNode.Parse(body) as JsonObject ?? new JsonObject();
                }

                var status = (int)response.StatusCode;
                // Rate-limited: do not retry — caller falls back to cache.
                if (status == 429) throw new YahooHttpException(429);

                lastErr = new YahooHttpException(status);
                if (status == 503 && attempt < 2)
                {
                    await Task.Delay(1500 * (attempt + 1));
                    continue;
                }
                if (attempt < 2)
                {
                    await Task.Delay(1000);
                    continue;
                }
                throw lastErr;
            }
            catch (YahooHttpException)
            {
                throw;
            }
            catch (Exception exc)
            {
                lastErr = exc;
                if (attempt < 2)
                {
                    await Task.Delay(1000);
                    continue;
                }
                throw;
            }
        }
        throw lastErr ?? new InvalidOperationException("Yahoo request failed");
    }

    private static JsonObject? ParseSearchPayload(string symbol, JsonObject payload, int count)
    {
        var name = "";
        if (payload["quotes"] is JsonArray quotes && quotes.Count > 0 && quotes[0] is JsonObject q0)
        {
            name = (q0["shortname"]?.GetValue<string>() ?? q0["longname"]?.GetValue<string>() ?? "").Trim();
        }

        var stories = new JsonArray();
        if (payload["news"] is JsonArray news)
        {
            foreach (var itemNode in news)
            {
                if (stories.Count >= count) break;
                if (itemNode is not JsonObject item) continue;
                var title = (item["title"]?.GetValue<string>() ?? "").Trim();
                if (title.Length == 0) continue;
                stories.Add(new JsonObject
                {
                    ["title"] = title,
                    ["publisher"] = (item["publisher"]?.GetValue<string>() ?? "").Trim(),
                    ["published"] = UnixToIso(item["providerPublishTime"]),
                    ["link"] = (item["link"]?.GetValue<string>() ?? "").Trim(),
                    ["uuid"] = (item["uuid"]?.GetValue<string>() ?? "").Trim(),
                });
            }
        }
        if (stories.Count == 0) return null;
        return new JsonObject
        {
            ["ticker"] = symbol,
            ["name"] = name.Length == 0 ? symbol : name,
            ["stories"] = stories,
            ["error"] = null,
            ["from_cache"] = false,
        };
    }

    private static async Task<JsonObject> FetchStoriesForTickerAsync(string ticker, int count)
    {
        var symbol = NormalizeTicker(ticker);
        if (symbol.Length == 0)
        {
            return new JsonObject
            {
                ["ticker"] = "",
                ["name"] = "",
                ["stories"] = new JsonArray(),
                ["error"] = "Ticker is empty.",
                ["from_cache"] = false,
            };
        }

        var queryVariants = new[]
        {
            new Dictionary<string, string>
            {
                ["q"] = symbol,
                ["quotesCount"] = "1",
                ["newsCount"] = Math.Max(1, count).ToString(),
                ["enableFuzzyQuery"] = "false",
                ["newsQueryId"] = "news_cie_vespa",
                ["lang"] = "en-US",
                ["region"] = "US",
            },
            new Dictionary<string, string>
            {
                ["q"] = symbol,
                ["quotesCount"] = "1",
                ["newsCount"] = Math.Max(1, count).ToString(),
                ["lang"] = "en-US",
                ["region"] = "US",
            },
        };

        var lastError = $"No recent stories found for {symbol}.";
        foreach (var host in YahooSearchHosts)
        {
            var rateLimited = false;
            foreach (var parms in queryVariants)
            {
                var url = $"{host}?{string.Join("&", parms.Select(kv => $"{Uri.EscapeDataString(kv.Key)}={Uri.EscapeDataString(kv.Value)}"))}";
                try
                {
                    var payload = await YahooGetJsonAsync(url);
                    var parsed = ParseSearchPayload(symbol, payload, count);
                    if (parsed is null)
                    {
                        lastError = $"No recent stories found for {symbol}.";
                        continue;
                    }
                    RememberTicker(symbol, parsed["name"]?.GetValue<string>(), parsed["stories"] as JsonArray);
                    return parsed;
                }
                catch (YahooHttpException exc)
                {
                    if (exc.StatusCode == 429)
                    {
                        lastError = $"Yahoo Finance HTTP 429 for {symbol}.";
                        rateLimited = true;
                        break;
                    }
                    lastError = $"Yahoo Finance HTTP {exc.StatusCode} for {symbol}.";
                }
                catch (Exception exc)
                {
                    lastError = $"Yahoo Finance request failed for {symbol}: {exc.Message}";
                }
            }
            if (rateLimited) break;
        }

        var cached = GetCachedTicker(symbol);
        if (cached != null)
        {
            cached["error"] = $"{lastError} Showing last saved headlines.";
            return cached;
        }

        return new JsonObject
        {
            ["ticker"] = symbol,
            ["name"] = symbol,
            ["stories"] = new JsonArray(),
            ["error"] = lastError,
            ["from_cache"] = false,
        };
    }

    public static async Task<JsonObject> FetchStoriesForTickersAsync(string? ticker1, string? ticker2, int count = 2)
    {
        var t1 = NormalizeTicker(ticker1);
        if (t1.Length == 0) t1 = DefaultTicker1;
        var t2 = NormalizeTicker(ticker2);
        if (t2.Length == 0) t2 = DefaultTicker2;

        var first = await FetchStoriesForTickerAsync(t1, count);
        await Task.Delay(RequestGapMs);
        var second = await FetchStoriesForTickerAsync(t2, count);

        var results = new List<JsonObject> { first, second };
        RememberPair(t1, t2, results);

        var errors = results
            .Select(r => r["error"]?.GetValue<string>())
            .Where(e => !string.IsNullOrEmpty(e))
            .Select(e => e!)
            .ToList();

        var tickersArray = new JsonArray();
        foreach (var r in results) tickersArray.Add(r);

        return new JsonObject
        {
            ["tickers"] = tickersArray,
            ["ok"] = errors.Count == 0,
            ["errors"] = new JsonArray(errors.Select(e => (JsonNode)JsonValue.Create(e)).ToArray()),
            ["ticker1"] = t1,
            ["ticker2"] = t2,
        };
    }

    /// <summary>Render the two ticker blocks into the `{{ stories }}` prompt variable.</summary>
    public static string FormatStoriesForPrompt(IEnumerable<JsonNode?> tickerResults)
    {
        var lines = new List<string>
        {
            "Using only the recent Yahoo Finance headlines below, write a short " +
                "market briefing that compares the two tickers. Cite story titles " +
                "where helpful. Do not invent facts beyond what the headlines imply.",
            "",
        };

        foreach (var blockNode in tickerResults)
        {
            var block = blockNode as JsonObject;
            var ticker = block?["ticker"]?.GetValue<string>();
            ticker = string.IsNullOrEmpty(ticker) ? "?" : ticker;
            var name = block?["name"]?.GetValue<string>();
            name = string.IsNullOrEmpty(name) ? ticker : name;
            lines.Add($"## {ticker} ({name})");

            var stories = block?["stories"] as JsonArray;
            if (stories is null || stories.Count == 0)
            {
                lines.Add("- (no stories available)");
                var error = block?["error"]?.GetValue<string>();
                if (!string.IsNullOrEmpty(error)) lines.Add($"- note: {error}");
            }
            else
            {
                var i = 1;
                foreach (var storyNode in stories)
                {
                    var title = storyNode?["title"]?.GetValue<string>();
                    title = string.IsNullOrEmpty(title) ? "(untitled)" : title;
                    var source = FormatStorySource(storyNode);
                    source = string.IsNullOrEmpty(source) ? "unknown" : source;
                    lines.Add($"{i++}. {title} — {source}");
                }
            }
            lines.Add("");
        }

        return string.Join("\n", lines).Trim();
    }
}

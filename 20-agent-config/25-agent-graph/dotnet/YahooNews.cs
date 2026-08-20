using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace AgentGraph;

/// <summary>
/// Fetch recent Yahoo Finance news titles for tickers (no API key).
/// Successful fetches are written to the shared example cache:
///   ../../stories/stories_cache.json (20-agent-config/stories/)
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

    private static string? _cachedExampleRoot;

    /// <summary>
    /// Locate the 25-agent-graph example root (the folder containing
    /// <c>rest/</c>) so messages resolve the same way whether you run
    /// <c>dotnet run</c> from <c>dotnet/</c> or launch the published binary directly.
    /// </summary>
    public static string ExampleRoot()
    {
        if (_cachedExampleRoot != null) return _cachedExampleRoot;

        var cwd = Directory.GetCurrentDirectory();
        var candidates = new List<string> { cwd, Path.GetFullPath(Path.Combine(cwd, "..")) };

        var dir = AppContext.BaseDirectory;
        for (var i = 0; i < 8 && !string.IsNullOrEmpty(dir); i++)
        {
            candidates.Add(dir);
            var parent = Directory.GetParent(dir.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
            dir = parent?.FullName;
        }

        foreach (var candidate in candidates)
        {
            var messages = Path.Combine(candidate, "rest", "messages");
            if (File.Exists(Path.Combine(messages, "assess-instructions.txt")) ||
                File.Exists(Path.Combine(messages, "finalize-instructions.txt")))
            {
                _cachedExampleRoot = candidate;
                return candidate;
            }
        }

        // Fallback: assume cwd is a language directory (dotnet/, node/, python/, java/)
        // sitting directly under the example root.
        _cachedExampleRoot = Path.GetFullPath(Path.Combine(cwd, ".."));
        return _cachedExampleRoot;
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
        var chars = upper.Where(c => (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '-');
        return new string(chars.ToArray());
    }

    // ---------------------------------------------------------------------
    // Cache (JSON file shared with the other language ports)
    // ---------------------------------------------------------------------

    private static JsonObject EmptyCache() => new()
    {
        ["updated_at"] = null,
        ["tickers"] = new JsonObject(),
        ["last_pair"] = null,
    };

    private static JsonObject LoadCache()
    {
        var path = CachePath();
        if (!File.Exists(path)) return EmptyCache();
        try
        {
            if (JsonNode.Parse(File.ReadAllText(path)) is not JsonObject obj) return EmptyCache();
            if (obj["tickers"] is not JsonObject) obj["tickers"] = new JsonObject();
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
        var path = CachePath();
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, cache.ToJsonString(new JsonSerializerOptions { WriteIndented = true }) + "\n");
    }

    public static Dictionary<string, object?>? GetCachedTicker(string ticker)
    {
        var symbol = NormalizeTicker(ticker);
        if (symbol.Length == 0) return null;

        var cache = LoadCache();
        if (cache["tickers"] is not JsonObject tickers) return null;
        if (tickers[symbol] is not JsonObject entry) return null;
        if (entry["stories"] is not JsonArray storiesArr || storiesArr.Count == 0) return null;

        var stories = new List<Dictionary<string, object?>>();
        for (var i = 0; i < Math.Min(2, storiesArr.Count); i++)
        {
            if (storiesArr[i] is JsonObject s) stories.Add(JsonUtil.ToMap(s));
        }

        var name = JsonUtil.AsString(entry["name"]);
        return new Dictionary<string, object?>
        {
            ["ticker"] = symbol,
            ["name"] = string.IsNullOrEmpty(name) ? symbol : name,
            ["stories"] = stories,
            ["error"] = null,
            ["from_cache"] = true,
            ["cached_at"] = JsonUtil.AsString(entry["cached_at"]),
        };
    }

    public static Dictionary<string, object?>? GetLastPairCached()
    {
        var cache = LoadCache();
        if (cache["last_pair"] is not JsonObject pair) return null;

        var t1 = NormalizeTicker(JsonUtil.AsString(pair["ticker1"]));
        var t2 = NormalizeTicker(JsonUtil.AsString(pair["ticker2"]));
        if (t1.Length == 0 || t2.Length == 0) return null;

        var blocks = new List<Dictionary<string, object?>>();
        foreach (var symbol in new[] { t1, t2 })
        {
            var cached = GetCachedTicker(symbol);
            if (cached == null) return null;
            blocks.Add(cached);
        }

        return new Dictionary<string, object?>
        {
            ["ticker1"] = t1,
            ["ticker2"] = t2,
            ["tickers"] = blocks,
            ["updated_at"] = JsonUtil.AsString(cache["updated_at"]),
            ["from_cache"] = true,
        };
    }

    private static void RememberTicker(string symbol, string? name, List<Dictionary<string, object?>> stories)
    {
        if (stories.Count == 0) return;
        var cache = LoadCache();
        var tickers = cache["tickers"] as JsonObject ?? new JsonObject();
        tickers[symbol] = new JsonObject
        {
            ["name"] = string.IsNullOrEmpty(name) ? symbol : name,
            ["stories"] = JsonUtil.FromObject(stories.Count > 2 ? stories.GetRange(0, 2) : stories),
            ["cached_at"] = NowIso(),
        };
        cache["tickers"] = tickers;
        SaveCache(cache);
    }

    private static void RememberPair(string ticker1, string ticker2, List<Dictionary<string, object?>> results)
    {
        if (results.Count != 2) return;
        foreach (var r in results)
        {
            if (JsonUtil.AsDictList(r.GetValueOrDefault("stories")).Count == 0) return;
        }

        var cache = LoadCache();
        cache["last_pair"] = new JsonObject
        {
            ["ticker1"] = NormalizeTicker(ticker1),
            ["ticker2"] = NormalizeTicker(ticker2),
        };

        var tickers = cache["tickers"] as JsonObject ?? new JsonObject();
        foreach (var block in results)
        {
            if (block.GetValueOrDefault("from_cache") is true) continue;
            var stories = JsonUtil.AsDictList(block.GetValueOrDefault("stories"));
            var symbol = NormalizeTicker(block.GetValueOrDefault("ticker") as string ?? "");
            if (symbol.Length == 0 || stories.Count == 0) continue;
            tickers[symbol] = new JsonObject
            {
                ["name"] = (block.GetValueOrDefault("name") as string) ?? symbol,
                ["stories"] = JsonUtil.FromObject(stories.Count > 2 ? stories.GetRange(0, 2) : stories),
                ["cached_at"] = NowIso(),
            };
        }
        cache["tickers"] = tickers;
        SaveCache(cache);
    }

    // ---------------------------------------------------------------------
    // Yahoo Finance fetch
    // ---------------------------------------------------------------------

    private sealed class YahooHttpException : Exception
    {
        public int StatusCode { get; }
        public YahooHttpException(int statusCode) : base($"HTTP {statusCode}") => StatusCode = statusCode;
    }

    private static async Task<JsonObject> YahooGetJsonAsync(string url)
    {
        Exception? last = null;
        for (var attempt = 0; attempt < 3; attempt++)
        {
            await Task.Delay(RequestGapMs);
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, url);
                request.Headers.TryAddWithoutValidation("User-Agent", UserAgent);
                request.Headers.TryAddWithoutValidation("Accept", "application/json");
                request.Headers.TryAddWithoutValidation("Accept-Language", "en-US,en;q=0.9");
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(20));
                using var response = await Http.SendAsync(request, cts.Token);
                var code = (int)response.StatusCode;
                if (code is >= 200 and < 300)
                {
                    var body = await response.Content.ReadAsStringAsync();
                    return JsonNode.Parse(body) as JsonObject ?? new JsonObject();
                }

                // Rate-limited: do not retry — caller falls back to cache.
                if (code == 429) throw new YahooHttpException(code);
                if (code == 503 && attempt < 2)
                {
                    last = new YahooHttpException(code);
                    await Task.Delay(1500 * (attempt + 1));
                    continue;
                }
                throw new YahooHttpException(code);
            }
            catch (YahooHttpException)
            {
                throw;
            }
            catch (Exception exc)
            {
                last = exc;
                if (attempt < 2)
                {
                    await Task.Delay(1000);
                    continue;
                }
                throw;
            }
        }
        throw last ?? new Exception("Yahoo request failed");
    }

    private static Dictionary<string, object?>? ParseSearchPayload(string symbol, JsonObject payload, int count)
    {
        var name = "";
        if (payload["quotes"] is JsonArray quotes && quotes.Count > 0 && quotes[0] is JsonObject q0)
        {
            name = FirstNonBlank(JsonUtil.AsString(q0["shortname"]), JsonUtil.AsString(q0["longname"]));
        }

        var stories = new List<Dictionary<string, object?>>();
        if (payload["news"] is JsonArray news)
        {
            foreach (var item in news)
            {
                if (stories.Count >= count) break;
                if (item is not JsonObject obj) continue;
                var title = (JsonUtil.AsString(obj["title"]) ?? "").Trim();
                if (title.Length == 0) continue;
                stories.Add(new Dictionary<string, object?>
                {
                    ["title"] = title,
                    ["publisher"] = (JsonUtil.AsString(obj["publisher"]) ?? "").Trim(),
                    ["published"] = UnixToIso(obj["providerPublishTime"]),
                    ["link"] = (JsonUtil.AsString(obj["link"]) ?? "").Trim(),
                    ["uuid"] = (JsonUtil.AsString(obj["uuid"]) ?? "").Trim(),
                });
            }
        }

        if (stories.Count == 0) return null;
        return new Dictionary<string, object?>
        {
            ["ticker"] = symbol,
            ["name"] = string.IsNullOrEmpty(name) ? symbol : name,
            ["stories"] = stories,
            ["error"] = null,
            ["from_cache"] = false,
        };
    }

    public static async Task<Dictionary<string, object?>> FetchStoriesForTickerAsync(string ticker, int count)
    {
        var symbol = NormalizeTicker(ticker);
        if (symbol.Length == 0)
        {
            return new Dictionary<string, object?>
            {
                ["ticker"] = "",
                ["name"] = "",
                ["stories"] = new List<Dictionary<string, object?>>(),
                ["error"] = "Ticker is empty.",
                ["from_cache"] = false,
            };
        }

        var newsCount = Math.Max(1, count).ToString(CultureInfo.InvariantCulture);
        var queryVariants = new List<Dictionary<string, string>>
        {
            new()
            {
                ["q"] = symbol,
                ["quotesCount"] = "1",
                ["newsCount"] = newsCount,
                ["enableFuzzyQuery"] = "false",
                ["newsQueryId"] = "news_cie_vespa",
                ["lang"] = "en-US",
                ["region"] = "US",
            },
            new()
            {
                ["q"] = symbol,
                ["quotesCount"] = "1",
                ["newsCount"] = newsCount,
                ["lang"] = "en-US",
                ["region"] = "US",
            },
        };

        var lastError = $"No recent stories found for {symbol}.";
        foreach (var host in YahooSearchHosts)
        {
            var rateLimited = false;
            foreach (var parameters in queryVariants)
            {
                var url = $"{host}?{BuildQuery(parameters)}";
                try
                {
                    var payload = await YahooGetJsonAsync(url);
                    var parsed = ParseSearchPayload(symbol, payload, count);
                    if (parsed == null)
                    {
                        lastError = $"No recent stories found for {symbol}.";
                        continue;
                    }
                    var stories = (List<Dictionary<string, object?>>)parsed["stories"]!;
                    RememberTicker(symbol, parsed["name"] as string, stories);
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

        return new Dictionary<string, object?>
        {
            ["ticker"] = symbol,
            ["name"] = symbol,
            ["stories"] = new List<Dictionary<string, object?>>(),
            ["error"] = lastError,
            ["from_cache"] = false,
        };
    }

    public static async Task<Dictionary<string, object?>> FetchStoriesForTickersAsync(string? ticker1, string? ticker2, int count)
    {
        var t1 = NormalizeTicker(ticker1);
        if (t1.Length == 0) t1 = DefaultTicker1;
        var t2 = NormalizeTicker(ticker2);
        if (t2.Length == 0) t2 = DefaultTicker2;

        var first = await FetchStoriesForTickerAsync(t1, count);
        await Task.Delay(RequestGapMs);
        var second = await FetchStoriesForTickerAsync(t2, count);
        var results = new List<Dictionary<string, object?>> { first, second };
        RememberPair(t1, t2, results);

        var errors = results
            .Select(r => r.GetValueOrDefault("error") as string)
            .Where(e => !string.IsNullOrEmpty(e))
            .ToList();

        return new Dictionary<string, object?>
        {
            ["tickers"] = results,
            ["ok"] = errors.Count == 0,
            ["errors"] = errors,
            ["ticker1"] = t1,
            ["ticker2"] = t2,
        };
    }

    public static string FormatStoriesForPrompt(List<Dictionary<string, object?>> tickerResults)
    {
        var lines = new List<string>
        {
            "Using only the recent Yahoo Finance headlines below, write a short market briefing " +
            "that compares the two tickers. Cite story titles where helpful. Do not invent facts " +
            "beyond what the headlines imply.",
            "",
        };

        foreach (var block in tickerResults)
        {
            var ticker = block.GetValueOrDefault("ticker") as string ?? "?";
            var name = block.GetValueOrDefault("name") as string ?? ticker;
            lines.Add($"## {ticker} ({name})");

            var stories = JsonUtil.AsDictList(block.GetValueOrDefault("stories"));
            if (stories.Count == 0)
            {
                lines.Add("- (no stories available)");
                if (block.GetValueOrDefault("error") is string error && !string.IsNullOrEmpty(error))
                {
                    lines.Add($"- note: {error}");
                }
            }
            else
            {
                for (var i = 0; i < stories.Count; i++)
                {
                    var title = stories[i].GetValueOrDefault("title") as string ?? "(untitled)";
                    var source = FormatStorySource(stories[i]);
                    if (string.IsNullOrEmpty(source)) source = "unknown";
                    lines.Add($"{i + 1}. {title} — {source}");
                }
            }
            lines.Add("");
        }

        return string.Join("\n", lines).Trim();
    }

    /// <summary>Human date+time: 'Aug 4, 2026, 3:25 PM'.</summary>
    public static string FormatPublishedDisplay(string? published)
    {
        var text = (published ?? "").Trim();
        if (text.Length == 0) return "";
        if (DateTimeOffset.TryParse(
                text, CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var dto))
        {
            return dto.ToLocalTime().ToString("MMM d, yyyy h:mm tt", CultureInfo.InvariantCulture);
        }
        return text;
    }

    /// <summary>Publisher followed by date/time, e.g. 'Simply Wall St. · Aug 4, 2026, 3:25 PM'.</summary>
    public static string FormatStorySource(Dictionary<string, object?> story)
    {
        var publisher = (story.GetValueOrDefault("publisher") as string ?? "").Trim();
        var when = FormatPublishedDisplay(story.GetValueOrDefault("published") as string);
        if (publisher.Length > 0 && when.Length > 0) return $"{publisher} · {when}";
        return publisher.Length > 0 ? publisher : when;
    }

    private static string FirstNonBlank(string? a, string? b)
    {
        if (!string.IsNullOrWhiteSpace(a)) return a!.Trim();
        if (!string.IsNullOrWhiteSpace(b)) return b!.Trim();
        return "";
    }

    private static string BuildQuery(Dictionary<string, string> parameters)
        => string.Join("&", parameters.Select(kv => $"{Uri.EscapeDataString(kv.Key)}={Uri.EscapeDataString(kv.Value)}"));

    private static string UnixToIso(JsonNode? node)
    {
        var ts = JsonUtil.AsLong(node);
        if (ts is null or <= 0) return "";
        try
        {
            return DateTimeOffset.FromUnixTimeSeconds(ts.Value).UtcDateTime
                .ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);
        }
        catch
        {
            return "";
        }
    }

    private static string NowIso() => DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);
}

using System.Collections.Generic;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace AgentTools;

/// <summary>
/// Fetch recent news titles (Finnhub → Massive → Yahoo). No LaunchDarkly.
/// Headlines are mapped to {title, publisher, published, link, uuid}.
/// Cache: 20-agent-config/stories/stories_cache.json.
/// </summary>
public static class YahooNews
{
    public const string DefaultTicker1 = "NVDA";
    public const string DefaultTicker2 = "SPCX";

    private static readonly string[] SearchHosts =
    {
        "https://query1.finance.yahoo.com/v1/finance/search",
        "https://query2.finance.yahoo.com/v1/finance/search",
    };

    // Space Yahoo calls; stop walking hosts/variants on HTTP 429.
    private static readonly TimeSpan RequestGap = TimeSpan.FromSeconds(1);
    private const string UserAgent =
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(20) };

    /// <summary>
    /// Locate 23-agent-tools/ by finding rest/messages/baseline-system.txt, walking
    /// up from the current working directory. Mirrors the Java port's exampleRoot().
    /// </summary>
    public static string ExampleRoot()
    {
        var cwd = Path.GetFullPath(Directory.GetCurrentDirectory());
        var candidates = new List<string?>
        {
            cwd,
            Directory.GetParent(cwd)?.FullName ?? cwd,
            Path.Combine(cwd, "23-agent-tools"),
            Path.GetFullPath(Path.Combine(cwd, "..")),
            Path.GetFullPath(Path.Combine(cwd, "..", "..")),
        };
        foreach (var candidate in candidates)
        {
            if (candidate is null) continue;
            var messages = Path.Combine(candidate, "rest", "messages");
            if (File.Exists(Path.Combine(messages, "baseline-system.txt")) ||
                File.Exists(Path.Combine(messages, "tools-system.txt")))
            {
                return candidate;
            }
        }
        return Path.GetFullPath(Path.Combine(cwd, ".."));
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
        return Regex.Replace(raw.Trim().ToUpperInvariant(), "[^A-Z0-9.\\-]", "");
    }

    public static JsonObject? GetLastPairCached()
    {
        var cache = LoadCache();
        if (cache["last_pair"] is not JsonObject pair) return null;
        var t1 = NormalizeTicker(JsonHelpers.GetStr(pair, "ticker1"));
        var t2 = NormalizeTicker(JsonHelpers.GetStr(pair, "ticker2"));
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
            ["updated_at"] = cache["updated_at"]?.DeepClone(),
            ["from_cache"] = true,
        };
    }

    public static async Task<JsonObject> FetchStoriesForTickersAsync(string ticker1, string ticker2, int count)
    {
        var t1 = NormalizeTicker(ticker1);
        if (t1.Length == 0) t1 = DefaultTicker1;
        var t2 = NormalizeTicker(ticker2);
        if (t2.Length == 0) t2 = DefaultTicker2;

        var first = await FetchStoriesForTickerAsync(t1, count);
        await Task.Delay(RequestGap);
        var second = await FetchStoriesForTickerAsync(t2, count);
        var results = new[] { first, second };
        RememberPair(t1, t2, results);

        var errors = new JsonArray();
        foreach (var r in results)
        {
            var error = JsonHelpers.GetStr(r, "error");
            if (error.Length > 0) errors.Add(error);
        }

        return new JsonObject
        {
            ["tickers"] = new JsonArray(first.DeepClone(), second.DeepClone()),
            ["ok"] = errors.Count == 0,
            ["errors"] = errors,
            ["ticker1"] = t1,
            ["ticker2"] = t2,
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
                ["source"] = "",
                ["error"] = "Ticker is empty.",
                ["from_cache"] = false,
            };
        }

        var lastError = $"No recent stories found for {symbol}.";
        if (EnvKey("FINNHUB_API_KEY").Length > 0)
        {
            var (parsed, err) = await FetchFinnhubJsonAsync(symbol, count);
            if (parsed != null)
            {
                RememberTicker(symbol, JsonHelpers.GetStr(parsed, "name", symbol), (JsonArray)parsed["stories"]!);
                return parsed;
            }
            if (!string.IsNullOrEmpty(err)) lastError = err;
        }
        if (EnvKey("MASSIVE_API_KEY").Length > 0)
        {
            var (parsed, err) = await FetchMassiveJsonAsync(symbol, count);
            if (parsed != null)
            {
                RememberTicker(symbol, JsonHelpers.GetStr(parsed, "name", symbol), (JsonArray)parsed["stories"]!);
                return parsed;
            }
            if (!string.IsNullOrEmpty(err)) lastError = err;
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
        foreach (var host in SearchHosts)
        {
            foreach (var parameters in queryVariants)
            {
                var url = $"{host}?{EncodeParams(parameters)}";
                try
                {
                    var node = await GetJsonNodeAsync(url, sleepBefore: RequestGap);
                    if (node is not JsonObject payload)
                    {
                        lastError = $"No recent stories found for {symbol}.";
                        continue;
                    }
                    var parsed = ParseSearchPayload(symbol, payload, count);
                    if (parsed is null)
                    {
                        lastError = $"No recent stories found for {symbol}.";
                        continue;
                    }
                    RememberTicker(symbol, JsonHelpers.GetStr(parsed, "name", symbol), (JsonArray)parsed["stories"]!);
                    return parsed;
                }
                catch (YahooHttpException exc)
                {
                    lastError = $"Yahoo Finance HTTP {exc.StatusCode} for {symbol}.";
                    if (exc.StatusCode == 429) goto AfterYahoo;
                }
                catch (Exception exc)
                {
                    lastError = $"Yahoo Finance request failed for {symbol}: {exc.Message}";
                }
            }
        }
        AfterYahoo:

        var cached = GetCachedTicker(symbol);
        if (cached is not null)
        {
            cached["error"] = $"{lastError} Showing last saved headlines.";
            return cached;
        }

        return new JsonObject
        {
            ["ticker"] = symbol,
            ["name"] = symbol,
            ["stories"] = new JsonArray(),
            ["source"] = "",
            ["error"] = lastError,
            ["from_cache"] = false,
        };
    }

    private static string EnvKey(string name) => (Environment.GetEnvironmentVariable(name) ?? "").Trim();

    private static async Task<JsonNode> GetJsonNodeAsync(string url, Dictionary<string, string>? extraHeaders = null, TimeSpan? sleepBefore = null)
    {
        Exception? last = null;
        for (var attempt = 0; attempt < 3; attempt++)
        {
            if (sleepBefore is { } gap) await Task.Delay(gap);
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.UserAgent.ParseAdd(UserAgent);
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            request.Headers.AcceptLanguage.Add(new StringWithQualityHeaderValue("en-US"));
            if (extraHeaders != null)
            {
                foreach (var kv in extraHeaders)
                    request.Headers.TryAddWithoutValidation(kv.Key, kv.Value);
            }
            HttpResponseMessage response;
            try
            {
                response = await Http.SendAsync(request);
            }
            catch (Exception exc)
            {
                last = exc;
                if (attempt < 2) { await Task.Delay(1000); continue; }
                throw;
            }
            var code = (int)response.StatusCode;
            if (code is >= 200 and < 300)
            {
                var body = await response.Content.ReadAsStringAsync();
                return JsonNode.Parse(body) ?? new JsonObject();
            }
            if (code == 429) throw new YahooHttpException(429, "HTTP 429");
            if (code == 503 && attempt < 2)
            {
                await Task.Delay(TimeSpan.FromMilliseconds(1500 * (attempt + 1)));
                continue;
            }
            if (attempt < 2)
            {
                await Task.Delay(1000);
                continue;
            }
            throw new YahooHttpException(code, $"HTTP {code}");
        }
        throw last ?? new YahooHttpException(0, "News request failed");
    }

    private static JsonObject? CommonStory(string? title, string? publisher, string? published, string? link, string? uuid)
    {
        title = (title ?? "").Trim();
        if (title.Length == 0) return null;
        return new JsonObject
        {
            ["title"] = title,
            ["publisher"] = (publisher ?? "").Trim(),
            ["published"] = (published ?? "").Trim(),
            ["link"] = (link ?? "").Trim(),
            ["uuid"] = (uuid ?? "").Trim(),
        };
    }

    private static async Task<(JsonObject? parsed, string err)> FetchFinnhubJsonAsync(string symbol, int count)
    {
        var token = EnvKey("FINNHUB_API_KEY");
        if (token.Length == 0) return (null, "");
        var end = DateTime.UtcNow.Date;
        var start = end.AddDays(-7);
        var url = "https://finnhub.io/api/v1/company-news?" +
                  $"symbol={Uri.EscapeDataString(symbol)}&from={start:yyyy-MM-dd}&to={end:yyyy-MM-dd}&token={Uri.EscapeDataString(token)}";
        JsonNode payload;
        try { payload = await GetJsonNodeAsync(url); }
        catch (YahooHttpException exc) { return (null, $"Finnhub HTTP {exc.StatusCode} for {symbol}."); }
        catch (Exception exc) { return (null, $"Finnhub request failed for {symbol}: {exc.Message}"); }
        if (payload is not JsonArray arr) return (null, $"Finnhub returned no stories for {symbol}.");
        var stories = new JsonArray();
        foreach (var item in arr)
        {
            if (stories.Count >= count) break;
            if (item is not JsonObject obj) continue;
            var story = CommonStory(
                JsonHelpers.GetStr(obj, "headline", JsonHelpers.GetStr(obj, "title")),
                JsonHelpers.GetStr(obj, "source"),
                UnixToIso(obj["datetime"]),
                JsonHelpers.GetStr(obj, "url"),
                obj["id"]?.ToString());
            if (story != null) stories.Add(story);
        }
        if (stories.Count == 0) return (null, $"No recent stories found for {symbol}.");
        return (new JsonObject
        {
            ["ticker"] = symbol, ["name"] = symbol, ["stories"] = stories,
            ["source"] = "finnhub", ["error"] = null, ["from_cache"] = false,
        }, "");
    }

    private static async Task<(JsonObject? parsed, string err)> FetchMassiveJsonAsync(string symbol, int count)
    {
        var token = EnvKey("MASSIVE_API_KEY");
        if (token.Length == 0) return (null, "");
        var url = "https://api.massive.com/v2/reference/news?" +
                  $"ticker={Uri.EscapeDataString(symbol)}&limit={Math.Max(1, count)}&sort=published_utc&order=desc";
        JsonNode payload;
        try
        {
            payload = await GetJsonNodeAsync(url, new Dictionary<string, string> { ["Authorization"] = $"Bearer {token}" });
        }
        catch (YahooHttpException exc) { return (null, $"Massive HTTP {exc.StatusCode} for {symbol}."); }
        catch (Exception exc) { return (null, $"Massive request failed for {symbol}: {exc.Message}"); }
        if (payload is not JsonObject obj || obj["results"] is not JsonArray results || results.Count == 0)
            return (null, $"No recent stories found for {symbol}.");
        var stories = new JsonArray();
        foreach (var item in results)
        {
            if (stories.Count >= count) break;
            if (item is not JsonObject news) continue;
            var publisher = news["publisher"] is JsonObject pub
                ? JsonHelpers.GetStr(pub, "name")
                : JsonHelpers.GetStr(news, "publisher");
            var story = CommonStory(
                JsonHelpers.GetStr(news, "title"),
                publisher,
                JsonHelpers.GetStr(news, "published_utc"),
                FirstNonBlank(JsonHelpers.GetStr(news, "article_url"), JsonHelpers.GetStr(news, "url")),
                JsonHelpers.GetStr(news, "id"));
            if (story != null) stories.Add(story);
        }
        if (stories.Count == 0) return (null, $"No recent stories found for {symbol}.");
        return (new JsonObject
        {
            ["ticker"] = symbol, ["name"] = symbol, ["stories"] = stories,
            ["source"] = "massive", ["error"] = null, ["from_cache"] = false,
        }, "");
    }

    private sealed class YahooHttpException(int statusCode, string message) : Exception(message)
    {
        public int StatusCode { get; } = statusCode;
    }

    private static JsonObject? ParseSearchPayload(string symbol, JsonObject payload, int count)
    {
        var name = "";
        if (payload["quotes"] is JsonArray { Count: > 0 } quotes && quotes[0] is JsonObject q0)
        {
            name = FirstNonBlank(JsonHelpers.GetStr(q0, "shortname"), JsonHelpers.GetStr(q0, "longname"));
        }

        var stories = new JsonArray();
        if (payload["news"] is JsonArray news)
        {
            foreach (var item in news)
            {
                if (stories.Count >= count) break;
                if (item is not JsonObject storyItem) continue;
                var title = JsonHelpers.GetStr(storyItem, "title").Trim();
                if (title.Length == 0) continue;
                stories.Add(new JsonObject
                {
                    ["title"] = title,
                    ["publisher"] = JsonHelpers.GetStr(storyItem, "publisher").Trim(),
                    ["published"] = UnixToIso(storyItem["providerPublishTime"]),
                    ["link"] = JsonHelpers.GetStr(storyItem, "link").Trim(),
                    ["uuid"] = JsonHelpers.GetStr(storyItem, "uuid").Trim(),
                });
            }
        }
        if (stories.Count == 0) return null;

        return new JsonObject
        {
            ["ticker"] = symbol,
            ["name"] = name.Length == 0 ? symbol : name,
            ["stories"] = stories,
            ["source"] = "yahoo",
            ["error"] = null,
            ["from_cache"] = false,
        };
    }

    private static JsonObject? GetCachedTicker(string ticker)
    {
        var symbol = NormalizeTicker(ticker);
        if (symbol.Length == 0) return null;
        var cache = LoadCache();
        if (cache["tickers"] is not JsonObject tickers || tickers[symbol] is not JsonObject entry) return null;
        if (entry["stories"] is not JsonArray storiesArr || storiesArr.Count == 0) return null;

        var stories = new JsonArray();
        var n = Math.Min(2, storiesArr.Count);
        for (var i = 0; i < n; i++)
        {
            stories.Add(storiesArr[i]?.DeepClone());
        }

        var result = new JsonObject
        {
            ["ticker"] = symbol,
            ["name"] = FirstNonBlank(JsonHelpers.GetStr(entry, "name"), symbol),
            ["stories"] = stories,
            ["source"] = "cache",
            ["error"] = null,
            ["from_cache"] = true,
        };
        if (entry["cached_at"] is not null)
        {
            result["cached_at"] = JsonHelpers.GetStr(entry, "cached_at");
        }
        return result;
    }

    private static void RememberTicker(string symbol, string name, JsonArray stories)
    {
        if (stories.Count == 0) return;
        var cache = LoadCache();
        var tickers = cache["tickers"] as JsonObject ?? new JsonObject();
        var trimmed = new JsonArray();
        for (var i = 0; i < Math.Min(2, stories.Count); i++) trimmed.Add(stories[i]?.DeepClone());
        tickers[symbol] = new JsonObject
        {
            ["name"] = name.Length == 0 ? symbol : name,
            ["stories"] = trimmed,
            ["cached_at"] = NowIso(),
        };
        cache["tickers"] = tickers;
        SaveCache(cache);
    }

    private static void RememberPair(string ticker1, string ticker2, JsonObject[] results)
    {
        if (results.Length != 2) return;
        foreach (var r in results)
        {
            if (r["stories"] is not JsonArray { Count: > 0 }) return;
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
            if (JsonHelpers.GetBool(block, "from_cache")) continue;
            if (block["stories"] is not JsonArray stories || stories.Count == 0) continue;
            var symbol = NormalizeTicker(JsonHelpers.GetStr(block, "ticker"));
            if (symbol.Length == 0) continue;
            var trimmed = new JsonArray();
            for (var i = 0; i < Math.Min(2, stories.Count); i++) trimmed.Add(stories[i]?.DeepClone());
            tickers[symbol] = new JsonObject
            {
                ["name"] = JsonHelpers.GetStr(block, "name", symbol),
                ["stories"] = trimmed,
                ["cached_at"] = NowIso(),
            };
        }
        cache["tickers"] = tickers;
        SaveCache(cache);
    }

    private static JsonObject LoadCache()
    {
        var path = CachePath();
        if (!File.Exists(path)) return EmptyCache();
        try
        {
            var parsed = JsonNode.Parse(File.ReadAllText(path, Encoding.UTF8));
            if (parsed is not JsonObject data) return EmptyCache();
            data["tickers"] ??= new JsonObject();
            if (!data.ContainsKey("last_pair")) data["last_pair"] = null;
            if (!data.ContainsKey("updated_at")) data["updated_at"] = null;
            return data;
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
            File.WriteAllText(path, cache.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }) + "\n", Encoding.UTF8);
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

    private static string EncodeParams(Dictionary<string, string> parameters) =>
        string.Join("&", parameters.Select(kv => $"{Uri.EscapeDataString(kv.Key)}={Uri.EscapeDataString(kv.Value)}"));

    private static string NowIso() => DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");

    private static string UnixToIso(JsonNode? node)
    {
        if (node is null) return "";
        long ts;
        try { ts = node.GetValue<long>(); }
        catch { return ""; }
        if (ts <= 0) return "";
        try
        {
            return DateTimeOffset.FromUnixTimeSeconds(ts).ToLocalTime().ToString("yyyy-MM-ddTHH:mm:sszzz");
        }
        catch
        {
            return "";
        }
    }

    /// <summary>Human date+time: 'Aug 4, 2026 3:25 PM'.</summary>
    public static string FormatPublishedDisplay(string? published)
    {
        if (string.IsNullOrWhiteSpace(published)) return "";
        if (!DateTimeOffset.TryParse(published, out var dt)) return published;
        return dt.LocalDateTime.ToString("MMM d, yyyy h:mm tt");
    }

    /// <summary>Publisher followed by date/time, e.g. 'Simply Wall St. · Aug 4, 2026 3:25 PM'.</summary>
    public static string FormatStorySource(JsonObject? story)
    {
        if (story is null) return "";
        var publisher = JsonHelpers.GetStr(story, "publisher").Trim();
        var when = FormatPublishedDisplay(JsonHelpers.GetStr(story, "published"));
        if (publisher.Length > 0 && when.Length > 0) return $"{publisher} · {when}";
        return publisher.Length > 0 ? publisher : when;
    }

    private static string FirstNonBlank(string? a, string? b)
    {
        if (!string.IsNullOrWhiteSpace(a)) return a.Trim();
        if (!string.IsNullOrWhiteSpace(b)) return b.Trim();
        return "";
    }
}

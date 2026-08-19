import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Fetch recent Yahoo Finance news titles for tickers (no API key).
 * Successful fetches are written to the series cache:
 *   20-agent-config/stories/stories_cache.json
 */
public final class YahooNews {
    public static final String DEFAULT_TICKER_1 = "NVDA";
    public static final String DEFAULT_TICKER_2 = "SPCX";

    private static final String[] YAHOO_SEARCH_HOSTS = {
            "https://query1.finance.yahoo.com/v1/finance/search",
            "https://query2.finance.yahoo.com/v1/finance/search"
    };
    /** Space Yahoo calls; stop walking hosts/variants on HTTP 429. */
    private static final long REQUEST_GAP_MS = 1000L;
    private static final String USER_AGENT =
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private YahooNews() {
    }

    /**
     * Locate 23-agent-tools/ by finding rest/messages/tools-system.txt or baseline-system.txt.
     */
    static Path exampleRoot() {
        Path cwd = Path.of("").toAbsolutePath().normalize();
        List<Path> candidates = List.of(
                cwd,
                cwd.getParent() == null ? cwd : cwd.getParent(),
                cwd.resolve("23-agent-tools"),
                cwd.resolve("..").normalize(),
                cwd.resolve("../..").normalize()
        );
        for (Path candidate : candidates) {
            if (candidate == null) {
                continue;
            }
            Path messages = candidate.resolve("rest").resolve("messages");
            if (Files.isRegularFile(messages.resolve("tools-system.txt"))
                    || Files.isRegularFile(messages.resolve("baseline-system.txt"))) {
                return candidate;
            }
        }
        return cwd.resolve("..").normalize();
    }

    /** Series root (20-agent-config/) — shared stories cache for 21–24. */
    private static Path seriesRoot() {
        Path ex = exampleRoot();
        Path parent = ex.getParent();
        return parent != null ? parent : ex;
    }

    private static Path cachePath() {
        return seriesRoot().resolve("stories").resolve("stories_cache.json");
    }

    public static String normalizeTicker(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.trim().toUpperCase().replaceAll("[^A-Z0-9.\\-]", "");
    }

    public static Map<String, Object> getLastPairCached() {
        JsonObject cache = loadCache();
        JsonElement pairEl = cache.get("last_pair");
        if (pairEl == null || !pairEl.isJsonObject()) {
            return null;
        }
        JsonObject pair = pairEl.getAsJsonObject();
        String t1 = normalizeTicker(asString(pair.get("ticker1")));
        String t2 = normalizeTicker(asString(pair.get("ticker2")));
        if (t1.isEmpty() || t2.isEmpty()) {
            return null;
        }
        List<Map<String, Object>> blocks = new ArrayList<>();
        for (String symbol : List.of(t1, t2)) {
            Map<String, Object> cached = getCachedTicker(symbol);
            if (cached == null) {
                return null;
            }
            blocks.add(cached);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ticker1", t1);
        out.put("ticker2", t2);
        out.put("tickers", blocks);
        out.put("updated_at", cache.has("updated_at") ? cache.get("updated_at") : null);
        out.put("from_cache", true);
        return out;
    }

    public static Map<String, Object> fetchStoriesForTickers(String ticker1, String ticker2, int count)
            throws InterruptedException {
        String t1 = normalizeTicker(ticker1);
        if (t1.isEmpty()) {
            t1 = DEFAULT_TICKER_1;
        }
        String t2 = normalizeTicker(ticker2);
        if (t2.isEmpty()) {
            t2 = DEFAULT_TICKER_2;
        }
        Map<String, Object> first = fetchStoriesForTicker(t1, count);
        Thread.sleep(REQUEST_GAP_MS);
        Map<String, Object> second = fetchStoriesForTicker(t2, count);
        List<Map<String, Object>> results = List.of(first, second);
        rememberPair(t1, t2, results);
        List<String> errors = new ArrayList<>();
        for (Map<String, Object> r : results) {
            Object err = r.get("error");
            if (err != null) {
                errors.add(String.valueOf(err));
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("tickers", results);
        out.put("ok", errors.isEmpty());
        out.put("errors", errors);
        out.put("ticker1", t1);
        out.put("ticker2", t2);
        return out;
    }

    /** Plain-text headlines for {{ stories }} (matches Python stories_as_prompt_text). */
    public static String formatStoriesForPrompt(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null || tickerResults.isEmpty()) {
            return "No ticker stories loaded yet. Ask the user to click Get Stories.";
        }
        StringBuilder lines = new StringBuilder();
        for (Map<String, Object> block : tickerResults) {
            String ticker = stringOr(block.get("ticker"), "?").trim().toUpperCase();
            if (ticker.isEmpty()) {
                ticker = "?";
            }
            String name = stringOr(block.get("name"), ticker).trim();
            lines.append(ticker).append(" (").append(name).append(")\n");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> stories = (List<Map<String, Object>>) block.get("stories");
            if (stories == null || stories.isEmpty()) {
                lines.append("  - (no stories available)\n");
                if (block.get("error") != null) {
                    lines.append("  - note: ").append(block.get("error")).append("\n");
                }
            } else {
                int i = 1;
                for (Map<String, Object> story : stories) {
                    if (story == null) {
                        continue;
                    }
                    String title = stringOr(story.get("title"), "").trim();
                    if (title.isEmpty()) {
                        title = "(untitled)";
                    }
                    String source = formatStorySource(story);
                    if (source.isEmpty()) {
                        source = "unknown";
                    }
                    lines.append("  ").append(i++).append(". ").append(title)
                            .append(" — ").append(source).append("\n");
                }
            }
            lines.append("\n");
        }
        return lines.toString().trim();
    }

    private static Map<String, Object> fetchStoriesForTicker(String ticker, int count)
            throws InterruptedException {
        String symbol = normalizeTicker(ticker);
        if (symbol.isEmpty()) {
            return Map.of(
                    "ticker", "",
                    "name", "",
                    "stories", List.of(),
                    "error", "Ticker is empty.",
                    "from_cache", false
            );
        }

        List<Map<String, String>> queryVariants = List.of(
                Map.of(
                        "q", symbol,
                        "quotesCount", "1",
                        "newsCount", String.valueOf(Math.max(1, count)),
                        "enableFuzzyQuery", "false",
                        "newsQueryId", "news_cie_vespa",
                        "lang", "en-US",
                        "region", "US"
                ),
                Map.of(
                        "q", symbol,
                        "quotesCount", "1",
                        "newsCount", String.valueOf(Math.max(1, count)),
                        "lang", "en-US",
                        "region", "US"
                )
        );

        String lastError = "No recent stories found for " + symbol + ".";
        hostLoop:
        for (String host : YAHOO_SEARCH_HOSTS) {
            for (Map<String, String> params : queryVariants) {
                String url = host + "?" + encodeParams(params);
                try {
                    JsonObject payload = yahooGetJson(url);
                    Map<String, Object> parsed = parseSearchPayload(symbol, payload, count);
                    if (parsed == null) {
                        lastError = "No recent stories found for " + symbol + ".";
                        continue;
                    }
                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> stories =
                            (List<Map<String, Object>>) parsed.get("stories");
                    rememberTicker(symbol, stringOr(parsed.get("name"), symbol), stories);
                    return parsed;
                } catch (IOException exc) {
                    lastError = "Yahoo Finance request failed for " + symbol + ": " + exc.getMessage();
                    if (exc.getMessage() != null && exc.getMessage().contains("HTTP 429")) {
                        lastError = "Yahoo Finance HTTP 429 for " + symbol + ".";
                        break hostLoop;
                    }
                    if (exc.getMessage() != null && exc.getMessage().startsWith("HTTP ")) {
                        lastError = "Yahoo Finance " + exc.getMessage() + " for " + symbol + ".";
                    }
                }
            }
        }

        Map<String, Object> cached = getCachedTicker(symbol);
        if (cached != null) {
            cached.put("error", lastError + " Showing last saved headlines.");
            return cached;
        }

        Map<String, Object> empty = new LinkedHashMap<>();
        empty.put("ticker", symbol);
        empty.put("name", symbol);
        empty.put("stories", List.of());
        empty.put("error", lastError);
        empty.put("from_cache", false);
        return empty;
    }

    private static Map<String, Object> parseSearchPayload(String symbol, JsonObject payload, int count) {
        String name = "";
        JsonArray quotes = payload.has("quotes") && payload.get("quotes").isJsonArray()
                ? payload.getAsJsonArray("quotes")
                : new JsonArray();
        if (!quotes.isEmpty() && quotes.get(0).isJsonObject()) {
            JsonObject q0 = quotes.get(0).getAsJsonObject();
            name = firstNonBlank(asString(q0.get("shortname")), asString(q0.get("longname")));
        }

        List<Map<String, Object>> stories = new ArrayList<>();
        JsonArray news = payload.has("news") && payload.get("news").isJsonArray()
                ? payload.getAsJsonArray("news")
                : new JsonArray();
        for (JsonElement el : news) {
            if (stories.size() >= count) {
                break;
            }
            if (!el.isJsonObject()) {
                continue;
            }
            JsonObject item = el.getAsJsonObject();
            String title = asString(item.get("title")).trim();
            if (title.isEmpty()) {
                continue;
            }
            Map<String, Object> story = new LinkedHashMap<>();
            story.put("title", title);
            story.put("publisher", asString(item.get("publisher")).trim());
            story.put("published", unixToIso(item.get("providerPublishTime")));
            story.put("link", asString(item.get("link")).trim());
            story.put("uuid", asString(item.get("uuid")).trim());
            stories.add(story);
        }
        if (stories.isEmpty()) {
            return null;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ticker", symbol);
        out.put("name", name.isEmpty() ? symbol : name);
        out.put("stories", stories);
        out.put("error", null);
        out.put("from_cache", false);
        return out;
    }

    private static JsonObject yahooGetJson(String url) throws IOException, InterruptedException {
        IOException last = null;
        for (int attempt = 0; attempt < 3; attempt++) {
            Thread.sleep(REQUEST_GAP_MS);
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(20))
                    .header("User-Agent", USER_AGENT)
                    .header("Accept", "application/json")
                    .header("Accept-Language", "en-US,en;q=0.9")
                    .GET()
                    .build();
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            int code = response.statusCode();
            if (code >= 200 && code < 300) {
                return JsonParser.parseString(response.body()).getAsJsonObject();
            }
            last = new IOException("HTTP " + code);
            if (code == 429) {
                throw last;
            }
            if (code == 503 && attempt < 2) {
                Thread.sleep(1500L * (attempt + 1));
                continue;
            }
            if (attempt < 2) {
                Thread.sleep(1000);
                continue;
            }
            throw last;
        }
        throw last != null ? last : new IOException("Yahoo request failed");
    }

    private static Map<String, Object> getCachedTicker(String ticker) {
        String symbol = normalizeTicker(ticker);
        if (symbol.isEmpty()) {
            return null;
        }
        JsonObject cache = loadCache();
        JsonObject tickers = cache.has("tickers") && cache.get("tickers").isJsonObject()
                ? cache.getAsJsonObject("tickers")
                : new JsonObject();
        if (!tickers.has(symbol) || !tickers.get(symbol).isJsonObject()) {
            return null;
        }
        JsonObject entry = tickers.getAsJsonObject(symbol);
        JsonArray storiesArr = entry.has("stories") && entry.get("stories").isJsonArray()
                ? entry.getAsJsonArray("stories")
                : new JsonArray();
        if (storiesArr.isEmpty()) {
            return null;
        }
        List<Map<String, Object>> stories = new ArrayList<>();
        int n = Math.min(2, storiesArr.size());
        for (int i = 0; i < n; i++) {
            if (storiesArr.get(i).isJsonObject()) {
                stories.add(GSON.fromJson(storiesArr.get(i), Map.class));
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ticker", symbol);
        out.put("name", firstNonBlank(asString(entry.get("name")), symbol));
        out.put("stories", stories);
        out.put("error", null);
        out.put("from_cache", true);
        if (entry.has("cached_at")) {
            out.put("cached_at", asString(entry.get("cached_at")));
        }
        return out;
    }

    private static void rememberTicker(String symbol, String name, List<Map<String, Object>> stories) {
        if (stories == null || stories.isEmpty()) {
            return;
        }
        JsonObject cache = loadCache();
        JsonObject tickers = cache.has("tickers") && cache.get("tickers").isJsonObject()
                ? cache.getAsJsonObject("tickers")
                : new JsonObject();
        JsonObject entry = new JsonObject();
        entry.addProperty("name", name == null || name.isEmpty() ? symbol : name);
        entry.add("stories", GSON.toJsonTree(stories.size() > 2 ? stories.subList(0, 2) : stories));
        entry.addProperty("cached_at", nowIso());
        tickers.add(symbol, entry);
        cache.add("tickers", tickers);
        saveCache(cache);
    }

    private static void rememberPair(String ticker1, String ticker2, List<Map<String, Object>> results) {
        if (results == null || results.size() != 2) {
            return;
        }
        for (Map<String, Object> r : results) {
            Object stories = r.get("stories");
            if (!(stories instanceof List<?> list) || list.isEmpty()) {
                return;
            }
        }
        JsonObject cache = loadCache();
        JsonObject pair = new JsonObject();
        pair.addProperty("ticker1", normalizeTicker(ticker1));
        pair.addProperty("ticker2", normalizeTicker(ticker2));
        cache.add("last_pair", pair);

        JsonObject tickers = cache.has("tickers") && cache.get("tickers").isJsonObject()
                ? cache.getAsJsonObject("tickers")
                : new JsonObject();
        for (Map<String, Object> block : results) {
            Object fromCache = block.get("from_cache");
            if (Boolean.TRUE.equals(fromCache)) {
                continue;
            }
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> stories = (List<Map<String, Object>>) block.get("stories");
            String symbol = normalizeTicker(stringOr(block.get("ticker"), ""));
            if (symbol.isEmpty() || stories == null || stories.isEmpty()) {
                continue;
            }
            JsonObject entry = new JsonObject();
            entry.addProperty("name", stringOr(block.get("name"), symbol));
            entry.add("stories", GSON.toJsonTree(stories.size() > 2 ? stories.subList(0, 2) : stories));
            entry.addProperty("cached_at", nowIso());
            tickers.add(symbol, entry);
        }
        cache.add("tickers", tickers);
        saveCache(cache);
    }

    private static JsonObject loadCache() {
        Path path = cachePath();
        if (!Files.isRegularFile(path)) {
            return emptyCache();
        }
        try {
            JsonElement parsed = JsonParser.parseString(Files.readString(path));
            if (!parsed.isJsonObject()) {
                return emptyCache();
            }
            JsonObject data = parsed.getAsJsonObject();
            if (!data.has("tickers")) {
                data.add("tickers", new JsonObject());
            }
            if (!data.has("last_pair")) {
                data.add("last_pair", null);
            }
            if (!data.has("updated_at")) {
                data.add("updated_at", null);
            }
            return data;
        } catch (Exception exc) {
            return emptyCache();
        }
    }

    private static void saveCache(JsonObject cache) {
        cache.addProperty("updated_at", nowIso());
        try {
            Path path = cachePath();
            Files.createDirectories(path.getParent());
            Files.writeString(path, GSON.toJson(cache) + "\n", StandardCharsets.UTF_8);
        } catch (IOException ignored) {
            // Cache is best-effort for demos.
        }
    }

    private static JsonObject emptyCache() {
        JsonObject data = new JsonObject();
        data.add("updated_at", null);
        data.add("tickers", new JsonObject());
        data.add("last_pair", null);
        return data;
    }

    private static String encodeParams(Map<String, String> params) {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, String> e : params.entrySet()) {
            if (!sb.isEmpty()) {
                sb.append('&');
            }
            sb.append(URLEncoder.encode(e.getKey(), StandardCharsets.UTF_8));
            sb.append('=');
            sb.append(URLEncoder.encode(e.getValue(), StandardCharsets.UTF_8));
        }
        return sb.toString();
    }

    private static String nowIso() {
        return Instant.now().toString().replaceAll("\\.\\d+Z$", "Z");
    }

    private static String unixToIso(JsonElement el) {
        if (el == null || el.isJsonNull()) {
            return "";
        }
        long ts;
        try {
            ts = el.getAsLong();
        } catch (Exception exc) {
            return "";
        }
        if (ts <= 0) {
            return "";
        }
        try {
            return Instant.ofEpochSecond(ts).atZone(ZoneId.systemDefault()).toOffsetDateTime().toString();
        } catch (Exception exc) {
            return "";
        }
    }

    /** Human date+time: 'Aug 4, 2026, 3:25 PM'. */
    public static String formatPublishedDisplay(String published) {
        if (published == null || published.isBlank()) {
            return "";
        }
        String text = published.trim();
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("MMM d, yyyy h:mm a", Locale.US);
        try {
            return java.time.OffsetDateTime.parse(text).atZoneSameInstant(ZoneId.systemDefault()).format(fmt);
        } catch (Exception ignored) {
            // fall through
        }
        try {
            return Instant.parse(text).atZone(ZoneId.systemDefault()).format(fmt);
        } catch (Exception ignored) {
            return text;
        }
    }

    /** Publisher followed by date/time, e.g. 'Simply Wall St. · Aug 4, 2026, 3:25 PM'. */
    public static String formatStorySource(Map<String, Object> story) {
        if (story == null) {
            return "";
        }
        String publisher = stringOr(story.get("publisher"), "").trim();
        String when = formatPublishedDisplay(stringOr(story.get("published"), ""));
        if (!publisher.isEmpty() && !when.isEmpty()) {
            return publisher + " · " + when;
        }
        if (!publisher.isEmpty()) {
            return publisher;
        }
        return when;
    }

    private static String asString(JsonElement el) {
        if (el == null || el.isJsonNull()) {
            return "";
        }
        try {
            return el.getAsString();
        } catch (Exception exc) {
            return String.valueOf(el);
        }
    }

    private static String stringOr(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String s = String.valueOf(value);
        return s.isEmpty() ? fallback : s;
    }

    private static String firstNonBlank(String a, String b) {
        if (a != null && !a.isBlank()) {
            return a.trim();
        }
        if (b != null && !b.isBlank()) {
            return b.trim();
        }
        return "";
    }
}

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
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Fetch recent news titles for two tickers.
 *
 * Live waterfall: Finnhub (FINNHUB_API_KEY) → Massive (MASSIVE_API_KEY) →
 * Yahoo Finance search JSON (no key) → disk cache.
 * Every provider is mapped into {title, publisher, published, link, uuid}.
 */
public final class YahooNews {
    public static final String DEFAULT_TICKER_1 = "NVDA";
    public static final String DEFAULT_TICKER_2 = "SPCX";

    private static final String[] YAHOO_SEARCH_HOSTS = {
            "https://query1.finance.yahoo.com/v1/finance/search",
            "https://query2.finance.yahoo.com/v1/finance/search"
    };
    private static final String FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news";
    private static final String MASSIVE_NEWS_URL = "https://api.massive.com/v2/reference/news";
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
     * Locate 24-agent-judges/ by finding rest/messages (skeptic or judge system prompts).
     */
    static Path exampleRoot() {
        Path cwd = Path.of("").toAbsolutePath().normalize();
        List<Path> candidates = List.of(
                cwd,
                cwd.getParent() == null ? cwd : cwd.getParent(),
                cwd.resolve("24-agent-judges"),
                cwd.resolve("..").normalize(),
                cwd.resolve("../..").normalize()
        );
        for (Path candidate : candidates) {
            if (candidate == null) {
                continue;
            }
            Path messages = candidate.resolve("rest").resolve("messages");
            if (Files.isRegularFile(messages.resolve("skeptic-system.txt"))
                    || Files.isRegularFile(messages.resolve("judge-source-fidelity-system.txt"))) {
                return candidate;
            }
        }
        return cwd.resolve("..").normalize();
    }

    /** Series root (20-agent-config/) — shared stories cache for 21–25. */
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
        if ("yahoo".equals(first.get("source")) || storiesEmpty(first)) {
            Thread.sleep(REQUEST_GAP_MS);
        }
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

    public static String formatStoriesForPrompt(List<Map<String, Object>> tickerResults) {
        StringBuilder lines = new StringBuilder();
        lines.append("Using only the recent headlines below, write a short ")
                .append("market briefing that compares the two tickers. Cite story titles ")
                .append("where helpful. Do not invent facts beyond what the headlines imply.\n\n");
        for (Map<String, Object> block : tickerResults) {
            String ticker = stringOr(block.get("ticker"), "?");
            String name = stringOr(block.get("name"), ticker);
            lines.append("## ").append(ticker).append(" (").append(name).append(")\n");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> stories = (List<Map<String, Object>>) block.get("stories");
            if (stories == null || stories.isEmpty()) {
                lines.append("- (no stories available)\n");
                if (block.get("error") != null) {
                    lines.append("- note: ").append(block.get("error")).append("\n");
                }
            } else {
                int i = 1;
                for (Map<String, Object> story : stories) {
                    String title = stringOr(story.get("title"), "(untitled)");
                    String source = formatStorySource(story);
                    if (source.isEmpty()) {
                        source = "unknown";
                    }
                    lines.append(i++).append(". ").append(title).append(" — ").append(source).append("\n");
                }
            }
            lines.append("\n");
        }
        return lines.toString().trim();
    }

    private static boolean storiesEmpty(Map<String, Object> block) {
        Object stories = block.get("stories");
        return !(stories instanceof List<?> list) || list.isEmpty();
    }

    private static String envKey(String name) {
        String v = System.getenv(name);
        return v == null ? "" : v.trim();
    }

    private static Map<String, Object> tickerOk(
            String symbol, String name, List<Map<String, Object>> stories, String source) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ticker", symbol);
        out.put("name", name == null || name.isEmpty() ? symbol : name);
        out.put("stories", stories);
        out.put("source", source);
        out.put("error", null);
        out.put("from_cache", false);
        return out;
    }

    private static Map<String, Object> commonStory(
            String title, String publisher, String published, String link, String uuid) {
        title = title == null ? "" : title.trim();
        if (title.isEmpty()) {
            return null;
        }
        Map<String, Object> story = new LinkedHashMap<>();
        story.put("title", title);
        story.put("publisher", publisher == null ? "" : publisher.trim());
        story.put("published", published == null ? "" : published.trim());
        story.put("link", link == null ? "" : link.trim());
        story.put("uuid", uuid == null ? "" : uuid.trim());
        return story;
    }

    private static Map<String, Object> fetchStoriesForTicker(String ticker, int count)
            throws InterruptedException {
        String symbol = normalizeTicker(ticker);
        if (symbol.isEmpty()) {
            Map<String, Object> empty = new LinkedHashMap<>();
            empty.put("ticker", "");
            empty.put("name", "");
            empty.put("stories", List.of());
            empty.put("source", "");
            empty.put("error", "Ticker is empty.");
            empty.put("from_cache", false);
            return empty;
        }

        String lastError = "No recent stories found for " + symbol + ".";
        if (!envKey("FINNHUB_API_KEY").isEmpty()) {
            FetchAttempt attempt = fetchFinnhub(symbol, count);
            if (attempt.parsed != null) {
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> stories =
                        (List<Map<String, Object>>) attempt.parsed.get("stories");
                rememberTicker(symbol, stringOr(attempt.parsed.get("name"), symbol), stories);
                return attempt.parsed;
            }
            if (!attempt.error.isEmpty()) {
                lastError = attempt.error;
            }
        }
        if (!envKey("MASSIVE_API_KEY").isEmpty()) {
            FetchAttempt attempt = fetchMassive(symbol, count);
            if (attempt.parsed != null) {
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> stories =
                        (List<Map<String, Object>>) attempt.parsed.get("stories");
                rememberTicker(symbol, stringOr(attempt.parsed.get("name"), symbol), stories);
                return attempt.parsed;
            }
            if (!attempt.error.isEmpty()) {
                lastError = attempt.error;
            }
        }
        FetchAttempt yahoo = fetchYahoo(symbol, count);
        if (yahoo.parsed != null) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> stories =
                    (List<Map<String, Object>>) yahoo.parsed.get("stories");
            rememberTicker(symbol, stringOr(yahoo.parsed.get("name"), symbol), stories);
            return yahoo.parsed;
        }
        if (!yahoo.error.isEmpty()) {
            lastError = yahoo.error;
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
        empty.put("source", "");
        empty.put("error", lastError);
        empty.put("from_cache", false);
        return empty;
    }

    private record FetchAttempt(Map<String, Object> parsed, String error) {
    }

    private static FetchAttempt fetchFinnhub(String symbol, int count) throws InterruptedException {
        String token = envKey("FINNHUB_API_KEY");
        if (token.isEmpty()) {
            return new FetchAttempt(null, "");
        }
        LocalDate end = LocalDate.now(ZoneId.of("UTC"));
        LocalDate start = end.minusDays(7);
        String url = FINNHUB_NEWS_URL + "?symbol=" + URLEncoder.encode(symbol, StandardCharsets.UTF_8)
                + "&from=" + start
                + "&to=" + end
                + "&token=" + URLEncoder.encode(token, StandardCharsets.UTF_8);
        JsonElement payload;
        try {
            payload = getJson(url, Map.of(), 0);
        } catch (IOException exc) {
            return new FetchAttempt(null, httpFail("Finnhub", symbol, exc));
        }
        if (!payload.isJsonArray()) {
            return new FetchAttempt(null, "Finnhub returned no stories for " + symbol + ".");
        }
        List<Map<String, Object>> stories = new ArrayList<>();
        for (JsonElement el : payload.getAsJsonArray()) {
            if (stories.size() >= count) {
                break;
            }
            if (!el.isJsonObject()) {
                continue;
            }
            JsonObject item = el.getAsJsonObject();
            Map<String, Object> story = commonStory(
                    firstNonBlank(asString(item.get("headline")), asString(item.get("title"))),
                    asString(item.get("source")),
                    toIso(item.get("datetime")),
                    asString(item.get("url")),
                    asString(item.get("id")));
            if (story != null) {
                stories.add(story);
            }
        }
        if (stories.isEmpty()) {
            return new FetchAttempt(null, "No recent stories found for " + symbol + ".");
        }
        return new FetchAttempt(tickerOk(symbol, symbol, stories, "finnhub"), "");
    }

    private static FetchAttempt fetchMassive(String symbol, int count) throws InterruptedException {
        String token = envKey("MASSIVE_API_KEY");
        if (token.isEmpty()) {
            return new FetchAttempt(null, "");
        }
        String url = MASSIVE_NEWS_URL + "?ticker=" + URLEncoder.encode(symbol, StandardCharsets.UTF_8)
                + "&limit=" + Math.max(1, count)
                + "&sort=published_utc&order=desc";
        JsonElement payload;
        try {
            payload = getJson(url, Map.of("Authorization", "Bearer " + token), 0);
        } catch (IOException exc) {
            return new FetchAttempt(null, httpFail("Massive", symbol, exc));
        }
        if (!payload.isJsonObject()) {
            return new FetchAttempt(null, "Massive returned no stories for " + symbol + ".");
        }
        JsonObject obj = payload.getAsJsonObject();
        JsonArray results = obj.has("results") && obj.get("results").isJsonArray()
                ? obj.getAsJsonArray("results")
                : new JsonArray();
        List<Map<String, Object>> stories = new ArrayList<>();
        for (JsonElement el : results) {
            if (stories.size() >= count) {
                break;
            }
            if (!el.isJsonObject()) {
                continue;
            }
            JsonObject item = el.getAsJsonObject();
            String publisher = "";
            if (item.has("publisher") && item.get("publisher").isJsonObject()) {
                publisher = asString(item.getAsJsonObject("publisher").get("name"));
            } else {
                publisher = asString(item.get("publisher"));
            }
            Map<String, Object> story = commonStory(
                    firstNonBlank(asString(item.get("title")), asString(item.get("headline"))),
                    publisher,
                    toIso(item.get("published_utc")),
                    firstNonBlank(asString(item.get("article_url")), asString(item.get("url"))),
                    asString(item.get("id")));
            if (story != null) {
                stories.add(story);
            }
        }
        if (stories.isEmpty()) {
            return new FetchAttempt(null, "No recent stories found for " + symbol + ".");
        }
        return new FetchAttempt(tickerOk(symbol, symbol, stories, "massive"), "");
    }

    private static FetchAttempt fetchYahoo(String symbol, int count) throws InterruptedException {
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
        for (String host : YAHOO_SEARCH_HOSTS) {
            for (Map<String, String> params : queryVariants) {
                String url = host + "?" + encodeParams(params);
                try {
                    JsonElement payload = getJson(url, Map.of(), REQUEST_GAP_MS);
                    if (!payload.isJsonObject()) {
                        lastError = "No recent stories found for " + symbol + ".";
                        continue;
                    }
                    Map<String, Object> parsed = parseSearchPayload(symbol, payload.getAsJsonObject(), count);
                    if (parsed == null) {
                        lastError = "No recent stories found for " + symbol + ".";
                        continue;
                    }
                    return new FetchAttempt(parsed, "");
                } catch (IOException exc) {
                    lastError = "Yahoo Finance request failed for " + symbol + ": " + exc.getMessage();
                    if (exc.getMessage() != null && exc.getMessage().contains("HTTP 429")) {
                        return new FetchAttempt(null, "Yahoo Finance HTTP 429 for " + symbol + ".");
                    }
                    if (exc.getMessage() != null && exc.getMessage().startsWith("HTTP ")) {
                        lastError = "Yahoo Finance " + exc.getMessage() + " for " + symbol + ".";
                    }
                }
            }
        }
        return new FetchAttempt(null, lastError);
    }

    private static String httpFail(String label, String symbol, IOException exc) {
        String msg = exc.getMessage() == null ? "" : exc.getMessage();
        if (msg.startsWith("HTTP ")) {
            return label + " " + msg + " for " + symbol + ".";
        }
        return label + " request failed for " + symbol + ": " + msg;
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
        out.put("source", "yahoo");
        out.put("error", null);
        out.put("from_cache", false);
        return out;
    }

    private static JsonElement getJson(String url, Map<String, String> extraHeaders, long sleepBeforeMs)
            throws IOException, InterruptedException {
        IOException last = null;
        for (int attempt = 0; attempt < 3; attempt++) {
            if (sleepBeforeMs > 0) {
                Thread.sleep(sleepBeforeMs);
            }
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(20))
                    .header("User-Agent", USER_AGENT)
                    .header("Accept", "application/json")
                    .header("Accept-Language", "en-US,en;q=0.9")
                    .GET();
            if (extraHeaders != null) {
                for (Map.Entry<String, String> h : extraHeaders.entrySet()) {
                    builder.header(h.getKey(), h.getValue());
                }
            }
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            int code = response.statusCode();
            if (code >= 200 && code < 300) {
                return JsonParser.parseString(response.body());
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
        throw last != null ? last : new IOException("News request failed");
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
        out.put("source", "cache");
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

    private static String toIso(JsonElement el) {
        if (el == null || el.isJsonNull()) {
            return "";
        }
        if (el.isJsonPrimitive() && el.getAsJsonPrimitive().isNumber()) {
            return unixToIso(el);
        }
        String text = asString(el).trim();
        if (text.isEmpty()) {
            return "";
        }
        if (text.matches("\\d+")) {
            JsonObject tmp = new JsonObject();
            tmp.addProperty("n", Long.parseLong(text));
            return unixToIso(tmp.get("n"));
        }
        try {
            if (text.endsWith("Z")) {
                return Instant.parse(text).atZone(ZoneId.systemDefault()).toOffsetDateTime().toString();
            }
            return java.time.OffsetDateTime.parse(text).atZoneSameInstant(ZoneId.systemDefault())
                    .toOffsetDateTime().toString();
        } catch (Exception ignored) {
            return text;
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

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

/**
 * Thin HTTP adapter for the capstone UI.
 *
 * GET  /              → index.html
 * GET  /api/bootstrap → personas, tools, graph keys
 * GET  /api/stories   → headlines
 * POST /api/generate  → SSE
 * POST /api/feedback  → thumbs on the specialist draft
 *
 * LaunchDarkly work lives in AgentCore.
 */
public class WebServer {
    private static final String APP_BANNER = "20-capstone-1[java]";
    private static final int PORT = Integer.parseInt(System.getenv().getOrDefault("PORT", "8292"));
    private static final Gson GSON = new Gson();

    public static void main(String[] args) throws IOException {
        AgentCore.initLaunchDarkly();
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.setExecutor(Executors.newCachedThreadPool());
        server.start();
        System.out.println(APP_BANNER);
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
        System.out.println("LD_GRAPH_KEY=" + AgentCore.graphKey());
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            URI uri = exchange.getRequestURI();
            String path = uri.getPath();
            if ("GET".equals(method) && ("/".equals(path) || "/index.html".equals(path))) {
                serveIndex(exchange);
                return;
            }
            if ("GET".equals(method) && "/api/bootstrap".equals(path)) {
                sendJson(exchange, 200, bootstrap());
                return;
            }
            if ("GET".equals(method) && "/api/stories".equals(path)) {
                Map<String, String> qs = queryParams(uri.getRawQuery());
                sendJson(exchange, 200, YahooNews.fetchStoriesForTickers(
                        qs.getOrDefault("ticker1", YahooNews.DEFAULT_TICKER_1),
                        qs.getOrDefault("ticker2", YahooNews.DEFAULT_TICKER_2),
                        2));
                return;
            }
            if ("POST".equals(method) && "/api/generate".equals(path)) {
                handleGenerate(exchange);
                return;
            }
            if ("POST".equals(method) && "/api/feedback".equals(path)) {
                handleFeedback(exchange);
                return;
            }
            byte[] missing = "Not found".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(404, missing.length);
            exchange.getResponseBody().write(missing);
            exchange.close();
        } catch (Exception exc) {
            if (!exchange.getResponseHeaders().containsKey("Content-Type") && exchange.getResponseCode() < 0) {
                sendJson(exchange, 500, Map.of("error", String.valueOf(exc.getMessage())));
            }
        }
    }

    private static Map<String, Object> bootstrap() {
        Map<String, Object> cached = YahooNews.getLastPairCached();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("appBanner", APP_BANNER);
        body.put("personas", AgentCore.PERSONAS.stream().map(persona -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", persona.id());
            row.put("name", persona.name());
            row.put("profile", persona.profile());
            row.put("anonymous", persona.anonymous());
            return row;
        }).toList());
        body.put("tools", AgentCore.TOOL_ORDER);
        body.put("actions", List.of(
                Map.of("id", "report", "labelKey", "actionReport"),
                Map.of("id", "questions", "labelKey", "actionQuestions"),
                Map.of("id", "good", "labelKey", "actionGood")
        ));
        body.put("graphKey", AgentCore.graphKey());
        Map<String, String> nodes = new LinkedHashMap<>();
        for (String role : List.of("assess", "report", "questions", "good", "finalize")) nodes.put(role, AgentCore.nodeKey(role));
        body.put("nodeKeys", nodes);
        body.put("judgeKeys", List.of(AgentCore.judgeKey("fidelity"), AgentCore.judgeKey("discipline")));
        Map<String, Object> tickers = new LinkedHashMap<>();
        tickers.put("ticker1", cached == null ? YahooNews.DEFAULT_TICKER_1 : cached.getOrDefault("ticker1", YahooNews.DEFAULT_TICKER_1));
        tickers.put("ticker2", cached == null ? YahooNews.DEFAULT_TICKER_2 : cached.getOrDefault("ticker2", YahooNews.DEFAULT_TICKER_2));
        body.put("defaultTickers", tickers);
        if (cached == null) {
            body.put("persistedStories", null);
        } else {
            Map<String, Object> persisted = new LinkedHashMap<>();
            persisted.put("ticker1", cached.get("ticker1"));
            persisted.put("ticker2", cached.get("ticker2"));
            persisted.put("tickers", cached.get("tickers"));
            persisted.put("savedAt", cached.get("updated_at"));
            persisted.put("directory", "20-agent-config/stories");
            body.put("persistedStories", persisted);
        }
        return body;
    }

    private static void handleGenerate(HttpExchange exchange) throws IOException {
        JsonObject payload = readJson(exchange);
        String personaId = payload.has("personaId") && !payload.get("personaId").isJsonNull() ? payload.get("personaId").getAsString() : "";
        AgentCore.Persona persona = AgentCore.personaById(personaId);
        if (persona == null) persona = AgentCore.PERSONAS.get(1);
        String action = payload.has("action") ? payload.get("action").getAsString() : "report";
        String locale = payload.has("locale") && "es".equals(payload.get("locale").getAsString()) ? "es" : "en";
        List<String> tools = new ArrayList<>();
        if (payload.has("tools") && payload.get("tools").isJsonArray()) {
            for (JsonElement item : payload.getAsJsonArray("tools")) tools.add(item.getAsString());
        }
        List<Map<String, Object>> stories = new ArrayList<>();
        if (payload.has("stories") && payload.get("stories").isJsonArray()) {
            for (JsonElement item : payload.getAsJsonArray("stories")) {
                if (item.isJsonObject()) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> block = GSON.fromJson(item, Map.class);
                    stories.add(block);
                }
            }
        }
        exchange.getResponseHeaders().set("Content-Type", "text/event-stream; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.getResponseHeaders().set("Connection", "close");
        exchange.sendResponseHeaders(200, 0);
        try (OutputStream out = exchange.getResponseBody()) {
            AgentCore.generateStream(persona, action, stories, tools, locale, event -> {
                try {
                    out.write(("data: " + GSON.toJson(event) + "\n\n").getBytes(StandardCharsets.UTF_8));
                    out.flush();
                } catch (IOException ioe) {
                    throw new RuntimeException(ioe);
                }
            });
        } catch (RuntimeException exc) {
            if (!(exc.getCause() instanceof IOException)) throw exc;
        }
    }

    private static void handleFeedback(HttpExchange exchange) throws IOException {
        JsonObject payload = readJson(exchange);
        String personaId = payload.has("personaId") && !payload.get("personaId").isJsonNull() ? payload.get("personaId").getAsString() : "";
        AgentCore.Persona persona = AgentCore.personaById(personaId);
        if (persona == null) persona = AgentCore.PERSONAS.get(1);
        try {
            sendJson(exchange, 200, AgentCore.submitFeedback(
                    persona,
                    payload.has("locale") ? payload.get("locale").getAsString() : "en",
                    payload.has("resumptionToken") && !payload.get("resumptionToken").isJsonNull() ? payload.get("resumptionToken").getAsString() : "",
                    payload.has("kind") ? payload.get("kind").getAsString() : ""
            ));
        } catch (IllegalArgumentException exc) {
            sendJson(exchange, 400, Map.of("ok", false, "error", exc.getMessage()));
        }
    }

    private static JsonObject readJson(HttpExchange exchange) throws IOException {
        byte[] raw = exchange.getRequestBody().readAllBytes();
        if (raw.length == 0) return new JsonObject();
        JsonElement parsed = JsonParser.parseString(new String(raw, StandardCharsets.UTF_8));
        return parsed.isJsonObject() ? parsed.getAsJsonObject() : new JsonObject();
    }

    private static void serveIndex(HttpExchange exchange) throws IOException {
        try (InputStream stream = WebServer.class.getClassLoader().getResourceAsStream("public/index.html")) {
            if (stream == null) {
                byte[] body = "Not found".getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(404, body.length);
                exchange.getResponseBody().write(body);
                exchange.close();
                return;
            }
            byte[] body = stream.readAllBytes();
            exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
            exchange.getResponseHeaders().set("Cache-Control", "no-store");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        }
    }

    private static void sendJson(HttpExchange exchange, int status, Object body) throws IOException {
        byte[] raw = GSON.toJson(body).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.sendResponseHeaders(status, raw.length);
        exchange.getResponseBody().write(raw);
        exchange.close();
    }

    private static Map<String, String> queryParams(String rawQuery) {
        Map<String, String> out = new LinkedHashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) return out;
        for (String part : rawQuery.split("&")) {
            int eq = part.indexOf('=');
            if (eq < 0) out.put(java.net.URLDecoder.decode(part, StandardCharsets.UTF_8), "");
            else {
                out.put(java.net.URLDecoder.decode(part.substring(0, eq), StandardCharsets.UTF_8),
                        java.net.URLDecoder.decode(part.substring(eq + 1), StandardCharsets.UTF_8));
            }
        }
        return out;
    }
}

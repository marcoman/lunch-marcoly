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
 * Thin HTTP adapter for the 22-config-outside-code UI.
 *
 * GET  /              → index.html
 * GET  /api/bootstrap → personas, tickers, cache, config key
 * GET  /api/stories   → Yahoo headlines for two tickers
 * POST /api/generate  → SSE generation events
 * POST /api/feedback  → thumbs via synthetic resumption token
 *
 * LaunchDarkly work lives in AgentCore (jsonValueVariationDetail + track feedback).
 */
public class WebServer {
    private static final String APP_BANNER = "22-config-outside-code[java]";
    private static final int PORT = Integer.parseInt(System.getenv().getOrDefault("PORT", "8222"));
    private static final Gson GSON = new Gson();

    public static void main(String[] args) throws IOException {
        AgentCore.initLaunchDarkly();

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.setExecutor(Executors.newCachedThreadPool());
        server.start();

        System.out.println(APP_BANNER);
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
        System.out.println("LD_AGENT_CONFIG_KEY=" + AgentCore.configKey());
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
                sendJson(exchange, 200, bootstrapBody());
                return;
            }
            if ("GET".equals(method) && "/api/stories".equals(path)) {
                Map<String, String> qs = queryParams(uri.getRawQuery());
                String ticker1 = qs.getOrDefault("ticker1", YahooNews.DEFAULT_TICKER_1);
                String ticker2 = qs.getOrDefault("ticker2", YahooNews.DEFAULT_TICKER_2);
                try {
                    sendJson(exchange, 200, YahooNews.fetchStoriesForTickers(ticker1, ticker2, 2));
                } catch (InterruptedException exc) {
                    Thread.currentThread().interrupt();
                    sendJson(exchange, 500, Map.of("error", "Interrupted while fetching stories."));
                }
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

            byte[] body = "Not found".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(404, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        } catch (Exception exc) {
            exc.printStackTrace();
            if (exchange.getResponseCode() == -1) {
                sendJson(exchange, 500, Map.of("error", String.valueOf(exc.getMessage())));
            } else {
                exchange.close();
            }
        }
    }

    private static Map<String, Object> bootstrapBody() {
        Map<String, Object> cached = YahooNews.getLastPairCached();

        List<Map<String, Object>> personas = new ArrayList<>();
        for (AgentCore.Persona p : AgentCore.PERSONAS) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", p.id());
            row.put("name", p.name());
            row.put("profile", p.profile());
            row.put("anonymous", p.anonymous());
            personas.add(row);
        }

        Map<String, Object> defaultTickers = new LinkedHashMap<>();
        defaultTickers.put(
                "ticker1",
                cached != null && cached.get("ticker1") != null
                        ? cached.get("ticker1")
                        : YahooNews.DEFAULT_TICKER_1
        );
        defaultTickers.put(
                "ticker2",
                cached != null && cached.get("ticker2") != null
                        ? cached.get("ticker2")
                        : YahooNews.DEFAULT_TICKER_2
        );

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("appBanner", APP_BANNER);
        body.put("personas", personas);
        body.put("defaultTickers", defaultTickers);
        body.put("cachedStories", cached);
        body.put("mode", "launchdarkly");
        body.put("provider", "AgentControl");
        body.put("model", "config:" + AgentCore.configKey());
        body.put("configKey", AgentCore.configKey());
        return body;
    }


    private static void handleFeedback(HttpExchange exchange) throws IOException {
        String raw = new String(readBytes(exchange.getRequestBody()), StandardCharsets.UTF_8);
        JsonObject payload;
        try {
            payload = JsonParser.parseString(raw.isBlank() ? "{}" : raw).getAsJsonObject();
        } catch (Exception exc) {
            sendJson(exchange, 400, Map.of("error", "Invalid JSON body."));
            return;
        }

        String personaId = payload.has("personaId") && !payload.get("personaId").isJsonNull()
                ? payload.get("personaId").getAsString()
                : AgentCore.PERSONAS.get(0).id();
        AgentCore.Persona persona = AgentCore.personaById(personaId);
        if (persona == null) {
            persona = AgentCore.PERSONAS.get(0);
        }
        String token = payload.has("resumptionToken") && !payload.get("resumptionToken").isJsonNull()
                ? payload.get("resumptionToken").getAsString()
                : "";
        String kind = payload.has("kind") && !payload.get("kind").isJsonNull()
                ? payload.get("kind").getAsString()
                : "";

        try {
            sendJson(exchange, 200, AgentCore.submitFeedback(persona, token, kind));
        } catch (IllegalArgumentException exc) {
            sendJson(exchange, 400, Map.of("error", String.valueOf(exc.getMessage())));
        } catch (Exception exc) {
            sendJson(exchange, 500, Map.of("error", String.valueOf(exc.getMessage())));
        }
    }

    private static void handleGenerate(HttpExchange exchange) throws IOException {
        String raw = new String(readBytes(exchange.getRequestBody()), StandardCharsets.UTF_8);
        JsonObject payload;
        try {
            payload = JsonParser.parseString(raw.isBlank() ? "{}" : raw).getAsJsonObject();
        } catch (Exception exc) {
            sendJson(exchange, 400, Map.of("error", "Invalid JSON body."));
            return;
        }

        String personaId = payload.has("personaId") && !payload.get("personaId").isJsonNull()
                ? payload.get("personaId").getAsString()
                : AgentCore.PERSONAS.get(0).id();
        AgentCore.Persona persona = AgentCore.personaById(personaId);
        if (persona == null) {
            persona = AgentCore.PERSONAS.get(0);
        }

        List<Map<String, Object>> stories = new ArrayList<>();
        if (payload.has("stories") && payload.get("stories").isJsonArray()) {
            JsonArray arr = payload.getAsJsonArray("stories");
            for (JsonElement el : arr) {
                if (el.isJsonObject()) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> block = GSON.fromJson(el, Map.class);
                    stories.add(block);
                }
            }
        }

        exchange.getResponseHeaders().set("Content-Type", "text/event-stream; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.getResponseHeaders().set("Connection", "close");
        exchange.sendResponseHeaders(200, 0);

        try (OutputStream out = exchange.getResponseBody()) {
            AgentCore.generateStream(persona, stories, event -> {
                try {
                    String line = "data: " + GSON.toJson(event) + "\n\n";
                    out.write(line.getBytes(StandardCharsets.UTF_8));
                    out.flush();
                } catch (IOException ioe) {
                    throw new RuntimeException(ioe);
                }
            });
        } catch (RuntimeException exc) {
            if (!(exc.getCause() instanceof IOException)) {
                throw exc;
            }
            // Client disconnected.
        }
    }

    private static void serveIndex(HttpExchange exchange) throws IOException {
        try (InputStream stream = WebServer.class.getClassLoader()
                .getResourceAsStream("public/index.html")) {
            if (stream == null) {
                byte[] body = "Not found".getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(404, body.length);
                exchange.getResponseBody().write(body);
                exchange.close();
                return;
            }
            byte[] body = readBytes(stream);
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
        if (rawQuery == null || rawQuery.isBlank()) {
            return out;
        }
        for (String part : rawQuery.split("&")) {
            int eq = part.indexOf('=');
            if (eq < 0) {
                out.put(java.net.URLDecoder.decode(part, StandardCharsets.UTF_8), "");
            } else {
                String key = java.net.URLDecoder.decode(part.substring(0, eq), StandardCharsets.UTF_8);
                String value = java.net.URLDecoder.decode(part.substring(eq + 1), StandardCharsets.UTF_8);
                out.put(key, value);
            }
        }
        return out;
    }

    private static byte[] readBytes(InputStream stream) throws IOException {
        return stream.readAllBytes();
    }
}

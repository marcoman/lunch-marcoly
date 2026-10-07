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
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

/**
 * Thin HTTP adapter for 26-flags-vs-agent-control.
 *
 * GET  /              → index.html
 * GET  /api/bootstrap → Toby, tickers, cached stories
 * GET  /api/stories   → headlines for two tickers
 * POST /api/generate  → SSE. Body field source: original | flags | json
 *
 * LaunchDarkly work lives in AgentCore (server SDK JSON + Ollama).
 * There is no official Java AI SDK.
 */
public class WebServer {
    private static final String APP_BANNER = "26-flags-vs-agent-control[java]";
    private static final int PORT = Integer.parseInt(System.getenv().getOrDefault("PORT", "8262"));
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
        System.out.println("LD_JUDGE_KEY=" + AgentCore.judgeKey());
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
        for (AgentCore.Persona p : AgentCore.demoPersonas()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", p.id());
            row.put("name", p.name());
            row.put("profile", p.profile());
            row.put("anonymous", false);
            personas.add(row);
        }
        Map<String, Object> defaultTickers = new LinkedHashMap<>();
        defaultTickers.put("ticker1", cached != null && cached.get("ticker1") != null
                ? cached.get("ticker1") : YahooNews.DEFAULT_TICKER_1);
        defaultTickers.put("ticker2", cached != null && cached.get("ticker2") != null
                ? cached.get("ticker2") : YahooNews.DEFAULT_TICKER_2);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("appBanner", APP_BANNER);
        body.put("personas", personas);
        body.put("defaultTickers", defaultTickers);
        body.put("cachedStories", cached);
        body.put("mode", "launchdarkly");
        body.put("provider", "AgentControl");
        body.put("model", "config:" + AgentCore.configKey());
        body.put("configKey", AgentCore.configKey());
        body.put("judgeKey", AgentCore.judgeKey());
        body.put("sources", List.of(
                Map.of("id", "original", "label", "AgentControl", "enabled", true),
                Map.of("id", "flags", "label", "Separate flags", "enabled", true),
                Map.of("id", "json", "label", "JSON flag", "enabled", true)
        ));
        return body;
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

        List<AgentCore.Persona> demo = AgentCore.demoPersonas();
        String personaId = payload.has("personaId") && !payload.get("personaId").isJsonNull()
                ? payload.get("personaId").getAsString()
                : demo.get(0).id();
        AgentCore.Persona persona = AgentCore.personaById(personaId);
        if (persona == null) {
            persona = demo.get(0);
        }

        List<Map<String, Object>> stories = new ArrayList<>();
        if (payload.has("stories") && payload.get("stories").isJsonArray()) {
            for (JsonElement el : payload.getAsJsonArray("stories")) {
                if (el.isJsonObject()) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> block = GSON.fromJson(el, Map.class);
                    stories.add(block);
                }
            }
        }
        String source = payload.has("source") && !payload.get("source").isJsonNull()
                ? payload.get("source").getAsString()
                : "original";
        if (!source.equals("original") && !source.equals("flags") && !source.equals("json")) {
            source = "original";
        }

        exchange.getResponseHeaders().set("Content-Type", "text/event-stream; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.getResponseHeaders().set("Connection", "close");
        exchange.sendResponseHeaders(200, 0);

        try (OutputStream out = exchange.getResponseBody()) {
            AgentCore.generateStream(persona, stories, source, event -> {
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
        }
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

    private static Map<String, String> queryParams(String raw) {
        Map<String, String> out = new LinkedHashMap<>();
        if (raw == null || raw.isBlank()) {
            return out;
        }
        for (String part : raw.split("&")) {
            int eq = part.indexOf('=');
            String key = eq < 0 ? part : part.substring(0, eq);
            String value = eq < 0 ? "" : part.substring(eq + 1);
            out.put(
                    URLDecoder.decode(key, StandardCharsets.UTF_8),
                    URLDecoder.decode(value, StandardCharsets.UTF_8)
            );
        }
        return out;
    }

    private static byte[] readBytes(InputStream in) throws IOException {
        return in.readAllBytes();
    }
}

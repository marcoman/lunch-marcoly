import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Serve the API guarded-rollout grid.
 *
 * Start guarded release POSTs the environment release.
 *
 * LaunchDarkly: guarded rollout via environment releases
 * https://launchdarkly.com/docs/api/environment-releases
 */
public class WebServer {
    private static final int PORT = Integer.parseInt(System.getenv().getOrDefault("PORT", "8786"));

    public static void main(String[] args) throws IOException {
        HighlightEval.init();
        Runtime.getRuntime().addShutdownHook(new Thread(HighlightEval::close));
        if (args.length >= 2 && "--evaluate-once".equals(args[0])) {
            System.out.println(HighlightEval.evaluate(args[1]));
            return;
        }

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("23-api-guarded-rollout[java]");
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        String method = exchange.getRequestMethod();
        if ("POST".equals(method) && "/api/track".equals(path)) {
            handleTrack(exchange);
            return;
        }
        drain(exchange);
        if ("GET".equals(method) && "/api/highlight".equals(path)) {
            handleHighlight(exchange);
            return;
        }
        if ("GET".equals(method) && "/api/release".equals(path)) {
            sendJson(exchange, 200, ReleaseStatus.latest());
            return;
        }
        if ("GET".equals(method) && "/api/bootstrap".equals(path)) {
            JsonObject body = new JsonObject();
            body.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
            String targeting = ReleaseStatus.targetingUrl();
            if (targeting == null) {
                body.add("targetingUrl", com.google.gson.JsonNull.INSTANCE);
            } else {
                body.addProperty("targetingUrl", targeting);
            }
            body.add("schedule", ReleaseStatus.schedule());
            body.addProperty("thresholdMs", Metrics.LATENCY_THRESHOLD_MS);
            body.add("metrics", Metrics.views());
            sendJson(exchange, 200, body);
            return;
        }
        if ("POST".equals(method) && "/api/release/start".equals(path)) {
            sendResult(exchange, ReleaseStatus.start());
            return;
        }
        if ("POST".equals(method) && "/api/release/stop".equals(path)) {
            sendResult(exchange, ReleaseStatus.stop());
            return;
        }
        if ("POST".equals(method) && "/api/release/reset".equals(path)) {
            sendResult(exchange, ReleaseStatus.reset());
            return;
        }
        if ("GET".equals(method) && ("/".equals(path) || "/index.html".equals(path))) {
            serveIndex(exchange);
            return;
        }
        byte[] missing = "Not found".getBytes(StandardCharsets.UTF_8);
        exchange.sendResponseHeaders(404, missing.length);
        exchange.getResponseBody().write(missing);
        exchange.close();
    }

    private static void handleTrack(HttpExchange exchange) throws IOException {
        String raw;
        try (InputStream in = exchange.getRequestBody()) {
            raw = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
        JsonObject body = raw.isBlank() ? new JsonObject() : JsonParser.parseString(raw).getAsJsonObject();
        String username = body.has("username") ? body.get("username").getAsString().trim() : "";
        double latency = body.has("latencyMs") && body.get("latencyMs").isJsonPrimitive()
                ? body.get("latencyMs").getAsDouble() : Double.NaN;
        if (!HighlightEval.ready()) {
            sendBytes(exchange, 503, "{\"error\":true,\"detail\":\"LD_SDK_KEY is missing or the SDK did not initialize.\"}".getBytes(StandardCharsets.UTF_8));
            return;
        }
        if (username.isEmpty() || latency < 0 || latency > 500) {
            sendBytes(exchange, 400, "{\"error\":true,\"detail\":\"username and latencyMs (0–500) are required.\"}".getBytes(StandardCharsets.UTF_8));
            return;
        }
        sendJson(exchange, 200, HighlightEval.trackObserved(username, latency));
    }

    private static void handleHighlight(HttpExchange exchange) throws IOException {
        Map<String, String> params = parseQuery(exchange.getRequestURI().getRawQuery());
        String username = params.getOrDefault("username", "").trim();
        if (username.isEmpty()) {
            sendBytes(exchange, 400, "{\"error\":\"username query parameter is required\"}".getBytes(StandardCharsets.UTF_8));
            return;
        }
        sendJson(exchange, 200, HighlightEval.evaluate(username));
    }

    private static void sendResult(HttpExchange exchange, JsonObject body) throws IOException {
        boolean failed = (body.has("error") && body.get("error").getAsBoolean())
                || (body.has("configured") && !body.get("configured").getAsBoolean());
        sendJson(exchange, failed ? 400 : 200, body);
    }

    private static void sendJson(HttpExchange exchange, int status, JsonObject body) throws IOException {
        sendBytes(exchange, status, body.toString().getBytes(StandardCharsets.UTF_8));
    }

    private static void sendBytes(HttpExchange exchange, int status, byte[] body) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static void serveIndex(HttpExchange exchange) throws IOException {
        try (InputStream stream = WebServer.class.getClassLoader().getResourceAsStream("public/index.html")) {
            if (stream == null) {
                byte[] missing = "Not found".getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(404, missing.length);
                exchange.getResponseBody().write(missing);
                exchange.close();
                return;
            }
            byte[] body = stream.readAllBytes();
            exchange.getResponseHeaders().set("Content-Type", "text/html; charset=utf-8");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(body);
            }
        }
    }

    private static void drain(HttpExchange exchange) throws IOException {
        try (InputStream in = exchange.getRequestBody()) {
            in.readAllBytes();
        }
    }

    private static Map<String, String> parseQuery(String query) {
        Map<String, String> params = new HashMap<>();
        if (query == null || query.isBlank()) {
            return params;
        }
        for (String pair : query.split("&")) {
            int idx = pair.indexOf('=');
            if (idx <= 0) {
                continue;
            }
            params.put(
                    URLDecoder.decode(pair.substring(0, idx), StandardCharsets.UTF_8),
                    URLDecoder.decode(pair.substring(idx + 1), StandardCharsets.UTF_8));
        }
        return params;
    }
}

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
 * Serve the team-targeting grid navigator web UI on a local HTTP server.
 */
public class WebServer {
    private static final int PORT = readPort();
    public static void main(String[] args) throws IOException {
        TeamStyle.init();
        Runtime.getRuntime().addShutdownHook(new Thread(TeamStyle::close));

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("Targeting-rules lab running at http://127.0.0.1:" + PORT + "/");
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        if ("/api/flags".equals(path)) {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendJson(exchange, 405, Map.of("error", "Method not allowed"));
                return;
            }
            handleFlags(exchange);
            return;
        }
        if ("/api/flag-controls".equals(path)) {
            handleFlagControls(exchange);
            return;
        }
        if ("/api/bootstrap".equals(path)) {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendJson(exchange, 405, Map.of("error", "Method not allowed"));
                return;
            }
            Map<String, Object> bootstrap = new java.util.LinkedHashMap<>();
            bootstrap.put("appBanner", "13-flag-targeting-rules[java]");
            bootstrap.put("controls", FlagControls.apiConfig());
            sendJson(exchange, 200, bootstrap);
            return;
        }

        if ("/".equals(path)) {
            path = "/public/index.html";
        } else if (!path.startsWith("/public/")) {
            path = "/public" + path;
        }

        String resourcePath = path.startsWith("/") ? path.substring(1) : path;
        InputStream stream = WebServer.class.getClassLoader().getResourceAsStream(resourcePath);
        if (stream == null) {
            byte[] body = "Not found".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(404, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
            return;
        }

        byte[] body;
        try (InputStream in = stream) {
            body = readBytes(in);
        }
        String contentType = resourcePath.endsWith(".html") ? "text/html" : "text/plain";
        exchange.getResponseHeaders().set("Content-Type", contentType);
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static void handleFlags(HttpExchange exchange) throws IOException {
        Map<String, String> params = parseQuery(exchange.getRequestURI().getRawQuery());
        String username = params.getOrDefault("username", "").trim();
        if (username.isEmpty()) {
            sendJson(exchange, 400, Map.of("error", "username query parameter is required"));
            return;
        }
        try {
            String team = TeamStyle.normalizeTeam(params.getOrDefault("team", ""));
            sendJson(exchange, 200, TeamStyle.evaluate(username, team));
        } catch (IllegalArgumentException exception) {
            sendJson(exchange, 400, Map.of("error", exception.getMessage()));
        }
    }

    private static void handleFlagControls(HttpExchange exchange) throws IOException {
        if ("GET".equals(exchange.getRequestMethod())) {
            sendJson(exchange, 200, FlagControls.listFlagControls());
            return;
        }
        if (!"POST".equals(exchange.getRequestMethod())) {
            sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            return;
        }

        try {
            String raw = new String(readBytes(exchange.getRequestBody()), StandardCharsets.UTF_8);
            Map<String, Object> request = Json.parseObject(raw.isBlank() ? "{}" : raw);
            String key = request.get("key") == null ? "" : request.get("key").toString().trim();
            if (key.isEmpty()) {
                throw new IllegalArgumentException("\"key\" is required");
            }
            Boolean turnOn = null;
            if (request.containsKey("on")) {
                if (!(request.get("on") instanceof Boolean)) {
                    throw new IllegalArgumentException("\"on\" must be a boolean");
                }
                turnOn = (Boolean) request.get("on");
            }
            boolean hasFallthrough = request.containsKey("fallthrough");
            Map<String, Object> result = FlagControls.applyFlagControl(
                    key, turnOn, hasFallthrough, request.get("fallthrough"));
            sendJson(exchange, 200, result);
        } catch (IllegalArgumentException exception) {
            sendJson(exchange, 400, Map.of("ok", false, "error", exception.getMessage()));
        } catch (RuntimeException exception) {
            sendJson(exchange, 502, Map.of("ok", false, "error", exception.getMessage()));
        }
    }

    private static void sendJson(HttpExchange exchange, int status, Object value) throws IOException {
        sendJsonText(exchange, status, Json.stringify(value));
    }

    private static void sendJsonText(HttpExchange exchange, int status, String json) throws IOException {
        byte[] body = json.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.sendResponseHeaders(status, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static Map<String, String> parseQuery(String query) {
        Map<String, String> params = new HashMap<>();
        if (query == null || query.isBlank()) {
            return params;
        }
        for (String pair : query.split("&")) {
            int idx = pair.indexOf('=');
            if (idx <= 0) continue;
            String key = URLDecoder.decode(pair.substring(0, idx), StandardCharsets.UTF_8);
            String value = URLDecoder.decode(pair.substring(idx + 1), StandardCharsets.UTF_8);
            params.put(key, value);
        }
        return params;
    }

    private static byte[] readBytes(InputStream stream) throws IOException {
        byte[] buffer = new byte[4096];
        int read;
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        while ((read = stream.read(buffer)) != -1) {
            out.write(buffer, 0, read);
        }
        return out.toByteArray();
    }

    private static int readPort() {
        String raw = System.getenv("PORT");
        if (raw == null || raw.isBlank()) {
            return 8080;
        }
        try {
            int port = Integer.parseInt(raw);
            if (port < 1 || port > 65535) throw new NumberFormatException();
            return port;
        } catch (NumberFormatException exception) {
            throw new IllegalArgumentException("PORT must be an integer from 1 to 65535");
        }
    }
}

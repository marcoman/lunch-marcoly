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

/** Serve the prerequisite-flags grid navigator web UI. */
public class WebServer {
    private static final int PORT = readPort();

    public static void main(String[] args) throws IOException {
        Prerequisite.init();
        Runtime.getRuntime().addShutdownHook(new Thread(Prerequisite::close));
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("15-prerequisite-flags[java]");
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        if ("/api/flags".equals(path)) {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendJson(exchange, 405, Map.of("error", "Method not allowed"));
                return;
            }
            Map<String, String> params = parseQuery(exchange.getRequestURI().getRawQuery());
            try {
                sendJson(exchange, 200, Prerequisite.evaluate(params.getOrDefault("username", "")));
            } catch (IllegalArgumentException exception) {
                sendJson(exchange, 400, Map.of("error", exception.getMessage()));
            }
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
            bootstrap.put("appBanner", "15-prerequisite-flags[java]");
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
        exchange.getResponseHeaders().set(
                "Content-Type", resourcePath.endsWith(".html") ? "text/html" : "text/plain");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
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
            sendJson(
                    exchange,
                    200,
                    FlagControls.applyFlagControl(
                            key, turnOn, request.containsKey("fallthrough"), request.get("fallthrough")));
        } catch (IllegalArgumentException exception) {
            sendJson(exchange, 400, Map.of("ok", false, "error", exception.getMessage()));
        } catch (RuntimeException exception) {
            sendJson(exchange, 502, Map.of("ok", false, "error", exception.getMessage()));
        }
    }

    private static void sendJson(HttpExchange exchange, int status, Object value) throws IOException {
        byte[] body = Json.stringify(value).getBytes(StandardCharsets.UTF_8);
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
            if (idx <= 0) {
                continue;
            }
            params.put(
                    URLDecoder.decode(pair.substring(0, idx), StandardCharsets.UTF_8),
                    URLDecoder.decode(pair.substring(idx + 1), StandardCharsets.UTF_8));
        }
        return params;
    }

    private static byte[] readBytes(InputStream stream) throws IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        stream.transferTo(out);
        return out.toByteArray();
    }

    private static int readPort() {
        String raw = System.getenv("PORT");
        if (raw == null || raw.isBlank()) {
            return 8080;
        }
        return Integer.parseInt(raw);
    }
}

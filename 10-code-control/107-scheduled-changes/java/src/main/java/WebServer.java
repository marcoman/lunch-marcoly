import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/** Serve the scheduled-changes grid navigator, SDK evaluation, and REST controls. */
public class WebServer {
    private static final int PORT = readPort();

    public static void main(String[] args) throws IOException {
        ScheduledChange.init();
        Runtime.getRuntime().addShutdownHook(new Thread(ScheduledChange::close));
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("17-scheduled-changes[java]");
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        if ("/api/flags".equals(path)) {
            handleFlags(exchange);
            return;
        }
        if ("/api/schedule".equals(path)) {
            handleSchedule(exchange);
            return;
        }
        if ("/api/bootstrap".equals(path)) {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendJson(exchange, 405, Map.of("error", "Method not allowed"));
                return;
            }
            Map<String, Object> bootstrap = new LinkedHashMap<>();
            bootstrap.put("appBanner", "17-scheduled-changes[java]");
            bootstrap.put("flagKey", ScheduledChange.FLAG_KEY);
            bootstrap.put("controls", ScheduleControls.apiConfig());
            bootstrap.put("port", PORT);
            sendJson(exchange, 200, bootstrap);
            return;
        }
        serveResource(exchange, path);
    }

    private static void handleFlags(HttpExchange exchange) throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            return;
        }
        Map<String, String> params = parseQuery(exchange.getRequestURI().getRawQuery());
        try {
            sendJson(
                    exchange,
                    200,
                    ScheduledChange.evaluate(params.getOrDefault("username", "")));
        } catch (IllegalArgumentException exception) {
            sendJson(exchange, 400, Map.of("error", exception.getMessage()));
        }
    }

    private static void handleSchedule(HttpExchange exchange) throws IOException {
        try {
            switch (exchange.getRequestMethod()) {
                case "GET" -> sendJson(exchange, 200, ScheduleControls.listScheduledChanges());
                case "POST" -> {
                    String raw =
                            new String(readBytes(exchange.getRequestBody()), StandardCharsets.UTF_8);
                    Map<String, Object> request =
                            Json.parseObject(raw.isBlank() ? "{}" : raw);
                    Object value = request.get("minutes");
                    int minutes = value instanceof Number number ? number.intValue() : 0;
                    sendJson(exchange, 201, ScheduleControls.start(minutes));
                }
                case "DELETE" -> sendJson(exchange, 200, ScheduleControls.stop());
                default -> sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            }
        } catch (IllegalArgumentException exception) {
            sendJson(exchange, 400, Map.of("ok", false, "error", exception.getMessage()));
        } catch (RuntimeException exception) {
            sendJson(exchange, 502, Map.of("ok", false, "error", exception.getMessage()));
        }
    }

    private static void serveResource(HttpExchange exchange, String requestedPath)
            throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            return;
        }
        String path = requestedPath;
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
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(body);
            }
            return;
        }
        byte[] body;
        try (InputStream in = stream) {
            body = readBytes(in);
        }
        exchange.getResponseHeaders().set(
                "Content-Type",
                resourcePath.endsWith(".html")
                        ? "text/html; charset=utf-8"
                        : "text/plain; charset=utf-8");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static void sendJson(HttpExchange exchange, int status, Object value)
            throws IOException {
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
        if (query == null || query.isBlank()) return params;
        for (String pair : query.split("&")) {
            int index = pair.indexOf('=');
            if (index <= 0) continue;
            params.put(
                    URLDecoder.decode(pair.substring(0, index), StandardCharsets.UTF_8),
                    URLDecoder.decode(pair.substring(index + 1), StandardCharsets.UTF_8));
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
        return raw == null || raw.isBlank() ? 8172 : Integer.parseInt(raw);
    }
}

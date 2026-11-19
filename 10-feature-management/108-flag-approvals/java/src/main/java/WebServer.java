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

/** Serve the approval lab for the move-count flag.
 *
 * Approvals
 * https://launchdarkly.com/docs/home/releases/approvals
 */
public class WebServer {
    private static final int PORT = readPort();

    public static void main(String[] args) throws IOException {
        FlagCount.init();
        Runtime.getRuntime().addShutdownHook(new Thread(FlagCount::close));
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("108-flag-approvals[java]");
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        try {
            if ("/api/flags".equals(path)) {
                flags(exchange);
                return;
            }
            if ("/api/approval".equals(path) || "/api/approval/apply".equals(path) || "/api/approval/reset".equals(path)) {
                approval(exchange, path);
                return;
            }
        } catch (IllegalArgumentException exception) {
            sendJson(exchange, 400, Map.of("ok", false, "error", exception.getMessage()));
            return;
        } catch (ApprovalFailure exception) {
            Map<String, Object> body = new java.util.LinkedHashMap<>();
            body.put("ok", false);
            body.put("error", exception.getMessage());
            body.put("request", null);
            body.put("steps", exception.steps);
            sendJson(exchange, 502, body);
            return;
        } catch (RuntimeException exception) {
            Map<String, Object> body = new java.util.LinkedHashMap<>();
            body.put("ok", false);
            body.put("error", exception.getMessage());
            if ("GET".equals(exchange.getRequestMethod()) && "/api/approval".equals(path)) {
                body.putAll(Approvals.apiConfig());
                body.put("request", null);
            }
            sendJson(exchange, 502, body);
            return;
        }
        serveResource(exchange, path);
    }

    private static void flags(HttpExchange exchange) throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            return;
        }
        Map<String, String> params = parseQuery(exchange.getRequestURI().getRawQuery());
        sendJson(exchange, 200, FlagCount.evaluate(params.getOrDefault("username", "")));
    }

    private static void approval(HttpExchange exchange, String path) throws IOException {
        String method = exchange.getRequestMethod();
        if ("GET".equals(method) && "/api/approval".equals(path)) {
            sendJson(exchange, 200, Approvals.state());
            return;
        }
        if (!"POST".equals(method)) {
            sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            return;
        }
        String raw = new String(readBytes(exchange.getRequestBody()), StandardCharsets.UTF_8);
        Map<String, Object> request = Json.parseObject(raw.isBlank() ? "{}" : raw);
        if ("/api/approval/apply".equals(path)) {
            sendJson(exchange, 200, Approvals.apply(String.valueOf(request.getOrDefault("id", ""))));
            return;
        }
        if ("/api/approval/reset".equals(path)) {
            sendJson(exchange, 200, Approvals.reset());
            return;
        }
        sendJson(exchange, 200, Approvals.requestApproval());
    }

    private static void serveResource(HttpExchange exchange, String requestedPath) throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            sendJson(exchange, 405, Map.of("error", "Method not allowed"));
            return;
        }
        String path = "/".equals(requestedPath) ? "/public/index.html" : "/public" + requestedPath;
        String resourcePath = path.startsWith("/") ? path.substring(1) : path;
        InputStream stream = WebServer.class.getClassLoader().getResourceAsStream(resourcePath);
        if (stream == null) {
            byte[] missing = "Not found".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(404, missing.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(missing);
            }
            return;
        }
        byte[] body;
        try (InputStream in = stream) {
            body = readBytes(in);
        }
        exchange.getResponseHeaders().set(
                "Content-Type",
                resourcePath.endsWith(".html") ? "text/html; charset=utf-8" : "text/plain; charset=utf-8");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
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
        return raw == null || raw.isBlank() ? 8182 : Integer.parseInt(raw);
    }
}

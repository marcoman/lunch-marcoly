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
 * Serve the guarded-rollout grid navigator web UI on a local HTTP server.
 */
public class WebServer {
    private static final int PORT = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));

    public static void main(String[] args) throws IOException {
        if (args.length >= 2 && "--evaluate-once".equals(args[0])) {
            HighlightEval.init();
            Runtime.getRuntime().addShutdownHook(new Thread(HighlightEval::close));
            HighlightEval.FlagValues result = HighlightEval.evaluate(args[1]);
            System.out.printf(
                    "{\"username\":\"%s\",\"flagValue\":\"%s\",\"highlightColor\":\"%s\",\"colorLabel\":\"%s\"}%n",
                    escapeJson(result.username()),
                    escapeJson(result.flagValue()),
                    escapeJson(result.highlightColor()),
                    escapeJson(result.colorLabel()));
            return;
        }

        HighlightEval.init();
        Runtime.getRuntime().addShutdownHook(new Thread(HighlightEval::close));

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("Grid navigator (create/eval flag) running at http://127.0.0.1:" + PORT + "/");
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        if ("/api/highlight".equals(path)) {
            handleHighlight(exchange);
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

    private static void handleHighlight(HttpExchange exchange) throws IOException {
        Map<String, String> params = parseQuery(exchange.getRequestURI().getRawQuery());
        String username = params.getOrDefault("username", "").trim();
        if (username.isEmpty()) {
            byte[] body = "{\"error\":\"username query parameter is required\"}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", "application/json");
            exchange.sendResponseHeaders(400, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
            return;
        }
        HighlightEval.FlagValues flags = HighlightEval.evaluate(username);
        byte[] body = toJson(flags).getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static String toJson(HighlightEval.FlagValues flags) {
        return "{\"username\":\""
                + escapeJson(flags.username())
                + "\",\"flagValue\":\""
                + escapeJson(flags.flagValue())
                + "\",\"highlightColor\":\""
                + escapeJson(flags.highlightColor())
                + "\",\"colorLabel\":\""
                + escapeJson(flags.colorLabel())
                + "\"}";
    }

    private static String escapeJson(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
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
}

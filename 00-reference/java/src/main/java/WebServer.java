import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/**
 * Serve the grid navigator web UI on a local HTTP server.
 */
public class WebServer {
    private static final int PORT = 8080;

    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.start();
        System.out.println("Grid navigator running at http://127.0.0.1:" + PORT + "/");
        System.out.println("Press Ctrl+C to stop.");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        if ("/".equals(path)) {
            path = "/public/index.html";
        } else if (path.startsWith("/public/")) {
            // already qualified
        } else {
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

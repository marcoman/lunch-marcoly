import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.Components;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.BufferedReader;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Executors;

/**
 * Serve the SDK-fallback lab through a controllable real streaming proxy.
 *
 * LaunchDarkly: every refresh uses stringVariationDetail. The stream gate
 * changes data delivery, not application evaluation logic.
 * https://launchdarkly.com/docs/sdk/features/evaluating
 */
public final class WebServer {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Object CLIENT_LOCK = new Object();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .version(HttpClient.Version.HTTP_1_1)
            .build();

    private static final int PORT = integerEnv("PORT", 8181);
    private static final int GATE_PORT = integerEnv("LD_STREAM_GATE_PORT", 8182);
    private static final double START_WAIT_SECONDS = doubleEnv("LD_START_WAIT", 2);
    private static final String STREAM_ORIGIN =
            trimSlash(env("LD_STREAM_ORIGIN", "https://stream.launchdarkly.com"));
    private static final String POLL_ORIGIN =
            trimSlash(env("LD_POLL_ORIGIN", "https://sdk.launchdarkly.com"));
    private static final String FLAG_KEY = "enable-sdk-fallback-grid-highlight";
    private static final String FLAG_NAME = "Enable: SDK fallback grid highlight";
    private static final String CODE_DEFAULT = "none";
    private static final String LIVE_VALUE = "green";

    private static final StreamGate GATE = new StreamGate();
    private static LDClient client;
    private static String mode = "starting";
    private static boolean everInitialized;
    private static HttpServer appServer;
    private static HttpServer gateServer;

    private WebServer() {
    }

    public static void main(String[] args) throws Exception {
        gateServer = HttpServer.create(new InetSocketAddress("127.0.0.1", GATE_PORT), 0);
        gateServer.createContext("/", WebServer::handleGate);
        gateServer.setExecutor(Executors.newCachedThreadPool());
        gateServer.start();

        if (configured()) {
            Map<String, Object> initial = replaceClient("stream");
            if (!Boolean.TRUE.equals(initial.get("initialized"))) {
                System.err.println("Warning: SDK did not initialize; use Connect stream to retry.");
            }
        } else {
            System.err.println("Warning: LD_SDK_KEY is unset; evaluations use none.");
        }

        appServer = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        appServer.createContext("/", WebServer::handleApp);
        appServer.setExecutor(Executors.newCachedThreadPool());
        appServer.start();
        Runtime.getRuntime().addShutdownHook(new Thread(WebServer::closeAll));

        System.out.println("18-sdk-fallbacks[java]");
        System.out.println("Flag: " + FLAG_NAME + " (" + FLAG_KEY + "); code default: " + CODE_DEFAULT);
        System.out.println("Stream gate: http://127.0.0.1:" + GATE_PORT + " → " + STREAM_ORIGIN);
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
    }

    /**
     * Proxy the SDK stream using chunked output; active streams are closable by
     * the Drop stream control and Authorization is never logged.
     */
    private static void handleGate(HttpExchange exchange) throws IOException {
        if (!GATE.allowed()) {
            sendText(exchange, 503, "stream gate closed", "text/plain; charset=utf-8");
            return;
        }

        ActiveStream active = null;
        try {
            URI requestUri = exchange.getRequestURI();
            HttpRequest.Builder request = HttpRequest.newBuilder(
                    URI.create(STREAM_ORIGIN + requestUri.toString()))
                    .GET();
            copyHeader(exchange, request, "Authorization");
            copyHeader(exchange, request, "Accept");
            copyHeader(exchange, request, "User-Agent");
            copyHeader(exchange, request, "X-LaunchDarkly-Event-Schema");
            copyHeader(exchange, request, "X-LaunchDarkly-Wrapper");

            HttpResponse<InputStream> response = HTTP.send(
                    request.build(), HttpResponse.BodyHandlers.ofInputStream());
            if (response.statusCode() >= 400) {
                response.body().close();
                sendText(exchange, response.statusCode(), "upstream stream error",
                        "text/plain; charset=utf-8");
                return;
            }

            exchange.getResponseHeaders().set(
                    "Content-Type",
                    response.headers().firstValue("Content-Type").orElse("text/event-stream"));
            exchange.getResponseHeaders().set("Cache-Control", "no-cache");
            exchange.sendResponseHeaders(response.statusCode(), 0);
            active = new ActiveStream(response.body(), exchange.getResponseBody());
            if (!GATE.register(active)) {
                active.close();
                return;
            }
            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(active.input, StandardCharsets.UTF_8));
            String line;
            while (GATE.allowed() && (line = reader.readLine()) != null) {
                active.output.write(line.getBytes(StandardCharsets.UTF_8));
                active.output.write('\n');
                active.output.flush();
            }
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
        } catch (IOException | RuntimeException ignored) {
            // A severed stream is the expected lab action.
        } finally {
            if (active != null) {
                GATE.unregister(active);
                active.close();
            } else {
                exchange.close();
            }
        }
    }

    private static void handleApp(HttpExchange exchange) throws IOException {
        try {
            String path = exchange.getRequestURI().getPath();
            String method = exchange.getRequestMethod();
            if (path.startsWith("/api/")) {
                if ("GET".equals(method) && "/api/config".equals(path)) {
                    Map<String, Object> body = new LinkedHashMap<>();
                    body.put("runtime", "18-sdk-fallbacks[java]");
                    body.put("flag", Map.of("key", FLAG_KEY, "name", FLAG_NAME));
                    body.put("codeDefault", CODE_DEFAULT);
                    body.putAll(status());
                    sendJson(exchange, 200, body);
                    return;
                }
                if ("GET".equals(method) && "/api/status".equals(path)) {
                    sendJson(exchange, 200, status());
                    return;
                }
                if ("GET".equals(method) && "/api/evaluate".equals(path)) {
                    String username = parseQuery(exchange.getRequestURI().getRawQuery())
                            .getOrDefault("username", "").trim();
                    if (username.isEmpty()) throw new ApiException(400,
                            "username query parameter is required");
                    sendJson(exchange, 200, evaluate(username));
                    return;
                }
                if ("POST".equals(method) && "/api/connect".equals(path)) {
                    sendJson(exchange, 200, replaceClient("stream"));
                    return;
                }
                if ("POST".equals(method) && "/api/drop-stream".equals(path)) {
                    sendJson(exchange, 200, dropStream());
                    return;
                }
                if ("POST".equals(method) && "/api/block-init".equals(path)) {
                    sendJson(exchange, 200, replaceClient("default"));
                    return;
                }
                throw new ApiException(404, "Not found");
            }

            if (!"/".equals(path) && !"/index.html".equals(path)) {
                sendText(exchange, 404, "Not found", "text/plain; charset=utf-8");
                return;
            }
            try (InputStream input = WebServer.class.getClassLoader()
                    .getResourceAsStream("public/index.html")) {
                if (input == null) {
                    sendText(exchange, 404, "Not found", "text/plain; charset=utf-8");
                    return;
                }
                sendBytes(exchange, 200, input.readAllBytes(), "text/html; charset=utf-8");
            }
        } catch (ApiException exception) {
            sendJson(exchange, exception.status, Map.of("error", exception.getMessage()));
        } catch (Exception exception) {
            sendJson(exchange, 500, Map.of("error", String.valueOf(exception.getMessage())));
        }
    }

    /**
     * Build a client with a loopback streaming endpoint and bounded start wait.
     */
    private static LDClient makeClient() {
        String sdkKey = env("LD_SDK_KEY", "").trim();
        if (sdkKey.isEmpty()) throw new ApiException(503,
                "LD_SDK_KEY is required for this lab.");
        LDConfig config = new LDConfig.Builder()
                .serviceEndpoints(Components.serviceEndpoints()
                        .streaming("http://127.0.0.1:" + GATE_PORT)
                        .polling(POLL_ORIGIN))
                .events(Components.noEvents())
                .diagnosticOptOut(true)
                .dataSource(Components.streamingDataSource()
                        .initialReconnectDelay(Duration.ofMillis(500)))
                .startWait(Duration.ofMillis((long) (START_WAIT_SECONDS * 1000)))
                .build();
        return new LDClient(sdkKey, config);
    }

    private static Map<String, Object> replaceClient(String nextMode) {
        if ("stream".equals(nextMode)) GATE.open();
        else if ("default".equals(nextMode)) GATE.drop();
        else throw new ApiException(400, "Unknown mode: " + nextMode);

        LDClient previous;
        synchronized (CLIENT_LOCK) {
            previous = client;
            client = null;
            mode = nextMode;
            everInitialized = false;
        }
        closeClient(previous);
        LDClient next = makeClient();
        synchronized (CLIENT_LOCK) {
            client = next;
            everInitialized = next.isInitialized();
        }
        return status();
    }

    private static Map<String, Object> dropStream() {
        synchronized (CLIENT_LOCK) {
            if (client == null || !client.isInitialized()) {
                throw new ApiException(409,
                        "Connect and initialize the stream before dropping it.");
            }
            everInitialized = true;
            mode = "last-known";
        }
        GATE.drop();
        return status();
    }

    private static String source() {
        if ("last-known".equals(mode)) return "LAST_KNOWN";
        if ("stream".equals(mode) && client != null && client.isInitialized()) return "STREAM";
        return "DEFAULT";
    }

    private static Map<String, Object> status() {
        synchronized (CLIENT_LOCK) {
            boolean initialized = client != null && client.isInitialized();
            if (initialized) everInitialized = true;
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("mode", mode);
            body.put("source", source());
            body.put("initialized", initialized);
            body.put("everInitialized", everInitialized);
            body.put("gateOpen", GATE.allowed());
            body.put("activeStreams", GATE.count());
            body.put("startWaitSeconds", START_WAIT_SECONDS);
            body.put("configured", configured());
            return body;
        }
    }

    /**
     * Evaluate the same string variation and code default in every mode.
     */
    private static Map<String, Object> evaluate(String username) {
        synchronized (CLIENT_LOCK) {
            Map<String, Object> body = new LinkedHashMap<>();
            if (client == null) {
                body.put("flagValue", CODE_DEFAULT);
                body.put("highlightColor", CODE_DEFAULT);
                body.put("reason", Map.of(
                        "kind", "ERROR", "errorKind", "CLIENT_NOT_READY"));
            } else {
                LDContext context = LDContext.builder(username).kind("user").build();
                EvaluationDetail<String> detail =
                        client.stringVariationDetail(FLAG_KEY, context, CODE_DEFAULT);
                String value = Set.of(CODE_DEFAULT, LIVE_VALUE).contains(detail.getValue())
                        ? detail.getValue() : CODE_DEFAULT;
                body.put("flagValue", value);
                body.put("highlightColor", value);
                body.put("reason", reasonPayload(detail.getReason()));
            }
            body.putAll(status());
            return body;
        }
    }

    private static Map<String, Object> reasonPayload(EvaluationReason reason) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", reason.getKind().toString());
        if (reason.getKind() == EvaluationReason.Kind.RULE_MATCH) {
            payload.put("ruleIndex", reason.getRuleIndex());
            if (reason.getRuleId() != null) payload.put("ruleId", reason.getRuleId());
        }
        if (reason.getKind() == EvaluationReason.Kind.PREREQUISITE_FAILED
                && reason.getPrerequisiteKey() != null) {
            payload.put("prerequisiteKey", reason.getPrerequisiteKey());
        }
        if (reason.getKind() == EvaluationReason.Kind.ERROR && reason.getErrorKind() != null) {
            payload.put("errorKind", reason.getErrorKind().toString());
        }
        return payload;
    }

    private static void closeAll() {
        GATE.drop();
        if (appServer != null) appServer.stop(0);
        if (gateServer != null) gateServer.stop(0);
        synchronized (CLIENT_LOCK) {
            closeClient(client);
            client = null;
        }
    }

    private static void closeClient(LDClient target) {
        if (target == null) return;
        try {
            target.close();
        } catch (IOException ignored) {
        }
    }

    private static void copyHeader(
            HttpExchange exchange, HttpRequest.Builder request, String name) {
        String value = exchange.getRequestHeaders().getFirst(name);
        if (value != null) request.header(name, value);
    }

    private static void sendJson(HttpExchange exchange, int status, Object body)
            throws IOException {
        sendBytes(exchange, status, JSON.writeValueAsBytes(body),
                "application/json; charset=utf-8");
    }

    private static void sendText(
            HttpExchange exchange, int status, String body, String contentType)
            throws IOException {
        sendBytes(exchange, status, body.getBytes(StandardCharsets.UTF_8), contentType);
    }

    private static void sendBytes(
            HttpExchange exchange, int status, byte[] body, String contentType)
            throws IOException {
        exchange.getResponseHeaders().set("Content-Type", contentType);
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        exchange.sendResponseHeaders(status, body.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(body);
        }
    }

    private static Map<String, String> parseQuery(String query) {
        Map<String, String> values = new LinkedHashMap<>();
        if (query == null || query.isBlank()) return values;
        for (String pair : query.split("&")) {
            int separator = pair.indexOf('=');
            if (separator < 0) continue;
            values.put(
                    URLDecoder.decode(pair.substring(0, separator), StandardCharsets.UTF_8),
                    URLDecoder.decode(pair.substring(separator + 1), StandardCharsets.UTF_8));
        }
        return values;
    }

    private static boolean configured() {
        return !env("LD_SDK_KEY", "").trim().isEmpty();
    }

    private static String env(String key, String fallback) {
        return System.getenv().getOrDefault(key, fallback);
    }

    private static int integerEnv(String key, int fallback) {
        try {
            return Integer.parseInt(env(key, String.valueOf(fallback)));
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static double doubleEnv(String key, double fallback) {
        try {
            return Double.parseDouble(env(key, String.valueOf(fallback)));
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static String trimSlash(String value) {
        return value.replaceAll("/+$", "");
    }

    private static final class ActiveStream {
        private final InputStream input;
        private final OutputStream output;

        private ActiveStream(InputStream input, OutputStream output) {
            this.input = input;
            this.output = output;
        }

        private void close() {
            try {
                input.close();
            } catch (IOException ignored) {
            }
            try {
                output.close();
            } catch (IOException ignored) {
            }
        }
    }

    private static final class StreamGate {
        private boolean open = true;
        private final List<ActiveStream> active = new ArrayList<>();

        synchronized boolean allowed() {
            return open;
        }

        synchronized void open() {
            open = true;
        }

        void drop() {
            List<ActiveStream> streams;
            synchronized (this) {
                open = false;
                streams = new ArrayList<>(active);
                active.clear();
            }
            streams.forEach(ActiveStream::close);
        }

        synchronized boolean register(ActiveStream stream) {
            if (!open) return false;
            active.add(stream);
            return true;
        }

        synchronized void unregister(ActiveStream stream) {
            active.remove(stream);
        }

        synchronized int count() {
            return active.size();
        }
    }

    private static final class ApiException extends RuntimeException {
        private final int status;

        private ApiException(int status, String message) {
            super(message);
            this.status = status;
        }
    }
}

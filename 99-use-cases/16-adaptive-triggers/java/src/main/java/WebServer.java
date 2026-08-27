import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;

/**
 * Serve the adaptive-trigger grid and keep every privileged operation on the
 * Java host.
 *
 * LaunchDarkly: server-side variation, numeric custom track, audit log, and
 * semantic-patch targeting updates.
 * https://launchdarkly.com/docs/home/flags/triggers
 * https://launchdarkly.com/docs/sdk/features/events
 */
public final class WebServer {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private static final int PORT = Integer.parseInt(env("PORT", "8161"));
    private static final String FLAG_NAME = "Enable: adaptive grid highlight";
    private static final String METRIC_KEY = "adaptive-grid-nav-latency-metric";
    private static final int THRESHOLD_MS = 200;
    private static final String LIVE_VALUE = "green";
    private static final String API_HOST = trimTrailingSlash(env("LD_API_HOST", "https://app.launchdarkly.com"));
    private static final String APP_HOST = trimTrailingSlash(env("LD_APP_HOST", API_HOST));

    private static volatile String cachedSdkEnvironmentKey;

    private WebServer() {
    }

    public static void main(String[] args) throws IOException {
        HighlightEval.init();
        Runtime.getRuntime().addShutdownHook(new Thread(HighlightEval::close));

        if (args.length >= 2 && "--evaluate-once".equals(args[0])) {
            HighlightEval.FlagValues result = HighlightEval.evaluate(args[1]);
            System.out.println(JSON.writeValueAsString(highlightJson(result)));
            HighlightEval.close();
            return;
        }

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.createContext("/", WebServer::handle);
        server.setExecutor(Executors.newCachedThreadPool());
        server.start();
        System.out.println("16-adaptive-triggers[java]");
        System.out.println("Flag: " + FLAG_NAME + " (" + HighlightEval.FLAG_HIGHLIGHT + ")");
        System.out.println("Metric event key: " + HighlightEval.EVENT_KEY + " — threshold " + THRESHOLD_MS + " ms");
        System.out.println("Open http://127.0.0.1:" + PORT + "/");
    }

    private static void handle(HttpExchange exchange) throws IOException {
        try {
            if (exchange.getRequestURI().getPath().startsWith("/api/")) {
                handleApi(exchange);
            } else {
                serveStatic(exchange);
            }
        } catch (ApiException exception) {
            sendError(exchange, exception.status, exception.getMessage());
        } catch (Exception exception) {
            sendError(exchange, 500, String.valueOf(exception.getMessage()));
        }
    }

    private static void handleApi(HttpExchange exchange) throws Exception {
        String path = exchange.getRequestURI().getPath();
        String method = exchange.getRequestMethod();

        if ("/api/config".equals(path) && "GET".equals(method)) {
            sendJson(exchange, 200, configResponse());
            return;
        }
        if ("/api/highlight".equals(path) && "GET".equals(method)) {
            String username = parseQuery(exchange.getRequestURI().getRawQuery())
                    .getOrDefault("username", "")
                    .trim();
            if (username.isEmpty()) {
                throw new ApiException(400, "username query parameter is required");
            }
            sendJson(exchange, 200, highlightJson(HighlightEval.evaluate(username)));
            return;
        }
        if ("/api/status".equals(path) && "GET".equals(method)) {
            sendJson(exchange, 200, getStatus());
            return;
        }
        if ("/api/start-live".equals(path) && "POST".equals(method)) {
            sendJson(exchange, 200, startLive());
            return;
        }
        if ("/api/stop".equals(path) && "POST".equals(method)) {
            sendJson(exchange, 200, stopLive());
            return;
        }
        if ("/api/track-latency".equals(path) && "POST".equals(method)) {
            JsonNode body = JSON.readTree(exchange.getRequestBody());
            String username = body == null ? "" : body.path("username").asText("").trim();
            JsonNode latencyNode = body == null ? null : body.get("latencyMs");
            double latencyMs = latencyNode == null ? Double.NaN : latencyNode.asDouble(Double.NaN);
            sendJson(exchange, 200, trackLatency(username, latencyMs));
            return;
        }
        throw new ApiException(404, "Not found");
    }

    /**
     * Return public identifiers and dashboard links while retaining REST and
     * SDK credentials exclusively on the server.
     */
    private static ObjectNode configResponse() {
        ApiConfig config = apiConfig();
        ObjectNode response = JSON.createObjectNode();
        response.set("controls", config.toJson());
        response.set("flag", JSON.createObjectNode()
                .put("key", HighlightEval.FLAG_HIGHLIGHT)
                .put("name", FLAG_NAME));
        response.put("metricKey", METRIC_KEY);
        response.put("eventKey", HighlightEval.EVENT_KEY);
        response.put("thresholdMs", THRESHOLD_MS);
        putNullable(response, "links", dashboardLinks(config.projectKey, config.environmentKey));
        return response;
    }

    /**
     * Read flag targeting plus best-effort environment and audit diagnostics.
     * LaunchDarkly: feature flag REST representation and audit log attribution.
     * https://launchdarkly.com/docs/api/audit-log/get-audit-log-entries
     */
    private static ObjectNode getStatus() throws Exception {
        ApiConfig config = apiConfig();
        ObjectNode result = config.toJson();
        putNullable(result, "links", dashboardLinks(config.projectKey, config.environmentKey));
        ObjectNode sdk = JSON.createObjectNode();
        sdk.put("initialized", HighlightEval.isInitialized());
        sdk.putNull("environmentKey");
        sdk.putNull("matchesRestEnvironment");
        result.set("sdk", sdk);

        if (!config.configured()) {
            result.putNull("flag");
            return result;
        }

        JsonNode flag = ldApi(
                "/flags/" + segment(config.projectKey) + "/" + segment(HighlightEval.FLAG_HIGHLIGHT),
                "GET",
                null,
                null);
        JsonNode targeting = flag.path("environments").get(config.environmentKey);
        JsonNode fallthroughIndex = targeting == null ? null : targeting.path("fallthrough").get("variation");

        JsonNode lastChange = null;
        try {
            String sdkEnvironment = resolveSdkEnvironmentKey();
            if (sdkEnvironment != null) {
                sdk.put("environmentKey", sdkEnvironment);
                sdk.put("matchesRestEnvironment", sdkEnvironment.equals(config.environmentKey));
            }
            lastChange = fetchLastChange(config);
        } catch (Exception ignored) {
            // Diagnostics are best effort and must never block flag status.
        }

        putNullable(result, "lastChange", lastChange);
        ObjectNode flagStatus = JSON.createObjectNode();
        flagStatus.put("key", HighlightEval.FLAG_HIGHLIGHT);
        flagStatus.put("name", flag.path("name").asText(FLAG_NAME));
        if (targeting == null || !targeting.has("on")) {
            flagStatus.putNull("on");
        } else {
            flagStatus.put("on", targeting.path("on").asBoolean());
        }
        if (fallthroughIndex != null && fallthroughIndex.isIntegralNumber()) {
            JsonNode value = flag.path("variations").path(fallthroughIndex.asInt()).get("value");
            putNullable(flagStatus, "fallthrough", value);
        } else {
            flagStatus.putNull("fallthrough");
        }
        result.set("flag", flagStatus);
        return result;
    }

    /**
     * Start the live behavior by turning targeting on and setting the default
     * rule to the green variation via LaunchDarkly semantic patch.
     */
    private static ObjectNode startLive() throws Exception {
        ApiConfig config = requireApiConfig();
        String flagPath = "/flags/" + segment(config.projectKey) + "/" + segment(HighlightEval.FLAG_HIGHLIGHT);
        JsonNode flag = ldApi(flagPath, "GET", null, null);
        String variationId = null;
        for (JsonNode variation : flag.path("variations")) {
            if (LIVE_VALUE.equals(variation.path("value").asText())) {
                variationId = variation.path("_id").asText(null);
                break;
            }
        }
        if (variationId == null) {
            throw new ApiException(409,
                    "Flag " + HighlightEval.FLAG_HIGHLIGHT + " has no " + LIVE_VALUE + " variation.");
        }

        ObjectNode body = JSON.createObjectNode();
        body.put("environmentKey", config.environmentKey);
        body.put("comment", "16-adaptive-triggers: start live from lab control");
        ArrayNode instructions = body.putArray("instructions");
        instructions.addObject().put("kind", "turnFlagOn");
        instructions.addObject()
                .put("kind", "updateFallthroughVariationOrRollout")
                .put("variationId", variationId);
        ldApi(flagPath, "PATCH", body,
                "application/json; domain-model=launchdarkly.semanticpatch");
        return getStatus();
    }

    /**
     * Return to the provisioned state by turning targeting off. The adaptive
     * trigger remains configured in LaunchDarkly for the next run.
     */
    private static ObjectNode stopLive() throws Exception {
        ApiConfig config = requireApiConfig();
        String flagPath = "/flags/" + segment(config.projectKey) + "/" + segment(HighlightEval.FLAG_HIGHLIGHT);
        ObjectNode body = JSON.createObjectNode();
        body.put("environmentKey", config.environmentKey);
        body.put("comment", "16-adaptive-triggers: stop from lab control");
        body.putArray("instructions").addObject().put("kind", "turnFlagOff");
        ldApi(flagPath, "PATCH", body,
                "application/json; domain-model=launchdarkly.semanticpatch");
        return getStatus();
    }

    /**
     * Validate and emit the slider value as a numeric custom metric. These
     * track calls, rather than flag evaluations, feed the adaptive trigger.
     */
    private static ObjectNode trackLatency(String username, double latencyMs) {
        if (!HighlightEval.isInitialized()) {
            throw new ApiException(503, "LD_SDK_KEY is missing or the SDK did not initialize.");
        }
        if (username.isEmpty() || !Double.isFinite(latencyMs) || latencyMs < 0 || latencyMs > 500) {
            throw new ApiException(400, "username and latencyMs (0–500) are required.");
        }
        HighlightEval.trackLatency(username, latencyMs);
        ObjectNode response = JSON.createObjectNode();
        response.put("tracked", true);
        response.put("eventKey", HighlightEval.EVENT_KEY);
        putNumber(response, "latencyMs", latencyMs);
        response.put("aboveThreshold", latencyMs > THRESHOLD_MS);
        return response;
    }

    /**
     * Resolve which environment owns LD_SDK_KEY. Adaptive triggers only consume
     * metric events from their own environment, so a mismatch is otherwise silent.
     */
    private static String resolveSdkEnvironmentKey() throws Exception {
        if (cachedSdkEnvironmentKey != null) {
            return cachedSdkEnvironmentKey;
        }
        String sdkKey = env("LD_SDK_KEY", "").trim();
        ApiConfig config = apiConfig();
        if (sdkKey.isEmpty() || !config.configured()) {
            return null;
        }
        JsonNode body = ldApi(
                "/projects/" + segment(config.projectKey) + "/environments?limit=100",
                "GET",
                null,
                null);
        for (JsonNode environment : body.path("items")) {
            if (sdkKey.equals(environment.path("apiKey").asText())) {
                cachedSdkEnvironmentKey = environment.path("key").asText();
                return cachedSdkEnvironmentKey;
            }
        }
        return null;
    }

    private static JsonNode fetchLastChange(ApiConfig config) throws Exception {
        String spec = "proj/" + config.projectKey + ":env/" + config.environmentKey
                + ":flag/" + HighlightEval.FLAG_HIGHLIGHT;
        JsonNode body = ldApi("/auditlog?spec=" + query(spec) + "&limit=1", "GET", null, null);
        JsonNode entry = body.path("items").path(0);
        if (entry.isMissingNode()) {
            return null;
        }
        String actor = textOrNull(entry.path("member").get("email"));
        if (actor == null) {
            actor = textOrNull(entry.path("token").get("name"));
        }
        String rawSummary = entry.path("description").asText(entry.path("titleVerb").asText(""));
        String summary = rawSummary.replaceAll("[*~`]", "").lines()
                .map(String::trim)
                .filter(line -> !line.isEmpty())
                .reduce((left, right) -> left + "; " + right)
                .orElse("");

        ObjectNode change = JSON.createObjectNode();
        putNullable(change, "date", entry.get("date"));
        if (actor == null) {
            change.putNull("actor");
        } else {
            change.put("actor", actor);
        }
        change.put("summary", summary);
        change.put("byAutomation", actor == null);
        return change;
    }

    /**
     * Build dashboard deep links for the flag targeting, monitoring, metric,
     * and environment pages without exposing the API access token.
     */
    private static ObjectNode dashboardLinks(String projectKey, String environmentKey) {
        if (projectKey == null || projectKey.isEmpty()) {
            return null;
        }
        String envQuery = environmentKey == null || environmentKey.isEmpty()
                ? ""
                : "?env=" + query(environmentKey) + "&selected-env=" + query(environmentKey);
        String flagBase = APP_HOST + "/projects/" + segment(projectKey)
                + "/flags/" + segment(HighlightEval.FLAG_HIGHLIGHT);
        ObjectNode links = JSON.createObjectNode();
        links.put("flagTargeting", flagBase + envQuery);
        links.put("flagMonitoring", flagBase + "/monitoring" + envQuery);
        links.put("metric", APP_HOST + "/projects/" + segment(projectKey) + "/metrics/" + segment(METRIC_KEY));
        links.put("environments", APP_HOST + "/projects/" + segment(projectKey) + "/settings/environments");
        return links;
    }

    /**
     * Call the LaunchDarkly REST API using only server-side credentials.
     * LaunchDarkly: API versioning and semantic patch request bodies.
     */
    private static JsonNode ldApi(
            String path,
            String method,
            JsonNode body,
            String contentType) throws Exception {
        ApiConfig config = requireApiConfig();
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(API_HOST + "/api/v2" + path))
                .timeout(Duration.ofSeconds(20))
                .header("Authorization", env("LD_API_ACCESS_TOKEN", ""))
                .header("LD-API-Version", "20240415")
                .header("Content-Type", contentType == null ? "application/json" : contentType);
        String payload = body == null ? "" : JSON.writeValueAsString(body);
        request.method(method, body == null
                ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8));
        HttpResponse<String> response = HTTP.send(
                request.build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        JsonNode responseBody;
        try {
            responseBody = response.body().isBlank()
                    ? JSON.createObjectNode()
                    : JSON.readTree(response.body());
        } catch (Exception ignored) {
            responseBody = JSON.createObjectNode();
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            String message = responseBody.path("message")
                    .asText("LaunchDarkly API returned " + response.statusCode());
            throw new ApiException(response.statusCode(), message);
        }
        return responseBody;
    }

    private static ApiConfig apiConfig() {
        String token = env("LD_API_ACCESS_TOKEN", "").trim();
        String project = env("LD_PROJECT_KEY", "").trim();
        String environment = env("LD_ENVIRONMENT_KEY", "").trim();
        List<String> missing = new ArrayList<>();
        if (token.isEmpty()) missing.add("LD_API_ACCESS_TOKEN");
        if (project.isEmpty()) missing.add("LD_PROJECT_KEY");
        if (environment.isEmpty()) missing.add("LD_ENVIRONMENT_KEY");
        return new ApiConfig(missing, emptyToNull(project), emptyToNull(environment));
    }

    private static ApiConfig requireApiConfig() {
        ApiConfig config = apiConfig();
        if (!config.configured()) {
            throw new ApiException(
                    503,
                    "This control needs " + String.join(", ", config.missing) + " on the Java host.");
        }
        return config;
    }

    private static void serveStatic(HttpExchange exchange) throws IOException {
        String path = exchange.getRequestURI().getPath();
        if ("/".equals(path)) {
            path = "/index.html";
        }
        if (path.contains("..")) {
            sendText(exchange, 403, "Forbidden", "text/plain; charset=utf-8");
            return;
        }
        String resourcePath = "public" + path;
        InputStream stream = WebServer.class.getClassLoader().getResourceAsStream(resourcePath);
        if (stream == null) {
            sendText(exchange, 404, "Not found", "text/plain; charset=utf-8");
            return;
        }
        byte[] bytes;
        try (stream) {
            bytes = stream.readAllBytes();
        }
        String contentType = resourcePath.endsWith(".html")
                ? "text/html; charset=utf-8"
                : "text/plain; charset=utf-8";
        sendBytes(exchange, 200, bytes, contentType, false);
    }

    private static void sendJson(HttpExchange exchange, int status, JsonNode body) throws IOException {
        sendBytes(
                exchange,
                status,
                JSON.writeValueAsBytes(body),
                "application/json; charset=utf-8",
                true);
    }

    private static void sendError(HttpExchange exchange, int status, String message) throws IOException {
        sendJson(exchange, status, JSON.createObjectNode().put("error", message == null ? "null" : message));
    }

    private static void sendText(
            HttpExchange exchange,
            int status,
            String body,
            String contentType) throws IOException {
        sendBytes(exchange, status, body.getBytes(StandardCharsets.UTF_8), contentType, false);
    }

    private static void sendBytes(
            HttpExchange exchange,
            int status,
            byte[] body,
            String contentType,
            boolean noStore) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", contentType);
        if (noStore) {
            exchange.getResponseHeaders().set("Cache-Control", "no-store");
        }
        exchange.sendResponseHeaders(status, body.length);
        try (OutputStream output = exchange.getResponseBody()) {
            output.write(body);
        }
    }

    private static ObjectNode highlightJson(HighlightEval.FlagValues result) {
        ObjectNode json = JSON.createObjectNode();
        json.put("username", result.username());
        json.put("flagValue", result.flagValue());
        json.put("highlightColor", result.highlightColor());
        json.put("colorLabel", result.colorLabel());
        return json;
    }

    private static Map<String, String> parseQuery(String rawQuery) {
        java.util.HashMap<String, String> values = new java.util.HashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) {
            return values;
        }
        for (String pair : rawQuery.split("&")) {
            int separator = pair.indexOf('=');
            if (separator <= 0) continue;
            values.put(
                    URLDecoder.decode(pair.substring(0, separator), StandardCharsets.UTF_8),
                    URLDecoder.decode(pair.substring(separator + 1), StandardCharsets.UTF_8));
        }
        return values;
    }

    private static void putNullable(ObjectNode object, String field, JsonNode value) {
        if (value == null || value.isMissingNode()) {
            object.putNull(field);
        } else {
            object.set(field, value);
        }
    }

    private static void putNumber(ObjectNode object, String field, double value) {
        if (value == Math.rint(value) && value >= Long.MIN_VALUE && value <= Long.MAX_VALUE) {
            object.put(field, (long) value);
        } else {
            object.put(field, value);
        }
    }

    private static String textOrNull(JsonNode node) {
        return node == null || node.isNull() || node.isMissingNode() ? null : node.asText();
    }

    private static String env(String key, String fallback) {
        return System.getenv().getOrDefault(key, fallback);
    }

    private static String emptyToNull(String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private static String trimTrailingSlash(String value) {
        return value.replaceAll("/+$", "");
    }

    private static String segment(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static String query(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private record ApiConfig(List<String> missing, String projectKey, String environmentKey) {
        boolean configured() {
            return missing.isEmpty();
        }

        ObjectNode toJson() {
            ObjectNode json = JSON.createObjectNode();
            json.put("configured", configured());
            ArrayNode missingJson = json.putArray("missing");
            missing.forEach(missingJson::add);
            if (projectKey == null) json.putNull("projectKey");
            else json.put("projectKey", projectKey);
            if (environmentKey == null) json.putNull("environmentKey");
            else json.put("environmentKey", environmentKey);
            return json;
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

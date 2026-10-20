import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Control LaunchDarkly scheduled changes for this lesson's dedicated flag.
 * Scheduled changes API: https://launchdarkly.com/docs/api/scheduled-changes
 */
final class ScheduleControls {
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();
    private static final String API_VERSION = env("LD_API_VERSION", "20240415");

    private ScheduleControls() {
    }

    static Map<String, Object> apiConfig() {
        List<String> missing = new ArrayList<>();
        if (env("LD_API_ACCESS_TOKEN", "").isBlank()) missing.add("LD_API_ACCESS_TOKEN");
        if (env("LD_PROJECT_KEY", "").isBlank()) missing.add("LD_PROJECT_KEY");
        if (env("LD_ENVIRONMENT_KEY", "").isBlank()) missing.add("LD_ENVIRONMENT_KEY");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("configured", missing.isEmpty());
        result.put("missing", missing);
        result.put("projectKey", blankToNull(env("LD_PROJECT_KEY", "")));
        result.put("environmentKey", blankToNull(env("LD_ENVIRONMENT_KEY", "")));
        result.put("apiHost", env("LD_API_HOST", "https://app.launchdarkly.com"));
        return result;
    }

    static Map<String, Object> listScheduledChanges() {
        Map<String, Object> result = new LinkedHashMap<>(apiConfig());
        if (!Boolean.TRUE.equals(result.get("configured"))) {
            result.put("items", List.of());
            return result;
        }
        List<Map<String, Object>> items = objectList(request("GET", basePath(), null, false).get("items"));
        items.sort(Comparator.comparingLong(item -> longValue(item.get("executionDate"))));
        result.put("items", items.stream().map(ScheduleControls::summarize).toList());
        return result;
    }

    /**
     * Replace pending schedules, turn the flag off now, then schedule turnFlagOn.
     */
    static Map<String, Object> start(int minutes) {
        if (minutes < 1 || minutes > 60) {
            throw new IllegalArgumentException("minutes must be between 1 and 60");
        }
        int deleted = deletePendingChanges();
        turnFlagOff("17-scheduled-changes: reset off before starting demo");

        long now = System.currentTimeMillis();
        long executionDate = now + minutes * 60_000L;
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("executionDate", executionDate);
        body.put("instructions", List.of(Map.of("kind", "turnFlagOn")));
        body.put(
                "comment",
                "17-scheduled-changes: turn highlight on after " + minutes + " minute(s)");
        Map<String, Object> created = request("POST", basePath(), body, false);

        Map<String, Object> scheduled = summarize(created);
        scheduled.putIfAbsent("createdAt", now);
        scheduled.putIfAbsent("executionDate", executionDate);
        if (!(scheduled.get("instructions") instanceof List<?> list) || list.isEmpty()) {
            scheduled.put("instructions", List.of(Map.of("kind", "turnFlagOn")));
        }
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", true);
        result.put("replacedCount", deleted);
        result.put("minutes", minutes);
        result.put("startedAt", now);
        result.put("scheduledChange", scheduled);
        return result;
    }

    /**
     * Delete pending changes and turn the flag off so neither state can re-enable it.
     */
    static Map<String, Object> stop() {
        int cancelled = deletePendingChanges();
        turnFlagOff("17-scheduled-changes: stop demo and turn highlight off");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", true);
        result.put("cancelledCount", cancelled);
        result.put("stoppedAt", System.currentTimeMillis());
        return result;
    }

    private static int deletePendingChanges() {
        int deleted = 0;
        for (Map<String, Object> item :
                objectList(request("GET", basePath(), null, false).get("items"))) {
            Object id = item.get("_id");
            if (id != null && !id.toString().isBlank()) {
                request("DELETE", basePath() + "/" + encode(id.toString()), null, false);
                deleted++;
            }
        }
        return deleted;
    }

    private static void turnFlagOff(String comment) {
        Map<String, Object> config = requireConfig();
        String path = "/flags/" + encode((String) config.get("projectKey"))
                + "/" + encode(ScheduledChange.FLAG_KEY);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("environmentKey", config.get("environmentKey"));
        body.put("comment", comment);
        body.put("instructions", List.of(Map.of("kind", "turnFlagOff")));
        request("PATCH", path, body, true);
    }

    private static String basePath() {
        Map<String, Object> config = requireConfig();
        return "/projects/" + encode((String) config.get("projectKey"))
                + "/flags/" + encode(ScheduledChange.FLAG_KEY)
                + "/environments/" + encode((String) config.get("environmentKey"))
                + "/scheduled-changes";
    }

    private static Map<String, Object> requireConfig() {
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            @SuppressWarnings("unchecked")
            List<String> missing = (List<String>) config.get("missing");
            throw new IllegalStateException(
                    "Scheduled changes need " + String.join(", ", missing));
        }
        return config;
    }

    /**
     * Scheduled POSTs use ordinary JSON; only feature-flag PATCHes use semanticpatch.
     */
    private static Map<String, Object> request(
            String method, String path, Map<String, Object> body, boolean semanticPatch) {
        Map<String, Object> config = requireConfig();
        String host = ((String) config.get("apiHost")).replaceAll("/+$", "");
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(host + "/api/v2" + path))
                .timeout(Duration.ofSeconds(30))
                .header("Authorization", env("LD_API_ACCESS_TOKEN", "").trim())
                .header("LD-API-Version", API_VERSION)
                .header("Accept", "application/json");
        if (body == null) {
            builder.method(method, HttpRequest.BodyPublishers.noBody());
        } else {
            builder.header(
                    "Content-Type",
                    semanticPatch
                            ? "application/json; domain-model=launchdarkly.semanticpatch"
                            : "application/json");
            builder.method(method, HttpRequest.BodyPublishers.ofString(Json.stringify(body)));
        }
        try {
            HttpResponse<String> response = HTTP.send(
                    builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            Object parsed =
                    response.body().isBlank() ? new LinkedHashMap<>() : Json.parse(response.body());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                String message = response.body();
                if (parsed instanceof Map<?, ?> map && map.get("message") != null) {
                    message = String.valueOf(map.get("message"));
                }
                throw new IllegalStateException(
                        "LaunchDarkly API " + response.statusCode() + ": " + message);
            }
            return object(parsed);
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "LaunchDarkly API request failed: " + exception.getMessage(), exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("LaunchDarkly API request interrupted", exception);
        }
    }

    private static Map<String, Object> summarize(Map<String, Object> item) {
        Map<String, Object> result = new LinkedHashMap<>();
        if (item.get("_id") != null) result.put("id", item.get("_id"));
        if (item.get("_creationDate") != null) result.put("createdAt", item.get("_creationDate"));
        if (item.get("executionDate") != null) result.put("executionDate", item.get("executionDate"));
        result.put("instructions", item.get("instructions") instanceof List<?> value ? value : List.of());
        return result;
    }

    private static long longValue(Object value) {
        return value instanceof Number number ? number.longValue() : 0L;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> object(Object value) {
        return value instanceof Map<?, ?> ? (Map<String, Object>) value : new LinkedHashMap<>();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> objectList(Object value) {
        return value instanceof List<?> ? (List<Map<String, Object>>) value : new ArrayList<>();
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String blankToNull(String value) {
        return value.isBlank() ? null : value;
    }
}

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
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

/**
 * REST controls for the two 15-prerequisite-flags keys.
 * Never edits the prerequisite relationship.
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */
final class FlagControls {
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();
    private static final String API_VERSION = env("LD_API_VERSION", "20240415");
    private static final List<Map<String, String>> CONTROLLED_FLAGS = List.of(
            metadata(
                    Prerequisite.FLAG_HIGHLIGHT,
                    "Parent · grid selection highlight",
                    "15-prerequisite-flags parent (cites 11's enable-grid-selection-highlight). Must be on and serving green."),
            metadata(
                    Prerequisite.FLAG_COUNT,
                    "Child · navigation move count",
                    "15-prerequisite-flags child (cites 11's show-navigation-move-count). Unmet prerequisite serves its off variation."));
    private static final Set<String> ALLOWED = Set.of(
            Prerequisite.FLAG_HIGHLIGHT, Prerequisite.FLAG_COUNT);

    private FlagControls() {
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

    static Map<String, Object> listFlagControls() {
        Map<String, Object> config = apiConfig();
        List<Map<String, Object>> flags = new ArrayList<>();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            for (Map<String, String> metadata : CONTROLLED_FLAGS) {
                Map<String, Object> item = new LinkedHashMap<>(metadata);
                item.put("on", null);
                item.put("targetingHint", "Set missing environment variables.");
                flags.add(item);
            }
            config.put("flags", flags);
            return config;
        }
        String project = (String) config.get("projectKey");
        String environment = (String) config.get("environmentKey");
        String query = "?env=" + encode(environment);
        List<Map<String, String>> errors = new ArrayList<>();
        for (Map<String, String> metadata : CONTROLLED_FLAGS) {
            String key = metadata.get("key");
            try {
                Map<String, Object> flag = request(
                        "GET", "/flags/" + encode(project) + "/" + encode(key) + query, null);
                flags.add(summarize(flag, environment, metadata));
            } catch (RuntimeException exception) {
                errors.add(Map.of("key", key, "error", exception.getMessage()));
                Map<String, Object> item = new LinkedHashMap<>(metadata);
                item.put("on", null);
                item.put("targetingHint", exception.getMessage());
                item.put("error", exception.getMessage());
                flags.add(item);
            }
        }
        config.put("flags", flags);
        config.put("errors", errors);
        return config;
    }

    static Map<String, Object> applyFlagControl(
            String flagKey, Boolean turnOn, boolean hasFallthrough, Object fallthrough) {
        if (!ALLOWED.contains(flagKey)) {
            throw new IllegalArgumentException("Flag key not allowed for controls: " + flagKey);
        }
        if (turnOn == null && !hasFallthrough) {
            throw new IllegalArgumentException("Provide \"on\" and/or \"fallthrough\"");
        }
        if (hasFallthrough && !Prerequisite.FLAG_HIGHLIGHT.equals(flagKey)) {
            throw new IllegalArgumentException("Only the parent highlight flag has color variations");
        }
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            @SuppressWarnings("unchecked")
            List<String> missing = (List<String>) config.get("missing");
            throw new IllegalStateException("Flag controls need " + String.join(", ", missing));
        }
        String project = (String) config.get("projectKey");
        String environment = (String) config.get("environmentKey");
        String flagPath = "/flags/" + encode(project) + "/" + encode(flagKey);
        String query = "?env=" + encode(environment);
        Map<String, Object> flag = request("GET", flagPath + query, null);
        List<Map<String, Object>> instructions = new ArrayList<>();
        if (Boolean.TRUE.equals(turnOn)) {
            instructions.add(instruction("turnFlagOn"));
        } else if (Boolean.FALSE.equals(turnOn)) {
            instructions.add(instruction("turnFlagOff"));
        }
        if (hasFallthrough) {
            Object wanted = fallthrough instanceof String text ? text.trim() : fallthrough;
            String variationId = variationId(flag, wanted);
            if (variationId == null) {
                throw new IllegalArgumentException("No variation matching fallthrough=" + wanted);
            }
            Map<String, Object> patch = instruction("updateFallthroughVariationOrRollout");
            patch.put("variationId", variationId);
            instructions.add(patch);
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("environmentKey", environment);
        body.put("comment", "15-prerequisite-flags UI control");
        body.put("instructions", instructions);
        request("PATCH", flagPath, body);
        flag = request("GET", flagPath + query, null);
        Map<String, String> metadata = CONTROLLED_FLAGS.stream()
                .filter(item -> flagKey.equals(item.get("key")))
                .findFirst()
                .orElseThrow();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", true);
        result.put("instructions", instructions.stream().map(item -> item.get("kind")).toList());
        result.put("projectKey", project);
        result.put("environmentKey", environment);
        result.put("flag", summarize(flag, environment, metadata));
        return result;
    }

    private static Map<String, Object> request(String method, String path, Map<String, Object> body) {
        Map<String, Object> config = apiConfig();
        String host = ((String) config.get("apiHost")).replaceAll("/+$", "");
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(host + "/api/v2" + path))
                .timeout(Duration.ofSeconds(30))
                .header("Authorization", env("LD_API_ACCESS_TOKEN", "").trim())
                .header("LD-API-Version", API_VERSION)
                .header("Accept", "application/json");
        if (body == null) {
            builder.method(method, HttpRequest.BodyPublishers.noBody());
        } else {
            builder.header("Content-Type", "application/json; domain-model=launchdarkly.semanticpatch");
            builder.method(method, HttpRequest.BodyPublishers.ofString(Json.stringify(body)));
        }
        try {
            HttpResponse<String> response = HTTP.send(
                    builder.build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            Object parsed = response.body().isBlank() ? new LinkedHashMap<>() : Json.parse(response.body());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                String message = response.body();
                if (parsed instanceof Map<?, ?> map && map.get("message") != null) {
                    message = String.valueOf(map.get("message"));
                }
                throw new IllegalStateException("LaunchDarkly API " + response.statusCode() + ": " + message);
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> object = parsed instanceof Map<?, ?> ? (Map<String, Object>) parsed : Map.of();
            return object;
        } catch (IOException exception) {
            throw new IllegalStateException("LaunchDarkly API request failed: " + exception.getMessage(), exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("LaunchDarkly API request interrupted", exception);
        }
    }

    private static Map<String, Object> summarize(
            Map<String, Object> flag, String environmentKey, Map<String, String> metadata) {
        Map<String, Object> environment = object(object(flag.get("environments")).get(environmentKey));
        List<Map<String, Object>> variations = objectList(flag.get("variations"));
        List<Object> values = variations.stream().map(item -> item.get("value")).toList();
        List<Map<String, Object>> prerequisites = objectList(environment.get("prerequisites"));
        Map<String, Object> prerequisite = prerequisites.isEmpty() ? null : prerequisites.get(0);
        Integer fallIndex = integer(object(environment.get("fallthrough")).get("variation"));
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("key", metadata.get("key"));
        result.put("label", metadata.get("label"));
        result.put("summary", metadata.get("summary"));
        result.put("on", Boolean.TRUE.equals(environment.get("on")));
        result.put(
                "variationKind",
                values.stream().allMatch(String.class::isInstance) ? "string" : "boolean");
        result.put(
                "colorOptions",
                metadata.get("key").equals(Prerequisite.FLAG_HIGHLIGHT)
                        ? values.stream()
                                .filter(value -> value instanceof String text
                                        && Prerequisite.VALID_COLORS.contains(text))
                                .toList()
                        : List.of());
        result.put("servedWhenOff", variationValue(variations, integer(environment.get("offVariation"))));
        result.put("servedWhenOnFallthrough", variationValue(variations, fallIndex));
        result.put("prerequisite", prerequisite);
        result.put(
                "prerequisiteConfigured",
                !metadata.get("key").equals(Prerequisite.FLAG_COUNT)
                        || (prerequisite != null
                                && Prerequisite.FLAG_HIGHLIGHT.equals(prerequisite.get("key"))));
        result.put(
                "targetingHint",
                metadata.get("key").equals(Prerequisite.FLAG_HIGHLIGHT)
                        ? "Required by child: parent must be ON and serve green."
                        : (prerequisite == null
                                ? "Missing prerequisite — run this example's provisioning."
                                : "Prerequisite configured; lab controls leave it unchanged."));
        return result;
    }

    private static String variationId(Map<String, Object> flag, Object wanted) {
        for (Map<String, Object> variation : objectList(flag.get("variations"))) {
            if (java.util.Objects.equals(wanted, variation.get("value"))) {
                Object id = variation.get("_id") != null ? variation.get("_id") : variation.get("id");
                return id == null ? null : id.toString();
            }
        }
        return null;
    }

    private static Object variationValue(List<Map<String, Object>> variations, Integer index) {
        return index == null || index < 0 || index >= variations.size()
                ? null
                : variations.get(index).get("value");
    }

    private static Map<String, String> metadata(String key, String label, String summary) {
        return Map.of("key", key, "label", label, "summary", summary);
    }

    private static Map<String, Object> instruction(String kind) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("kind", kind);
        return result;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> object(Object value) {
        return value instanceof Map<?, ?> ? (Map<String, Object>) value : new LinkedHashMap<>();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> objectList(Object value) {
        return value instanceof List<?> ? (List<Map<String, Object>>) value : List.of();
    }

    private static Integer integer(Object value) {
        return value instanceof Number number ? number.intValue() : null;
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

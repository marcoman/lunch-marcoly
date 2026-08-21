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

/**
 * REST controls for the targeting-rules lab's single string flag.
 *
 * LaunchDarkly feature flags — semantic patch:
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */
final class FlagControls {
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();
    private static final String API_VERSION = env("LD_API_VERSION", "20240415");
    private static final List<Map<String, String>> CONTROLLED_FLAGS = List.of(
            metadata(
                    TeamStyle.FLAG_KEY,
                    "Configure team label style",
                    "String style selected by provisioned targeting rules on public team."));

    private FlagControls() {
    }

    static Map<String, Object> apiConfig() {
        String token = env("LD_API_ACCESS_TOKEN", "").trim();
        String project = env("LD_PROJECT_KEY", "").trim();
        String environment = env("LD_ENVIRONMENT_KEY", "").trim();
        List<String> missing = new ArrayList<>();
        if (token.isEmpty()) missing.add("LD_API_ACCESS_TOKEN");
        if (project.isEmpty()) missing.add("LD_PROJECT_KEY");
        if (environment.isEmpty()) missing.add("LD_ENVIRONMENT_KEY");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("configured", missing.isEmpty());
        result.put("missing", missing);
        result.put("projectKey", project.isEmpty() ? null : project);
        result.put("environmentKey", environment.isEmpty() ? null : environment);
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
                item.put("targetingHint", "Set missing env vars to enable controls.");
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
                flags.add(summarizeFlag(flag, environment, metadata));
            } catch (RuntimeException exception) {
                Map<String, String> error = Map.of("key", key, "error", exception.getMessage());
                errors.add(error);
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
        if (!TeamStyle.FLAG_KEY.equals(flagKey)) {
            throw new IllegalArgumentException("Flag key not allowed for controls: " + flagKey);
        }
        if (turnOn == null && !hasFallthrough) {
            throw new IllegalArgumentException("Provide \"on\" and/or \"fallthrough\"");
        }
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            @SuppressWarnings("unchecked")
            List<String> missing = (List<String>) config.get("missing");
            throw new IllegalStateException(
                    "Flag controls need " + String.join(", ", missing) + " in the server environment.");
        }

        String project = (String) config.get("projectKey");
        String environment = (String) config.get("environmentKey");
        String flagPath = "/flags/" + encode(project) + "/" + encode(flagKey);
        String query = "?env=" + encode(environment);
        Map<String, Object> flag = request("GET", flagPath + query, null);
        List<Map<String, Object>> instructions = new ArrayList<>();
        List<String> actions = new ArrayList<>();

        if (Boolean.TRUE.equals(turnOn)) {
            instructions.add(instruction("turnFlagOn"));
            actions.add("turnFlagOn");
        } else if (Boolean.FALSE.equals(turnOn)) {
            instructions.add(instruction("turnFlagOff"));
            actions.add("turnFlagOff");
        }

        if (hasFallthrough) {
            Object wanted = normalizeFallthrough(fallthrough);
            Map<String, Object> instruction = fallthroughInstruction(flag, wanted);
            if (instruction == null && !Boolean.FALSE.equals(turnOn)) {
                throw new IllegalArgumentException(
                        "No variation matching fallthrough=" + Json.stringify(wanted) + " on " + flagKey);
            }
            if (instruction != null) {
                instructions.add(instruction);
                actions.add("updateFallthrough");
            }
        }

        String action = actions.isEmpty() ? "noop" : String.join("+", actions);
        Map<String, Object> patch = new LinkedHashMap<>();
        patch.put("environmentKey", environment);
        patch.put("comment", "13-flag-targeting-rules UI: on/off or fallthrough");
        patch.put("instructions", instructions);
        request("PATCH", flagPath, patch);

        flag = request("GET", flagPath + query, null);
        Map<String, String> metadata = CONTROLLED_FLAGS.stream()
                .filter(item -> flagKey.equals(item.get("key")))
                .findFirst()
                .orElseThrow();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("ok", true);
        result.put("action", action);
        result.put("instructions", instructions.stream().map(item -> item.get("kind")).toList());
        result.put("projectKey", project);
        result.put("environmentKey", environment);
        result.put("flag", summarizeFlag(flag, environment, metadata));
        return result;
    }

    private static Map<String, Object> request(
            String method, String path, Map<String, Object> body) {
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            throw new IllegalStateException("LaunchDarkly REST controls are not configured.");
        }
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
                    "PATCH".equals(method)
                            ? "application/json; domain-model=launchdarkly.semanticpatch"
                            : "application/json");
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
                throw new IllegalStateException(
                        "LaunchDarkly API " + response.statusCode() + ": " + message);
            }
            if (!(parsed instanceof Map<?, ?>)) {
                throw new IllegalStateException("LaunchDarkly API returned non-object JSON");
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> object = (Map<String, Object>) parsed;
            return object;
        } catch (IOException exception) {
            throw new IllegalStateException("LaunchDarkly API request failed: " + exception.getMessage(), exception);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("LaunchDarkly API request interrupted", exception);
        }
    }

    private static Map<String, Object> summarizeFlag(
            Map<String, Object> flag, String environmentKey, Map<String, String> metadata) {
        Map<String, Object> environments = object(flag.get("environments"));
        Map<String, Object> environment = object(environments.get(environmentKey));
        boolean on = Boolean.TRUE.equals(environment.get("on"));
        Integer offIndex = integer(environment.get("offVariation"));
        Integer fallthroughIndex = integer(object(environment.get("fallthrough")).get("variation"));
        List<Map<String, Object>> sourceVariations = objectList(flag.get("variations"));
        String kind = variationKind(sourceVariations);
        List<Map<String, Object>> variations = new ArrayList<>();
        List<Map<String, Object>> options = new ArrayList<>();
        for (int index = 0; index < sourceVariations.size(); index++) {
            Map<String, Object> source = sourceVariations.get(index);
            Object value = source.get("value");
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("index", index);
            item.put("value", value);
            item.put("name", string(source.get("name")));
            item.put("description", string(source.get("description")));
            item.put("token", optionToken(value));
            variations.add(item);
            if (!"boolean".equals(kind)) {
                Map<String, Object> option = new LinkedHashMap<>();
                option.put("token", item.get("token"));
                option.put("label", string(source.get("name")).isEmpty() ? item.get("token") : source.get("name"));
                option.put("value", value);
                options.add(option);
            }
        }

        Object offValue = variationValue(sourceVariations, offIndex);
        Object fallthroughValue = variationValue(sourceVariations, fallthroughIndex);
        List<Object> rules = list(environment.get("rules"));
        List<Object> targets = list(environment.get("targets"));
        List<Object> contextTargets = list(environment.get("contextTargets"));
        String hint = rules.size()
                + " provisioned rules remain unchanged; this lab controls only flag state and fallthrough.";

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("key", flag.getOrDefault("key", metadata.get("key")));
        result.put("name", flag.getOrDefault("name", metadata.get("label")));
        result.put("label", metadata.get("label"));
        result.put("summary", metadata.get("summary"));
        result.put("on", on);
        result.put("variationKind", kind);
        result.put("fallthroughOptions", options);
        result.put("fallthroughToken", fallthroughValue == null ? null : optionToken(fallthroughValue));
        result.put("variations", variations);
        result.put("offVariation", offIndex);
        result.put("fallthroughVariation", fallthroughIndex);
        result.put("servedWhenOff", offValue);
        result.put("servedWhenOnFallthrough", fallthroughValue);
        result.put("ruleCount", rules.size());
        result.put("targetCount", targets.size() + contextTargets.size());
        result.put("targetingHint", hint);
        return result;
    }

    private static Map<String, Object> fallthroughInstruction(
            Map<String, Object> flag, Object wanted) {
        for (Map<String, Object> variation : objectList(flag.get("variations"))) {
            if (!valuesEqual(variation.get("value"), wanted)) continue;
            Object id = variation.get("_id") != null ? variation.get("_id") : variation.get("id");
            if (id != null && !id.toString().isBlank()) {
                Map<String, Object> result = instruction("updateFallthroughVariationOrRollout");
                result.put("variationId", id.toString());
                return result;
            }
        }
        return null;
    }

    private static boolean valuesEqual(Object left, Object right) {
        if (left == null || right == null) return left == right;
        if (left.equals(right)) return true;
        if (left instanceof Number leftNumber && right instanceof Number rightNumber) {
            return Double.compare(leftNumber.doubleValue(), rightNumber.doubleValue()) == 0;
        }
        if ((left instanceof Number || left instanceof String)
                && (right instanceof Number || right instanceof String)) {
            try {
                return Double.compare(
                        Double.parseDouble(left.toString()), Double.parseDouble(right.toString())) == 0;
            } catch (NumberFormatException ignored) {
                return left.toString().trim().equals(right.toString().trim());
            }
        }
        return false;
    }

    private static Object normalizeFallthrough(Object raw) {
        if (!(raw instanceof String text)) return raw;
        text = text.trim();
        if (text.isEmpty()) return text;
        try {
            return Json.parse(text);
        } catch (IllegalArgumentException ignored) {
            return text;
        }
    }

    private static String variationKind(List<Map<String, Object>> variations) {
        if (variations.isEmpty()) return "other";
        List<Object> values = variations.stream().map(item -> item.get("value")).toList();
        if (values.stream().allMatch(Boolean.class::isInstance)) return "boolean";
        if (values.stream().allMatch(String.class::isInstance)) return "string";
        if (values.stream().allMatch(Number.class::isInstance)) return "number";
        if (values.stream().allMatch(value -> value instanceof Map<?, ?> || value instanceof List<?>)) {
            return "json";
        }
        return "other";
    }

    private static String optionToken(Object value) {
        return value instanceof Map<?, ?> || value instanceof List<?>
                ? Json.stringify(value)
                : String.valueOf(value);
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

    @SuppressWarnings("unchecked")
    private static List<Object> list(Object value) {
        return value instanceof List<?> ? (List<Object>) value : List.of();
    }

    private static Integer integer(Object value) {
        return value instanceof Number number ? number.intValue() : null;
    }

    private static String string(Object value) {
        return value == null ? "" : value.toString();
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null || value.isBlank() ? fallback : value;
    }
}

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Approval request for the move-count flag.
 *
 * Approvals
 * https://launchdarkly.com/docs/home/releases/approvals
 *
 * Create an approval request for a flag
 * https://launchdarkly.com/docs/api/approvals/post-approval-request-for-a-flag
 */
final class Approvals {
    static final String FLAG_KEY = FlagCount.FLAG_KEY;
    private static final String DESCRIPTION = "Turn on the move count";
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();

    private Approvals() {
    }

    static Map<String, Object> apiConfig() {
        String token = env("LD_API_ACCESS_TOKEN");
        String project = env("LD_PROJECT_KEY");
        String environment = env("LD_ENVIRONMENT_KEY");
        List<String> missing = new ArrayList<>();
        if (token.isEmpty()) missing.add("LD_API_ACCESS_TOKEN");
        if (project.isEmpty()) missing.add("LD_PROJECT_KEY");
        if (environment.isEmpty()) missing.add("LD_ENVIRONMENT_KEY");
        Map<String, Object> config = new LinkedHashMap<>();
        config.put("configured", missing.isEmpty());
        config.put("missing", missing);
        config.put("projectKey", project.isEmpty() ? null : project);
        config.put("environmentKey", environment.isEmpty() ? null : environment);
        config.put("flagKey", FLAG_KEY);
        config.put("appOrigin", host());
        return config;
    }

    static Map<String, Object> state() {
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            config.put("ok", true);
            config.put("request", null);
            return config;
        }
        Object payload = request("GET", flagPath(config), null, false);
        List<Map<String, Object>> items = items(payload);
        config.put("ok", true);
        config.put("request", current(items));
        return config;
    }

    /** LaunchDarkly: approval request · semantic patch turnFlagOn */
    static Map<String, Object> requestApproval() {
        Map<String, Object> current = state();
        Map<String, Object> existing = mapOrEmpty(current.get("request"));
        if (!existing.isEmpty()
                && !"declined".equals(existing.get("reviewStatus"))
                && !Boolean.TRUE.equals(existing.get("applied"))) {
            current.put("steps", List.of(step(
                    "Lab API",
                    "Open request reused. LaunchDarkly was not asked for a second one.")));
            return current;
        }
        String description = nextDescription();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("description", description);
        body.put("comment", "108-flag-approvals");
        body.put("instructions", List.of(Map.of("kind", "turnFlagOn")));
        Object created = request("POST", flagPath(apiConfig()), body, true);
        Map<String, Object> row = summary(asMap(created));
        Map<String, Object> result = apiConfig();
        result.put("ok", true);
        result.put("request", row);
        result.put("steps", List.of(step(
                "LaunchDarkly",
                "POST approval-requests · turnFlagOn · " + description + " · review " + row.get("reviewStatus"))));
        return result;
    }

    /** LaunchDarkly: apply approval request */
    static Map<String, Object> apply(String requestId) {
        String id = requestId == null ? "" : requestId.trim();
        if (id.isEmpty()) throw new IllegalArgumentException("Approval id is required");
        Map<String, Object> config = apiConfig();
        Object applied = request(
                "POST",
                flagPath(config) + "/" + encode(id) + "/apply",
                Map.of("comment", "108-flag-approvals apply"),
                false);
        Map<String, Object> row = summary(asMap(applied));
        config.put("ok", true);
        config.put("request", row);
        config.put("steps", List.of(step(
                "LaunchDarkly",
                "POST approval-requests/" + id + "/apply · status " + row.get("status"))));
        return config;
    }

    /** Delete approval requests for this flag and turn the flag off. */
    static Map<String, Object> reset() {
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            throw new IllegalStateException("Approvals need " + String.join(", ", missing(config)) + ".");
        }
        List<Map<String, Object>> steps = new ArrayList<>();
        Map<String, Map<String, Object>> found = new LinkedHashMap<>();
        for (Map<String, Object> item : items(request("GET", flagPath(config), null, false))) {
            Object id = item.get("_id");
            if (id != null) found.put(String.valueOf(id), item);
        }
        String resource = "proj/" + config.get("projectKey") + ":env/" + config.get("environmentKey") + ":flag/" + FLAG_KEY;
        try {
            for (Map<String, Object> item : items(request(
                    "GET",
                    "/approval-requests?limit=20&filter=" + encode("resourceId equals " + resource),
                    null,
                    false))) {
                Object id = item.get("_id");
                if (id != null) found.put(String.valueOf(id), item);
            }
        } catch (RuntimeException ignored) {
            // The flag list is enough when the account list is unavailable.
        }
        List<Map<String, Object>> items = new ArrayList<>(found.values());
        if (items.isEmpty()) {
            steps.add(step("LaunchDarkly", "GET approval-requests · none to delete"));
        }
        for (Map<String, Object> item : items) {
            Object id = item.get("_id");
            if (id == null || String.valueOf(id).isBlank()) continue;
            String requestId = String.valueOf(id);
            try {
                request("DELETE", flagPath(config) + "/" + encode(requestId), null, false);
                steps.add(step("LaunchDarkly", "DELETE approval-requests/" + requestId));
            } catch (RuntimeException exception) {
                steps.add(step("LaunchDarkly", "DELETE approval-requests/" + requestId + " · " + exception.getMessage()));
            }
        }
        Object patched;
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("environmentKey", config.get("environmentKey"));
            body.put("comment", "108-flag-approvals reset");
            body.put("instructions", List.of(Map.of("kind", "turnFlagOff")));
            patched = request("PATCH", "/flags/" + encode(String.valueOf(config.get("projectKey"))) + "/" + encode(FLAG_KEY), body, true);
        } catch (RuntimeException exception) {
            throw new ApprovalFailure(exception.getMessage(), steps);
        }
        Object on = null;
        if (patched instanceof Map<?, ?> map && map.get("environments") instanceof Map<?, ?> environments) {
            Object environment = environments.get(config.get("environmentKey"));
            if (environment instanceof Map<?, ?> env) on = env.get("on");
        }
        steps.add(step("LaunchDarkly", "PATCH flag · turnFlagOff · on " + on));
        config.put("ok", true);
        config.put("request", null);
        config.put("steps", steps);
        return config;
    }

    private static Map<String, Object> step(String where, String text) {
        Map<String, Object> step = new LinkedHashMap<>();
        step.put("where", where);
        step.put("text", text);
        return step;
    }

    private static Object request(String method, String path, Map<String, Object> body, boolean semantic) {
        Map<String, Object> config = apiConfig();
        if (!Boolean.TRUE.equals(config.get("configured"))) {
            throw new IllegalStateException("Approvals need " + String.join(", ", missing(config)) + ".");
        }
        String type = semantic
                ? "application/json; domain-model=launchdarkly.semanticpatch"
                : "application/json";
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(host() + "/api/v2" + path))
                .timeout(Duration.ofSeconds(30))
                .header("Authorization", env("LD_API_ACCESS_TOKEN"))
                .header("LD-API-Version", version())
                .header("Accept", "application/json");
        if (body == null) {
            builder.method(method, HttpRequest.BodyPublishers.noBody());
        } else {
            builder.header("Content-Type", type);
            builder.method(method, HttpRequest.BodyPublishers.ofString(Json.stringify(body)));
        }
        try {
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                String detail = response.body() == null ? "" : response.body();
                if (detail.length() > 300) detail = detail.substring(0, 300);
                throw new IllegalStateException("LaunchDarkly " + response.statusCode() + ": " + detail);
            }
            if (response.body() == null || response.body().isBlank()) return Map.of();
            return Json.parse(response.body());
        } catch (IllegalStateException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalStateException(exception.getMessage(), exception);
        }
    }

    private static Map<String, Object> summary(Map<String, Object> item) {
        boolean applied = item.get("appliedDate") != null || "completed".equals(item.get("status"));
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", item.get("_id"));
        row.put("reviewStatus", item.getOrDefault("reviewStatus", "pending"));
        row.put("status", item.getOrDefault("status", "pending"));
        row.put("applied", applied);
        row.put("description", item.getOrDefault("description", DESCRIPTION));
        return row;
    }

    private static Map<String, Object> current(List<Map<String, Object>> items) {
        List<Map<String, Object>> ranked = new ArrayList<>();
        for (Map<String, Object> item : items) {
            Map<String, Object> row = summary(item);
            row.put("creationDate", number(item.get("creationDate")));
            if (Boolean.TRUE.equals(row.get("applied"))) continue;
            String status = String.valueOf(row.get("status"));
            if ("completed".equals(status) || "failed".equals(status)) continue;
            ranked.add(row);
        }
        ranked.sort(Comparator.comparingLong((Map<String, Object> row) -> number(row.get("creationDate"))).reversed());
        for (Map<String, Object> row : ranked) {
            if (!"declined".equals(row.get("reviewStatus"))) {
                row.remove("creationDate");
                return row;
            }
        }
        if (ranked.isEmpty()) return null;
        ranked.get(0).remove("creationDate");
        return ranked.get(0);
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> items(Object payload) {
        if (!(payload instanceof Map<?, ?> map) || !(map.get("items") instanceof List<?> list)) return List.of();
        List<Map<String, Object>> items = new ArrayList<>();
        for (Object item : list) {
            if (item instanceof Map<?, ?> row) items.add((Map<String, Object>) row);
        }
        return items;
    }

    /** Next approval name. `.request-count` is shared with Python, Node, and .NET. */
    private static String nextDescription() {
        Path root = exampleRoot();
        Path counter = root.resolve(".request-count");
        Path lock = root.resolve(".request-count.lock");
        long deadline = System.nanoTime() + 2_000_000_000L;
        while (true) {
            try {
                Files.writeString(lock, "", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
                break;
            } catch (FileAlreadyExistsException exists) {
                if (System.nanoTime() <= deadline) {
                    try {
                        Thread.sleep(50);
                    } catch (InterruptedException interrupted) {
                        Thread.currentThread().interrupt();
                        throw new IllegalStateException("Approval counter is locked.");
                    }
                    continue;
                }
                try {
                    if (Files.getLastModifiedTime(lock).toMillis() < System.currentTimeMillis() - 5000) {
                        Files.deleteIfExists(lock);
                        continue;
                    }
                } catch (IOException ignored) {
                    continue;
                }
                throw new IllegalStateException("Approval counter is locked.");
            } catch (IOException failure) {
                throw new IllegalStateException("Approval counter could not be locked.", failure);
            }
        }
        try {
            int current = 0;
            if (Files.isRegularFile(counter)) {
                String raw = Files.readString(counter).trim();
                if (raw.matches("\\d+")) current = Integer.parseInt(raw);
            }
            int next = current + 1;
            Path temporary = root.resolve(".request-count.tmp");
            Files.writeString(temporary, next + "\n");
            try {
                Files.move(temporary, counter, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            } catch (java.nio.file.AtomicMoveNotSupportedException unsupported) {
                Files.move(temporary, counter, StandardCopyOption.REPLACE_EXISTING);
            }
            return DESCRIPTION + " · " + next;
        } catch (IOException failure) {
            throw new IllegalStateException("Approval counter could not be updated.", failure);
        } finally {
            try {
                Files.deleteIfExists(lock);
            } catch (IOException ignored) {
                // The next caller treats a leftover lock as stale after a few seconds.
            }
        }
    }

    private static Path exampleRoot() {
        List<Path> starts = new ArrayList<>();
        starts.add(Path.of("").toAbsolutePath());
        try {
            java.net.URL location = Approvals.class.getProtectionDomain().getCodeSource().getLocation();
            if (location != null) starts.add(Path.of(location.toURI()));
        } catch (Exception ignored) {
            // user.dir is enough when the process was started in this example.
        }
        for (Path start : starts) {
            for (Path dir = start; dir != null; dir = dir.getParent()) {
                if (Files.isRegularFile(dir.resolve("approvals.py")) && Files.isDirectory(dir.resolve("python"))) {
                    return dir;
                }
            }
        }
        throw new IllegalStateException("Approval counter directory was not found.");
    }

    private static String flagPath(Map<String, Object> config) {
        return "/projects/" + encode(String.valueOf(config.get("projectKey")))
                + "/flags/" + encode(FLAG_KEY)
                + "/environments/" + encode(String.valueOf(config.get("environmentKey")))
                + "/approval-requests";
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) return (Map<String, Object>) map;
        return Map.of();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> mapOrEmpty(Object value) {
        if (value instanceof Map<?, ?> map) return (Map<String, Object>) map;
        return Map.of();
    }

    @SuppressWarnings("unchecked")
    private static List<String> missing(Map<String, Object> config) {
        Object value = config.get("missing");
        if (value instanceof List<?> list) return (List<String>) list;
        return List.of();
    }

    private static long number(Object value) {
        return value instanceof Number number ? number.longValue() : 0L;
    }

    private static String env(String name) {
        String value = System.getenv(name);
        return value == null ? "" : value.trim();
    }

    private static String host() {
        String value = env("LD_API_HOST");
        if (value.isEmpty()) value = "https://app.launchdarkly.com";
        while (value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value;
    }

    private static String version() {
        String value = env("LD_API_VERSION");
        return value.isEmpty() ? "20240415" : value;
    }

    private static String encode(String value) {
        return java.net.URLEncoder.encode(value, java.nio.charset.StandardCharsets.UTF_8).replace("+", "%20");
    }
}

/** Reset deleted requests, then the flag-off patch failed. */
final class ApprovalFailure extends RuntimeException {
    final List<Map<String, Object>> steps;

    ApprovalFailure(String message, List<Map<String, Object>> steps) {
        super(message);
        this.steps = steps;
    }
}

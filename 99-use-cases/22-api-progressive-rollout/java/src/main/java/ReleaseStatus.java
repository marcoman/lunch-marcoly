import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * Read and start the progressive environment release for this example.
 *
 * LaunchDarkly: environment releases — kind progressive
 * https://launchdarkly.com/docs/api/environment-releases
 */
public final class ReleaseStatus {
    private static final int ALLOCATION_SCALE = 1000;
    private static final int[] ROLLOUT_PERCENTAGES = {10, 20, 40, 60, 100};
    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

    private ReleaseStatus() {
    }

    static int stageSeconds() {
        String raw = System.getenv("STAGE_SECONDS");
        if (raw == null || raw.isBlank()) {
            return 60;
        }
        try {
            return Integer.parseInt(raw.trim());
        } catch (NumberFormatException err) {
            return 60;
        }
    }

    static String host() {
        String raw = System.getenv().getOrDefault("LD_API_HOST", "https://app.launchdarkly.com");
        return raw.endsWith("/") ? raw.substring(0, raw.length() - 1) : raw;
    }

    static JsonArray schedule() {
        JsonArray steps = new JsonArray();
        for (int percent : ROLLOUT_PERCENTAGES) {
            JsonObject step = new JsonObject();
            step.addProperty("percent", percent);
            step.addProperty("durationSeconds", stageSeconds());
            steps.add(step);
        }
        return steps;
    }

    static String targetingUrl() {
        String project = env("LD_PROJECT_KEY");
        String environment = env("LD_ENVIRONMENT_KEY");
        if (project.isEmpty() || environment.isEmpty()) {
            return null;
        }
        return host()
                + "/projects/" + project
                + "/flags/" + HighlightEval.FLAG_HIGHLIGHT
                + "/targeting?env=" + environment
                + "&selected-env=" + environment;
    }

    /** Start the progressive release. Header LD-API-Version: beta. */
    static JsonObject start() {
        // https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        String flagPath = "/api/v2/flags/" + env("LD_PROJECT_KEY") + "/" + HighlightEval.FLAG_HIGHLIGHT;
        Reply flagReply = request("GET", flagPath, null, flagApiVersion(), "application/json");
        if (flagReply.status == 404) {
            return error("Flag not found. Run rest/create-flag.sh, then start again.", flagReply.status, null);
        }
        if (flagReply.status != 200 || !flagReply.body.isJsonObject()) {
            return apiError(flagReply);
        }
        JsonObject flag = flagReply.body.getAsJsonObject();
        String noneId = variationId(flag, "none");
        String greenId = variationId(flag, "green");
        if (noneId == null || greenId == null) {
            return error("The flag is missing the none or green variation.", null, null);
        }
        JsonArray instructions = removePhaseRules(flag);
        JsonObject turnOn = new JsonObject();
        turnOn.addProperty("kind", "turnFlagOn");
        JsonObject fallthrough = new JsonObject();
        fallthrough.addProperty("kind", "updateFallthroughVariationOrRollout");
        fallthrough.addProperty("variationId", noneId);
        instructions.add(turnOn);
        instructions.add(fallthrough);
        JsonObject patch = new JsonObject();
        patch.addProperty("environmentKey", env("LD_ENVIRONMENT_KEY"));
        patch.addProperty("comment", "22-api-progressive-rollout: on, default rule stays none");
        patch.add("instructions", instructions);
        Reply patched = request(
                "PATCH",
                flagPath,
                patch,
                flagApiVersion(),
                "application/json; domain-model=launchdarkly.semanticpatch");
        if (patched.status >= 400) {
            return apiError(patched);
        }
        Reply started = request("POST", releasesPath(), startBody(noneId, greenId), "beta", "application/json");
        if ((started.status != 200 && started.status != 201) || !started.body.isJsonObject()
                || !started.body.getAsJsonObject().has("phases")) {
            return apiError(started);
        }
        JsonObject summary = summarize(started.body.getAsJsonObject());
        summary.addProperty("started", true);
        return summary;
    }

    /** Stop the active progressive release and roll it back to none. */
    static JsonObject stop() {
        // https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        Reply listed = request(
                "GET",
                releasesPath() + "?queryfilter=kind:equals:progressive&limit=5",
                null,
                "beta",
                "application/json");
        if (listed.status != 200 || !listed.body.isJsonObject()) {
            return apiError(listed);
        }
        JsonObject active = null;
        JsonArray items = array(listed.body.getAsJsonObject(), "items");
        for (JsonElement node : items) {
            if (!node.isJsonObject()) {
                continue;
            }
            JsonObject item = node.getAsJsonObject();
            String status = text(item, "status");
            boolean ended = item.has("endedAt") && !item.get("endedAt").isJsonNull();
            if (!ended && !"completed".equals(status) && !"reverted".equals(status)) {
                active = item;
                break;
            }
        }
        if (active == null || text(active, "id") == null) {
            return error("No active progressive release to stop.", null, "no_active_release");
        }
        JsonObject body = new JsonObject();
        body.addProperty("resolution", "roll_back_all_phases_and_remove_pending_phases");
        body.addProperty("comment", "22-api-progressive-rollout: stop progressive release");
        Reply stopped = request("PUT", releasesPath() + "/" + text(active, "id") + "/stop", body, "beta", "application/json");
        if ((stopped.status != 200 && stopped.status != 201) || !stopped.body.isJsonObject()) {
            return apiError(stopped);
        }
        JsonObject summary = summarize(stopped.body.getAsJsonObject());
        summary.addProperty("stopped", true);
        Boolean on = flagIsOn();
        if (on == null) {
            summary.add("flagOn", JsonNull.INSTANCE);
        } else {
            summary.addProperty("flagOn", on);
        }
        return summary;
    }

    /** Roll back a running release, then turn the flag off. */
    static JsonObject reset() {
        // https://launchdarkly.com/docs/api/feature-flags/update-feature-flag
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        JsonObject stopped = stop();
        if (stopped.has("error") && stopped.get("error").getAsBoolean()
                && !"no_active_release".equals(text(stopped, "code"))) {
            return stopped;
        }
        JsonArray instructions = new JsonArray();
        Reply flagReply = request(
                "GET",
                "/api/v2/flags/" + env("LD_PROJECT_KEY") + "/" + HighlightEval.FLAG_HIGHLIGHT,
                null,
                flagApiVersion(),
                "application/json");
        if (flagReply.status == 200 && flagReply.body.isJsonObject()) {
            instructions = removePhaseRules(flagReply.body.getAsJsonObject());
        }
        JsonObject turnOff = new JsonObject();
        turnOff.addProperty("kind", "turnFlagOff");
        instructions.add(turnOff);
        JsonObject patch = new JsonObject();
        patch.addProperty("environmentKey", env("LD_ENVIRONMENT_KEY"));
        patch.addProperty("comment", "22-api-progressive-rollout: reset, flag off, phase rule removed");
        patch.add("instructions", instructions);
        Reply patched = request(
                "PATCH",
                "/api/v2/flags/" + env("LD_PROJECT_KEY") + "/" + HighlightEval.FLAG_HIGHLIGHT,
                patch,
                flagApiVersion(),
                "application/json; domain-model=launchdarkly.semanticpatch");
        if (patched.status >= 400) {
            return apiError(patched);
        }
        JsonObject summary = latest();
        summary.addProperty("reset", true);
        summary.addProperty("flagOn", false);
        summary.addProperty("active", false);
        return summary;
    }

    static JsonObject latest() {
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        Reply listed = request(
                "GET",
                releasesPath() + "?queryfilter=kind:equals:progressive&limit=1",
                null,
                "beta",
                "application/json");
        if (listed.status != 200 || !listed.body.isJsonObject()) {
            return apiError(listed);
        }
        JsonObject body = listed.body.getAsJsonObject();
        JsonArray items = array(body, "items");
        JsonObject summary;
        if (!items.isEmpty() && items.get(0).isJsonObject()) {
            summary = summarize(items.get(0).getAsJsonObject());
            if (body.has("totalCount") && body.get("totalCount").isJsonPrimitive()) {
                summary.add("totalCount", body.get("totalCount"));
            }
        } else {
            summary = new JsonObject();
            summary.addProperty("configured", true);
            summary.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
            summary.addProperty("status", "none");
            summary.addProperty("metricCount", 0);
            summary.add("steps", new JsonArray());
            summary.addProperty("detail", "No progressive release on this flag yet.");
        }
        Boolean on = flagIsOn();
        if (on == null) {
            summary.add("flagOn", JsonNull.INSTANCE);
        } else {
            summary.addProperty("flagOn", on);
        }
        if (Boolean.FALSE.equals(on)) {
            summary.addProperty("active", false);
        }
        return summary;
    }

    private static JsonObject startBody(String noneId, String greenId) {
        JsonArray steps = new JsonArray();
        for (int percent : ROLLOUT_PERCENTAGES) {
            JsonObject step = new JsonObject();
            step.addProperty("allocation", percent * ALLOCATION_SCALE);
            step.addProperty("durationMillis", stageSeconds() * 1000L);
            steps.add(step);
        }
        JsonObject clause = new JsonObject();
        clause.addProperty("contextKind", "user");
        clause.addProperty("attribute", "kind");
        clause.addProperty("op", "in");
        JsonArray values = new JsonArray();
        values.add("user");
        clause.add("values", values);
        JsonArray clauses = new JsonArray();
        clauses.add(clause);
        JsonObject phase = new JsonObject();
        phase.addProperty("description", "All users");
        phase.add("clauses", clauses);
        phase.add("steps", steps);
        JsonArray phases = new JsonArray();
        phases.add(phase);
        JsonObject body = new JsonObject();
        body.addProperty("originalVariationId", noneId);
        body.addProperty("targetVariationId", greenId);
        body.addProperty("randomizationUnit", "user");
        body.addProperty("cleanupBehavior", "remove_rules_and_update_default_rule");
        body.addProperty("comment", "22-api-progressive-rollout: start progressive release");
        body.add("phases", phases);
        return body;
    }

    private static JsonObject summarize(JsonObject item) {
        JsonArray phases = array(item, "phases");
        JsonObject phase = !phases.isEmpty() && phases.get(0).isJsonObject()
                ? phases.get(0).getAsJsonObject()
                : new JsonObject();
        JsonArray steps = new JsonArray();
        for (JsonElement node : array(phase, "steps")) {
            if (!node.isJsonObject()) {
                continue;
            }
            JsonObject step = node.getAsJsonObject();
            JsonObject view = new JsonObject();
            if (step.has("allocation") && step.get("allocation").isJsonPrimitive()) {
                view.addProperty("percent", step.get("allocation").getAsInt() / ALLOCATION_SCALE);
            } else {
                view.add("percent", JsonNull.INSTANCE);
            }
            if (step.has("durationMillis") && step.get("durationMillis").isJsonPrimitive()) {
                view.addProperty("durationSeconds", step.get("durationMillis").getAsInt() / 1000);
            } else {
                view.add("durationSeconds", JsonNull.INSTANCE);
            }
            steps.add(view);
        }
        Integer index = phase.has("currentStepIndex") && phase.get("currentStepIndex").isJsonPrimitive()
                ? phase.get("currentStepIndex").getAsInt()
                : null;
        Integer current = null;
        if (index != null && index >= 0 && index < steps.size()) {
            JsonObject step = steps.get(index).getAsJsonObject();
            if (step.has("percent") && step.get("percent").isJsonPrimitive()) {
                current = step.get("percent").getAsInt();
            }
        }
        String status = text(item, "status");
        boolean ended = (item.has("endedAt") && !item.get("endedAt").isJsonNull())
                || "completed".equals(status)
                || "reverted".equals(status);
        JsonObject summary = new JsonObject();
        summary.addProperty("configured", true);
        summary.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
        summary.add("kind", orNull(item, "kind"));
        summary.addProperty("status", status);
        summary.add("statusReason", orNull(item, "statusReason"));
        summary.add("randomizationUnit", orNull(item, "randomizationUnit"));
        summary.addProperty("metricCount", array(item, "metrics").size());
        summary.addProperty("hasRule", phase.has("ruleId") && !phase.get("ruleId").isJsonNull());
        if (index == null) {
            summary.add("stepIndex", JsonNull.INSTANCE);
        } else {
            summary.addProperty("stepIndex", index);
        }
        summary.addProperty("stepCount", steps.size());
        if (current == null) {
            summary.add("currentPercent", JsonNull.INSTANCE);
        } else {
            summary.addProperty("currentPercent", current);
        }
        summary.add("steps", steps);
        summary.addProperty("active", !ended);
        return summary;
    }

    private static Boolean flagIsOn() {
        Reply reply = request(
                "GET",
                "/api/v2/flags/" + env("LD_PROJECT_KEY") + "/" + HighlightEval.FLAG_HIGHLIGHT
                        + "?env=" + env("LD_ENVIRONMENT_KEY"),
                null,
                flagApiVersion(),
                "application/json");
        if (reply.status != 200 || !reply.body.isJsonObject()) {
            return null;
        }
        JsonObject environments = reply.body.getAsJsonObject().has("environments")
                && reply.body.getAsJsonObject().get("environments").isJsonObject()
                ? reply.body.getAsJsonObject().getAsJsonObject("environments")
                : new JsonObject();
        if (!environments.has(env("LD_ENVIRONMENT_KEY")) || !environments.get(env("LD_ENVIRONMENT_KEY")).isJsonObject()) {
            return null;
        }
        JsonObject environment = environments.getAsJsonObject(env("LD_ENVIRONMENT_KEY"));
        if (!environment.has("on") || !environment.get("on").isJsonPrimitive()) {
            return null;
        }
        return environment.get("on").getAsBoolean();
    }

    /** Rules left by a stopped release. The next start rejects a duplicate description. */
    private static JsonArray removePhaseRules(JsonObject flag) {
        JsonArray instructions = new JsonArray();
        if (!flag.has("environments") || !flag.get("environments").isJsonObject()) {
            return instructions;
        }
        JsonObject environments = flag.getAsJsonObject("environments");
        String environmentKey = env("LD_ENVIRONMENT_KEY");
        if (!environments.has(environmentKey) || !environments.get(environmentKey).isJsonObject()) {
            return instructions;
        }
        for (JsonElement node : array(environments.getAsJsonObject(environmentKey), "rules")) {
            if (!node.isJsonObject()) {
                continue;
            }
            String ruleId = text(node.getAsJsonObject(), "_id");
            if (ruleId == null) {
                ruleId = text(node.getAsJsonObject(), "id");
            }
            if (ruleId == null) {
                continue;
            }
            JsonObject remove = new JsonObject();
            remove.addProperty("kind", "removeRule");
            remove.addProperty("ruleId", ruleId);
            instructions.add(remove);
        }
        return instructions;
    }

    private static String variationId(JsonObject flag, String value) {
        for (JsonElement node : array(flag, "variations")) {
            if (!node.isJsonObject()) {
                continue;
            }
            JsonObject item = node.getAsJsonObject();
            if (value.equals(text(item, "value")) && text(item, "_id") != null) {
                return text(item, "_id");
            }
        }
        return null;
    }

    private static JsonObject missingConfig() {
        if (!env("LD_API_ACCESS_TOKEN").isEmpty() && !env("LD_PROJECT_KEY").isEmpty()
                && !env("LD_ENVIRONMENT_KEY").isEmpty()) {
            return null;
        }
        JsonObject body = new JsonObject();
        body.addProperty("configured", false);
        body.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
        body.addProperty("detail", "Set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, and LD_ENVIRONMENT_KEY, then restart.");
        return body;
    }

    private static String releasesPath() {
        return "/api/v2/projects/" + env("LD_PROJECT_KEY")
                + "/flags/" + HighlightEval.FLAG_HIGHLIGHT
                + "/environments/" + env("LD_ENVIRONMENT_KEY")
                + "/releases";
    }

    private static String flagApiVersion() {
        String version = env("LD_API_VERSION");
        return version.isEmpty() ? "20240415" : version;
    }

    private static Reply request(String method, String path, JsonElement body, String version, String contentType) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(host() + path))
                    .timeout(Duration.ofSeconds(30))
                    .header("Authorization", env("LD_API_ACCESS_TOKEN"))
                    .header("LD-API-Version", version);
            if ("GET".equals(method)) {
                builder.GET();
            } else if (body == null) {
                builder.method(method, HttpRequest.BodyPublishers.noBody());
            } else {
                builder.header("Content-Type", contentType);
                builder.method(method, HttpRequest.BodyPublishers.ofString(body.toString()));
            }
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            String text = response.body() == null || response.body().isBlank() ? "{}" : response.body();
            JsonElement parsed;
            try {
                parsed = JsonParser.parseString(text);
            } catch (RuntimeException err) {
                JsonObject message = new JsonObject();
                message.addProperty("message", text.substring(0, Math.min(text.length(), 240)));
                parsed = message;
            }
            return new Reply(response.statusCode(), parsed);
        } catch (Exception err) {
            JsonObject message = new JsonObject();
            message.addProperty("message", "Could not reach LaunchDarkly: " + err.getMessage());
            return new Reply(0, message);
        }
    }

    private static JsonObject apiError(Reply reply) {
        String message = reply.body.isJsonObject() ? text(reply.body.getAsJsonObject(), "message") : null;
        String code = reply.body.isJsonObject() ? text(reply.body.getAsJsonObject(), "code") : null;
        String detail = message == null || message.isBlank() ? "LaunchDarkly rejected the request." : message;
        if ("health_checks_failed".equals(code)) {
            detail += " Log in on the grid once so the flag has a user evaluation, then start again.";
        }
        return error(detail, reply.status, code);
    }

    private static JsonObject error(String detail, Integer http, String code) {
        JsonObject body = new JsonObject();
        body.addProperty("configured", true);
        body.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
        body.addProperty("error", true);
        if (http == null) {
            body.add("http", JsonNull.INSTANCE);
        } else {
            body.addProperty("http", http);
        }
        if (code == null) {
            body.add("code", JsonNull.INSTANCE);
        } else {
            body.addProperty("code", code);
        }
        body.addProperty("detail", detail);
        return body;
    }

    private static JsonElement orNull(JsonObject object, String key) {
        return object.has(key) ? object.get(key) : JsonNull.INSTANCE;
    }

    private static JsonArray array(JsonObject object, String key) {
        if (object.has(key) && object.get(key).isJsonArray()) {
            return object.getAsJsonArray(key);
        }
        return new JsonArray();
    }

    private static String text(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull() || !object.get(key).isJsonPrimitive()) {
            return null;
        }
        return object.get(key).getAsString();
    }

    private static String env(String name) {
        String value = System.getenv(name);
        return value == null ? "" : value.trim();
    }

    private record Reply(int status, JsonElement body) {
    }
}

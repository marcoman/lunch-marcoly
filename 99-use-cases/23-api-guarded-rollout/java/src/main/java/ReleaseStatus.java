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
import java.util.ArrayList;
import java.util.List;

/**
 * Read and start the guarded environment release for this example.
 *
 * LaunchDarkly: environment releases — kind guarded
 * https://launchdarkly.com/docs/api/environment-releases
 */
public final class ReleaseStatus {
    private static final int ALLOCATION_SCALE = 1000;
    private static final int[][] ROLLOUT_STEPS = {{10, 120}, {20, 120}, {30, 60}, {50, 60}};
    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

    private ReleaseStatus() {
    }

    static String host() {
        String raw = System.getenv().getOrDefault("LD_API_HOST", "https://app.launchdarkly.com");
        return raw.endsWith("/") ? raw.substring(0, raw.length() - 1) : raw;
    }

    static String env(String name) {
        String value = System.getenv(name);
        return value == null ? "" : value;
    }

    static String flagApiVersion() {
        String value = System.getenv("LD_API_VERSION");
        return value == null || value.isBlank() ? "20240415" : value;
    }

    static JsonArray schedule() {
        JsonArray steps = new JsonArray();
        for (int[] step : ROLLOUT_STEPS) {
            JsonObject item = new JsonObject();
            item.addProperty("percent", step[0]);
            item.addProperty("durationSeconds", step[1]);
            steps.add(item);
        }
        return steps;
    }

    static String targetingUrl() {
        String project = env("LD_PROJECT_KEY");
        String environment = env("LD_ENVIRONMENT_KEY");
        if (project.isEmpty() || environment.isEmpty()) {
            return null;
        }
        return host() + "/projects/" + project + "/flags/" + HighlightEval.FLAG_HIGHLIGHT
                + "/targeting?env=" + environment + "&selected-env=" + environment;
    }

    static JsonObject latest() {
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        Reply reply = request("GET", releasesPath() + "?queryfilter=kind:equals:guarded&limit=1", null, "beta", "application/json");
        if (reply.status == 404) {
            JsonObject summary = new JsonObject();
            summary.addProperty("configured", true);
            summary.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
            summary.addProperty("status", "none");
            summary.addProperty("detail", "No flag yet. Start creates it.");
            summary.addProperty("flagOn", false);
            summary.addProperty("headline", headline(summary));
            return summary;
        }
        if (reply.status != 200 || !reply.body.isJsonObject()) {
            return apiError(reply);
        }
        JsonArray items = array(reply.body.getAsJsonObject(), "items");
        JsonObject summary = items.isEmpty()
                ? noneSummary("No guarded release on this flag yet.")
                : summarize(items.get(0).getAsJsonObject());
        Boolean on = flagIsOn();
        if (on == null) {
            summary.add("flagOn", JsonNull.INSTANCE);
        } else {
            summary.addProperty("flagOn", on);
            if (!on) {
                summary.addProperty("active", false);
            }
        }
        summary.addProperty("headline", headline(summary));
        return summary;
    }

    /** Start the guarded release. Header LD-API-Version: beta. */
    static JsonObject start() {
        // https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        List<String> warnings = ensureMetrics();
        JsonObject flagError = ensureFlag();
        if (flagError != null) {
            return flagError;
        }
        Reply flagReply = request("GET", flagPath(), null, flagApiVersion(), "application/json");
        if (flagReply.status != 200 || !flagReply.body.isJsonObject()) {
            return apiError(flagReply);
        }
        JsonObject flag = flagReply.body.getAsJsonObject();
        String noneId = variationId(flag, "none");
        String greenId = variationId(flag, "green");
        if (noneId == null || greenId == null) {
            return error("The flag is missing the none or green variation.", null, null);
        }
        JsonArray instructions = removeRules(flag);
        JsonObject turnOn = new JsonObject();
        turnOn.addProperty("kind", "turnFlagOn");
        JsonObject fallthrough = new JsonObject();
        fallthrough.addProperty("kind", "updateFallthroughVariationOrRollout");
        fallthrough.addProperty("variationId", noneId);
        instructions.add(turnOn);
        instructions.add(fallthrough);
        JsonObject patch = new JsonObject();
        patch.addProperty("environmentKey", env("LD_ENVIRONMENT_KEY"));
        patch.addProperty("comment", "23-api-guarded-rollout: on, default rule stays none");
        patch.add("instructions", instructions);
        Reply patched = request("PATCH", flagPath(), patch, flagApiVersion(), "application/json; domain-model=launchdarkly.semanticpatch");
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
        summary.addProperty("flagOn", true);
        summary.addProperty("headline", headline(summary));
        if (!warnings.isEmpty()) {
            summary.addProperty("metricDescriptionWarning", String.join(" ", warnings));
        }
        return summary;
    }

    static JsonObject stop() {
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        Reply reply = request("GET", releasesPath() + "?queryfilter=kind:equals:guarded&limit=5", null, "beta", "application/json");
        if (reply.status != 200 || !reply.body.isJsonObject()) {
            return apiError(reply);
        }
        String releaseId = null;
        for (JsonElement element : array(reply.body.getAsJsonObject(), "items")) {
            JsonObject item = element.getAsJsonObject();
            String status = text(item, "status");
            boolean ended = item.has("endedAt") && !item.get("endedAt").isJsonNull();
            if (!ended && !"completed".equals(status) && !"reverted".equals(status) && item.has("id")) {
                releaseId = item.get("id").getAsString();
                break;
            }
        }
        if (releaseId == null) {
            return error("No active guarded release to stop.", null, "no_active_release");
        }
        JsonObject body = new JsonObject();
        body.addProperty("resolution", "roll_back_all_phases_and_remove_pending_phases");
        body.addProperty("comment", "23-api-guarded-rollout: stop guarded release");
        Reply stopped = request("PUT", releasesPath() + "/" + releaseId + "/stop", body, "beta", "application/json");
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
        summary.addProperty("headline", headline(summary));
        return summary;
    }

    static JsonObject reset() {
        JsonObject missing = missingConfig();
        if (missing != null) {
            return missing;
        }
        JsonObject stopped = stop();
        if (stopped.has("error") && stopped.get("error").getAsBoolean()
                && !"no_active_release".equals(text(stopped, "code"))) {
            return stopped;
        }
        Reply flagReply = request("GET", flagPath(), null, flagApiVersion(), "application/json");
        JsonArray instructions = new JsonArray();
        if (flagReply.status == 200 && flagReply.body.isJsonObject()) {
            instructions = removeRules(flagReply.body.getAsJsonObject());
        }
        JsonObject off = new JsonObject();
        off.addProperty("kind", "turnFlagOff");
        instructions.add(off);
        JsonObject patch = new JsonObject();
        patch.addProperty("environmentKey", env("LD_ENVIRONMENT_KEY"));
        patch.addProperty("comment", "23-api-guarded-rollout: reset, flag off, phase rule removed");
        patch.add("instructions", instructions);
        Reply patched = request("PATCH", flagPath(), patch, flagApiVersion(), "application/json; domain-model=launchdarkly.semanticpatch");
        if (patched.status >= 400) {
            return apiError(patched);
        }
        JsonObject summary = latest();
        summary.addProperty("reset", true);
        summary.addProperty("flagOn", false);
        summary.addProperty("active", false);
        summary.addProperty("headline", "Flag is off. Every context receives none.");
        return summary;
    }

    private static JsonObject ensureFlag() {
        Reply existing = request("GET", flagPath(), null, flagApiVersion(), "application/json");
        if (existing.status == 200 && existing.body.isJsonObject()) {
            return null;
        }
        if (existing.status != 404) {
            return apiError(existing);
        }
        JsonObject body = new JsonObject();
        body.addProperty("key", HighlightEval.FLAG_HIGHLIGHT);
        body.addProperty("name", "API guarded grid highlight");
        body.addProperty("description", "Guarded rollout of the grid highlight from none to green, started with the environment releases API. Latency, error rate, and movement are the guardrails.");
        body.addProperty("temporary", false);
        JsonArray tags = new JsonArray();
        for (String tag : new String[]{"grid-navigator", "use-case", "api-guarded-rollout", "environment-release", "guarded-rollout", "string"}) {
            tags.add(tag);
        }
        body.add("tags", tags);
        JsonArray variations = new JsonArray();
        variations.add(variation("none", "No highlight", "Selected cell stays dark. The release starts here."));
        variations.add(variation("green", "Green", "Selected cell turns green. The release moves traffic here."));
        variations.add(variation("yellow", "Yellow", "Yellow highlight. This release does not target it."));
        variations.add(variation("red", "Red", "Red highlight. This release does not target it."));
        variations.add(variation("blue", "Blue", "Blue highlight. This release does not target it."));
        variations.add(variation("purple", "Purple", "Purple highlight. This release does not target it."));
        body.add("variations", variations);
        JsonObject defaults = new JsonObject();
        defaults.addProperty("onVariation", 1);
        defaults.addProperty("offVariation", 0);
        body.add("defaults", defaults);
        Reply created = request("POST", "/api/v2/flags/" + env("LD_PROJECT_KEY"), body, flagApiVersion(), "application/json");
        if (created.status != 200 && created.status != 201) {
            return apiError(created);
        }
        return null;
    }

    private static List<String> ensureMetrics() {
        List<String> warnings = new ArrayList<>();
        String project = env("LD_PROJECT_KEY");
        for (JsonObject definition : Metrics.definitions()) {
            String key = definition.get("key").getAsString();
            String path = "/api/v2/metrics/" + project + "/" + key;
            Reply existing = request("GET", path, null, flagApiVersion(), "application/json");
            if (existing.status == 404) {
                Reply created = request("POST", "/api/v2/metrics/" + project, Metrics.createBody(definition), flagApiVersion(), "application/json");
                if (created.status != 200 && created.status != 201) {
                    warnings.add(key + ": create failed (" + created.status + ") " + messageOf(created.body));
                }
                continue;
            }
            if (existing.status != 200 || !existing.body.isJsonObject()) {
                warnings.add(key + ": could not read the metric (" + existing.status + ")");
                continue;
            }
            String description = definition.get("description").getAsString();
            if (description.equals(text(existing.body.getAsJsonObject(), "description"))) {
                continue;
            }
            JsonArray patch = new JsonArray();
            JsonObject op = new JsonObject();
            op.addProperty("op", "replace");
            op.addProperty("path", "/description");
            op.addProperty("value", description);
            patch.add(op);
            Reply patched = request("PATCH", path, patch, flagApiVersion(), "application/json");
            if (patched.status >= 400) {
                warnings.add(key + ": description was not updated (" + patched.status + ") " + messageOf(patched.body));
            }
        }
        return warnings;
    }

    private static JsonObject startBody(String noneId, String greenId) {
        JsonObject body = new JsonObject();
        body.addProperty("originalVariationId", noneId);
        body.addProperty("targetVariationId", greenId);
        body.addProperty("randomizationUnit", "user");
        body.addProperty("cleanupBehavior", "remove_rules_and_update_default_rule");
        body.addProperty("comment", "23-api-guarded-rollout: start guarded release");
        JsonArray checks = new JsonArray();
        checks.add("metric_events_any");
        checks.add("metric_events_with_context");
        body.add("bypassHealthChecks", checks);
        JsonArray metrics = new JsonArray();
        for (JsonObject definition : Metrics.definitions()) {
            JsonObject metric = new JsonObject();
            metric.addProperty("metricKey", definition.get("key").getAsString());
            metric.addProperty("autoRollback", true);
            metrics.add(metric);
        }
        body.add("metrics", metrics);
        JsonObject clause = new JsonObject();
        clause.addProperty("contextKind", "user");
        clause.addProperty("attribute", "kind");
        clause.addProperty("op", "in");
        JsonArray values = new JsonArray();
        values.add("user");
        clause.add("values", values);
        JsonArray clauses = new JsonArray();
        clauses.add(clause);
        JsonArray steps = new JsonArray();
        for (int[] step : ROLLOUT_STEPS) {
            JsonObject item = new JsonObject();
            item.addProperty("allocation", step[0] * ALLOCATION_SCALE);
            item.addProperty("durationMillis", step[1] * 1000);
            steps.add(item);
        }
        JsonObject phase = new JsonObject();
        phase.addProperty("description", "All users");
        phase.add("clauses", clauses);
        phase.add("steps", steps);
        JsonArray phases = new JsonArray();
        phases.add(phase);
        body.add("phases", phases);
        return body;
    }

    private static JsonObject summarize(JsonObject item) {
        JsonArray phases = array(item, "phases");
        JsonObject phase = phases.isEmpty() ? new JsonObject() : phases.get(0).getAsJsonObject();
        JsonArray steps = new JsonArray();
        for (JsonElement element : array(phase, "steps")) {
            JsonObject step = element.getAsJsonObject();
            JsonObject view = new JsonObject();
            if (step.has("allocation") && step.get("allocation").isJsonPrimitive()) {
                view.addProperty("percent", step.get("allocation").getAsDouble() / ALLOCATION_SCALE);
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
        JsonArray regressed = new JsonArray();
        if (phase.has("metricStatuses") && phase.get("metricStatuses").isJsonObject()) {
            for (String key : phase.getAsJsonObject("metricStatuses").keySet()) {
                if ("regressed".equals(text(phase.getAsJsonObject("metricStatuses"), key))) {
                    regressed.add(key);
                }
            }
        }
        String status = text(item, "status");
        boolean ended = (item.has("endedAt") && !item.get("endedAt").isJsonNull())
                || "completed".equals(status) || "reverted".equals(status);
        JsonObject summary = new JsonObject();
        summary.addProperty("configured", true);
        summary.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
        copy(summary, "kind", item);
        copy(summary, "status", item);
        copy(summary, "statusReason", item);
        summary.addProperty("metricCount", array(item, "metrics").size());
        summary.add("regressedMetrics", regressed);
        if (phase.has("currentStepIndex") && phase.get("currentStepIndex").isJsonPrimitive()) {
            summary.addProperty("stepIndex", phase.get("currentStepIndex").getAsInt());
        } else {
            summary.add("stepIndex", JsonNull.INSTANCE);
        }
        summary.addProperty("stepCount", steps.size());
        summary.add("steps", steps);
        summary.addProperty("active", !ended);
        summary.addProperty("headline", headline(summary));
        return summary;
    }

    private static String headline(JsonObject item) {
        if (item.has("flagOn") && item.get("flagOn").isJsonPrimitive() && !item.get("flagOn").getAsBoolean()) {
            return "Flag is off. Every context receives none.";
        }
        String status = text(item, "status");
        if (status == null || "none".equals(status)) {
            String detail = text(item, "detail");
            return detail == null ? "No guarded release yet." : detail;
        }
        String names = joined(array(item, "regressedMetrics"));
        boolean rolled = "reverted".equals(status) || (item.has("stopped") && item.get("stopped").getAsBoolean());
        if (rolled && ("reverted_regression_detected".equals(text(item, "statusReason")) || !names.isEmpty())) {
            return "Rolled back to none. " + (names.isEmpty() ? "A guardrail" : names) + " regressed.";
        }
        if (rolled) {
            return "Rolled back to none.";
        }
        if ("waiting".equals(status) && "waiting_regression_detected".equals(text(item, "statusReason"))) {
            return "Paused. " + (names.isEmpty() ? "A guardrail" : names) + " regressed.";
        }
        if ("completed".equals(status)) {
            return "Completed.";
        }
        if ("in_progress".equals(status) || (item.has("active") && item.get("active").getAsBoolean())) {
            return "Monitoring.";
        }
        return status;
    }

    private static Boolean flagIsOn() {
        if (env("LD_API_ACCESS_TOKEN").isEmpty() || env("LD_PROJECT_KEY").isEmpty() || env("LD_ENVIRONMENT_KEY").isEmpty()) {
            return null;
        }
        Reply reply = request("GET", flagPath() + "?env=" + env("LD_ENVIRONMENT_KEY"), null, flagApiVersion(), "application/json");
        if (reply.status != 200 || !reply.body.isJsonObject()) {
            return null;
        }
        JsonObject environments = reply.body.getAsJsonObject().has("environments")
                && reply.body.getAsJsonObject().get("environments").isJsonObject()
                ? reply.body.getAsJsonObject().getAsJsonObject("environments") : new JsonObject();
        if (!environments.has(env("LD_ENVIRONMENT_KEY")) || !environments.get(env("LD_ENVIRONMENT_KEY")).isJsonObject()) {
            return null;
        }
        JsonObject environment = environments.getAsJsonObject(env("LD_ENVIRONMENT_KEY"));
        return environment.has("on") && environment.get("on").getAsBoolean();
    }

    private static JsonArray removeRules(JsonObject flag) {
        JsonArray instructions = new JsonArray();
        if (!flag.has("environments") || !flag.get("environments").isJsonObject()) {
            return instructions;
        }
        JsonObject environments = flag.getAsJsonObject("environments");
        if (!environments.has(env("LD_ENVIRONMENT_KEY")) || !environments.get(env("LD_ENVIRONMENT_KEY")).isJsonObject()) {
            return instructions;
        }
        for (JsonElement element : array(environments.getAsJsonObject(env("LD_ENVIRONMENT_KEY")), "rules")) {
            JsonObject rule = element.getAsJsonObject();
            String ruleId = rule.has("_id") && rule.get("_id").isJsonPrimitive()
                    ? rule.get("_id").getAsString()
                    : text(rule, "id");
            if (ruleId == null) {
                continue;
            }
            JsonObject instruction = new JsonObject();
            instruction.addProperty("kind", "removeRule");
            instruction.addProperty("ruleId", ruleId);
            instructions.add(instruction);
        }
        return instructions;
    }

    private static String variationId(JsonObject flag, String value) {
        for (JsonElement element : array(flag, "variations")) {
            JsonObject item = element.getAsJsonObject();
            if (value.equals(text(item, "value")) && item.has("_id") && item.get("_id").isJsonPrimitive()) {
                return item.get("_id").getAsString();
            }
        }
        return null;
    }

    private static String flagPath() {
        return "/api/v2/flags/" + env("LD_PROJECT_KEY") + "/" + HighlightEval.FLAG_HIGHLIGHT;
    }

    private static String releasesPath() {
        return "/api/v2/projects/" + env("LD_PROJECT_KEY") + "/flags/" + HighlightEval.FLAG_HIGHLIGHT
                + "/environments/" + env("LD_ENVIRONMENT_KEY") + "/releases";
    }

    private static JsonObject missingConfig() {
        if (!env("LD_API_ACCESS_TOKEN").isEmpty() && !env("LD_PROJECT_KEY").isEmpty() && !env("LD_ENVIRONMENT_KEY").isEmpty()) {
            return null;
        }
        JsonObject body = new JsonObject();
        body.addProperty("configured", false);
        body.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
        body.addProperty("detail", "Set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, and LD_ENVIRONMENT_KEY, then restart.");
        return body;
    }

    private static JsonObject noneSummary(String detail) {
        JsonObject summary = new JsonObject();
        summary.addProperty("configured", true);
        summary.addProperty("flagKey", HighlightEval.FLAG_HIGHLIGHT);
        summary.addProperty("status", "none");
        summary.addProperty("metricCount", 0);
        summary.add("steps", new JsonArray());
        summary.addProperty("detail", detail);
        return summary;
    }

    private static JsonObject variation(String value, String name, String description) {
        JsonObject item = new JsonObject();
        item.addProperty("value", value);
        item.addProperty("name", name);
        item.addProperty("description", description);
        return item;
    }

    private static Reply request(String method, String path, JsonElement body, String version, String contentType) {
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(host() + path))
                .timeout(Duration.ofSeconds(20))
                .header("Authorization", env("LD_API_ACCESS_TOKEN"))
                .header("LD-API-Version", version);
        if (body == null) {
            builder.method(method, HttpRequest.BodyPublishers.noBody());
        } else {
            builder.method(method, HttpRequest.BodyPublishers.ofString(body.toString())).header("Content-Type", contentType);
        }
        try {
            HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            String raw = response.body() == null ? "" : response.body();
            JsonElement payload = raw.isBlank() ? new JsonObject() : JsonParser.parseString(raw);
            return new Reply(response.statusCode(), payload);
        } catch (Exception err) {
            JsonObject message = new JsonObject();
            message.addProperty("message", "Could not reach LaunchDarkly: " + err.getMessage());
            return new Reply(0, message);
        }
    }

    private static JsonObject apiError(Reply reply) {
        String code = reply.body.isJsonObject() ? text(reply.body.getAsJsonObject(), "code") : null;
        String detail = messageOf(reply.body);
        if (detail == null || detail.isBlank()) {
            detail = "LaunchDarkly rejected the request.";
        }
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

    private static String messageOf(JsonElement body) {
        if (body != null && body.isJsonObject() && body.getAsJsonObject().has("message") && body.getAsJsonObject().get("message").isJsonPrimitive()) {
            return body.getAsJsonObject().get("message").getAsString();
        }
        return body == null ? "" : body.toString();
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

    private static void copy(JsonObject target, String key, JsonObject source) {
        if (!source.has(key) || source.get(key).isJsonNull()) {
            target.add(key, JsonNull.INSTANCE);
        } else if (source.get(key).isJsonPrimitive()) {
            target.add(key, source.get(key));
        } else {
            target.add(key, source.get(key));
        }
    }

    private static String joined(JsonArray values) {
        List<String> names = new ArrayList<>();
        for (JsonElement element : values) {
            if (element.isJsonPrimitive()) {
                names.add(element.getAsString());
            }
        }
        return String.join(", ", names);
    }

    private record Reply(int status, JsonElement body) {
    }
}

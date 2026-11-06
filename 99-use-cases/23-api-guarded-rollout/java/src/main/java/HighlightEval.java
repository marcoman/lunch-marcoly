import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * Evaluate api-guarded-grid-highlight for one username.
 * The schedule lives in an environment release. This only reads the variation.
 *
 * LaunchDarkly: string flag variation
 * https://launchdarkly.com/docs/sdk/features/evaluations
 */
public final class HighlightEval {
    static final String FLAG_HIGHLIGHT = "api-guarded-grid-highlight";
    private static final Set<String> VALID_COLORS =
            Set.of("yellow", "red", "blue", "green", "purple");
    private static LDClient client;

    private HighlightEval() {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            return;
        }
        client = new LDClient(sdkKey, new LDConfig.Builder().build());
        if (!client.isInitialized()) {
            try {
                client.close();
            } catch (IOException ignored) {
            }
            client = null;
        }
    }

    static synchronized void close() {
        if (client != null) {
            try {
                client.close();
            } catch (IOException ignored) {
            }
            client = null;
        }
    }

    static boolean ready() {
        return client != null && client.isInitialized();
    }

    static JsonObject evaluate(String username) {
        if (!ready() || username == null || username.isBlank()) {
            return build(username == null ? "" : username, "none", "ERROR", null);
        }
        LDContext context = context(username);
        EvaluationDetail<String> detail = client.stringVariationDetail(FLAG_HIGHLIGHT, context, "none");
        String kind = detail.getReason() == null ? "UNKNOWN" : detail.getReason().getKind().name();
        int rawIndex = detail.getVariationIndex();
        Integer index = rawIndex == EvaluationDetail.NO_VARIATION ? null : rawIndex;
        return build(username, detail.getValue(), kind, index);
    }

    static LDContext context(String username) {
        return LDContext.builder(username).name(username).build();
    }

    /**
     * Green contexts report the slider. None contexts report 50 ms.
     * LaunchDarkly: custom events with a numeric metric value.
     * https://launchdarkly.com/docs/sdk/features/events
     */
    static JsonObject trackObserved(String username, double latencyMs) {
        int green = 0;
        int none = 0;
        for (String name : Metrics.sampleUsernames(username)) {
            String served = evaluate(name).get("highlightColor").getAsString();
            double value = "green".equals(served) ? latencyMs : Metrics.HEALTHY_LATENCY_MS;
            LDContext context = context(name);
            client.trackMetric(Metrics.EVENT_LATENCY, context, LDValue.ofNull(), value);
            client.trackMetric(Metrics.EVENT_MOVEMENT, context, LDValue.ofNull(), 1);
            if ("green".equals(served)) {
                green += 1;
            } else {
                none += 1;
            }
        }
        client.flush();
        JsonObject body = new JsonObject();
        body.addProperty("tracked", true);
        body.addProperty("latencyMs", latencyMs);
        body.addProperty("healthyMs", Metrics.HEALTHY_LATENCY_MS);
        body.addProperty("aboveThreshold", latencyMs > Metrics.LATENCY_THRESHOLD_MS);
        body.addProperty("greenContexts", green);
        body.addProperty("noneContexts", none);
        body.addProperty("movement", 1);
        body.addProperty("colorErrors", 0);
        body.addProperty("latencyEvent", Metrics.EVENT_LATENCY);
        body.addProperty("movementEvent", Metrics.EVENT_MOVEMENT);
        return body;
    }

    private static JsonObject build(String username, String raw, String reasonKind, Integer variationIndex) {
        String color = String.valueOf(raw == null ? "none" : raw).trim().toLowerCase(Locale.ROOT);
        if (!VALID_COLORS.contains(color)) {
            color = "none";
        }
        JsonObject reason = new JsonObject();
        reason.addProperty("kind", reasonKind);
        JsonObject ldContext = new JsonObject();
        ldContext.addProperty("kind", "user");
        ldContext.addProperty("key", username);
        ldContext.addProperty("name", username);
        JsonObject body = new JsonObject();
        body.addProperty("username", username);
        body.addProperty("flagKey", FLAG_HIGHLIGHT);
        body.addProperty("flagValue", raw == null ? "none" : raw);
        body.addProperty("highlightColor", color);
        body.addProperty("colorLabel", "none".equals(color) ? "(no-color)" : "(" + color + ")");
        body.add("variationIndex", variationIndex == null ? JsonNull.INSTANCE : new JsonPrimitive(variationIndex));
        body.add("reason", reason);
        body.add("ldContext", ldContext);
        return body;
    }
}

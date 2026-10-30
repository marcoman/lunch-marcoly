import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * Evaluate api-progressive-grid-highlight for one username.
 * The schedule lives in an environment release. This only reads the variation.
 *
 * LaunchDarkly: string flag variation
 * https://launchdarkly.com/docs/sdk/features/evaluations
 */
public final class HighlightEval {
    static final String FLAG_HIGHLIGHT = "api-progressive-grid-highlight";
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

    static JsonObject evaluate(String username) {
        if (client == null || username == null || username.isBlank()) {
            return build(username == null ? "" : username, "none", "ERROR", null);
        }
        LDContext context = LDContext.builder(username).name(username).build();
        EvaluationDetail<String> detail = client.stringVariationDetail(FLAG_HIGHLIGHT, context, "none");
        String kind = detail.getReason() == null ? "UNKNOWN" : detail.getReason().getKind().name();
        return build(username, detail.getValue(), kind, detail.getVariationIndex());
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

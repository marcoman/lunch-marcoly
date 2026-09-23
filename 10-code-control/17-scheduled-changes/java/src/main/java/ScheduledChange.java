import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Evaluate the scheduled-change flag; LaunchDarkly applies the remote schedule.
 * Feature flag evaluation: https://launchdarkly.com/docs/sdk/features/evaluating
 */
final class ScheduledChange {
    static final String FLAG_KEY = "enable-grid-selection-highlight-sched";
    static final String DEFAULT_VALUE = "none";
    private static final Set<String> VALID = Set.of("none", "green");
    private static LDClient client;

    private ScheduledChange() {
    }

    static synchronized void init() {
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — highlight defaults to none.");
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize.");
        }
    }

    static synchronized void close() {
        if (client == null) return;
        try {
            client.close();
        } catch (IOException ignored) {
        }
        client = null;
    }

    static String normalizeUsername(String raw) {
        String username = raw == null ? "" : raw.trim();
        if (username.isEmpty()) throw new IllegalArgumentException("Username is required.");
        return username;
    }

    static Map<String, Object> evaluate(String rawUsername) {
        String username = normalizeUsername(rawUsername);
        Map<String, Object> contextPayload = new LinkedHashMap<>();
        contextPayload.put("kind", "user");
        contextPayload.put("key", username);
        contextPayload.put("name", username);

        if (client == null || !client.isInitialized()) {
            Map<String, Object> result = baseResult(DEFAULT_VALUE, contextPayload);
            result.put("variationIndex", null);
            result.put("reason", Map.of("kind", "ERROR", "errorKind", "CLIENT_NOT_READY"));
            return result;
        }

        LDContext context = LDContext.builder(username).kind("user").name(username).build();
        EvaluationDetail<String> detail =
                client.stringVariationDetail(FLAG_KEY, context, DEFAULT_VALUE);
        String value = VALID.contains(detail.getValue()) ? detail.getValue() : DEFAULT_VALUE;
        Map<String, Object> result = baseResult(value, contextPayload);
        result.put("variationIndex", detail.getVariationIndex() < 0 ? null : detail.getVariationIndex());
        result.put("reason", reasonPayload(detail.getReason()));
        return result;
    }

    private static Map<String, Object> baseResult(
            String value, Map<String, Object> contextPayload) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("flagKey", FLAG_KEY);
        result.put("flagValue", value);
        result.put("highlightColor", value);
        result.put("ldContext", contextPayload);
        return result;
    }

    private static Map<String, Object> reasonPayload(EvaluationReason reason) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", reason.getKind().toString());
        if (reason.getKind() == EvaluationReason.Kind.ERROR && reason.getErrorKind() != null) {
            payload.put("errorKind", reason.getErrorKind().toString());
        }
        return payload;
    }
}

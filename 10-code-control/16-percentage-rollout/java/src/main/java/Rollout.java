import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Evaluate the static percentage rollout without implementing bucketing in app code.
 * LaunchDarkly percentage rollout: https://launchdarkly.com/docs/home/flags/rollouts
 */
final class Rollout {
    static final String FLAG_KEY = "enable-grid-selection-highlight-pct";
    static final String DEFAULT_VALUE = "none";
    private static final Set<String> VALID = Set.of("none", "green");
    private static LDClient client;

    private Rollout() {
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
        if (client == null) {
            return;
        }
        try {
            client.close();
        } catch (IOException ignored) {
        }
        client = null;
    }

    static String normalizeUsername(String raw) {
        String username = raw == null ? "" : raw.trim();
        if (username.isEmpty()) {
            throw new IllegalArgumentException("Username is required.");
        }
        return username;
    }

    static Map<String, Object> evaluate(String rawUsername) {
        String username = normalizeUsername(rawUsername);
        Map<String, Object> contextPayload = new LinkedHashMap<>();
        contextPayload.put("kind", "user");
        contextPayload.put("key", username);
        contextPayload.put("name", username);

        if (client == null || !client.isInitialized()) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("flagKey", FLAG_KEY);
            result.put("flagValue", DEFAULT_VALUE);
            result.put("highlightColor", DEFAULT_VALUE);
            result.put("variationIndex", null);
            result.put("reason", Map.of("kind", "ERROR", "errorKind", "CLIENT_NOT_READY"));
            result.put("ldContext", contextPayload);
            result.put("stickyNote", "Safe SDK default; LaunchDarkly client is not ready.");
            return result;
        }

        LDContext context = LDContext.builder(username).kind("user").name(username).build();
        EvaluationDetail<String> detail = client.stringVariationDetail(FLAG_KEY, context, DEFAULT_VALUE);
        String raw = detail.getValue();
        String value = VALID.contains(raw) ? raw : DEFAULT_VALUE;

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("flagKey", FLAG_KEY);
        result.put("flagValue", value);
        result.put("highlightColor", value);
        result.put("variationIndex", variationIndex(detail));
        result.put("reason", reasonPayload(detail.getReason()));
        result.put("ldContext", contextPayload);
        result.put(
                "stickyNote",
                "LaunchDarkly buckets this user context key deterministically. "
                        + "The same key keeps the same assignment while weights stay unchanged.");
        return result;
    }

    private static Integer variationIndex(EvaluationDetail<?> detail) {
        int index = detail.getVariationIndex();
        return index < 0 ? null : index;
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

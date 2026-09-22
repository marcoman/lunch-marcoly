import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.Set;

/**
 * Evaluate the static percentage rollout without implementing bucketing in app code.
 * LaunchDarkly percentage rollout: https://launchdarkly.com/docs/home/flags/rollouts
 */
public final class FlagEvaluator {
    static final String FLAG_KEY = "enable-grid-selection-highlight-pct";
    static final String DEFAULT_VALUE = "none";
    private static final Set<String> VALID = Set.of("none", "green");
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            close();
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

    static FlagValues evaluate(String rawUsername) {
        String username = rawUsername == null ? "" : rawUsername.trim();
        if (username.isEmpty() || client == null || !client.isInitialized()) {
            return FlagValues.offline(username);
        }
        LDContext context = LDContext.builder(username).kind("user").name(username).build();
        EvaluationDetail<String> detail = client.stringVariationDetail(FLAG_KEY, context, DEFAULT_VALUE);
        String raw = detail.getValue();
        String value = VALID.contains(raw) ? raw : DEFAULT_VALUE;
        int index = detail.getVariationIndex();
        return new FlagValues(
                username,
                value,
                value,
                index < 0 ? null : index,
                reasonKind(detail.getReason()));
    }

    private static String reasonKind(EvaluationReason reason) {
        return reason.getKind().toString();
    }

    record FlagValues(
            String username,
            String flagValue,
            String highlightColor,
            Integer variationIndex,
            String reasonKind
    ) {
        static FlagValues offline(String username) {
            return new FlagValues(username, DEFAULT_VALUE, DEFAULT_VALUE, null, "ERROR");
        }

        String variationText() {
            return variationIndex == null ? "default" : String.valueOf(variationIndex);
        }
    }
}

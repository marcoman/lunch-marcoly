import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;

/**
 * LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
 */
public final class FlagEvaluator {
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flags default to off.");
            return;
        }
        client = new LDClient(sdkKey, new LDConfig.Builder().build());
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flags default to off.");
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

    static FlagValues evaluate(String username) {
        if (client == null || username == null || username.isBlank()) {
            return FlagValues.off(username);
        }
        LDContext context = LDContext.builder(username).build();
        boolean highlight = client.boolVariation(HighlightStyle.FLAG_HIGHLIGHT, context, false);
        boolean contextHighlight = client.boolVariation(HighlightStyle.FLAG_CONTEXT, context, false);
        boolean showCount = client.boolVariation(HighlightStyle.FLAG_COUNT, context, false);
        HighlightStyle.Style style = HighlightStyle.resolve(username, highlight, contextHighlight);
        return new FlagValues(highlight, contextHighlight, showCount, style.highlightColor(), style.cohortLabel());
    }

    record FlagValues(
            boolean highlightEnabled,
            boolean contextHighlight,
            boolean showMoveCount,
            String highlightColor,
            String cohortLabel) {

        static FlagValues off(String username) {
            HighlightStyle.Style style = HighlightStyle.resolve(username, false, false);
            return new FlagValues(false, false, false, style.highlightColor(), style.cohortLabel());
        }
    }
}

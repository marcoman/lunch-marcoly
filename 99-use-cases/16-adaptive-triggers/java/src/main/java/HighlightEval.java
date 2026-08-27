import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * Own the server-side LaunchDarkly client used for flag evaluation and custom
 * metric events. The SDK key and event transport never cross into the browser.
 *
 * LaunchDarkly: string variation, contexts, and numeric custom events.
 * https://launchdarkly.com/docs/sdk/features/evaluations
 * https://launchdarkly.com/docs/sdk/features/events
 */
public final class HighlightEval {
    static final String FLAG_HIGHLIGHT = "enable-adaptive-grid-highlight";
    static final String EVENT_KEY = "adaptive-grid-nav-latency";

    private static final Set<String> VALID_COLORS = Set.of("green");
    private static LDClient client;

    private HighlightEval() {
    }

    record FlagValues(String username, String flagValue, String highlightColor, String colorLabel) {
    }

    /**
     * Initialize the LaunchDarkly Java server-side SDK. Missing or invalid SDK
     * configuration deliberately leaves evaluation at the code fallback.
     */
    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY is unset — evaluation stays at code fallback none.");
            return;
        }
        client = new LDClient(sdkKey, new LDConfig.Builder().build());
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly initialization failed — evaluation stays at code fallback none.");
            close();
        }
    }

    static synchronized boolean isInitialized() {
        return client != null;
    }

    /**
     * Evaluate the string feature flag for a user context.
     * LaunchDarkly: stringVariation with the code fallback {@code none}.
     */
    static synchronized FlagValues evaluate(String username) {
        String safeUsername = username == null ? "" : username;
        if (client == null || safeUsername.isBlank()) {
            return buildResponse(safeUsername, "none");
        }
        String raw = client.stringVariation(FLAG_HIGHLIGHT, buildContext(safeUsername), "none");
        return buildResponse(safeUsername, raw);
    }

    /**
     * Emit one numeric custom metric event and flush it before acknowledging the
     * API call, matching the Node lab's observable event-delivery behavior.
     */
    static synchronized void trackLatency(String username, double latencyMs) {
        if (client == null) {
            throw new IllegalStateException("LD_SDK_KEY is missing or the SDK did not initialize.");
        }
        LDValue data = LDValue.buildObject()
                .put("source", "16-adaptive-triggers")
                .build();
        client.trackMetric(EVENT_KEY, buildContext(username), data, latencyMs);
        client.flush();
    }

    /**
     * Build the same user context for evaluations and metric attribution.
     * LaunchDarkly: single-kind context with kind {@code user}.
     */
    static LDContext buildContext(String username) {
        return LDContext.builder(username).kind("user").build();
    }

    static synchronized void close() {
        if (client == null) {
            return;
        }
        try {
            client.close();
        } catch (IOException ignored) {
            // Shutdown is best effort.
        } finally {
            client = null;
        }
    }

    private static FlagValues buildResponse(String username, String raw) {
        String value = String.valueOf(raw == null ? "none" : raw).trim().toLowerCase(Locale.ROOT);
        String highlightColor = VALID_COLORS.contains(value) ? value : "none";
        String colorLabel = "none".equals(highlightColor) ? "(no-color)" : "(" + highlightColor + ")";
        return new FlagValues(username, value, highlightColor, colorLabel);
    }
}

import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * Evaluate configure-grid-selection-green-highlight for grid highlight color.
 */
public final class HighlightEval {
    static final String FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";

    private static final Set<String> VALID_COLORS =
            Set.of("yellow", "red", "blue", "green", "purple");

    private static LDClient client;

    private HighlightEval() {
    }

    record FlagValues(String username, String flagValue, String highlightColor, String colorLabel) {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — highlight defaults to none.");
            return;
        }
        client = new LDClient(sdkKey, new LDConfig.Builder().build());
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — highlight defaults to none.");
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
            return buildResponse(username == null ? "" : username, "none");
        }
        LDContext context = LDContext.builder(username).build();
        String raw = client.stringVariation(FLAG_HIGHLIGHT, context, "none");
        return buildResponse(username, raw);
    }

    static String colorLabel(String highlightColor) {
        return "none".equals(highlightColor) ? "(no-color)" : "(" + highlightColor + ")";
    }

    private static String normalizeHighlightColor(String raw) {
        String color = String.valueOf(raw == null ? "none" : raw).trim().toLowerCase(Locale.ROOT);
        return VALID_COLORS.contains(color) ? color : "none";
    }

    private static FlagValues buildResponse(String username, String raw) {
        String color = normalizeHighlightColor(raw);
        String flagValue = raw == null || raw.isBlank() ? "none" : raw.trim();
        return new FlagValues(username, flagValue, color, colorLabel(color));
    }
}

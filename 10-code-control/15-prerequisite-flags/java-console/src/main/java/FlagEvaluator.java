import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.Set;

/**
 * Evaluate parent and child independently; LaunchDarkly enforces the prerequisite.
 * https://launchdarkly.com/docs/home/flags/prereqs
 */
public final class FlagEvaluator {
    static final String FLAG_HIGHLIGHT = "enable-grid-selection-highlight-prereq";
    static final String FLAG_COUNT = "show-navigation-move-count-prereq";
    private static final Set<String> VALID_COLORS = Set.of(
            "green", "yellow", "red", "blue", "purple", "pink");
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flags use safe defaults.");
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize.");
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
        String username = rawUsername == null ? "" : rawUsername.trim().toLowerCase();
        if (username.isEmpty()) {
            return FlagValues.offline("");
        }
        LDContext context = LDContext.builder(username).kind("user").build();
        EvaluationDetail<String> parentDetail = client == null
                ? null
                : client.stringVariationDetail(FLAG_HIGHLIGHT, context, "none");
        EvaluationDetail<Boolean> childDetail = client == null
                ? null
                : client.boolVariationDetail(FLAG_COUNT, context, false);
        String parentValue = parentDetail == null ? "none" : parentDetail.getValue();
        boolean childValue = childDetail != null && Boolean.TRUE.equals(childDetail.getValue());
        String parentReason = parentDetail == null ? "OFFLINE" : formatReason(parentDetail.getReason());
        String childReason = childDetail == null ? "OFFLINE" : formatReason(childDetail.getReason());
        String color = VALID_COLORS.contains(parentValue) ? parentValue : "none";
        return new FlagValues(username, color, childValue, parentValue, parentReason, childValue, childReason);
    }

    private static String formatReason(EvaluationReason reason) {
        String kind = reason.getKind().toString();
        if (reason.getKind() == EvaluationReason.Kind.PREREQUISITE_FAILED
                && reason.getPrerequisiteKey() != null) {
            return kind + " (" + reason.getPrerequisiteKey() + ")";
        }
        return kind;
    }

    record FlagValues(
            String username,
            String highlightColor,
            boolean showMoveCount,
            Object parentValue,
            String parentReason,
            boolean childValue,
            String childReason
    ) {
        static FlagValues offline(String username) {
            return new FlagValues(username, "none", false, "none", "OFFLINE", false, "OFFLINE");
        }
    }
}

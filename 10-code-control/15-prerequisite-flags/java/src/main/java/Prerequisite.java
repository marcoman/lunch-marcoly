import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Evaluate the parent and dependent flags. LaunchDarkly enforces the prerequisite.
 * https://launchdarkly.com/docs/home/flags/prereqs
 */
final class Prerequisite {
    static final String FLAG_HIGHLIGHT = "enable-grid-selection-highlight-prereq";
    static final String FLAG_COUNT = "show-navigation-move-count-prereq";
    static final Set<String> VALID_COLORS = Set.of(
            "green", "yellow", "red", "blue", "purple", "pink");
    private static LDClient client;

    private Prerequisite() {
    }

    static synchronized void init() {
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flags use safe defaults.");
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
        String username = raw == null ? "" : raw.trim().toLowerCase();
        if (username.isEmpty()) {
            throw new IllegalArgumentException("username is required");
        }
        return username;
    }

    static Map<String, Object> evaluate(String rawUsername) {
        String username = normalizeUsername(rawUsername);
        LDContext context = LDContext.builder(username).kind("user").build();
        EvaluationDetail<String> parentDetail = client == null
                ? null
                : client.stringVariationDetail(FLAG_HIGHLIGHT, context, "none");
        EvaluationDetail<Boolean> childDetail = client == null
                ? null
                : client.boolVariationDetail(FLAG_COUNT, context, false);

        Object parentValue = parentDetail == null ? "none" : parentDetail.getValue();
        boolean childValue = childDetail != null && Boolean.TRUE.equals(childDetail.getValue());
        Map<String, Object> parentReason = parentDetail == null
                ? Map.of("kind", "OFFLINE")
                : reasonPayload(parentDetail.getReason());
        Map<String, Object> childReason = childDetail == null
                ? Map.of("kind", "OFFLINE")
                : reasonPayload(childDetail.getReason());
        boolean prerequisiteFailed = "PREREQUISITE_FAILED".equals(childReason.get("kind"));

        Map<String, Object> parent = new LinkedHashMap<>();
        parent.put("key", FLAG_HIGHLIGHT);
        parent.put("value", parentValue);
        parent.put("variationIndex", variationIndex(parentDetail));
        parent.put("reason", parentReason);

        Map<String, Object> child = new LinkedHashMap<>();
        child.put("key", FLAG_COUNT);
        child.put("value", childValue);
        child.put("variationIndex", variationIndex(childDetail));
        child.put("reason", childReason);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("username", username);
        result.put("highlightColor", highlightColor(parentValue));
        result.put("showMoveCount", childValue);
        result.put("prerequisiteMet", client != null && "green".equals(parentValue) && !prerequisiteFailed);
        result.put("ldContext", Map.of("kind", "user", "key", username));
        result.put("parent", parent);
        result.put("child", child);
        return result;
    }

    private static Integer variationIndex(EvaluationDetail<?> detail) {
        if (detail == null) {
            return null;
        }
        int index = detail.getVariationIndex();
        return index < 0 ? null : index;
    }

    private static String highlightColor(Object value) {
        if (!(value instanceof String text)) {
            return "none";
        }
        String candidate = text.trim().toLowerCase();
        return VALID_COLORS.contains(candidate) ? candidate : "none";
    }

    private static Map<String, Object> reasonPayload(EvaluationReason reason) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", reason.getKind().toString());
        if (reason.getKind() == EvaluationReason.Kind.RULE_MATCH) {
            payload.put("ruleIndex", reason.getRuleIndex());
            if (reason.getRuleId() != null) {
                payload.put("ruleId", reason.getRuleId());
            }
        }
        if (reason.getKind() == EvaluationReason.Kind.PREREQUISITE_FAILED
                && reason.getPrerequisiteKey() != null) {
            payload.put("prerequisiteKey", reason.getPrerequisiteKey());
        }
        if (reason.getKind() == EvaluationReason.Kind.ERROR && reason.getErrorKind() != null) {
            payload.put("errorKind", reason.getErrorKind().toString());
        }
        return payload;
    }
}

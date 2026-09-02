import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Evaluate the partner-badge flag with a user + organization multi-context.
 * LaunchDarkly multi-contexts: https://launchdarkly.com/docs/home/flags/multi-contexts
 */
final class Partner {
    static final String FLAG_KEY = "show-partner-org-badge";
    private static final Map<String, String> ORG_LABELS = Map.of(
            "acme", "Acme",
            "globex", "Globex");
    private static final Set<String> ORGS = ORG_LABELS.keySet();
    private static LDClient client;

    private Partner() {
    }

    static synchronized void init() {
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — partner badge stays false.");
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — partner badge stays false.");
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
        String username = raw == null ? "" : raw.trim().toLowerCase();
        if (username.isEmpty()) {
            throw new IllegalArgumentException("username is required");
        }
        return username;
    }

    static String normalizeOrg(String raw) {
        String org = raw == null ? "" : raw.trim().toLowerCase();
        if (!ORGS.contains(org)) {
            throw new IllegalArgumentException("org must be acme or globex");
        }
        return org;
    }

    /**
     * Build user + organization multi-context. Do not put org on the user.
     * https://launchdarkly.com/docs/sdk/features/user-context
     */
    static LDContext buildMultiContext(String username, String org) {
        LDContext user = LDContext.builder(username).kind("user").build();
        LDContext organization = LDContext.builder(org)
                .kind("organization")
                .set("name", ORG_LABELS.get(org))
                .build();
        return LDContext.createMulti(user, organization);
    }

    static Map<String, Object> evaluate(String rawUsername, String rawOrg) {
        String username = normalizeUsername(rawUsername);
        String org = normalizeOrg(rawOrg);
        LDContext context = buildMultiContext(username, org);
        EvaluationDetail<Boolean> detail = client == null
                ? null
                : client.boolVariationDetail(FLAG_KEY, context, false);
        boolean partner = detail != null && Boolean.TRUE.equals(detail.getValue());

        Map<String, Object> userCtx = new LinkedHashMap<>();
        userCtx.put("key", username);
        Map<String, Object> orgCtx = new LinkedHashMap<>();
        orgCtx.put("key", org);
        orgCtx.put("name", ORG_LABELS.get(org));
        Map<String, Object> shown = new LinkedHashMap<>();
        shown.put("kind", "multi");
        shown.put("user", userCtx);
        shown.put("organization", orgCtx);
        shown.put("note", "Org is a separate context kind, not a user attribute.");

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("username", username);
        result.put("org", org);
        result.put("orgLabel", ORG_LABELS.get(org));
        result.put("partner", partner);
        result.put("ldContext", shown);
        result.put("variationIndex", detail == null ? null : detail.getVariationIndex());
        result.put("reason", detail == null
                ? Map.of("kind", "OFFLINE")
                : reasonPayload(detail.getReason()));
        return result;
    }

    private static Map<String, Object> reasonPayload(EvaluationReason reason) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", reason.getKind().toString());
        if (reason.getKind() == EvaluationReason.Kind.RULE_MATCH) {
            payload.put("ruleIndex", reason.getRuleIndex());
            if (reason.getRuleId() != null) payload.put("ruleId", reason.getRuleId());
        }
        if (reason.getKind() == EvaluationReason.Kind.ERROR && reason.getErrorKind() != null) {
            payload.put("errorKind", reason.getErrorKind().toString());
        }
        return payload;
    }
}

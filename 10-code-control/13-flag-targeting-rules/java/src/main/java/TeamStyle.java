import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Evaluate the team-label string flag using a public team context attribute.
 * LaunchDarkly targeting rules: https://launchdarkly.com/docs/home/flags/target-rules
 */
final class TeamStyle {
    static final String FLAG_KEY = "configure-team-label-style";
    private static final String PLAIN = "plain";
    private static final Map<String, String> LABELS = Map.of(
            "", "No team",
            "red", "Team Red",
            "blue", "Team Blue",
            "yellow", "Team Yellow");
    private static final Map<String, String> COLORS = new LinkedHashMap<>();
    private static final Set<String> STYLES = Set.of(
            PLAIN, "colored-red", "colored-blue", "colored-yellow");
    private static LDClient client;

    static {
        COLORS.put(PLAIN, null);
        COLORS.put("colored-red", "red");
        COLORS.put("colored-blue", "blue");
        COLORS.put("colored-yellow", "yellow");
    }

    private TeamStyle() {
    }

    static synchronized void init() {
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flag uses plain default.");
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flag uses plain default.");
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

    static String normalizeTeam(String raw) {
        String team = raw == null ? "" : raw.trim().toLowerCase();
        if (!LABELS.containsKey(team)) {
            throw new IllegalArgumentException("team must be empty, red, blue, or yellow");
        }
        return team;
    }

    /**
     * Build a user context and omit team entirely for No team.
     * Context attributes: https://launchdarkly.com/docs/home/flags/context-attributes
     */
    static LDContext buildContext(String username, String team) {
        var builder = LDContext.builder(username);
        if (!team.isEmpty()) builder.set("team", team);
        return builder.build();
    }

    static Map<String, Object> evaluate(String username, String rawTeam) {
        String team = normalizeTeam(rawTeam);
        LDContext context = buildContext(username, team);
        EvaluationDetail<String> detail = client == null
                ? null
                : client.stringVariationDetail(FLAG_KEY, context, PLAIN);
        String candidate = detail == null ? PLAIN : detail.getValue();
        String style = STYLES.contains(candidate) ? candidate : PLAIN;
        String color = COLORS.get(style);
        Map<String, String> attributes = team.isEmpty() ? Map.of() : Map.of("team", team);

        Map<String, Object> shownContext = new LinkedHashMap<>();
        shownContext.put("kind", "user");
        shownContext.put("key", username);
        shownContext.put("attributes", attributes);
        shownContext.put("teamAttribute", team.isEmpty() ? null : team);
        shownContext.put("teamOmitted", team.isEmpty());
        shownContext.put("privateAttributes", List.of());
        shownContext.put("note", "team is public; No team omits the attribute so rules skip to fallthrough.");

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("team", team);
        result.put("teamLabel", LABELS.get(team));
        result.put("style", style);
        result.put("colored", color != null);
        result.put("cssColor", color);
        result.put("ldContext", shownContext);
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

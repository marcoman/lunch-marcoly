import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.LDValueType;
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
    // LaunchDarkly: flag key=configure-team-label-style
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-team-label-style

    static final String FLAG_KEY = "configure-team-label-style";
    // JSON flag: words on screen. Style values stay colored-red/blue/yellow/plain.
    // https://launchdarkly.com/docs/sdk/features/flag-types
    static final String LABELS_KEY = "configure-team-display-labels";
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

        LabelRead labels = readLabels(context);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("team", team);
        result.put("teamLabel", labels.words.get(team.isEmpty() ? "none" : team));
        result.put("labels", labels.words);
        result.put("style", style);
        result.put("colored", color != null);
        result.put("cssColor", color);
        result.put("ldContext", shownContext);
        result.put("variationIndex", detail == null ? null : detail.getVariationIndex());
        result.put("reason", detail == null
                ? Map.of("kind", "OFFLINE")
                : reasonPayload(detail.getReason()));
        result.put("labelEvaluation", labels.evaluation);
        return result;
    }

    private static Map<String, String> defaultLabels() {
        Map<String, String> labels = new LinkedHashMap<>();
        labels.put("none", LABELS.get(""));
        labels.put("red", LABELS.get("red"));
        labels.put("blue", LABELS.get("blue"));
        labels.put("yellow", LABELS.get("yellow"));
        return labels;
    }

    /** One JSON-flag read. Missing keys keep the built-in words. */
    private static LabelRead readLabels(LDContext context) {
        Map<String, String> labels = defaultLabels();
        Map<String, Object> evaluation = new LinkedHashMap<>();
        evaluation.put("flagKey", LABELS_KEY);
        if (client == null) {
            evaluation.put("value", labels);
            evaluation.put("variationIndex", null);
            evaluation.put("reason", Map.of("kind", "OFFLINE"));
            return new LabelRead(labels, evaluation);
        }
        EvaluationDetail<LDValue> detail = client.jsonValueVariationDetail(
                LABELS_KEY, context, LDValue.parse(Json.stringify(labels)));
        LDValue value = detail.getValue();
        if (value != null && value.getType() == LDValueType.OBJECT) {
            for (String key : List.of("none", "red", "blue", "yellow")) {
                LDValue text = value.get(key);
                if (text != null && text.getType() == LDValueType.STRING && !text.stringValue().isBlank()) {
                    labels.put(key, text.stringValue().trim());
                }
            }
        }
        evaluation.put("value", labels);
        evaluation.put("variationIndex", detail.getVariationIndex());
        evaluation.put("reason", reasonPayload(detail.getReason()));
        return new LabelRead(labels, evaluation);
    }

    private record LabelRead(Map<String, String> words, Map<String, Object> evaluation) {
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

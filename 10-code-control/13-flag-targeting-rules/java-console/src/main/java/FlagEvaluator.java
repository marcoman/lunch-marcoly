import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.Map;
import java.util.Set;

/**
 * Evaluates the team-label string flag against a public team context attribute.
 * LaunchDarkly targeting rules: https://launchdarkly.com/docs/home/flags/target-rules
 */
public final class FlagEvaluator {
    private static final String FLAG_KEY = "configure-team-label-style";
    private static final String PLAIN = "plain";
    private static final Map<String, String> LABELS = Map.of(
            "", "No team",
            "red", "Team Red",
            "blue", "Team Blue",
            "yellow", "Team Yellow");
    private static final Set<String> STYLES = Set.of(
            PLAIN, "colored-red", "colored-blue", "colored-yellow");
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        if (client != null) return;
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flag uses plain default.");
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flag uses plain default.");
            close();
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

    /**
     * Evaluate the string variation; omit team entirely for the No team choice.
     * Context attributes: https://launchdarkly.com/docs/home/flags/context-attributes
     */
    static TeamStyle evaluate(String username, String team) {
        String normalizedTeam = normalizeTeam(team);
        var contextBuilder = LDContext.builder(username);
        if (!normalizedTeam.isEmpty()) {
            contextBuilder.set("team", normalizedTeam);
        }
        LDContext context = contextBuilder.build();
        String candidate = client == null
                ? PLAIN
                : client.stringVariation(FLAG_KEY, context, PLAIN);
        String style = STYLES.contains(candidate) ? candidate : PLAIN;
        return new TeamStyle(LABELS.get(normalizedTeam), style);
    }

    private static String normalizeTeam(String rawTeam) {
        String team = rawTeam == null ? "" : rawTeam.trim().toLowerCase();
        if (!LABELS.containsKey(team)) {
            throw new IllegalArgumentException("team must be empty, red, blue, or yellow");
        }
        return team;
    }

    record TeamStyle(String teamLabel, String style) {
    }
}

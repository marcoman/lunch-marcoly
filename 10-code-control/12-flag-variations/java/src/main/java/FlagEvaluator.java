import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * LaunchDarkly capability: Multivariate flag evaluation + anonymous contexts
 * See: https://launchdarkly.com/docs/sdk/features/flag-types
 * See: https://launchdarkly.com/docs/sdk/features/anonymous
 */
public final class FlagEvaluator {
    // LaunchDarkly: flag key=configure-navigation-count-label name="Configure: navigation count label" kind=string
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-navigation-count-label

    private static final String FLAG_COUNT_LABEL = "configure-navigation-count-label";
    // LaunchDarkly: flag key=configure-lucky-number name="Configure: lucky number" kind=number
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-lucky-number

    private static final String FLAG_LUCKY_NUMBER = "configure-lucky-number";
    // LaunchDarkly: flag key=configure-max-navigation-moves name="Configure: max navigation moves" kind=json
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-max-navigation-moves

    private static final String FLAG_MAX_MOVES = "configure-max-navigation-moves";
    private static final String DEFAULT_COUNT_LABEL = "Count";
    private static final int DEFAULT_LUCKY_NUMBER = 0;
    private static final int DEFAULT_MAX_MOVES = 100;

    private static final String HOST_OS = HostOs.detectHostOs();
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flags use defaults.");
            return;
        }
        LDConfig config = new LDConfig.Builder()
                .events(com.launchdarkly.sdk.server.Components.sendEvents()
                        .privateAttributes(HostOs.HOST_OS_ATTR))
                .build();
        client = new LDClient(sdkKey, config);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flags use defaults.");
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
            return FlagValues.defaults(username);
        }
        LDContext anonContext = HostOs.buildAnonymousContext(HOST_OS);
        LDContext userContext = HostOs.buildUserContext(username);

        boolean showEmoji = client.boolVariation(HostOs.FLAG_ANON_OS_EMOJI, anonContext, false);
        String countLabel = client.stringVariation(FLAG_COUNT_LABEL, userContext, DEFAULT_COUNT_LABEL);
        int luckyNumber = client.intVariation(FLAG_LUCKY_NUMBER, userContext, DEFAULT_LUCKY_NUMBER);
        LDValue maxMovesRaw = client.jsonValueVariation(
                FLAG_MAX_MOVES,
                userContext,
                LDValue.buildObject().put("maxMoves", DEFAULT_MAX_MOVES).build());
        int maxMoves = parseMaxMoves(maxMovesRaw);
        String osEmoji = HostOs.osEmojiFor(HOST_OS, showEmoji);

        return new FlagValues(
                countLabel == null || countLabel.isBlank() ? DEFAULT_COUNT_LABEL : countLabel,
                luckyNumber,
                maxMoves,
                osEmoji,
                username);
    }

    private static int parseMaxMoves(LDValue raw) {
        if (raw == null || raw.isNull()) {
            return DEFAULT_MAX_MOVES;
        }
        return raw.get("maxMoves").intValue();
    }

    record FlagValues(String countLabel, int luckyNumber, int maxMoves, String osEmoji, String username) {
        static FlagValues defaults(String username) {
            return new FlagValues(
                    DEFAULT_COUNT_LABEL,
                    DEFAULT_LUCKY_NUMBER,
                    DEFAULT_MAX_MOVES,
                    "",
                    username == null ? "" : username);
        }

        /**
         * Include both evaluated values and the user/anonymous contexts shown by the lab.
         * LaunchDarkly contexts + private attributes:
         * https://launchdarkly.com/docs/home/observability/contexts
         */
        String toJson() {
            Map<String, Object> user = new LinkedHashMap<>();
            user.put("kind", "user");
            user.put("key", username);
            user.put("note", "String, number, and JSON flags evaluate against this user context.");

            Map<String, Object> anonymous = new LinkedHashMap<>();
            anonymous.put("kind", "user");
            anonymous.put("key", HostOs.ANONYMOUS_CONTEXT_KEY);
            anonymous.put("anonymous", true);
            anonymous.put("attributes", Map.of(HostOs.HOST_OS_ATTR, HOST_OS));
            anonymous.put("privateAttributes", List.of(HostOs.HOST_OS_ATTR));
            anonymous.put("flagKey", HostOs.FLAG_ANON_OS_EMOJI);
            anonymous.put(
                    "note",
                    HostOs.FLAG_ANON_OS_EMOJI + " uses this anonymous context. "
                            + HostOs.HOST_OS_ATTR
                            + " is private (targeting only; redacted from analytics).");

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("countLabel", countLabel);
            response.put("luckyNumber", luckyNumber);
            response.put("maxMoves", maxMoves);
            response.put("osEmoji", osEmoji);
            response.put("ldContext", Map.of("user", user, "anonymous", anonymous));
            return Json.stringify(response);
        }
    }
}
